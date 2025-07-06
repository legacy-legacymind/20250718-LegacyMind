import { spawn } from 'child_process';

console.log('Starting Comprehensive Tool Test...\n');

// Start the MCP server
const serverProcess = spawn('node', ['src/index.js'], {
  env: { ...process.env },
  stdio: ['pipe', 'pipe', 'pipe']
});

// Capture server errors
serverProcess.stderr.on('data', (data) => {
  const error = data.toString();
  if (!error.includes('[INFO]')) {
    console.error('\x1b[31mServer error:', error, '\x1b[0m');
  }
});

// Wait for server to be ready
await new Promise(resolve => setTimeout(resolve, 2000));

// Test sequence
async function runTests() {
  const results = {
    ui_think: { capture: false, status: false },
    ui_remember: { create: false, search: false },
    ui_inject: { help: false, expert: false }
  };
  
  try {
    // Test 1: ui_think capture
    console.log('1. Testing ui_think capture...');
    const thinkResponse = await sendRequest(serverProcess, {
      name: 'ui_think',
      arguments: {
        thought: 'Test thought for comprehensive test'
      }
    }, 1);
    results.ui_think.capture = thinkResponse?.result?.content?.[0]?.text?.includes('captured');
    
    // Test 2: ui_think status
    console.log('2. Testing ui_think status...');
    const statusResponse = await sendRequest(serverProcess, {
      name: 'ui_think',
      arguments: {
        action: 'status'
      }
    }, 2);
    results.ui_think.status = statusResponse?.result?.content?.[0]?.text?.includes('session');
    
    // Test 3: ui_remember create
    console.log('3. Testing ui_remember create...');
    const rememberResponse = await sendRequest(serverProcess, {
      name: 'ui_remember',
      arguments: {
        action: 'create',
        memory_type: 'context',
        content: 'Test context memory',
        options: {
          tags: ['test']
        }
      }
    }, 3);
    results.ui_remember.create = rememberResponse?.result?.content?.[0]?.text?.includes('created');
    
    // Test 4: ui_remember search
    console.log('4. Testing ui_remember search...');
    const searchResponse = await sendRequest(serverProcess, {
      name: 'ui_remember',
      arguments: {
        action: 'search',
        memory_type: 'context',
        query: 'test'
      }
    }, 4);
    results.ui_remember.search = searchResponse?.result?.content?.[0]?.text?.includes('memories');
    
    // Test 5: ui_inject help
    console.log('5. Testing ui_inject help...');
    const injectHelpResponse = await sendRequest(serverProcess, {
      name: 'ui_inject',
      arguments: {
        action: 'help'
      }
    }, 5);
    results.ui_inject.help = injectHelpResponse?.result?.content?.[0]?.text?.includes('UI_INJECT');
    
    // Test 6: ui_inject expert
    console.log('6. Testing ui_inject expert...');
    const expertResponse = await sendRequest(serverProcess, {
      name: 'ui_inject',
      arguments: {
        type: 'expert',
        source: 'docker'
      }
    }, 6);
    results.ui_inject.expert = expertResponse?.result?.content?.[0]?.text?.includes('Docker');
    
    // Print results
    console.log('\n=== TEST RESULTS ===');
    console.log('ui_think:');
    console.log('  - capture:', results.ui_think.capture ? '✓' : '✗');
    console.log('  - status:', results.ui_think.status ? '✓' : '✗');
    console.log('ui_remember:');
    console.log('  - create:', results.ui_remember.create ? '✓' : '✗');
    console.log('  - search:', results.ui_remember.search ? '✓' : '✗');
    console.log('ui_inject:');
    console.log('  - help:', results.ui_inject.help ? '✓' : '✗');
    console.log('  - expert:', results.ui_inject.expert ? '✓' : '✗');
    
    const totalTests = 6;
    const passedTests = Object.values(results).flatMap(r => Object.values(r)).filter(v => v).length;
    console.log(`\nTotal: ${passedTests}/${totalTests} tests passed`);
    
  } catch (error) {
    console.error('Test error:', error);
  } finally {
    serverProcess.kill();
    process.exit(0);
  }
}

// Helper function to send request and wait for response
async function sendRequest(process, toolParams, id) {
  const request = {
    jsonrpc: '2.0',
    method: 'tools/call',
    params: toolParams,
    id
  };
  
  process.stdin.write(JSON.stringify(request) + '\n');
  
  return new Promise((resolve) => {
    let buffer = '';
    const timeout = setTimeout(() => {
      process.stdout.removeListener('data', onData);
      resolve(null);
    }, 3000);
    
    const onData = (data) => {
      buffer += data.toString();
      const lines = buffer.split('\n');
      
      for (const line of lines) {
        if (line.trim()) {
          try {
            const response = JSON.parse(line);
            if (response.id === id) {
              clearTimeout(timeout);
              process.stdout.removeListener('data', onData);
              resolve(response);
              return;
            }
          } catch (e) {
            // Not valid JSON yet
          }
        }
      }
    };
    
    process.stdout.on('data', onData);
  });
}

// Run tests
runTests();