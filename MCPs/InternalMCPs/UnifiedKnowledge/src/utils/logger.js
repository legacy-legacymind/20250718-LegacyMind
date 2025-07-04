// src/utils/logger.js

/**
 * Enhanced logger with contextual information and structured logging
 */
export const logger = {
  info: (message, context = {}) => {
    const logEntry = {
      level: 'INFO',
      timestamp: new Date().toISOString(),
      message,
      ...context
    };
    console.error(`[INFO] ${logEntry.timestamp}: ${message}`, 
      Object.keys(context).length > 0 ? context : '');
  },
  
  error: (message, context = {}) => {
    const logEntry = {
      level: 'ERROR',
      timestamp: new Date().toISOString(),
      message,
      ...context
    };
    console.error(`[ERROR] ${logEntry.timestamp}: ${message}`, 
      Object.keys(context).length > 0 ? context : '');
  },
  
  warn: (message, context = {}) => {
    const logEntry = {
      level: 'WARN',
      timestamp: new Date().toISOString(),
      message,
      ...context
    };
    console.error(`[WARN] ${logEntry.timestamp}: ${message}`, 
      Object.keys(context).length > 0 ? context : '');
  },
  
  debug: (message, context = {}) => {
    if (process.env.NODE_ENV !== 'production' || process.env.DEBUG === 'true') {
      const logEntry = {
        level: 'DEBUG',
        timestamp: new Date().toISOString(),
        message,
        ...context
      };
      console.error(`[DEBUG] ${logEntry.timestamp}: ${message}`, 
        Object.keys(context).length > 0 ? context : '');
    }
  },
  
  trace: (message, context = {}) => {
    if (process.env.NODE_ENV !== 'production' || process.env.TRACE === 'true') {
      const logEntry = {
        level: 'TRACE',
        timestamp: new Date().toISOString(),
        message,
        ...context
      };
      console.error(`[TRACE] ${logEntry.timestamp}: ${message}`, 
        Object.keys(context).length > 0 ? context : '');
    }
  }
};
