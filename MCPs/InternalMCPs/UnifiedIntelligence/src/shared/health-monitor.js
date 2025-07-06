// src/shared/health-monitor.js
import { redisManager } from './redis-manager.js';
import { logger } from '../utils/logger.js';

export class HealthMonitor {
  constructor() {
    this.warningThresholds = {
      totalKeys: 1000000, // 1M keys warning
      memoryUsage: 1024 * 1024 * 1024, // 1GB warning
      uptimeHours: 24 * 7 // 7 days continuous operation
    };
  }

  async check() {
    try {
      // Redis health check
      const redisHealth = await redisManager.healthCheck();
      
      // Memory usage
      const memoryUsage = process.memoryUsage();
      
      // Process uptime
      const uptimeSeconds = process.uptime();
      const uptimeHours = uptimeSeconds / 3600;
      
      // Data growth check
      let dataGrowth = { totalKeys: 0, warning: false };
      try {
        const client = redisManager.connections.get('default');
        if (client && client.isOpen) {
          const dbSize = await client.dbSize();
          dataGrowth = {
            totalKeys: dbSize,
            warning: dbSize > this.warningThresholds.totalKeys,
            threshold: this.warningThresholds.totalKeys
          };
        }
      } catch (error) {
        logger.error('Failed to get Redis dbSize', { error: error.message });
      }
      
      // Redis info for detailed metrics
      let redisInfo = {};
      try {
        const client = redisManager.connections.get('default');
        if (client && client.isOpen) {
          const info = await client.info('memory');
          const lines = info.split('\r\n');
          for (const line of lines) {
            if (line.includes(':')) {
              const [key, value] = line.split(':');
              redisInfo[key] = value;
            }
          }
        }
      } catch (error) {
        logger.error('Failed to get Redis info', { error: error.message });
      }
      
      const healthCheck = {
        timestamp: new Date().toISOString(),
        redis: redisHealth,
        memory: {
          rss: memoryUsage.rss,
          heapTotal: memoryUsage.heapTotal,
          heapUsed: memoryUsage.heapUsed,
          external: memoryUsage.external,
          warning: memoryUsage.heapUsed > this.warningThresholds.memoryUsage
        },
        uptime: {
          seconds: uptimeSeconds,
          hours: uptimeHours.toFixed(2),
          warning: uptimeHours > this.warningThresholds.uptimeHours
        },
        dataGrowth,
        redisMemory: {
          used: redisInfo.used_memory || 'unknown',
          peak: redisInfo.used_memory_peak || 'unknown',
          rss: redisInfo.used_memory_rss || 'unknown'
        }
      };
      
      // Log warnings
      if (healthCheck.dataGrowth.warning) {
        logger.warn('Data growth warning', {
          totalKeys: dataGrowth.totalKeys,
          threshold: dataGrowth.threshold
        });
      }
      
      if (healthCheck.memory.warning) {
        logger.warn('Memory usage warning', {
          heapUsed: memoryUsage.heapUsed,
          threshold: this.warningThresholds.memoryUsage
        });
      }
      
      return healthCheck;
      
    } catch (error) {
      logger.error('Health check failed', { error: error.message });
      return {
        timestamp: new Date().toISOString(),
        error: error.message,
        status: 'unhealthy'
      };
    }
  }
  
  async getInstanceMetrics(instanceId) {
    try {
      const client = redisManager.connections.get('default');
      if (!client || !client.isOpen) {
        throw new Error('Redis connection not available');
      }
      
      // Count instance-specific keys
      const patterns = [
        `instance:${instanceId}:*`,
        `stream:${instanceId}:*`,
        `memory:*:*`, // Need to filter by source_agent_id
        `ratelimit:${instanceId}:*`
      ];
      
      let totalKeys = 0;
      for (const pattern of patterns) {
        const keys = await client.keys(pattern);
        totalKeys += keys.length;
      }
      
      // Get stream length
      const streamKey = `stream:${instanceId}:thoughts`;
      let streamLength = 0;
      try {
        streamLength = await client.xLen(streamKey);
      } catch (error) {
        // Stream might not exist
      }
      
      return {
        instanceId,
        totalKeys,
        streamLength,
        timestamp: new Date().toISOString()
      };
      
    } catch (error) {
      logger.error('Failed to get instance metrics', {
        instanceId,
        error: error.message
      });
      return {
        instanceId,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    }
  }
}

export const healthMonitor = new HealthMonitor();