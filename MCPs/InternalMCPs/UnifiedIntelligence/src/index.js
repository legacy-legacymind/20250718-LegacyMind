#!/usr/bin/env node
/**
 * UnifiedIntelligence v3 - MCP Server
 * The conscious, real-time mind of an AI instance
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { 
  CallToolRequestSchema, 
  ListToolsRequestSchema 
} from '@modelcontextprotocol/sdk/types.js';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

// Import storage components
import { RedisManager, SessionManager, ThoughtRecorder } from './storage/index.js';
import { MemoryFormationPipeline } from './pipeline/index.js';
import { FrameworkEngine } from './frameworks/index.js';
import { FederationHandler } from './handlers/FederationHandler.js';

// Import tools
import {
  ui_think,
  ui_context,
  ui_bot
} from './tools/index.js';

// Server metadata
const SERVER_INFO = {
  name: 'unified-intelligence-v3',
  version: '3.0.0',
  description: 'The conscious, real-time mind of an AI instance'
};

// Initialize server
const server = new Server(SERVER_INFO, {
  capabilities: {
    tools: {},
    resources: {}
  }
});

// Global instances
let redisManager = null;
let sessionManager = null;
let thoughtRecorder = null;
let pipeline = null;
let frameworkEngine = null;
let federationHandler = null;
let instanceId = null;

// Initialize components
async function initialize() {
  try {
    console.log('Initializing UnifiedIntelligence v3...');
    
    // Connect to Redis
    redisManager = new RedisManager();
    await redisManager.connect();
    console.log('Connected to Redis');
    
    const redisClient = redisManager.getClient();
    
    // Initialize storage components
    sessionManager = new SessionManager(redisClient);
    thoughtRecorder = new ThoughtRecorder(redisClient);
    
    // Initialize framework engine
    frameworkEngine = new FrameworkEngine();
    
    // Initialize federation handler
    federationHandler = new FederationHandler(redisClient);
    
    // Initialize pipeline
    pipeline = new MemoryFormationPipeline(
      redisManager,
      sessionManager,
      thoughtRecorder
    );
    
    // Get instance ID (from environment or generate)
    instanceId = process.env.INSTANCE_ID || 
                 (await redisClient.get('ui:last_instance')) || 
                 'default';
    
    console.log(`Instance ID: ${instanceId}`);
    console.log('UnifiedIntelligence v3 initialized successfully');
    
  } catch (error) {
    console.error('Failed to initialize:', error);
    process.exit(1);
  }
}

// Tool handlers with dependency injection
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: ui_think.name,
        description: ui_think.description,
        inputSchema: ui_think.inputSchema
      },
      {
        name: ui_context.name,
        description: ui_context.description,
        inputSchema: ui_context.inputSchema
      },
      {
        name: ui_bot.name,
        description: ui_bot.description,
        inputSchema: ui_bot.inputSchema
      }
    ]
  };
});

// Register tool handlers
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  
  try {
    switch (name) {
      case 'ui_think': {
        const handler = ui_think.handler(pipeline, sessionManager, frameworkEngine, instanceId);
        const result = await handler(args);
        return { 
          content: [{
            type: 'text',
            text: JSON.stringify(result, null, 2)
          }]
        };
      }
      
      case 'ui_context': {
        const handler = ui_context.handler(redisManager, instanceId);
        const result = await handler(args);
        return { 
          content: [{
            type: 'text',
            text: JSON.stringify(result, null, 2)
          }]
        };
      }
      
      case 'ui_bot': {
        const handler = ui_bot.handler(pipeline, sessionManager, frameworkEngine, redisManager, instanceId);
        const result = await handler(args);
        return { 
          content: [{
            type: 'text',
            text: JSON.stringify(result, null, 2)
          }]
        };
      }
      
      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    console.error(`Error in tool ${name}:`, error);
    throw error;
  }
});

// Graceful shutdown
async function shutdown() {
  console.log('Shutting down UnifiedIntelligence v3...');
  
  if (redisManager) {
    await redisManager.disconnect();
  }
  
  process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

// Main execution
async function main() {
  // Initialize components
  await initialize();
  
  // Start server
  const transport = new StdioServerTransport();
  await server.connect(transport);
  
  console.log('UnifiedIntelligence v3 MCP server running');
}

// Run the server
main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});