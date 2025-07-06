import { spawn } from 'child_process';

console.log('Testing ui_inject help action...\n');

// Start the MCP server
const serverProcess = spawn('node', ['src/index.js'], {
  env: { ...process.env },
  stdio: ['pipe', 'pipe', 'pipe']
});

// Wait for server to be ready
await new Promise(resolve => setTimeout(resolve, 2000));

// Test help action
const helpRequest = {
  jsonrpc: '2.0',
  method: 'tools/call',
  params: {
    name: 'ui_inject',
    arguments: {
      action: 'help'
    }
  },
  id: 1
};

serverProcess.stdin.write(JSON.stringify(helpRequest) + '\n');

// Wait for response
setTimeout(() => {
  console.log('Test completed');
  serverProcess.kill();
  process.exit(0);
}, 2000);

// Capture output
serverProcess.stdout.on('data', (data) => {
  const response = data.toString();
  console.log('Response:', response);
});

serverProcess.stderr.on('data', (data) => {
  const error = data.toString();
  if (error.includes('ERROR')) {
    console.error('Error:', error);
  }
});