#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { RedisManager } from './managers/redis-manager.js';
import { PostgreSQLManager } from './managers/postgresql-manager.js';
import { QdrantManager } from './managers/qdrant-manager.js';
import { EmbeddingService } from './services/embedding-service.js';
import { ticketTools } from './tools/ticket-tools.js';
import { systemDocTools } from './tools/system-doc-tools.js';
import { handleDocumentTool } from './tools/document-tools.js';
import { DocumentManager } from './managers/document-manager.js';
import { runMigrations } from './utils/run-migrations.js';

class UnifiedKnowledgeServer {
  constructor() {
    this.server = new Server(
      {
        name: "unified-knowledge",
        version: "1.0.0",
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.redis = null;
    this.postgres = null;
    this.qdrant = null;
    this.embedding = null;
    this.documentManager = null;
    
    this.setupHandlers();
  }

  async initialize() {
    try {
      // Initialize Redis
      console.error('[UK] Initializing Redis connection...');
      this.redis = new RedisManager();
      await this.redis.connect();
      
      // Initialize PostgreSQL
      console.error('[UK] Initializing PostgreSQL connection...');
      const dbUrl = process.env.DATABASE_URL || 'postgresql://postgres:postgres@localhost:5432/postgres';
      this.postgres = new PostgreSQLManager({ connectionString: dbUrl });
      await this.postgres.connect();
      
      // Run database migrations
      console.error('[UK] Running database migrations...');
      await runMigrations(this.postgres);
      
      // Initialize Qdrant
      console.error('[UK] Initializing Qdrant connection...');
      this.qdrant = new QdrantManager();
      await this.qdrant.connect();
      
      // Initialize Embedding Service
      console.error('[UK] Initializing embedding service...');
      this.embedding = new EmbeddingService();
      
      // Initialize Document Manager
      console.error('[UK] Initializing document manager...');
      this.documentManager = new DocumentManager(this.redis, this.postgres);
      console.error('[UK] Document manager initialized with Active-Archive pattern');
      
      console.error('[UK] All services initialized successfully');
      
      // Set up connection monitoring
      this.startHealthMonitoring();
    } catch (error) {
      console.error('[UK] Failed to initialize services:', error);
      // Clean up any successful connections
      await this.cleanup();
      throw error;
    }
  }

  async cleanup() {
    console.error('[UK] Cleaning up connections...');
    
    try {
      if (this.redis && this.redis.isConnected) {
        await this.redis.disconnect();
      }
    } catch (error) {
      console.error('[UK] Error disconnecting Redis:', error);
    }
    
    try {
      if (this.postgres && this.postgres.isConnected) {
        await this.postgres.disconnect();
      }
    } catch (error) {
      console.error('[UK] Error disconnecting PostgreSQL:', error);
    }
    
    // Qdrant doesn't have explicit disconnect
    this.qdrant = null;
    this.embedding = null;
  }
  
  startHealthMonitoring() {
    // Monitor connection health every 30 seconds
    this.healthCheckInterval = setInterval(async () => {
      try {
        const health = await this.checkHealth();
        if (!health.healthy) {
          console.error('[UK] Health check failed:', health);
          // Attempt reconnection
          await this.reconnectServices();
        }
      } catch (error) {
        console.error('[UK] Health check error:', error);
      }
    }, 30000);
  }
  
  async checkHealth() {
    const results = {
      redis: null,
      postgres: null,
      qdrant: null,
      healthy: true
    };
    
    try {
      results.redis = await this.redis.healthCheck();
      if (results.redis.status !== 'healthy') results.healthy = false;
    } catch (error) {
      results.redis = { status: 'error', error: error.message };
      results.healthy = false;
    }
    
    try {
      results.postgres = await this.postgres.healthCheck();
      if (results.postgres.status !== 'healthy') results.healthy = false;
    } catch (error) {
      results.postgres = { status: 'error', error: error.message };
      results.healthy = false;
    }
    
    try {
      results.qdrant = await this.qdrant.healthCheck();
      if (results.qdrant.status !== 'healthy') results.healthy = false;
    } catch (error) {
      results.qdrant = { status: 'error', error: error.message };
      results.healthy = false;
    }
    
    return results;
  }
  
  async reconnectServices() {
    console.error('[UK] Attempting to reconnect failed services...');
    
    // Try to reconnect Redis if needed
    if (!this.redis.isConnected) {
      try {
        await this.redis.connect();
        console.error('[UK] Redis reconnected successfully');
      } catch (error) {
        console.error('[UK] Failed to reconnect Redis:', error);
      }
    }
    
    // Try to reconnect PostgreSQL if needed
    if (!this.postgres.isConnected) {
      try {
        await this.postgres.connect();
        console.error('[UK] PostgreSQL reconnected successfully');
      } catch (error) {
        console.error('[UK] Failed to reconnect PostgreSQL:', error);
      }
    }
    
    // Try to reconnect Qdrant if needed
    if (!this.qdrant.isConnected) {
      try {
        await this.qdrant.connect();
        console.error('[UK] Qdrant reconnected successfully');
      } catch (error) {
        console.error('[UK] Failed to reconnect Qdrant:', error);
      }
    }
  }
  
  setupHandlers() {
    // Tool listing
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          ...ticketTools.getToolDefinitions(),
          ...systemDocTools.getToolDefinitions(),
          {
            name: "document",
            description: "Manage versioned documents with Active-Archive storage pattern",
            inputSchema: {
              type: "object",
              properties: {
                action: {
                  type: "string",
                  enum: ["create", "update", "get", "history", "list"],
                  description: "The action to perform"
                },
                title: {
                  type: "string",
                  description: "Document title (for create action)"
                },
                content: {
                  type: "string", 
                  description: "Document content (for create/update actions)"
                },
                doc_id: {
                  type: "string",
                  description: "Document UUID (for update/get/history actions)"
                },
                revision_id: {
                  type: "string",
                  description: "Specific revision UUID (optional for get action)"
                },
                author: {
                  type: "string",
                  description: "Author name (optional)"
                },
                notes: {
                  type: "string", 
                  description: "Revision notes (optional for update action)"
                },
                metadata: {
                  type: "object",
                  description: "Document metadata (optional for create action)"
                },
                limit: {
                  type: "number",
                  description: "Number of results to return (for list action, max 100)"
                },
                offset: {
                  type: "number",
                  description: "Number of results to skip (for list action)"
                }
              },
              required: ["action"]
            }
          }
        ]
      };
    });

    // Tool execution
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;
      
      console.error(`[UK] Tool call received: ${name}`, JSON.stringify(args, null, 2));
      
      try {
        // Check connection health before executing
        const health = await this.checkHealth();
        if (!health.healthy) {
          console.error('[UK] Services unhealthy, attempting reconnection...');
          await this.reconnectServices();
          
          // Re-check after reconnection attempt
          const retryHealth = await this.checkHealth();
          if (!retryHealth.healthy) {
            throw new Error('Services are not healthy. Please check connections.');
          }
        }

        // Route to appropriate tool handler
        let result;
        if (name === 'uk_ticket') {
          result = await ticketTools.handleTool(
            name, 
            args, 
            {
              redis: this.redis,
              postgres: this.postgres,
              qdrant: this.qdrant,
              embedding: this.embedding
            }
          );
        } else if (name === 'uk_system_doc') {
          result = await systemDocTools.handleTool(
            name, 
            args, 
            {
              redis: this.redis,
              postgres: this.postgres,
              qdrant: this.qdrant,
              embedding: this.embedding
            }
          );
        } else if (name === 'document') {
          result = await handleDocumentTool(args, {
            documentManager: this.documentManager
          });
        } else {
          throw new Error(`Unknown tool: ${name}`);
        }
        
        console.error(`[UK] Tool call ${name} completed successfully`);
        console.error(`[UK] Result:`, JSON.stringify(result, null, 2));
        
        return result;
      } catch (error) {
        console.error(`[UK] Error executing tool ${name}:`, error);
        console.error(`[UK] Error stack:`, error.stack);
        return {
          content: [
            {
              type: "text",
              text: `Error: ${error.message}`
            }
          ],
          isError: true
        };
      }
    });
  }

  async run() {
    try {
      // Initialize services before starting
      await this.initialize();
      
      // Set up stdio transport
      const transport = new StdioServerTransport();
      
      // Connect server to transport
      await this.server.connect(transport);
      
      console.error('[UK] UnifiedKnowledge MCP server running');
    } catch (error) {
      console.error('[UK] Failed to start server:', error);
      process.exit(1);
    }
  }
}

// Global server instance for cleanup
let globalServer = null;

// Handle graceful shutdown
process.on('SIGINT', async () => {
  console.error('[UK] Shutting down...');
  if (globalServer) {
    if (globalServer.healthCheckInterval) {
      clearInterval(globalServer.healthCheckInterval);
    }
    await globalServer.cleanup();
  }
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.error('[UK] Shutting down...');
  if (globalServer) {
    if (globalServer.healthCheckInterval) {
      clearInterval(globalServer.healthCheckInterval);
    }
    await globalServer.cleanup();
  }
  process.exit(0);
});

// Start the server
globalServer = new UnifiedKnowledgeServer();
globalServer.run().catch(console.error);