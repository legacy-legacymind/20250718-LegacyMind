#!/usr/bin/env node

/**
 * Test script to verify UnifiedKnowledge response handling
 */

import { spawn } from 'child_process';
import readline from 'readline';

const SERVER_PATH = './src/index.js';

class TestClient {
  constructor() {
    this.process = null;
    this.reader = null;
    this.writer = null;
    this.requestId = 0;
    this.pendingRequests = new Map();
  }

  async start() {
    console.log('Starting UnifiedKnowledge server...');
    
    this.process = spawn('node', [SERVER_PATH], {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, NODE_ENV: 'test' }
    });

    this.reader = readline.createInterface({
      input: this.process.stdout,
      crlfDelay: Infinity
    });

    this.writer = this.process.stdin;

    // Handle server output
    this.reader.on('line', (line) => {
      try {
        const response = JSON.parse(line);
        console.log('Server response:', JSON.stringify(response, null, 2));
        
        const requestId = response.id;
        if (this.pendingRequests.has(requestId)) {
          const { resolve } = this.pendingRequests.get(requestId);
          this.pendingRequests.delete(requestId);
          resolve(response);
        }
      } catch (e) {
        // Not JSON, might be debug output
        console.log('Server output:', line);
      }
    });

    // Handle server errors
    this.process.stderr.on('data', (data) => {
      console.error('Server error:', data.toString());
    });

    // Wait for server to be ready
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Initialize connection
    await this.sendRequest('initialize', {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: {
        name: 'test-client',
        version: '1.0.0'
      }
    });
  }

  async sendRequest(method, params = {}) {
    const id = ++this.requestId;
    const request = {
      jsonrpc: '2.0',
      id,
      method,
      params
    };

    console.log('\nSending request:', JSON.stringify(request, null, 2));

    return new Promise((resolve, reject) => {
      this.pendingRequests.set(id, { resolve, reject });
      this.writer.write(JSON.stringify(request) + '\n');
      
      // Timeout after 10 seconds
      setTimeout(() => {
        if (this.pendingRequests.has(id)) {
          this.pendingRequests.delete(id);
          reject(new Error('Request timeout'));
        }
      }, 10000);
    });
  }

  async stop() {
    if (this.process) {
      this.process.kill();
      await new Promise(resolve => this.process.on('close', resolve));
    }
  }
}

async function runTests() {
  const client = new TestClient();
  
  try {
    await client.start();
    
    console.log('\n=== Test 1: Create ticket ===');
    const createResponse = await client.sendRequest('tools/call', {
      name: 'uk_ticket',
      arguments: {
        action: 'create',
        title: 'Test ticket for response handling',
        description: 'Testing the new response handler',
        priority: 'high',
        type: 'bug',
        tags: ['test', 'response-handler']
      }
    });
    
    // Parse the response content
    if (createResponse.result?.content?.[0]?.text) {
      const result = JSON.parse(createResponse.result.content[0].text);
      console.log('\nCreate result:', JSON.stringify(result, null, 2));
      
      if (result.success && result.data?.ticket_id) {
        const ticketId = result.data.ticket_id;
        
        console.log('\n=== Test 2: Update ticket ===');
        const updateResponse = await client.sendRequest('tools/call', {
          name: 'uk_ticket',
          arguments: {
            action: 'update',
            ticket_id: ticketId,
            updates: {
              priority: 'urgent',
              tags: ['test', 'response-handler', 'updated']
            }
          }
        });
        
        if (updateResponse.result?.content?.[0]?.text) {
          const updateResult = JSON.parse(updateResponse.result.content[0].text);
          console.log('\nUpdate result:', JSON.stringify(updateResult, null, 2));
        }
        
        console.log('\n=== Test 3: Get ticket ===');
        const getResponse = await client.sendRequest('tools/call', {
          name: 'uk_ticket',
          arguments: {
            action: 'get',
            ticket_id: ticketId,
            include_history: true
          }
        });
        
        if (getResponse.result?.content?.[0]?.text) {
          const getResult = JSON.parse(getResponse.result.content[0].text);
          console.log('\nGet result:', JSON.stringify(getResult, null, 2));
        }
        
        console.log('\n=== Test 4: Search tickets ===');
        const searchResponse = await client.sendRequest('tools/call', {
          name: 'uk_ticket',
          arguments: {
            action: 'search',
            query: 'response handler',
            limit: 10
          }
        });
        
        if (searchResponse.result?.content?.[0]?.text) {
          const searchResult = JSON.parse(searchResponse.result.content[0].text);
          console.log('\nSearch result:', JSON.stringify(searchResult, null, 2));
        }
        
        console.log('\n=== Test 5: Test validation error ===');
        const errorResponse = await client.sendRequest('tools/call', {
          name: 'uk_ticket',
          arguments: {
            action: 'create',
            // Missing required fields
            description: 'This should fail'
          }
        });
        
        if (errorResponse.result?.content?.[0]?.text) {
          const errorResult = JSON.parse(errorResponse.result.content[0].text);
          console.log('\nValidation error result:', JSON.stringify(errorResult, null, 2));
        }
      }
    }
    
    console.log('\n=== All tests completed ===');
    
  } catch (error) {
    console.error('\nTest error:', error);
  } finally {
    await client.stop();
  }
}

// Run the tests
runTests().catch(console.error);