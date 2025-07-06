#!/usr/bin/env node

import { UnifiedIntelligence } from './src/index.js';
import { createThinkTool } from './src/tools/think-tool.js';

async function main() {
    // Set environment variables
    process.env.REDIS_PASSWORD = 'legacymind_redis_pass';
    process.env.REDIS_URL = 'redis://:legacymind_redis_pass@localhost:6379';

    // Initialize UnifiedIntelligence
    const intelligence = new UnifiedIntelligence();
    await intelligence.initialize();

    console.log('UnifiedIntelligence initialized');

    // Create think tool
    const thinkTool = createThinkTool(intelligence);

    try {
        // Perform check-in for CCI
        console.log('\nPerforming check-in for CCI...');
        const checkInResult = await thinkTool.handler({
            action: 'check_in',
            identity: {
                name: 'CCI',
                id: 'cci-001',
                type: 'intelligence',
                role: 'Intelligence Specialist'
            }
        });

        console.log('\nCheck-in Result:', JSON.stringify(checkInResult, null, 2));

        // Capture a thought
        console.log('\nCapturing initial thought...');
        const captureResult = await thinkTool.handler({
            action: 'capture',
            thought: 'CCI check-in completed successfully at ' + new Date().toISOString() + '. Ready to begin work on UnifiedIntelligence MCP enhancements as the Intelligence Specialist.',
            options: {
                confidence: 0.9,
                tags: ['check-in', 'initialization', 'CCI', 'start']
            }
        });

        console.log('\nCapture Result:', JSON.stringify(captureResult, null, 2));

        // Get status
        console.log('\nGetting current status...');
        const statusResult = await thinkTool.handler({
            action: 'status'
        });

        console.log('\nStatus Result:', JSON.stringify(statusResult, null, 2));

    } catch (error) {
        console.error('Error:', error);
    } finally {
        // Clean up
        await intelligence.cleanup();
        process.exit(0);
    }
}

main().catch(console.error);