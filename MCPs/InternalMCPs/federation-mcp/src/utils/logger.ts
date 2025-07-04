export interface LogContext {
  [key: string]: any;
}

export class Logger {
  private static instance: Logger;
  private debugMode: boolean;

  private constructor() {
    this.debugMode = process.env['DEBUG_MODE'] === 'true' || process.env['NODE_ENV'] !== 'production';
  }

  static getInstance(): Logger {
    if (!Logger.instance) {
      Logger.instance = new Logger();
    }
    return Logger.instance;
  }

  setDebugMode(enabled: boolean): void {
    this.debugMode = enabled;
  }

  private formatMessage(level: string, message: string, context?: LogContext): string {
    const timestamp = new Date().toISOString();
    const contextStr = context ? ` | ${JSON.stringify(context)}` : '';
    return `[${timestamp}] [${level}] ${message}${contextStr}`;
  }

  info(message: string, context?: LogContext): void {
    console.error(this.formatMessage('INFO', message, context));
  }

  debug(message: string, context?: LogContext): void {
    if (this.debugMode) {
      console.error(this.formatMessage('DEBUG', message, context));
    }
  }

  warn(message: string, context?: LogContext): void {
    console.error(this.formatMessage('WARN', message, context));
  }

  error(message: string, context?: LogContext): void {
    console.error(this.formatMessage('ERROR', message, context));
  }

  fatal(message: string, context?: LogContext): void {
    console.error(this.formatMessage('FATAL', message, context));
  }
}

export const logger = Logger.getInstance();