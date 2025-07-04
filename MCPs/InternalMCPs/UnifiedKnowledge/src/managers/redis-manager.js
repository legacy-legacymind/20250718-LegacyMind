// src/managers/redis-manager.js
import { createClient } from 'redis';
import { logger } from '../utils/logger.js';
import { ErrorHandler, ConnectionError, OperationError, ErrorCodes } from '../utils/error-handler.js';

export class RedisManager {
  constructor() {
    this.client = null;
    this.isConnected = false;
  }

  async connect() {
    const redisUrl = process.env.REDIS_URL || `redis://${process.env.REDIS_HOST || 'localhost'}:${process.env.REDIS_PORT || 6379}`;
    
    this.client = createClient({
      url: redisUrl,
      password: process.env.REDIS_PASSWORD,
    });

    this.client.on('error', (err) => {
      logger.error('Redis Client Error', {
        error: err.message,
        url: redisUrl,
        hasPassword: !!process.env.REDIS_PASSWORD
      });
    });

    try {
      await ErrorHandler.withRetry(
        () => this.client.connect(),
        {
          maxRetries: 3,
          baseDelay: 1000,
          context: { service: 'redis', url: redisUrl }
        }
      );
      
      this.isConnected = true;
      logger.info('Redis connected successfully', {
        url: redisUrl,
        hasPassword: !!process.env.REDIS_PASSWORD
      });
    } catch (err) {
      this.isConnected = false;
      const error = ErrorHandler.handleConnectionError('redis', err, {
        url: redisUrl,
        hasPassword: !!process.env.REDIS_PASSWORD
      });
      logger.error('Failed to connect to Redis', {
        error: error.message,
        context: error.context
      });
      throw error;
    }
  }

  async hSet(key, data) {
    if (!this.isConnected) {
      throw new ConnectionError('Redis is not connected', 'redis', {
        operation: 'hSet',
        key
      });
    }
    
    try {
      const toSet = {};
      for (const [field, value] of Object.entries(data)) {
        toSet[field] = typeof value === 'string' ? value : JSON.stringify(value);
      }
      
      return await ErrorHandler.withRetry(
        () => this.client.hSet(key, toSet),
        {
          maxRetries: 2,
          context: { operation: 'hSet', key, fieldCount: Object.keys(toSet).length }
        }
      );
    } catch (error) {
      throw ErrorHandler.handleExternalServiceError('redis', 'hSet', error, {
        key,
        fieldCount: Object.keys(data).length
      });
    }
  }

  async hGetAll(key) {
    if (!this.isConnected) {
      throw new ConnectionError('Redis is not connected', 'redis', {
        operation: 'hGetAll',
        key
      });
    }
    
    try {
      return await ErrorHandler.withRetry(
        () => this.client.hGetAll(key),
        {
          maxRetries: 2,
          context: { operation: 'hGetAll', key }
        }
      );
    } catch (error) {
      throw ErrorHandler.handleExternalServiceError('redis', 'hGetAll', error, { key });
    }
  }

  async sAdd(key, member) {
    if (!this.isConnected) {
      throw new ConnectionError('Redis is not connected', 'redis', {
        operation: 'sAdd',
        key
      });
    }
    
    try {
      return await ErrorHandler.withRetry(
        () => this.client.sAdd(key, member),
        {
          maxRetries: 2,
          context: { operation: 'sAdd', key, member }
        }
      );
    } catch (error) {
      throw ErrorHandler.handleExternalServiceError('redis', 'sAdd', error, { key, member });
    }
  }

  async sRem(key, member) {
    if (!this.isConnected) {
      throw new ConnectionError('Redis is not connected', 'redis', {
        operation: 'sRem',
        key
      });
    }
    
    try {
      return await ErrorHandler.withRetry(
        () => this.client.sRem(key, member),
        {
          maxRetries: 2,
          context: { operation: 'sRem', key, member }
        }
      );
    } catch (error) {
      throw ErrorHandler.handleExternalServiceError('redis', 'sRem', error, { key, member });
    }
  }

  async expire(key, seconds) {
    if (!this.isConnected) {
      throw new ConnectionError('Redis is not connected', 'redis', {
        operation: 'expire',
        key
      });
    }
    
    try {
      return await ErrorHandler.withRetry(
        () => this.client.expire(key, seconds),
        {
          maxRetries: 2,
          context: { operation: 'expire', key, seconds }
        }
      );
    } catch (error) {
      throw ErrorHandler.handleExternalServiceError('redis', 'expire', error, { key, seconds });
    }
  }

  async del(key) {
    if (!this.isConnected) {
      throw new ConnectionError('Redis is not connected', 'redis', {
        operation: 'del',
        key
      });
    }
    
    try {
      return await ErrorHandler.withRetry(
        () => this.client.del(key),
        {
          maxRetries: 2,
          context: { operation: 'del', key }
        }
      );
    } catch (error) {
      throw ErrorHandler.handleExternalServiceError('redis', 'del', error, { key });
    }
  }

  async lPush(key, value) {
    if (!this.isConnected) {
      throw new ConnectionError('Redis is not connected', 'redis', {
        operation: 'lPush',
        key
      });
    }
    
    try {
      return await ErrorHandler.withRetry(
        () => this.client.lPush(key, value),
        {
          maxRetries: 2,
          context: { operation: 'lPush', key, value }
        }
      );
    } catch (error) {
      throw ErrorHandler.handleExternalServiceError('redis', 'lPush', error, { key, value });
    }
  }

  async get(key) {
    if (!this.isConnected) {
      throw new ConnectionError('Redis is not connected', 'redis', {
        operation: 'get',
        key
      });
    }
    
    try {
      return await ErrorHandler.withRetry(
        () => this.client.get(key),
        {
          maxRetries: 2,
          context: { operation: 'get', key }
        }
      );
    } catch (error) {
      throw ErrorHandler.handleExternalServiceError('redis', 'get', error, { key });
    }
  }

  async setex(key, seconds, value) {
    if (!this.isConnected) {
      throw new ConnectionError('Redis is not connected', 'redis', {
        operation: 'setex',
        key,
        seconds
      });
    }
    
    try {
      return await ErrorHandler.withRetry(
        () => this.client.setEx(key, seconds, value),
        {
          maxRetries: 2,
          context: { operation: 'setex', key, seconds }
        }
      );
    } catch (error) {
      throw ErrorHandler.handleExternalServiceError('redis', 'setex', error, { key, seconds });
    }
  }

  async close() {
    if (this.client && this.isConnected) {
      try {
        await this.client.quit();
        this.isConnected = false;
        logger.info('Redis connection closed successfully');
      } catch (error) {
        logger.error('Error closing Redis connection', {
          error: error.message
        });
        throw ErrorHandler.handleExternalServiceError('redis', 'close', error);
      }
    }
  }
}
