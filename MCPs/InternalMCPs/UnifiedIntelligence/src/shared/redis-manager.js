// src/shared/redis-manager.js
import Redis from 'ioredis';
import { logger } from '../utils/logger.js';

// Simple circuit breaker implementation
class SimpleCircuitBreaker {
    constructor(options = {}) {
        this.timeout = options.timeout || 3000;
        this.errorThreshold = options.errorThresholdPercentage || 50;
        this.resetTimeout = options.resetTimeout || 30000;
        this.state = 'CLOSED'; // CLOSED, OPEN, HALF_OPEN
        this.failures = 0;
        this.successes = 0;
        this.lastFailureTime = null;
        this.nextAttemptTime = null;
    }

    async fire(operation) {
        if (this.state === 'OPEN') {
            if (Date.now() < this.nextAttemptTime) {
                throw new Error('Circuit breaker is OPEN');
            }
            this.state = 'HALF_OPEN';
        }

        try {
            const result = await Promise.race([
                operation(),
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Operation timeout')), this.timeout)
                )
            ]);
            
            if (this.state === 'HALF_OPEN') {
                this.state = 'CLOSED';
                this.failures = 0;
                this.successes = 0;
            } else {
                this.successes++;
            }
            
            return result;
        } catch (error) {
            this.failures++;
            this.lastFailureTime = Date.now();
            
            const totalCalls = this.failures + this.successes;
            const failureRate = (this.failures / totalCalls) * 100;
            
            if (failureRate >= this.errorThreshold && totalCalls >= 5) {
                this.state = 'OPEN';
                this.nextAttemptTime = Date.now() + this.resetTimeout;
                this.failures = 0;
                this.successes = 0;
            }
            
            throw error;
        }
    }
}

class RedisManager {
    constructor() {
        if (RedisManager.instance) {
            return RedisManager.instance;
        }

        this.client = null;
        this.breaker = null;
        this.isInitialized = false;
        
        RedisManager.instance = this;
    }

    async initialize() {
        if (this.isInitialized) {
            return;
        }
        
        // Prevent concurrent initialization
        if (this.initializationPromise) {
            return this.initializationPromise;
        }
        
        this.initializationPromise = this._doInitialize();
        return this.initializationPromise;
    }
    
    async _doInitialize() {

        const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
        
        // Create a single Redis client with connection pooling
        this.client = new Redis(redisUrl, {
            // Connection pool settings
            maxRetriesPerRequest: 3,
            connectTimeout: 5000,
            commandTimeout: 5000,
            
            // Enable connection pooling
            enableReadyCheck: true,
            enableOfflineQueue: true,
            
            // Reconnection strategy with exponential backoff
            retryStrategy: (times) => {
                if (times > 10) {
                    logger.error('Max Redis reconnection attempts reached');
                    return null;
                }
                const delay = Math.min(times * 50, 2000);
                logger.info(`Reconnecting to Redis in ${delay}ms (attempt ${times})`);
                return delay;
            },
            
            // Connection pool settings
            connectionPool: {
                min: 2,
                max: 10
            },
            
            // Keep alive
            keepAlive: 10000,
            
            // Lazy connect for faster startup
            lazyConnect: true
        });

        // Circuit breaker wrapper
        this.breaker = new SimpleCircuitBreaker({
            timeout: 3000,
            errorThresholdPercentage: 50,
            resetTimeout: 30000
        });

        // Event handlers
        this.client.on('connect', () => {
            logger.info('Redis connected successfully');
        });

        this.client.on('ready', () => {
            logger.info('Redis ready to accept commands');
        });

        this.client.on('error', (err) => {
            logger.error('Redis connection error:', err);
        });

        this.client.on('close', () => {
            logger.warn('Redis connection closed');
        });

        this.client.on('reconnecting', (delay) => {
            logger.info(`Reconnecting to Redis in ${delay}ms`);
        });

        try {
            // Wait for connection
            await this.client.connect();
            
            // Test the connection
            await this.client.ping();
            
            this.isInitialized = true;
            logger.info('Redis manager initialized with connection pooling');
        } catch (error) {
            logger.error('Failed to initialize Redis manager:', error);
            this.initializationPromise = null;
            throw error;
        }
    }

    // Get the main client for operations
    getClient() {
        if (!this.isInitialized || !this.client) {
            throw new Error('Redis manager not initialized');
        }
        return this.client;
    }

    // Execute operation with circuit breaker protection
    async execute(operation) {
        if (!this.isInitialized) {
            await this.initialize();
        }
        
        return this.breaker.fire(async () => {
            return operation(this.client);
        });
    }

    // Get a duplicate client for blocking operations (e.g., pub/sub)
    async getDuplicateClient() {
        if (!this.isInitialized) {
            await this.initialize();
        }
        
        const duplicate = this.client.duplicate();
        await duplicate.connect();
        return duplicate;
    }

    async healthCheck() {
        try {
            await this.execute(async (client) => {
                return client.ping();
            });
            return { status: 'healthy', connected: this.client.status === 'ready' };
        } catch (error) {
            return { status: 'unhealthy', error: error.message };
        }
    }

    async shutdown() {
        if (this.client) {
            logger.info('Shutting down Redis connection');
            await this.client.quit();
            this.isInitialized = false;
        }
    }
}

// Export singleton instance
export const redisManager = new RedisManager();