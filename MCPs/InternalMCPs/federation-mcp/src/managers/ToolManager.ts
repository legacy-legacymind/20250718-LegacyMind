
import { federationTools } from './tools/index.js';
import { FederationContext, Tool, ToolResult } from './types/index.js';
import { ToolNotFoundError, InvalidToolInputError } from './utils/errors.js';
import { SimpleCache } from './utils/cache.js';
import { sanitizeObject } from './utils/sanitize.js';
import { logger } from './utils/logger.js';
import { z } from 'zod';

export class ToolManager {
  private tools: Tool[];
  private cache: SimpleCache<ToolResult>;

  constructor(cacheTtlSeconds: number) {
    this.tools = federationTools;
    this.cache = new SimpleCache<ToolResult>(cacheTtlSeconds);
  }

  listTools() {
    return this.tools.map(tool => ({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.schema,
    }));
  }

  async executeTool(name: string, rawArgs: any, context: FederationContext): Promise<ToolResult> {
    const sanitizedArgs = sanitizeObject(rawArgs);
    const cacheKey = `${name}:${JSON.stringify(sanitizedArgs)}`;

    // Check cache first
    const cachedResult = this.cache.get(cacheKey);
    if (cachedResult) {
      logger.debug('Returning cached result', { name, cacheKey });
      return cachedResult;
    }

    const tool = this.tools.find(t => t.name === name);
    if (!tool) {
      throw new ToolNotFoundError(name);
    }

    // Validate input against the tool's schema
    try {
      tool.schema.parse(sanitizedArgs);
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new InvalidToolInputError(error.message, error.errors);
      }
      throw error;
    }

    const result = await tool.handler(sanitizedArgs, context);

    // Cache the result if successful
    if (result.success) {
      this.cache.set(cacheKey, result);
    }

    return result;
  }
}
