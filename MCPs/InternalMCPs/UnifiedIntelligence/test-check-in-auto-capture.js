#!/usr/bin/env node

/**
 * Test script to verify check_in automatically starts auto-capture
 */

import { UnifiedIntelligence } from './src/core/unified-intelligence.js';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

async function testCheckInAutoCapture() {
  console.log('=== Testing Check-In Auto-Capture ===\n');
  
  try {
    // Initialize UnifiedIntelligence with Redis config
    const config = {
      redisUrl: process.env.REDIS_URL || 'redis://localhost:6379',
      enableAutoCapture: true
    };
    
    console.log('1. Initializing UnifiedIntelligence with config:', config);
    const ui = new UnifiedIntelligence(config);
    
    // Wait a moment for Redis connection
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Perform check_in
    console.log('\n2. Performing check_in for CCI instance...');
    const checkInResult = await ui.think({
      action: 'check_in',
      identity: {
        name: 'CCI',
        type: 'Intelligence Specialist',
        role: 'UnifiedIntelligence Lead'
      },
      samContext: {
        test: true,
        timestamp: new Date().toISOString()
      },
      activeTickets: []
    });
    
    console.log('\n3. Check-in result:');
    console.log(JSON.stringify(checkInResult, null, 2));
    
    // Check auto-capture status
    console.log('\n4. Checking monitor status...');
    const monitorStatus = await ui.think({
      action: 'monitor',
      operation: 'status'
    });
    
    console.log('\n5. Monitor status:');
    console.log(JSON.stringify(monitorStatus, null, 2));
    
    // Verify auto-capture is running
    if (checkInResult.autoCapture?.enabled) {
      console.log('\n✅ SUCCESS: Auto-capture was automatically started during check_in');
      console.log('   - Stream key:', checkInResult.autoCapture.streamKey);
      console.log('   - Monitoring:', checkInResult.autoCapture.monitoring);
    } else {
      console.log('\n❌ FAILED: Auto-capture was not started');
      if (checkInResult.autoCapture?.error) {
        console.log('   - Error:', checkInResult.autoCapture.error);
      }
      if (checkInResult.autoCapture?.reason) {
        console.log('   - Reason:', checkInResult.autoCapture.reason);
      }
    }
    
    // Clean up - stop monitoring
    console.log('\n6. Stopping monitor for cleanup...');
    await ui.think({
      action: 'monitor',
      operation: 'stop'
    });
    
    console.log('\n=== Test Complete ===');
    process.exit(0);
    
  } catch (error) {
    console.error('\n❌ Test failed with error:', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

// Run the test
testCheckInAutoCapture();