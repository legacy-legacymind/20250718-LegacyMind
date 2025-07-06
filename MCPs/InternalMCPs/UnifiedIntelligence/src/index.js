#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { UnifiedIntelligence } from './core/unified-intelligence.js';
import { RememberTool } from './tools/remember-tool.js';
import { InjectTool } from './tools/inject-tool.js';
import { logger } from './utils/logger.js';
import { healthMonitor } from './shared/health-monitor.js';
import { cleanupService } from './shared/cleanup-service.js';

class UnifiedIntelligenceServer {
  constructor() {
    this.uiThinkTool = {
      name: 'ui_think',
      description: `The core thinking tool for the Federation. Captures thoughts with automatic mode detection to Redis only.

Actions:
- capture: Process thoughts and save to Redis
- status: Get current session status  
- check_in: Initialize federation for instance (identity only)
- monitor: Control auto-capture monitoring (start/stop/status/thresholds)
- help: Get detailed usage information

Note: Use ui_remember for persistent memory management and ui_inject for context loading

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
          options: {
            type: 'object',
            properties: {
              confidence: { type: 'number' },
              tags: { type: 'array', items: { type: 'string' } },
            },
          },
        },
      },
    };

    this.uiRememberTool = {
      name: 'ui_remember',
      description: `Persistent memory management for the Federation. Create and search memories across identity, context, and curiosity.

Actions:
- create: Store a new memory entry
- search: Search memories by query and tags
- list: List all memories of a specific type
- get: Retrieve a specific memory by ID
- update: Update an existing memory
- delete: Remove a memory
- help: Get detailed usage information

Memory Types:
- identity: Who the instance is, role, capabilities
- context: Current work, projects, environment
- curiosity: Research interests, explorations

Philosophy: "Remember what matters" - Structured, searchable persistent memory in Redis.`,
      inputSchema: {
        type: 'object',
        properties: {
          action: {
            type: 'string',
            enum: ['create', 'search', 'list', 'get', 'update', 'delete', 'help'],
            description: 'Action to perform'
          },
          memory_type: {
            type: 'string',
            enum: ['identity', 'context', 'curiosity'],
            description: 'Type of memory to work with'
          },
          content: {
            type: 'string',
            description: 'Content for create/update actions'
          },
          query: {
            type: 'string',
            description: 'Search query or memory ID for search/get/update/delete'
          },
          options: {
            type: 'object',
            properties: {
              tags: { 
                type: 'array', 
                items: { type: 'string' },
                description: 'Tags for categorization'
              },
              metadata: {
                type: 'object',
                description: 'Additional metadata'
              },
              limit: {
                type: 'number',
                description: 'Maximum results for search/list'
              },
              offset: {
                type: 'number',
                description: 'Pagination offset'
              }
            }
          }
        }
      }
    };

    this.uiInjectTool = {
      name: 'ui_inject',
      description: `Enhanced context injection with federation support. Load specialized knowledge, custom context, or federation instance data.

Actions:
- action: 'inject' - Perform injection (default)
- action: 'help' - Get detailed usage information

Injection Types:
- type: 'context' - Load custom files or URLs
- type: 'expert' - Load expert knowledge modules
- type: 'federation' - Load context from another instance

Expert Modules Available:
- docker: Docker containerization expertise
- mcp: Model Context Protocol development
- postgresql: PostgreSQL database expertise
- qdrant: Qdrant vector database expertise  
- redis: Redis in-memory database expertise

Federation Features:
- Cross-instance context loading
- Parallel data retrieval
- Graceful partial loading
- Service-oriented architecture

Philosophy: "Knowledge on demand" - Inject relevant expertise exactly when needed, from any source.`,
      inputSchema: {
        type: 'object',
        properties: {
          action: {
            type: 'string',
            enum: ['inject', 'help'],
            description: 'Action to perform (defaults to inject)'
          },
          type: {
            type: 'string',
            enum: ['context', 'expert', 'federation'],
            description: 'Type of injection: context for general knowledge, expert for specialized modules, federation for instance context'
          },
          source: {
            oneOf: [
              {
                type: 'string',
                description: 'For context: file path or URL. For expert: module name'
              },
              {
                type: 'object',
                properties: {
                  instance: {
                    type: 'string',
                    description: 'Target instance ID (e.g., CCI, CCD, CCB)'
                  },
                  mode: {
                    type: 'string',
                    enum: ['default', 'custom'],
                    description: 'Mode for federation injection',
                    default: 'default'
                  }
                },
                required: ['instance'],
                description: 'For federation: instance configuration'
              }
            ],
            description: 'Source of content to inject'
          },
          validate: {
            type: 'boolean',
            description: 'Whether to validate the injected content',
            default: true
          }
        },
        required: ['type', 'source']
      }
    };

    this.server = new Server(
      {
        name: 'unified-intelligence',
        version: '1.0.0',
        protocolVersion: '1.14.0',
      },
      {
        capabilities: {
          tools: { 
            ui_think: this.uiThinkTool,
            ui_remember: this.uiRememberTool,
            ui_inject: this.uiInjectTool
          },
        },
      }
    );
    this.intelligence = null;
    this.rememberTool = null;
    this.injectTool = null;
    this.healthCheckInterval = null;
    this.cleanupInterval = null;
    this.setupHandlers();
  }

  async initialize() {
    // Log environment variables for debugging
    logger.info('Environment check', {
      REDIS_HOST: process.env.REDIS_HOST || 'not set',
      REDIS_PORT: process.env.REDIS_PORT || 'not set',
      REDIS_PASSWORD: process.env.REDIS_PASSWORD ? 'set' : 'not set',
      REDIS_URL: process.env.REDIS_URL ? 'set' : 'not set'
    });
    
    // Create UnifiedIntelligence with Redis config only
    const uiConfig = {
      redisUrl: process.env.REDIS_URL || 'redis://localhost:6379'
    };
    
    logger.info('Initializing UnifiedIntelligence with Redis-only config', {
      redisUrl: uiConfig.redisUrl.replace(/:([^:@]+)@/, ':***@')
    });
    
    this.intelligence = new UnifiedIntelligence(uiConfig);
    
    // Wait for Redis to be fully initialized
    if (this.intelligence.initializationPromise) {
      await this.intelligence.initializationPromise;
    }
    
    // Initialize RememberTool with Redis and SessionManager
    if (this.intelligence.redis && this.intelligence.sessions) {
      this.rememberTool = new RememberTool(this.intelligence.redis, this.intelligence.sessions);
      // Share the current instance ID context
      if (this.intelligence.currentInstanceId) {
        this.rememberTool.setCurrentInstanceId(this.intelligence.currentInstanceId);
      }
      logger.info('RememberTool initialized successfully');
    } else {
      logger.warn('RememberTool not initialized - Redis or SessionManager not available');
    }
    
    // Initialize InjectTool with logger, SessionManager, and RememberTool
    if (this.intelligence.sessions) {
      this.injectTool = new InjectTool(logger, this.intelligence.sessions, this.rememberTool);
      logger.info('InjectTool initialized successfully');
    } else {
      logger.warn('InjectTool not initialized - SessionManager not available');
    }
    
    this.setupHandlers();
  }

  setupHandlers() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [this.uiThinkTool, this.uiRememberTool, this.uiInjectTool],
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        switch (name) {
          case 'ui_think': {
            const result = await this.intelligence.think(args);
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }
          
          case 'ui_remember': {
            if (!this.rememberTool) {
              throw new Error('RememberTool not initialized. Please check in first.');
            }
            
            // Sync current instance ID if available
            if (this.intelligence.currentInstanceId) {
              this.rememberTool.setCurrentInstanceId(this.intelligence.currentInstanceId);
            }
            
            const result = await this.rememberTool.execute(args);
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }
          
          case 'ui_inject': {
            if (!this.injectTool) {
              throw new Error('InjectTool not initialized. Please check in first.');
            }
            
            const result = await this.injectTool.execute(args);
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }
          
          default:
            throw new Error(`Unknown tool: ${name}`);
        }
      } catch (error) {
        logger.error(`Error in ${name} tool:`, error);
        return {
          content: [{ type: 'text', text: `Error: ${error.message}` }],
          isError: true,
        };
      }
    });
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    logger.info('UnifiedIntelligence MCP server started (Redis-only mode)');
    
    // Start background services
    this.startBackgroundServices();
  }
  
  
  startBackgroundServices() {
    // Start health monitoring every 30 seconds
    this.healthCheckInterval = setInterval(async () => {
      try {
        const health = await healthMonitor.check();
        
        // Log warnings when data growth exceeds thresholds
        if (health.dataGrowth?.warning) {
          logger.warn('Data growth threshold exceeded', {
            totalKeys: health.dataGrowth.totalKeys,
            threshold: health.dataGrowth.threshold
          });
        }
        
        if (health.memory?.warning) {
          logger.warn('Memory usage threshold exceeded', {
            heapUsed: health.memory.heapUsed,
            threshold: healthMonitor.warningThresholds.memoryUsage
          });
        }
        
        if (health.uptime?.warning) {
          logger.warn('Uptime threshold exceeded', {
            hours: health.uptime.hours,
            threshold: healthMonitor.warningThresholds.uptimeHours / 24 + ' days'
          });
        }
        
        logger.debug('Health check completed', health);
      } catch (error) {
        logger.error('Health check failed', { error: error.message });
      }
    }, 30000); // 30 seconds
    
    // Start cleanup every hour
    this.cleanupInterval = setInterval(async () => {
      try {
        logger.info('Starting scheduled cleanup');
        const result = await cleanupService.runCleanup();
        logger.info('Scheduled cleanup completed', result);
      } catch (error) {
        logger.error('Scheduled cleanup failed', { error: error.message });
      }
    }, 3600000); // 1 hour
    
    logger.info('Background services started', {
      healthCheck: 'every 30 seconds',
      cleanup: 'every hour'
    });
  }
  
  async shutdown() {
    logger.info('Shutting down background services');
    
    // Stop intervals
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
    
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    
    // Wait for any running cleanup to finish
    if (cleanupService.isRunning) {
      logger.info('Waiting for cleanup to finish');
      let attempts = 0;
      while (cleanupService.isRunning && attempts < 30) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;
      }
    }
    
    // Shutdown Redis manager
    const { redisManager } = await import('./shared/redis-manager.js');
    await redisManager.shutdown();
    
    logger.info('Background services stopped');
  }
}

const server = new UnifiedIntelligenceServer();

// Graceful shutdown handlers
process.on('SIGINT', async () => {
  logger.info('Received SIGINT, shutting down gracefully');
  await server.shutdown();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  logger.info('Received SIGTERM, shutting down gracefully');
  await server.shutdown();
  process.exit(0);
});

// Initialize and run in stdio mode (spawn-per-call)
server.initialize().then(async () => {
  await server.run().catch((error) => {
    logger.error('Fatal error during runtime:', error);
    process.exit(1);
  });
}).catch((error) => {
  logger.error('Fatal error during initialization:', error);
  process.exit(1);
});