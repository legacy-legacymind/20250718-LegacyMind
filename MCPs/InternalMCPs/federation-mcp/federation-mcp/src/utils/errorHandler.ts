import { logger } from './logger.js';

export interface ErrorContext {
  tool?: string;
  agent?: 'ccmcp' | 'gmcp';
  operation?: string;
  timeout?: number;
  [key: string]: any;
}

export interface ErrorResponse {
  success: false;
  error: string;
  errorType: string;
  context?: ErrorContext;
  timestamp: string;
  retryable?: boolean;
}

export class FederationError extends Error {
  public readonly errorType: string;
  public readonly context?: ErrorContext;
  public readonly retryable: boolean;

  constructor(
    message: string,
    errorType: string = 'UNKNOWN_ERROR',
    context?: ErrorContext,
    retryable: boolean = false
  ) {
    super(message);
    this.name = 'FederationError';
    this.errorType = errorType;
    this.context = context;
    this.retryable = retryable;
  }
}

export class TimeoutError extends FederationError {
  constructor(operation: string, timeout: number, context?: ErrorContext) {
    super(
      `Operation '${operation}' timed out after ${timeout}ms`,
      'TIMEOUT_ERROR',
      { ...context, operation, timeout },
      true
    );
  }
}

export class AgentUnavailableError extends FederationError {
  constructor(agent: 'ccmcp' | 'gmcp', context?: ErrorContext) {
    super(
      `Agent '${agent}' is not available`,
      'AGENT_UNAVAILABLE',
      { ...context, agent },
      true
    );
  }
}

export class TaskExecutionError extends FederationError {
  constructor(agent: 'ccmcp' | 'gmcp', message: string, context?: ErrorContext) {
    super(
      `Task execution failed on ${agent}: ${message}`,
      'TASK_EXECUTION_ERROR',
      { ...context, agent },
      false
    );
  }
}

export class ConfigurationError extends FederationError {
  constructor(message: string, context?: ErrorContext) {
    super(
      `Configuration error: ${message}`,
      'CONFIGURATION_ERROR',
      context,
      false
    );
  }
}

export class ErrorHandler {
  static createErrorResponse(
    error: Error | FederationError,
    includeStack: boolean = false
  ): ErrorResponse {
    const response: ErrorResponse = {
      success: false,
      error: error.message,
      errorType: error instanceof FederationError ? error.errorType : 'UNKNOWN_ERROR',
      timestamp: new Date().toISOString(),
    };

    if (error instanceof FederationError) {
      response.context = error.context;
      response.retryable = error.retryable;
    }

    if (includeStack && error.stack) {
      response.context = { ...response.context, stack: error.stack };
    }

    return response;
  }

  static async handleWithRetry<T>(
    operation: () => Promise<T>,
    maxRetries: number = 3,
    delayMs: number = 1000,
    context?: ErrorContext
  ): Promise<T> {
    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error as Error;
        
        logger.warn(`Operation failed, attempt ${attempt}/${maxRetries}`, {
          error: lastError.message,
          context,
          attempt,
        });

        if (attempt === maxRetries) {
          break;
        }

        // Only retry if it's a retryable error
        if (error instanceof FederationError && !error.retryable) {
          break;
        }

        // Wait before retry
        await new Promise(resolve => setTimeout(resolve, delayMs * attempt));
      }
    }

    throw lastError || new Error('Unknown error occurred during retry');
  }

  static isRetryable(error: Error): boolean {
    if (error instanceof FederationError) {
      return error.retryable;
    }

    // Network errors are generally retryable
    if (error.message.includes('ECONNREFUSED') || 
        error.message.includes('ETIMEDOUT') ||
        error.message.includes('timeout')) {
      return true;
    }

    return false;
  }

  static logError(error: Error, context?: ErrorContext): void {
    const errorData = {
      error: error.message,
      errorType: error instanceof FederationError ? error.errorType : 'UNKNOWN_ERROR',
      context,
    };

    if (error instanceof FederationError) {
      errorData.context = { ...errorData.context, ...error.context };
    }

    logger.error('Federation error occurred', errorData);
  }
}

export { ErrorHandler as default };