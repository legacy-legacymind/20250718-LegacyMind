// src/managers/database-manager.js
import pg from 'pg';
import { logger } from '../utils/logger.js';
import { ErrorHandler, ConnectionError, TransactionError, OperationError } from '../utils/error-handler.js';

const { Pool } = pg;

export class DatabaseManager {
  constructor() {
    this.pool = null;
    this.isConnected = false;
    this.activeTransactions = new Map(); // Track active transactions by ID
  }

  async connect() {
    const dbUrl = process.env.DATABASE_URL || `postgres://${process.env.POSTGRES_USER}:${process.env.POSTGRES_PASSWORD}@${process.env.POSTGRES_HOST}:${process.env.POSTGRES_PORT}/${process.env.POSTGRES_DB}`;
    
    this.pool = new Pool({ connectionString: dbUrl });

    this.pool.on('error', (err) => {
      logger.error('PostgreSQL Pool Error', {
        error: err.message,
        code: err.code,
        database: process.env.POSTGRES_DB
      });
    });

    try {
      await ErrorHandler.withRetry(
        () => this.pool.query('SELECT 1'),
        {
          maxRetries: 3,
          baseDelay: 2000,
          context: { service: 'postgresql', database: process.env.POSTGRES_DB }
        }
      );
      
      this.isConnected = true;
      logger.info('PostgreSQL connected successfully', {
        database: process.env.POSTGRES_DB,
        host: process.env.POSTGRES_HOST
      });
    } catch (err) {
      this.isConnected = false;
      const error = ErrorHandler.handleConnectionError('postgresql', err, {
        database: process.env.POSTGRES_DB,
        host: process.env.POSTGRES_HOST
      });
      logger.error('Failed to connect to PostgreSQL', {
        error: error.message,
        context: error.context
      });
      throw error;
    }
  }

  async insert(table, data) {
    if (!this.isConnected) {
      throw new ConnectionError('PostgreSQL is not connected', 'postgresql', {
        operation: 'insert',
        table
      });
    }

    const columns = Object.keys(data);
    const values = Object.values(data);
    const placeholders = columns.map((_, i) => `$${i + 1}`).join(', ');

    const sql = `INSERT INTO ${table} (${columns.join(', ')}) VALUES (${placeholders}) RETURNING *`;

    try {
      const result = await ErrorHandler.withRetry(
        () => this.pool.query(sql, values),
        {
          maxRetries: 2,
          context: { operation: 'insert', table, columns: columns.length }
        }
      );
      
      logger.debug('Insert operation successful', {
        table,
        columns: columns.length,
        rowsAffected: result.rowCount
      });
      
      return result.rows[0];
    } catch (error) {
      throw ErrorHandler.handleExternalServiceError('postgresql', 'insert', error, {
        table,
        columns,
        sql: sql.substring(0, 100) + '...'
      });
    }
  }

  async query(sql, params) {
    if (!this.isConnected) {
      throw new ConnectionError('PostgreSQL is not connected', 'postgresql', {
        operation: 'query'
      });
    }
    
    try {
      const result = await ErrorHandler.withRetry(
        () => this.pool.query(sql, params),
        {
          maxRetries: 2,
          context: { operation: 'query', paramCount: params?.length || 0 }
        }
      );
      
      logger.debug('Query operation successful', {
        rowsAffected: result.rowCount,
        paramCount: params?.length || 0
      });
      
      return result;
    } catch (error) {
      throw ErrorHandler.handleExternalServiceError('postgresql', 'query', error, {
        sql: sql.substring(0, 100) + '...',
        paramCount: params?.length || 0
      });
    }
  }

  async beginTransaction() {
    if (!this.isConnected) {
      throw new ConnectionError('PostgreSQL is not connected', 'postgresql', {
        operation: 'beginTransaction'
      });
    }
    
    try {
      const client = await ErrorHandler.withRetry(
        () => this.pool.connect(),
        {
          maxRetries: 2,
          context: { operation: 'getConnection' }
        }
      );
      
      await client.query('BEGIN');
      
      const transactionId = Math.random().toString(36).substring(2, 15);
      this.activeTransactions.set(transactionId, client);
      
      logger.debug('Transaction started successfully', {
        transactionId,
        activeTransactions: this.activeTransactions.size
      });
      
      return transactionId;
    } catch (error) {
      throw new TransactionError('Failed to begin transaction', null, {
        activeTransactions: this.activeTransactions.size,
        originalError: error.message
      });
    }
  }

  async commitTransaction(transactionId) {
    const client = this.activeTransactions.get(transactionId);
    if (!client) {
      throw new TransactionError(`Transaction not found: ${transactionId}`, transactionId, {
        operation: 'commit',
        activeTransactions: this.activeTransactions.size
      });
    }

    try {
      await client.query('COMMIT');
      logger.debug('Transaction committed successfully', {
        transactionId,
        activeTransactions: this.activeTransactions.size - 1
      });
    } catch (error) {
      throw new TransactionError(`Failed to commit transaction: ${error.message}`, transactionId, {
        operation: 'commit',
        originalError: error.message
      });
    } finally {
      client.release();
      this.activeTransactions.delete(transactionId);
    }
  }

  async rollbackTransaction(transactionId) {
    const client = this.activeTransactions.get(transactionId);
    if (!client) {
      throw new TransactionError(`Transaction not found: ${transactionId}`, transactionId, {
        operation: 'rollback',
        activeTransactions: this.activeTransactions.size
      });
    }

    try {
      await client.query('ROLLBACK');
      logger.debug('Transaction rolled back successfully', {
        transactionId,
        activeTransactions: this.activeTransactions.size - 1
      });
    } catch (error) {
      logger.error('Failed to rollback transaction', {
        transactionId,
        error: error.message,
        activeTransactions: this.activeTransactions.size
      });
      throw new TransactionError(`Failed to rollback transaction: ${error.message}`, transactionId, {
        operation: 'rollback',
        originalError: error.message
      });
    } finally {
      client.release();
      this.activeTransactions.delete(transactionId);
    }
  }

  getTransactionConnection(transactionId) {
    const client = this.activeTransactions.get(transactionId);
    if (!client) {
      throw new TransactionError(`Transaction not found: ${transactionId}`, transactionId, {
        operation: 'getConnection',
        activeTransactions: this.activeTransactions.size
      });
    }
    return client;
  }

  async insertWithTransaction(table, data, transactionId = null) {
    if (!this.isConnected) {
      throw new ConnectionError('PostgreSQL is not connected', 'postgresql', {
        operation: 'insertWithTransaction',
        table,
        transactionId
      });
    }

    const columns = Object.keys(data);
    const values = Object.values(data);
    const placeholders = columns.map((_, i) => `$${i + 1}`).join(', ');

    // Quote column names to handle reserved words
    const quotedColumns = columns.map(col => `"${col}"`).join(', ');
    const sql = `INSERT INTO ${table} (${quotedColumns}) VALUES (${placeholders}) RETURNING *`;

    try {
      let result;
      if (transactionId) {
        const client = this.getTransactionConnection(transactionId);
        result = await client.query(sql, values);
        logger.debug('Insert with transaction successful', {
          table,
          transactionId,
          columns: columns.length,
          rowsAffected: result.rowCount
        });
      } else {
        result = await ErrorHandler.withRetry(
          () => this.pool.query(sql, values),
          {
            maxRetries: 2,
            context: { operation: 'insertWithTransaction', table, columns: columns.length }
          }
        );
        logger.debug('Insert without transaction successful', {
          table,
          columns: columns.length,
          rowsAffected: result.rowCount
        });
      }
      return result.rows[0];
    } catch (error) {
      throw ErrorHandler.handleExternalServiceError('postgresql', 'insertWithTransaction', error, {
        table,
        transactionId,
        columns,
        sql: sql.substring(0, 100) + '...'
      });
    }
  }

  async queryWithTransaction(sql, params, transactionId = null) {
    if (!this.isConnected) {
      throw new ConnectionError('PostgreSQL is not connected', 'postgresql', {
        operation: 'queryWithTransaction',
        transactionId
      });
    }
    
    try {
      let result;
      if (transactionId) {
        const client = this.getTransactionConnection(transactionId);
        result = await client.query(sql, params);
        logger.debug('Query with transaction successful', {
          transactionId,
          paramCount: params?.length || 0,
          rowsAffected: result.rowCount
        });
      } else {
        result = await ErrorHandler.withRetry(
          () => this.pool.query(sql, params),
          {
            maxRetries: 2,
            context: { operation: 'queryWithTransaction', paramCount: params?.length || 0 }
          }
        );
        logger.debug('Query without transaction successful', {
          paramCount: params?.length || 0,
          rowsAffected: result.rowCount
        });
      }
      return result;
    } catch (error) {
      throw ErrorHandler.handleExternalServiceError('postgresql', 'queryWithTransaction', error, {
        transactionId,
        sql: sql.substring(0, 100) + '...',
        paramCount: params?.length || 0
      });
    }
  }

  async close() {
    logger.info('Closing database connection', {
      activeTransactions: this.activeTransactions.size,
      isConnected: this.isConnected
    });
    
    // Rollback any active transactions before closing
    for (const [transactionId, client] of this.activeTransactions) {
      try {
        await client.query('ROLLBACK');
        client.release();
        logger.warn('Force rolled back transaction on close', {
          transactionId
        });
      } catch (error) {
        logger.error('Error rolling back transaction on close', {
          transactionId,
          error: error.message
        });
      }
    }
    this.activeTransactions.clear();

    if (this.pool && this.isConnected) {
      try {
        await this.pool.end();
        this.isConnected = false;
        logger.info('Database connection closed successfully');
      } catch (error) {
        logger.error('Error closing database connection', {
          error: error.message
        });
        throw ErrorHandler.handleExternalServiceError('postgresql', 'close', error);
      }
    }
  }
}
