// src/managers/ticket-manager.js
import { logger } from '../utils/logger.js';
import { ErrorHandler, ValidationError, OperationError, ErrorCodes } from '../utils/error-handler.js';

export class TicketManager {
  constructor(redisManager, dbManager, qdrantManager, workLogManager, statsManager, batchManager) {
    this.redis = redisManager;
    this.db = dbManager;
    this.qdrant = qdrantManager;
    this.workLogManager = workLogManager;
    this.statsManager = statsManager;
    this.batchManager = batchManager;
    this.activeTicketsKey = 'tickets:active';
    this.closedTicketsKey = 'tickets:closed';
    this.completedStatuses = ['CLOSED', 'CANCELLED'];
  }

  generateShortId() {
    return Math.random().toString(36).substring(2, 8);
  }

  async create(data) {
    return ErrorHandler.wrapOperation(async () => {
      const {
        title,
        priority,
        type,
        category,
        reporter,
        description = null,
        assignee = 'unassigned',
        tags = [],
        acceptance_criteria = [],
        estimated_hours = 0,
        system = null,
      } = data;

      // Validate required fields
      ErrorHandler.validateRequired(data, ['title', 'priority', 'type', 'category', 'reporter'], {
        operation: 'createTicket'
      });

      const timestamp = new Date().toISOString();
      const ticketId = `${timestamp.split('T')[0].replace(/-/g, '')}-${reporter.toUpperCase()}-${this.generateShortId()}`;

      const ticketData = {
        ticket_id: ticketId,
        title,
        description,
        priority,
        type,
        category,
        system,
        reporter,
        assignee,
        tags,
        acceptance_criteria,
        estimated_hours,
        status: 'OPEN',
        created_at: timestamp,
        updated_at: timestamp,
      };

      try {
        // Store in Redis with error handling
        await this.redis.hSet(`ticket:${ticketId}`, ticketData);
        await this.redis.client.zAdd(this.activeTicketsKey, { score: Date.now(), value: ticketId });
        
        logger.info('Ticket created successfully', {
          ticketId,
          type,
          priority,
          reporter,
          assignee
        });
        
        return {
          success: true,
          ticket_id: ticketId,
          message: `Ticket ${ticketId} created successfully.`,
          ticket: ticketData,
        };
      } catch (error) {
        logger.error('Failed to create ticket', {
          ticketId,
          error: error.message,
          type,
          reporter
        });
        
        // Clean up any partial state
        try {
          await this.redis.del(`ticket:${ticketId}`);
          await this.redis.client.zRem(this.activeTicketsKey, ticketId);
        } catch (cleanupError) {
          logger.warn('Failed to clean up partial ticket creation', {
            ticketId,
            cleanupError: cleanupError.message
          });
        }
        
        throw new OperationError(
          `Failed to create ticket: ${error.message}`,
          'createTicket',
          { ticketId, type, reporter }
        );
      }
    }, 'createTicket', { type: data.type, reporter: data.reporter })();
  }

  async update(data) {
    const { ticket_id, status, ...updates } = data;
    if (!ticket_id) {
      throw new Error('ticket_id is required for updates.');
    }

    const redisKey = `ticket:${ticket_id}`;

    try {
      const oldStatus = await this.redis.client.hGet(redisKey, 'status');
      if (!oldStatus) {
        throw new Error(`Ticket not found: ${ticket_id}`);
      }

      const newStatus = status || oldStatus;

      const updateData = {
        ...updates,
        status: newStatus,
        updated_at: new Date().toISOString(),
      };

      await this.redis.hSet(redisKey, updateData);

      const wasCompleted = this.completedStatuses.includes(oldStatus);
      const isCompleted = this.completedStatuses.includes(newStatus);

      if (isCompleted && !wasCompleted) {
        logger.info(`[TICKET DEBUG] Ticket ${ticket_id} is being closed. Old status: ${oldStatus}, New status: ${newStatus}`);
        const ticketToArchive = await this.redis.client.hGetAll(redisKey);
        logger.info(`[TICKET DEBUG] Retrieved ticket data for archiving:`, JSON.stringify(ticketToArchive, null, 2));
        
        // Use PostgreSQL transaction for data integrity during ticket closure
        const transactionId = await this.db.beginTransaction();
        
        try {
          // 1. Archive to PostgreSQL within transaction
          logger.info(`[TICKET DEBUG] Archiving to PostgreSQL...`);
          await this.db.insertWithTransaction('tickets', {
            ...ticketToArchive,
            tags: JSON.stringify(ticketToArchive.tags),
            acceptance_criteria: JSON.stringify(ticketToArchive.acceptance_criteria),
          }, transactionId);
          logger.info(`[TICKET DEBUG] Ticket ${ticket_id} archived to PostgreSQL successfully.`);

          // 2. Embed and store in Qdrant
          logger.info(`[TICKET DEBUG] Starting Qdrant embedding process...`);
          await this.qdrant.embedAndStoreTicket(ticketToArchive);
          logger.info(`[TICKET DEBUG] Qdrant embedding process completed.`);

          // 3. Perform Redis operations
          logger.info(`[TICKET DEBUG] Updating Redis indexes...`);
          await this.redis.client.zRem(this.activeTicketsKey, ticket_id);
          await this.redis.client.zAdd(this.closedTicketsKey, { score: Date.now(), value: ticket_id });
          await this.redis.client.expire(redisKey, 3600);
          logger.info(`[TICKET DEBUG] Ticket ${ticket_id} closed and set to expire in 1 hour.`);

          // Commit the database transaction
          await this.db.commitTransaction(transactionId);
          logger.info(`[TICKET DEBUG] Transaction committed for ticket ${ticket_id}`);
        } catch (archiveError) {
          // Rollback the database transaction
          await this.db.rollbackTransaction(transactionId);
          logger.error(`[TICKET DEBUG] Failed to archive ticket ${ticket_id}, rolling back:`, archiveError);
          
          // Revert Redis status change since archival failed
          await this.redis.hSet(redisKey, { status: oldStatus });
          
          throw archiveError;
        }
      } else if (!isCompleted && wasCompleted) {
        await this.redis.client.zRem(this.closedTicketsKey, ticket_id);
        await this.redis.client.zAdd(this.activeTicketsKey, { score: Date.now(), value: ticket_id });
        await this.redis.client.persist(redisKey);
        logger.info(`Ticket ${ticket_id} re-opened and TTL removed.`);
      }

      const updatedTicket = await this.redis.client.hGetAll(redisKey);

      logger.info(`Ticket updated successfully: ${ticket_id}`);
      return {
        success: true,
        ticket_id,
        message: `Ticket ${ticket_id} updated.`,
        ticket: updatedTicket,
      };
    } catch (error) {
      logger.error(`Failed to update ticket: ${ticket_id}`, error);
      throw error;
    }
  }

  async query(data) {
    const { ticket_id } = data;

    try {
      if (ticket_id) {
        const ticketData = await this.redis.client.hGetAll(`ticket:${ticket_id}`);
        if (Object.keys(ticketData).length === 0) {
          return { success: true, tickets: [], message: `Ticket ${ticket_id} not found.` };
        }
        return { success: true, tickets: [ticketData] };
      }

      const ticketIds = await this.redis.client.zRange(this.activeTicketsKey, 0, -1);
      if (ticketIds.length === 0) {
        return { success: true, tickets: [] };
      }

      const pipeline = this.redis.client.multi();
      ticketIds.forEach(id => pipeline.hGetAll(`ticket:${id}`));
      const results = await pipeline.exec();

      return { success: true, tickets: results };
    } catch (error) {
      logger.error('Failed to query tickets:', error);
      throw error;
    }
  }

  async delete(data) {
    const { ticket_id } = data;
    if (!ticket_id) {
      throw new Error('ticket_id is required for deletion.');
    }

    const redisKey = `ticket:${ticket_id}`;

    try {
      const delResult = await this.redis.client.del(redisKey);
      if (delResult === 0) {
        throw new Error(`Ticket not found for deletion: ${ticket_id}`);
      }
      
      await this.redis.client.zRem(this.activeTicketsKey, ticket_id);
      await this.redis.client.zRem(this.closedTicketsKey, ticket_id);

      logger.info(`Ticket deleted successfully: ${ticket_id}`);
      return {
        success: true,
        ticket_id,
        message: `Ticket ${ticket_id} deleted.`,
      };
    } catch (error) {
      logger.error(`Failed to delete ticket: ${ticket_id}`, error);
      throw error;
    }
  }

  /**
   * Log work for a ticket
   * @param {object} data - Work log data
   * @returns {object} - Work log result
   */
  async logWork(data) {
    if (!this.workLogManager) {
      throw new Error('Work log manager not available');
    }
    return this.workLogManager.createWorkLog(data);
  }

  /**
   * Get work logs for a ticket
   * @param {object} data - Query data
   * @returns {object} - Work logs result
   */
  async getWorkLogs(data) {
    if (!this.workLogManager) {
      throw new Error('Work log manager not available');
    }
    
    const { ticket_id, user_id } = data;
    
    if (ticket_id) {
      return this.workLogManager.getWorkLogsByTicket(ticket_id);
    } else if (user_id) {
      return this.workLogManager.getWorkLogsByUser(user_id, data);
    } else {
      throw new Error('Either ticket_id or user_id is required');
    }
  }

  /**
   * Get ticket statistics
   * @param {object} data - Filter data
   * @returns {object} - Statistics result
   */
  async getStats(data) {
    if (!this.statsManager) {
      throw new Error('Stats manager not available');
    }
    return this.statsManager.getTicketStats(data);
  }

  /**
   * Perform batch operations
   * @param {object} data - Batch operation data
   * @returns {object} - Batch operation result
   */
  async batchUpdate(data) {
    if (!this.batchManager) {
      throw new Error('Batch manager not available');
    }
    
    const { operation, ...operationData } = data;
    
    switch (operation) {
      case 'update_tickets':
        return this.batchManager.batchUpdateTickets(operationData);
      case 'create_work_logs':
        return this.batchManager.batchCreateWorkLogs(operationData);
      default:
        throw new Error(`Unknown batch operation: ${operation}`);
    }
  }
}
