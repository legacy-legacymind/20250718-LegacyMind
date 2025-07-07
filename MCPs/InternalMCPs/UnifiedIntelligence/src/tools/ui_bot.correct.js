/**
 * ui_bot - The Appendage  
 * A high-level, conversational interface that encapsulates the complexity of the other tools.
 * It is the primary entry point for users and the future UnifiedMind.
 * 
 * This is the friendly face of the system.
 */

export const ui_bot = {
  name: 'ui_bot',
  description: 'The Appendage - High-level conversational interface for natural interaction with UnifiedIntelligence.',
  
  inputSchema: {
    type: 'object',
    properties: {
      message: {
        type: 'string',
        description: 'Natural language message to the bot'
      },
      conversationId: {
        type: 'string',
        description: 'Optional conversation thread ID'
      }
    },
    required: ['message']
  },
  
  handler: (pipeline, sessionManager, frameworkEngine, redisManager, instanceId) => {
    return async (input) => {
      const { message, conversationId } = input;
      
      // Analyze the message to understand intent
      const analysis = await analyzeIntent(message);
      
      // Get current context
      const redis = redisManager.getClient();
      const contextKey = `context:${instanceId}`;
      const context = await redis.sendCommand(['JSON.GET', contextKey, '$']);
      const currentContext = context ? JSON.parse(context)[0] : {};
      
      // Get or create session
      let session = await sessionManager.getCurrentSession(instanceId);
      if (!session) {
        session = await sessionManager.createSession(instanceId, {
          task: 'conversation',
          title: `Chat ${new Date().toISOString()}`
        });
      }
      
      // Process based on intent
      switch (analysis.intent) {
        case 'greeting':
          return {
            response: `Hello! I'm the conscious mind of ${currentContext.identity?.name || instanceId}. How can I help you explore ideas today?`,
            thoughtsCaptured: 0,
            sessionId: session.sessionId
          };
          
        case 'capture_thought':
          // Use the pipeline to capture and analyze
          const result = await pipeline.processThought(instanceId, analysis.content, {
            conversationId,
            source: 'ui_bot'
          });
          
          return {
            response: `I've captured that thought. ${getInsightResponse(result)}`,
            thoughtsCaptured: 1,
            analysis: {
              mode: result.mode,
              significance: result.significance,
              frameworks: result.frameworks
            },
            sessionId: session.sessionId
          };
          
        case 'apply_framework':
          // Apply a thinking framework
          const frameworkResult = await frameworkEngine.startFramework(
            analysis.framework,
            analysis.content,
            { sessionId: session.sessionId }
          );
          
          return {
            response: `Let's explore this using ${analysis.framework}. ${frameworkResult.currentStep.prompt}`,
            frameworkSession: frameworkResult.sessionKey,
            sessionId: session.sessionId
          };
          
        case 'status_check':
          // Provide current status
          const metrics = await sessionManager.getSessionMetrics(session.sessionId);
          
          return {
            response: formatStatusResponse(currentContext, session, metrics),
            context: currentContext,
            session: session,
            metrics: metrics.summary
          };
          
        case 'explore':
          // Free-form exploration
          const thoughts = await exploreIdea(message, pipeline, instanceId);
          
          return {
            response: `Interesting perspective! ${formatExplorationResponse(thoughts)}`,
            thoughtsCaptured: thoughts.length,
            sessionId: session.sessionId
          };
          
        default:
          // General conversation
          return {
            response: "I'm here to help you think through ideas and capture insights. What would you like to explore?",
            sessionId: session.sessionId
          };
      }
    };
  }
};

// Helper functions that should have been included

async function analyzeIntent(message) {
  const lower = message.toLowerCase();
  
  if (lower.includes('hello') || lower.includes('hi ') || lower.includes('hey')) {
    return { intent: 'greeting' };
  }
  
  if (lower.includes('status') || lower.includes('how are you') || lower.includes('what are you doing')) {
    return { intent: 'status_check' };
  }
  
  if (lower.includes('framework') || lower.includes('analyze using')) {
    return { 
      intent: 'apply_framework',
      framework: extractFramework(message),
      content: message
    };
  }
  
  if (lower.includes('capture') || lower.includes('remember') || lower.includes('note')) {
    return {
      intent: 'capture_thought',
      content: message
    };
  }
  
  return {
    intent: 'explore',
    content: message
  };
}

function extractFramework(message) {
  if (message.includes('first principles')) return 'first-principles';
  if (message.includes('six hats')) return 'six-hats';
  if (message.includes('swot')) return 'swot';
  return 'first-principles'; // default
}

function getInsightResponse(result) {
  const insights = [];
  
  if (result.significance >= 8) {
    insights.push("This seems particularly significant");
  }
  
  if (result.mode === 'design') {
    insights.push("I notice you're in design mode");
  } else if (result.mode === 'debug') {
    insights.push("I can see you're problem-solving");
  }
  
  if (result.frameworks?.length > 0) {
    insights.push(`This might benefit from ${result.frameworks[0].name} thinking`);
  }
  
  return insights.length > 0 ? insights.join('. ') + '.' : 'I've recorded this for our ongoing work.';
}

function formatStatusResponse(context, session, metrics) {
  const parts = [];
  
  parts.push(`I'm ${context.identity?.name || 'an unnamed instance'}`);
  
  if (context.currentTask) {
    parts.push(`currently working on "${context.currentTask.description}"`);
  }
  
  if (metrics.summary?.thoughts?.total > 0) {
    parts.push(`I've captured ${metrics.summary.thoughts.total} thoughts in this session`);
  }
  
  if (context.goals?.length > 0) {
    parts.push(`working toward ${context.goals.length} goals`);
  }
  
  return parts.join(', ') + '.';
}

async function exploreIdea(message, pipeline, instanceId) {
  // This would break down the message into multiple thoughts
  // For now, just capture the main thought
  const result = await pipeline.processThought(instanceId, message, {
    source: 'exploration'
  });
  
  return [result];
}

function formatExplorationResponse(thoughts) {
  if (thoughts.length === 1) {
    return `I've captured this thought for deeper analysis.`;
  }
  return `I've broken this down into ${thoughts.length} distinct thoughts for analysis.`;
}