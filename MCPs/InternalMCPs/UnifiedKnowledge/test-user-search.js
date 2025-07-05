import { RedisManager } from './src/managers/redis-manager.js';
import dotenv from 'dotenv';

dotenv.config();

async function testUserSearch() {
  console.log('Testing User-based Ticket Search...\n');
  
  const redisManager = new RedisManager();
  
  try {
    await redisManager.connect();
    console.log('✓ Connected to Redis\n');
    
    // Test searching for CCD's involvement
    console.log('=== Testing CCD Involvement ===');
    
    // Check reporter index
    const ccdReporterKey = 'index:reporter:ccd';
    const ccdReportedTickets = await redisManager.client.sMembers(ccdReporterKey);
    console.log(`Tickets reported by CCD: ${ccdReportedTickets.length}`);
    if (ccdReportedTickets.length > 0) {
      console.log('Ticket IDs:', ccdReportedTickets);
    }
    
    // Check assignee index
    const ccdAssigneeKey = 'index:assignee:ccd';
    const ccdAssignedTickets = await redisManager.client.sMembers(ccdAssigneeKey);
    console.log(`Tickets assigned to CCD: ${ccdAssignedTickets.length}`);
    
    // Get full details of tickets reported by CCD
    console.log('\n=== Tickets Reported by CCD ===');
    for (const ticketId of ccdReportedTickets) {
      const ticket = await redisManager.getTicket(ticketId);
      if (ticket) {
        console.log(`\nTicket: ${ticket.ticket_id}`);
        console.log(`Title: ${ticket.title}`);
        console.log(`Status: ${ticket.status}`);
        console.log(`Reporter: ${ticket.reporter}`);
        console.log(`Assignee: ${ticket.assignee}`);
      }
    }
    
    // Test assigning a ticket to CCD
    console.log('\n=== Testing Ticket Assignment ===');
    if (ccdReportedTickets.length > 0) {
      const ticketId = ccdReportedTickets[0];
      const ticket = await redisManager.getTicket(ticketId);
      
      // Update assignee to CCD
      ticket.assignee = 'CCD';
      await redisManager.storeTicket(ticketId, ticket);
      
      console.log(`\nAssigned ticket ${ticketId} to CCD`);
      
      // Now check assignee index again
      const updatedAssignedTickets = await redisManager.client.sMembers(ccdAssigneeKey);
      console.log(`Tickets now assigned to CCD: ${updatedAssignedTickets.length}`);
      
      // Test search by assignee
      const searchResults = await redisManager.searchTickets({ assignee: 'CCD' });
      console.log(`Search results for assignee=CCD: ${searchResults.length}`);
    }
    
  } catch (error) {
    console.error('Error during testing:', error);
  } finally {
    await redisManager.disconnect();
    console.log('\n✓ Disconnected from Redis');
  }
}

// Run the test
testUserSearch().catch(console.error);