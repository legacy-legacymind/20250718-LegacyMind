import { spawn } from 'child_process';
import { readFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('Starting UI Think Test...\n');

// Start the MCP server
const serverProcess = spawn('node', ['src/index.js'], {
  env: { ...process.env },
  stdio: ['pipe', 'pipe', 'pipe']
});

// Capture server errors
let serverErrors = [];
serverProcess.stderr.on('data', (data) => {
  const error = data.toString();
  serverErrors.push(error);
  console.error('\x1b[31mServer error:', error, '\x1b[0m');
});

// Wait for server to be ready
await new Promise(resolve => setTimeout(resolve, 2000));

// Test sequence
async function runTests() {
  try {
    // Test 1: Check in with identity
    console.log('1. Testing check_in action...');
    const checkInRequest = {
      jsonrpc: '2.0',
      method: 'tools/call',
      params: {
        name: 'ui_think',
        arguments: {
          action: 'check_in',
          identity: {
            name: 'TEST_INSTANCE',
            id: 'test-001',
            type: 'test',
            role: 'Test Instance'
          }
        }
      },
      id: 1
    };
    
    serverProcess.stdin.write(JSON.stringify(checkInRequest) + '\n');
    
    // Wait for response
    const checkInResponse = await waitForResponse(serverProcess, 1);
    console.log('Check-in response:', checkInResponse ? 'SUCCESS' : 'FAILED');
    
    // Test 2: Capture a thought
    console.log('\n2. Testing capture action...');
    const captureRequest = {
      jsonrpc: '2.0',
      method: 'tools/call',
      params: {
        name: 'ui_think',
        arguments: {
          action: 'capture',
          thought: 'This is a test thought from the ui_think test script',
          options: {
            tags: ['test', 'validation'],
            confidence: 0.95
          }
        }
      },
      id: 2
    };
    
    serverProcess.stdin.write(JSON.stringify(captureRequest) + '\n');
    
    const captureResponse = await waitForResponse(serverProcess, 2);
    console.log('Capture response:', captureResponse ? 'SUCCESS' : 'FAILED');
    
    // Test 3: Get status
    console.log('\n3. Testing status action...');
    const statusRequest = {
      jsonrpc: '2.0',
      method: 'tools/call',
      params: {
        name: 'ui_think',
        arguments: {
          action: 'status'
        }
      },
      id: 3
    };
    
    serverProcess.stdin.write(JSON.stringify(statusRequest) + '\n');
    
    const statusResponse = await waitForResponse(serverProcess, 3);
    console.log('Status response:', statusResponse ? 'SUCCESS' : 'FAILED');
    
    console.log('\nTest completed!');
    
  } catch (error) {
    console.error('Test error:', error);
  } finally {
    serverProcess.kill();
    process.exit(0);
  }
}

// Helper function to wait for response
function waitForResponse(process, expectedId) {
  return new Promise((resolve) => {
    let buffer = '';
    const timeout = setTimeout(() => {
      process.stdout.removeListener('data', onData);
      resolve(null);
    }, 5000);
    
    const onData = (data) => {
      buffer += data.toString();
      const lines = buffer.split('\n');
      
      for (const line of lines) {
        if (line.trim()) {
          try {
            const response = JSON.parse(line);
            if (response.id === expectedId) {
              clearTimeout(timeout);
              process.stdout.removeListener('data', onData);
              resolve(response);
              return;
            }
          } catch (e) {
            // Not valid JSON yet, continue buffering
          }
        }
      }
    };
    
    process.stdout.on('data', onData);
  });
}

// Run tests
runTests();