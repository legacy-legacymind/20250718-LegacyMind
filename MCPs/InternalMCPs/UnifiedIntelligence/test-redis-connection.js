import Redis from 'ioredis';
import { config } from './src/config.js';

async function testConnection() {
  console.log('Testing Redis connection...');
  console.log('Environment variables:');
  console.log('- REDIS_HOST:', process.env.REDIS_HOST || 'not set');
  console.log('- REDIS_PORT:', process.env.REDIS_PORT || 'not set');
  console.log('- REDIS_PASSWORD:', process.env.REDIS_PASSWORD ? 'set' : 'not set');
  console.log('- REDIS_URL:', process.env.REDIS_URL || 'not set');
  
  // Test with URL from config
  if (config.redisUrl) {
    console.log('\nTesting with config URL:', config.redisUrl.replace(/:([^:@]+)@/, ':***@'));
    const redisUrl = new Redis(config.redisUrl);
    
    try {
      const pong = await redisUrl.ping();
      console.log('✓ URL connection successful:', pong);
      
      // Test JSON support
      await redisUrl.call('JSON.SET', 'test:json', '$', JSON.stringify({test: true, timestamp: Date.now()}));
      const result = await redisUrl.call('JSON.GET', 'test:json', '$');
      console.log('✓ JSON support working:', result);
      
      // Clean up
      await redisUrl.del('test:json');
      redisUrl.disconnect();
    } catch (error) {
      console.error('✗ URL connection failed:', error.message);
      redisUrl.disconnect();
    }
  }
  
  // Test with host/port configuration
  console.log('\nTesting with host/port configuration...');
  const redisHostPort = new Redis({
    host: process.env.REDIS_HOST || 'legacymind_redis',
    port: parseInt(process.env.REDIS_PORT) || 6379,
    password: process.env.REDIS_PASSWORD
  });
  
  try {
    const pong = await redisHostPort.ping();
    console.log('✓ Host/port connection successful:', pong);
    
    // Test pub/sub
    const subscriber = new Redis({
      host: process.env.REDIS_HOST || 'legacymind_redis',
      port: parseInt(process.env.REDIS_PORT) || 6379,
      password: process.env.REDIS_PASSWORD
    });
    
    const publisher = new Redis({
      host: process.env.REDIS_HOST || 'legacymind_redis',
      port: parseInt(process.env.REDIS_PORT) || 6379,
      password: process.env.REDIS_PASSWORD
    });
    
    await subscriber.subscribe('test:channel');
    console.log('✓ Pub/sub subscription successful');
    
    // Test publishing
    await publisher.publish('test:channel', JSON.stringify({test: 'message'}));
    console.log('✓ Pub/sub publishing successful');
    
    // Clean up
    await subscriber.unsubscribe('test:channel');
    subscriber.disconnect();
    publisher.disconnect();
    redisHostPort.disconnect();
    
  } catch (error) {
    console.error('✗ Host/port connection failed:', error.message);
    redisHostPort.disconnect();
  }
  
  console.log('\nTest complete.');
}

testConnection().catch(console.error);