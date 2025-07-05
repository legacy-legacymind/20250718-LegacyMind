import { z } from 'zod';

/**
 * Input validation schemas for the UnifiedIntelligence MCP
 * Using Zod for runtime type checking and validation
 */

// Base schema for instance identifiers
export const instanceIdSchema = z.string()
  .min(1, 'Instance ID cannot be empty')
  .max(50, 'Instance ID too long')
  .regex(/^[a-zA-Z0-9_-]+$/, 'Instance ID can only contain alphanumeric characters, underscores, and hyphens')
  .refine(val => !val.includes(':'), 'Instance ID cannot contain colons');

// Session configuration schema
export const sessionConfigSchema = z.object({
  instanceId: instanceIdSchema,
  sessionId: z.string().uuid().optional(),
  createdAt: z.string().datetime().optional(),
  lastActive: z.string().datetime().optional(),
  status: z.enum(['active', 'inactive', 'archived']).default('active'),
  thoughtCount: z.number().int().nonnegative().default(0),
  metadata: z.record(z.unknown()).optional()
});

// Thought confidence level schema
export const confidenceSchema = z.number()
  .min(0, 'Confidence must be between 0 and 1')
  .max(1, 'Confidence must be between 0 and 1')
  .default(0.5);

// Tag schema
export const tagSchema = z.string()
  .min(1, 'Tag cannot be empty')
  .max(50, 'Tag too long')
  .regex(/^[a-zA-Z0-9_-]+$/, 'Tags can only contain alphanumeric characters, underscores, and hyphens');

// Thought mode schema
export const thoughtModeSchema = z.enum([
  'debug',
  'design',
  'learn',
  'analyze',
  'plan',
  'review',
  'explore',
  'solve',
  'implement',
  'optimize',
  'document',
  'collaborate',
  'unknown'
]).default('unknown');

// Thought options schema
export const thoughtOptionsSchema = z.object({
  instance: instanceIdSchema.optional(),
  confidence: confidenceSchema.optional(),
  tags: z.array(tagSchema).max(10, 'Maximum 10 tags allowed').optional(),
  mode: thoughtModeSchema.optional(),
  framework: z.string().optional(),
  metadata: z.record(z.unknown()).optional()
});

// Message schema for thoughts
export const messageSchema = z.object({
  id: z.string().uuid().optional(),
  thought: z.string()
    .min(1, 'Thought cannot be empty')
    .max(5000, 'Thought too long (max 5000 characters)'),
  instanceId: instanceIdSchema,
  sessionId: z.string().uuid(),
  timestamp: z.string().datetime().default(() => new Date().toISOString()),
  mode: thoughtModeSchema,
  confidence: confidenceSchema,
  tags: z.array(tagSchema).default([]),
  context: z.object({
    previousThoughtId: z.string().uuid().optional(),
    framework: z.string().optional(),
    patterns: z.array(z.string()).optional(),
    relatedThoughts: z.array(z.string().uuid()).optional()
  }).optional(),
  metadata: z.record(z.unknown()).optional()
});

// Stream configuration schema
export const streamConfigSchema = z.object({
  enabled: z.boolean().default(false),
  bufferSize: z.number().int().positive().default(10),
  flushInterval: z.number().int().positive().default(1000), // milliseconds
  retryAttempts: z.number().int().nonnegative().default(3),
  retryDelay: z.number().int().positive().default(1000) // milliseconds
});

// Extension message schema (for MCP extensions)
export const extensionMessageSchema = z.object({
  type: z.enum(['extension', 'plugin', 'integration']),
  source: z.string().min(1),
  target: instanceIdSchema.optional(),
  action: z.string().min(1),
  payload: z.unknown(),
  timestamp: z.string().datetime().default(() => new Date().toISOString())
});

// Tool use schema (for ui_think tool)
export const toolUseSchema = z.object({
  action: z.enum(['capture', 'status', 'framework', 'session', 'help', 'checkin']).default('capture'),
  thought: z.string().optional(),
  options: thoughtOptionsSchema.optional()
});

// Response content schema
export const responseContentSchema = z.object({
  type: z.enum(['text', 'markdown', 'json', 'error']).default('text'),
  content: z.string(),
  metadata: z.record(z.unknown()).optional()
});

// Session status response schema
export const sessionStatusSchema = z.object({
  sessionId: z.string().uuid(),
  instanceId: instanceIdSchema,
  status: z.enum(['active', 'inactive', 'archived']),
  createdAt: z.string().datetime(),
  lastActive: z.string().datetime(),
  thoughtCount: z.number().int().nonnegative(),
  recentThoughts: z.array(messageSchema).optional(),
  patterns: z.array(z.string()).optional(),
  activeFramework: z.string().optional()
});

// Framework schema
export const frameworkSchema = z.object({
  name: z.string().min(1),
  description: z.string(),
  steps: z.array(z.string()),
  tags: z.array(tagSchema),
  applicableModes: z.array(thoughtModeSchema)
});

// Pattern detection schema
export const patternSchema = z.object({
  type: z.enum(['loop', 'confusion', 'progress', 'breakthrough', 'stagnation']),
  confidence: confidenceSchema,
  description: z.string(),
  detectedAt: z.string().datetime(),
  thoughtIds: z.array(z.string().uuid())
});

// Auto-capture configuration schema
export const autoCaptureConfigSchema = z.object({
  enabled: z.boolean().default(true),
  triggers: z.array(z.enum(['timer', 'event', 'pattern', 'context'])).default(['pattern']),
  intervalMs: z.number().int().positive().default(300000), // 5 minutes
  maxCaptures: z.number().int().positive().default(100),
  filters: z.object({
    minConfidence: confidenceSchema.optional(),
    includeTags: z.array(tagSchema).optional(),
    excludeTags: z.array(tagSchema).optional(),
    modes: z.array(thoughtModeSchema).optional()
  }).optional()
});

// Redis key schema
export const redisKeySchema = z.object({
  namespace: z.enum(['session', 'thought', 'pattern', 'framework', 'context']),
  instanceId: instanceIdSchema,
  resourceId: z.string().min(1),
  subResource: z.string().optional()
});

// Health check schema
export const healthCheckSchema = z.object({
  status: z.enum(['healthy', 'degraded', 'unhealthy']),
  timestamp: z.string().datetime(),
  checks: z.object({
    redis: z.boolean(),
    memory: z.boolean(),
    cpu: z.boolean()
  }),
  metrics: z.object({
    uptime: z.number().nonnegative(),
    memoryUsage: z.number().nonnegative(),
    activeConnections: z.number().int().nonnegative(),
    thoughtsProcessed: z.number().int().nonnegative()
  }).optional()
});

// Utility function to validate and parse with better error messages
export function validateInput(schema, data, contextName = 'input') {
  try {
    return schema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      const issues = error.issues.map(issue => {
        const path = issue.path.join('.');
        return `${path ? path + ': ' : ''}${issue.message}`;
      }).join('; ');
      throw new Error(`Invalid ${contextName}: ${issues}`);
    }
    throw error;
  }
}

// Export a helper to create validated Redis keys
export function createRedisKey(namespace, instanceId, resourceId, subResource) {
  const validated = validateInput(redisKeySchema, {
    namespace,
    instanceId,
    resourceId,
    subResource
  }, 'Redis key configuration');
  
  const parts = [validated.instanceId, validated.namespace, validated.resourceId];
  if (validated.subResource) {
    parts.push(validated.subResource);
  }
  return parts.join(':');
}

// Export all schemas for easy access
export const schemas = {
  instanceId: instanceIdSchema,
  sessionConfig: sessionConfigSchema,
  confidence: confidenceSchema,
  tag: tagSchema,
  thoughtMode: thoughtModeSchema,
  thoughtOptions: thoughtOptionsSchema,
  message: messageSchema,
  streamConfig: streamConfigSchema,
  extensionMessage: extensionMessageSchema,
  toolUse: toolUseSchema,
  responseContent: responseContentSchema,
  sessionStatus: sessionStatusSchema,
  framework: frameworkSchema,
  pattern: patternSchema,
  autoCaptureConfig: autoCaptureConfigSchema,
  redisKey: redisKeySchema,
  healthCheck: healthCheckSchema
};