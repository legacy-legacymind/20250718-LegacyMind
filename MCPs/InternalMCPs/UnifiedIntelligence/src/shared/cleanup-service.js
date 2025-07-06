// src/shared/cleanup-service.js
import { redisManager } from './redis-manager.js';
import { KEY_SCHEMA } from './key-schema.js';
import { logger } from '../utils/logger.js';

export class CleanupService {
  constructor() {
    this.batchSize = 100;
    this.isRunning = false;
    this.stats = {
      lastRun: null,
      totalCleaned: 0,
      lastRunCleaned: 0,
      errors: []
    };
  }
  
  async runCleanup() {
    if (this.isRunning) {
      logger.info('Cleanup already in progress');
      return { success: false, message: 'Cleanup already in progress' };
    }
    
    this.isRunning = true;
    this.stats.lastRun = new Date().toISOString();
    this.stats.lastRunCleaned = 0;
    this.stats.errors = [];
    
    try {
      const client = redisManager.connections.get('default');
      if (!client || !client.isOpen) {
        throw new Error('Redis connection not available');
      }
      
      let totalCleaned = 0;
      
      // Clean expired memories from indices
      for (const type of ['identity', 'context', 'curiosity']) {
        const indexKey = KEY_SCHEMA.SEARCH_INDEX(type).key;
        const members = await client.zRange(indexKey, 0, -1);
        
        const pipeline = client.pipeline();
        let cleaned = 0;
        
        for (const memberId of members) {
          const memoryKey = `memory:${type}:${memberId}`;
          const exists = await client.exists(memoryKey);
          if (!exists) {
            pipeline.zRem(indexKey, memberId);
            cleaned++;
          }
        }
        
        if (cleaned > 0) {
          await pipeline.exec();
          totalCleaned += cleaned;
          logger.info(`Cleaned ${cleaned} expired entries from ${type} index`);
        }
      }
      
      // Clean old rate limit keys
      const rateLimitPattern = 'ratelimit:*';
      const rateLimitKeys = await this.scanKeys(client, rateLimitPattern);
      if (rateLimitKeys.length > 0) {
        // Rate limit keys have TTL, so we just check if they're expired
        for (const key of rateLimitKeys) {
          const ttl = await client.ttl(key);
          if (ttl === -1) {
            // No TTL set, delete it
            await client.del(key);
            totalCleaned++;
          }
        }
      }
      
      // Clean orphaned agent memory lists
      const agentPattern = 'agent:*:memories';
      const agentKeys = await this.scanKeys(client, agentPattern);
      
      for (const agentKey of agentKeys) {
        const members = await client.zRange(agentKey, 0, -1);
        const validMembers = [];
        
        for (const member of members) {
          const [type, memoryId] = member.split(':');
          const memoryKey = `memory:${type}:${memoryId}`;
          const exists = await client.exists(memoryKey);
          if (exists) {
            validMembers.push(member);
          }
        }
        
        if (validMembers.length < members.length) {
          await client.del(agentKey);
          if (validMembers.length > 0) {
            const pipeline = client.pipeline();
            for (const member of validMembers) {
              pipeline.zAdd(agentKey, { score: Date.now(), value: member });
            }
            await pipeline.exec();
          }
          totalCleaned += members.length - validMembers.length;
        }
      }
      
      // Clean old stream entries
      const streamPattern = 'stream:*:thoughts';
      const streamKeys = await this.scanKeys(client, streamPattern);
      
      for (const streamKey of streamKeys) {
        try {
          // Get stream info
          const info = await client.xInfoStream(streamKey);
          const streamLength = info.length;
          
          if (streamLength > 10000) {
            // Trim to last 10000 entries
            await client.xTrim(streamKey, 'MAXLEN', '~', 10000);
            logger.info(`Trimmed stream ${streamKey} from ${streamLength} to ~10000 entries`);
          }
        } catch (error) {
          // Stream might not exist
          logger.debug(`Stream ${streamKey} not found`);
        }
      }
      
      this.stats.lastRunCleaned = totalCleaned;
      this.stats.totalCleaned += totalCleaned;
      
      logger.info('Cleanup completed', {
        cleaned: totalCleaned,
        totalCleaned: this.stats.totalCleaned
      });
      
      return {
        success: true,
        cleaned: totalCleaned,
        timestamp: new Date().toISOString()
      };
      
    } catch (error) {
      this.stats.errors.push({
        timestamp: new Date().toISOString(),
        error: error.message
      });
      logger.error('Cleanup failed', { error: error.message });
      throw error;
    } finally {
      this.isRunning = false;
    }
  }
  
  async scanKeys(client, pattern) {
    const keys = [];
    let cursor = '0';
    
    do {
      const result = await client.scan(cursor, {
        MATCH: pattern,
        COUNT: this.batchSize
      });
      cursor = result.cursor;
      keys.push(...result.keys);
    } while (cursor !== '0');
    
    return keys;
  }
  
  getStats() {
    return {
      ...this.stats,
      isRunning: this.isRunning
    };
  }
}

export const cleanupService = new CleanupService();