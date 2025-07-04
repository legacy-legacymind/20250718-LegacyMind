#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

import { CCMCPManager } from './managers/CCMCPManager.js';
import { GMCPManager } from './managers/GMCPManager.js';
import { ToolManager } from './managers/ToolManager.js';
import { config, validateConfig } from './utils/config.js';
import { logger } from './utils/logger.js';
import { FederationContext } from './types/index.js';
import { FederationError } from './utils/errors.js';

class FederationMCPServer {
  private server: Server;
  private ccmcpManager: CCMCPManager;
  private gmcpManager: GMCPManager;
  private toolManager: ToolManager;
  private context: FederationContext;

  constructor() {
    this.server = new Server(
      {
        name: 'federation-mcp',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.ccmcpManager = new CCMCPManager(config.ccmcpTimeout);
    this.gmcpManager = new GMCPManager(config.gmcpTimeout);
    this.toolManager = new ToolManager(config.cacheTtl);
    
    this.context = {
      config,
      ccmcpManager: this.ccmcpManager,
      gmcpManager: this.gmcpManager,
    };
  }

  async initialize(): Promise<void> {
    try {
      logger.info('Initializing Federation MCP Server');
      
      // Validate configuration
      validateConfig(config);
      logger.debug('Configuration validated', { config });

      // Set up request handlers
      this.setupHandlers();

      // Test connections to both agents
      await this.testConnections();

      logger.info('Federation MCP Server initialized successfully');
    } catch (error) {
      logger.fatal('Failed to initialize Federation MCP Server', { error });
      throw error;
    }
  }

  private async testConnections(): Promise<void> {
    logger.debug('Testing connections to CCMCP and GMCP');
    
    const ccmcpAvailable = await this.ccmcpManager.ping();
    const gmcpAvailable = await this.gmcpManager.ping();

    if (!ccmcpAvailable && !gmcpAvailable) {
      throw new Error('Both CCMCP and GMCP are unavailable');
    }

    if (!ccmcpAvailable) {
      logger.warn('CCMCP is not available - some features may be limited');
    }

    if (!gmcpAvailable) {
      logger.warn('GMCP is not available - some features may be limited');
    }

    logger.info('Connection test completed', { 
      ccmcpAvailable, 
      gmcpAvailable 
    });
  }

  private setupHandlers(): void {
    // Handle list tools request
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      logger.debug('Listing available tools');
      return {
        tools: this.toolManager.listTools(),
      };
    });

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;
      const startTime = Date.now();

      logger.info('Executing tool', { name, args });

      try {
        const result = await this.toolManager.executeTool(name, args, this.context);
        const executionTime = Date.now() - startTime;

        logger.info('Tool execution completed', { 
          name, 
          executionTime,
          success: result.success 
        });

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      } catch (error) {
        const executionTime = Date.now() - startTime;
        const isFederationError = error instanceof FederationError;

        const errorResponse = {
          success: false,
          error: {
            message: error instanceof Error ? error.message : String(error),
            code: isFederationError ? error.code : 'INTERNAL_SERVER_ERROR',
            status: isFederationError ? error.status : 500,
          },
          tool: name,
          executionTime,
          timestamp: new Date().toISOString(),
        };
        
        logger.error('Tool execution failed', { 
          name, 
          executionTime,
          error: errorResponse.error
        });

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(errorResponse, null, 2),
            },
          ],
          isError: true,
        };
      }
    });
  }

  async start(): Promise<void> {
    try {
      await this.initialize();
      
      const transport = new StdioServerTransport();
      await this.server.connect(transport);
      
      logger.info('Federation MCP Server started successfully');
      logger.info('Available tools:', { 
        tools: this.toolManager.listTools().map(t => t.name) 
      });
    } catch (error) {
      logger.fatal('Failed to start Federation MCP Server', { error });
      process.exit(1);
    }
  }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
  logger.info('Received SIGINT, shutting down gracefully');
  process.exit(0);
});

process.on('SIGTERM', () => {
  logger.info('Received SIGTERM, shutting down gracefully');
  process.exit(0);
});

// Start the server
const server = new FederationMCPServer();
server.start().catch((error) => {
  logger.fatal('Fatal error during startup', { error });
  process.exit(1);
});