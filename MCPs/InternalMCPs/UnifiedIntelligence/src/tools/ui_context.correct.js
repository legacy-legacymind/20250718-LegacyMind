/**
 * ui_context - The Dashboard
 * Manages the instance's active state (identity, current task, etc.)
 * 
 * This manages the living context of an AI instance.
 */

export const ui_context = {
  name: 'ui_context',
  description: 'The Dashboard - Manages the instance\'s active state including identity, current task, goals, and curiosity.',
  
  inputSchema: {
    type: 'object', 
    properties: {
      action: {
        type: 'string',
        enum: ['get', 'update', 'set_identity', 'set_task', 'add_goal', 'update_curiosity'],
        description: 'Context management action'
      },
      data: {
        type: 'object',
        description: 'Data for update actions'
      },
      field: {
        type: 'string',
        description: 'Specific field to get/update'
      }
    },
    required: ['action']
  },
  
  handler: (redisManager, instanceId) => {
    return async (input) => {
      const { action, data, field } = input;
      const redis = redisManager.getClient();
      const contextKey = `context:${instanceId}`;
      
      switch (action) {
        case 'get':
          // Get full context or specific field
          if (field) {
            const result = await redis.sendCommand([
              'JSON.GET', contextKey, `$.${field}`
            ]);
            return result ? JSON.parse(result)[0] : null;
          }
          
          const fullContext = await redis.sendCommand([
            'JSON.GET', contextKey, '$'
          ]);
          return fullContext ? JSON.parse(fullContext)[0] : {
            instanceId,
            identity: null,
            currentTask: null,
            goals: [],
            curiosity: [],
            lastUpdate: null
          };
          
        case 'update':
          // Update entire context
          const updatedContext = {
            ...data,
            instanceId,
            lastUpdate: Date.now()
          };
          
          await redis.sendCommand([
            'JSON.SET', contextKey, '$', JSON.stringify(updatedContext)
          ]);
          return updatedContext;
          
        case 'set_identity':
          // Set instance identity
          await redis.sendCommand([
            'JSON.SET', contextKey, '$.identity', JSON.stringify(data)
          ]);
          await redis.sendCommand([
            'JSON.SET', contextKey, '$.lastUpdate', Date.now().toString()
          ]);
          return { success: true, identity: data };
          
        case 'set_task':
          // Set current task
          await redis.sendCommand([
            'JSON.SET', contextKey, '$.currentTask', JSON.stringify(data)
          ]);
          await redis.sendCommand([
            'JSON.SET', contextKey, '$.lastUpdate', Date.now().toString()
          ]);
          return { success: true, currentTask: data };
          
        case 'add_goal':
          // Add a goal
          await redis.sendCommand([
            'JSON.ARRAPPEND', contextKey, '$.goals', JSON.stringify(data)
          ]);
          return { success: true, goal: data };
          
        case 'update_curiosity':
          // Update curiosity items
          await redis.sendCommand([
            'JSON.SET', contextKey, '$.curiosity', JSON.stringify(data)
          ]);
          return { success: true, curiosity: data };
          
        default:
          throw new Error(`Unknown action: ${action}`);
      }
    };
  }
};