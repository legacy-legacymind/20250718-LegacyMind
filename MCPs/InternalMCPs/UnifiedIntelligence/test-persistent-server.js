#!/usr/bin/env node

import { spawn } from 'child_process';
import net from 'net';
import { performance } from 'perf_hooks';

const SOCKET_PATH = '/tmp/unified-intelligence.sock';

async function waitForSocket(timeout = 10000) {
  const start = Date.now();
  
  while (Date.now() - start < timeout) {
    try {
      await new Promise((resolve, reject) => {
        const client = net.createConnection(SOCKET_PATH, () => {
          client.end();
          resolve();
        });
        
        client.on('error', reject);
      });
      
      return true;
    } catch (error) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }
  
  return false;
}

async function sendRequest(request) {
  return new Promise((resolve, reject) => {
    const client = net.createConnection(SOCKET_PATH);
    let response = '';
    
    client.on('connect', () => {
      client.write(JSON.stringify(request) + '\n');
    });
    
    client.on('data', (data) => {
      response += data.toString();
      
      // Check if we have a complete response (ends with newline)
      if (response.endsWith('\n')) {
        client.end();
        try {
          const parsedResponse = JSON.parse(response.trim());
          resolve(parsedResponse);
        } catch (error) {
          reject(new Error(`Failed to parse response: ${response}`));
        }
      }
    });
    
    client.on('error', reject);
    
    client.on('timeout', () => {
      reject(new Error('Request timeout'));
    });
    
    client.setTimeout(5000);
  });
}

async function testPerformance() {
  console.log('🚀 Testing UnifiedIntelligence Persistent Server Performance\n');
  
  // Start the server
  console.log('Starting server...');
  const serverProcess = spawn('node', ['src/index.js', 'serve'], {
    stdio: 'inherit',
    detached: false
  });
  
  // Wait for server to be ready
  console.log('Waiting for server to be ready...');
  const serverReady = await waitForSocket();
  
  if (!serverReady) {
    console.error('❌ Server failed to start');
    serverProcess.kill();
    process.exit(1);
  }
  
  console.log('✅ Server is ready\n');
  
  // Test 1: List tools
  console.log('Test 1: List Tools');
  const listStart = performance.now();
  
  try {
    const listResponse = await sendRequest({
      jsonrpc: '2.0',
      id: 1,
      method: 'tools/list',
      params: {}
    });
    
    const listEnd = performance.now();
    console.log(`✅ Response time: ${(listEnd - listStart).toFixed(2)}ms`);
    console.log(`   Tools found: ${listResponse.result?.tools?.length || 0}\n`);
  } catch (error) {
    console.error(`❌ Error: ${error.message}\n`);
  }
  
  // Test 2: Multiple rapid requests
  console.log('Test 2: Multiple Rapid Requests (10 requests)');
  const requests = [];
  const multiStart = performance.now();
  
  for (let i = 0; i < 10; i++) {
    requests.push(sendRequest({
      jsonrpc: '2.0',
      id: i + 10,
      method: 'tools/list',
      params: {}
    }));
  }
  
  try {
    await Promise.all(requests);
    const multiEnd = performance.now();
    const avgTime = (multiEnd - multiStart) / 10;
    console.log(`✅ Total time: ${(multiEnd - multiStart).toFixed(2)}ms`);
    console.log(`   Average per request: ${avgTime.toFixed(2)}ms\n`);
  } catch (error) {
    console.error(`❌ Error: ${error.message}\n`);
  }
  
  // Test 3: Tool call (ui_think help)
  console.log('Test 3: Tool Call (ui_think help)');
  const callStart = performance.now();
  
  try {
    const callResponse = await sendRequest({
      jsonrpc: '2.0',
      id: 100,
      method: 'tools/call',
      params: {
        name: 'ui_think',
        arguments: {
          action: 'help'
        }
      }
    });
    
    const callEnd = performance.now();
    console.log(`✅ Response time: ${(callEnd - callStart).toFixed(2)}ms`);
    console.log(`   Response received: ${callResponse.result ? 'Yes' : 'No'}\n`);
  } catch (error) {
    console.error(`❌ Error: ${error.message}\n`);
  }
  
  // Compare with direct startup time
  console.log('Test 4: Direct Startup Time Comparison');
  const directStart = performance.now();
  
  const directProcess = spawn('node', ['src/index.js'], {
    stdio: 'pipe'
  });
  
  // Wait for the process to be ready (when it outputs to stderr/stdout)
  await new Promise((resolve) => {
    directProcess.stderr.once('data', resolve);
    directProcess.stdout.once('data', resolve);
    setTimeout(resolve, 5000); // Timeout after 5 seconds
  });
  
  const directEnd = performance.now();
  directProcess.kill();
  
  console.log(`   Direct startup time: ${(directEnd - directStart).toFixed(2)}ms`);
  console.log(`   Server request time: ${avgTime.toFixed(2)}ms`);
  console.log(`   Performance improvement: ${((directEnd - directStart) / avgTime).toFixed(1)}x faster\n`);
  
  // Cleanup
  console.log('Shutting down server...');
  serverProcess.kill('SIGTERM');
  
  // Wait for server to shut down
  await new Promise(resolve => setTimeout(resolve, 1000));
  
  console.log('✅ Test complete!');
}

// Run the test
testPerformance().catch((error) => {
  console.error('Test failed:', error);
  process.exit(1);
});