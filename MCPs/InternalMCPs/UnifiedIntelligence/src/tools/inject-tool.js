import { promises as fs } from 'fs';
import path from 'path';
import { z } from 'zod';

const MAX_CONTEXT_SIZE = 50000; // 50KB limit for injected context
const ALLOWED_EXTENSIONS = ['.md', '.txt', '.json', '.yml', '.yaml'];

// Schema for the ui_inject tool
export const injectSchema = z.object({
  name: z.literal('ui_inject'),
  description: z.literal('Inject context or expert knowledge into the current session'),
  inputSchema: z.object({
    type: z.literal('object'),
    properties: z.object({
      type: z.object({
        type: z.literal('string'),
        enum: z.array(z.literal('context').or(z.literal('expert'))),
        description: z.literal('Type of injection: context for general knowledge, expert for specialized modules')
      }),
      source: z.object({
        type: z.literal('string'),
        description: z.literal('For context: file path or URL. For expert: module name (e.g., "docker", "mcp", "postgresql")')
      }),
      validate: z.object({
        type: z.literal('boolean'),
        description: z.literal('Whether to validate the injected content'),
        default: z.literal(true)
      }).optional()
    }),
    required: z.array(z.literal('type').or(z.literal('source')))
  })
});

// Expert modules configuration
const EXPERT_MODULES = {
  docker: {
    path: '/Users/samuelatagana/Library/Mobile Documents/iCloud~md~obsidian/Documents/LegacyMind/Experts/Docker',
    files: ['Docker_Expert_Guide.md', 'Docker_Best_Practices.md'],
    description: 'Docker containerization expertise'
  },
  mcp: {
    path: '/Users/samuelatagana/Library/Mobile Documents/iCloud~md~obsidian/Documents/LegacyMind/Experts/MCP',
    files: ['MCP_Development_Operations_Hub.md', 'MCP_Architecture.md'],
    description: 'Model Context Protocol development expertise'
  },
  postgresql: {
    path: '/Users/samuelatagana/Library/Mobile Documents/iCloud~md~obsidian/Documents/LegacyMind/Experts/PostgreSQL',
    files: ['PostgreSQL_Expert_Guide.md', 'PostgreSQL_Performance.md'],
    description: 'PostgreSQL database expertise'
  },
  qdrant: {
    path: '/Users/samuelatagana/Library/Mobile Documents/iCloud~md~obsidian/Documents/LegacyMind/Experts/Qdrant',
    files: ['Qdrant_Expert_Guide.md', 'Qdrant_Vector_Operations.md'],
    description: 'Qdrant vector database expertise'
  },
  redis: {
    path: '/Users/samuelatagana/Library/Mobile Documents/iCloud~md~obsidian/Documents/LegacyMind/Experts/Redis',
    files: ['Redis_Expert_Guide.md', 'Redis_Data_Structures.md'],
    description: 'Redis in-memory database expertise'
  }
};

export class InjectTool {
  constructor(logger, sessionManager) {
    this.logger = logger;
    this.sessionManager = sessionManager;
    this.redis = sessionManager?.redis || null;
  }

  async execute(args) {
    const { type, source, validate = true } = args;

    try {
      if (!this.redis) {
        throw new Error('Redis connection not available');
      }

      this.logger.info(`Executing ui_inject: type=${type}, source=${source}`);

      let content;
      let metadata = {
        type,
        source,
        timestamp: new Date().toISOString()
      };

      if (type === 'expert') {
        content = await this.loadExpertModule(source);
        metadata.expert = {
          module: source,
          description: EXPERT_MODULES[source]?.description
        };
      } else if (type === 'context') {
        content = await this.loadContextFile(source);
        metadata.context = {
          path: source,
          size: content.length
        };
      }

      // Validate content if requested
      if (validate) {
        await this.validateContent(content, type);
      }

      // Get the active session
      const activeSession = await this.sessionManager.getActiveSession();
      if (!activeSession) {
        throw new Error('No active session found. Please check in first.');
      }

      // Store injected content in Redis with session reference
      const contextKey = `${activeSession.instanceId}:context:${Date.now()}`;
      await this.redis.setex(
        contextKey, 
        86400, // 24 hour expiry
        JSON.stringify({
          sessionId: activeSession.id,
          type: 'injected',
          content,
          metadata
        })
      );

      // Update session activity
      await this.sessionManager.updateActivity(activeSession.instanceId);

      this.logger.info(`Successfully injected ${type} content: ${source}`);

      return {
        success: true,
        type,
        source,
        contentSize: content.length,
        metadata,
        message: `Successfully injected ${type} content from ${source}`
      };

    } catch (error) {
      this.logger.error(`Error in ui_inject:`, error);
      throw error;
    }
  }

  async loadExpertModule(moduleName) {
    const module = EXPERT_MODULES[moduleName.toLowerCase()];
    if (!module) {
      throw new Error(`Unknown expert module: ${moduleName}. Available modules: ${Object.keys(EXPERT_MODULES).join(', ')}`);
    }

    const contents = [];
    for (const filename of module.files) {
      const filePath = path.join(module.path, filename);
      try {
        const content = await fs.readFile(filePath, 'utf-8');
        contents.push(`\n## ${filename}\n\n${content}`);
      } catch (error) {
        this.logger.warn(`Could not load expert file ${filePath}: ${error.message}`);
      }
    }

    if (contents.length === 0) {
      throw new Error(`No expert content found for module: ${moduleName}`);
    }

    return `# Expert Module: ${moduleName}\n${module.description}\n${contents.join('\n')}`;
  }

  async loadContextFile(source) {
    // Check if source is a file path
    if (source.startsWith('/') || source.startsWith('./')) {
      return await this.loadLocalFile(source);
    }
    
    // Check if source is a URL
    if (source.startsWith('http://') || source.startsWith('https://')) {
      return await this.loadFromURL(source);
    }

    throw new Error(`Invalid source: ${source}. Must be a file path or URL`);
  }

  async loadLocalFile(filePath) {
    // Validate file extension
    const ext = path.extname(filePath).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      throw new Error(`File type not allowed: ${ext}. Allowed types: ${ALLOWED_EXTENSIONS.join(', ')}`);
    }

    // Check file size
    const stats = await fs.stat(filePath);
    if (stats.size > MAX_CONTEXT_SIZE) {
      throw new Error(`File too large: ${stats.size} bytes. Maximum allowed: ${MAX_CONTEXT_SIZE} bytes`);
    }

    // Read file content
    const content = await fs.readFile(filePath, 'utf-8');
    return content;
  }

  async loadFromURL(url) {
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const contentLength = response.headers.get('content-length');
      if (contentLength && parseInt(contentLength) > MAX_CONTEXT_SIZE) {
        throw new Error(`Content too large: ${contentLength} bytes. Maximum allowed: ${MAX_CONTEXT_SIZE} bytes`);
      }

      const content = await response.text();
      if (content.length > MAX_CONTEXT_SIZE) {
        throw new Error(`Content too large: ${content.length} bytes. Maximum allowed: ${MAX_CONTEXT_SIZE} bytes`);
      }

      return content;
    } catch (error) {
      throw new Error(`Failed to fetch URL: ${error.message}`);
    }
  }

  async validateContent(content, type) {
    // Basic validation
    if (!content || typeof content !== 'string') {
      throw new Error('Invalid content: must be a non-empty string');
    }

    if (content.length === 0) {
      throw new Error('Content is empty');
    }

    if (content.length > MAX_CONTEXT_SIZE) {
      throw new Error(`Content too large: ${content.length} bytes. Maximum allowed: ${MAX_CONTEXT_SIZE} bytes`);
    }

    // Type-specific validation
    if (type === 'expert') {
      // Ensure expert content has expected structure
      if (!content.includes('# Expert Module:')) {
        throw new Error('Invalid expert module content structure');
      }
    }

    // Check for potentially harmful content
    const suspiciousPatterns = [
      /<script[\s\S]*?<\/script>/gi,
      /javascript:/gi,
      /on\w+\s*=/gi
    ];

    for (const pattern of suspiciousPatterns) {
      if (pattern.test(content)) {
        throw new Error('Content contains potentially unsafe patterns');
      }
    }

    return true;
  }

  getSchema() {
    return injectSchema.shape;
  }
}

export const createInjectTool = (logger, sessionManager) => {
  return new InjectTool(logger, sessionManager);
};