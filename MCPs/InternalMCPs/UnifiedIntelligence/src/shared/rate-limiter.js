// src/shared/rate-limiter.js
import { KEY_SCHEMA } from './key-schema.js';
import { redisManager } from './redis-manager.js';

export class RateLimiter {
    async check(instanceId, action, limits) {
        const keyConfig = KEY_SCHEMA.RATE_LIMIT(instanceId, action);
        
        return redisManager.execute(async (client) => {
            const current = await client.incr(keyConfig.key);
            
            if (current === 1) {
                await client.expire(keyConfig.key, limits.window);
            }
            
            return current > limits.max;
        });
    }
}

export const rateLimiter = new RateLimiter();