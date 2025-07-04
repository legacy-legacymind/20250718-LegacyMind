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
export declare class FederationError extends Error {
    readonly errorType: string;
    readonly context?: ErrorContext;
    readonly retryable: boolean;
    constructor(message: string, errorType?: string, context?: ErrorContext, retryable?: boolean);
}
export declare class TimeoutError extends FederationError {
    constructor(operation: string, timeout: number, context?: ErrorContext);
}
export declare class AgentUnavailableError extends FederationError {
    constructor(agent: 'ccmcp' | 'gmcp', context?: ErrorContext);
}
export declare class TaskExecutionError extends FederationError {
    constructor(agent: 'ccmcp' | 'gmcp', message: string, context?: ErrorContext);
}
export declare class ConfigurationError extends FederationError {
    constructor(message: string, context?: ErrorContext);
}
export declare class ErrorHandler {
    static createErrorResponse(error: Error | FederationError, includeStack?: boolean): ErrorResponse;
    static handleWithRetry<T>(operation: () => Promise<T>, maxRetries?: number, delayMs?: number, context?: ErrorContext): Promise<T>;
    static isRetryable(error: Error): boolean;
    static logError(error: Error, context?: ErrorContext): void;
}
export { ErrorHandler as default };
//# sourceMappingURL=errorHandler.d.ts.map