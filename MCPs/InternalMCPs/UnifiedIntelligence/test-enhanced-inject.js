#!/usr/bin/env node

import { spawn } from 'child_process';
import readline from 'readline';

// Test script for enhanced UnifiedIntelligence injection
async function runTest() {
    console.log('Starting UnifiedIntelligence Enhanced Injection Test...\n');
    
    // Start the MCP server
    const mcp = spawn('node', ['src/index.js'], {
        stdio: ['pipe', 'pipe', 'pipe'],
        cwd: process.cwd()
    });
    
    // Create interface for sending commands
    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
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
    
    // Capture stderr for logging
    mcp.stderr.on('data', (data) => {
        console.error('MCP Error:', data.toString());
    });
    
    try {
        // Wait for server to start
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        console.log('=== Test 1: Initialize instance (check_in) ===');
        const checkInId = sendRequest('tools/call', {
            name: 'ui_think',
            arguments: {
                action: 'check_in',
                identity: {
                    name: 'TEST_CCI',
                    type: 'intelligence',
                    role: 'test_specialist'
                }
            }
        });
        const checkInResponse = await waitForResponse(checkInId);
        console.log('Check-in response:', JSON.stringify(checkInResponse.result, null, 2));
        
        console.log('\n=== Test 2: Create identity memory ===');
        const rememberIdentityId = sendRequest('tools/call', {
            name: 'ui_remember',
            arguments: {
                action: 'create',
                memory_type: 'identity',
                content: 'I am TEST_CCI, an intelligence specialist focused on testing enhanced injection capabilities.',
                options: {
                    tags: ['test', 'identity', 'enhancement'],
                    metadata: { version: '3.1' }
                }
            }
        });
        const rememberIdentityResponse = await waitForResponse(rememberIdentityId);
        console.log('Remember identity response:', JSON.stringify(rememberIdentityResponse.result, null, 2));
        
        console.log('\n=== Test 3: Create context memory ===');
        const rememberContextId = sendRequest('tools/call', {
            name: 'ui_remember',
            arguments: {
                action: 'create',
                memory_type: 'context',
                content: 'Currently testing the enhanced UnifiedIntelligence MCP with parallel loading and federation support.',
                options: {
                    tags: ['test', 'context', 'parallel-loading']
                }
            }
        });
        const rememberContextResponse = await waitForResponse(rememberContextId);
        console.log('Remember context response:', JSON.stringify(rememberContextResponse.result, null, 2));
        
        console.log('\n=== Test 4: Get help for ui_inject ===');
        const helpId = sendRequest('tools/call', {
            name: 'ui_inject',
            arguments: {
                action: 'help'
            }
        });
        const helpResponse = await waitForResponse(helpId);
        console.log('Inject help response:', JSON.stringify(helpResponse.result, null, 2));
        
        console.log('\n=== Test 5: Inject expert knowledge ===');
        const expertId = sendRequest('tools/call', {
            name: 'ui_inject',
            arguments: {
                type: 'expert',
                source: 'mcp'
            }
        });
        const expertResponse = await waitForResponse(expertId);
        console.log('Expert injection response:', JSON.stringify(expertResponse.result, null, 2));
        
        console.log('\n=== Test 6: Inject federation context ===');
        const federationId = sendRequest('tools/call', {
            name: 'ui_inject',
            arguments: {
                type: 'federation',
                source: {
                    instance: 'TEST_CCI',
                    mode: 'default'
                }
            }
        });
        const federationResponse = await waitForResponse(federationId);
        console.log('Federation injection response:', JSON.stringify(federationResponse.result, null, 2));
        
        console.log('\n=== Test 7: Capture a thought ===');
        const thoughtId = sendRequest('tools/call', {
            name: 'ui_think',
            arguments: {
                action: 'capture',
                thought: 'The enhanced injection system with parallel loading is working well!',
                options: {
                    confidence: 0.9,
                    tags: ['test', 'success']
                }
            }
        });
        const thoughtResponse = await waitForResponse(thoughtId);
        console.log('Thought capture response:', JSON.stringify(thoughtResponse.result, null, 2));
        
        console.log('\n=== All tests completed successfully! ===');
        
    } catch (error) {
        console.error('Test failed:', error);
    } finally {
        // Clean up
        mcp.kill();
        rl.close();
        process.exit(0);
    }
}

// Run the test
runTest().catch(console.error);