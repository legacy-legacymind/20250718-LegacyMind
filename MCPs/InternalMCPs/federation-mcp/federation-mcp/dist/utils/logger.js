export class Logger {
    static instance;
    debugMode;
    constructor() {
        this.debugMode = process.env['DEBUG_MODE'] === 'true' || process.env['NODE_ENV'] !== 'production';
    }
    static getInstance() {
        if (!Logger.instance) {
            Logger.instance = new Logger();
        }
        return Logger.instance;
    }
    setDebugMode(enabled) {
        this.debugMode = enabled;
    }
    formatMessage(level, message, context) {
        const timestamp = new Date().toISOString();
        const contextStr = context ? ` | ${JSON.stringify(context)}` : '';
        return `[${timestamp}] [${level}] ${message}${contextStr}`;
    }
    info(message, context) {
        console.error(this.formatMessage('INFO', message, context));
    }
    debug(message, context) {
        if (this.debugMode) {
            console.error(this.formatMessage('DEBUG', message, context));
        }
    }
    warn(message, context) {
        console.error(this.formatMessage('WARN', message, context));
    }
    error(message, context) {
        console.error(this.formatMessage('ERROR', message, context));
    }
    fatal(message, context) {
        console.error(this.formatMessage('FATAL', message, context));
    }
}
export const logger = Logger.getInstance();
//# sourceMappingURL=logger.js.map