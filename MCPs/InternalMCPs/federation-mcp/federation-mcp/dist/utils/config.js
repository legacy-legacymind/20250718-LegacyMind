export const defaultConfig = {
    ccmcpTimeout: 120000, // 2 minutes
    gmcpTimeout: 300000, // 5 minutes (Gemini has longer context processing)
    parallelTimeout: 180000, // 3 minutes for parallel execution
    fallbackEnabled: true,
    debugMode: process.env['NODE_ENV'] !== 'production',
};
export const config = {
    ccmcpTimeout: parseInt(process.env['CCMCP_TIMEOUT'] || '') || defaultConfig.ccmcpTimeout,
    gmcpTimeout: parseInt(process.env['GMCP_TIMEOUT'] || '') || defaultConfig.gmcpTimeout,
    parallelTimeout: parseInt(process.env['PARALLEL_TIMEOUT'] || '') || defaultConfig.parallelTimeout,
    fallbackEnabled: process.env['FALLBACK_ENABLED'] !== 'false',
    debugMode: process.env['DEBUG_MODE'] === 'true' || defaultConfig.debugMode,
};
export function validateConfig(config) {
    if (config.ccmcpTimeout < 1000) {
        throw new Error('CCMCP timeout must be at least 1000ms');
    }
    if (config.gmcpTimeout < 1000) {
        throw new Error('GMCP timeout must be at least 1000ms');
    }
    if (config.parallelTimeout < 1000) {
        throw new Error('Parallel timeout must be at least 1000ms');
    }
}
//# sourceMappingURL=config.js.map