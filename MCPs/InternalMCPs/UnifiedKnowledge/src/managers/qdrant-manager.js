import { QdrantClient } from '@qdrant/js-client-rest';
import crypto from 'crypto';

export class QdrantManager {
  constructor() {
    this.client = null;
    this.isConnected = false;
    this.collections = {
      tickets: 'uk_tickets',
      docs: 'uk_system_docs'
    };
  }

  async connect() {
    try {
      const host = process.env.QDRANT_HOST || 'localhost';
      const port = process.env.QDRANT_PORT || 6333;
      const apiKey = process.env.QDRANT_API_KEY;
      
      this.client = new QdrantClient({
        url: `http://${host}:${port}`,
        apiKey
      });

      // Test connection
      await this.client.getCollections();
      
      console.error('[Qdrant] Connected to Qdrant');
      this.isConnected = true;
      
      // Ensure collections exist
      await this.ensureCollections();
      
      return true;
    } catch (error) {
      console.error('[Qdrant] Connection failed:', error);
      throw error;
    }
  }

  async ensureCollections() {
    try {
      // Check and create tickets collection
      const collections = await this.client.getCollections();
      const existingCollections = collections.collections.map(c => c.name);
      
      if (!existingCollections.includes(this.collections.tickets)) {
        await this.createCollection(this.collections.tickets);
        await this.createPayloadIndex(this.collections.tickets, 'ticket_id');
      }
      
      if (!existingCollections.includes(this.collections.docs)) {
        await this.createCollection(this.collections.docs);
        await this.createPayloadIndex(this.collections.docs, 'doc_id');
      }
      
      console.error('[Qdrant] Collections verified');
    } catch (error) {
      console.error('[Qdrant] Failed to ensure collections:', error);
      throw error;
    }
  }

  async createCollection(collectionName) {
    try {
      await this.client.createCollection(collectionName, {
        vectors: {
          size: 1536, // OpenAI text-embedding-3-small dimension
          distance: 'Cosine'
        },
        optimizers_config: {
          default_segment_number: 2
        },
        replication_factor: 1
      });
      
      console.error(`[Qdrant] Created collection: ${collectionName}`);
    } catch (error) {
      console.error(`[Qdrant] Failed to create collection ${collectionName}:`, error);
      throw error;
    }
  }

  async createPayloadIndex(collectionName, fieldName) {
    try {
      await this.client.createPayloadIndex(collectionName, {
        field_name: fieldName,
        field_schema: 'keyword'
      });
      console.error(`[Qdrant] Created payload index on ${fieldName} for collection: ${collectionName}`);
    } catch (error) {
      // Index might already exist, which is fine
      if (error.message && error.message.includes('already exists')) {
        console.error(`[Qdrant] Payload index on ${fieldName} already exists for collection: ${collectionName}`);
      } else {
        console.error(`[Qdrant] Failed to create payload index on ${fieldName} for collection ${collectionName}:`, error);
        // Don't throw - index creation failure shouldn't break initialization
      }
    }
  }

  async upsertTicketEmbedding(ticketId, embedding, ticketData) {
    try {
      // Generate a UUID for the point ID
      const point = {
        id: crypto.randomUUID(),
        vector: embedding,
        payload: {
          ticket_id: ticketId, // Store ticket_id in payload instead
          title: ticketData.title,
          type: ticketData.type,
          category: ticketData.category,
          system: ticketData.system,
          reporter: ticketData.reporter,
          assignee: ticketData.assignee,
          status: ticketData.status,
          priority: ticketData.priority,
          tags: ticketData.tags || [],
          created_at: ticketData.created_at,
          updated_at: ticketData.updated_at,
          resolution: ticketData.resolution,
          description: ticketData.description || ''
        }
      };

      // First, delete any existing embedding for this ticket_id
      await this.deleteTicketEmbedding(ticketId);

      await this.client.upsert(this.collections.tickets, {
        wait: true,
        points: [point]
      });

      console.error(`[Qdrant] Upserted embedding for ticket ${ticketId}`);
      return true;
    } catch (error) {
      console.error('[Qdrant] Failed to upsert ticket embedding:', error);
      throw error;
    }
  }

  async searchTickets(queryEmbedding, limit = 10, filter = null) {
    try {
      const searchParams = {
        vector: queryEmbedding,
        limit,
        with_payload: true,
        with_vector: false
      };

      if (filter) {
        searchParams.filter = filter;
      }

      const results = await this.client.search(this.collections.tickets, searchParams);
      
      return results.map(result => ({
        score: result.score,
        ticket_id: result.payload.ticket_id, // Explicitly include ticket_id from payload
        ...result.payload
      }));
    } catch (error) {
      console.error('[Qdrant] Failed to search tickets:', error);
      throw error;
    }
  }

  async deleteTicketEmbedding(ticketId) {
    try {
      // Delete by payload filter since we're no longer using ticket_id as point ID
      const filter = {
        must: [
          {
            key: 'ticket_id',
            match: {
              value: ticketId
            }
          }
        ]
      };

      await this.client.delete(this.collections.tickets, {
        wait: true,
        filter: filter
      });
      
      console.error(`[Qdrant] Deleted embedding for ticket ${ticketId}`);
      return true;
    } catch (error) {
      // Ignore errors - ticket might not have an embedding yet
      console.error('[Qdrant] Failed to delete ticket embedding (may not exist):', error.message);
      return false;
    }
  }

  async getTicketEmbeddingByTicketId(ticketId) {
    try {
      const filter = {
        must: [
          {
            key: 'ticket_id',
            match: {
              value: ticketId
            }
          }
        ]
      };

      const result = await this.client.scroll(this.collections.tickets, {
        filter: filter,
        limit: 1,
        with_payload: true,
        with_vector: true
      });

      if (result.points && result.points.length > 0) {
        return {
          vector: result.points[0].vector,
          payload: result.points[0].payload
        };
      }

      return null;
    } catch (error) {
      console.error('[Qdrant] Failed to get ticket embedding by ID:', error);
      throw error;
    }
  }

  // System documentation operations (Phase 2)
  async upsertDocEmbedding(docId, embedding, docData) {
    try {
      // Generate a UUID for the point ID
      const point = {
        id: crypto.randomUUID(),
        vector: embedding,
        payload: {
          doc_id: docId, // Store doc_id in payload instead
          title: docData.title,
          category: docData.category,
          system: docData.system,
          version: docData.version,
          valid_from: docData.valid_from,
          valid_to: docData.valid_to,
          created_at: docData.created_at,
          updated_at: docData.updated_at,
          content: docData.content || ''
        }
      };

      // First, delete any existing embedding for this doc_id
      await this.deleteDocEmbedding(docId);

      await this.client.upsert(this.collections.docs, {
        wait: true,
        points: [point]
      });

      console.error(`[Qdrant] Upserted embedding for doc ${docId}`);
      return true;
    } catch (error) {
      console.error('[Qdrant] Failed to upsert doc embedding:', error);
      throw error;
    }
  }

  async deleteDocEmbedding(docId) {
    try {
      // Delete by payload filter since we're no longer using doc_id as point ID
      const filter = {
        must: [
          {
            key: 'doc_id',
            match: {
              value: docId
            }
          }
        ]
      };

      await this.client.delete(this.collections.docs, {
        wait: true,
        filter: filter
      });
      
      console.error(`[Qdrant] Deleted embedding for doc ${docId}`);
      return true;
    } catch (error) {
      // Ignore errors - doc might not have an embedding yet
      console.error('[Qdrant] Failed to delete doc embedding (may not exist):', error.message);
      return false;
    }
  }

  async searchDocs(queryEmbedding, limit = 10, filter = null) {
    try {
      const searchParams = {
        vector: queryEmbedding,
        limit,
        with_payload: true,
        with_vector: false
      };

      if (filter) {
        searchParams.filter = filter;
      }

      const results = await this.client.search(this.collections.docs, searchParams);
      
      return results.map(result => ({
        score: result.score,
        doc_id: result.payload.doc_id, // Explicitly include doc_id from payload
        ...result.payload
      }));
    } catch (error) {
      console.error('[Qdrant] Failed to search docs:', error);
      throw error;
    }
  }

  // Health check
  async healthCheck() {
    try {
      await this.client.getCollections();
      return { status: 'healthy', timestamp: new Date().toISOString() };
    } catch (error) {
      return { 
        status: 'unhealthy', 
        error: error.message, 
        timestamp: new Date().toISOString() 
      };
    }
  }

  // Deprecated - no longer needed as we use UUID strings directly
  // Qdrant supports UUID strings as point IDs
  generatePointId(id) {
    console.warn('[Qdrant] generatePointId is deprecated - use UUID strings directly');
    return id; // Return the ID as-is
  }
}