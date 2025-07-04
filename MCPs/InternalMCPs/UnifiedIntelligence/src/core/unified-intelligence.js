import { SessionManager } from './session-manager.js';
import { ModeDetector } from './mode-detector.js';
import ioredis from 'ioredis';
import { logger } from '../utils/logger.js';
import { v4 as uuidv4 } from 'uuid';

export class UnifiedIntelligence {
  constructor(config = {}) {
    this.config = config;
    this.redis = null;
    this.sessions = null; // Will be initialized after Redis connection
    this.modeDetector = new ModeDetector();
    this.isShuttingDown = false;
    
    // Initialize Redis connection
    if (config.redisUrl) {
      this.initializeRedis(config.redisUrl);
    }
    
    // Add process exit handlers for proper cleanup
    this.setupCleanupHandlers();
    
    logger.info('UnifiedIntelligence core initialized (Redis-only mode).');
  }

  async initializeRedis(redisUrl) {
    try {
      this.redis = new ioredis(redisUrl, {
        retryDelayOnFailure: 1000,
        maxRetriesPerRequest: 3,
        lazyConnect: true,
        // Add connection timeout
        connectTimeout: 10000,
        // Add error handling
        enableOfflineQueue: false
      });
      
      // Add Redis error handlers
      this.redis.on('error', (error) => {
        logger.error('Redis connection error', { error: error.message });
      });
      
      this.redis.on('ready', () => {
        logger.info('Redis connection ready');
      });
      
      await this.redis.connect();
      
      // Initialize SessionManager with Redis client
      this.sessions = new SessionManager(this.redis);
      
      logger.info('Redis connection established successfully');
    } catch (error) {
      logger.error('Failed to initialize Redis connection', {
        error: error.message
      });
      this.redis = null;
      this.sessions = null;
    }
  }

  async think(args) {
    const { action = 'capture', thought, options = {} } = args;
    
    logger.info(`Received 'think' call with action '${action}'.`);

    try {
      switch (action) {
        case 'capture':
          if (!thought || typeof thought !== 'string') {
            throw new Error('A non-empty "thought" string is required for the "capture" action.');
          }
          
          if (!this.sessions) {
            throw new Error('Session manager not initialized. Redis connection required.');
          }
          
          // Get or create session
          const session = await this.sessions.getCurrentOrCreate('default');
          
          // Capture thought and update session activity
          const result = await this.captureThought({ thought, options, sessionId: session.id });
          
          // Update session activity after capturing thought
          await this.sessions.updateActivity('default');
          
          return result;

        case 'status':
          const session2 = await this.sessions.getActiveSession();
          if (!session2) {
            return {
              status: 'no_active_session',
              message: 'No active session found.'
            };
          }
          return await this.getSessionStatus(session2.id);

        case 'check_in':
          const { identity } = args;
          if (!identity || !identity.name) {
            throw new Error('Identity information with name is required for check_in action');
          }
          return await this.initializeFederation(identity);

        case 'help':
          return {
            description: 'UnifiedIntelligence: Simple thought capture to Redis',
            actions: {
              capture: 'Capture a thought to Redis',
              status: 'Get session status',
              check_in: 'Initialize instance',
              help: 'Get this help'
            },
            example: '{ "action": "capture", "thought": "your thought content" }'
          };

        default:
          throw new Error(`Unknown action: ${action}`);
      }
    } catch (error) {
      logger.error(`Error during 'think' action '${action}'`, { error: error.message });
      throw error;
    }
  }

  async captureThought({ thought, options, sessionId }) {
    if (!this.redis) {
      throw new Error('Redis connection not available');
    }
    
    // Input validation - reject invalid inputs instead of silent sanitization
    if (!thought || typeof thought !== 'string' || thought.trim() === '') {
      throw new Error('Thought content must be a non-empty string');
    }
    
    if (!sessionId || typeof sessionId !== 'string' || sessionId.trim() === '') {
      throw new Error('Session ID must be a non-empty string');
    }
    
    // Validate sessionId format - reject instead of sanitize to prevent data loss
    if (!/^[a-zA-Z0-9_-]+$/.test(sessionId)) {
      throw new Error('Session ID contains invalid characters. Only alphanumeric, underscore, and hyphen allowed.');
    }
    
    // Validate options object
    if (options && typeof options !== 'object') {
      throw new Error('Options must be an object');
    }
    
    // XSS prevention for thought content
    if (thought.includes('<script>') || thought.includes('javascript:') || thought.includes('data:')) {
      throw new Error('Thought content contains potentially malicious content');
    }

    // Detect mode
    const modeResult = this.modeDetector.detect(thought);
    
    // Create thought object
    const thoughtData = {
      id: uuidv4(),
      content: thought,
      mode: modeResult.mode,
      confidence: options.confidence || 0.7,
      tags: Array.isArray(options.tags) ? options.tags : [],
      sessionId: sessionId, // Use original validated sessionId
      timestamp: new Date().toISOString(),
      createdAt: Date.now()
    };

    try {
      // Use Redis pipeline for atomic operations (performance improvement)
      const pipeline = this.redis.pipeline();
      
      // Write to Redis stream
      const streamKey = `thoughts:${thoughtData.sessionId}`;
      pipeline.xadd(streamKey, '*', 
        'id', thoughtData.id,
        'content', thoughtData.content,
        'mode', thoughtData.mode,
        'confidence', thoughtData.confidence,
        'timestamp', thoughtData.timestamp,
        'tags', JSON.stringify(thoughtData.tags)
      );
      
      // Add stream trimming to prevent infinite growth (keep last 1000 entries)
      pipeline.xtrim(streamKey, 'MAXLEN', '~', 1000);

      // Store in Redis hash for direct access (using hset instead of deprecated hmset)
      const thoughtKey = `thought:${thoughtData.id}`;
      const hashData = {
        ...thoughtData,
        tags: JSON.stringify(thoughtData.tags) // Ensure consistent JSON handling
      };
      pipeline.hset(thoughtKey, hashData);
      
      // Set expiration (30 days)
      pipeline.expire(thoughtKey, 30 * 24 * 60 * 60);
      
      // Execute all commands atomically and check results with retry
      const results = await this.retryRedisOperation(
        () => pipeline.exec(),
        3,
        'Thought capture pipeline'
      );
      
      // Check for pipeline failures
      if (results && results.some(result => result[0] !== null)) {
        const errors = results.filter(r => r[0] !== null).map(r => r[0].message);
        logger.error('Pipeline execution had errors', { 
          thoughtId: thoughtData.id,
          errors 
        });
        throw new Error(`Pipeline execution failed: ${errors.join(', ')}`);
      }

      logger.info(`Thought captured to Redis: ${thoughtData.id}`);

      return {
        captured: {
          id: thoughtData.id,
          mode: thoughtData.mode,
          confidence: thoughtData.confidence,
          sessionId: sessionId
        },
        message: 'Thought successfully captured to Redis'
      };

    } catch (error) {
      logger.error('Failed to capture thought to Redis', { error: error.message });
      throw new Error(`Failed to capture thought: ${error.message}`);
    }
  }

  async getSessionStatus(sessionId) {
    if (!this.redis) {
      return {
        status: 'no_redis',
        message: 'Redis connection not available'
      };
    }

    try {
      const streamKey = `thoughts:${sessionId}`;
      const thoughtCount = await this.redis.xlen(streamKey);
      
      return {
        status: 'active',
        sessionId,
        thoughtCount,
        message: `Session has ${thoughtCount} thoughts`
      };
    } catch (error) {
      logger.error('Error getting session status', { error: error.message });
      return {
        status: 'error',
        error: error.message
      };
    }
  }

  async initializeFederation(identity) {
    if (!this.redis) {
      throw new Error('Redis connection required for federation');
    }

    // Input validation
    if (!identity || typeof identity !== 'object') {
      throw new Error('Invalid identity object provided');
    }
    
    if (!identity.name || typeof identity.name !== 'string' || identity.name.trim() === '') {
      throw new Error('Identity must have a valid name property');
    }
    
    // Validate instanceId format - reject instead of sanitize
    if (!/^[a-zA-Z0-9_-]+$/.test(identity.name)) {
      throw new Error('Instance ID contains invalid characters. Only alphanumeric, underscore, and hyphen allowed.');
    }
    
    const instanceId = identity.name;
    
    try {
      // Create federation entry
      const federationKey = `federation:${instanceId}`;
      const federationData = {
        instanceId,
        identity: JSON.stringify(identity),
        checkinTime: Date.now(),
        status: 'active'
      };

      await this.redis.hset(federationKey, federationData);
      await this.redis.expire(federationKey, 24 * 60 * 60); // 24 hours

      // Initialize session
      const session = await this.sessions.initializeSession(instanceId);

      logger.info(`Federation initialized for ${instanceId}`);

      return {
        success: true,
        instanceId,
        sessionId: session.id,
        message: `Instance ${instanceId} checked into federation`
      };

    } catch (error) {
      logger.error('Federation initialization failed', { error: error.message });
      throw new Error(`Federation initialization failed: ${error.message}`);
    }
  }
  
  /**
   * Retry a Redis operation with exponential backoff
   * @param {Function} operation - The Redis operation to retry
   * @param {number} maxRetries - Maximum number of retries
   * @param {string} operationName - Name for logging
   * @returns {Promise} - The operation result
   */
  async retryRedisOperation(operation, maxRetries = 3, operationName = 'Redis operation') {
    let lastError;
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error;
        
        if (attempt === maxRetries) {
          logger.error(`${operationName} failed after ${maxRetries} attempts`, {
            error: error.message,
            attempts: maxRetries
          });
          throw error;
        }
        
        const delayMs = Math.min(1000 * Math.pow(2, attempt - 1), 5000); // Cap at 5 seconds
        logger.warn(`${operationName} failed, retrying in ${delayMs}ms`, {
          attempt,
          maxRetries,
          error: error.message
        });
        
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
    }
    
    throw lastError;
  }

  /**
   * Setup cleanup handlers for proper resource management
   */
  setupCleanupHandlers() {
    const cleanup = async () => {
      if (this.isShuttingDown) {
        return;
      }
      
      this.isShuttingDown = true;
      logger.info('Shutting down UnifiedIntelligence...');
      
      try {
        if (this.redis) {
          // Properly await Redis disconnect with timeout
          const disconnectPromise = this.redis.quit();
          const timeoutPromise = new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Redis disconnect timeout')), 5000)
          );
          
          await Promise.race([disconnectPromise, timeoutPromise]);
          logger.info('Redis connection closed');
        }
      } catch (error) {
        logger.error('Error during cleanup', { error: error.message });
        // Force disconnect if graceful quit fails
        if (this.redis) {
          try {
            this.redis.disconnect();
          } catch (forceError) {
            logger.error('Error during forced disconnect', { error: forceError.message });
          }
        }
      }
    };
    
    // Handle various exit conditions
    process.on('SIGINT', async () => {
      await cleanup();
      process.exit(0);
    });
    process.on('SIGTERM', async () => {
      await cleanup();
      process.exit(0);
    });
    process.on('uncaughtException', async (error) => {
      logger.error('Uncaught exception', { error: error.message });
      await cleanup();
      process.exit(1);
    });
    process.on('unhandledRejection', async (reason, promise) => {
      logger.error('Unhandled promise rejection', { reason, promise });
      await cleanup();
      process.exit(1);
    });
  }
}