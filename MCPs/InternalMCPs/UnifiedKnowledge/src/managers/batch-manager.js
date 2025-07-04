// src/managers/batch-manager.js
import { logger } from '../utils/logger.js';
import { ErrorHandler, ValidationError, OperationError } from '../utils/error-handler.js';

export class BatchManager {
  constructor(redisManager, dbManager) {
    this.redis = redisManager;
    this.db = dbManager;
    this.defaultBatchSize = 100;
    this.maxBatchSize = 500;
  }

  /**
   * Perform batch ticket updates
   * @param {object} data - Batch operation data
   * @returns {object} - Batch operation result
   */
  async batchUpdateTickets(data) {
    return ErrorHandler.wrapOperation(async () => {
      const {
        tickets,
        updates,
        batch_size = this.defaultBatchSize,
        dry_run = false
      } = data;

      // Validate input
      ErrorHandler.validateRequired(data, ['tickets', 'updates'], {
        operation: 'batchUpdateTickets'
      });

      if (!Array.isArray(tickets) || tickets.length === 0) {
        throw new ValidationError('tickets must be a non-empty array', 'batchUpdateTickets');
      }

      if (batch_size > this.maxBatchSize) {
        throw new ValidationError(`batch_size cannot exceed ${this.maxBatchSize}`, 'batchUpdateTickets');
      }

      const batchSize = Math.min(batch_size, this.maxBatchSize);
      const totalTickets = tickets.length;
      const batches = Math.ceil(totalTickets / batchSize);

      logger.info('Starting batch ticket update', {
        totalTickets,
        batchSize,
        batches,
        dryRun: dry_run
      });

      const results = {
        success: true,
        total_tickets: totalTickets,
        processed: 0,
        successful: 0,
        failed: 0,
        batches_processed: 0,
        errors: [],
        updated_tickets: [],
        dry_run
      };

      if (dry_run) {
        // Validate that tickets exist without making changes
        const validationResults = await this.validateTicketsExist(tickets);
        results.validation = validationResults;
        return results;
      }

      try {
        for (let i = 0; i < batches; i++) {
          const startIdx = i * batchSize;
          const endIdx = Math.min(startIdx + batchSize, totalTickets);
          const batch = tickets.slice(startIdx, endIdx);

          logger.info(`Processing batch ${i + 1}/${batches}`, {
            batchStart: startIdx,
            batchEnd: endIdx,
            batchSize: batch.length
          });

          const batchResult = await this.processBatchUpdate(batch, updates);
          
          results.processed += batchResult.processed;
          results.successful += batchResult.successful;
          results.failed += batchResult.failed;
          results.errors.push(...batchResult.errors);
          results.updated_tickets.push(...batchResult.updated_tickets);
          results.batches_processed++;

          // Small delay between batches to prevent overwhelming the system
          if (i < batches - 1) {
            await new Promise(resolve => setTimeout(resolve, 100));
          }
        }

        logger.info('Batch ticket update completed', {
          totalTickets,
          successful: results.successful,
          failed: results.failed
        });

        return results;
      } catch (error) {
        logger.error('Batch ticket update failed', {
          error: error.message,
          processed: results.processed
        });
        
        results.success = false;
        results.error = error.message;
        return results;
      }
    }, 'batchUpdateTickets', { ticketCount: data.tickets?.length })();
  }

  /**
   * Process a single batch of ticket updates
   * @param {array} batch - Batch of ticket IDs
   * @param {object} updates - Updates to apply
   * @returns {object} - Batch processing result
   */
  async processBatchUpdate(batch, updates) {
    const result = {
      processed: 0,
      successful: 0,
      failed: 0,
      errors: [],
      updated_tickets: []
    };

    // Start database transaction for the batch
    const transactionId = await this.db.beginTransaction();

    try {
      for (const ticketId of batch) {
        try {
          // Check if ticket exists in Redis
          const ticketExists = await this.redis.client.exists(`ticket:${ticketId}`);
          
          if (!ticketExists) {
            result.errors.push({
              ticket_id: ticketId,
              error: 'Ticket not found'
            });
            result.failed++;
            result.processed++;
            continue;
          }

          // Prepare update data
          const updateData = {
            ...updates,
            updated_at: new Date().toISOString()
          };

          // Update in Redis
          await this.redis.hSet(`ticket:${ticketId}`, updateData);

          // If ticket is being closed, handle archival
          if (updates.status && ['CLOSED', 'CANCELLED'].includes(updates.status)) {
            await this.handleTicketClosure(ticketId, transactionId);
          }

          result.updated_tickets.push({
            ticket_id: ticketId,
            updates: updateData
          });
          result.successful++;
          result.processed++;

        } catch (ticketError) {
          logger.error('Failed to update ticket in batch', {
            ticketId,
            error: ticketError.message
          });
          
          result.errors.push({
            ticket_id: ticketId,
            error: ticketError.message
          });
          result.failed++;
          result.processed++;
        }
      }

      // Commit the transaction
      await this.db.commitTransaction(transactionId);

      return result;
    } catch (error) {
      // Rollback the transaction
      await this.db.rollbackTransaction(transactionId);
      throw error;
    }
  }

  /**
   * Handle ticket closure during batch processing
   * @param {string} ticketId - Ticket ID
   * @param {string} transactionId - Database transaction ID
   */
  async handleTicketClosure(ticketId, transactionId) {
    try {
      // Get ticket data
      const ticketData = await this.redis.client.hGetAll(`ticket:${ticketId}`);
      
      // Archive to PostgreSQL within transaction
      await this.db.insertWithTransaction('tickets', {
        ...ticketData,
        tags: JSON.stringify(ticketData.tags || []),
        acceptance_criteria: JSON.stringify(ticketData.acceptance_criteria || []),
      }, transactionId);

      // Update Redis indexes
      await this.redis.client.zRem('tickets:active', ticketId);
      await this.redis.client.zAdd('tickets:closed', { score: Date.now(), value: ticketId });
      await this.redis.client.expire(`ticket:${ticketId}`, 3600);

      logger.debug('Ticket archived during batch processing', { ticketId });
    } catch (error) {
      logger.error('Failed to handle ticket closure in batch', {
        ticketId,
        error: error.message
      });
      throw error;
    }
  }

  /**
   * Validate that tickets exist
   * @param {array} ticketIds - Array of ticket IDs
   * @returns {object} - Validation results
   */
  async validateTicketsExist(ticketIds) {
    const validation = {
      total: ticketIds.length,
      existing: 0,
      missing: 0,
      missing_tickets: []
    };

    try {
      // Check tickets in batches
      const batchSize = 50;
      for (let i = 0; i < ticketIds.length; i += batchSize) {
        const batch = ticketIds.slice(i, i + batchSize);
        const pipeline = this.redis.client.multi();
        
        batch.forEach(ticketId => {
          pipeline.exists(`ticket:${ticketId}`);
        });
        
        const results = await pipeline.exec();
        
        results.forEach((exists, idx) => {
          if (exists) {
            validation.existing++;
          } else {
            validation.missing++;
            validation.missing_tickets.push(batch[idx]);
          }
        });
      }

      return validation;
    } catch (error) {
      logger.error('Failed to validate tickets', {
        error: error.message
      });
      throw new OperationError(
        `Failed to validate tickets: ${error.message}`,
        'validateTicketsExist',
        { ticketCount: ticketIds.length }
      );
    }
  }

  /**
   * Batch create work logs
   * @param {object} data - Batch work log data
   * @returns {object} - Batch creation result
   */
  async batchCreateWorkLogs(data) {
    return ErrorHandler.wrapOperation(async () => {
      const {
        work_logs,
        batch_size = this.defaultBatchSize,
        dry_run = false
      } = data;

      // Validate input
      ErrorHandler.validateRequired(data, ['work_logs'], {
        operation: 'batchCreateWorkLogs'
      });

      if (!Array.isArray(work_logs) || work_logs.length === 0) {
        throw new ValidationError('work_logs must be a non-empty array', 'batchCreateWorkLogs');
      }

      const batchSize = Math.min(batch_size, this.maxBatchSize);
      const totalLogs = work_logs.length;
      const batches = Math.ceil(totalLogs / batchSize);

      logger.info('Starting batch work log creation', {
        totalLogs,
        batchSize,
        batches,
        dryRun: dry_run
      });

      const results = {
        success: true,
        total_logs: totalLogs,
        processed: 0,
        successful: 0,
        failed: 0,
        batches_processed: 0,
        errors: [],
        created_logs: [],
        dry_run
      };

      if (dry_run) {
        // Validate work log data without creating
        results.validation = this.validateWorkLogData(work_logs);
        return results;
      }

      try {
        for (let i = 0; i < batches; i++) {
          const startIdx = i * batchSize;
          const endIdx = Math.min(startIdx + batchSize, totalLogs);
          const batch = work_logs.slice(startIdx, endIdx);

          const batchResult = await this.processBatchWorkLogCreation(batch);
          
          results.processed += batchResult.processed;
          results.successful += batchResult.successful;
          results.failed += batchResult.failed;
          results.errors.push(...batchResult.errors);
          results.created_logs.push(...batchResult.created_logs);
          results.batches_processed++;

          // Small delay between batches
          if (i < batches - 1) {
            await new Promise(resolve => setTimeout(resolve, 100));
          }
        }

        logger.info('Batch work log creation completed', {
          totalLogs,
          successful: results.successful,
          failed: results.failed
        });

        return results;
      } catch (error) {
        logger.error('Batch work log creation failed', {
          error: error.message,
          processed: results.processed
        });
        
        results.success = false;
        results.error = error.message;
        return results;
      }
    }, 'batchCreateWorkLogs', { logCount: data.work_logs?.length })();
  }

  /**
   * Process a single batch of work log creation
   * @param {array} batch - Batch of work log data
   * @returns {object} - Batch processing result
   */
  async processBatchWorkLogCreation(batch) {
    const result = {
      processed: 0,
      successful: 0,
      failed: 0,
      errors: [],
      created_logs: []
    };

    // Start database transaction for the batch
    const transactionId = await this.db.beginTransaction();

    try {
      for (const workLogData of batch) {
        try {
          // Validate required fields
          if (!workLogData.ticket_id || !workLogData.user_id || !workLogData.hours_worked) {
            result.errors.push({
              work_log: workLogData,
              error: 'Missing required fields: ticket_id, user_id, hours_worked'
            });
            result.failed++;
            result.processed++;
            continue;
          }

          // Prepare work log data
          const logData = {
            ticket_id: workLogData.ticket_id,
            user_id: workLogData.user_id,
            hours_worked: parseFloat(workLogData.hours_worked),
            work_date: workLogData.work_date || new Date().toISOString().split('T')[0],
            description: workLogData.description,
            work_type: workLogData.work_type || 'DEVELOPMENT',
            billable: workLogData.billable !== undefined ? workLogData.billable : true,
            metadata: JSON.stringify(workLogData.metadata || {})
          };

          // Insert into PostgreSQL
          const insertResult = await this.db.insertWithTransaction('work_logs', logData, transactionId);
          const logId = insertResult.log_id;

          // Cache in Redis
          const cacheKey = `work_log:${logId}`;
          await this.redis.hSet(cacheKey, {
            ...logData,
            log_id: logId,
            created_at: new Date().toISOString()
          });
          await this.redis.client.expire(cacheKey, 86400);

          // Update ticket's work log index
          await this.redis.client.sAdd(`ticket:${workLogData.ticket_id}:work_logs`, logId);

          result.created_logs.push({
            log_id: logId,
            ...logData
          });
          result.successful++;
          result.processed++;

        } catch (logError) {
          logger.error('Failed to create work log in batch', {
            workLogData,
            error: logError.message
          });
          
          result.errors.push({
            work_log: workLogData,
            error: logError.message
          });
          result.failed++;
          result.processed++;
        }
      }

      // Commit the transaction
      await this.db.commitTransaction(transactionId);

      return result;
    } catch (error) {
      // Rollback the transaction
      await this.db.rollbackTransaction(transactionId);
      throw error;
    }
  }

  /**
   * Validate work log data
   * @param {array} workLogs - Array of work log data
   * @returns {object} - Validation results
   */
  validateWorkLogData(workLogs) {
    const validation = {
      total: workLogs.length,
      valid: 0,
      invalid: 0,
      errors: []
    };

    workLogs.forEach((log, index) => {
      const errors = [];

      if (!log.ticket_id) errors.push('Missing ticket_id');
      if (!log.user_id) errors.push('Missing user_id');
      if (!log.hours_worked) errors.push('Missing hours_worked');
      if (log.hours_worked && log.hours_worked <= 0) errors.push('hours_worked must be positive');

      if (errors.length > 0) {
        validation.invalid++;
        validation.errors.push({
          index,
          work_log: log,
          errors
        });
      } else {
        validation.valid++;
      }
    });

    return validation;
  }

  /**
   * Get batch operation status
   * @param {string} operationId - Operation ID
   * @returns {object} - Operation status
   */
  async getBatchOperationStatus(operationId) {
    try {
      const statusKey = `batch_operation:${operationId}`;
      const status = await this.redis.client.hGetAll(statusKey);
      
      if (Object.keys(status).length === 0) {
        return {
          success: false,
          error: 'Operation not found'
        };
      }

      return {
        success: true,
        status: {
          ...status,
          progress: parseFloat(status.progress || 0),
          total: parseInt(status.total || 0),
          processed: parseInt(status.processed || 0)
        }
      };
    } catch (error) {
      logger.error('Failed to get batch operation status', {
        operationId,
        error: error.message
      });
      throw new OperationError(
        `Failed to get operation status: ${error.message}`,
        'getBatchOperationStatus',
        { operationId }
      );
    }
  }
}