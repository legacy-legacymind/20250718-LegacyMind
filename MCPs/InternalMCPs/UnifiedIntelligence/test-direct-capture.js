#!/usr/bin/env node
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

async function testDirectCapture() {
  console.log('Testing ui_think capture performance directly...\n');
  
  // First, do a check-in
  const checkInCmd = `npx mcp-cli --server-script "node src/index.js" call ui_think '{"action": "check_in", "identity": {"name": "PERF_TEST", "type": "test", "role": "performance"}}'`;
  
  console.log('1. Performing check-in...');
  const checkInStart = Date.now();
  
  try {
    const { stdout: checkInOutput } = await execAsync(checkInCmd);
    const checkInDuration = Date.now() - checkInStart;
    console.log(`   Check-in completed in ${checkInDuration}ms`);
    console.log(`   Response: ${checkInOutput.substring(0, 100)}...`);
  } catch (error) {
    console.error('Check-in failed:', error.message);
  }
  
  // Now test the capture
  const captureCmd = `npx mcp-cli --server-script "node src/index.js" call ui_think '{"action": "capture", "thought": "Performance test thought at ${new Date().toISOString()}"}'`;
  
  console.log('\n2. Testing capture performance...');
  const captureStart = Date.now();
  
  try {
    const { stdout: captureOutput } = await execAsync(captureCmd);
    const captureDuration = Date.now() - captureStart;
    
    console.log(`   Capture completed in ${captureDuration}ms`);
    console.log(`   Response: ${captureOutput.substring(0, 100)}...`);
    
    if (captureDuration > 5000) {
      console.log('\n⚠️  WARNING: Capture is taking much longer than expected!');
      console.log(`   Expected: < 1000ms`);
      console.log(`   Actual: ${captureDuration}ms`);
      console.log('\n   Possible causes:');
      console.log('   - Redis connection issues');
      console.log('   - Retry mechanism being triggered');
      console.log('   - MCP server initialization overhead');
    }
    
    // Try multiple captures to see if it's consistent
    console.log('\n3. Testing multiple captures...');
    const captureCount = 5;
    const durations = [];
    
    for (let i = 0; i < captureCount; i++) {
      const start = Date.now();
      try {
        await execAsync(captureCmd.replace('Performance test thought', `Test ${i+1}`));
        const duration = Date.now() - start;
        durations.push(duration);
        console.log(`   Capture ${i+1}: ${duration}ms`);
      } catch (error) {
        console.error(`   Capture ${i+1} failed:`, error.message);
      }
    }
    
    if (durations.length > 0) {
      const avgDuration = durations.reduce((a, b) => a + b, 0) / durations.length;
      const minDuration = Math.min(...durations);
      const maxDuration = Math.max(...durations);
      
      console.log('\n4. Performance Summary:');
      console.log(`   Average: ${avgDuration.toFixed(2)}ms`);
      console.log(`   Min: ${minDuration}ms`);
      console.log(`   Max: ${maxDuration}ms`);
    }
    
  } catch (error) {
    console.error('Capture test failed:', error.message);
  }
}

// Run the test
testDirectCapture().catch(console.error);