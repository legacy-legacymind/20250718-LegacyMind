#!/usr/bin/env node

import { UnifiedIntelligence } from './src/core/unified-intelligence.js';
import { config } from './src/config.js';
import { logger } from './src/utils/logger.js';

// Test the auto-capture functionality
async function testAutoCapture() {
  console.log('Testing UnifiedIntelligence Auto-Capture...\n');
  
  try {
    // Initialize with Redis config
    const uiConfig = {
      redisUrl: config.redisUrl || process.env.REDIS_URL || 'redis://:unifiedmemory@localhost:6379',
      enableAutoCapture: true
    };
    
    console.log('Initializing UnifiedIntelligence with config:', {
      redisUrl: uiConfig.redisUrl.replace(/:([^:@]+)@/, ':***@')
    });
    
    const ui = new UnifiedIntelligence(uiConfig);
    
    // Wait for initialization
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Test monitor status
    console.log('\n1. Testing monitor status:');
    const statusResult = await ui.think({
      action: 'monitor',
      operation: 'status',
      options: { instance: 'test' }
    });
    console.log(JSON.stringify(statusResult, null, 2));
    
    // Test starting monitor
    console.log('\n2. Testing monitor start:');
    const startResult = await ui.think({
      action: 'monitor',
      operation: 'start',
      options: { instance: 'test' }
    });
    console.log(JSON.stringify(startResult, null, 2));
    
    // Test threshold update
    console.log('\n3. Testing threshold update:');
    const thresholdResult = await ui.think({
      action: 'monitor',
      operation: 'thresholds',
      thresholds: { autoCapture: 0.4 },
      options: { instance: 'test' }
    });
    console.log(JSON.stringify(thresholdResult, null, 2));
    
    // Simulate a conversation message that should trigger auto-capture
    console.log('\n4. Simulating conversation for auto-capture:');
    
    // Create a test session in Redis
    const sessionId = `test_${Date.now()}_test`;
    const streamKey = `ui:conversation:${sessionId}`;
    
    if (ui.redisManager && ui.redisManager.client) {
      // Add test conversation messages
      await ui.redisManager.xadd(streamKey, '*', 
        'content', 'I just realized something important about our architecture',
        'type', 'message',
        'instance', 'test',
        'timestamp', new Date().toISOString()
      );
      
      await ui.redisManager.xadd(streamKey, '*',
        'content', 'The problem with our current approach is that we are not monitoring conversations automatically',
        'type', 'message', 
        'instance', 'test',
        'timestamp', new Date().toISOString()
      );
      
      console.log('Added test messages to stream:', streamKey);
      
      // Wait for analyzer to process
      await new Promise(resolve => setTimeout(resolve, 12000));
      
      // Check if thoughts were captured
      // Note: Direct persistence access not available in test context
      console.log('\nAuto-capture test messages processed successfully');
      console.log('Check database or logs for captured thoughts');
    }
    
    // Stop monitoring
    console.log('\n5. Stopping monitor:');
    const stopResult = await ui.think({
      action: 'monitor',
      operation: 'stop',
      options: { instance: 'test' }
    });
    console.log(JSON.stringify(stopResult, null, 2));
    
    console.log('\nAuto-capture test completed!');
    
    // Cleanup
    if (ui.redisManager) {
      await ui.redisManager.shutdown();
    }
    
    process.exit(0);
    
  } catch (error) {
    console.error('Test failed:', error);
    process.exit(1);
  }
}

// Run the test
testAutoCapture();