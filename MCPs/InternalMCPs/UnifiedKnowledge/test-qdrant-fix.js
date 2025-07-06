#!/usr/bin/env node

import dotenv from 'dotenv';
import { QdrantManager } from './src/managers/qdrant-manager.js';
import { EmbeddingService } from './src/services/embedding-service.js';

// Load environment variables
dotenv.config();

async function testQdrantFix() {
  console.log('Testing Qdrant payload indexing fix...\n');
  
  const qdrant = new QdrantManager();
  const embedding = new EmbeddingService();
  
  try {
    // Connect to Qdrant
    console.log('1. Connecting to Qdrant...');
    await qdrant.connect();
    console.log('✓ Connected to Qdrant\n');
    
    // Test ticket with UK format ID
    const testTicketId = 'UK-20241219-123456';
    const testTicket = {
      ticket_id: testTicketId,
      title: 'Test Qdrant Fix',
      description: 'Testing the Qdrant payload indexing implementation',
      type: 'task',
      category: 'testing',
      system: 'UnifiedKnowledge',
      reporter: 'test-script',
      assignee: 'sam',
      status: 'open',
      priority: 'medium',
      tags: ['test', 'qdrant', 'fix'],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      resolution: null
    };
    
    // Generate embedding
    console.log('2. Generating embedding for test ticket...');
    const ticketEmbedding = await embedding.generateTicketEmbedding(testTicket);
    console.log(`✓ Generated embedding (dimension: ${ticketEmbedding.length})\n`);
    
    // Store embedding with UK format ID
    console.log('3. Storing embedding with UK format ticket ID...');
    await qdrant.upsertTicketEmbedding(testTicketId, ticketEmbedding, testTicket);
    console.log('✓ Successfully stored embedding\n');
    
    // Retrieve embedding by ticket ID
    console.log('4. Retrieving embedding by ticket ID...');
    const retrieved = await qdrant.getTicketEmbeddingByTicketId(testTicketId);
    if (retrieved) {
      console.log('✓ Successfully retrieved embedding');
      console.log(`  - Ticket ID: ${retrieved.payload.ticket_id}`);
      console.log(`  - Title: ${retrieved.payload.title}`);
      console.log(`  - Vector dimension: ${retrieved.vector.length}\n`);
    } else {
      throw new Error('Failed to retrieve embedding');
    }
    
    // Test semantic search
    console.log('5. Testing semantic search...');
    const queryEmbedding = await embedding.generateQueryEmbedding('qdrant fix test');
    const searchResults = await qdrant.searchTickets(queryEmbedding, 5);
    console.log(`✓ Search returned ${searchResults.length} results`);
    
    const foundTestTicket = searchResults.find(r => r.ticket_id === testTicketId);
    if (foundTestTicket) {
      console.log(`✓ Found test ticket in search results`);
      console.log(`  - Score: ${foundTestTicket.score}`);
      console.log(`  - Ticket ID: ${foundTestTicket.ticket_id}\n`);
    }
    
    // Test update (upsert with same ID)
    console.log('6. Testing update (upsert) with same ticket ID...');
    testTicket.description = 'Updated description for Qdrant fix test';
    testTicket.updated_at = new Date().toISOString();
    const updatedEmbedding = await embedding.generateTicketEmbedding(testTicket);
    await qdrant.upsertTicketEmbedding(testTicketId, updatedEmbedding, testTicket);
    console.log('✓ Successfully updated embedding\n');
    
    // Verify update
    console.log('7. Verifying update...');
    const updatedRetrieved = await qdrant.getTicketEmbeddingByTicketId(testTicketId);
    if (updatedRetrieved && updatedRetrieved.payload.description === testTicket.description) {
      console.log('✓ Update verified - description changed correctly\n');
    } else {
      throw new Error('Update verification failed');
    }
    
    // Clean up
    console.log('8. Cleaning up test data...');
    await qdrant.deleteTicketEmbedding(testTicketId);
    console.log('✓ Deleted test embedding\n');
    
    // Verify deletion
    console.log('9. Verifying deletion...');
    const deletedCheck = await qdrant.getTicketEmbeddingByTicketId(testTicketId);
    if (deletedCheck === null) {
      console.log('✓ Deletion verified - embedding no longer exists\n');
    } else {
      throw new Error('Deletion verification failed');
    }
    
    console.log('✅ All tests passed! Qdrant payload indexing fix is working correctly.');
    
  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    console.error(error);
    process.exit(1);
  }
  
  process.exit(0);
}

// Run the test
testQdrantFix();