#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema, } from '@modelcontextprotocol/sdk/types.js';
import { federationTools } from './tools/index.js';
import { CCMCPManager } from './managers/CCMCPManager.js';
import { GMCPManager } from './managers/GMCPManager.js';
import { config, validateConfig } from './utils/config.js';
import { logger } from './utils/logger.js';
class FederationMCPServer {
    server;
    ccmcpManager;
    gmcpManager;
    context;
    constructor() {
        this.server = new Server({
            name: 'federation-mcp',
            version: '1.0.0',
        }, {
            capabilities: {
                tools: {},
            },
        });
        this.ccmcpManager = new CCMCPManager(config.ccmcpTimeout);
        this.gmcpManager = new GMCPManager(config.gmcpTimeout);
        this.context = {
            config,
            ccmcpManager: this.ccmcpManager,
            gmcpManager: this.gmcpManager,
        };
    }
    async initialize() {
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
        }
        catch (error) {
            logger.fatal('Failed to initialize Federation MCP Server', { error });
            throw error;
        }
    }
    async testConnections() {
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
    setupHandlers() {
        // Handle list tools request
        this.server.setRequestHandler(ListToolsRequestSchema, async () => {
            logger.debug('Listing available tools');
            return {
                tools: federationTools.map(tool => ({
                    name: tool.name,
                    description: tool.description,
                    inputSchema: tool.schema,
                })),
            };
        });
        // Handle tool calls
        this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
            const { name, arguments: args } = request.params;
            const startTime = Date.now();
            logger.info('Executing tool', { name, args });
            try {
                const tool = federationTools.find(t => t.name === name);
                if (!tool) {
                    throw new Error(`Unknown tool: ${name}`);
                }
                const result = await tool.handler(args, this.context);
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
            }
            catch (error) {
                const executionTime = Date.now() - startTime;
                const errorMessage = error instanceof Error ? error.message : String(error);
                logger.error('Tool execution failed', {
                    name,
                    executionTime,
                    error: errorMessage
                });
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify({
                                success: false,
                                error: errorMessage,
                                tool: name,
                                executionTime,
                                timestamp: new Date().toISOString(),
                            }, null, 2),
                        },
                    ],
                    isError: true,
                };
            }
        });
    }
    async start() {
        try {
            await this.initialize();
            const transport = new StdioServerTransport();
            await this.server.connect(transport);
            logger.info('Federation MCP Server started successfully');
            logger.info('Available tools:', {
                tools: federationTools.map(t => t.name)
            });
        }
        catch (error) {
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
//# sourceMappingURL=index.js.map