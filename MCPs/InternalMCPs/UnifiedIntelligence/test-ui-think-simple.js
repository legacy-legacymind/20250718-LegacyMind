import { spawn } from 'child_process';

console.log('Starting Simple UI Think Test...\n');

// Start the MCP server with auto-capture disabled
const serverProcess = spawn('node', ['src/index.js'], {
  env: { 
    ...process.env,
    ENABLE_AUTO_CAPTURE: 'false'
  },
  stdio: ['pipe', 'pipe', 'pipe']
});

// Capture server output
let serverOutput = '';
serverProcess.stdout.on('data', (data) => {
  serverOutput += data.toString();
});

// Capture server errors
serverProcess.stderr.on('data', (data) => {
  console.error('\x1b[31mServer error:', data.toString(), '\x1b[0m');
});

// Wait for server to be ready
await new Promise(resolve => setTimeout(resolve, 2000));

// Simple test
async function runTest() {
  try {
    console.log('Testing direct thought capture...');
    
    // Direct capture without check_in
    const captureRequest = {
      jsonrpc: '2.0',
      method: 'tools/call',
      params: {
        name: 'ui_think',
        arguments: {
          thought: 'Direct test thought without check_in'
        }
      },
      id: 1
    };
    
    serverProcess.stdin.write(JSON.stringify(captureRequest) + '\n');
    
    // Wait and check output
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    console.log('Server output:');
    console.log(serverOutput);
    
  } catch (error) {
    console.error('Test error:', error);
  } finally {
    serverProcess.kill();
    process.exit(0);
  }
}

runTest();