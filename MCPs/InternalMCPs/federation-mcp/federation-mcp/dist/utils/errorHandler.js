import { logger } from './logger.js';
export class FederationError extends Error {
    errorType;
    context;
    retryable;
    constructor(message, errorType = 'UNKNOWN_ERROR', context, retryable = false) {
        super(message);
        this.name = 'FederationError';
        this.errorType = errorType;
        this.context = context;
        this.retryable = retryable;
    }
}
export class TimeoutError extends FederationError {
    constructor(operation, timeout, context) {
        super(`Operation '${operation}' timed out after ${timeout}ms`, 'TIMEOUT_ERROR', { ...context, operation, timeout }, true);
    }
}
export class AgentUnavailableError extends FederationError {
    constructor(agent, context) {
        super(`Agent '${agent}' is not available`, 'AGENT_UNAVAILABLE', { ...context, agent }, true);
    }
}
export class TaskExecutionError extends FederationError {
    constructor(agent, message, context) {
        super(`Task execution failed on ${agent}: ${message}`, 'TASK_EXECUTION_ERROR', { ...context, agent }, false);
    }
}
export class ConfigurationError extends FederationError {
    constructor(message, context) {
        super(`Configuration error: ${message}`, 'CONFIGURATION_ERROR', context, false);
    }
}
export class ErrorHandler {
    static createErrorResponse(error, includeStack = false) {
        const response = {
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
    static async handleWithRetry(operation, maxRetries = 3, delayMs = 1000, context) {
        let lastError;
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                return await operation();
            }
            catch (error) {
                lastError = error;
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
    static isRetryable(error) {
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
    static logError(error, context) {
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
//# sourceMappingURL=errorHandler.js.map