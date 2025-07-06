// src/shared/validators.js
import { z } from 'zod';
import DOMPurify from 'isomorphic-dompurify';

// Custom sanitization
const sanitizeString = (val) => {
    if (typeof val !== 'string') return val;
    return DOMPurify.sanitize(val, { ALLOWED_TAGS: [] });
};

// Reusable schemas with sanitization
export const zInstanceId = z.string()
    .regex(/^[a-zA-Z0-9_-]+$/, "Invalid instance ID")
    .max(50);

export const zContent = z.string()
    .min(1)
    .max(10000)
    .transform(sanitizeString);

export const zCategory = z.enum(['identity', 'context', 'curiosity']);

// Tool-specific schemas with rate limit metadata
export const ThinkSchemas = {
    capture: z.object({
        thought: zContent,
        instanceId: zInstanceId.optional(),
        options: z.object({
            confidence: z.number().min(0).max(1).optional(),
            tags: z.array(z.string().max(50)).max(20).optional()
        }).optional()
    }).strict(),
    
    check_in: z.object({
        identity: z.object({
            name: zInstanceId,
            id: zInstanceId.optional(),
            type: z.string().max(100),
            role: z.string().max(200)
        }).strict()
    }).strict()
};

export const RememberSchemas = {
    base: z.object({
        type: zCategory,
        operation: z.enum(['create', 'search', 'list', 'get', 'update', 'delete'])
    }),
    
    create: z.object({
        content: zContent,
        tags: z.array(z.string().max(50)).max(20).optional(),
        metadata: z.record(z.string(), z.any()).optional(),
        source_agent_id: zInstanceId
    }),
    
    search: z.object({
        query: z.string().max(200),
        limit: z.number().int().min(1).max(100).default(10),
        tags: z.array(z.string()).optional()
    })
};