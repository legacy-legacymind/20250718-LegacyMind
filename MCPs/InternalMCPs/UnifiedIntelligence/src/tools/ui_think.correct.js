/**
 * ui_think - The Engine
 * Low-level, programmatic control over sessions, thought capture, and frameworks
 * 
 * This is what should have been built from the start.
 */

export const ui_think = {
  name: 'ui_think',
  description: 'The Engine - Low-level, programmatic control over sessions, thought capture, and frameworks.',
  
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['capture', 'analyze', 'session_start', 'session_end', 'apply_framework'],
        description: 'The low-level action to perform'
      },
      content: {
        type: 'string',
        description: 'Thought content for capture/analyze actions'
      },
      sessionData: {
        type: 'object',
        description: 'Session configuration for session_start'
      },
      framework: {
        type: 'string', 
        description: 'Framework identifier for apply_framework'
      },
      options: {
        type: 'object',
        description: 'Additional options for the action'
      }
    },
    required: ['action']
  },
  
  handler: (pipeline, sessionManager, frameworkEngine, instanceId) => {
    return async (input) => {
      const { action, content, sessionData, framework, options = {} } = input;
      
      switch (action) {
        case 'capture':
          // Direct thought capture with full control
          return await pipeline.processThought(instanceId, content, {
            ...options,
            lowLevel: true
          });
          
        case 'analyze':
          // Analyze without storing
          return await pipeline.analyzeOnly(content, options);
          
        case 'session_start':
          // Programmatic session control
          return await sessionManager.createSession(instanceId, sessionData);
          
        case 'session_end':
          // End current session
          return await sessionManager.endSession(instanceId);
          
        case 'apply_framework':
          // Direct framework application
          const session = await sessionManager.getCurrentSession(instanceId);
          return await frameworkEngine.applyFramework(framework, {
            thoughtId: options.thoughtId,
            sessionId: session?.sessionId,
            content: content
          });
          
        default:
          throw new Error(`Unknown action: ${action}`);
      }
    };
  }
};