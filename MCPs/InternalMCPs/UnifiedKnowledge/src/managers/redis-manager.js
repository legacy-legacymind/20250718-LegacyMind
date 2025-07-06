import { createClient } from 'redis';

export class RedisManager {
  constructor() {
    this.client = null;
    this.isConnected = false;
    this.connectionAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 1000;
  }

  async connect() {
    try {
      if (this.isConnected && this.client) {
        console.log('[Redis] Already connected');
        return true;
      }

      const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
      console.log(`[Redis] Connecting to: ${redisUrl.replace(/:([^@]+)@/, ':****@')}`); // Log URL with masked password
      
      this.client = createClient({
        url: redisUrl,
        socket: {
          reconnectStrategy: (retries) => {
            this.connectionAttempts = retries;
            if (retries > this.maxReconnectAttempts) {
              console.error(`[Redis] Max reconnection attempts (${this.maxReconnectAttempts}) reached`);
              return new Error('Max reconnection attempts reached');
            }
            const delay = Math.min(retries * this.reconnectDelay, 10000);
            console.log(`[Redis] Reconnection attempt ${retries}, waiting ${delay}ms`);
            return delay;
          },
          connectTimeout: 10000,
          keepAlive: 5000
        }
      });

      // Set up event handlers
      this.client.on('error', (err) => {
        console.error('[Redis] Client error:', err.message);
        this.isConnected = false;
      });

      this.client.on('connect', () => {
        console.log('[Redis] Connected to Redis server');
        this.isConnected = true;
        this.connectionAttempts = 0;
      });

      this.client.on('ready', () => {
        console.log('[Redis] Redis client ready for commands');
      });

      this.client.on('reconnecting', () => {
        console.log('[Redis] Attempting to reconnect...');
        this.isConnected = false;
      });

      this.client.on('end', () => {
        console.log('[Redis] Connection closed');
        this.isConnected = false;
      });

      await this.client.connect();
      
      // Test connection with ping
      const pingResult = await this.client.ping();
      console.log('[Redis] Connection test:', pingResult);
      
      return true;
    } catch (error) {
      console.error('[Redis] Connection failed:', error.message);
      this.isConnected = false;
      throw new Error(`Redis connection failed: ${error.message}`);
    }
  }

  async disconnect() {
    if (this.client && this.isConnected) {
      try {
        await this.client.quit();
        console.log('[Redis] Disconnected gracefully');
      } catch (error) {
        console.error('[Redis] Error during disconnect:', error.message);
        await this.client.disconnect();
      }
      this.isConnected = false;
      this.client = null;
    }
  }

  // Ensure connection is active before operations
  async ensureConnected() {
    if (!this.isConnected || !this.client) {
      await this.connect();
    }
    
    // Test connection is still alive
    try {
      await this.client.ping();
    } catch (error) {
      console.log('[Redis] Connection lost, reconnecting...');
      await this.connect();
    }
  }

  // Store ticket with MULTI/EXEC transaction for atomicity
  async storeTicket(ticketId, ticketData) {
    await this.ensureConnected();
    
    try {
      console.log(`[Redis] Starting storeTicket for ticket ID: ${ticketId}`);
      
      const key = `ticket:${ticketId}`;
      const now = new Date().toISOString();
      const timestamp = Date.now();
      
      // Priority scores for sorting
      const priorityScores = { 'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1 };
      const priorityScore = priorityScores[ticketData.priority] || 0;
      
      // Prepare ticket data
      const ticketHash = {
        ticket_id: ticketData.id || ticketData.ticket_id,
        title: ticketData.title || '',
        description: ticketData.description || '',
        status: ticketData.status || 'OPEN',
        priority: ticketData.priority || 'MEDIUM',
        type: ticketData.type || '',
        category: ticketData.category || '',
        system: ticketData.system || '',
        reporter: ticketData.reporter || '',
        assignee: ticketData.assignee || '',
        created_at: ticketData.created_at || now,
        updated_at: now,
        closed_at: ticketData.closed_at || '',
        tags: JSON.stringify(ticketData.tags || []),
        members: JSON.stringify(ticketData.members || []),
        linked_tickets: JSON.stringify(ticketData.linked_tickets || []),
        acceptance_criteria: JSON.stringify(ticketData.acceptance_criteria || []),
        estimated_hours: String(ticketData.estimated_hours || 0),
        resolution: ticketData.resolution || '',
        qdrant_id: ticketData.qdrant_id || '',
        comments: JSON.stringify(ticketData.comments || []),
        history: JSON.stringify(ticketData.history || []),
        links: JSON.stringify(ticketData.links || []),
        metadata: JSON.stringify(ticketData.metadata || {})
      };
      
      console.log(`[Redis] Prepared ticket hash with ${Object.keys(ticketHash).length} fields`);
      console.log(`[Redis] Key: ${key}`);
      console.log(`[Redis] Sample fields - status: ${ticketHash.status}, priority: ${ticketHash.priority}`);
      
      // Get old ticket data to clean up old indexes
      const oldTicket = await this.getTicket(ticketId);
      console.log(`[Redis] Old ticket exists: ${!!oldTicket}`);
      
      // Use MULTI for atomic transaction
      console.log('[Redis] Creating MULTI transaction');
      const multi = this.client.multi();
      
      // Store ticket hash
      console.log('[Redis] Adding hSet command to transaction');
      
      // The node-redis client expects field-value pairs as arguments
      // We'll add each field individually to ensure compatibility
      for (const [field, value] of Object.entries(ticketHash)) {
        multi.hSet(key, field, value);
      }
      console.log(`[Redis] Added ${Object.keys(ticketHash).length} hSet commands to transaction`);
      
      // Clean up old indexes if updating
      if (oldTicket) {
        // Remove from old status index
        if (oldTicket.status) {
          multi.sRem(`index:status:${oldTicket.status.toLowerCase()}`, ticketId);
        }
        // Remove from old assignee index
        if (oldTicket.assignee) {
          multi.sRem(`index:assignee:${oldTicket.assignee.toLowerCase()}`, ticketId);
        }
        // Remove from old type index
        if (oldTicket.type) {
          multi.sRem(`index:type:${oldTicket.type.toLowerCase()}`, ticketId);
        }
        // Remove from old priority index
        if (oldTicket.priority) {
          multi.sRem(`index:priority:${oldTicket.priority.toLowerCase()}`, ticketId);
        }
        // Remove from old tag indexes
        if (oldTicket.tags && oldTicket.tags.length > 0) {
          for (const tag of oldTicket.tags) {
            multi.sRem(`index:tag:${tag.toLowerCase()}`, ticketId);
          }
        }
      }
      
      // Add to new indexes
      if (ticketData.status) {
        const statusKey = `index:status:${ticketData.status.toLowerCase()}`;
        console.log(`[Redis] Adding to status index: ${statusKey}`);
        multi.sAdd(statusKey, ticketId);
      }
      
      if (ticketData.assignee) {
        const assigneeKey = `index:assignee:${ticketData.assignee.toLowerCase()}`;
        console.log(`[Redis] Adding to assignee index: ${assigneeKey}`);
        multi.sAdd(assigneeKey, ticketId);
      }
      
      if (ticketData.reporter) {
        multi.sAdd(`index:reporter:${ticketData.reporter.toLowerCase()}`, ticketId);
      }
      
      if (ticketData.type) {
        multi.sAdd(`index:type:${ticketData.type.toLowerCase()}`, ticketId);
      }
      
      if (ticketData.priority) {
        multi.sAdd(`index:priority:${ticketData.priority.toLowerCase()}`, ticketId);
      }
      
      // Add to tag indexes
      if (ticketData.tags && ticketData.tags.length > 0) {
        for (const tag of ticketData.tags) {
          multi.sAdd(`index:tag:${tag.toLowerCase()}`, ticketId);
        }
      }
      
      // Update sorted sets for ordering
      const createdTimestamp = new Date(ticketData.created_at || now).getTime();
      multi.zAdd('index:created_at', { score: createdTimestamp, value: ticketId });
      multi.zAdd('index:updated_at', { score: timestamp, value: ticketId });
      multi.zAdd('index:priority', { score: priorityScore, value: ticketId });
      
      // Set TTL for closed tickets (24 hours)
      if (['CLOSED', 'CANCELLED'].includes(ticketData.status)) {
        multi.expire(key, 86400);
      } else {
        multi.persist(key);
      }
      
      // Execute transaction
      console.log('[Redis] Preparing to execute transaction...');
      console.log(`[Redis] Transaction queue length: ${multi.queue ? multi.queue.length : 'unknown'}`);
      
      let results;
      try {
        results = await multi.exec();
        console.log(`[Redis] Transaction executed, results:`, results);
        console.log(`[Redis] Number of results: ${results ? results.length : 'null'}`);
      } catch (execError) {
        console.error('[Redis] Transaction execution error:', execError);
        console.error('[Redis] Error stack:', execError.stack);
        throw new Error(`Transaction execution failed: ${execError.message}`);
      }
      
      // Check if results is null (transaction was aborted)
      if (results === null) {
        throw new Error('Transaction was aborted (possibly due to watched keys changing)');
      }
      
      // Check if all operations succeeded
      // In node-redis v4, exec() returns an array of results directly (not [error, result] tuples)
      console.log(`[Redis] Checking ${results.length} operation results...`);
      
      // Log a few sample results for debugging
      if (results.length > 0) {
        console.log('[Redis] Sample operation results:', results.slice(0, 3));
      }
      
      console.log(`[Redis] Ticket ${ticketId} stored successfully`);
      return ticketData;
      
    } catch (error) {
      console.error(`[Redis] Failed to store ticket ${ticketId}:`, error.message);
      throw new Error(`Failed to store ticket: ${error.message}`);
    }
  }

  // Get ticket by ID
  async getTicket(ticketId) {
    await this.ensureConnected();
    
    try {
      const key = `ticket:${ticketId}`;
      const data = await this.client.hGetAll(key);
      
      if (!data || Object.keys(data).length === 0) {
        return null;
      }
      
      // Parse JSON fields
      return {
        id: data.ticket_id,  // Map ticket_id to id for consistency
        ticket_id: data.ticket_id,
        title: data.title,
        description: data.description,
        status: data.status,
        priority: data.priority,
        type: data.type,
        category: data.category,
        system: data.system,
        reporter: data.reporter,
        assignee: data.assignee,
        created_at: data.created_at,
        updated_at: data.updated_at,
        closed_at: data.closed_at || null,
        tags: JSON.parse(data.tags || '[]'),
        members: JSON.parse(data.members || '[]'),
        linked_tickets: JSON.parse(data.linked_tickets || '[]'),
        acceptance_criteria: JSON.parse(data.acceptance_criteria || '[]'),
        estimated_hours: parseInt(data.estimated_hours || '0'),
        resolution: data.resolution,
        qdrant_id: data.qdrant_id,
        comments: JSON.parse(data.comments || '[]'),
        history: JSON.parse(data.history || '[]'),
        links: JSON.parse(data.links || '[]'),
        metadata: JSON.parse(data.metadata || '{}')
      };
    } catch (error) {
      console.error(`[Redis] Failed to get ticket ${ticketId}:`, error.message);
      throw new Error(`Failed to get ticket: ${error.message}`);
    }
  }

  // Find tickets by multiple criteria using SINTER
  async findTicketsBy(filters = {}) {
    await this.ensureConnected();
    
    try {
      const setKeys = [];
      
      // Build set keys from filters
      if (filters.status) {
        setKeys.push(`index:status:${filters.status.toLowerCase()}`);
      }
      
      if (filters.assignee) {
        setKeys.push(`index:assignee:${filters.assignee.toLowerCase()}`);
      }
      
      if (filters.reporter) {
        setKeys.push(`index:reporter:${filters.reporter.toLowerCase()}`);
      }
      
      if (filters.type) {
        setKeys.push(`index:type:${filters.type.toLowerCase()}`);
      }
      
      if (filters.priority) {
        setKeys.push(`index:priority:${filters.priority.toLowerCase()}`);
      }
      
      if (filters.tags && Array.isArray(filters.tags)) {
        for (const tag of filters.tags) {
          setKeys.push(`index:tag:${tag.toLowerCase()}`);
        }
      }
      
      let ticketIds = [];
      
      if (setKeys.length === 0) {
        // No filters - get all tickets from created_at index
        ticketIds = await this.client.zRange('index:created_at', 0, -1, { REV: true });
      } else if (setKeys.length === 1) {
        // Single filter - direct set members
        ticketIds = await this.client.sMembers(setKeys[0]);
      } else {
        // Multiple filters - use SINTER for intersection
        ticketIds = await this.client.sInter(setKeys);
      }
      
      if (ticketIds.length === 0) {
        return [];
      }
      
      // Batch fetch tickets using multi
      const multi = this.client.multi();
      for (const ticketId of ticketIds) {
        multi.hGetAll(`ticket:${ticketId}`);
      }
      
      const results = await multi.exec();
      const tickets = [];
      
      // Process results
      // In node-redis v4, multi.exec() returns an array of results directly
      for (let i = 0; i < results.length; i++) {
        const data = results[i];
        if (data && Object.keys(data).length > 0) {
          tickets.push({
            ticket_id: data.ticket_id,
            title: data.title,
            description: data.description,
            status: data.status,
            priority: data.priority,
            type: data.type,
            category: data.category,
            system: data.system,
            reporter: data.reporter,
            assignee: data.assignee,
            created_at: data.created_at,
            updated_at: data.updated_at,
            tags: JSON.parse(data.tags || '[]'),
            members: JSON.parse(data.members || '[]'),
            linked_tickets: JSON.parse(data.linked_tickets || '[]'),
            acceptance_criteria: JSON.parse(data.acceptance_criteria || '[]'),
            estimated_hours: parseInt(data.estimated_hours || '0'),
            resolution: data.resolution,
            qdrant_id: data.qdrant_id
          });
        }
      }
      
      // Sort results
      const sortBy = filters.sortBy || 'priority';
      const sortOrder = filters.sortOrder || 'desc';
      
      tickets.sort((a, b) => {
        let compareValue = 0;
        
        switch (sortBy) {
          case 'priority':
            const priorityOrder = { 'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1 };
            compareValue = (priorityOrder[b.priority] || 0) - (priorityOrder[a.priority] || 0);
            break;
          case 'created_at':
            compareValue = new Date(b.created_at) - new Date(a.created_at);
            break;
          case 'updated_at':
            compareValue = new Date(b.updated_at) - new Date(a.updated_at);
            break;
          default:
            compareValue = 0;
        }
        
        return sortOrder === 'asc' ? -compareValue : compareValue;
      });
      
      return tickets;
      
    } catch (error) {
      console.error('[Redis] Failed to find tickets:', error.message);
      throw new Error(`Failed to find tickets: ${error.message}`);
    }
  }

  // Delete ticket with transaction
  async deleteTicket(ticketId) {
    await this.ensureConnected();
    
    try {
      const key = `ticket:${ticketId}`;
      
      // Get ticket data first for index cleanup
      const ticket = await this.getTicket(ticketId);
      if (!ticket) {
        console.log(`[Redis] Ticket ${ticketId} not found for deletion`);
        return true;
      }
      
      // Use MULTI for atomic deletion
      const multi = this.client.multi();
      
      // Remove from all indexes
      if (ticket.status) {
        multi.sRem(`index:status:${ticket.status.toLowerCase()}`, ticketId);
      }
      
      if (ticket.assignee) {
        multi.sRem(`index:assignee:${ticket.assignee.toLowerCase()}`, ticketId);
      }
      
      if (ticket.reporter) {
        multi.sRem(`index:reporter:${ticket.reporter.toLowerCase()}`, ticketId);
      }
      
      if (ticket.type) {
        multi.sRem(`index:type:${ticket.type.toLowerCase()}`, ticketId);
      }
      
      if (ticket.priority) {
        multi.sRem(`index:priority:${ticket.priority.toLowerCase()}`, ticketId);
      }
      
      // Remove from tag indexes
      if (ticket.tags && ticket.tags.length > 0) {
        for (const tag of ticket.tags) {
          multi.sRem(`index:tag:${tag.toLowerCase()}`, ticketId);
        }
      }
      
      // Remove from sorted sets
      multi.zRem('index:created_at', ticketId);
      multi.zRem('index:updated_at', ticketId);
      multi.zRem('index:priority', ticketId);
      
      // Delete the ticket hash
      multi.del(key);
      
      // Execute transaction
      await multi.exec();
      
      console.log(`[Redis] Ticket ${ticketId} deleted successfully`);
      return true;
      
    } catch (error) {
      console.error(`[Redis] Failed to delete ticket ${ticketId}:`, error.message);
      throw new Error(`Failed to delete ticket: ${error.message}`);
    }
  }

  // Get all active tickets (optimized with multi)
  async getAllActiveTickets() {
    await this.ensureConnected();
    
    try {
      // Use SINTER to get active tickets (all except closed/cancelled)
      const closedIds = await this.client.sMembers('index:status:closed');
      const cancelledIds = await this.client.sMembers('index:status:cancelled');
      const excludeIds = new Set([...closedIds, ...cancelledIds]);
      
      // Get all ticket IDs sorted by creation date
      const allIds = await this.client.zRange('index:created_at', 0, -1, { REV: true });
      const activeIds = allIds.filter(id => !excludeIds.has(id));
      
      if (activeIds.length === 0) {
        return [];
      }
      
      // Batch fetch using multi
      const multi = this.client.multi();
      for (const ticketId of activeIds) {
        multi.hGetAll(`ticket:${ticketId}`);
      }
      
      const results = await multi.exec();
      const tickets = [];
      
      for (let i = 0; i < results.length; i++) {
        const data = results[i];
        if (data && Object.keys(data).length > 0) {
          tickets.push({
            ticket_id: data.ticket_id,
            title: data.title,
            description: data.description,
            status: data.status,
            priority: data.priority,
            type: data.type,
            category: data.category,
            system: data.system,
            reporter: data.reporter,
            assignee: data.assignee,
            created_at: data.created_at,
            updated_at: data.updated_at,
            tags: JSON.parse(data.tags || '[]'),
            members: JSON.parse(data.members || '[]'),
            linked_tickets: JSON.parse(data.linked_tickets || '[]'),
            acceptance_criteria: JSON.parse(data.acceptance_criteria || '[]'),
            estimated_hours: parseInt(data.estimated_hours || '0'),
            resolution: data.resolution,
            qdrant_id: data.qdrant_id
          });
        }
      }
      
      return tickets;
      
    } catch (error) {
      console.error('[Redis] Failed to get active tickets:', error.message);
      throw new Error(`Failed to get active tickets: ${error.message}`);
    }
  }

  // Get all closed tickets (optimized with multi)
  async getAllClosedTickets() {
    await this.ensureConnected();
    
    try {
      // Get closed and cancelled ticket IDs
      const [closedIds, cancelledIds] = await Promise.all([
        this.client.sMembers('index:status:closed'),
        this.client.sMembers('index:status:cancelled')
      ]);
      
      const allClosedIds = [...new Set([...closedIds, ...cancelledIds])];
      
      if (allClosedIds.length === 0) {
        return [];
      }
      
      // Batch fetch using multi
      const multi = this.client.multi();
      for (const ticketId of allClosedIds) {
        multi.hGetAll(`ticket:${ticketId}`);
      }
      
      const results = await multi.exec();
      const tickets = [];
      
      for (let i = 0; i < results.length; i++) {
        const data = results[i];
        if (data && Object.keys(data).length > 0) {
          tickets.push({
            ticket_id: data.ticket_id,
            title: data.title,
            description: data.description,
            status: data.status,
            priority: data.priority,
            type: data.type,
            category: data.category,
            system: data.system,
            reporter: data.reporter,
            assignee: data.assignee,
            created_at: data.created_at,
            updated_at: data.updated_at,
            tags: JSON.parse(data.tags || '[]'),
            members: JSON.parse(data.members || '[]'),
            linked_tickets: JSON.parse(data.linked_tickets || '[]'),
            acceptance_criteria: JSON.parse(data.acceptance_criteria || '[]'),
            estimated_hours: parseInt(data.estimated_hours || '0'),
            resolution: data.resolution,
            qdrant_id: data.qdrant_id
          });
        }
      }
      
      // Sort by updated_at descending
      tickets.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
      
      return tickets;
      
    } catch (error) {
      console.error('[Redis] Failed to get closed tickets:', error.message);
      throw new Error(`Failed to get closed tickets: ${error.message}`);
    }
  }

  // Get tickets by status (convenience method)
  async getTicketsByStatus(status) {
    return this.findTicketsBy({ status });
  }
  
  // Get tickets by assignee (convenience method)
  async getTicketsByAssignee(assignee) {
    return this.findTicketsBy({ assignee });
  }
  
  // Get tickets by tag (convenience method)
  async getTicketsByTag(tag) {
    return this.findTicketsBy({ tags: [tag] });
  }
  
  // Get recent tickets
  async getRecentTickets(limit = 10) {
    await this.ensureConnected();
    
    try {
      const ticketIds = await this.client.zRange('index:created_at', -limit, -1, { REV: true });
      
      if (ticketIds.length === 0) {
        return [];
      }
      
      // Batch fetch using multi
      const multi = this.client.multi();
      for (const ticketId of ticketIds) {
        multi.hGetAll(`ticket:${ticketId}`);
      }
      
      const results = await multi.exec();
      const tickets = [];
      
      for (let i = 0; i < results.length; i++) {
        const data = results[i];
        if (data && Object.keys(data).length > 0) {
          tickets.push({
            ticket_id: data.ticket_id,
            title: data.title,
            description: data.description,
            status: data.status,
            priority: data.priority,
            type: data.type,
            category: data.category,
            system: data.system,
            reporter: data.reporter,
            assignee: data.assignee,
            created_at: data.created_at,
            updated_at: data.updated_at,
            tags: JSON.parse(data.tags || '[]'),
            members: JSON.parse(data.members || '[]'),
            linked_tickets: JSON.parse(data.linked_tickets || '[]'),
            acceptance_criteria: JSON.parse(data.acceptance_criteria || '[]'),
            estimated_hours: parseInt(data.estimated_hours || '0'),
            resolution: data.resolution,
            qdrant_id: data.qdrant_id
          });
        }
      }
      
      return tickets;
      
    } catch (error) {
      console.error('[Redis] Failed to get recent tickets:', error.message);
      throw new Error(`Failed to get recent tickets: ${error.message}`);
    }
  }
  
  // Get tickets by priority (convenience method)
  async getTicketsByPriority(priority) {
    return this.findTicketsBy({ priority });
  }

  // System documentation operations (Phase 2)
  async storeSystemDoc(docId, docData) {
    await this.ensureConnected();
    
    try {
      const key = `uk:doc:${docId}`;
      const serialized = JSON.stringify(docData);
      const timestamp = Date.now();
      
      // Use MULTI for atomic operation
      const multi = this.client.multi();
      
      multi.hSet(key, {
        data: serialized,
        updated_at: new Date().toISOString()
      });
      
      // Add to category index
      multi.zAdd(`uk:docs:${docData.category}`, { score: timestamp, value: docId });
      
      await multi.exec();
      
      console.log(`[Redis] System doc ${docId} stored successfully`);
      return docData;
      
    } catch (error) {
      console.error(`[Redis] Failed to store system doc ${docId}:`, error.message);
      throw new Error(`Failed to store system doc: ${error.message}`);
    }
  }

  async getSystemDoc(docId) {
    await this.ensureConnected();
    
    try {
      const key = `uk:doc:${docId}`;
      const data = await this.client.hGet(key, 'data');
      
      if (!data) {
        return null;
      }
      
      return JSON.parse(data);
      
    } catch (error) {
      console.error(`[Redis] Failed to get system doc ${docId}:`, error.message);
      throw new Error(`Failed to get system doc: ${error.message}`);
    }
  }

  // Health check
  async healthCheck() {
    try {
      if (!this.isConnected || !this.client) {
        return { 
          status: 'unhealthy', 
          message: 'Not connected',
          timestamp: new Date().toISOString() 
        };
      }
      
      const start = Date.now();
      await this.client.ping();
      const latency = Date.now() - start;
      
      return { 
        status: 'healthy', 
        latency: `${latency}ms`,
        connected: this.isConnected,
        timestamp: new Date().toISOString() 
      };
    } catch (error) {
      return { 
        status: 'unhealthy', 
        error: error.message,
        connected: false,
        timestamp: new Date().toISOString() 
      };
    }
  }

  // Get all tickets (convenience method)
  async getAllTickets() {
    await this.ensureConnected();
    
    try {
      // Get all ticket IDs from the created_at index
      const ticketIds = await this.client.zRange('index:created_at', 0, -1, { REV: true });
      
      if (ticketIds.length === 0) {
        return [];
      }
      
      // Batch fetch using multi
      const multi = this.client.multi();
      for (const ticketId of ticketIds) {
        multi.hGetAll(`ticket:${ticketId}`);
      }
      
      const results = await multi.exec();
      const tickets = [];
      
      for (let i = 0; i < results.length; i++) {
        const data = results[i];
        if (data && Object.keys(data).length > 0) {
          tickets.push({
            id: data.ticket_id,  // Map ticket_id to id for consistency
            ticket_id: data.ticket_id,
            title: data.title,
            description: data.description,
            status: data.status,
            priority: data.priority,
            type: data.type,
            category: data.category,
            system: data.system,
            reporter: data.reporter,
            assignee: data.assignee,
            created_at: data.created_at,
            updated_at: data.updated_at,
            tags: JSON.parse(data.tags || '[]'),
            members: JSON.parse(data.members || '[]'),
            linked_tickets: JSON.parse(data.linked_tickets || '[]'),
            acceptance_criteria: JSON.parse(data.acceptance_criteria || '[]'),
            estimated_hours: parseInt(data.estimated_hours || '0'),
            resolution: data.resolution,
            qdrant_id: data.qdrant_id,
            // Include these fields that ticket-tools expects
            comments: JSON.parse(data.comments || '[]'),
            history: JSON.parse(data.history || '[]'),
            links: JSON.parse(data.links || '[]'),
            closed_at: data.closed_at || null,
            metadata: JSON.parse(data.metadata || '{}')
          });
        }
      }
      
      return tickets;
      
    } catch (error) {
      console.error('[Redis] Failed to get all tickets:', error.message);
      throw new Error(`Failed to get all tickets: ${error.message}`);
    }
  }

  // Get connection status
  getConnectionStatus() {
    return {
      connected: this.isConnected,
      attempts: this.connectionAttempts,
      maxAttempts: this.maxReconnectAttempts
    };
  }
}