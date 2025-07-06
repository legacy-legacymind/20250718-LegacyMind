#!/usr/bin/env node

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { spawn } from 'child_process';

async function testTicketCreation() {
  console.log('Starting UnifiedKnowledge ticket creation test...');
  
  // Start the MCP server
  const serverProcess = spawn('node', ['/Users/samuelatagana/Projects/LegacyMind/MCPs/InternalMCPs/UnifiedKnowledge/src/index.js'], {
    env: {
      ...process.env,
      DATABASE_URL: 'postgresql://postgres:postgres@localhost:5432/postgres',
      QDRANT_HOST: 'localhost',
      QDRANT_PORT: '6333',
      QDRANT_API_KEY: process.env.QDRANT_API_KEY,
      REDIS_URL: 'redis://:redis123@localhost:6379',
      OPENAI_API_KEY: process.env.OPENAI_API_KEY
    }
  });

  const transport = new StdioClientTransport({
    command: serverProcess.command,
    args: serverProcess.args,
    env: serverProcess.env
  });

  const client = new Client({
    name: 'test-client',
    version: '1.0.0'
  }, {
    capabilities: {}
  });

  try {
    await client.connect(transport);
    console.log('Connected to UnifiedKnowledge MCP server');

    // Create a test ticket
    console.log('\nCreating test ticket...');
    const result = await client.callTool({
      name: 'uk_ticket',
      arguments: {
        action: 'create',
        title: 'Test Ticket for Log Analysis',
        description: 'This is a test ticket to analyze embedding generation and Qdrant storage logs',
        priority: 'medium',
        type: 'task',
        tags: ['test', 'logging', 'embedding'],
        assignee: 'CC',
        metadata: {
          test_run: true,
          timestamp: new Date().toISOString()
        }
      }
    });

    console.log('\nTicket creation result:', JSON.stringify(result, null, 2));

    // Wait a bit to ensure logs are flushed
    await new Promise(resolve => setTimeout(resolve, 2000));

  } catch (error) {
    console.error('Error:', error);
  } finally {
    await client.close();
    serverProcess.kill();
  }
}

testTicketCreation().catch(console.error);