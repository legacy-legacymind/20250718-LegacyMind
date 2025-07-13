# Unified-Think Test Scripts

This directory contains multiple Python test scripts for testing the unified-think MCP server. Each script serves a different purpose and demonstrates various aspects of the JSON-RPC communication protocol.

## Test Scripts Overview

### 1. `test_unified_think.py` - Comprehensive Test Suite
The main test client with full features:
- **Purpose**: Complete testing of all server functionality
- **Features**:
  - Thread-safe response handling
  - Proper timeout management
  - Context manager support (with statement)
  - Detailed logging
  - Error handling
- **Usage**: `./test_unified_think.py`

### 2. `quick_test.py` - Quick Functionality Test
A simple test for basic operations:
- **Purpose**: Quick smoke test of server functionality
- **Features**:
  - Initialize server
  - Store a thought
  - Search for thoughts
- **Usage**: `./quick_test.py`

### 3. `debug_test.py` - Debugging Helper
Shows detailed stderr output for troubleshooting:
- **Purpose**: Debug server issues and connection problems
- **Features**:
  - Captures and displays stderr output
  - Shows all JSON-RPC messages
  - Checks server status after each operation
- **Usage**: `./debug_test.py`

### 4. `test_edge_cases.py` - Edge Case Testing
Tests error conditions and boundary cases:
- **Purpose**: Validate error handling and robustness
- **Tests**:
  - Invalid tool names
  - Missing parameters
  - Invalid parameter types
  - Malformed requests
  - Special characters
  - Rapid requests
- **Usage**: `./test_edge_cases.py`

### 5. `interactive_client.py` - Interactive Testing
Manual testing with a command-line interface:
- **Purpose**: Explore server functionality interactively
- **Commands**:
  - `think <thought>` - Store a thought
  - `search <query>` - Search thoughts
  - `recall <chain_id>` - Get chain thoughts
  - `analyze <query>` - Analyze thoughts
  - `help` - Show commands
- **Usage**: `./interactive_client.py`

### 6. `test_from_jsonl.py` - JSONL-based Testing
Replays messages from phase3_test.jsonl:
- **Purpose**: Test with known-good message sequences
- **Features**:
  - Reads test cases from JSONL file
  - Sends exact message format
  - Validates responses
- **Usage**: `./test_from_jsonl.py`

### 7. `minimal_test.py` - Minimal Protocol Test
Tests basic protocol without notifications:
- **Purpose**: Isolate protocol issues
- **Features**:
  - No initialized notification
  - Basic request/response only
  - Uses select() for non-blocking reads
- **Usage**: `./minimal_test.py`

## Common Issues and Solutions

### Server Exits Immediately
- **Cause**: Redis connection failure
- **Solution**: Ensure Redis is running at 192.168.1.160:6379 with correct password

### Broken Pipe Error
- **Cause**: Server crashes while processing request
- **Solution**: Run `debug_test.py` to see stderr output

### No Response to Requests
- **Cause**: JSON formatting issues or protocol mismatch
- **Solution**: Check that requests include newline character

### Timeout Errors
- **Cause**: Server taking too long or not responding
- **Solution**: Increase timeout values in test scripts

## JSON-RPC Message Format

All messages must:
1. Be valid JSON
2. End with a newline character (`\n`)
3. Include `"jsonrpc": "2.0"`
4. Have either `id` (for requests) or no `id` (for notifications)

Example request:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "ui_think",
    "arguments": {
      "thought": "Test thought",
      "thought_number": 1,
      "total_thoughts": 1,
      "next_thought_needed": false
    }
  }
}
```

## Building the Server

Before running tests:
```bash
cargo build         # Debug build
cargo build --release  # Release build
```

## Environment Variables

- `INSTANCE_ID`: Identifies the client instance (default: "test")
- `RUST_LOG`: Set to "debug" for detailed server logs

## Running Tests in Order

Recommended testing sequence:
1. `./minimal_test.py` - Verify basic connectivity
2. `./quick_test.py` - Test core functionality
3. `./test_unified_think.py` - Full test suite
4. `./test_edge_cases.py` - Validate error handling
5. `./interactive_client.py` - Manual exploration