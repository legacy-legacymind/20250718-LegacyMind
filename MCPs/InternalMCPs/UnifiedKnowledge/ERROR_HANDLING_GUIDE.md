# Error Handling Guide - UnifiedWorkflow MCP

## Overview

This document describes the comprehensive error handling system implemented in the UnifiedWorkflow MCP. The system provides consistent error patterns, detailed logging, graceful degradation, and recovery mechanisms.

## Error Types

### Custom Error Classes

#### 1. WorkflowError (Base Class)
Base error class for all workflow-related errors.
```javascript
new WorkflowError(message, code, context)
```

#### 2. ValidationError
Used for input validation failures.
```javascript
new ValidationError(message, missingFields, context)
```

#### 3. ConnectionError
Used for service connection failures.
```javascript
new ConnectionError(message, service, context)
```

#### 4. OperationError
Used for general operation failures.
```javascript
new OperationError(message, operation, context)
```

#### 5. TransactionError
Used for database transaction failures.
```javascript
new TransactionError(message, transactionId, context)
```

#### 6. ExternalServiceError
Used for external service failures (Redis, PostgreSQL, Qdrant, OpenAI).
```javascript
new ExternalServiceError(message, service, originalError, context)
```

## Error Codes

### Validation Errors
- `MISSING_REQUIRED_FIELDS`: Required fields are missing
- `INVALID_FORMAT`: Data format is invalid
- `INVALID_STATUS`: Invalid status value

### Connection Errors
- `REDIS_CONNECTION_FAILED`: Redis connection failed
- `POSTGRES_CONNECTION_FAILED`: PostgreSQL connection failed
- `QDRANT_CONNECTION_FAILED`: Qdrant connection failed
- `OPENAI_CONNECTION_FAILED`: OpenAI API connection failed

### Operation Errors
- `TICKET_NOT_FOUND`: Ticket not found
- `PROJECT_NOT_FOUND`: Project not found
- `DOCUMENT_NOT_FOUND`: Document not found
- `OPERATION_FAILED`: General operation failure

### Transaction Errors
- `TRANSACTION_NOT_FOUND`: Transaction ID not found
- `TRANSACTION_COMMIT_FAILED`: Transaction commit failed
- `TRANSACTION_ROLLBACK_FAILED`: Transaction rollback failed

### External Service Errors
- `QDRANT_OPERATION_FAILED`: Qdrant operation failed
- `OPENAI_EMBEDDING_FAILED`: OpenAI embedding failed
- `REDIS_OPERATION_FAILED`: Redis operation failed
- `POSTGRES_QUERY_FAILED`: PostgreSQL query failed

## Error Handler Utilities

### 1. Field Validation
```javascript
ErrorHandler.validateRequired(data, requiredFields, context)
```
Validates that required fields are present in the data object.

### 2. Operation Wrapping
```javascript
const wrappedOperation = ErrorHandler.wrapOperation(operation, operationName, context);
```
Wraps operations with standardized error handling and logging.

### 3. Retry Logic
```javascript
await ErrorHandler.withRetry(operation, {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 10000,
  backoffFactor: 2,
  retryableErrors: ['ECONNREFUSED', 'ENOTFOUND', 'ETIMEDOUT'],
  context: {}
});
```

### 4. Connection Error Handling
```javascript
ErrorHandler.handleConnectionError(service, error, context)
```
Creates standardized connection errors with troubleshooting hints.

### 5. External Service Error Handling
```javascript
ErrorHandler.handleExternalServiceError(service, operation, error, context)
```
Creates standardized external service errors with context.

### 6. Error Response Creation
```javascript
ErrorHandler.createErrorResponse(error, includeStack = false)
```
Creates standardized error responses for API clients.

## Logging Enhancements

### Structured Logging
All logging now includes contextual information:

```javascript
logger.info('Operation completed', {
  operation: 'createTicket',
  ticketId: 'ABC123',
  duration: 250,
  success: true
});

logger.error('Operation failed', {
  operation: 'embedTicket',
  ticketId: 'ABC123',
  error: error.message,
  stack: error.stack,
  context: error.context
});
```

### Log Levels
- **INFO**: Successful operations and important events
- **ERROR**: Failed operations and errors
- **WARN**: Non-critical issues and degraded functionality
- **DEBUG**: Detailed operation information (development only)
- **TRACE**: Very detailed execution flow (development only)

## Service-Specific Error Handling

### Redis Manager
- Connection retry with exponential backoff
- Operation retry for transient failures
- Graceful degradation when Redis is unavailable
- Comprehensive cleanup on failures

### PostgreSQL Manager
- Transaction management with proper rollback
- Connection pooling error handling
- Query retry for transient failures
- Active transaction tracking and cleanup

### Qdrant Manager
- Optional embedding operations (can be disabled)
- Graceful degradation when Qdrant is unavailable
- OpenAI API retry logic
- Detailed error context for troubleshooting

### Ticket Manager
- Field validation with detailed error messages
- Partial state cleanup on failures
- Comprehensive logging of ticket operations
- Error context preservation

## Error Recovery Mechanisms

### 1. Retry Logic
Automatic retry for transient failures:
- Network timeouts
- Connection refused errors
- Temporary service unavailability

### 2. Graceful Degradation
Non-critical services can fail without stopping core operations:
- Qdrant embedding failures don't prevent ticket creation
- Redis cache misses fall back to database queries
- Logging failures don't interrupt business operations

### 3. Transaction Rollback
Database transactions are properly rolled back on failures:
- Automatic rollback on commit failures
- Force rollback of active transactions on shutdown
- Comprehensive cleanup of partial state

### 4. Partial State Cleanup
Failed operations clean up any partial state:
- Ticket creation failures remove partial Redis entries
- Project creation failures roll back database transactions
- Connection failures properly release resources

## Troubleshooting Hints

The error system provides automatic troubleshooting hints:

### ValidationError
- Lists missing required fields
- Provides format validation guidance

### ConnectionError
- Service-specific connection troubleshooting
- Configuration verification steps

### ExternalServiceError
- Service-specific troubleshooting guides
- Common configuration issues
- Rate limiting and quota guidance

## Testing Error Scenarios

### Unit Tests
Test error conditions for each manager:

```javascript
// Test validation errors
expect(() => ticketManager.create({}))
  .toThrow(ValidationError);

// Test connection errors
mockRedis.connect.mockRejectedValue(new Error('Connection refused'));
expect(() => redisManager.connect())
  .toThrow(ConnectionError);

// Test operation errors
mockRedis.hSet.mockRejectedValue(new Error('Operation failed'));
expect(() => ticketManager.create(validData))
  .toThrow(OperationError);
```

### Integration Tests
Test error recovery and degradation:

```javascript
// Test graceful degradation
await stopQdrant();
const result = await ticketManager.create(validData);
expect(result.success).toBe(true);
expect(result.warnings).toContain('Qdrant embedding skipped');

// Test retry logic
mockTransientFailures(redisManager, 2);
const result = await ticketManager.create(validData);
expect(result.success).toBe(true);
```

## Environment Configuration

### Error Handling Settings
```bash
# Enable detailed error responses (development only)
NODE_ENV=development

# Enable debug logging
DEBUG=true

# Enable trace logging
TRACE=true

# Retry configuration
MAX_RETRIES=3
BASE_DELAY_MS=1000
MAX_DELAY_MS=10000
```

### Service Configuration
```bash
# Redis
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=your_password

# PostgreSQL
DATABASE_URL=postgres://user:pass@localhost:5432/workflow
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=workflow
POSTGRES_USER=workflow_user
POSTGRES_PASSWORD=your_password

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_api_key

# OpenAI
OPENAI_API_KEY=your_api_key
```

## Best Practices

### 1. Error Context
Always provide meaningful context in errors:
```javascript
throw new OperationError(
  'Failed to create ticket',
  'createTicket',
  { ticketId, type, reporter, timestamp }
);
```

### 2. Logging
Use structured logging with appropriate levels:
```javascript
logger.error('Critical operation failed', {
  operation: 'createTicket',
  error: error.message,
  context: { ticketId, type }
});
```

### 3. Recovery
Implement graceful degradation where possible:
```javascript
try {
  await criticalOperation();
} catch (error) {
  logger.warn('Critical operation failed, using fallback', {
    error: error.message
  });
  await fallbackOperation();
}
```

### 4. Cleanup
Always clean up partial state on failures:
```javascript
try {
  await operation();
} catch (error) {
  await cleanup();
  throw error;
}
```

## Monitoring and Alerting

### Error Metrics
Track error rates and types:
- Connection failure rates
- Operation failure rates
- Retry success rates
- Error distribution by type

### Alerting Rules
Set up alerts for:
- High error rates (>5% of operations)
- Connection failures
- Transaction rollback rates
- Service degradation events

### Health Checks
Implement health checks for:
- Service connectivity
- Database transaction health
- Error rate thresholds
- Resource utilization

## Migration from Legacy Error Handling

### Before
```javascript
try {
  await operation();
} catch (error) {
  logger.error('Operation failed:', error);
  throw error;
}
```

### After
```javascript
return ErrorHandler.wrapOperation(async () => {
  await operation();
}, 'operationName', { context })();
```

This migration provides:
- Standardized error types
- Consistent logging format
- Automatic retry logic
- Graceful degradation
- Troubleshooting hints
- Better error context