import { RedisManager } from './src/managers/redis-manager.js';
import { createClient } from 'redis';
import dotenv from 'dotenv';

dotenv.config();

async function testTicketSearch() {
  console.log('Testing Ticket Search Functionality...\n');
  
  const redisManager = new RedisManager();
  
  try {
    // Connect to Redis
    await redisManager.connect();
    console.log('✓ Connected to Redis\n');
    
    // Test 1: Direct Redis queries to check indexes
    console.log('=== Test 1: Checking Index Keys ===');
    const client = redisManager.client;
    
    // List all keys to see what's in Redis
    const allKeys = await client.keys('*');
    console.log(`Total keys in Redis: ${allKeys.length}`);
    
    // Group keys by type
    const ticketKeys = allKeys.filter(k => k.startsWith('ticket:'));
    const indexKeys = allKeys.filter(k => k.startsWith('index:'));
    
    console.log(`Ticket keys: ${ticketKeys.length}`);
    console.log(`Index keys: ${indexKeys.length}`);
    
    // Show some sample keys
    console.log('\nSample ticket keys:', ticketKeys.slice(0, 5));
    console.log('Sample index keys:', indexKeys.slice(0, 10));
    
    // Test 2: Check specific indexes
    console.log('\n=== Test 2: Checking Specific Indexes ===');
    
    // Check assignee index for CCD
    const ccdAssigneeKey = 'index:assignee:ccd';
    const ccdTickets = await client.sMembers(ccdAssigneeKey);
    console.log(`\nTickets assigned to CCD (${ccdAssigneeKey}): ${ccdTickets.length}`);
    if (ccdTickets.length > 0) {
      console.log('CCD ticket IDs:', ccdTickets);
    }
    
    // Check if there's a case sensitivity issue
    const ccdUpperKey = 'index:assignee:CCD';
    const ccdUpperTickets = await client.sMembers(ccdUpperKey);
    console.log(`\nTickets assigned to CCD (uppercase): ${ccdUpperTickets.length}`);
    
    // Check status indexes
    console.log('\n=== Status Indexes ===');
    const statuses = ['open', 'in_progress', 'closed', 'cancelled'];
    for (const status of statuses) {
      const statusKey = `index:status:${status}`;
      const statusTickets = await client.sMembers(statusKey);
      console.log(`${status}: ${statusTickets.length} tickets`);
    }
    
    // Check sorted sets
    console.log('\n=== Sorted Sets ===');
    const createdAtCount = await client.zCard('index:created_at');
    const updatedAtCount = await client.zCard('index:updated_at');
    const priorityCount = await client.zCard('index:priority');
    
    console.log(`Created at index: ${createdAtCount} entries`);
    console.log(`Updated at index: ${updatedAtCount} entries`);
    console.log(`Priority index: ${priorityCount} entries`);
    
    // Test 3: Test getAllActiveTickets method
    console.log('\n=== Test 3: getAllActiveTickets ===');
    const activeTickets = await redisManager.getAllActiveTickets();
    console.log(`Active tickets found: ${activeTickets.length}`);
    
    if (activeTickets.length > 0) {
      console.log('\nFirst active ticket:', JSON.stringify(activeTickets[0], null, 2));
    }
    
    // Test 4: Test searchTickets with assignee filter
    console.log('\n=== Test 4: searchTickets with assignee filter ===');
    const ccdSearchResults = await redisManager.searchTickets({ assignee: 'CCD' });
    console.log(`Search results for assignee=CCD: ${ccdSearchResults.length}`);
    
    // Try lowercase
    const ccdLowerSearchResults = await redisManager.searchTickets({ assignee: 'ccd' });
    console.log(`Search results for assignee=ccd: ${ccdLowerSearchResults.length}`);
    
    // Test 5: Check a specific ticket's data
    if (ticketKeys.length > 0) {
      console.log('\n=== Test 5: Sample Ticket Data ===');
      const sampleTicketId = ticketKeys[0].replace('ticket:', '');
      const sampleTicket = await redisManager.getTicket(sampleTicketId);
      console.log('Sample ticket:', JSON.stringify(sampleTicket, null, 2));
    }
    
    // Test 6: Check for orphaned indexes
    console.log('\n=== Test 6: Checking for Orphaned Index Entries ===');
    let orphanedCount = 0;
    
    // Check assignee indexes
    const assigneeIndexes = indexKeys.filter(k => k.startsWith('index:assignee:'));
    for (const indexKey of assigneeIndexes) {
      const ticketIds = await client.sMembers(indexKey);
      for (const ticketId of ticketIds) {
        const exists = await client.exists(`ticket:${ticketId}`);
        if (!exists) {
          orphanedCount++;
          console.log(`Orphaned entry: ${ticketId} in ${indexKey}`);
        }
      }
    }
    
    console.log(`\nTotal orphaned index entries found: ${orphanedCount}`);
    
  } catch (error) {
    console.error('Error during testing:', error);
  } finally {
    await redisManager.disconnect();
    console.log('\n✓ Disconnected from Redis');
  }
}

// Run the test
testTicketSearch().catch(console.error);