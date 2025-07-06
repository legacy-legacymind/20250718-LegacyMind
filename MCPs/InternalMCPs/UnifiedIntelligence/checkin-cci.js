#!/usr/bin/env node

// Direct check-in script for CCI
import { UnifiedIntelligence } from './src/core/unified-intelligence.js';
import { createThinkTool } from './src/tools/think-tool.js';
import { redisManager } from './src/shared/redis-manager.js';
import { logger } from './src/utils/logger.js';

async function performCCICheckIn() {
    // Set environment variables
    process.env.REDIS_PASSWORD = 'legacymind_redis_pass';
    process.env.REDIS_URL = 'redis://:legacymind_redis_pass@localhost:6379';

    console.log('\n=== CCI Check-in Process ===');
    console.log('Date:', new Date().toISOString());

    try {
        // Initialize UnifiedIntelligence (which will handle Redis connections)
        console.log('\nInitializing UnifiedIntelligence...');
        const intelligence = new UnifiedIntelligence({
            redisUrl: process.env.REDIS_URL
        });
        
        // Wait a moment for Redis to connect
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        console.log('✓ UnifiedIntelligence initialized');

        // Create think tool
        const thinkTool = createThinkTool(intelligence);

        // Perform check-in
        console.log('\nPerforming CCI check-in...');
        const checkInResult = await thinkTool.handler({
            action: 'check_in',
            identity: {
                name: 'CCI',
                id: 'cci-' + Date.now(),
                type: 'intelligence',
                role: 'Intelligence Specialist'
            }
        });

        console.log('✓ Check-in successful:', checkInResult);

        // Capture initial thought
        console.log('\nCapturing initial thought...');
        const thought = `CCI check-in completed at ${new Date().toISOString()}. Ready to assist with UnifiedIntelligence MCP development. Current working directory: ${process.cwd()}`;
        
        const captureResult = await thinkTool.handler({
            action: 'capture',
            thought: thought,
            options: {
                confidence: 0.95,
                tags: ['check-in', 'CCI', 'start', 'unified-intelligence']
            }
        });

        console.log('✓ Thought captured:', captureResult);

        // Get status
        console.log('\nGetting current status...');
        const statusResult = await thinkTool.handler({
            action: 'status'
        });

        console.log('✓ Current status:', JSON.stringify(statusResult, null, 2));

        console.log('\n=== CCI Check-in Complete ===');
        console.log('Instance ID:', checkInResult.instanceId);
        console.log('Next steps:', checkInResult.next_steps);

    } catch (error) {
        console.error('\n❌ Error during check-in:', error);
        logger.error('Check-in failed:', error);
    } finally {
        // Clean up
        process.exit(0);
    }
}

// Run the check-in
performCCICheckIn().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
});