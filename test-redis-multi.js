#!/usr/bin/env node

import { createClient } from 'redis';

async function testRedisMulti() {
  console.log('Testing Redis multi() support...\n');
  
  const client = createClient({
    url: 'redis://:LegacyMind@localhost:6379'
  });
  
  try {
    await client.connect();
    console.log('Connected to Redis');
    
    // Test if multi is available
    console.log('Client methods available:');
    console.log('- multi:', typeof client.multi);
    console.log('- pipeline:', typeof client.pipeline);
    console.log('- MULTI:', typeof client.MULTI);
    
    // Try using multi
    console.log('\nTesting multi() command...');
    const multi = client.multi();
    console.log('Multi object created:', !!multi);
    console.log('Multi type:', typeof multi);
    
    // Add some commands
    multi.set('test:1', 'value1');
    multi.set('test:2', 'value2');
    multi.get('test:1');
    multi.get('test:2');
    
    const results = await multi.exec();
    console.log('Multi exec results:', results);
    
    // Clean up
    await client.del(['test:1', 'test:2']);
    
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await client.quit();
  }
}

testRedisMulti().catch(console.error);