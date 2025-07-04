#!/usr/bin/env node

/**
 * Test script for Federation MCP
 * 
 * This script tests the basic functionality of the Federation MCP
 * including tool registration, parallel execution, and error handling.
 */

import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

class FederationTester {
  constructor() {
    this.serverProcess = null;
    this.testResults = [];
  }

  async runTests() {
    console.log('🚀 Starting Federation MCP Tests...\n');
    
    try {
      // Test 1: Server startup
      await this.testServerStartup();
      
      // Test 2: Tool listing
      await this.testToolListing();
      
      // Test 3: Parallel task execution
      await this.testParallelTask();
      
      // Test 4: Research and build workflow
      await this.testResearchAndBuild();
      
      // Test 5: Error handling
      await this.testErrorHandling();
      
      this.printResults();
      
    } catch (error) {
      console.error('❌ Test suite failed:', error.message);
      process.exit(1);
    } finally {
      if (this.serverProcess) {
        this.serverProcess.kill();
      }
    }
  }

  async testServerStartup() {
    console.log('🔧 Testing server startup...');
    
    return new Promise((resolve, reject) => {
      const serverPath = join(__dirname, '..', 'dist', 'index.js');
      this.serverProcess = spawn('node', [serverPath], {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env, NODE_ENV: 'test' }
      });

      let startupComplete = false;
      
      const timeout = setTimeout(() => {
        if (!startupComplete) {
          this.addResult('Server Startup', false, 'Timeout waiting for server to start');
          reject(new Error('Server startup timeout'));
        }
      }, 10000);

      this.serverProcess.stderr.on('data', (data) => {
        const output = data.toString();
        if (output.includes('Federation MCP Server started successfully')) {
          startupComplete = true;
          clearTimeout(timeout);
          this.addResult('Server Startup', true, 'Server started successfully');
          resolve();
        }
      });

      this.serverProcess.on('error', (error) => {
        clearTimeout(timeout);
        this.addResult('Server Startup', false, `Server failed to start: ${error.message}`);
        reject(error);
      });
    });
  }

  async testToolListing() {
    console.log('🔧 Testing tool listing...');
    
    return new Promise((resolve) => {
      const request = {
        jsonrpc: '2.0',
        id: 1,
        method: 'tools/list',
        params: {}
      };

      this.serverProcess.stdin.write(JSON.stringify(request) + '\n');
      
      let responseReceived = false;
      const timeout = setTimeout(() => {
        if (!responseReceived) {
          this.addResult('Tool Listing', false, 'Timeout waiting for tool list response');
          resolve();
        }
      }, 5000);

      this.serverProcess.stdout.on('data', (data) => {
        try {
          const response = JSON.parse(data.toString());
          if (response.id === 1 && response.result && response.result.tools) {
            responseReceived = true;
            clearTimeout(timeout);
            const tools = response.result.tools;
            const expectedTools = ['parallel_task', 'research_and_build', 'analyze_and_document', 'validation_and_fixes'];
            const hasAllTools = expectedTools.every(tool => tools.some(t => t.name === tool));
            
            this.addResult('Tool Listing', hasAllTools, 
              hasAllTools ? `Found all expected tools: ${tools.map(t => t.name).join(', ')}` 
                         : `Missing tools. Found: ${tools.map(t => t.name).join(', ')}`);
            resolve();
          }
        } catch (error) {
          // Ignore parsing errors, might be partial data
        }
      });
    });
  }

  async testParallelTask() {
    console.log('🔧 Testing parallel task execution...');
    
    return new Promise((resolve) => {
      const request = {
        jsonrpc: '2.0',
        id: 2,
        method: 'tools/call',
        params: {
          name: 'parallel_task',
          arguments: {
            title: 'Test Parallel Task',
            description: 'Test parallel execution of CCMCP and GMCP',
            ccmcpTask: 'Create a simple hello world function',
            gmcpTask: 'Analyze the concept of hello world programs',
            executionStrategy: 'parallel'
          }
        }
      };

      this.serverProcess.stdin.write(JSON.stringify(request) + '\n');
      
      let responseReceived = false;
      const timeout = setTimeout(() => {
        if (!responseReceived) {
          this.addResult('Parallel Task', false, 'Timeout waiting for parallel task response');
          resolve();
        }
      }, 30000); // Longer timeout for parallel execution

      this.serverProcess.stdout.on('data', (data) => {
        try {
          const response = JSON.parse(data.toString());
          if (response.id === 2 && response.result) {
            responseReceived = true;
            clearTimeout(timeout);
            const result = JSON.parse(response.result.content[0].text);
            
            this.addResult('Parallel Task', result.success, 
              result.success ? 'Parallel task executed successfully' : `Task failed: ${result.error}`);
            resolve();
          }
        } catch (error) {
          // Ignore parsing errors
        }
      });
    });
  }

  async testResearchAndBuild() {
    console.log('🔧 Testing research and build workflow...');
    
    return new Promise((resolve) => {
      const request = {
        jsonrpc: '2.0',
        id: 3,
        method: 'tools/call',
        params: {
          name: 'research_and_build',
          arguments: {
            topic: 'REST API Design',
            researchQuery: 'What are the best practices for REST API design?',
            buildInstructions: 'Create a simple REST API structure',
            executionMode: 'sequential'
          }
        }
      };

      this.serverProcess.stdin.write(JSON.stringify(request) + '\n');
      
      let responseReceived = false;
      const timeout = setTimeout(() => {
        if (!responseReceived) {
          this.addResult('Research and Build', false, 'Timeout waiting for research and build response');
          resolve();
        }
      }, 60000); // Even longer timeout for research and build

      this.serverProcess.stdout.on('data', (data) => {
        try {
          const response = JSON.parse(data.toString());
          if (response.id === 3 && response.result) {
            responseReceived = true;
            clearTimeout(timeout);
            const result = JSON.parse(response.result.content[0].text);
            
            this.addResult('Research and Build', result.success, 
              result.success ? 'Research and build workflow completed successfully' : `Workflow failed: ${result.error}`);
            resolve();
          }
        } catch (error) {
          // Ignore parsing errors
        }
      });
    });
  }

  async testErrorHandling() {
    console.log('🔧 Testing error handling...');
    
    return new Promise((resolve) => {
      const request = {
        jsonrpc: '2.0',
        id: 4,
        method: 'tools/call',
        params: {
          name: 'nonexistent_tool',
          arguments: {}
        }
      };

      this.serverProcess.stdin.write(JSON.stringify(request) + '\n');
      
      let responseReceived = false;
      const timeout = setTimeout(() => {
        if (!responseReceived) {
          this.addResult('Error Handling', false, 'Timeout waiting for error response');
          resolve();
        }
      }, 5000);

      this.serverProcess.stdout.on('data', (data) => {
        try {
          const response = JSON.parse(data.toString());
          if (response.id === 4 && response.result && response.result.isError) {
            responseReceived = true;
            clearTimeout(timeout);
            const result = JSON.parse(response.result.content[0].text);
            
            this.addResult('Error Handling', !result.success && result.error, 
              result.error ? 'Error handling works correctly' : 'Error not properly handled');
            resolve();
          }
        } catch (error) {
          // Ignore parsing errors
        }
      });
    });
  }

  addResult(testName, success, message) {
    this.testResults.push({ testName, success, message });
    const status = success ? '✅' : '❌';
    console.log(`${status} ${testName}: ${message}`);
  }

  printResults() {
    console.log('\n📊 Test Results Summary:');
    console.log('=' .repeat(50));
    
    const passed = this.testResults.filter(r => r.success).length;
    const total = this.testResults.length;
    
    this.testResults.forEach(result => {
      const status = result.success ? '✅' : '❌';
      console.log(`${status} ${result.testName}`);
      if (result.message) {
        console.log(`   ${result.message}`);
      }
    });
    
    console.log('=' .repeat(50));
    console.log(`Results: ${passed}/${total} tests passed`);
    
    if (passed === total) {
      console.log('🎉 All tests passed!');
    } else {
      console.log('⚠️  Some tests failed. Please review the results above.');
    }
  }
}

// Run the tests
const tester = new FederationTester();
tester.runTests().catch(console.error);