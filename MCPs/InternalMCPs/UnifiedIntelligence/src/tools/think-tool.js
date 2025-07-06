// src/tools/think-tool.js
import { redisManager } from '../shared/redis-manager.js';
import { ThinkSchemas } from '../shared/validators.js';
import { KEY_SCHEMA } from '../shared/key-schema.js';
import { rateLimiter } from '../shared/rate-limiter.js';
import { logger } from '../utils/logger.js';
import crypto from 'crypto';

export const UI_THINK_TOOL = {
  name: 'ui_think',
  description: `The core thinking tool for the Federation. Captures thoughts with automatic mode detection to Redis only.

Actions:
- capture: Process thoughts and save to Redis
- status: Get current session status  
- check_in: Initialize federation for instance
- monitor: Control auto-capture monitoring (start/stop/status/thresholds)
- help: Get detailed usage information

Features:
- Automatic mode detection (convo, design, debug, task, learn, decision, test)
- Redis-only storage for fast, simple thought capture
- Session management in memory
- Identity and context persistence

Philosophy: "Keep it simple" - Just capture thoughts to Redis, nothing else.`,
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['capture', 'status', 'check_in', 'monitor', 'help'],
        description: 'Action to perform (defaults to capture)',
      },
      thought: {
        type: 'string',
        description: 'The thought content (required for capture)',
      },
      identity: {
        type: 'object',
        description: 'Identity information for check_in action',
        properties: {
          name: { type: 'string', description: 'Instance name (e.g., CCI, CCD, CCB)' },
          id: { type: 'string', description: 'Instance ID' },
          type: { type: 'string', description: 'Instance type' },
          role: { type: 'string', description: 'Instance role' }
        }
      },
      operation: {
        type: 'string',
        enum: ['start', 'stop', 'status', 'thresholds'],
        description: 'Monitor operation type (for monitor action)',
      },
      thresholds: {
        type: 'object',
        description: 'Threshold configuration for monitor action',
        properties: {
          tokenUsage: { type: 'number', description: 'Token usage threshold' },
          timeInterval: { type: 'number', description: 'Time interval in minutes' },
          messageCount: { type: 'number', description: 'Message count threshold' }
        }
      },
      options: {
        type: 'object',
        properties: {
          confidence: { type: 'number' },
          tags: { type: 'array', items: { type: 'string' } },
          instance: { type: 'string', description: 'Instance ID for monitor operations' }
        },
      },
    },
  },
};

export class ThinkTool {
    constructor(intelligence) {
        this.intelligence = intelligence;
        this.rateLimits = {
            capture: { max: 100, window: 60 }, // 100/minute
            check_in: { max: 10, window: 3600 } // 10/hour
        };
    }

    async handle(args) {
        const { action = 'capture', identity } = args;
        const instanceId = identity?.name || this.intelligence.currentInstanceId || 'anonymous';

        logger.info(`ThinkTool: Handling action '${action}' for instance '${instanceId}'`);

        try {
            // Rate limiting
            if (this.rateLimits[action]) {
                const limited = await rateLimiter.check(
                    instanceId,
                    action,
                    this.rateLimits[action]
                );
                
                if (limited) {
                    throw new Error(`Rate limit exceeded for action '${action}'`);
                }
            }
        
            switch (action) {
                case 'capture':
                    return await this.handleCapture(args, instanceId);
                
                case 'status':
                    return await this.handleStatus(args, instanceId);
                
                case 'check_in':
                    return await this.handleCheckIn(args);
                
                case 'monitor':
                    return await this.handleMonitor(args, instanceId);
                
                case 'help':
                    return await this.handleHelp();
                
                default:
                    throw new Error(`Unknown action: ${action}`);
            }
        } catch (error) {
            logger.error(`ThinkTool: Error during action '${action}'`, { error: error.message, instanceId });
            throw error;
        }
    }

    async handleCapture(args, instanceId) {
        const validated = ThinkSchemas.capture.parse({ ...args, instanceId });
        const correlationId = crypto.randomUUID();
        
        return redisManager.execute('default', async () => {
            const client = redisManager.connections.get('default');
            const keyConfig = KEY_SCHEMA.THOUGHTS_STREAM(validated.instanceId);
            
            const transaction = client.multi();
            
            transaction.xAdd(keyConfig.key, '*', {
                content: validated.thought,
                confidence: validated.options?.confidence || 0.5,
                tags: JSON.stringify(validated.options?.tags || []),
                timestamp: new Date().toISOString(),
                source_agent_id: validated.instanceId,
                correlationId
            });
            
            transaction.expire(keyConfig.key, keyConfig.ttl);
            
            const results = await transaction.exec();
            
            // Verify atomic transaction succeeded
            if (!results || results.some(r => r === null)) {
                throw new Error('Failed to capture thought atomically');
            }
            
            return {
                success: true,
                thoughtId: results[0],
                correlationId,
                message: 'Thought captured successfully'
            };
        });
    }

    async handleStatus(args, instanceId) {
        if (instanceId === 'anonymous') {
             return {
                status: 'no_active_session',
                message: 'No active session found. Please check in first.'
            };
        }
        const session = await this.intelligence.sessions.getCurrentOrCreate(instanceId);
        return await this.intelligence.getSessionStatus(session.id);
    }

    async handleCheckIn(args) {
        const validated = ThinkSchemas.check_in.parse(args);
        const correlationId = crypto.randomUUID();
        const instanceName = validated.identity.name;
        
        return redisManager.execute('default', async () => {
            const client = redisManager.connections.get('default');
            const publisher = redisManager.connections.get('pubsub');
            
            const transaction = client.multi();
            
            const identityKeyConfig = KEY_SCHEMA.IDENTITY(instanceName);
            transaction.hSet(identityKeyConfig.key, {
                ...validated.identity,
                lastCheckIn: new Date().toISOString(),
                correlationId
            });
            
            // In v3, session management is simplified. We'll just set the identity.
            // The concept of a separate session object is removed for simplicity.
            
            transaction.expire(identityKeyConfig.key, identityKeyConfig.ttl);
            
            const results = await transaction.exec();
            
            // Verify atomic transaction succeeded
            if (!results || results.some(r => r === null)) {
                throw new Error('Failed to complete check-in atomically');
            }
            
            await publisher.publish('federation:events', JSON.stringify({
                event: 'check_in_complete',
                instanceId: instanceName,
                correlationId,
                timestamp: new Date().toISOString()
            }));

            // Set current instance on successful check-in
            this.intelligence.currentInstanceId = instanceName;
            
            return {
                success: true,
                instanceId: instanceName,
                correlationId,
                federation_initialized: true,
                next_steps: [
                    'Run bash date/time for timestamp',
                    'Use ui_inject to load context if needed'
                ],
                message: 'Federation check-in complete. Instance initialized.'
            };
        });
    }

    async handleMonitor(args, instanceId) {
        const { operation = 'status', thresholds } = args;
        
        if (!this.intelligence.autoCapture) {
            throw new Error('Auto-capture monitor not initialized');
        }
        if (instanceId === 'anonymous') {
            throw new Error('Instance ID required for monitor operations');
        }
        
        switch (operation) {
            case 'start':
                return await this.intelligence.autoCapture.start(instanceId);
            case 'stop':
                return await this.intelligence.autoCapture.stop(instanceId);
            case 'status':
                return await this.intelligence.autoCapture.status(instanceId);
            case 'thresholds':
                if (!thresholds) {
                    throw new Error('Thresholds required for update operation');
                }
                return await this.intelligence.autoCapture.updateThresholds(thresholds);
            default:
                throw new Error(`Unknown monitor operation: ${operation}`);
        }
    }

    async handleHelp() {
        return {
            tool: 'ui_think',
            version: '3.0',
            description: 'UnifiedIntelligence: Secure thought capture to Redis with rate limiting and atomic operations.',
            actions: {
                capture: {
                    description: 'Capture a thought to Redis stream',
                    required: ['thought'],
                    optional: ['options', 'instanceId'],
                    example: '{ "action": "capture", "thought": "your thought", "instanceId": "CCI" }'
                },
                status: {
                    description: 'Get current instance status',
                    example: '{ "action": "status", "instanceId": "CCI" }'
                },
                check_in: {
                    description: 'Initialize federation for instance (identity only)',
                    required: ['identity'],
                    example: '{ "action": "check_in", "identity": { "name": "CCI", "type": "intelligence", "role": "specialist" } }',
                    note: 'Focuses on federation initialization. Use ui_inject for context loading.'
                },
                monitor: {
                    description: 'Control auto-capture monitoring',
                    operations: {
                        start: 'Start monitoring',
                        stop: 'Stop monitoring',
                        status: 'Get monitoring status',
                        thresholds: 'Update thresholds'
                    },
                    example: '{ "action": "monitor", "operation": "start", "instanceId": "CCI" }'
                },
                help: {
                    description: 'Get this help information',
                    example: '{ "action": "help" }'
                }
            }
        };
    }
}

export function createThinkTool(intelligence) {
  const tool = new ThinkTool(intelligence);
  return {
    definition: UI_THINK_TOOL,
    handler: (args) => tool.handle(args)
  };
}