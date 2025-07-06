#!/usr/bin/env node

// Simple test to create a ticket via MCP and observe logs
const net = require('net');

const request = {
  jsonrpc: "2.0",
  method: "tools/call",
  params: {
    name: "uk_ticket",
    arguments: {
      action: "create",
      title: "Test Embedding and Qdrant Storage",
      description: "Testing if embeddings are generated and stored in Qdrant when creating tickets",
      priority: "high",
      type: "task",
      tags: ["test", "embedding", "qdrant", "logging"],
      assignee: "CC",
      metadata: {
        test_timestamp: new Date().toISOString(),
        test_purpose: "verify logging"
      }
    }
  },
  id: 1
};

// Connect to the MCP server via docker exec
const client = net.createConnection({ port: 3000, host: 'localhost' }, () => {
  console.log('Connected to MCP server');
  client.write(JSON.stringify(request) + '\n');
});

client.on('data', (data) => {
  console.log('Response:', data.toString());
  client.end();
});

client.on('error', (err) => {
  console.error('Connection error:', err);
});

client.on('end', () => {
  console.log('Disconnected from server');
  process.exit(0);
});