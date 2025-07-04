export interface LogContext {
    [key: string]: any;
}
export declare class Logger {
    private static instance;
    private debugMode;
    private constructor();
    static getInstance(): Logger;
    setDebugMode(enabled: boolean): void;
    private formatMessage;
    info(message: string, context?: LogContext): void;
    debug(message: string, context?: LogContext): void;
    warn(message: string, context?: LogContext): void;
    error(message: string, context?: LogContext): void;
    fatal(message: string, context?: LogContext): void;
}
export declare const logger: Logger;
//# sourceMappingURL=logger.d.ts.map