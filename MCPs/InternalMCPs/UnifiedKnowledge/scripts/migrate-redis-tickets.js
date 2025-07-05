#!/usr/bin/env node

/**
 * Migration script to convert old Redis ticket structure to new dual structure
 * Old: uk:ticket:* with JSON data
 * New: ticket:* with direct hash fields + indexes
 */

import { createClient } from 'redis';
import dotenv from 'dotenv';

dotenv.config();

class RedisTicketMigration {
  constructor() {
    this.client = null;
    this.stats = {
      total: 0,
      migrated: 0,
      skipped: 0,
      errors: 0
    };
  }

  async connect() {
    const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
    this.client = createClient({ url: redisUrl });
    
    this.client.on('error', (err) => {
      console.error('[Migration] Redis Client Error:', err);
    });

    await this.client.connect();
    console.log('[Migration] Connected to Redis');
  }

  async findOldTickets() {
    console.log('[Migration] Scanning for old tickets (uk:ticket:*)...');
    const oldTicketKeys = [];
    
    // Use SCAN to find all old ticket keys
    for await (const key of this.client.scanIterator({
      MATCH: 'uk:ticket:*',
      COUNT: 100
    })) {
      oldTicketKeys.push(key);
    }
    
    console.log(`[Migration] Found ${oldTicketKeys.length} old tickets`);
    return oldTicketKeys;
  }

  async migrateTicket(oldKey) {
    try {
      // Extract ticket ID from old key
      const ticketId = oldKey.replace('uk:ticket:', '');
      const newKey = `ticket:${ticketId}`;
      
      // Check if already migrated
      const exists = await this.client.exists(newKey);
      if (exists) {
        console.log(`[Migration] Ticket ${ticketId} already migrated, skipping`);
        this.stats.skipped++;
        return;
      }
      
      // Get old ticket data
      const oldData = await this.client.hGet(oldKey, 'data');
      if (!oldData) {
        console.error(`[Migration] No data found for ${ticketId}`);
        this.stats.errors++;
        return;
      }
      
      // Parse the JSON data
      const ticketData = JSON.parse(oldData);
      
      // Store in new hash structure
      const hashData = {
        ticket_id: ticketData.ticket_id,
        title: ticketData.title || '',
        description: ticketData.description || '',
        status: ticketData.status || 'OPEN',
        priority: ticketData.priority || 'MEDIUM',
        type: ticketData.type || 'TASK',
        category: ticketData.category || '',
        system: ticketData.system || '',
        reporter: ticketData.reporter || '',
        assignee: ticketData.assignee || '',
        created_at: ticketData.created_at || new Date().toISOString(),
        updated_at: ticketData.updated_at || new Date().toISOString(),
        tags: JSON.stringify(ticketData.tags || []),
        members: JSON.stringify(ticketData.members || []),
        linked_tickets: JSON.stringify(ticketData.linked_tickets || []),
        acceptance_criteria: JSON.stringify(ticketData.acceptance_criteria || []),
        estimated_hours: String(ticketData.estimated_hours || 0),
        resolution: ticketData.resolution || '',
        qdrant_id: ticketData.qdrant_id || ''
      };
      
      await this.client.hSet(newKey, hashData);
      
      // Build indexes
      await this.buildIndexes(ticketId, ticketData);
      
      // Set TTL if closed
      if (['CLOSED', 'CANCELLED'].includes(ticketData.status)) {
        await this.client.expire(newKey, 86400); // 24 hours
      }
      
      console.log(`[Migration] ✓ Migrated ticket ${ticketId}`);
      this.stats.migrated++;
      
    } catch (error) {
      console.error(`[Migration] Error migrating ${oldKey}:`, error);
      this.stats.errors++;
    }
  }

  async buildIndexes(ticketId, ticketData) {
    const priorityScores = { 'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1 };
    
    // Status index
    if (ticketData.status) {
      await this.client.sAdd(`index:status:${ticketData.status.toLowerCase()}`, ticketId);
    }
    
    // Assignee index
    if (ticketData.assignee) {
      await this.client.sAdd(`index:assignee:${ticketData.assignee.toLowerCase()}`, ticketId);
    }
    
    // Reporter index
    if (ticketData.reporter) {
      await this.client.sAdd(`index:reporter:${ticketData.reporter.toLowerCase()}`, ticketId);
    }
    
    // Type index
    if (ticketData.type) {
      await this.client.sAdd(`index:type:${ticketData.type.toLowerCase()}`, ticketId);
    }
    
    // Priority index
    if (ticketData.priority) {
      await this.client.sAdd(`index:priority:${ticketData.priority.toLowerCase()}`, ticketId);
    }
    
    // Tag indexes
    if (ticketData.tags && Array.isArray(ticketData.tags)) {
      for (const tag of ticketData.tags) {
        await this.client.sAdd(`index:tag:${tag.toLowerCase()}`, ticketId);
      }
    }
    
    // Sorted sets for ordering
    const createdTimestamp = new Date(ticketData.created_at).getTime();
    const updatedTimestamp = new Date(ticketData.updated_at).getTime();
    
    await this.client.zAdd('index:created_at', { score: createdTimestamp, value: ticketId });
    await this.client.zAdd('index:updated_at', { score: updatedTimestamp, value: ticketId });
    
    if (ticketData.priority && priorityScores[ticketData.priority]) {
      await this.client.zAdd('index:priority', { 
        score: priorityScores[ticketData.priority], 
        value: ticketId 
      });
    }
  }

  async cleanupOldIndexes() {
    console.log('[Migration] Cleaning up old indexes...');
    
    try {
      // Remove old sorted sets
      await this.client.del('uk:tickets:active');
      await this.client.del('uk:tickets:closed');
      console.log('[Migration] ✓ Old indexes cleaned up');
    } catch (error) {
      console.error('[Migration] Error cleaning old indexes:', error);
    }
  }

  async run() {
    try {
      await this.connect();
      
      const oldTickets = await this.findOldTickets();
      this.stats.total = oldTickets.length;
      
      if (oldTickets.length === 0) {
        console.log('[Migration] No old tickets found to migrate');
        return;
      }
      
      console.log('[Migration] Starting migration...');
      
      for (const oldKey of oldTickets) {
        await this.migrateTicket(oldKey);
      }
      
      // Clean up old indexes
      await this.cleanupOldIndexes();
      
      // Print summary
      console.log('\n[Migration] Summary:');
      console.log(`  Total tickets found: ${this.stats.total}`);
      console.log(`  Successfully migrated: ${this.stats.migrated}`);
      console.log(`  Skipped (already migrated): ${this.stats.skipped}`);
      console.log(`  Errors: ${this.stats.errors}`);
      
      if (this.stats.errors > 0) {
        console.log('\n[Migration] ⚠️  Some tickets failed to migrate. Check logs for details.');
      } else {
        console.log('\n[Migration] ✅ All tickets migrated successfully!');
      }
      
    } catch (error) {
      console.error('[Migration] Fatal error:', error);
    } finally {
      if (this.client) {
        await this.client.quit();
      }
    }
  }
}

// Run migration
const migration = new RedisTicketMigration();
migration.run().catch(console.error);