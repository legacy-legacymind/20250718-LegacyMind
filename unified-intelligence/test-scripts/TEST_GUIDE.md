# Unified-Think Test Scripts Guide

This directory contains Python test scripts for testing the unified-think MCP server.

## Prerequisites

1. **Build the server** (if not already built):
   ```bash
   cargo build        # Debug build
   cargo build --release  # Release build
   ```

2. **Redis server** must be running and accessible at:
   - Host: `192.168.1.160`
   - Port: `6379`
   - Password: `legacymind_redis_pass`

## Test Scripts

### 1. `test_unified_think.py` - Comprehensive Test Suite

A full-featured test client with:
- Proper error handling and timeouts
- Thread-safe response handling
- Context manager support
- Detailed logging
- Complete test coverage

**Usage:**
```bash
./test_unified_think.py
```

**Features:**
- Initialization sequence testing
- Tool listing
- Thought storage (ui_think)
- Thought searching (ui_recall)
- Chain retrieval
- Thought analysis

### 2. `quick_test.py` - Minimal Test

A simple, straightforward test that:
- Initializes the server
- Stores a single thought
- Searches for it

**Usage:**
```bash
./quick_test.py
```

## JSON-RPC Protocol

The server uses MCP (Model Context Protocol) over JSON-RPC 2.0:

### Initialize
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "test-client",
      "version": "1.0"
    }
  }
}
```

### Store Thought (ui_think)
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "ui_think",
    "arguments": {
      "thought": "Your thought content",
      "thought_number": 1,
      "total_thoughts": 1,
      "next_thought_needed": false,
      "chain_id": "optional-chain-id"
    }
  }
}
```

### Search/Recall (ui_recall)
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "ui_recall",
    "arguments": {
      "query": "search terms",
      "limit": 10,
      "action": "search"
    }
  }
}
```

## Actions Available in ui_recall

- **search**: Basic search (default)
- **analyze**: Analyze thought patterns
- **merge**: Merge multiple chains
- **branch**: Create new chain from a thought
- **continue**: Continue existing chain

## Troubleshooting

1. **Server won't start**: Check Redis connection settings
2. **No responses**: Ensure proper JSON formatting with newlines
3. **Timeout errors**: Increase timeout in test script
4. **Redis errors**: Verify Redis server is running and accessible

## Example Output

```
2024-01-01 12:00:00 - INFO - Starting server: ./target/debug/unified-think
2024-01-01 12:00:01 - INFO - Server started successfully
2024-01-01 12:00:01 - INFO - === Step 1: Initialize ===
2024-01-01 12:00:01 - INFO - Initialization successful: {
  "protocolVersion": "2024-11-05",
  "capabilities": {
    "tools": {}
  },
  "serverInfo": {
    "name": "unified-think",
    "version": "0.1.0"
  }
}
```