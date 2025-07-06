#!/usr/bin/env node
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { spawn } from 'child_process';

async function testCapturePerformance() {
  console.log('=== UI_THINK CAPTURE PERFORMANCE TEST ===\n');

  const serverProcess = spawn('node', ['src/index.js'], {
    env: { 
      ...process.env,
      LOG_LEVEL: 'info',
      REDIS_URL: process.env.REDIS_URL || 'redis://localhost:6379'
    }
  });

  const client = new Client({
    name: 'test-client',
    version: '1.0.0',
  });

  const transport = new StdioClientTransport({
    inputStream: serverProcess.stdout,
    outputStream: serverProcess.stdin,
    errorStream: serverProcess.stderr,
  });

  try {
    console.log('1. Connecting to MCP server...');
    const connectStart = Date.now();
    await client.connect(transport);
    console.log(`   Connected in ${Date.now() - connectStart}ms\n`);

    // First do a check-in
    console.log('2. Performing check-in...');
    const checkInStart = Date.now();
    const checkInResult = await client.call('ui_think', {
      action: 'check_in',
      identity: {
        name: 'PERF_TEST',
        type: 'test',
        role: 'performance'
      }
    });
    console.log(`   Check-in completed in ${Date.now() - checkInStart}ms`);
    console.log(`   Result: ${JSON.stringify(checkInResult).substring(0, 100)}...\n`);

    // Test single capture
    console.log('3. Testing single capture...');
    const captureStart = Date.now();
    const captureResult = await client.call('ui_think', {
      action: 'capture',
      thought: 'Performance test thought'
    });
    const captureDuration = Date.now() - captureStart;
    console.log(`   Capture completed in ${captureDuration}ms`);
    console.log(`   Result: ${JSON.stringify(captureResult).substring(0, 100)}...\n`);

    if (captureDuration > 5000) {
      console.log('⚠️  WARNING: Capture is taking much longer than expected!');
      console.log(`   Expected: < 1000ms`);
      console.log(`   Actual: ${captureDuration}ms\n`);
    }

    // Test multiple captures
    console.log('4. Testing multiple captures...');
    const captureCount = 10;
    const durations = [];
    
    for (let i = 0; i < captureCount; i++) {
      const start = Date.now();
      await client.call('ui_think', {
        action: 'capture',
        thought: `Test thought ${i + 1} at ${new Date().toISOString()}`
      });
      const duration = Date.now() - start;
      durations.push(duration);
      console.log(`   Capture ${i + 1}: ${duration}ms`);
    }

    // Calculate statistics
    const avgDuration = durations.reduce((a, b) => a + b, 0) / durations.length;
    const minDuration = Math.min(...durations);
    const maxDuration = Math.max(...durations);

    console.log('\n5. Performance Summary:');
    console.log(`   Total captures: ${captureCount}`);
    console.log(`   Average: ${avgDuration.toFixed(2)}ms`);
    console.log(`   Min: ${minDuration}ms`);
    console.log(`   Max: ${maxDuration}ms`);

    // Test with rate limiting
    console.log('\n6. Testing rate limiting (100 rapid captures)...');
    const rapidStart = Date.now();
    let rateLimitHit = false;
    
    for (let i = 0; i < 100; i++) {
      try {
        await client.call('ui_think', {
          action: 'capture',
          thought: `Rapid test ${i}`
        });
      } catch (error) {
        if (error.message.includes('Rate limit')) {
          rateLimitHit = true;
          console.log(`   Rate limit hit at capture ${i + 1}`);
          break;
        }
      }
    }
    
    if (!rateLimitHit) {
      console.log('   ✅ Completed 100 captures without rate limit');
    }
    const rapidDuration = Date.now() - rapidStart;
    console.log(`   Total time for rapid captures: ${rapidDuration}ms`);

    // Get final status
    console.log('\n7. Final status check...');
    const statusResult = await client.call('ui_think', {
      action: 'status'
    });
    console.log(`   Status: ${JSON.stringify(statusResult, null, 2)}`);

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    console.error(error.stack);
  } finally {
    await client.close();
    serverProcess.kill();
  }
}

// Run the test
testCapturePerformance()
  .then(() => {
    console.log('\n✅ Test completed');
    process.exit(0);
  })
  .catch(error => {
    console.error('\n❌ Test error:', error);
    process.exit(1);
  });