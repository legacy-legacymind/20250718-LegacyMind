import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { UnifiedIntelligence } from './core/unified-intelligence.js';
import { logger } from './utils/logger.js';

class UnifiedIntelligenceServer {
  constructor() {
    this.uiThinkTool = {
      name: 'ui_think',
      description: `The core thinking tool for the Federation. Captures thoughts with automatic mode detection to Redis only.

Actions:
- capture: Process thoughts and save to Redis
- status: Get current session status  
- check_in: Initialize federation for instance
- help: Get detailed usage information

Features:
- Automatic mode detection (convo, design, debug, task, learn, decision, test)
- Redis-only storage for fast, simple thought capture
- Session management in memory

Philosophy: "Keep it simple" - Just capture thoughts to Redis, nothing else.`,
      inputSchema: {
        type: 'object',
        properties: {
          action: {
            type: 'string',
            enum: ['capture', 'status', 'check_in', 'help'],
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

    this.server = new Server(
      {
        name: 'unified-intelligence',
        version: '1.0.0',
        protocolVersion: '1.14.0',
      },
      {
        capabilities: {
          tools: { ui_think: this.uiThinkTool },
        },
      }
    );
    this.intelligence = null;
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
    this.setupHandlers();
  }

  setupHandlers() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [this.uiThinkTool],
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      if (name === 'ui_think') {
        try {
          const result = await this.intelligence.think(args);
          return {
            content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
          };
        } catch (error) {
          logger.error('Error in ui_think tool:', error);
          return {
            content: [{ type: 'text', text: `Error: ${error.message}` }],
            isError: true,
          };
        }
      }
      throw new Error(`Unknown tool: ${name}`);
    });
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    logger.info('UnifiedIntelligence MCP server started (Redis-only mode)');
  }
}

const server = new UnifiedIntelligenceServer();
server.initialize().then(() => {
  server.run().catch((error) => {
    logger.error('Fatal error during runtime:', error);
    process.exit(1);
  });
}).catch((error) => {
  logger.error('Fatal error during initialization:', error);
  process.exit(1);
});