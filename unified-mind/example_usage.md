# UnifiedMind MCP Usage Examples

## Starting the Service

```bash
# Ensure Redis is running
redis-server

# In another terminal, start the UnifiedMind service
cd /Users/samuelatagana/Projects/LegacyMind/unified-mind
cargo run --release
```

## Tool Examples

### 1. Internal Dialogue Processing

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "mind_dialogue",
    "arguments": {
      "thought": "I need to understand how to better organize complex information retrieval tasks",
      "context": "Working on improving search efficiency"
    }
  }
}
```

### 2. Pattern Matching

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "mind_pattern_match",
    "arguments": {
      "context": "User is searching for configuration files in a large codebase",
      "pattern_type": "search_strategy"
    }
  }
}
```

### 3. Retrieval Strategy Suggestion

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "mind_suggest_retrieval",
    "arguments": {
      "task_description": "Find all references to a specific function across multiple files",
      "constraints": {
        "time_limit": "fast",
        "accuracy": "high"
      }
    }
  }
}
```

### 4. Learning from Outcomes

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "mind_learn_outcome",
    "arguments": {
      "task_id": "search_config_files_001",
      "outcome": "success",
      "metrics": {
        "time_taken": 2.5,
        "files_searched": 150,
        "matches_found": 3,
        "strategy_used": "grep_then_read"
      }
    }
  }
}
```

## Integration with Claude Desktop

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "unified-mind": {
      "command": "cargo",
      "args": ["run", "--release"],
      "cwd": "/Users/samuelatagana/Projects/LegacyMind/unified-mind",
      "env": {
        "REDIS_URL": "redis://127.0.0.1:6379",
        "RUST_LOG": "unified_mind=debug"
      }
    }
  }
}
```