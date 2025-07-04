#!/usr/bin/env node

/**
 * UnifiedIntelligence MCP Test Suite
 * Tests all exposed tools using JSON-RPC protocol
 */

import { spawn } from 'child_process';
import readline from 'readline';

// Test configuration
const TIMEOUT = 10000; // 10 seconds per test

// ANSI color codes
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m'
};

// Helper to format JSON-RPC requests
function createRequest(method, params = {}, id = 1) {
  return JSON.stringify({
    jsonrpc: '2.0',
    method,
    params,
    id
  });
}

// Test cases
const testCases = [
  {
    name: 'List Tools',
    request: createRequest('tools/list'),
    validate: (response) => {
      return response.result && 
             Array.isArray(response.result.tools) &&
             response.result.tools.length > 0;
    }
  },
  {
    name: 'UI Think - Capture Thought',
    request: createRequest('tools/call', {
      name: 'ui_think',
      arguments: {
        thought: 'Test thought from UnifiedIntelligence test suite',
        action: 'capture'
      }
    }, 2),
    validate: (response) => {
      return response.result && 
             response.result.content[0].type === 'text' &&
             response.result.content[0].text.includes('captured');
    }
  },
  {
    name: 'UI Think - Session Status',
    request: createRequest('tools/call', {
      name: 'ui_think',
      arguments: {
        action: 'session'
      }
    }, 3),
    validate: (response) => {
      return response.result && 
             response.result.content[0].type === 'text';
    }
  },

];

// Run tests
async function runTests() {
  console.log(`${colors.blue}Starting UnifiedIntelligence MCP Tests...${colors.reset}\n`);

  // Start the MCP server
  const mcp = spawn('node', ['src/index.js'], {
    env: { ...process.env, NODE_ENV: 'test' }
  });

  const rl = readline.createInterface({
    input: mcp.stdout,
    output: process.stdout,
    terminal: false
  });

  let testResults = [];
  let currentTest = 0;

  // Handle server output
  rl.on('line', (line) => {
    try {
      const response = JSON.parse(line);
      
      if (currentTest < testCases.length) {
        const test = testCases[currentTest];
        const passed = test.validate(response);
        
        testResults.push({
          name: test.name,
          passed,
          response
        });

        if (passed) {
          console.log(`${colors.green}✓ ${test.name}${colors.reset}`);
        } else {
          console.log(`${colors.red}✗ ${test.name}${colors.reset}`);
          console.log(`  Response: ${JSON.stringify(response, null, 2)}`);
        }

        currentTest++;
        
        if (currentTest < testCases.length) {
          // Send next test
          mcp.stdin.write(testCases[currentTest].request + '\n');
        } else {
          // All tests complete
          displayResults();
          cleanup();
        }
      }
    } catch (e) {
      // Not JSON, likely server startup message
      if (line.includes('UnifiedIntelligence MCP server started')) {
        console.log(`${colors.yellow}Server started, running tests...${colors.reset}\n`);
        // Send first test
        mcp.stdin.write(testCases[0].request + '\n');
      }
    }
  });

  // Handle errors
  mcp.stderr.on('data', (data) => {
    console.error(`${colors.red}Server error: ${data}${colors.reset}`);
  });

  // Handle server exit
  mcp.on('exit', (code) => {
    if (code !== 0 && currentTest < testCases.length) {
      console.error(`${colors.red}Server exited unexpectedly with code ${code}${colors.reset}`);
      process.exit(1);
    }
  });

  // Display test results
  function displayResults() {
    console.log(`\n${colors.blue}Test Results:${colors.reset}`);
    const passed = testResults.filter(r => r.passed).length;
    const total = testResults.length;
    
    console.log(`${colors.green}Passed: ${passed}/${total}${colors.reset}`);
    
    if (passed < total) {
      console.log(`${colors.red}Failed: ${total - passed}/${total}${colors.reset}`);
      const failed = testResults.filter(r => !r.passed);
      failed.forEach(test => {
        console.log(`\n${colors.red}Failed: ${test.name}${colors.reset}`);
        console.log(`Response: ${JSON.stringify(test.response, null, 2)}`);
      });
    }
  }

  // Cleanup
  function cleanup() {
    rl.close();
    mcp.kill();
    process.exit(testResults.every(r => r.passed) ? 0 : 1);
  }

  // Timeout handling
  setTimeout(() => {
    console.error(`${colors.red}Tests timed out after ${TIMEOUT}ms${colors.reset}`);
    cleanup();
  }, TIMEOUT);
}

// Run tests if executed directly
runTests().catch(err => {
  console.error(`${colors.red}Test runner error: ${err.message}${colors.reset}`);
  process.exit(1);
});
