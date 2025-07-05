export const KeySchema = {
  // Session-related keys
  session: {
    active: (sessionId) => `ui:session:${sessionId}:active`,
    hash: (sessionId) => `ui:session:${sessionId}`,
    list: () => 'ui:sessions:list',
    lastAccess: (sessionId) => `ui:session:${sessionId}:last_access`,
    
    // Session subkeys (for hash fields)
    fields: {
      id: 'id',
      name: 'name',
      startTime: 'start_time',
      lastAccess: 'last_access',
      toolCalls: 'tool_calls',
      tokenCount: 'token_count',
      status: 'status'
    }
  },

  // Tool-related keys
  tools: {
    registered: () => 'ui:tools:registered',
    call: (callId) => `ui:tool:call:${callId}`,
    history: (sessionId) => `ui:session:${sessionId}:tool_history`,
    
    // Tool subkeys (for hash fields)
    fields: {
      name: 'name',
      description: 'description',
      inputSchema: 'input_schema',
      handler: 'handler',
      lastUsed: 'last_used',
      callCount: 'call_count'
    }
  },

  // Message-related keys
  messages: {
    list: (sessionId) => `ui:session:${sessionId}:messages`,
    content: (messageId) => `ui:message:${messageId}`,
    
    // Message subkeys (for hash fields)
    fields: {
      id: 'id',
      role: 'role',
      content: 'content',
      timestamp: 'timestamp',
      toolCallId: 'tool_call_id',
      metadata: 'metadata'
    }
  },

  // Stats-related keys
  stats: {
    global: () => 'ui:stats:global',
    session: (sessionId) => `ui:session:${sessionId}:stats`,
    daily: (date) => `ui:stats:daily:${date}`,
    
    // Stats subkeys (for hash fields)
    fields: {
      totalSessions: 'total_sessions',
      totalToolCalls: 'total_tool_calls',
      totalTokens: 'total_tokens',
      averageSessionDuration: 'avg_session_duration',
      mostUsedTools: 'most_used_tools'
    }
  },

  // Context-related keys
  context: {
    window: (sessionId) => `ui:session:${sessionId}:context`,
    summary: (sessionId) => `ui:session:${sessionId}:summary`,
    
    // Context subkeys (for hash fields)
    fields: {
      messages: 'messages',
      toolResults: 'tool_results',
      summary: 'summary',
      lastUpdate: 'last_update'
    }
  },

  // Error tracking keys
  errors: {
    log: () => 'ui:errors:log',
    bySession: (sessionId) => `ui:session:${sessionId}:errors`,
    
    // Error subkeys (for hash fields)
    fields: {
      message: 'message',
      stack: 'stack',
      timestamp: 'timestamp',
      context: 'context',
      toolName: 'tool_name'
    }
  },

  // Lock keys for distributed operations
  locks: {
    session: (sessionId) => `ui:lock:session:${sessionId}`,
    tool: (toolName) => `ui:lock:tool:${toolName}`,
    global: (resource) => `ui:lock:global:${resource}`
  },

  // Utility functions
  utils: {
    // Generate a key pattern for scanning
    pattern: {
      allSessions: () => 'ui:session:*',
      sessionData: (sessionId) => `ui:session:${sessionId}:*`,
      allTools: () => 'ui:tools:*',
      allErrors: () => 'ui:errors:*'
    },
    
    // TTL configurations (in seconds)
    ttl: {
      session: 86400,      // 24 hours
      message: 3600,       // 1 hour  
      toolCall: 1800,      // 30 minutes
      lock: 30,            // 30 seconds
      error: 604800        // 7 days
    }
  }
};

// Export individual namespaces for convenience
export const sessionKeys = KeySchema.session;
export const toolKeys = KeySchema.tools;
export const messageKeys = KeySchema.messages;
export const statsKeys = KeySchema.stats;
export const contextKeys = KeySchema.context;
export const errorKeys = KeySchema.errors;
export const lockKeys = KeySchema.locks;
export const keyUtils = KeySchema.utils;