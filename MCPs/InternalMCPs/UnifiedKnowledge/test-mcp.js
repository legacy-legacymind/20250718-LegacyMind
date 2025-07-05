#!/usr/bin/env node

import { spawn } from 'child_process';

// Test MCP server connection
async function testMCPServer() {
  console.log('Testing UnifiedKnowledge MCP Server...\n');
  
  const mcp = spawn('docker', [
    'exec', '-i', 'legacymind_unified_knowledge',
    'node', 'src/index.js'
  ]);

  let responseBuffer = '';
  
  mcp.stdout.on('data', (data) => {
    responseBuffer += data.toString();
    
    // Try to parse complete JSON-RPC messages
    const lines = responseBuffer.split('\n');
    for (let i = 0; i < lines.length - 1; i++) {
      const line = lines[i].trim();
      if (line) {
        try {
          const response = JSON.parse(line);
          console.log('Response:', JSON.stringify(response, null, 2));
        } catch (e) {
          // Not a complete JSON message yet
        }
      }
    }
    // Keep the last incomplete line
    responseBuffer = lines[lines.length - 1];
  });

  mcp.stderr.on('data', (data) => {
    console.error('Server log:', data.toString());
  });

  // Send initialize request
  console.log('Sending initialize request...');
  const initRequest = {
    jsonrpc: "2.0",
    method: "initialize",
    params: {
      protocolVersion: "0.1.0",
      capabilities: {
        tools: {}
      }
    },
    id: 1
  };
  
  mcp.stdin.write(JSON.stringify(initRequest) + '\n');
  
  // Wait for response
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // Send tools/list request
  console.log('\nSending tools/list request...');
  const listRequest = {
    jsonrpc: "2.0",
    method: "tools/list",
    id: 2
  };
  
  mcp.stdin.write(JSON.stringify(listRequest) + '\n');
  
  // Wait for response
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // Close the connection
  mcp.stdin.end();
  
  setTimeout(() => {
    mcp.kill();
    process.exit(0);
  }, 1000);
}

testMCPServer().catch(console.error);