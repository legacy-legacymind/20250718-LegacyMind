#!/usr/bin/env node

import { spawn } from 'child_process';

async function testTicketCreationWithLogs() {
  console.log('Testing UnifiedKnowledge ticket creation with log monitoring...\n');
  
  // Start log monitoring in separate process
  const logMonitor = spawn('docker', ['logs', '-f', 'legacymind_unified_knowledge']);
  
  let logs = [];
  logMonitor.stderr.on('data', (data) => {
    const logLine = data.toString();
    logs.push(logLine);
    if (logLine.includes('[Qdrant]') || logLine.includes('[Embedding]')) {
      console.log('LOG:', logLine.trim());
    }
  });

  // Give log monitor time to start
  await new Promise(resolve => setTimeout(resolve, 1000));

  // Start MCP server interaction
  const mcp = spawn('docker', [
    'exec', '-i', 'legacymind_unified_knowledge',
    'node', 'src/index.js'
  ]);

  let responseBuffer = '';
  
  mcp.stdout.on('data', (data) => {
    responseBuffer += data.toString();
    
    const lines = responseBuffer.split('\n');
    for (let i = 0; i < lines.length - 1; i++) {
      const line = lines[i].trim();
      if (line) {
        try {
          const response = JSON.parse(line);
          if (response.result) {
            console.log('\nMCP Response:', JSON.stringify(response.result, null, 2));
          }
        } catch (e) {
          // Not complete JSON
        }
      }
    }
    responseBuffer = lines[lines.length - 1];
  });

  mcp.stderr.on('data', (data) => {
    // Server initialization logs
  });

  // Send initialize request
  console.log('Initializing MCP connection...');
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
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Create a test ticket
  console.log('\nCreating test ticket...');
  const createTicketRequest = {
    jsonrpc: "2.0",
    method: "tools/call",
    params: {
      name: "uk_ticket",
      arguments: {
        action: "create",
        title: "Test Embedding and Qdrant Storage " + new Date().toISOString(),
        description: "This is a test ticket to verify that embeddings are generated and stored in Qdrant",
        priority: "high",
        type: "task",
        tags: ["test", "embedding", "qdrant", "verification"],
        assignee: "CC",
        metadata: {
          test_run: true,
          timestamp: new Date().toISOString()
        }
      }
    },
    id: 2
  };
  
  mcp.stdin.write(JSON.stringify(createTicketRequest) + '\n');
  
  // Wait for processing
  await new Promise(resolve => setTimeout(resolve, 5000));
  
  // Clean up
  mcp.stdin.end();
  logMonitor.kill();
  
  // Show summary
  console.log('\n=== Log Summary ===');
  const relevantLogs = logs.filter(log => 
    log.includes('[Qdrant]') || 
    log.includes('[Embedding]') || 
    log.includes('ticket')
  );
  
  if (relevantLogs.length > 0) {
    console.log('Relevant logs found:');
    relevantLogs.forEach(log => console.log(log.trim()));
  } else {
    console.log('No relevant logs found for embedding/Qdrant operations');
  }
  
  setTimeout(() => {
    mcp.kill();
    process.exit(0);
  }, 1000);
}

testTicketCreationWithLogs().catch(console.error);