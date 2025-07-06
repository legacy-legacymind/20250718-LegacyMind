import { z } from 'zod';
import { logger } from '../utils/logger.js';
import { rateLimiter } from '../shared/rate-limiter.js';
import { v4 as uuidv4 } from 'uuid';

/**
 * InjectTool - A lightweight router for knowledge injection
 * 
 * This tool acts as a simple client for the UnifiedKnowledge MCP.
 * It has no knowledge of filesystem or data storage - it delegates
 * all operations to the appropriate UnifiedKnowledge tools.
 * 
 * Architecture:
 * - Single responsibility: Route requests to UnifiedKnowledge
 * - No filesystem access
 * - No direct Redis/database operations
 * - Service-oriented design
 */

// Simplified schema - no federation, no filesystem paths
export const injectSchema = z.object({
  name: z.literal('ui_inject'),
  description: z.literal('Injects context from the knowledge base via direct lookup or semantic search'),
  inputSchema: z.object({
    type: z.literal('object'),
    properties: z.object({
      action: z.object({
        type: z.literal('string'),
        enum: z.array(z.literal('inject').or(z.literal('help'))),
        description: z.literal('Action to perform'),
        default: z.literal('inject')
      }).optional(),
      type: z.object({
        type: z.literal('string'),
        enum: z.array(z.literal('expert').or(z.literal('document'))),
        description: z.literal('The type of knowledge to inject')
      }),
      lookup: z.object({
        type: z.literal('string'),
        description: z.literal('The identifier for a direct lookup (e.g., "Docker:Networking" or a document ID)')
      }).optional(),
      query: z.object({
        type: z.literal('string'),
        description: z.literal('A natural language query for a semantic search')
      }).optional()
    }),
    oneOf: z.array(
      z.object({ required: z.array(z.literal('type').and(z.literal('lookup'))) })
        .or(z.object({ required: z.array(z.literal('type').and(z.literal('query'))) }))
    )
  })
});

/**
 * Input validation schema
 */
const InjectInputSchema = z.object({
  action: z.enum(['inject', 'help']).default('inject'),
  type: z.enum(['expert', 'document']),
  lookup: z.string().optional(),
  query: z.string().optional()
}).refine(
  (data) => {
    // Must have either lookup OR query, but not both
    return (data.lookup && !data.query) || (!data.lookup && data.query);
  },
  {
    message: "Must provide either 'lookup' or 'query', but not both"
  }
);

/**
 * Rate limit configuration
 */
const RATE_LIMITS = {
  inject: { max: 10, window: 300 }, // 10 injections per 5 minutes
  help: { max: 20, window: 60 }     // 20 help requests per minute
};

export class InjectTool {
  constructor(sessionManager) {
    this.sessionManager = sessionManager;
    this.logger = logger;
    
    // Note: In the future, this will be replaced with actual MCP client
    // For now, we'll throw an error indicating the service dependency
    this.unifiedKnowledgeClient = null;
    
    this.logger.info('InjectTool initialized (lightweight router mode)');
  }

  /**
   * Main execution method - acts as a router to UnifiedKnowledge
   */
  async execute(args) {
    try {
      // Validate input
      const validatedArgs = this.validate(args);
      const { action, type, lookup, query } = validatedArgs;

      // Handle help action
      if (action === 'help') {
        return this.getHelp();
      }

      // Rate limiting
      const currentInstanceId = this.sessionManager?.currentInstanceId || 'unknown';
      const isRateLimited = await rateLimiter.check(currentInstanceId, 'inject', RATE_LIMITS.inject);
      if (isRateLimited) {
        throw new Error('Rate limit exceeded for inject operations');
      }

      // Route to appropriate UnifiedKnowledge service
      const result = await this.routeToUnifiedKnowledge(type, lookup, query);
      
      // Store injected content in session context
      await this.storeInjectedContext(result, type, lookup || query);

      return {
        success: true,
        message: `Successfully injected ${type} knowledge: ${lookup || query}`,
        injected: {
          type,
          identifier: lookup || query,
          contentLength: result.content ? result.content.length : 0,
          timestamp: new Date().toISOString()
        }
      };

    } catch (error) {
      this.logger.error('InjectTool execution failed', {
        error: error.message,
        args
      });
      throw error;
    }
  }

  /**
   * Input validation
   */
  validate(args) {
    try {
      return InjectInputSchema.parse(args);
    } catch (error) {
      throw new Error(`Input validation failed: ${error.message}`);
    }
  }

  /**
   * Route request to UnifiedKnowledge MCP
   */
  async routeToUnifiedKnowledge(type, lookup, query) {
    // TODO: Replace with actual UnifiedKnowledge MCP client call
    // This is where we'll implement the service call to:
    // - UnifiedKnowledge:experts:get for expert lookups
    // - UnifiedKnowledge:experts:search for expert queries  
    // - UnifiedKnowledge:document:get for document lookups
    // - UnifiedKnowledge:document:search for document queries
    
    throw new Error(
      'UnifiedKnowledge MCP integration not yet implemented. ' +
      'This tool requires connection to UnifiedKnowledge service for: ' +
      `${type} ${lookup ? 'lookup' : 'search'}: ${lookup || query}`
    );
  }

  /**
   * Parse lookup string into structured payload
   */
  parseLookup(lookup) {
    if (!lookup) return null;

    // Handle expert module format: "Docker:Networking" 
    if (lookup.includes(':')) {
      const [topic, module] = lookup.split(':', 2);
      return {
        type: 'expert',
        topic: topic.trim(),
        module: module.trim()
      };
    }

    // Handle document ID or simple identifier
    return {
      type: 'document',
      identifier: lookup.trim()
    };
  }

  /**
   * Format result from UnifiedKnowledge for injection
   */
  formatResult(result) {
    if (!result || !result.content) {
      return 'No content available';
    }

    // Add metadata header
    const header = `# Injected Knowledge\n\n**Source**: ${result.source || 'Unknown'}\n**Type**: ${result.type || 'Unknown'}\n**Retrieved**: ${new Date().toISOString()}\n\n---\n\n`;
    
    return header + result.content;
  }

  /**
   * Store injected content in session context
   */
  async storeInjectedContext(result, type, identifier) {
    if (!this.sessionManager) {
      this.logger.warn('No session manager available - context not stored');
      return;
    }

    const contextData = {
      id: uuidv4(),
      type: 'injected_knowledge',
      source: `${type}:${identifier}`,
      content: this.formatResult(result),
      injectedAt: new Date().toISOString(),
      sessionId: this.sessionManager.currentSessionId
    };

    // Store in session context (this will use the session manager's storage)
    await this.sessionManager.addContextData(contextData);
    
    this.logger.info('Injected content stored in session context', {
      type,
      identifier,
      contentLength: contextData.content.length
    });
  }

  /**
   * Provide help information
   */
  getHelp() {
    return {
      tool: 'ui_inject',
      description: 'Lightweight knowledge injection router',
      architecture: 'Service-oriented - delegates to UnifiedKnowledge MCP',
      
      usage: {
        expert_lookup: {
          description: 'Inject expert knowledge by direct lookup',
          example: {
            type: 'expert',
            lookup: 'Docker:Networking'
          }
        },
        expert_search: {
          description: 'Find expert knowledge by semantic search',
          example: {
            type: 'expert', 
            query: 'container networking best practices'
          }
        },
        document_lookup: {
          description: 'Inject document by ID or identifier',
          example: {
            type: 'document',
            lookup: 'DOC-12345'
          }
        },
        document_search: {
          description: 'Find documents by semantic search',
          example: {
            type: 'document',
            query: 'microservices architecture patterns'
          }
        }
      },

      changes: {
        removed: [
          'Federation context loading (use direct cross-instance calls)',
          'Filesystem access and file reading',
          'Direct Redis/database operations',
          'Complex monolithic logic'
        ],
        added: [
          'Service-oriented architecture',
          'Clean separation of concerns', 
          'UnifiedKnowledge MCP integration',
          'Lightweight routing design'
        ]
      },

      next_steps: [
        'Implement UnifiedKnowledge MCP client integration',
        'Add retry logic and error handling',
        'Create comprehensive test suite',
        'Add metrics and monitoring'
      ]
    };
  }
}