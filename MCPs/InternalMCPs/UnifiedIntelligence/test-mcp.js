#!/usr/bin/env node
/**
 * Test MCP server without Redis dependency
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { 
  CallToolRequestSchema, 
  ListToolsRequestSchema 
} from '@modelcontextprotocol/sdk/types.js';

const server = new Server(
  { name: 'test-server', version: '1.0.0' },
  { capabilities: { tools: {} } }
);

// Simple test tool
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [{
      name: 'test_tool',
      description: 'A simple test tool',
      inputSchema: {
        type: 'object',
        properties: {
          message: {
            type: 'string',
            description: 'Test message'
          }
        },
        required: ['message']
      }
    }]
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  
  if (name === 'test_tool') {
    return {
      content: [{
        type: 'text',
        text: `Test response: ${args.message}`
      }]
    };
  }
  
  throw new Error(`Unknown tool: ${name}`);
});

const transport = new StdioServerTransport();
await server.connect(transport);
console.error('Test MCP server running');