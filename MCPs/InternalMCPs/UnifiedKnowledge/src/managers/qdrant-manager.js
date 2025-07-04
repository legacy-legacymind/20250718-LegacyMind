// src/managers/qdrant-manager.js
import { QdrantClient } from '@qdrant/js-client-rest';
import { OpenAI } from 'openai';
import { v4 as uuidv4 } from 'uuid';
import { logger } from '../utils/logger.js';
import { ErrorHandler, ConnectionError, ExternalServiceError, ErrorCodes } from '../utils/error-handler.js';

export class QdrantManager {
  constructor() {
    this.client = null;
    this.openai = null;
    this.isConnected = false;
  }

  async connect() {
    const qdrantUrl = process.env.QDRANT_URL || `http://${process.env.QDRANT_HOST || 'localhost'}:${process.env.QDRANT_PORT || 6333}`;
    
    logger.info('Connecting to Qdrant', {
      url: qdrantUrl,
      hasApiKey: !!process.env.QDRANT_API_KEY,
      hasOpenAIKey: !!process.env.OPENAI_API_KEY
    });
    
    this.client = new QdrantClient({ 
      url: qdrantUrl, 
      apiKey: process.env.QDRANT_API_KEY,
      checkCompatibility: false 
    });
    
    if (!process.env.OPENAI_API_KEY) {
      throw new ConnectionError(
        'OpenAI API key is required for embedding operations',
        'openai',
        { operation: 'connect' }
      );
    }
    
    this.openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

    try {
      const result = await ErrorHandler.withRetry(
        () => this.client.getCollections(),
        {
          maxRetries: 3,
          baseDelay: 2000,
          context: { service: 'qdrant', url: qdrantUrl }
        }
      );
      
      this.isConnected = true;
      logger.info('Qdrant connected successfully', {
        url: qdrantUrl,
        collections: result.collections.map(c => c.name)
      });
      
      // Ensure the 'memories' collection exists
      const hasMemoriesCollection = result.collections.some(c => c.name === 'memories');
      if (!hasMemoriesCollection) {
        await this.ensureMemoriesCollection();
      }
    } catch (err) {
      this.isConnected = false;
      const error = ErrorHandler.handleConnectionError('qdrant', err, {
        url: qdrantUrl,
        hasApiKey: !!process.env.QDRANT_API_KEY
      });
      logger.error('Failed to connect to Qdrant', {
        error: error.message,
        context: error.context
      });
      throw error;
    }
  }

  async ensureMemoriesCollection() {
    try {
      await this.client.createCollection('memories', {
        vectors: { size: 1536, distance: 'Cosine' },
      });
      logger.info('Created "memories" collection in Qdrant');
    } catch (error) {
      if (error.message.includes('already exists')) {
        logger.debug('Memories collection already exists');
      } else {
        throw ErrorHandler.handleExternalServiceError('qdrant', 'createCollection', error, {
          collection: 'memories'
        });
      }
    }
  }

  async embedAndStoreTicket(ticket, options = { throwOnFailure: false }) {
    logger.info('Starting ticket embedding process', {
      ticketId: ticket.ticket_id,
      isConnected: this.isConnected,
      status: ticket.status
    });
    
    if (!this.isConnected) {
      const error = new ConnectionError(
        'Qdrant not connected, cannot embed ticket',
        'qdrant',
        { operation: 'embedAndStoreTicket', ticketId: ticket.ticket_id }
      );
      
      if (options.throwOnFailure) {
        throw error;
      } else {
        logger.warn('Qdrant not connected, skipping embedding', {
          ticketId: ticket.ticket_id,
          error: error.message
        });
        return { success: false, error: error.message, skipped: true };
      }
    }

    try {
      const textToEmbed = `
        Ticket ID: ${ticket.ticket_id}
        Title: ${ticket.title}
        Type: ${ticket.type}
        System: ${ticket.system}
        Description: ${ticket.description}
        Resolution: ${ticket.resolution || 'No resolution notes.'}
      `.trim();
      
      logger.debug('Prepared text for embedding', {
        ticketId: ticket.ticket_id,
        textLength: textToEmbed.length,
        preview: textToEmbed.substring(0, 200)
      });

      // Create embedding with retry logic
      const embeddingResponse = await ErrorHandler.withRetry(
        () => this.openai.embeddings.create({
          model: 'text-embedding-3-small',
          input: textToEmbed,
        }),
        {
          maxRetries: 2,
          baseDelay: 1000,
          context: { service: 'openai', operation: 'embedding', ticketId: ticket.ticket_id }
        }
      );

      const embedding = embeddingResponse.data[0].embedding;
      logger.debug('Embedding created successfully', {
        ticketId: ticket.ticket_id,
        vectorLength: embedding.length
      });

      const pointId = uuidv4();
      
      // Store in Qdrant with retry logic
      await ErrorHandler.withRetry(
        () => this.client.upsert('memories', {
          wait: true,
          points: [
            {
              id: pointId,
              vector: embedding,
              payload: {
                type: 'ticket',
                source: 'UnifiedWorkflow',
                ticket_id: ticket.ticket_id,
                content: textToEmbed,
                created_at: ticket.created_at,
                completed_at: ticket.updated_at,
                reporter: ticket.reporter,
                assignee: ticket.assignee,
              },
            },
          ],
        }),
        {
          maxRetries: 2,
          baseDelay: 1000,
          context: { service: 'qdrant', operation: 'upsert', ticketId: ticket.ticket_id }
        }
      );

      logger.info('Ticket embedded and stored successfully', {
        ticketId: ticket.ticket_id,
        pointId,
        vectorLength: embedding.length
      });
      
      return { success: true, pointId, vectorLength: embedding.length };
    } catch (error) {
      const contextualError = ErrorHandler.handleExternalServiceError(
        error.message.includes('openai') || error.message.includes('embedding') ? 'openai' : 'qdrant',
        'embedAndStoreTicket',
        error,
        { ticketId: ticket.ticket_id }
      );
      
      logger.error('Ticket embedding failed', {
        ticketId: ticket.ticket_id,
        error: contextualError.message,
        errorType: error.constructor.name,
        stack: error.stack
      });
      
      if (options.throwOnFailure) {
        throw contextualError;
      } else {
        return { 
          success: false, 
          error: contextualError.message, 
          errorCode: contextualError.code,
          skipped: false 
        };
      }
    }
  }

  async indexProject(projectId, name, description, payload, options = { throwOnFailure: false }) {
    if (!this.isConnected) {
      const error = new ConnectionError(
        'Qdrant not connected, cannot index project',
        'qdrant',
        { operation: 'indexProject', projectId }
      );
      
      if (options.throwOnFailure) {
        throw error;
      } else {
        logger.warn('Qdrant not connected, skipping project indexing', {
          projectId,
          error: error.message
        });
        return { success: false, error: error.message, skipped: true };
      }
    }

    try {
      const text = `${name} ${description || ''}`.trim();
      
      const embedding = await ErrorHandler.withRetry(
        () => this.openai.embeddings.create({
          model: 'text-embedding-ada-002',
          input: text,
        }),
        {
          maxRetries: 2,
          context: { service: 'openai', operation: 'embedding', projectId }
        }
      );

      const pointId = uuidv4();
      await ErrorHandler.withRetry(
        () => this.client.upsert('memories', {
          points: [
            {
              id: pointId,
              vector: embedding.data[0].embedding,
              payload: {
                ...payload,
                type: 'project',
                text,
                indexed_at: new Date().toISOString()
              }
            }
          ]
        }),
        {
          maxRetries: 2,
          context: { service: 'qdrant', operation: 'upsert', projectId }
        }
      );

      logger.info('Project indexed successfully', {
        projectId,
        pointId,
        textLength: text.length
      });
      
      return { success: true, pointId };
    } catch (error) {
      const contextualError = ErrorHandler.handleExternalServiceError(
        error.message.includes('openai') || error.message.includes('embedding') ? 'openai' : 'qdrant',
        'indexProject',
        error,
        { projectId }
      );
      
      logger.error('Project indexing failed', {
        projectId,
        error: contextualError.message
      });
      
      if (options.throwOnFailure) {
        throw contextualError;
      } else {
        return { 
          success: false, 
          error: contextualError.message, 
          errorCode: contextualError.code,
          skipped: false 
        };
      }
    }
  }

  async deleteProject(projectId, options = { throwOnFailure: false }) {
    if (!this.isConnected) {
      const error = new ConnectionError(
        'Qdrant not connected, cannot delete project',
        'qdrant',
        { operation: 'deleteProject', projectId }
      );
      
      if (options.throwOnFailure) {
        throw error;
      } else {
        logger.warn('Qdrant not connected, skipping project deletion', {
          projectId,
          error: error.message
        });
        return { success: false, error: error.message, skipped: true };
      }
    }

    try {
      await ErrorHandler.withRetry(
        () => this.client.delete('memories', {
          filter: {
            must: [
              { key: 'project_id', match: { value: projectId } },
              { key: 'type', match: { value: 'project' } }
            ]
          }
        }),
        {
          maxRetries: 2,
          context: { service: 'qdrant', operation: 'delete', projectId }
        }
      );

      logger.info('Project removed from Qdrant successfully', { projectId });
      return { success: true };
    } catch (error) {
      const contextualError = ErrorHandler.handleExternalServiceError('qdrant', 'deleteProject', error, {
        projectId
      });
      
      logger.error('Project deletion from Qdrant failed', {
        projectId,
        error: contextualError.message
      });
      
      if (options.throwOnFailure) {
        throw contextualError;
      } else {
        return { 
          success: false, 
          error: contextualError.message, 
          errorCode: contextualError.code,
          skipped: false 
        };
      }
    }
  }

  async indexDocument(docId, title, content, payload) {
    if (!this.isConnected) {
      logger.warn('Qdrant is not connected. Skipping document indexing.');
      return;
    }

    try {
      const text = `${title} ${content || ''}`.trim().substring(0, 8000); // Limit text length
      const embedding = await this.openai.embeddings.create({
        model: 'text-embedding-ada-002',
        input: text,
      });

      const pointId = uuidv4();
      await this.client.upsert('memories', {
        points: [
          {
            id: pointId,
            vector: embedding.data[0].embedding,
            payload: {
              ...payload,
              type: 'document',
              text,
              indexed_at: new Date().toISOString()
            }
          }
        ]
      });

      logger.info(`Document ${docId} indexed in Qdrant with ID: ${pointId}`);
    } catch (error) {
      logger.error(`Failed to index document in Qdrant: ${error.message}`);
      // Non-critical error, don't throw
    }
  }

  async deleteDocument(docId) {
    if (!this.isConnected) {
      logger.warn('Qdrant is not connected. Skipping document deletion.');
      return;
    }

    try {
      await this.client.delete('memories', {
        filter: {
          must: [
            { key: 'doc_id', match: { value: docId } },
            { key: 'type', match: { value: 'document' } }
          ]
        }
      });

      logger.info(`Document ${docId} removed from Qdrant`);
    } catch (error) {
      logger.error(`Failed to delete document from Qdrant: ${error.message}`);
      // Non-critical error, don't throw
    }
  }
}
