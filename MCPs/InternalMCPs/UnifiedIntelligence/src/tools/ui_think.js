/**
 * ui_think - The Engine
 * Low-level, programmatic control over sessions, thought capture, and frameworks
 */

// Framework detection logic
async function detectBestFramework(content) {
  const lowerContent = content.toLowerCase();
  
  // First principles - for fundamental questions
  if (lowerContent.includes('why') || 
      lowerContent.includes('what is the purpose') ||
      lowerContent.includes('fundamentally') ||
      lowerContent.includes('root cause')) {
    return 'first-principles';
  }
  
  // SWOT - for evaluations and comparisons
  if (lowerContent.includes('evaluate') || 
      lowerContent.includes('compare') ||
      lowerContent.includes('pros and cons') ||
      lowerContent.includes('strengths') ||
      lowerContent.includes('weaknesses')) {
    return 'swot';
  }
  
  // Six hats - for multi-perspective analysis
  if (lowerContent.includes('perspectives') || 
      lowerContent.includes('consider all') ||
      lowerContent.includes('different angles') ||
      lowerContent.includes('comprehensive')) {
    return 'six-hats';
  }
  
  // Default - no specific framework
  return 'none';
}

export const ui_think = {
  name: 'ui_think',
  description: 'The Engine - Low-level, programmatic control over sessions, thought capture, and frameworks.',
  
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['capture', 'think', 'check_in', 'apply_framework'],
        description: 'The action to perform'
      },
      content: {
        type: 'string',
        description: 'Thought content for capture/analyze actions'
      },
      sessionData: {
        type: 'object',
        description: 'Session configuration for check_in'
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
        case 'capture': {
          // Direct thought capture with full control
          // Get current active session to determine correct instanceId
          const redis = pipeline.redis;
          const lastInstance = await redis.get('ui:last_instance');
          const activeInstanceId = lastInstance || instanceId;
          return await pipeline.processThought(activeInstanceId, content, {
            ...options,
            lowLevel: true
          });
        }
          
        case 'think': {
          // Enhanced thinking with auto framework and capture
          const redis = pipeline.redis;
          const lastInstance = await redis.get('ui:last_instance');
          const activeInstanceId = lastInstance || instanceId;
          
          // Auto-detect framework if not specified
          let selectedFramework = options?.framework;
          if (!selectedFramework || selectedFramework === 'auto') {
            selectedFramework = await detectBestFramework(content);
          }
          
          // Get significance threshold for this instance
          const contextKey = `${activeInstanceId}:context`;
          const contextData = await redis.sendCommand(['JSON.GET', contextKey, '$']);
          const context = contextData ? JSON.parse(contextData)[0] : {};
          const significanceThreshold = context.significanceThreshold || 6;
          
          // Analyze with framework if applicable
          let analysis;
          if (selectedFramework && selectedFramework !== 'none') {
            analysis = await frameworkEngine.applyFramework(
              selectedFramework,
              content,
              { sessionId: await sessionManager.getCurrentSession(activeInstanceId) }
            );
          } else {
            analysis = await pipeline.analyzeOnly(content, options);
          }
          
          // Auto-capture decision based on significance
          const shouldCapture = options?.capture === 'always' || 
                               (options?.capture !== 'never' && analysis.significance >= significanceThreshold);
          
          if (shouldCapture) {
            const captureResult = await pipeline.processThought(activeInstanceId, content, {
              ...options,
              analysis, // Pass the analysis to avoid re-analyzing
              framework: selectedFramework
            });
            
            return {
              ...analysis,
              captured: true,
              thoughtId: captureResult.thoughtId,
              framework: selectedFramework
            };
          }
          
          return {
            ...analysis,
            captured: false,
            framework: selectedFramework
          };
        }
          
        case 'check_in': {
          // Check in and enable enhanced thinking
          const redis = pipeline.redis;
          const sessionInstanceId = sessionData?.instanceId || instanceId;
          
          // Store significance threshold if provided
          if (sessionData?.significanceThreshold !== undefined) {
            const contextKey = `${sessionInstanceId}:context`;
            const existingContext = await redis.sendCommand(['JSON.GET', contextKey, '$']);
            const context = existingContext ? JSON.parse(existingContext)[0] : {};
            
            await redis.sendCommand([
              'JSON.SET', contextKey, '$', 
              JSON.stringify({
                ...context,
                significanceThreshold: sessionData.significanceThreshold,
                lastUpdate: Date.now()
              })
            ]);
          }
          
          // Create session
          const session = await sessionManager.createSession(sessionInstanceId, sessionData);
          
          // Enable auto-think for this instance (default true)
          const enableAutoThink = sessionData?.enableAutoThink !== false;
          if (enableAutoThink) {
            await redis.set(`${sessionInstanceId}:auto_think_enabled`, '1');
          }
          
          return {
            ...session,
            autoThinkEnabled: enableAutoThink,
            significanceThreshold: sessionData?.significanceThreshold || 6
          };
        }

        case 'apply_framework': {
          // Direct framework application
          const currentSession = await sessionManager.getCurrentSession(instanceId);
          return await frameworkEngine.applyFramework(framework, {
            thoughtId: options.thoughtId,
            sessionId: currentSession?.sessionId,
            content: content
          });
        }
          
        default:
          throw new Error(`Unknown action: ${action}`);
      }
    };
  }
};