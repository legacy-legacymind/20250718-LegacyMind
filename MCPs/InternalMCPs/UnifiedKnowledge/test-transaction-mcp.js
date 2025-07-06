import { MCPClient } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { spawn } from 'child_process';

async function testMCPTransaction() {
  console.log('Starting MCP test...');
  
  const proc = spawn('node', ['src/index.js'], {
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env }
  });

  const transport = new StdioClientTransport({
    command: 'node',
    args: ['src/index.js'],
    env: process.env
  });

  const client = new MCPClient({
    name: 'test-client',
    version: '1.0.0'
  }, { 
    capabilities: {},
    enforceStrictCapabilities: false
  });

  try {
    await client.connect(transport);
    console.log('Connected to MCP server');

    // Test ticket creation which uses transactions
    const result = await client.callTool({
      name: 'ticket_create',
      arguments: {
        title: 'Test Transaction',
        description: 'Testing Redis transaction functionality',
        priority: 'high',
        tags: ['test', 'transaction']
      }
    });

    console.log('Ticket creation result:', result);
  } catch (error) {
    console.error('Error during MCP test:', error);
  } finally {
    await client.close();
    proc.kill();
  }
}

testMCPTransaction().catch(console.error);