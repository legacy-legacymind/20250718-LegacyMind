# UnifiedIntelligence MCP

## Overview

The `UnifiedIntelligence` MCP is the core reasoning and thinking layer for the LegacyMind Federation. It provides a sophisticated `ui_think` tool designed to capture, analyze, and persist thoughts in a structured and intelligent way.

The core philosophy is **"If the user has to call it manually, we've failed."** To this end, persistence, pattern analysis, session management, and framework guidance are all handled automatically by the MCP.

## Features

- **Automatic Dual-Write Persistence**: Thoughts are saved to PostgreSQL for structured storage and to Qdrant for semantic vector search.
- **Automatic Session Management**: Thinking sessions are created and managed automatically per instance.
- **Automatic Mode Detection**: The MCP automatically detects the mode of a thought (e.g., `debug`, `design`, `learn`).
- **Automatic Pattern Analysis**: The system analyzes recent thoughts to detect patterns like "thinking loops" or "confusion."
- **Thinking Frameworks**: Provides guidance based on established thinking methodologies like OODA Loop and the Socratic Method.
- **Automatic Context Injection**: Delivers relevant context, such as previous thoughts and framework guidance, to the user.

## Tools

### `ui_think`

The primary tool for all thinking-related activities.

**Actions:**

- `capture` (default): Captures a thought and triggers all automatic behaviors.
- `status`: Shows the status of the current thinking session.
- `framework`: Lists available thinking frameworks.
- `session`: Manages the thinking session (not fully implemented).
- `help`: Provides help information for the tool.

**Example Usage:**

```
ui_think({
  action: "capture",
  thought: "I need to figure out why the database connection is failing.",
  options: {
    instance: "cc",
    confidence: 0.9,
    tags: ["database", "debugging"]
  }
})
```

## Architecture

The MCP is built with a modular architecture:

- `index.js`: The main server entry point.
- `core/unified-intelligence.js`: The central class that orchestrates all logic.
- `core/persistence.js`: Handles all database interactions (PostgreSQL and Qdrant).
- `core/session-manager.js`: Manages the lifecycle of thinking sessions.
- `core/mode-detector.js`: Detects the mode of a thought.
- `core/pattern-analyzer.js`: Analyzes thought patterns.
- `core/framework-engine.js`: Manages thinking frameworks.
- `core/context-injector.js`: Provides contextual information to the user.

## Setup and Installation

1.  **Install Dependencies:**
    ```bash
    npm install
    ```

2.  **Environment Variables:**
    Create a `.env` file in the root of this MCP's directory with the following variables:
    ```
    DATABASE_URL=postgresql://user:password@host:port/database
    QDRANT_URL=http://host:port
    # QDRANT_API_KEY=your_qdrant_api_key (if needed)
    ```

3.  **Run the MCP:**
    The MCP is designed to be run via the MCP SDK, typically through a client like Claude Desktop or a containerized setup. To run it directly for testing:
    ```bash
    node src/index.js
    ```

## Containerization

This MCP is designed to be containerized. Refer to the system's `docker-compose.yml` file and the `MCP Containerization Guide` for instructions on how to build and run it as a Docker container.

## Testing

Run the test suite:
```bash
npm test
```

For continuous testing during development:
```bash
npm run test:watch
```

## Version History

### Recent Updates

- **July 3, 2025**: Upgraded Qdrant client from 1.11.0 to 1.14.1 for compatibility with updated database infrastructure
  - Updated health monitor to use `versionInfo()` instead of deprecated `getClusterInfo()` method
  - All core Qdrant operations (upsert, search, scroll, delete, collections) remain fully compatible
  - No breaking changes for persistence layer functionality

## Deployment Checklist

- [ ] Ensure all environment variables are set in `.env` or deployment environment
- [ ] Verify database connectivity (PostgreSQL and Redis)
- [ ] Verify Qdrant connectivity if using vector search
- [ ] Run test suite to ensure all tools are functioning
- [ ] Check Docker image builds successfully
- [ ] Verify network connectivity in containerized environment
- [ ] Monitor logs for any startup errors

## Security Considerations

- **Database Credentials**: Never commit database credentials to version control
- **API Keys**: Store API keys securely in environment variables
- **Network Isolation**: When containerized, ensure proper network isolation
- **Input Validation**: All tool inputs are validated before processing
- **SQL Injection**: Using parameterized queries to prevent SQL injection
- **Rate Limiting**: Consider implementing rate limiting for production deployments

## Performance Optimization

- **Connection Pooling**: Database connections are pooled for efficiency
- **Batch Processing**: Thoughts can be processed in batches (configurable via `THOUGHT_BATCH_SIZE`)
- **Session Cleanup**: Automatic cleanup of old sessions (configurable via `SESSION_CLEANUP_INTERVAL`)
- **Caching**: Redis is used for session caching with configurable TTL
- **Query Optimization**: Database queries are optimized with proper indexes

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check `DATABASE_URL` is correctly formatted
   - Verify PostgreSQL is running and accessible
   - Check network connectivity if using containers

2. **Redis Connection Errors**
   - Verify `REDIS_URL` is correct
   - Ensure Redis server is running
   - Check for firewall/network issues

3. **Qdrant Connection Errors**
   - Verify `QDRANT_URL` and `QDRANT_API_KEY`
   - Check Qdrant server health
   - Note: Embedding generation requires `OPENAI_API_KEY`

4. **Tool Execution Errors**
   - Check logs for detailed error messages
   - Verify all required environment variables are set
   - Run test suite to isolate issues

### Debug Mode

Enable debug logging by setting:
```bash
DEBUG=true
```

## Example JSON-RPC Requests

### List Available Tools
```json
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "id": 1
}
```

### Capture a Thought
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "ui_think",
    "arguments": {
      "thought": "Working on improving error handling",
      "action": "capture",
      "options": {
        "confidence": 0.8,
        "tags": ["development", "error-handling"]
      }
    }
  },
  "id": 2
}
```

### View Session Status
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "manage_context",
    "arguments": {
      "action": "view_session"
    }
  },
  "id": 3
}
```
