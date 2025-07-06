// src/shared/key-schema.js
export const KEY_SCHEMA = {
    // Instance data with TTL
    IDENTITY: (instanceId) => ({ 
        key: `instance:${instanceId}:identity`,
        ttl: 90 * 24 * 60 * 60 // 90 days
    }),
    
    CONTEXT: (instanceId) => ({
        key: `instance:${instanceId}:context`,
        ttl: 30 * 24 * 60 * 60 // 30 days
    }),
    
    THOUGHTS_STREAM: (instanceId) => ({
        key: `stream:${instanceId}:thoughts`,
        ttl: 7 * 24 * 60 * 60 // 7 days for stream entries
    }),
    
    // Search indices with cleanup
    SEARCH_INDEX: (type) => ({
        key: `search:${type}:index`,
        ttl: null // Permanent but with member expiry
    }),
    
    // Rate limiting
    RATE_LIMIT: (instanceId, action) => ({
        key: `ratelimit:${instanceId}:${action}`,
        ttl: 60 // 1 minute sliding window
    })
};

// TTL helper
export function applyTTL(client, keyConfig, data) {
    if (keyConfig.ttl) {
        return client.expire(keyConfig.key, keyConfig.ttl);
    }
}