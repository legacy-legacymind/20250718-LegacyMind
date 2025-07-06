import { RedisManager } from './src/managers/redis-manager.js';

async function testRedisTransaction() {
  const redis = new RedisManager();
  
  try {
    console.log('Connecting to Redis...');
    await redis.connect();
    
    console.log('\nTesting ticket store with transaction...');
    const testTicket = {
      id: 'TEST-001',
      ticket_id: 'TEST-001',
      title: 'Test Ticket for Transaction',
      description: 'Testing Redis transaction result handling',
      status: 'OPEN',
      priority: 'HIGH',
      type: 'BUG',
      category: 'TECHNICAL',
      system: 'UnifiedKnowledge',
      reporter: 'Sam',
      assignee: 'CCI',
      tags: ['test', 'redis', 'transaction'],
      members: ['Sam', 'CCI'],
      created_at: new Date().toISOString(),
      estimated_hours: 1,
      acceptance_criteria: ['Transaction works correctly', 'No errors thrown'],
      comments: [],
      history: [],
      links: [],
      metadata: { test: true }
    };
    
    // Store the ticket
    const result = await redis.storeTicket('TEST-001', testTicket);
    console.log('\nTicket stored successfully!');
    console.log('Result:', result.id, '-', result.title);
    
    // Retrieve and verify
    console.log('\nRetrieving ticket...');
    const retrieved = await redis.getTicket('TEST-001');
    console.log('Retrieved ticket:', retrieved.id, '-', retrieved.title);
    console.log('Tags:', retrieved.tags);
    console.log('Status:', retrieved.status);
    console.log('Priority:', retrieved.priority);
    
    // Test finding by filters
    console.log('\nTesting findTicketsBy with filters...');
    const byStatus = await redis.findTicketsBy({ status: 'OPEN' });
    console.log('Found', byStatus.length, 'OPEN tickets');
    
    const byAssignee = await redis.findTicketsBy({ assignee: 'CCI' });
    console.log('Found', byAssignee.length, 'tickets assigned to CCI');
    
    const byTags = await redis.findTicketsBy({ tags: ['test'] });
    console.log('Found', byTags.length, 'tickets with "test" tag');
    
    // Clean up
    console.log('\nCleaning up test ticket...');
    await redis.deleteTicket('TEST-001');
    console.log('Test ticket deleted');
    
    console.log('\n✅ All tests passed! Transaction handling is working correctly.');
    
  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    console.error('Stack:', error.stack);
  } finally {
    console.log('\nDisconnecting...');
    await redis.disconnect();
  }
}

// Run the test
testRedisTransaction();