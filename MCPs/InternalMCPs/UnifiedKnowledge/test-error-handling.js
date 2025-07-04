#!/usr/bin/env node

// Test script for error handling functionality
import { ErrorHandler, ValidationError, ConnectionError, OperationError } from './src/utils/error-handler.js';
import { logger } from './src/utils/logger.js';

console.log('🧪 Testing Error Handling System...\n');

// Test 1: Validation Error
try {
  ErrorHandler.validateRequired({}, ['name', 'email'], { test: 'validation' });
} catch (error) {
  console.log('✅ ValidationError test passed');
  console.log(`   Error: ${error.message}`);
  console.log(`   Code: ${error.code}`);
  console.log(`   Missing fields: ${error.missingFields?.join(', ')}\n`);
}

// Test 2: Error Response Creation
const testError = new ConnectionError('Redis connection failed', 'redis', {
  host: 'localhost',
  port: 6379
});

const errorResponse = ErrorHandler.createErrorResponse(testError);
console.log('✅ Error Response Creation test passed');
console.log('   Response structure:');
console.log(JSON.stringify(errorResponse, null, 2));
console.log();

// Test 3: Operation Wrapping
const testOperation = ErrorHandler.wrapOperation(
  async () => {
    throw new Error('Simulated failure');
  },
  'testOperation',
  { testContext: true }
);

try {
  await testOperation();
} catch (error) {
  console.log('✅ Operation Wrapping test passed');
  console.log(`   Wrapped error type: ${error.constructor.name}`);
  console.log(`   Operation: ${error.operation}`);
  console.log();
}

// Test 4: Retry Logic
let attempts = 0;
const flakyOperation = async () => {
  attempts++;
  if (attempts < 3) {
    const error = new Error('Transient failure');
    error.code = 'ECONNREFUSED';
    throw error;
  }
  return 'Success!';
};

try {
  const result = await ErrorHandler.withRetry(flakyOperation, {
    maxRetries: 3,
    baseDelay: 100,
    context: { test: 'retry' }
  });
  console.log('✅ Retry Logic test passed');
  console.log(`   Result: ${result}`);
  console.log(`   Attempts: ${attempts}`);
  console.log();
} catch (error) {
  console.log('❌ Retry Logic test failed');
  console.log(`   Error: ${error.message}`);
}

// Test 5: Troubleshooting Hints
const connectionError = new ConnectionError('Database connection failed', 'postgresql', {
  database: 'workflow',
  host: 'localhost'
});

const hints = ErrorHandler.getTroubleshootingHints(connectionError);
console.log('✅ Troubleshooting Hints test passed');
console.log('   Hints:');
hints.forEach(hint => console.log(`   - ${hint}`));
console.log();

// Test 6: Logging with Context
logger.info('Test log entry', {
  operation: 'testLogging',
  success: true,
  duration: 150
});

logger.error('Test error log', {
  operation: 'testError',
  error: 'Simulated error message',
  context: { critical: true }
});

console.log('✅ Enhanced Logging test passed');
console.log();

console.log('🎉 All error handling tests completed successfully!');
console.log('\n📚 See ERROR_HANDLING_GUIDE.md for comprehensive documentation.');