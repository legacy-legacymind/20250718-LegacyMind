import { SessionManager } from './session-manager.js';
import { ModeDetector } from './mode-detector.js';
import { AutoCaptureMonitor } from './auto-capture/monitor.js';
import { redisManager } from '../shared/redis-manager.js';
import { logger } from '../utils/logger.js';
import { v4 as uuidv4 } from 'uuid';

export class UnifiedIntelligence {
  constructor(config = {}) {
    this.config = config;
    this.redis = null;
    this.sessions = null; // Will be initialized after Redis connection
    this.modeDetector = new ModeDetector();
    this.autoCapture = null; // Will be initialized after Redis connection
    this.isShuttingDown = false;
    this.currentInstanceId = null; // Track the current instance for this connection
    this.initializationPromise = null;
    
    // Store the initialization promise
    this.initializationPromise = this.initializeRedis();
    
    // Add process exit handlers for proper cleanup
    this.setupCleanupHandlers();
    
    logger.info('UnifiedIntelligence core initialized (Redis-only mode).');
  }

  async initializeRedis() {
    try {
      // Initialize the shared Redis manager
      await redisManager.initialize();
      
      // Get the Redis client from the manager
      this.redis = redisManager.getClient();
      
      // Initialize SessionManager with Redis client
      this.sessions = new SessionManager(this.redis);
      
      // Initialize AutoCaptureMonitor
      this.autoCapture = new AutoCaptureMonitor(this.redis, this);
      
      logger.info('Redis connection established successfully through RedisManager');
    } catch (error) {
      logger.error('Failed to initialize Redis connection', {
        error: error.message
      });
      this.redis = null;
      this.sessions = null;
      this.autoCapture = null;
    }
  }

  async think(args) {
    const { action = 'capture', thought, options = {} } = args;
    
    logger.info(`Received 'think' call with action '${action}'.`);
    
    // Ensure Redis is initialized before proceeding
    if (this.initializationPromise) {
      await this.initializationPromise;
    }

    try {
      switch (action) {
        case 'capture':
          if (!thought || typeof thought !== 'string') {
            throw new Error('A non-empty "thought" string is required for the "capture" action.');
          }
          
          if (!this.sessions) {
            throw new Error('Session manager not initialized. Redis connection required.');
          }
          
          // Use current instance or get active session
          let instanceId = this.currentInstanceId;
          let sessionId;
          
          if (instanceId) {
            // Get session for current instance
            const session = await this.sessions.getCurrentOrCreate(instanceId);
            sessionId = session.id;
          } else {
            // Fallback to active session
            const session = await this.sessions.getActiveSession();
            if (!session || !session.instanceId) {
              throw new Error('No active session found. Please check in first with an instance identity.');
            }
            instanceId = session.instanceId;
            sessionId = session.id;
          }
          
          // Capture thought and update session activity
          const result = await this.captureThought({ 
            thought, 
            options, 
            sessionId,
            instanceId 
          });
          
          // Update session activity after capturing thought
          await this.sessions.updateActivity(instanceId);
          
          return result;

        case 'status':
          // Use current instance if available
          if (this.currentInstanceId) {
            const session = await this.sessions.getCurrentOrCreate(this.currentInstanceId);
            return await this.getSessionStatus(session.id);
          } else {
            // Fallback to active session
            const session2 = await this.sessions.getActiveSession();
            if (!session2) {
              return {
                status: 'no_active_session',
                message: 'No active session found.'
              };
            }
            return await this.getSessionStatus(session2.id);
          }

        case 'check_in':
          const { identity } = args;
          if (!identity || !identity.name) {
            throw new Error('Identity information with name is required for check_in action');
          }
          return await this.initializeFederation(identity);

        case 'remember_identity':
          const { content: identityContent } = args;
          if (!identityContent || typeof identityContent !== 'string') {
            throw new Error('Content is required for remember_identity action');
          }
          return await this.rememberIdentity(identityContent);

        case 'remember_context':
          const { content: contextContent } = args;
          if (!contextContent || typeof contextContent !== 'string') {
            throw new Error('Content is required for remember_context action');
          }
          return await this.rememberContext(contextContent);

        case 'remember_curiosity':
          const { content: curiosityContent } = args;
          if (!curiosityContent || typeof curiosityContent !== 'string') {
            throw new Error('Content is required for remember_curiosity action');
          }
          return await this.rememberCuriosity(curiosityContent);

        case 'monitor':
          const { operation = 'status', thresholds } = args;
          if (!this.autoCapture) {
            throw new Error('Auto-capture monitor not initialized');
          }
          
          switch (operation) {
            case 'start':
              const instanceForStart = this.currentInstanceId || args.options?.instance;
              if (!instanceForStart) {
                throw new Error('Instance ID required to start monitor');
              }
              return await this.autoCapture.start(instanceForStart);
              
            case 'stop':
              const instanceForStop = this.currentInstanceId || args.options?.instance;
              if (!instanceForStop) {
                throw new Error('Instance ID required to stop monitor');
              }
              return await this.autoCapture.stop(instanceForStop);
              
            case 'status':
              const instanceForStatus = this.currentInstanceId || args.options?.instance;
              if (!instanceForStatus) {
                throw new Error('Instance ID required for monitor status');
              }
              return await this.autoCapture.status(instanceForStatus);
              
            case 'thresholds':
              if (!thresholds) {
                throw new Error('Thresholds required for update operation');
              }
              return await this.autoCapture.updateThresholds(thresholds);
              
            default:
              throw new Error(`Unknown monitor operation: ${operation}`);
          }

        case 'help':
          return {
            description: 'UnifiedIntelligence: Simple thought capture to Redis',
            actions: {
              capture: 'Capture a thought to Redis',
              status: 'Get session status',
              monitor: 'Control auto-capture monitoring (start/stop/status/thresholds)',
              check_in: 'Initialize instance',
              remember_identity: 'Store/update instance identity information',
              remember_context: 'Store/update current working context',
              remember_curiosity: 'Store/update what the instance is curious about',
              help: 'Get this help'
            },
            examples: {
              capture: '{ "action": "capture", "thought": "your thought content" }',
              remember: '{ "action": "remember_identity", "content": "I am CCI, the Intelligence Specialist" }'
            }
          };

        default:
          throw new Error(`Unknown action: ${action}`);
      }
    } catch (error) {
      logger.error(`Error during 'think' action '${action}'`, { error: error.message });
      throw error;
    }
  }

  async captureThought({ thought, options, sessionId, instanceId }) {
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
    
    if (!instanceId || typeof instanceId !== 'string' || instanceId.trim() === '') {
      throw new Error('Instance ID must be a non-empty string');
    }
    
    // Validate sessionId format - reject instead of sanitize to prevent data loss
    if (!/^[a-zA-Z0-9_-]+$/.test(sessionId)) {
      throw new Error('Session ID contains invalid characters. Only alphanumeric, underscore, and hyphen allowed.');
    }
    
    // Validate instanceId format
    if (!/^[a-zA-Z0-9_-]+$/.test(instanceId)) {
      throw new Error('Instance ID contains invalid characters. Only alphanumeric, underscore, and hyphen allowed.');
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
      
      // Write to Redis stream with instance namespace
      const streamKey = `${instanceId}:thoughts`;
      pipeline.xadd(streamKey, '*', 
        'id', thoughtData.id,
        'content', thoughtData.content,
        'mode', thoughtData.mode,
        'confidence', thoughtData.confidence,
        'timestamp', thoughtData.timestamp,
        'tags', JSON.stringify(thoughtData.tags),
        'sessionId', sessionId
      );
      
      // Stream trimming removed for performance - handled by cleanup service

      // Store in Redis hash for direct access with instance namespace
      const thoughtKey = `${instanceId}:thought:${thoughtData.id}`;
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
      // Try to get session for current instance first
      let instanceId = this.currentInstanceId;
      
      if (!instanceId) {
        // Fallback: Get the active session to find the instanceId
        const session = await this.sessions.getActiveSession();
        if (!session || session.id !== sessionId) {
          return {
            status: 'not_found',
            message: 'Session not found or not active'
          };
        }
        instanceId = session.instanceId;
      }
      
      const streamKey = `${instanceId}:thoughts`;
      const thoughtCount = await this.redis.xlen(streamKey);
      
      return {
        status: 'active',
        sessionId,
        instanceId,
        thoughtCount,
        message: `Session ${instanceId} has ${thoughtCount} thoughts`
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

      // Initialize instance namespace structure
      const pipeline = this.redis.pipeline();
      
      // Create the thoughts stream (empty initially)
      const streamKey = `${instanceId}:thoughts`;
      pipeline.xadd(streamKey, '*', 'init', 'namespace_created', 'timestamp', new Date().toISOString());
      
      // Create placeholder keys for identity, context, and curiosity
      pipeline.set(`${instanceId}:identity`, JSON.stringify(identity));
      pipeline.expire(`${instanceId}:identity`, 30 * 24 * 60 * 60); // 30 days
      
      pipeline.set(`${instanceId}:context`, 'Initial check-in context');
      pipeline.expire(`${instanceId}:context`, 30 * 24 * 60 * 60); // 30 days
      
      pipeline.set(`${instanceId}:curiosity`, 'Ready for exploration');
      pipeline.expire(`${instanceId}:curiosity`, 30 * 24 * 60 * 60); // 30 days
      
      // Execute namespace initialization
      await pipeline.exec();

      // Set this as the current instance for this connection
      this.currentInstanceId = instanceId;

      // Automatically start auto-capture if enabled
      let autoCaptureResult = null;
      if (this.config.enableAutoCapture !== false && this.autoCapture) {
        try {
          autoCaptureResult = await this.autoCapture.start(instanceId);
          logger.info(`Auto-capture started for ${instanceId}`);
        } catch (error) {
          logger.error(`Failed to start auto-capture for ${instanceId}`, { error: error.message });
          autoCaptureResult = { 
            error: error.message, 
            reason: 'Auto-capture initialization failed' 
          };
        }
      }

      logger.info(`Federation initialized for ${instanceId} with namespace structure`);

      const response = {
        success: true,
        instanceId,
        sessionId: session.id,
        message: `Instance ${instanceId} checked into federation with namespace initialized`
      };

      // Add auto-capture status if applicable
      if (autoCaptureResult) {
        response.autoCapture = {
          enabled: autoCaptureResult.success === true,
          streamKey: autoCaptureResult.streamKey,
          monitoring: autoCaptureResult.success === true,
          error: autoCaptureResult.error,
          reason: autoCaptureResult.reason
        };
      }

      return response;

    } catch (error) {
      logger.error('Federation initialization failed', { error: error.message });
      throw new Error(`Federation initialization failed: ${error.message}`);
    }
  }

  async rememberIdentity(content) {
    if (!this.redis) {
      throw new Error('Redis connection required');
    }

    // Use current instance if available
    let instanceId = this.currentInstanceId;
    
    if (!instanceId) {
      // Fallback to active session
      const session = await this.sessions.getActiveSession();
      if (!session || !session.instanceId) {
        throw new Error('No active session found. Please check in first.');
      }
      instanceId = session.instanceId;
    }
    const identityKey = `${instanceId}:identity`;

    try {
      await this.redis.set(identityKey, content);
      await this.redis.expire(identityKey, 30 * 24 * 60 * 60); // 30 days

      logger.info(`Identity remembered for ${instanceId}`);
      return {
        success: true,
        instanceId,
        type: 'identity',
        message: `Identity information stored for ${instanceId}`
      };
    } catch (error) {
      logger.error('Failed to remember identity', { error: error.message });
      throw new Error(`Failed to remember identity: ${error.message}`);
    }
  }

  async rememberContext(content) {
    if (!this.redis) {
      throw new Error('Redis connection required');
    }

    // Use current instance if available
    let instanceId = this.currentInstanceId;
    
    if (!instanceId) {
      // Fallback to active session
      const session = await this.sessions.getActiveSession();
      if (!session || !session.instanceId) {
        throw new Error('No active session found. Please check in first.');
      }
      instanceId = session.instanceId;
    }
    const contextKey = `${instanceId}:context`;

    try {
      await this.redis.set(contextKey, content);
      await this.redis.expire(contextKey, 30 * 24 * 60 * 60); // 30 days

      logger.info(`Context remembered for ${instanceId}`);
      return {
        success: true,
        instanceId,
        type: 'context',
        message: `Context information stored for ${instanceId}`
      };
    } catch (error) {
      logger.error('Failed to remember context', { error: error.message });
      throw new Error(`Failed to remember context: ${error.message}`);
    }
  }

  async rememberCuriosity(content) {
    if (!this.redis) {
      throw new Error('Redis connection required');
    }

    // Use current instance if available
    let instanceId = this.currentInstanceId;
    
    if (!instanceId) {
      // Fallback to active session
      const session = await this.sessions.getActiveSession();
      if (!session || !session.instanceId) {
        throw new Error('No active session found. Please check in first.');
      }
      instanceId = session.instanceId;
    }
    const curiosityKey = `${instanceId}:curiosity`;

    try {
      await this.redis.set(curiosityKey, content);
      await this.redis.expire(curiosityKey, 30 * 24 * 60 * 60); // 30 days

      logger.info(`Curiosity remembered for ${instanceId}`);
      return {
        success: true,
        instanceId,
        type: 'curiosity',
        message: `Curiosity information stored for ${instanceId}`
      };
    } catch (error) {
      logger.error('Failed to remember curiosity', { error: error.message });
      throw new Error(`Failed to remember curiosity: ${error.message}`);
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
        
        const delayMs = Math.min(1000 * Math.pow(2, attempt - 1), 2000); // Cap at 2 seconds
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
        // Stop auto-capture monitors
        if (this.autoCapture) {
          await this.autoCapture.shutdown();
          logger.info('Auto-capture monitors stopped');
        }
        
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