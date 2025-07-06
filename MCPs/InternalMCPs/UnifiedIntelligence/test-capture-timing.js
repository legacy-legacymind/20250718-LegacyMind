import { spawn } from 'child_process';
import { performance } from 'perf_hooks';

async function testCapturePerformance() {
  console.log('Testing ui_think capture performance...\n');
  
  // Start the MCP server
  const server = spawn('node', ['src/index.js'], {
    env: { ...process.env, LOG_LEVEL: 'debug' }
  });
  
  // Wait for server to be ready
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // Test capture action
  const captureRequest = {
    jsonrpc: "2.0",
    method: "call_tool",
    params: {
      name: "ui_think",
      arguments: {
        action: "capture",
        thought: "Performance test thought",
        identity: { name: "PERF_TEST" }
      }
    },
    id: 1
  };
  
  console.log('Sending capture request...');
  const startTime = performance.now();
  
  // Send request to server
  server.stdin.write(JSON.stringify(captureRequest) + '\n');
  
  // Listen for response
  return new Promise((resolve, reject) => {
    let responseData = '';
    
    server.stdout.on('data', (data) => {
      responseData += data.toString();
      
      // Check if we have a complete JSON response
      try {
        const lines = responseData.split('\n').filter(line => line.trim());
        for (const line of lines) {
          if (line.includes('"jsonrpc"')) {
            const response = JSON.parse(line);
            const endTime = performance.now();
            const duration = endTime - startTime;
            
            console.log(`\nCapture completed in ${duration.toFixed(2)}ms`);
            console.log('Response:', JSON.stringify(response, null, 2));
            
            server.kill();
            resolve(duration);
            return;
          }
        }
      } catch (e) {
        // Not a complete JSON yet, continue collecting
      }
    });
    
    server.stderr.on('data', (data) => {
      console.error('Server error:', data.toString());
    });
    
    server.on('close', (code) => {
      if (code !== 0 && code !== null) {
        reject(new Error(`Server exited with code ${code}`));
      }
    });
    
    // Timeout after 20 seconds
    setTimeout(() => {
      server.kill();
      reject(new Error('Test timed out after 20 seconds'));
    }, 20000);
  });
}

// Run the test
testCapturePerformance()
  .then(duration => {
    console.log(`\nTest completed. Total duration: ${duration.toFixed(2)}ms`);
    if (duration > 5000) {
      console.log('\n⚠️  WARNING: Capture is taking longer than expected!');
      console.log('Expected: < 1000ms');
      console.log(`Actual: ${duration.toFixed(2)}ms`);
    }
    process.exit(0);
  })
  .catch(error => {
    console.error('\nTest failed:', error);
    process.exit(1);
  });