import { logger } from '../../utils/logger.js';

export class AutoCaptureMonitor {
  constructor(redis, intelligence) {
    this.redis = redis;
    this.intelligence = intelligence;
    this.monitoring = new Map(); // instanceId -> monitor state
    this.intervals = new Map();  // instanceId -> interval ID
    this.thresholds = {
      autoCapture: 0.5
    };
  }

  async start(instanceId) {
    if (this.monitoring.has(instanceId)) {
      return {
        success: false,
        message: `Monitor already running for ${instanceId}`
      };
    }

    try {
      // Initialize monitor state
      this.monitoring.set(instanceId, {
        active: true,
        startTime: new Date().toISOString(),
        lastStreamId: '$', // Start from newest messages
        capturedCount: 0,
        cancelled: false
      });

      // Start real-time stream monitoring
      this.startStreamMonitoring(instanceId);

      logger.info(`Auto-capture monitor started for ${instanceId}`);

      return {
        success: true,
        message: `Auto-capture monitor started for ${instanceId}`,
        streamKey: `${instanceId}:conversation`
      };
    } catch (error) {
      logger.error('Failed to start auto-capture monitor', { error: error.message });
      return {
        success: false,
        error: error.message
      };
    }
  }

  async stop(instanceId) {
    const state = this.monitoring.get(instanceId);
    if (state) {
      state.cancelled = true;
      state.active = false;
    }
    
    this.monitoring.delete(instanceId);

    logger.info(`Auto-capture monitor stopped for ${instanceId}`);

    return {
      success: true,
      message: `Auto-capture monitor stopped for ${instanceId}`,
      capturedCount: state?.capturedCount || 0
    };
  }

  async status(instanceId) {
    const state = this.monitoring.get(instanceId);
    
    if (!state) {
      return {
        active: false,
        message: `No monitor running for ${instanceId}`
      };
    }

    return {
      active: true,
      instanceId,
      startTime: state.startTime,
      lastCheck: state.lastCheck,
      capturedCount: state.capturedCount,
      thresholds: this.thresholds
    };
  }

  async updateThresholds(newThresholds) {
    // Ensure newThresholds is an object
    if (typeof newThresholds === 'string') {
      try {
        newThresholds = JSON.parse(newThresholds);
      } catch (error) {
        return {
          success: false,
          error: 'Invalid JSON in thresholds'
        };
      }
    }
    
    this.thresholds = { ...this.thresholds, ...newThresholds };
    return {
      success: true,
      thresholds: this.thresholds
    };
  }

  async startStreamMonitoring(instanceId) {
    const state = this.monitoring.get(instanceId);
    if (!state) return;

    const streamKey = `${instanceId}:conversation`;
    
    // Start monitoring loop
    const monitor = async () => {
      while (state.active && !state.cancelled) {
        try {
          // Use XREAD with BLOCK to wait for new messages
          const result = await this.redis.xread(
            'BLOCK', 5000, // 5 second timeout
            'COUNT', 10,    // Read up to 10 messages at once
            'STREAMS', streamKey, state.lastStreamId
          );

          if (result && result.length > 0) {
            const [, messages] = result[0]; // Get messages from first stream
            
            for (const [id, fields] of messages) {
              if (!state.active) break;
              
              // Parse message fields
              const messageData = {};
              for (let i = 0; i < fields.length; i += 2) {
                messageData[fields[i]] = fields[i + 1];
              }
              
              const content = messageData.content || messageData.message;
              if (content && this.shouldCapture(content)) {
                // Auto-capture the thought
                const result = await this.intelligence.captureThought({
                  thought: content,
                  options: {
                    autoCapture: true,
                    confidence: this.calculateConfidence(content),
                    tags: ['auto-capture', instanceId]
                  },
                  sessionId: await this.getSessionId(instanceId),
                  instanceId
                });

                if (result.captured) {
                  state.capturedCount++;
                  logger.info(`Auto-captured thought for ${instanceId}`, {
                    thoughtId: result.captured.id,
                    streamId: id
                  });
                }
              }
              
              // Update last stream ID
              state.lastStreamId = id;
            }
          }
        } catch (error) {
          if (error.message.includes('timeout')) {
            // Timeout is expected, continue monitoring
            continue;
          }
          logger.error(`Stream monitoring error for ${instanceId}`, { 
            error: error.message 
          });
          await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1s before retry
        }
      }
      
      logger.info(`Stream monitoring stopped for ${instanceId}`);
    };

    // Start monitoring in background
    monitor().catch(error => {
      logger.error(`Fatal monitoring error for ${instanceId}`, { error: error.message });
    });
  }

  shouldCapture(content) {
    // Simple heuristics for now
    const significantPhrases = [
      'realized', 'important', 'problem', 'solution', 'idea',
      'need to', 'should', 'must', 'critical', 'key insight'
    ];

    const lowerContent = content.toLowerCase();
    return significantPhrases.some(phrase => lowerContent.includes(phrase));
  }

  calculateConfidence(content) {
    // Basic confidence calculation
    const length = content.length;
    if (length > 200) return 0.8;
    if (length > 100) return 0.6;
    return 0.4;
  }

  async getSessionId(instanceId) {
    // Get current session for instance
    const sessionKey = `${instanceId}:session`;
    const sessionData = await this.redis.get(sessionKey);
    if (sessionData) {
      const session = JSON.parse(sessionData);
      return session.id;
    }
    return null;
  }

  async shutdown() {
    // Stop all monitors
    for (const instanceId of this.monitoring.keys()) {
      await this.stop(instanceId);
    }
  }
}