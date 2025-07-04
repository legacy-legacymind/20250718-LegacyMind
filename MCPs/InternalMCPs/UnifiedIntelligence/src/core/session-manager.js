import { logger } from '../utils/logger.js';
import { v4 as uuidv4 } from 'uuid';

export class SessionManager {
  constructor(redisClient) {
    this.redis = redisClient;
  }

  /**
   * Gets the current active session for an instance, or creates a new one.
   * Uses atomic Lua script to prevent race conditions.
   * @param {string} instanceId - The ID of the instance (e.g., 'CCI', 'CCD').
   * @returns {Promise<object>} - The active or newly created session object.
   */
  async getCurrentOrCreate(instanceId) {
    if (!this.redis) {
      throw new Error('Redis connection required for session management');
    }
    
    // Input validation to prevent key injection
    if (!instanceId || typeof instanceId !== 'string' || instanceId.trim() === '' || instanceId.includes(':')) {
      throw new Error('Invalid instanceId provided');
    }

    const sessionKey = `session:${instanceId}`;
    const activitySetKey = 'z_session_activity';
    const currentTime = new Date().toISOString();
    const unixTime = Math.floor(Date.now() / 1000);
    
    // Atomic Lua script to check existence and create if needed
    const luaScript = `
      local sessionKey = KEYS[1]
      local activitySetKey = KEYS[2]
      local instanceId = ARGV[1]
      local currentTime = ARGV[2]
      local unixTime = ARGV[3]
      local sessionId = ARGV[4]
      
      -- Check if session exists
      local existingSession = redis.call('HGETALL', sessionKey)
      if #existingSession > 0 then
        -- Session exists, update activity and return
        redis.call('HSET', sessionKey, 'lastActive', currentTime)
        redis.call('ZADD', activitySetKey, unixTime, sessionKey)
        redis.call('EXPIRE', sessionKey, 86400)
        return existingSession
      else
        -- Create new session
        local session = {
          'id', sessionId,
          'instanceId', instanceId,
          'status', 'active',
          'createdAt', currentTime,
          'lastActive', currentTime,
          'thoughtCount', 0
        }
        redis.call('HSET', sessionKey, unpack(session))
        redis.call('ZADD', activitySetKey, unixTime, sessionKey)
        redis.call('EXPIRE', sessionKey, 86400)
        return session
      end
    `;
    
    try {
      const result = await this.redis.eval(
        luaScript,
        2,
        sessionKey,
        activitySetKey,
        instanceId,
        currentTime,
        unixTime,
        uuidv4()
      );
      
      // Convert Redis array result to object
      const session = {};
      for (let i = 0; i < result.length; i += 2) {
        session[result[i]] = result[i + 1];
      }
      
      // Convert string values back to appropriate types
      return {
        id: session.id,
        instanceId: session.instanceId,
        status: session.status,
        createdAt: session.createdAt,
        lastActive: session.lastActive,
        thoughtCount: parseInt(session.thoughtCount) || 0
      };
    } catch (error) {
      logger.error('Error in atomic session creation', { instanceId, error: error.message });
      throw new Error(`Failed to get or create session: ${error.message}`);
    }
  }

  /**
   * Initialize a session (used by federation)
   * @param {string} instanceId - The ID of the instance
   * @returns {Promise<object>} - The initialized session
   */
  async initializeSession(instanceId) {
    return await this.getCurrentOrCreate(instanceId);
  }

  /**
   * Get the currently active session using Redis Sorted Set (O(1) operation)
   * @returns {Promise<object|null>} - The active session or null
   * @throws {Error} - Redis connection errors are thrown, not swallowed
   */
  async getActiveSession() {
    if (!this.redis) {
      throw new Error('Redis connection not available');
    }
    
    try {
      const activitySetKey = 'z_session_activity';
      
      // Get most recent session (highest score) - O(1) operation
      const recentSessions = await this.redis.zrevrange(activitySetKey, 0, 0);
      
      if (!recentSessions || recentSessions.length === 0) {
        return null; // No sessions found
      }
      
      const sessionKey = recentSessions[0];
      const sessionData = await this.redis.hgetall(sessionKey);
      
      if (!sessionData || !sessionData.id) {
        // Clean up orphaned entry in sorted set
        await this.redis.zrem(activitySetKey, sessionKey);
        return null;
      }
      
      return {
        id: sessionData.id,
        instanceId: sessionData.instanceId,
        status: sessionData.status,
        createdAt: sessionData.createdAt,
        lastActive: sessionData.lastActive,
        thoughtCount: parseInt(sessionData.thoughtCount) || 0
      };
    } catch (error) {
      logger.error('Error getting active session', { error: error.message });
      throw new Error(`Failed to get active session: ${error.message}`);
    }
  }

  /**
   * Update session activity and maintain sorted set for efficient lookups
   * @param {string} instanceId - The instance ID
   * @throws {Error} - Validation and Redis errors are thrown
   */
  async updateActivity(instanceId) {
    if (!this.redis) {
      throw new Error('Redis connection not available');
    }
    
    // Input validation to prevent key injection
    if (!instanceId || typeof instanceId !== 'string' || instanceId.trim() === '' || instanceId.includes(':')) {
      throw new Error('Invalid instanceId provided');
    }
    
    const sessionKey = `session:${instanceId}`;
    const activitySetKey = 'z_session_activity';
    const currentTime = new Date().toISOString();
    const unixTime = Math.floor(Date.now() / 1000);
    
    try {
      // Get current thought count
      const currentCount = await this.redis.hget(sessionKey, 'thoughtCount');
      const newCount = (parseInt(currentCount) || 0) + 1;
      
      // Update session activity atomically using pipeline
      const pipeline = this.redis.pipeline();
      pipeline.hset(sessionKey, {
        'lastActive': currentTime,
        'thoughtCount': newCount
      });
      pipeline.zadd(activitySetKey, unixTime, sessionKey);
      pipeline.expire(sessionKey, 24 * 60 * 60);
      
      // Check pipeline results for errors
      const results = await pipeline.exec();
      if (results && results.some(result => result[0] !== null)) {
        const errors = results.filter(r => r[0] !== null).map(r => r[0].message);
        logger.error('Pipeline execution had errors', { instanceId, errors });
        throw new Error(`Pipeline execution failed: ${errors.join(', ')}`);
      }
      
      logger.debug(`Updated activity for session ${instanceId}, count: ${newCount}`);
    } catch (error) {
      logger.error('Error updating session activity', { instanceId, error: error.message });
      throw new Error(`Failed to update session activity: ${error.message}`);
    }
  }

  /**
   * End a session and clean up from activity tracking
   * @param {string} instanceId - The instance ID
   * @throws {Error} - Validation and Redis errors are thrown
   */
  async endSession(instanceId) {
    if (!this.redis) {
      throw new Error('Redis connection not available');
    }
    
    // Input validation to prevent key injection
    if (!instanceId || typeof instanceId !== 'string' || instanceId.trim() === '' || instanceId.includes(':')) {
      throw new Error('Invalid instanceId provided');
    }
    
    const sessionKey = `session:${instanceId}`;
    const activitySetKey = 'z_session_activity';
    
    try {
      // Get session data before ending
      const sessionData = await this.redis.hgetall(sessionKey);
      if (sessionData && sessionData.id) {
        // Use pipeline for atomic completion
        const pipeline = this.redis.pipeline();
        pipeline.hset(sessionKey, 'status', 'completed');
        pipeline.expire(sessionKey, 60 * 60); // 1 hour for completed sessions
        pipeline.zrem(activitySetKey, sessionKey); // Remove from activity tracking
        
        const results = await pipeline.exec();
        if (results && results.some(result => result[0] !== null)) {
          const errors = results.filter(r => r[0] !== null).map(r => r[0].message);
          throw new Error(`Pipeline execution failed: ${errors.join(', ')}`);
        }
        
        logger.info(`Session ${sessionData.id} for ${instanceId} completed.`);
      }
    } catch (error) {
      logger.error('Error ending session', { instanceId, error: error.message });
      throw new Error(`Failed to end session: ${error.message}`);
    }
  }
}