#!/usr/bin/env node

import { spawn } from 'child_process';
import readline from 'readline';

// Simple test for enhanced injection
async function runTest() {
    console.log('Starting Simple Injection Test...\n');
    
    // Start the MCP server
    const mcp = spawn('node', ['src/index.js'], {
        stdio: ['pipe', 'pipe', 'inherit'],
        cwd: process.cwd(),
        env: { ...process.env, REDIS_URL: 'redis://:legacymind_redis_pass@localhost:6379' }
    });
    
    // Helper to send JSON-RPC request
    function sendRequest(method, params) {
        const request = {
            jsonrpc: '2.0',
            id: Date.now(),
            method,
            params
        };
        mcp.stdin.write(JSON.stringify(request) + '\n');
        return request.id;
    }
    
    // Helper to wait for response
    function waitForResponse(id) {
        return new Promise((resolve) => {
            const handler = (data) => {
                const lines = data.toString().split('\n');
                for (const line of lines) {
                    if (line.trim()) {
                        try {
                            const response = JSON.parse(line);
                            if (response.id === id) {
                                mcp.stdout.removeListener('data', handler);
                                resolve(response);
                            }
                        } catch (e) {
                            // Not JSON, ignore
                        }
                    }
                }
            };
            mcp.stdout.on('data', handler);
        });
    }
    
    try {
        // Wait for server to start
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        console.log('1. Testing help action...');
        const helpId = sendRequest('tools/call', {
            name: 'ui_inject',
            arguments: { action: 'help' }
        });
        const helpResponse = await waitForResponse(helpId);
        console.log('Help response received:', helpResponse.result?.content?.[0]?.text ? 'SUCCESS' : 'FAILED');
        
        console.log('\nTest completed!');
        
    } catch (error) {
        console.error('Test failed:', error);
    } finally {
        mcp.kill();
        process.exit(0);
    }
}

runTest().catch(console.error);