// src/utils/logger.js
const LOG_LEVEL = process.env.LOG_LEVEL || 'info';

const levels = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

const currentLevel = levels[LOG_LEVEL] ?? levels.info;

const logger = {
    debug: (...args) => {
        if (currentLevel <= levels.debug) {
            console.error('[DEBUG]', ...args)
        }
    },
    info: (...args) => {
        if (currentLevel <= levels.info) {
            console.error('[INFO]', ...args)
        }
    },
    warn: (...args) => {
        if (currentLevel <= levels.warn) {
            console.error('[WARN]', ...args)
        }
    },
    error: (...args) => {
        if (currentLevel <= levels.error) {
            console.error('[ERROR]', ...args)
        }
    },
  };
  
  export { logger };
  