#!/usr/bin/env node

/**
 * Unit Tests for Refactored InjectTool
 * 
 * Tests the new lightweight, service-oriented inject tool
 * focusing on validation, parsing, and routing logic.
 */

import { InjectTool } from './src/tools/inject-tool.js';

// Mock session manager for testing
class MockSessionManager {
  constructor() {
    this.currentInstanceId = 'TEST';
    this.currentSessionId = 'test-session-123';
    this.contextData = [];
  }

  async addContextData(data) {
    this.contextData.push(data);
    console.log('✓ Context data stored:', data.source);
  }
}

// Test suite
class InjectToolTestSuite {
  constructor() {
    this.passed = 0;
    this.failed = 0;
    this.injectTool = new InjectTool(new MockSessionManager());
  }

  test(name, fn) {
    try {
      console.log(`\n🧪 Testing: ${name}`);
      fn();
      console.log(`✅ PASSED: ${name}`);
      this.passed++;
    } catch (error) {
      console.error(`❌ FAILED: ${name}`);
      console.error(`   Error: ${error.message}`);
      this.failed++;
    }
  }

  async asyncTest(name, fn) {
    try {
      console.log(`\n🧪 Testing: ${name}`);
      await fn();
      console.log(`✅ PASSED: ${name}`);
      this.passed++;
    } catch (error) {
      console.error(`❌ FAILED: ${name}`);
      console.error(`   Error: ${error.message}`);
      this.failed++;
    }
  }

  assertEqual(actual, expected, message = '') {
    if (JSON.stringify(actual) !== JSON.stringify(expected)) {
      throw new Error(`Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}. ${message}`);
    }
  }

  assertTrue(condition, message = '') {
    if (!condition) {
      throw new Error(`Assertion failed. ${message}`);
    }
  }

  async expectError(fn, expectedMessage = null) {
    let errorThrown = false;
    try {
      await fn();
    } catch (error) {
      errorThrown = true;
      if (expectedMessage && !error.message.includes(expectedMessage)) {
        throw new Error(`Expected error containing "${expectedMessage}", got "${error.message}"`);
      }
    }
    if (!errorThrown) {
      throw new Error('Expected an error to be thrown');
    }
  }

  summary() {
    console.log(`\n📊 Test Results:`);
    console.log(`✅ Passed: ${this.passed}`);
    console.log(`❌ Failed: ${this.failed}`);
    console.log(`📈 Success Rate: ${((this.passed / (this.passed + this.failed)) * 100).toFixed(1)}%`);
    
    if (this.failed === 0) {
      console.log(`\n🎉 All tests passed!`);
    } else {
      console.log(`\n⚠️  Some tests failed. Review and fix issues.`);
    }
  }
}

// Run tests
async function runTests() {
  console.log('🚀 Starting InjectTool Refactor Tests\n');
  console.log('Testing the new lightweight, service-oriented architecture');
  console.log('='.repeat(60));

  const suite = new InjectToolTestSuite();

  // Test 1: Input Validation - Valid Cases
  suite.test('Input validation - expert lookup', () => {
    const result = suite.injectTool.validate({
      type: 'expert',
      lookup: 'Docker:Networking'
    });
    
    suite.assertEqual(result.action, 'inject');
    suite.assertEqual(result.type, 'expert');
    suite.assertEqual(result.lookup, 'Docker:Networking');
  });

  suite.test('Input validation - document query', () => {
    const result = suite.injectTool.validate({
      type: 'document',
      query: 'microservices patterns'
    });
    
    suite.assertEqual(result.type, 'document');
    suite.assertEqual(result.query, 'microservices patterns');
  });

  suite.test('Input validation - help action', () => {
    const result = suite.injectTool.validate({
      action: 'help',
      type: 'expert',
      lookup: 'test'
    });
    
    suite.assertEqual(result.action, 'help');
  });

  // Test 2: Input Validation - Error Cases
  await suite.asyncTest('Input validation - missing type', async () => {
    await suite.expectError(() => {
      suite.injectTool.validate({ lookup: 'test' });
    }, 'validation failed');
  });

  await suite.asyncTest('Input validation - both lookup and query', async () => {
    await suite.expectError(() => {
      suite.injectTool.validate({
        type: 'expert',
        lookup: 'test',
        query: 'test'
      });
    }, 'Must provide either');
  });

  await suite.asyncTest('Input validation - neither lookup nor query', async () => {
    await suite.expectError(() => {
      suite.injectTool.validate({
        type: 'expert'
      });
    }, 'Must provide either');
  });

  // Test 3: Lookup Parsing
  suite.test('parseLookup - expert module format', () => {
    const result = suite.injectTool.parseLookup('Docker:Networking');
    
    suite.assertEqual(result, {
      type: 'expert',
      topic: 'Docker',
      module: 'Networking'
    });
  });

  suite.test('parseLookup - document identifier', () => {
    const result = suite.injectTool.parseLookup('DOC-12345');
    
    suite.assertEqual(result, {
      type: 'document',
      identifier: 'DOC-12345'
    });
  });

  suite.test('parseLookup - whitespace handling', () => {
    const result = suite.injectTool.parseLookup('  Redis : Performance  ');
    
    suite.assertEqual(result, {
      type: 'expert',
      topic: 'Redis',
      module: 'Performance'
    });
  });

  suite.test('parseLookup - null input', () => {
    const result = suite.injectTool.parseLookup(null);
    suite.assertEqual(result, null);
  });

  // Test 4: Result Formatting
  suite.test('formatResult - with content', () => {
    const mockResult = {
      content: 'Test content here',
      source: 'Docker:Networking',
      type: 'expert'
    };
    
    const formatted = suite.injectTool.formatResult(mockResult);
    
    suite.assertTrue(formatted.includes('# Injected Knowledge'));
    suite.assertTrue(formatted.includes('**Source**: Docker:Networking'));
    suite.assertTrue(formatted.includes('**Type**: expert'));
    suite.assertTrue(formatted.includes('Test content here'));
  });

  suite.test('formatResult - empty result', () => {
    const formatted = suite.injectTool.formatResult(null);
    suite.assertEqual(formatted, 'No content available');
  });

  suite.test('formatResult - missing content', () => {
    const formatted = suite.injectTool.formatResult({ source: 'test' });
    suite.assertEqual(formatted, 'No content available');
  });

  // Test 5: Help Function
  suite.test('getHelp - returns comprehensive help', () => {
    const help = suite.injectTool.getHelp();
    
    suite.assertEqual(help.tool, 'ui_inject');
    suite.assertTrue(help.usage.expert_lookup !== undefined);
    suite.assertTrue(help.usage.document_search !== undefined);
    suite.assertTrue(help.changes.removed.length > 0);
    suite.assertTrue(help.changes.added.length > 0);
  });

  // Test 6: Execute Method - Help Action
  await suite.asyncTest('execute - help action', async () => {
    const result = await suite.injectTool.execute({
      action: 'help',
      type: 'expert',
      lookup: 'test'
    });
    
    suite.assertEqual(result.tool, 'ui_inject');
    suite.assertTrue(result.description.includes('Lightweight'));
  });

  // Test 7: Execute Method - Service Call (Expected to Fail)
  await suite.asyncTest('execute - expert lookup (service not implemented)', async () => {
    await suite.expectError(async () => {
      await suite.injectTool.execute({
        type: 'expert',
        lookup: 'Docker:Networking'
      });
    }); // Don't check specific error message since it could be rate limiting or service unavailable
  });

  // Test 8: Architecture Validation
  await suite.asyncTest('Architecture - no filesystem imports', async () => {
    // Verify the new implementation doesn't import filesystem modules
    const { readFileSync } = await import('fs');
    const injectToolSource = readFileSync(
      '/Users/samuelatagana/Projects/LegacyMind/MCPs/InternalMCPs/UnifiedIntelligence/src/tools/inject-tool.js',
      'utf8'
    );
    
    suite.assertTrue(!injectToolSource.includes("import { promises as fs }"));
    suite.assertTrue(!injectToolSource.includes("import path"));
    suite.assertTrue(!injectToolSource.includes("redisManager"));
    suite.assertTrue(!injectToolSource.includes("loadFederationContext"));
  });

  suite.test('Architecture - clean constructor', () => {
    // Verify constructor only takes sessionManager
    const tool = new InjectTool(new MockSessionManager());
    suite.assertTrue(tool.sessionManager !== null);
    suite.assertTrue(tool.unifiedKnowledgeClient === null); // Not yet implemented
  });

  // Summary
  suite.summary();
  
  return suite.failed === 0;
}

// Execute tests
runTests().then(success => {
  console.log('\n' + '='.repeat(60));
  if (success) {
    console.log('🎯 All tests passed! The refactor is working correctly.');
    console.log('📋 Ready for integration with UnifiedKnowledge MCP.');
  } else {
    console.log('⚠️  Some tests failed. Please review and fix issues.');
    process.exit(1);
  }
}).catch(error => {
  console.error('\n💥 Test suite crashed:', error);
  process.exit(1);
});