import Redis from 'ioredis';

async function testDirectTransaction() {
  const client = new Redis({
    host: 'localhost',
    port: 6379,
    username: 'redis',
    password: 'UnifiedRedis2024!'
  });

  client.on('error', err => console.error('Redis Client Error:', err));
  
  try {
    console.log('Connected to Redis');

    // Test a simple transaction
    const multi = client.multi();
    
    multi.set('test:key1', 'value1');
    multi.set('test:key2', 'value2');
    multi.get('test:key1');
    
    console.log('Executing transaction...');
    const results = await multi.exec();
    console.log('Transaction results:', results);
    
    // Test watch/multi/exec pattern
    await client.watch('test:counter');
    const watchMulti = client.multi();
    watchMulti.incr('test:counter');
    
    console.log('Executing watched transaction...');
    const watchResults = await watchMulti.exec();
    console.log('Watched transaction results:', watchResults);
    
  } catch (error) {
    console.error('Error during transaction test:', error);
    console.error('Error stack:', error.stack);
  } finally {
    await client.quit();
  }
}

testDirectTransaction();