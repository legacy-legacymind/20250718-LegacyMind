// src/managers/work-log-manager.js
import { logger } from '../utils/logger.js';
import { ErrorHandler, ValidationError, OperationError } from '../utils/error-handler.js';

export class WorkLogManager {
  constructor(redisManager, dbManager) {
    this.redis = redisManager;
    this.db = dbManager;
  }

  /**
   * Create a new work log entry
   * @param {object} data - Work log data
   * @returns {object} - Created work log
   */
  async createWorkLog(data) {
    return ErrorHandler.wrapOperation(async () => {
      const {
        ticket_id,
        user_id,
        hours_worked,
        work_date,
        description,
        work_type = 'DEVELOPMENT',
        billable = true,
        metadata = {}
      } = data;

      // Validate required fields
      ErrorHandler.validateRequired(data, ['ticket_id', 'user_id', 'hours_worked'], {
        operation: 'createWorkLog'
      });

      // Validate hours_worked is positive
      if (hours_worked <= 0) {
        throw new ValidationError('hours_worked must be positive', 'createWorkLog', {
          hours_worked
        });
      }

      const workLogData = {
        ticket_id,
        user_id,
        hours_worked: parseFloat(hours_worked),
        work_date: work_date || new Date().toISOString().split('T')[0],
        description,
        work_type,
        billable,
        metadata: JSON.stringify(metadata)
      };

      try {
        // Insert into PostgreSQL
        const result = await this.db.insert('work_logs', workLogData);
        const logId = result.log_id;

        // Cache in Redis for quick access
        const cacheKey = `work_log:${logId}`;
        await this.redis.hSet(cacheKey, {
          ...workLogData,
          log_id: logId,
          created_at: new Date().toISOString()
        });

        // Set expiration for cache (24 hours)
        await this.redis.client.expire(cacheKey, 86400);

        // Update ticket's work log index
        await this.redis.client.sAdd(`ticket:${ticket_id}:work_logs`, logId);

        logger.info('Work log created successfully', {
          logId,
          ticketId: ticket_id,
          userId: user_id,
          hoursWorked: hours_worked
        });

        return {
          success: true,
          log_id: logId,
          message: 'Work log created successfully',
          work_log: {
            ...workLogData,
            log_id: logId,
            created_at: new Date().toISOString()
          }
        };
      } catch (error) {
        logger.error('Failed to create work log', {
          error: error.message,
          ticketId: ticket_id,
          userId: user_id
        });
        throw new OperationError(
          `Failed to create work log: ${error.message}`,
          'createWorkLog',
          { ticket_id, user_id }
        );
      }
    }, 'createWorkLog', { ticket_id: data.ticket_id, user_id: data.user_id })();
  }

  /**
   * Get work logs for a ticket
   * @param {string} ticketId - Ticket ID
   * @returns {array} - Array of work logs
   */
  async getWorkLogsByTicket(ticketId) {
    return ErrorHandler.wrapOperation(async () => {
      if (!ticketId) {
        throw new ValidationError('ticket_id is required', 'getWorkLogsByTicket');
      }

      try {
        // Try to get from cache first
        const cachedLogIds = await this.redis.client.sMembers(`ticket:${ticketId}:work_logs`);
        
        if (cachedLogIds.length > 0) {
          const pipeline = this.redis.client.multi();
          cachedLogIds.forEach(logId => {
            pipeline.hGetAll(`work_log:${logId}`);
          });
          const cachedLogs = await pipeline.exec();
          
          // If all logs are cached, return them
          if (cachedLogs.every(log => log && Object.keys(log).length > 0)) {
            return {
              success: true,
              work_logs: cachedLogs.map(log => ({
                ...log,
                metadata: JSON.parse(log.metadata || '{}')
              }))
            };
          }
        }

        // Fallback to database
        const workLogs = await this.db.query(
          'SELECT * FROM work_logs WHERE ticket_id = $1 ORDER BY work_date DESC, created_at DESC',
          [ticketId]
        );

        return {
          success: true,
          work_logs: workLogs.map(log => ({
            ...log,
            metadata: JSON.parse(log.metadata || '{}')
          }))
        };
      } catch (error) {
        logger.error('Failed to get work logs by ticket', {
          ticketId,
          error: error.message
        });
        throw new OperationError(
          `Failed to get work logs: ${error.message}`,
          'getWorkLogsByTicket',
          { ticketId }
        );
      }
    }, 'getWorkLogsByTicket', { ticketId })();
  }

  /**
   * Get work logs for a user
   * @param {string} userId - User ID
   * @param {object} options - Query options
   * @returns {array} - Array of work logs
   */
  async getWorkLogsByUser(userId, options = {}) {
    return ErrorHandler.wrapOperation(async () => {
      if (!userId) {
        throw new ValidationError('user_id is required', 'getWorkLogsByUser');
      }

      const {
        startDate,
        endDate,
        limit = 100,
        offset = 0
      } = options;

      try {
        let query = 'SELECT * FROM work_logs WHERE user_id = $1';
        const params = [userId];

        if (startDate) {
          query += ' AND work_date >= $' + (params.length + 1);
          params.push(startDate);
        }

        if (endDate) {
          query += ' AND work_date <= $' + (params.length + 1);
          params.push(endDate);
        }

        query += ' ORDER BY work_date DESC, created_at DESC';
        query += ' LIMIT $' + (params.length + 1) + ' OFFSET $' + (params.length + 2);
        params.push(limit, offset);

        const workLogs = await this.db.query(query, params);

        return {
          success: true,
          work_logs: workLogs.map(log => ({
            ...log,
            metadata: JSON.parse(log.metadata || '{}')
          })),
          total: workLogs.length,
          offset,
          limit
        };
      } catch (error) {
        logger.error('Failed to get work logs by user', {
          userId,
          error: error.message
        });
        throw new OperationError(
          `Failed to get work logs: ${error.message}`,
          'getWorkLogsByUser',
          { userId }
        );
      }
    }, 'getWorkLogsByUser', { userId })();
  }

  /**
   * Update a work log entry
   * @param {string} logId - Work log ID
   * @param {object} updates - Fields to update
   * @returns {object} - Updated work log
   */
  async updateWorkLog(logId, updates) {
    return ErrorHandler.wrapOperation(async () => {
      if (!logId) {
        throw new ValidationError('log_id is required', 'updateWorkLog');
      }

      try {
        // Validate hours_worked if provided
        if (updates.hours_worked !== undefined && updates.hours_worked <= 0) {
          throw new ValidationError('hours_worked must be positive', 'updateWorkLog');
        }

        const updateData = {
          ...updates,
          updated_at: new Date().toISOString()
        };

        // If metadata is provided, stringify it
        if (updateData.metadata) {
          updateData.metadata = JSON.stringify(updateData.metadata);
        }

        // Update in database
        await this.db.update('work_logs', updateData, { log_id: logId });

        // Update cache
        const cacheKey = `work_log:${logId}`;
        await this.redis.hSet(cacheKey, updateData);

        // Get updated work log
        const updatedWorkLog = await this.db.query(
          'SELECT * FROM work_logs WHERE log_id = $1',
          [logId]
        );

        if (updatedWorkLog.length === 0) {
          throw new OperationError('Work log not found', 'updateWorkLog', { logId });
        }

        const workLog = {
          ...updatedWorkLog[0],
          metadata: JSON.parse(updatedWorkLog[0].metadata || '{}')
        };

        logger.info('Work log updated successfully', { logId });

        return {
          success: true,
          log_id: logId,
          message: 'Work log updated successfully',
          work_log: workLog
        };
      } catch (error) {
        logger.error('Failed to update work log', {
          logId,
          error: error.message
        });
        throw new OperationError(
          `Failed to update work log: ${error.message}`,
          'updateWorkLog',
          { logId }
        );
      }
    }, 'updateWorkLog', { logId })();
  }

  /**
   * Delete a work log entry
   * @param {string} logId - Work log ID
   * @returns {object} - Deletion result
   */
  async deleteWorkLog(logId) {
    return ErrorHandler.wrapOperation(async () => {
      if (!logId) {
        throw new ValidationError('log_id is required', 'deleteWorkLog');
      }

      try {
        // Get work log before deletion
        const workLog = await this.db.query(
          'SELECT * FROM work_logs WHERE log_id = $1',
          [logId]
        );

        if (workLog.length === 0) {
          throw new OperationError('Work log not found', 'deleteWorkLog', { logId });
        }

        const workLogData = workLog[0];

        // Delete from database
        await this.db.delete('work_logs', { log_id: logId });

        // Remove from cache
        const cacheKey = `work_log:${logId}`;
        await this.redis.del(cacheKey);

        // Remove from ticket's work log index
        await this.redis.client.sRem(`ticket:${workLogData.ticket_id}:work_logs`, logId);

        logger.info('Work log deleted successfully', { logId });

        return {
          success: true,
          log_id: logId,
          message: 'Work log deleted successfully'
        };
      } catch (error) {
        logger.error('Failed to delete work log', {
          logId,
          error: error.message
        });
        throw new OperationError(
          `Failed to delete work log: ${error.message}`,
          'deleteWorkLog',
          { logId }
        );
      }
    }, 'deleteWorkLog', { logId })();
  }
}