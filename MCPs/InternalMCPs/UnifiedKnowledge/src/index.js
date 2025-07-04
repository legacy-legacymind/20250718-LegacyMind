// src/index.js
console.error('!!! UNIFIED WORKFLOW MCP STARTING !!!');

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { RedisManager } from './managers/redis-manager.js';
import { DatabaseManager } from './managers/database-manager.js';
import { QdrantManager } from './managers/qdrant-manager.js';
import { TicketManager } from './managers/ticket-manager.js';
import { ProjectManager } from './managers/project-manager.js';
import { DocManager } from './managers/doc-manager.js';
import { WorkLogManager } from './managers/work-log-manager.js';
import { StatsManager } from './managers/stats-manager.js';
import { BatchManager } from './managers/batch-manager.js';
import { logger } from './utils/logger.js';
import { ErrorHandler } from './utils/error-handler.js';

class UnifiedWorkflowServer {
  constructor() {
    this.server = new Server(
      { name: 'unified-workflow', version: '2.1.0' },
      { capabilities: { tools: {} } }
    );
    this.redisManager = new RedisManager();
    this.dbManager = new DatabaseManager();
    this.qdrantManager = new QdrantManager();
    this.workLogManager = new WorkLogManager(this.redisManager, this.dbManager);
    this.statsManager = new StatsManager(this.redisManager, this.dbManager);
    this.batchManager = new BatchManager(this.redisManager, this.dbManager);
    this.ticketManager = new TicketManager(
      this.redisManager, 
      this.dbManager, 
      this.qdrantManager, 
      this.workLogManager,
      this.statsManager,
      this.batchManager
    );
    this.projectManager = new ProjectManager(this.redisManager, this.dbManager, this.qdrantManager);
    this.docManager = new DocManager(this.redisManager, this.dbManager, this.qdrantManager);
  }

  async initialize() {
    try {
      await this.redisManager.connect();
      await this.dbManager.connect();
      await this.qdrantManager.connect();
      this.setupHandlers();
      logger.info('UnifiedWorkflow server initialized successfully');
    } catch (error) {
      logger.error('Failed to initialize UnifiedWorkflow server', {
        error: error.message,
        stack: error.stack
      });
      throw error;
    }
  }

  setupHandlers() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: 'uw_tickets',
          description: 'Manages tickets using a Redis-based workflow with enhanced Phase 2 features.',
          inputSchema: {
            type: 'object',
            properties: {
              action: { 
                type: 'string', 
                enum: ['create', 'update', 'query', 'delete', 'log_work', 'get_work_logs', 'get_stats', 'batch_update'] 
              },
              data: { type: 'object' },
            },
            required: ['action', 'data'],
          },
        },
        {
          name: 'uw_projects',
          description: 'Manages projects with team collaboration features.',
          inputSchema: {
            type: 'object',
            properties: {
              action: { 
                type: 'string', 
                enum: ['create', 'update', 'query', 'delete', 'add_member', 'remove_member', 'link_ticket', 'unlink_ticket'] 
              },
              data: { type: 'object' },
            },
            required: ['action', 'data'],
          },
        },
        {
          name: 'uw_system_docs',
          description: 'Manages system documentation with version control and temporal validity.',
          inputSchema: {
            type: 'object',
            properties: {
              action: { 
                type: 'string', 
                enum: ['create', 'update', 'query', 'delete', 'add_reference', 'remove_reference'] 
              },
              data: { type: 'object' },
            },
            required: ['action', 'data'],
          },
        },
      ],
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;
      
      try {
        let result;
        
        switch (name) {
          case 'uw_tickets':
            switch (args.action) {
              case 'create':
                result = await this.ticketManager.create(args.data);
                break;
              case 'update':
                result = await this.ticketManager.update(args.data);
                break;
              case 'query':
                result = await this.ticketManager.query(args.data);
                break;
              case 'delete':
                result = await this.ticketManager.delete(args.data);
                break;
              case 'log_work':
                result = await this.ticketManager.logWork(args.data);
                break;
              case 'get_work_logs':
                result = await this.ticketManager.getWorkLogs(args.data);
                break;
              case 'get_stats':
                result = await this.ticketManager.getStats(args.data);
                break;
              case 'batch_update':
                result = await this.ticketManager.batchUpdate(args.data);
                break;
              default:
                throw new Error(`Unknown ticket action: ${args.action}`);
            }
            break;
            
          case 'uw_projects':
            switch (args.action) {
              case 'create':
                result = await this.projectManager.create(args.data);
                break;
              case 'update':
                result = await this.projectManager.update(args.data);
                break;
              case 'query':
                result = await this.projectManager.query(args.data);
                break;
              case 'delete':
                result = await this.projectManager.delete(args.data);
                break;
              case 'add_member':
                result = await this.projectManager.addMember(args.data);
                break;
              case 'remove_member':
                result = await this.projectManager.removeMember(args.data);
                break;
              case 'link_ticket':
                result = await this.projectManager.linkTicket(args.data);
                break;
              case 'unlink_ticket':
                result = await this.projectManager.unlinkTicket(args.data);
                break;
              default:
                throw new Error(`Unknown project action: ${args.action}`);
            }
            break;
            
          case 'uw_system_docs':
            switch (args.action) {
              case 'create':
                result = await this.docManager.create(args.data);
                break;
              case 'update':
                result = await this.docManager.update(args.data);
                break;
              case 'query':
                result = await this.docManager.query(args.data);
                break;
              case 'delete':
                result = await this.docManager.delete(args.data);
                break;
              case 'add_reference':
                result = await this.docManager.addReference(args.data);
                break;
              case 'remove_reference':
                result = await this.docManager.removeReference(args.data);
                break;
              default:
                throw new Error(`Unknown document action: ${args.action}`);
            }
            break;
            
          default:
            throw new Error(`Unknown tool: ${name}`);
        }
        
        return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
      } catch (error) {
        logger.error('Tool execution failed', {
          tool: name,
          action: args.action,
          error: error.message,
          stack: error.stack,
          context: error.context || {}
        });
        
        const errorResponse = ErrorHandler.createErrorResponse(error, process.env.NODE_ENV !== 'production');
        return {
          content: [{ type: 'text', text: JSON.stringify(errorResponse, null, 2) }],
          isError: true,
        };
      }
    });
  }

  async start() {
    try {
      await this.initialize();
      const transport = new StdioServerTransport();
      await this.server.connect(transport);
      logger.info('UnifiedWorkflow v2.1 (Enhanced with Projects & Docs) MCP server started.');
    } catch (error) {
      logger.error('Failed to start UnifiedWorkflow v2 server:', error);
      process.exit(1);
    }
  }
}

const server = new UnifiedWorkflowServer();
server.start();