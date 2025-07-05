import { v4 as uuidv4 } from 'uuid';
import {
  validateCreateTicket,
  validateUpdateTicket,
  validateSearchTickets,
  validateListTickets,
  validateGetTicket,
  validateCloseTicket,
  validateAssignTicket,
  validateAddMember,
  validateLinkTickets,
  TicketStatus,
  TicketPriority,
  TicketType,
  LinkType
} from '../shared/validators.js';

export const ticketTools = {
  getToolDefinitions() {
    return [
      {
        name: "uk_ticket",
        description: "Manage tickets in UnifiedKnowledge - create, update, search, and organize project tickets",
        inputSchema: {
          type: "object",
          properties: {
            action: {
              type: "string",
              enum: ["create", "update", "get", "search", "list", "close", "assign", "add_member", "link_tickets"],
              description: "Action to perform on tickets"
            },
            // Create ticket fields
            title: {
              type: "string",
              description: "Ticket title (for create)"
            },
            description: {
              type: "string",
              description: "Detailed description of the ticket (for create/update)"
            },
            priority: {
              type: "string",
              enum: ["low", "medium", "high", "urgent"],
              description: "Ticket priority level (for create/update)"
            },
            type: {
              type: "string",
              enum: ["bug", "feature", "question", "task", "improvement"],
              description: "Type of ticket (for create/update)"
            },
            tags: {
              type: "array",
              items: { type: "string" },
              description: "Tags for categorization (for create/update)"
            },
            assignee: {
              type: "string",
              description: "Person assigned to the ticket (for create/update/assign)"
            },
            metadata: {
              type: "object",
              description: "Additional metadata (for create/update)"
            },
            // Update ticket fields
            ticket_id: {
              type: "string",
              description: "Ticket ID (for get/update/close/assign/add_member/link_tickets)"
            },
            updates: {
              type: "object",
              description: "Updates to apply to the ticket (for update)"
            },
            // Search/list fields
            query: {
              type: "string",
              description: "Search query (for search)"
            },
            filters: {
              type: "object",
              description: "Search filters (for search/list)"
            },
            sort_by: {
              type: "string",
              enum: ["created_at", "updated_at", "priority", "status"],
              description: "Sort field (for search/list)"
            },
            sort_order: {
              type: "string",
              enum: ["asc", "desc"],
              description: "Sort order (for search/list)"
            },
            limit: {
              type: "number",
              description: "Number of results to return (for search/list)"
            },
            offset: {
              type: "number",
              description: "Number of results to skip (for search/list)"
            },
            // Close ticket fields
            resolution: {
              type: "string",
              description: "Resolution notes (for close)"
            },
            // Member fields
            member: {
              type: "string",
              description: "Member name (for add_member)"
            },
            role: {
              type: "string",
              enum: ["viewer", "contributor", "owner"],
              description: "Member role (for add_member)"
            },
            notify: {
              type: "boolean",
              description: "Whether to notify (for assign/add_member)"
            },
            // Link tickets fields
            source_ticket_id: {
              type: "string",
              description: "Source ticket ID (for link_tickets)"
            },
            target_ticket_id: {
              type: "string",
              description: "Target ticket ID (for link_tickets)"
            },
            link_type: {
              type: "string",
              enum: ["blocks", "blocked_by", "relates_to", "duplicates", "parent", "child"],
              description: "Type of link relationship (for link_tickets)"
            },
            // Get ticket options
            include_history: {
              type: "boolean",
              description: "Include ticket history (for get)"
            },
            include_comments: {
              type: "boolean",
              description: "Include ticket comments (for get)"
            },
            include_links: {
              type: "boolean",
              description: "Include ticket links (for get)"
            }
          },
          required: ["action"]
        }
      }
    ];
  },

  async handleTool(toolName, args, services) {
    if (toolName !== 'uk_ticket') {
      throw new Error(`Unknown tool: ${toolName}`);
    }
    
    const { action } = args;
    
    try {
      switch (action) {
        case 'create':
          return await this.createTicket(args, services);
        case 'update':
          return await this.updateTicket(args, services);
        case 'get':
          return await this.getTicket(args, services);
        case 'search':
          return await this.searchTickets(args, services);
        case 'list':
          return await this.listTickets(args, services);
        case 'close':
          return await this.closeTicket(args, services);
        case 'assign':
          return await this.assignTicket(args, services);
        case 'add_member':
          return await this.addMember(args, services);
        case 'link_tickets':
          return await this.linkTickets(args, services);
        default:
          throw new Error(`Unknown action: ${action}`);
      }
    } catch (error) {
      console.error(`[TicketTools] Error in ${action}:`, error);
      
      // Format validation errors nicely
      if (error.errors) {
        const validationErrors = error.errors.map(err => 
          `${err.path.join('.')}: ${err.message}`
        ).join(', ');
        
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: false,
                error: `Validation failed: ${validationErrors}`,
                code: 'VALIDATION_ERROR',
                details: error.errors
              }, null, 2)
            }
          ]
        };
      }
      
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              success: false,
              error: error.message,
              code: error.code || 'UNKNOWN_ERROR'
            }, null, 2)
          }
        ]
      };
    }
  },

  async createTicket(args, services) {
    const { redis, postgres, qdrant, embedding } = services;
    
    // Extract fields for validation
    const ticketData = {
      title: args.title,
      description: args.description,
      priority: args.priority,
      type: args.type,
      tags: args.tags,
      assignee: args.assignee,
      metadata: args.metadata
    };
    
    // Validate using Zod
    const validation = validateCreateTicket(ticketData);
    if (!validation.success) {
      throw validation.error;
    }
    
    const validatedData = validation.data;
    
    // Generate ticket ID
    const date = new Date().toISOString().split('T')[0].replace(/-/g, '');
    const randomId = uuidv4().split('-')[0];
    const ticketId = `UK-${date}-${randomId.toUpperCase()}`;
    
    // Create ticket object
    const ticket = {
      id: ticketId,
      title: validatedData.title,
      description: validatedData.description || null,
      status: 'OPEN',
      priority: validatedData.priority,
      type: validatedData.type,
      tags: validatedData.tags || [],
      assignee: validatedData.assignee || null,
      reporter: 'system', // TODO: Get from context/auth
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      closed_at: null,
      resolution: null,
      metadata: validatedData.metadata || {},
      comments: [],
      history: [
        {
          action: 'created',
          timestamp: new Date().toISOString(),
          user: 'system',
          details: {
            title: validatedData.title,
            priority: validatedData.priority,
            type: validatedData.type
          }
        }
      ],
      links: []
    };
    
    // Store in Redis
    await redis.storeTicket(ticketId, ticket);
    
    // Generate embedding for semantic search
    const embeddingText = `${ticket.title} ${ticket.description || ''} ${ticket.tags.join(' ')}`;
    const ticketEmbedding = await embedding.generateEmbedding(embeddingText);
    
    // Store in Qdrant for vector search
    await qdrant.upsertTicketEmbedding(ticketId, ticketEmbedding, {
      title: ticket.title,
      description: ticket.description,
      status: ticket.status,
      priority: ticket.priority,
      type: ticket.type,
      tags: ticket.tags
    });
    
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            success: true,
            ticket_id: ticketId,
            message: "Ticket created successfully",
            ticket: ticket
          }, null, 2)
        }
      ]
    };
  },

  async updateTicket(args, services) {
    const { redis, postgres, qdrant, embedding } = services;
    
    // Validate input
    const validation = validateUpdateTicket({
      ticket_id: args.ticket_id,
      updates: args.updates
    });
    
    if (!validation.success) {
      throw validation.error;
    }
    
    const { ticket_id, updates } = validation.data;
    
    // Get existing ticket
    const ticket = await redis.getTicket(ticket_id);
    if (!ticket) {
      throw new Error(`Ticket ${ticket_id} not found`);
    }
    
    // Track what changed for history
    const changes = {};
    Object.keys(updates).forEach(key => {
      if (ticket[key] !== updates[key]) {
        changes[key] = {
          from: ticket[key],
          to: updates[key]
        };
      }
    });
    
    // Apply updates
    const updatedTicket = {
      ...ticket,
      ...updates,
      updated_at: new Date().toISOString()
    };
    
    // Add history entry
    updatedTicket.history = updatedTicket.history || [];
    updatedTicket.history.push({
      action: 'updated',
      timestamp: new Date().toISOString(),
      user: 'system',
      changes: changes
    });
    
    // Handle status changes to completed states
    const wasOpen = !['CLOSED', 'CANCELLED'].includes(ticket.status);
    const isClosed = ['CLOSED', 'CANCELLED'].includes(updatedTicket.status);
    
    if (wasOpen && isClosed) {
      updatedTicket.closed_at = new Date().toISOString();
    }
    
    // Store updated ticket in Redis
    await redis.storeTicket(ticket_id, updatedTicket);
    
    // Update embeddings if significant fields changed
    if (changes.title || changes.description || changes.tags) {
      const embeddingText = `${updatedTicket.title} ${updatedTicket.description || ''} ${(updatedTicket.tags || []).join(' ')}`;
      const ticketEmbedding = await embedding.generateEmbedding(embeddingText);
      
      await qdrant.upsertTicketEmbedding(ticket_id, ticketEmbedding, {
        title: updatedTicket.title,
        description: updatedTicket.description,
        status: updatedTicket.status,
        priority: updatedTicket.priority,
        type: updatedTicket.type,
        tags: updatedTicket.tags
      });
    }
    
    // Archive if closed
    if (wasOpen && isClosed) {
      await postgres.archiveTicket(updatedTicket);
    }
    
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            success: true,
            ticket_id: ticket_id,
            message: "Ticket updated successfully",
            ticket: updatedTicket,
            changes: changes,
            archived: wasOpen && isClosed
          }, null, 2)
        }
      ]
    };
  },

  async getTicket(args, services) {
    const { redis, postgres } = services;
    
    // Validate input
    const validation = validateGetTicket({
      ticket_id: args.ticket_id,
      include_history: args.include_history,
      include_comments: args.include_comments,
      include_links: args.include_links
    });
    
    if (!validation.success) {
      throw validation.error;
    }
    
    const { ticket_id, include_history, include_comments, include_links } = validation.data;
    
    // Try Redis first
    let ticket = await redis.getTicket(ticket_id);
    let source = 'active';
    
    // Check archives if not found
    if (!ticket) {
      ticket = await postgres.getArchivedTicket(ticket_id);
      source = 'archive';
    }
    
    if (!ticket) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              success: false,
              error: `Ticket ${ticket_id} not found`,
              code: 'NOT_FOUND'
            }, null, 2)
          }
        ]
      };
    }
    
    // Filter response based on options
    const response = { ...ticket };
    if (!include_history) delete response.history;
    if (!include_comments) delete response.comments;
    if (!include_links) delete response.links;
    
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            success: true,
            ticket: response,
            source: source
          }, null, 2)
        }
      ]
    };
  },

  async searchTickets(args, services) {
    const { redis, postgres, qdrant, embedding } = services;
    
    // Validate input
    const validation = validateSearchTickets({
      query: args.query,
      filters: args.filters,
      sort_by: args.sort_by,
      sort_order: args.sort_order,
      limit: args.limit,
      offset: args.offset
    });
    
    if (!validation.success) {
      throw validation.error;
    }
    
    const validatedData = validation.data;
    const limit = validatedData.limit || 20;
    const offset = validatedData.offset || 0;
    
    // Semantic search if query provided
    if (validatedData.query) {
      const queryEmbedding = await embedding.generateEmbedding(validatedData.query);
      const results = await qdrant.searchTickets(queryEmbedding, limit, validatedData.filters);
      
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              success: true,
              query: validatedData.query,
              total: results.length,
              limit: limit,
              offset: offset,
              tickets: results
            }, null, 2)
          }
        ]
      };
    }
    
    // Otherwise do a regular search
    return this.listTickets(args, services);
  },

  async listTickets(args, services) {
    const { redis, postgres } = services;
    
    // Validate input
    const validation = validateListTickets({
      status: args.status || args.filters?.status,
      assignee: args.assignee || args.filters?.assignee,
      priority: args.priority || args.filters?.priority,
      type: args.type || args.filters?.type,
      tags: args.tags || args.filters?.tags,
      sort_by: args.sort_by,
      sort_order: args.sort_order,
      limit: args.limit,
      offset: args.offset
    });
    
    if (!validation.success) {
      throw validation.error;
    }
    
    const filters = validation.data;
    const limit = filters.limit || 20;
    const offset = filters.offset || 0;
    
    // Get all tickets from Redis
    let tickets = await redis.getAllTickets();
    
    // Apply filters
    if (filters.status) {
      const statuses = Array.isArray(filters.status) ? filters.status : [filters.status];
      tickets = tickets.filter(t => statuses.includes(t.status));
    }
    
    if (filters.assignee) {
      tickets = tickets.filter(t => t.assignee === filters.assignee);
    }
    
    if (filters.priority) {
      const priorities = Array.isArray(filters.priority) ? filters.priority : [filters.priority];
      tickets = tickets.filter(t => priorities.includes(t.priority));
    }
    
    if (filters.type) {
      const types = Array.isArray(filters.type) ? filters.type : [filters.type];
      tickets = tickets.filter(t => types.includes(t.type));
    }
    
    if (filters.tags) {
      const tags = Array.isArray(filters.tags) ? filters.tags : [filters.tags];
      tickets = tickets.filter(t => 
        t.tags && tags.some(tag => t.tags.includes(tag))
      );
    }
    
    // Sort
    const sortBy = filters.sort_by || 'created_at';
    const sortOrder = filters.sort_order || 'desc';
    
    tickets.sort((a, b) => {
      let aVal = a[sortBy];
      let bVal = b[sortBy];
      
      // Handle priority sorting
      if (sortBy === 'priority') {
        const priorityOrder = { urgent: 4, high: 3, medium: 2, low: 1 };
        aVal = priorityOrder[aVal] || 0;
        bVal = priorityOrder[bVal] || 0;
      }
      
      // Handle status sorting
      if (sortBy === 'status') {
        const statusOrder = { 
          OPEN: 1, 
          IN_PROGRESS: 2, 
          BLOCKED: 3, 
          REVIEW: 4, 
          TESTING: 5, 
          CLOSED: 6, 
          CANCELLED: 7 
        };
        aVal = statusOrder[aVal] || 0;
        bVal = statusOrder[bVal] || 0;
      }
      
      if (sortOrder === 'asc') {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });
    
    // Paginate
    const total = tickets.length;
    const paginatedTickets = tickets.slice(offset, offset + limit);
    
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            success: true,
            tickets: paginatedTickets,
            total: total,
            limit: limit,
            offset: offset
          }, null, 2)
        }
      ]
    };
  },

  async closeTicket(args, services) {
    const { redis } = services;
    
    // Validate input
    const validation = validateCloseTicket({
      ticket_id: args.ticket_id,
      resolution: args.resolution,
      metadata: args.metadata
    });
    
    if (!validation.success) {
      throw validation.error;
    }
    
    const { ticket_id, resolution, metadata } = validation.data;
    
    // Update ticket with closed status and resolution
    return this.updateTicket({
      ticket_id: ticket_id,
      updates: {
        status: 'CLOSED',
        resolution: resolution,
        metadata: {
          ...metadata,
          closed_by: 'system',
          closed_at: new Date().toISOString()
        }
      }
    }, services);
  },

  async assignTicket(args, services) {
    const { redis } = services;
    
    // Validate input
    const validation = validateAssignTicket({
      ticket_id: args.ticket_id,
      assignee: args.assignee,
      notify: args.notify
    });
    
    if (!validation.success) {
      throw validation.error;
    }
    
    const { ticket_id, assignee, notify } = validation.data;
    
    // Update ticket with new assignee
    const result = await this.updateTicket({
      ticket_id: ticket_id,
      updates: {
        assignee: assignee
      }
    }, services);
    
    // TODO: Handle notification if notify is true
    if (notify) {
      console.log(`[TicketTools] Would notify ${assignee} about assignment to ${ticket_id}`);
    }
    
    return result;
  },

  async addMember(args, services) {
    const { redis } = services;
    
    // Validate input
    const validation = validateAddMember({
      ticket_id: args.ticket_id,
      member: args.member,
      role: args.role,
      notify: args.notify
    });
    
    if (!validation.success) {
      throw validation.error;
    }
    
    const { ticket_id, member, role, notify } = validation.data;
    
    // Get existing ticket
    const ticket = await redis.getTicket(ticket_id);
    if (!ticket) {
      throw new Error(`Ticket ${ticket_id} not found`);
    }
    
    // Initialize members array if needed
    if (!ticket.members) {
      ticket.members = [];
    }
    
    // Check if member already exists
    const existingMember = ticket.members.find(m => m.name === member);
    if (existingMember) {
      existingMember.role = role || existingMember.role;
      existingMember.updated_at = new Date().toISOString();
    } else {
      ticket.members.push({
        name: member,
        role: role || 'viewer',
        added_at: new Date().toISOString()
      });
    }
    
    // Add history entry
    ticket.history = ticket.history || [];
    ticket.history.push({
      action: 'member_added',
      timestamp: new Date().toISOString(),
      user: 'system',
      details: {
        member: member,
        role: role || 'viewer'
      }
    });
    
    ticket.updated_at = new Date().toISOString();
    await redis.storeTicket(ticket_id, ticket);
    
    // TODO: Handle notification if notify is true
    if (notify) {
      console.log(`[TicketTools] Would notify ${member} about being added to ${ticket_id}`);
    }
    
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            success: true,
            ticket_id: ticket_id,
            member: member,
            role: role || 'viewer',
            message: "Member added successfully"
          }, null, 2)
        }
      ]
    };
  },

  async linkTickets(args, services) {
    const { redis } = services;
    
    // Map old field names to new ones for backwards compatibility
    const linkData = {
      source_ticket_id: args.source_ticket_id || args.ticket_id,
      target_ticket_id: args.target_ticket_id || args.linked_ticket_id,
      link_type: args.link_type,
      metadata: args.metadata
    };
    
    // Validate input
    const validation = validateLinkTickets(linkData);
    
    if (!validation.success) {
      throw validation.error;
    }
    
    const { source_ticket_id, target_ticket_id, link_type, metadata } = validation.data;
    
    // Get both tickets
    const sourceTicket = await redis.getTicket(source_ticket_id);
    const targetTicket = await redis.getTicket(target_ticket_id);
    
    if (!sourceTicket) {
      throw new Error(`Source ticket ${source_ticket_id} not found`);
    }
    if (!targetTicket) {
      throw new Error(`Target ticket ${target_ticket_id} not found`);
    }
    
    // Initialize links arrays if needed
    if (!sourceTicket.links) sourceTicket.links = [];
    if (!targetTicket.links) targetTicket.links = [];
    
    // Create link ID
    const linkId = uuidv4();
    const timestamp = new Date().toISOString();
    
    // Add link to source ticket
    const sourceLink = {
      id: linkId,
      ticket_id: target_ticket_id,
      link_type: link_type,
      created_at: timestamp,
      metadata: metadata || {}
    };
    
    // Remove existing link if present
    sourceTicket.links = sourceTicket.links.filter(l => l.ticket_id !== target_ticket_id);
    sourceTicket.links.push(sourceLink);
    
    // Add reciprocal link to target ticket
    const reciprocalType = this.getReciprocalLinkType(link_type);
    const targetLink = {
      id: linkId,
      ticket_id: source_ticket_id,
      link_type: reciprocalType,
      created_at: timestamp,
      metadata: metadata || {}
    };
    
    // Remove existing link if present
    targetTicket.links = targetTicket.links.filter(l => l.ticket_id !== source_ticket_id);
    targetTicket.links.push(targetLink);
    
    // Add history entries
    sourceTicket.history = sourceTicket.history || [];
    sourceTicket.history.push({
      action: 'linked',
      timestamp: timestamp,
      user: 'system',
      details: {
        linked_to: target_ticket_id,
        link_type: link_type
      }
    });
    
    targetTicket.history = targetTicket.history || [];
    targetTicket.history.push({
      action: 'linked',
      timestamp: timestamp,
      user: 'system',
      details: {
        linked_to: source_ticket_id,
        link_type: reciprocalType
      }
    });
    
    // Update both tickets
    sourceTicket.updated_at = timestamp;
    targetTicket.updated_at = timestamp;
    
    await redis.storeTicket(source_ticket_id, sourceTicket);
    await redis.storeTicket(target_ticket_id, targetTicket);
    
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            success: true,
            link_id: linkId,
            source_ticket_id: source_ticket_id,
            target_ticket_id: target_ticket_id,
            link_type: link_type,
            message: "Tickets linked successfully"
          }, null, 2)
        }
      ]
    };
  },

  getReciprocalLinkType(linkType) {
    const reciprocals = {
      'blocks': 'blocked_by',
      'blocked_by': 'blocks',
      'relates_to': 'relates_to',
      'duplicates': 'duplicates',
      'parent': 'child',
      'child': 'parent'
    };
    
    return reciprocals[linkType] || linkType;
  }
};