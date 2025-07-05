import { logger } from '../utils/logger.js';
import { validateInput } from '../shared/validators.js';

/**
 * RememberTool - A separate tool for managing persistent memory
 * 
 * This tool provides create/search operations for three memory types:
 * - Identity: Who the instance is and its characteristics
 * - Context: Current working context and environment
 * - Curiosity: What the instance is curious about or exploring
 * 
 * All data is stored in Redis with instance-specific namespacing
 */
export class RememberTool {
  constructor(redis, sessionManager) {
    this.redis = redis;
    this.sessionManager = sessionManager;
    this.memoryTypes = ['identity', 'context', 'curiosity'];
  }

  /**
   * Main entry point for the remember tool
   */
  async execute(args) {
    const { action, memory_type, content, query, options = {} } = args;

    logger.info(`RememberTool executing action: ${action}, type: ${memory_type}`);

    try {
      switch (action) {
        case 'create':
          return await this.createMemory({ memory_type, content, options });
        
        case 'search':
          return await this.searchMemory({ memory_type, query, options });
        
        case 'list':
          return await this.listMemories({ memory_type, options });
        
        case 'get':
          return await this.getMemory({ memory_type, id: query, options });
        
        case 'update':
          return await this.updateMemory({ memory_type, id: query, content, options });
        
        case 'delete':
          return await this.deleteMemory({ memory_type, id: query, options });
        
        case 'help':
          return this.getHelp();
        
        default:
          throw new Error(`Unknown action: ${action}`);
      }
    } catch (error) {
      logger.error(`RememberTool error in action '${action}'`, { error: error.message });
      throw error;
    }
  }

  /**
   * Create a new memory entry
   */
  async createMemory({ memory_type, content, options }) {
    // Validate inputs
    if (!this.memoryTypes.includes(memory_type)) {
      throw new Error(`Invalid memory type. Must be one of: ${this.memoryTypes.join(', ')}`);
    }

    if (!content || typeof content !== 'string' || content.trim() === '') {
      throw new Error('Content must be a non-empty string');
    }

    // Get current instance
    const instanceId = await this.getCurrentInstanceId();
    
    // Generate unique ID for this memory entry
    const memoryId = this.generateMemoryId();
    const timestamp = new Date().toISOString();
    
    // Create memory object
    const memoryData = {
      id: memoryId,
      type: memory_type,
      content: content.trim(),
      tags: Array.isArray(options.tags) ? options.tags : [],
      metadata: options.metadata || {},
      created_at: timestamp,
      updated_at: timestamp,
      instance_id: instanceId
    };

    try {
      // Store in Redis using appropriate data structure
      const pipeline = this.redis.pipeline();
      
      // 1. Store full memory object in hash
      const memoryKey = `${instanceId}:memory:${memory_type}:${memoryId}`;
      pipeline.hset(memoryKey, this.flattenForRedis(memoryData));
      pipeline.expire(memoryKey, 90 * 24 * 60 * 60); // 90 days
      
      // 2. Add to memory type index (sorted set by timestamp)
      const indexKey = `${instanceId}:memory_index:${memory_type}`;
      pipeline.zadd(indexKey, Date.now(), memoryId);
      
      // 3. Add to searchable content (for text search)
      const searchKey = `${instanceId}:memory_search:${memory_type}`;
      const searchableContent = this.createSearchableContent(memoryData);
      pipeline.hset(searchKey, memoryId, searchableContent);
      
      // 4. Update tags index
      if (memoryData.tags.length > 0) {
        for (const tag of memoryData.tags) {
          const tagKey = `${instanceId}:memory_tags:${memory_type}:${tag}`;
          pipeline.sadd(tagKey, memoryId);
          pipeline.expire(tagKey, 90 * 24 * 60 * 60);
        }
      }
      
      // Execute pipeline
      await pipeline.exec();
      
      logger.info(`Memory created: ${memory_type}/${memoryId} for instance ${instanceId}`);
      
      return {
        success: true,
        memory: {
          id: memoryId,
          type: memory_type,
          preview: content.substring(0, 100) + (content.length > 100 ? '...' : ''),
          created_at: timestamp
        },
        message: `${memory_type} memory created successfully`
      };
      
    } catch (error) {
      logger.error('Failed to create memory', { error: error.message, memory_type, instanceId });
      throw new Error(`Failed to create memory: ${error.message}`);
    }
  }

  /**
   * Search memories by query
   */
  async searchMemory({ memory_type, query, options }) {
    if (!query || typeof query !== 'string' || query.trim() === '') {
      throw new Error('Query must be a non-empty string');
    }

    const instanceId = await this.getCurrentInstanceId();
    const limit = options.limit || 10;
    const offset = options.offset || 0;

    try {
      // Get all memory IDs for this type
      const indexKey = `${instanceId}:memory_index:${memory_type}`;
      const memoryIds = await this.redis.zrevrange(indexKey, offset, offset + limit - 1);
      
      if (memoryIds.length === 0) {
        return {
          results: [],
          total: 0,
          query,
          memory_type
        };
      }

      // Search through memories
      const searchKey = `${instanceId}:memory_search:${memory_type}`;
      const results = [];
      const queryLower = query.toLowerCase();
      
      for (const memoryId of memoryIds) {
        const searchContent = await this.redis.hget(searchKey, memoryId);
        if (searchContent && searchContent.toLowerCase().includes(queryLower)) {
          // Get full memory data
          const memoryKey = `${instanceId}:memory:${memory_type}:${memoryId}`;
          const memoryData = await this.redis.hgetall(memoryKey);
          
          if (memoryData && Object.keys(memoryData).length > 0) {
            results.push(this.parseMemoryData(memoryData));
          }
        }
      }

      // Also search by tags if provided
      if (options.tags && Array.isArray(options.tags)) {
        for (const tag of options.tags) {
          const tagKey = `${instanceId}:memory_tags:${memory_type}:${tag}`;
          const taggedIds = await this.redis.smembers(tagKey);
          
          for (const memoryId of taggedIds) {
            if (!results.find(r => r.id === memoryId)) {
              const memoryKey = `${instanceId}:memory:${memory_type}:${memoryId}`;
              const memoryData = await this.redis.hgetall(memoryKey);
              
              if (memoryData && Object.keys(memoryData).length > 0) {
                results.push(this.parseMemoryData(memoryData));
              }
            }
          }
        }
      }

      return {
        results: results.slice(0, limit),
        total: results.length,
        query,
        memory_type,
        instance_id: instanceId
      };

    } catch (error) {
      logger.error('Failed to search memories', { error: error.message, memory_type, query });
      throw new Error(`Failed to search memories: ${error.message}`);
    }
  }

  /**
   * List all memories of a specific type
   */
  async listMemories({ memory_type, options }) {
    const instanceId = await this.getCurrentInstanceId();
    const limit = options.limit || 10;
    const offset = options.offset || 0;

    try {
      const indexKey = `${instanceId}:memory_index:${memory_type}`;
      const memoryIds = await this.redis.zrevrange(indexKey, offset, offset + limit - 1);
      const total = await this.redis.zcard(indexKey);
      
      const memories = [];
      for (const memoryId of memoryIds) {
        const memoryKey = `${instanceId}:memory:${memory_type}:${memoryId}`;
        const memoryData = await this.redis.hgetall(memoryKey);
        
        if (memoryData && Object.keys(memoryData).length > 0) {
          memories.push(this.parseMemoryData(memoryData));
        }
      }

      return {
        memories,
        total,
        memory_type,
        limit,
        offset,
        instance_id: instanceId
      };

    } catch (error) {
      logger.error('Failed to list memories', { error: error.message, memory_type });
      throw new Error(`Failed to list memories: ${error.message}`);
    }
  }

  /**
   * Get a specific memory by ID
   */
  async getMemory({ memory_type, id, options }) {
    if (!id || typeof id !== 'string') {
      throw new Error('Memory ID is required');
    }

    const instanceId = await this.getCurrentInstanceId();
    
    try {
      const memoryKey = `${instanceId}:memory:${memory_type}:${id}`;
      const memoryData = await this.redis.hgetall(memoryKey);
      
      if (!memoryData || Object.keys(memoryData).length === 0) {
        throw new Error(`Memory not found: ${memory_type}/${id}`);
      }

      return {
        memory: this.parseMemoryData(memoryData),
        instance_id: instanceId
      };

    } catch (error) {
      logger.error('Failed to get memory', { error: error.message, memory_type, id });
      throw new Error(`Failed to get memory: ${error.message}`);
    }
  }

  /**
   * Update an existing memory
   */
  async updateMemory({ memory_type, id, content, options }) {
    if (!id || typeof id !== 'string') {
      throw new Error('Memory ID is required');
    }

    if (!content || typeof content !== 'string' || content.trim() === '') {
      throw new Error('Content must be a non-empty string');
    }

    const instanceId = await this.getCurrentInstanceId();
    
    try {
      const memoryKey = `${instanceId}:memory:${memory_type}:${id}`;
      const exists = await this.redis.exists(memoryKey);
      
      if (!exists) {
        throw new Error(`Memory not found: ${memory_type}/${id}`);
      }

      // Get existing memory
      const existingData = await this.redis.hgetall(memoryKey);
      const existingMemory = this.parseMemoryData(existingData);

      // Update memory
      const updatedMemory = {
        ...existingMemory,
        content: content.trim(),
        updated_at: new Date().toISOString(),
        tags: options.tags || existingMemory.tags,
        metadata: { ...existingMemory.metadata, ...options.metadata }
      };

      // Update in Redis
      const pipeline = this.redis.pipeline();
      
      // Update memory hash
      pipeline.hset(memoryKey, this.flattenForRedis(updatedMemory));
      
      // Update search index
      const searchKey = `${instanceId}:memory_search:${memory_type}`;
      const searchableContent = this.createSearchableContent(updatedMemory);
      pipeline.hset(searchKey, id, searchableContent);
      
      // Update tags
      if (options.tags) {
        // Remove from old tags
        for (const oldTag of existingMemory.tags) {
          const tagKey = `${instanceId}:memory_tags:${memory_type}:${oldTag}`;
          pipeline.srem(tagKey, id);
        }
        // Add to new tags
        for (const newTag of options.tags) {
          const tagKey = `${instanceId}:memory_tags:${memory_type}:${newTag}`;
          pipeline.sadd(tagKey, id);
        }
      }
      
      await pipeline.exec();
      
      logger.info(`Memory updated: ${memory_type}/${id}`);
      
      return {
        success: true,
        memory: {
          id,
          type: memory_type,
          preview: content.substring(0, 100) + (content.length > 100 ? '...' : ''),
          updated_at: updatedMemory.updated_at
        },
        message: `${memory_type} memory updated successfully`
      };

    } catch (error) {
      logger.error('Failed to update memory', { error: error.message, memory_type, id });
      throw new Error(`Failed to update memory: ${error.message}`);
    }
  }

  /**
   * Delete a memory
   */
  async deleteMemory({ memory_type, id, options }) {
    if (!id || typeof id !== 'string') {
      throw new Error('Memory ID is required');
    }

    const instanceId = await this.getCurrentInstanceId();
    
    try {
      const memoryKey = `${instanceId}:memory:${memory_type}:${id}`;
      const memoryData = await this.redis.hgetall(memoryKey);
      
      if (!memoryData || Object.keys(memoryData).length === 0) {
        throw new Error(`Memory not found: ${memory_type}/${id}`);
      }

      const memory = this.parseMemoryData(memoryData);
      
      // Delete from Redis
      const pipeline = this.redis.pipeline();
      
      // Delete memory hash
      pipeline.del(memoryKey);
      
      // Remove from index
      const indexKey = `${instanceId}:memory_index:${memory_type}`;
      pipeline.zrem(indexKey, id);
      
      // Remove from search index
      const searchKey = `${instanceId}:memory_search:${memory_type}`;
      pipeline.hdel(searchKey, id);
      
      // Remove from tags
      for (const tag of memory.tags) {
        const tagKey = `${instanceId}:memory_tags:${memory_type}:${tag}`;
        pipeline.srem(tagKey, id);
      }
      
      await pipeline.exec();
      
      logger.info(`Memory deleted: ${memory_type}/${id}`);
      
      return {
        success: true,
        deleted: {
          id,
          type: memory_type
        },
        message: `${memory_type} memory deleted successfully`
      };

    } catch (error) {
      logger.error('Failed to delete memory', { error: error.message, memory_type, id });
      throw new Error(`Failed to delete memory: ${error.message}`);
    }
  }

  /**
   * Get help information for the remember tool
   */
  getHelp() {
    return {
      tool: 'ui_remember',
      description: 'Manage persistent memory for identity, context, and curiosity',
      actions: {
        create: {
          description: 'Create a new memory entry',
          parameters: {
            memory_type: 'Type of memory (identity, context, or curiosity)',
            content: 'The content to remember',
            options: {
              tags: 'Array of tags for categorization',
              metadata: 'Additional metadata object'
            }
          },
          example: {
            action: 'create',
            memory_type: 'identity',
            content: 'I am CCI, the Intelligence Specialist focused on analysis and research',
            options: {
              tags: ['role', 'specialization'],
              metadata: { version: '1.0' }
            }
          }
        },
        search: {
          description: 'Search memories by query',
          parameters: {
            memory_type: 'Type of memory to search (or omit for all)',
            query: 'Search query string',
            options: {
              tags: 'Filter by tags',
              limit: 'Maximum results (default: 10)',
              offset: 'Pagination offset'
            }
          },
          example: {
            action: 'search',
            memory_type: 'context',
            query: 'MCP development',
            options: { limit: 5 }
          }
        },
        list: {
          description: 'List all memories of a specific type',
          parameters: {
            memory_type: 'Type of memory to list',
            options: {
              limit: 'Maximum results (default: 10)',
              offset: 'Pagination offset'
            }
          }
        },
        get: {
          description: 'Get a specific memory by ID',
          parameters: {
            memory_type: 'Type of memory',
            query: 'Memory ID'
          }
        },
        update: {
          description: 'Update an existing memory',
          parameters: {
            memory_type: 'Type of memory',
            query: 'Memory ID',
            content: 'New content',
            options: {
              tags: 'New tags (optional)',
              metadata: 'Additional metadata to merge'
            }
          }
        },
        delete: {
          description: 'Delete a memory',
          parameters: {
            memory_type: 'Type of memory',
            query: 'Memory ID'
          }
        }
      },
      memory_types: {
        identity: 'Who the instance is, its role, capabilities, and characteristics',
        context: 'Current working context, project information, and environment',
        curiosity: 'What the instance is curious about, research interests, and explorations'
      },
      philosophy: 'Simple, persistent memory management with Redis-backed storage'
    };
  }

  // Helper methods

  /**
   * Get the current instance ID
   */
  async getCurrentInstanceId() {
    // First check if we have a current instance in the intelligence context
    if (this.currentInstanceId) {
      return this.currentInstanceId;
    }

    // Otherwise get from active session
    const session = await this.sessionManager.getActiveSession();
    if (!session || !session.instanceId) {
      throw new Error('No active instance found. Please check in first.');
    }
    return session.instanceId;
  }

  /**
   * Set the current instance ID (used by UnifiedIntelligence)
   */
  setCurrentInstanceId(instanceId) {
    this.currentInstanceId = instanceId;
  }

  /**
   * Generate a unique memory ID
   */
  generateMemoryId() {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substring(2, 8);
    return `${timestamp}-${random}`;
  }

  /**
   * Flatten memory object for Redis hash storage
   */
  flattenForRedis(memoryData) {
    return {
      id: memoryData.id,
      type: memoryData.type,
      content: memoryData.content,
      tags: JSON.stringify(memoryData.tags),
      metadata: JSON.stringify(memoryData.metadata),
      created_at: memoryData.created_at,
      updated_at: memoryData.updated_at,
      instance_id: memoryData.instance_id
    };
  }

  /**
   * Parse memory data from Redis
   */
  parseMemoryData(redisData) {
    return {
      id: redisData.id,
      type: redisData.type,
      content: redisData.content,
      tags: JSON.parse(redisData.tags || '[]'),
      metadata: JSON.parse(redisData.metadata || '{}'),
      created_at: redisData.created_at,
      updated_at: redisData.updated_at,
      instance_id: redisData.instance_id
    };
  }

  /**
   * Create searchable content from memory data
   */
  createSearchableContent(memoryData) {
    const parts = [
      memoryData.content,
      memoryData.tags.join(' '),
      JSON.stringify(memoryData.metadata)
    ];
    return parts.join(' ').toLowerCase();
  }
}