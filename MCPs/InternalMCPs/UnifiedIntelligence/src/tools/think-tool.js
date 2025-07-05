import { logger } from '../utils/logger.js';

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
  }

  async handle(args) {
    const { action = 'capture' } = args;
    
    logger.info(`ThinkTool: Handling action '${action}'`);

    try {
      switch (action) {
        case 'capture':
          return await this.handleCapture(args);
        
        case 'status':
          return await this.handleStatus(args);
        
        case 'check_in':
          return await this.handleCheckIn(args);
        
        case 'monitor':
          return await this.handleMonitor(args);
        
        case 'help':
          return await this.handleHelp();
        
        default:
          throw new Error(`Unknown action: ${action}`);
      }
    } catch (error) {
      logger.error(`ThinkTool: Error during action '${action}'`, { error: error.message });
      throw error;
    }
  }

  async handleCapture(args) {
    const { thought, options = {} } = args;
    
    if (!thought || typeof thought !== 'string') {
      throw new Error('A non-empty "thought" string is required for the "capture" action.');
    }
    
    if (!this.intelligence.sessions) {
      throw new Error('Session manager not initialized. Redis connection required.');
    }
    
    // Use current instance or get active session
    let instanceId = this.intelligence.currentInstanceId;
    let sessionId;
    
    if (instanceId) {
      // Get session for current instance
      const session = await this.intelligence.sessions.getCurrentOrCreate(instanceId);
      sessionId = session.id;
    } else {
      // Fallback to active session
      const session = await this.intelligence.sessions.getActiveSession();
      if (!session || !session.instanceId) {
        throw new Error('No active session found. Please check in first with an instance identity.');
      }
      instanceId = session.instanceId;
      sessionId = session.id;
    }
    
    // Capture thought and update session activity
    const result = await this.intelligence.captureThought({ 
      thought, 
      options, 
      sessionId,
      instanceId 
    });
    
    // Update session activity after capturing thought
    await this.intelligence.sessions.updateActivity(instanceId);
    
    return result;
  }

  async handleStatus(args) {
    // Use current instance if available
    if (this.intelligence.currentInstanceId) {
      const session = await this.intelligence.sessions.getCurrentOrCreate(this.intelligence.currentInstanceId);
      return await this.intelligence.getSessionStatus(session.id);
    } else {
      // Fallback to active session
      const session = await this.intelligence.sessions.getActiveSession();
      if (!session) {
        return {
          status: 'no_active_session',
          message: 'No active session found.'
        };
      }
      return await this.intelligence.getSessionStatus(session.id);
    }
  }

  async handleCheckIn(args) {
    const { identity } = args;
    if (!identity || !identity.name) {
      throw new Error('Identity information with name is required for check_in action');
    }
    return await this.intelligence.initializeFederation(identity);
  }

  async handleMonitor(args) {
    const { operation = 'status', thresholds, options = {} } = args;
    
    if (!this.intelligence.autoCapture) {
      throw new Error('Auto-capture monitor not initialized');
    }
    
    switch (operation) {
      case 'start':
        const instanceForStart = this.intelligence.currentInstanceId || options.instance;
        if (!instanceForStart) {
          throw new Error('Instance ID required to start monitor');
        }
        return await this.intelligence.autoCapture.start(instanceForStart);
        
      case 'stop':
        const instanceForStop = this.intelligence.currentInstanceId || options.instance;
        if (!instanceForStop) {
          throw new Error('Instance ID required to stop monitor');
        }
        return await this.intelligence.autoCapture.stop(instanceForStop);
        
      case 'status':
        const instanceForStatus = this.intelligence.currentInstanceId || options.instance;
        if (!instanceForStatus) {
          throw new Error('Instance ID required for monitor status');
        }
        return await this.intelligence.autoCapture.status(instanceForStatus);
        
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
      version: '2.0',
      description: 'UnifiedIntelligence: Simple thought capture to Redis',
      actions: {
        capture: {
          description: 'Capture a thought to Redis',
          required: ['thought'],
          optional: ['options'],
          example: '{ "action": "capture", "thought": "your thought content", "options": { "confidence": 0.8, "tags": ["design", "api"] } }'
        },
        status: {
          description: 'Get current session status',
          required: [],
          optional: [],
          example: '{ "action": "status" }'
        },
        check_in: {
          description: 'Initialize instance with identity',
          required: ['identity'],
          optional: [],
          example: '{ "action": "check_in", "identity": { "name": "CCI", "id": "cci-001", "type": "intelligence", "role": "specialist" } }'
        },
        monitor: {
          description: 'Control auto-capture monitoring',
          operations: {
            start: 'Start monitoring for an instance',
            stop: 'Stop monitoring for an instance', 
            status: 'Get monitoring status',
            thresholds: 'Update monitoring thresholds'
          },
          examples: [
            '{ "action": "monitor", "operation": "start" }',
            '{ "action": "monitor", "operation": "stop" }',
            '{ "action": "monitor", "operation": "status" }',
            '{ "action": "monitor", "operation": "thresholds", "thresholds": { "tokenUsage": 1000, "timeInterval": 10, "messageCount": 20 } }'
          ]
        },
        help: {
          description: 'Get this help information',
          required: [],
          optional: [],
          example: '{ "action": "help" }'
        }
      },
      features: {
        'Mode Detection': 'Automatically detects conversation mode (convo, design, debug, task, learn, decision, test)',
        'Redis Storage': 'Fast, simple thought capture directly to Redis',
        'Session Management': 'Lightweight in-memory session tracking',
        'Instance Support': 'Multi-instance federation support',
        'Auto-Capture': 'Automatic monitoring and capture based on configurable thresholds'
      },
      philosophy: '"Keep it simple" - Just capture thoughts to Redis, nothing else.'
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