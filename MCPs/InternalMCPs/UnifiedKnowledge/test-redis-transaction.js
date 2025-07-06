#!/usr/bin/env node

import { RedisManager } from './src/managers/redis-manager.js';

async function testRedisTransaction() {
  console.log('Testing Redis Transaction...\n');
  
  const manager = new RedisManager();
  
  try {
    console.log('Connecting to Redis...');
    await manager.connect();
    console.log('Connected successfully\n');
    
    // Test ticket data
    const testTicket = {
      id: 'TEST-001',
      ticket_id: 'TEST-001',
      title: 'Test Ticket for Transaction Debugging',
      description: 'This is a test ticket to debug MULTI/EXEC transactions',
      status: 'OPEN',
      priority: 'HIGH',
      type: 'BUG',
      category: 'Testing',
      system: 'UnifiedKnowledge',
      reporter: 'test-script',
      assignee: 'developer',
      tags: ['test', 'debug', 'redis'],
      members: ['test-script', 'developer'],
      linked_tickets: [],
      acceptance_criteria: ['Transaction completes successfully'],
      estimated_hours: 1,
      resolution: '',
      comments: [{
        id: 'comment-1',
        author: 'test-script',
        content: 'Initial test comment',
        created_at: new Date().toISOString()
      }],
      history: [{
        action: 'created',
        by: 'test-script',
        at: new Date().toISOString(),
        details: 'Ticket created for testing'
      }],
      links: [],
      metadata: {
        source: 'test-script',
        version: '1.0'
      }
    };
    
    console.log('Attempting to store ticket...');
    console.log('Ticket ID:', testTicket.id);
    console.log('Ticket Status:', testTicket.status);
    console.log('Ticket Priority:', testTicket.priority);
    console.log('');
    
    const result = await manager.storeTicket(testTicket.id, testTicket);
    console.log('\nTicket stored successfully!');
    console.log('Result:', result);
    
    // Try to retrieve the ticket
    console.log('\nRetrieving stored ticket...');
    const retrieved = await manager.getTicket(testTicket.id);
    console.log('Retrieved ticket:', retrieved);
    
  } catch (error) {
    console.error('\nError during test:', error.message);
    console.error('Stack:', error.stack);
  } finally {
    console.log('\nDisconnecting...');
    await manager.disconnect();
    console.log('Test complete');
  }
}

testRedisTransaction().catch(console.error);