// src/utils/error-handler.js
import { logger } from './logger.js';

/**
 * Custom error classes for different types of errors
 */
export class WorkflowError extends Error {
  constructor(message, code = 'WORKFLOW_ERROR', context = {}) {
    super(message);
    this.name = 'WorkflowError';
    this.code = code;
    this.context = context;
    this.timestamp = new Date().toISOString();
    
    // Capture stack trace
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, WorkflowError);
    }
  }

  toJSON() {
    return {
      name: this.name,
      message: this.message,
      code: this.code,
      context: this.context,
      timestamp: this.timestamp,
      stack: this.stack
    };
  }
}

export class ValidationError extends WorkflowError {
  constructor(message, missingFields = [], context = {}) {
    super(message, 'VALIDATION_ERROR', { ...context, missingFields });
    this.name = 'ValidationError';
    this.missingFields = missingFields;
  }
}

export class ConnectionError extends WorkflowError {
  constructor(message, service, context = {}) {
    super(message, 'CONNECTION_ERROR', { ...context, service });
    this.name = 'ConnectionError';
    this.service = service;
  }
}

export class OperationError extends WorkflowError {
  constructor(message, operation, context = {}) {
    super(message, 'OPERATION_ERROR', { ...context, operation });
    this.name = 'OperationError';
    this.operation = operation;
  }
}

export class TransactionError extends WorkflowError {
  constructor(message, transactionId, context = {}) {
    super(message, 'TRANSACTION_ERROR', { ...context, transactionId });
    this.name = 'TransactionError';
    this.transactionId = transactionId;
  }
}

export class ExternalServiceError extends WorkflowError {
  constructor(message, service, originalError, context = {}) {
    super(message, 'EXTERNAL_SERVICE_ERROR', { 
      ...context, 
      service, 
      originalError: originalError?.message || originalError 
    });
    this.name = 'ExternalServiceError';
    this.service = service;
    this.originalError = originalError;
  }
}

/**
 * Error codes for different scenarios
 */
export const ErrorCodes = {
  // Validation errors
  MISSING_REQUIRED_FIELDS: 'MISSING_REQUIRED_FIELDS',
  INVALID_FORMAT: 'INVALID_FORMAT',
  INVALID_STATUS: 'INVALID_STATUS',
  
  // Connection errors
  REDIS_CONNECTION_FAILED: 'REDIS_CONNECTION_FAILED',
  POSTGRES_CONNECTION_FAILED: 'POSTGRES_CONNECTION_FAILED',
  QDRANT_CONNECTION_FAILED: 'QDRANT_CONNECTION_FAILED',
  OPENAI_CONNECTION_FAILED: 'OPENAI_CONNECTION_FAILED',
  
  // Operation errors
  TICKET_NOT_FOUND: 'TICKET_NOT_FOUND',
  PROJECT_NOT_FOUND: 'PROJECT_NOT_FOUND',
  DOCUMENT_NOT_FOUND: 'DOCUMENT_NOT_FOUND',
  OPERATION_FAILED: 'OPERATION_FAILED',
  
  // Transaction errors
  TRANSACTION_NOT_FOUND: 'TRANSACTION_NOT_FOUND',
  TRANSACTION_COMMIT_FAILED: 'TRANSACTION_COMMIT_FAILED',
  TRANSACTION_ROLLBACK_FAILED: 'TRANSACTION_ROLLBACK_FAILED',
  
  // External service errors
  QDRANT_OPERATION_FAILED: 'QDRANT_OPERATION_FAILED',
  OPENAI_EMBEDDING_FAILED: 'OPENAI_EMBEDDING_FAILED',
  REDIS_OPERATION_FAILED: 'REDIS_OPERATION_FAILED',
  POSTGRES_QUERY_FAILED: 'POSTGRES_QUERY_FAILED'
};

/**
 * Error handler utility class
 */
export class ErrorHandler {
  static validateRequired(data, requiredFields, context = {}) {
    const missing = requiredFields.filter(field => !data[field]);
    if (missing.length > 0) {
      throw new ValidationError(
        `Missing required fields: ${missing.join(', ')}`,
        missing,
        context
      );
    }
  }

  static wrapOperation(operation, operationName, context = {}) {
    return async (...args) => {
      const startTime = Date.now();
      const operationId = Math.random().toString(36).substring(2, 15);
      
      logger.debug(`Starting operation: ${operationName}`, {
        operationId,
        context,
        args: args.length
      });

      try {
        const result = await operation(...args);
        const duration = Date.now() - startTime;
        
        logger.debug(`Operation completed: ${operationName}`, {
          operationId,
          duration,
          success: true
        });
        
        return result;
      } catch (error) {
        const duration = Date.now() - startTime;
        
        logger.error(`Operation failed: ${operationName}`, {
          operationId,
          duration,
          error: error.message,
          stack: error.stack,
          context
        });
        
        // Re-throw as OperationError with context
        if (error instanceof WorkflowError) {
          throw error;
        }
        
        throw new OperationError(
          `Operation '${operationName}' failed: ${error.message}`,
          operationName,
          { ...context, originalError: error.message, operationId }
        );
      }
    };
  }

  static async withRetry(operation, options = {}) {
    const {
      maxRetries = 3,
      baseDelay = 1000,
      maxDelay = 10000,
      backoffFactor = 2,
      retryableErrors = ['ECONNREFUSED', 'ENOTFOUND', 'ETIMEDOUT'],
      context = {}
    } = options;

    let lastError;
    let delay = baseDelay;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error;
        
        // Check if error is retryable
        const isRetryable = retryableErrors.some(code => 
          error.message.includes(code) || 
          error.code === code ||
          (error.originalError && error.originalError.code === code)
        );

        if (attempt === maxRetries || !isRetryable) {
          logger.error(`Operation failed after ${attempt + 1} attempts`, {
            context,
            error: error.message,
            isRetryable,
            totalAttempts: attempt + 1
          });
          throw error;
        }

        logger.warn(`Operation failed, retrying in ${delay}ms`, {
          context,
          attempt: attempt + 1,
          maxRetries,
          delay,
          error: error.message
        });

        await new Promise(resolve => setTimeout(resolve, delay));
        delay = Math.min(delay * backoffFactor, maxDelay);
      }
    }

    throw lastError;
  }

  static handleConnectionError(service, error, context = {}) {
    logger.error(`Connection failed for ${service}`, {
      service,
      error: error.message,
      context
    });

    return new ConnectionError(
      `Failed to connect to ${service}: ${error.message}`,
      service,
      { ...context, originalError: error.message }
    );
  }

  static handleExternalServiceError(service, operation, error, context = {}) {
    logger.error(`External service operation failed`, {
      service,
      operation,
      error: error.message,
      context
    });

    return new ExternalServiceError(
      `${service} operation '${operation}' failed: ${error.message}`,
      service,
      error,
      { ...context, operation }
    );
  }

  static createErrorResponse(error, includeStack = false) {
    const response = {
      success: false,
      error: {
        name: error.name || 'Error',
        message: error.message,
        code: error.code || 'UNKNOWN_ERROR',
        timestamp: error.timestamp || new Date().toISOString()
      }
    };

    if (error.context) {
      response.error.context = error.context;
    }

    if (includeStack && error.stack) {
      response.error.stack = error.stack;
    }

    // Add troubleshooting hints
    response.error.troubleshooting = ErrorHandler.getTroubleshootingHints(error);

    return response;
  }

  static getTroubleshootingHints(error) {
    const hints = [];

    if (error instanceof ValidationError) {
      hints.push('Check that all required fields are provided');
      if (error.missingFields?.length > 0) {
        hints.push(`Missing fields: ${error.missingFields.join(', ')}`);
      }
    }

    if (error instanceof ConnectionError) {
      hints.push(`Check ${error.service} connection configuration`);
      hints.push(`Verify ${error.service} service is running and accessible`);
    }

    if (error instanceof ExternalServiceError) {
      switch (error.service) {
        case 'qdrant':
          hints.push('Verify Qdrant service is running');
          hints.push('Check QDRANT_URL and QDRANT_API_KEY configuration');
          break;
        case 'openai':
          hints.push('Verify OpenAI API key is valid');
          hints.push('Check OpenAI API rate limits');
          break;
        case 'redis':
          hints.push('Verify Redis service is running');
          hints.push('Check Redis connection parameters');
          break;
        case 'postgresql':
          hints.push('Verify PostgreSQL service is running');
          hints.push('Check database connection parameters');
          break;
      }
    }

    if (error instanceof TransactionError) {
      hints.push('Transaction may have been rolled back');
      hints.push('Check database connectivity and constraints');
    }

    if (hints.length === 0) {
      hints.push('Check service logs for more details');
      hints.push('Verify all required services are running');
    }

    return hints;
  }
}

/**
 * Async error boundary decorator
 */
export function asyncErrorBoundary(target, propertyKey, descriptor) {
  const originalMethod = descriptor.value;
  
  descriptor.value = async function(...args) {
    try {
      return await originalMethod.apply(this, args);
    } catch (error) {
      const context = {
        class: target.constructor.name,
        method: propertyKey,
        args: args.length
      };
      
      logger.error(`Unhandled error in ${target.constructor.name}.${propertyKey}`, {
        error: error.message,
        stack: error.stack,
        context
      });
      
      throw error;
    }
  };
  
  return descriptor;
}