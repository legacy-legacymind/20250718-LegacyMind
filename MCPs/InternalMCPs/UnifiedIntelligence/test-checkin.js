#!/usr/bin/env node

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { spawn } from 'child_process';

async function main() {
    const transport = new StdioClientTransport({
        command: 'node',
        args: ['src/index.js'],
        env: {
            ...process.env,
            REDIS_PASSWORD: 'legacymind_redis_pass',
            REDIS_URL: 'redis://:legacymind_redis_pass@localhost:6379'
        }
    });

    const client = new Client({
        name: 'test-client',
        version: '1.0.0'
    }, {
        capabilities: {
            tools: {}
        }
    });

    await client.connect(transport);
    console.log('Connected to UnifiedIntelligence MCP');

    try {
        // Perform check-in for CCI
        const checkInResult = await client.callTool('ui_think', {
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
        const captureResult = await client.callTool('ui_think', {
            action: 'capture',
            thought: 'CCI check-in completed successfully at ' + new Date().toISOString() + '. Ready to begin work on UnifiedIntelligence MCP enhancements.',
            options: {
                confidence: 0.9,
                tags: ['check-in', 'initialization', 'CCI']
            }
        });

        console.log('\nCapture Result:', JSON.stringify(captureResult, null, 2));

        // Get status
        const statusResult = await client.callTool('ui_think', {
            action: 'status'
        });

        console.log('\nStatus Result:', JSON.stringify(statusResult, null, 2));

    } catch (error) {
        console.error('Error:', error);
    } finally {
        await client.close();
    }
}

main().catch(console.error);