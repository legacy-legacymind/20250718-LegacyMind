# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains two main Rust projects as part of the LegacyMind system:
- **unified-intelligence**: An MCP (Model Context Protocol) server implementing a Redis-backed thought storage and retrieval system
- **bot-cli**: A CLI tool for interacting with local Ollama LLM models with session persistence

## Essential Commands

### Build Commands
```bash
# Build unified-intelligence
cargo build --manifest-path=unified-intelligence/Cargo.toml --release

# Build bot-cli
cargo build --manifest-path=bot-cli/Cargo.toml --release

# Build everything
cargo build --release
```

### Test Commands
```bash
# Run Rust tests
cargo test

# Run unified-intelligence integration tests (requires Redis at 192.168.1.160:6379)
cd unified-intelligence/test-scripts
./test_unified_think.py    # Comprehensive test suite
./quick_test.py           # Quick smoke test
./debug_test.py          # Debug mode with stderr output
./test_edge_cases.py     # Edge case testing
```

### Lint Commands
```bash
# Format code
cargo fmt

# Run clippy
cargo clippy --all-targets --all-features -- -D warnings

# Check formatting without applying changes
cargo fmt -- --check
```

### Running the Services
```bash
# Run unified-intelligence MCP server (for Claude Desktop integration)
cargo run --manifest-path=unified-intelligence/Cargo.toml

# Run bot CLI
cargo run --manifest-path=bot-cli/Cargo.toml -- [options]

# Use the ollama-quick script for simple tasks
./scripts/ollama-quick.sh "your prompt here"
```

## High-Level Architecture

### unified-intelligence
The MCP server follows a modular architecture with these key components:

1. **Repository Pattern**: `ThoughtRepository` trait with `RedisThoughtRepository` implementation
2. **MCP Protocol**: Tool-based architecture exposing `ui_think`, `ui_recall`, `ui_identity` operations
3. **Data Storage**: Redis with JSON module for structured data, optional Search module for full-text search
4. **Background Services**: Python-based embedding service for semantic search
5. **Instance Namespacing**: Supports multiple instances (CC, CCI, DT) with isolated data

Key architectural decisions:
- Async/await throughout using Tokio
- Connection pooling with deadpool-redis
- Comprehensive error handling with custom error types
- Visual feedback system for terminal output
- Rate limiting and validation layers

### bot-cli
CLI tool architecture:
- Session management with Redis persistence
- Interactive and single-prompt modes
- File context analysis capabilities
- Integration with local Ollama models

## Critical Configuration

### Redis Setup
- Default connection: `192.168.1.160:6379`
- Password: `legacymind_redis_pass` (SECURITY: Update in production)
- Required modules: JSON (mandatory), Search (optional but recommended)

### Environment Variables
- `REDIS_URL`: Override default Redis connection
- `OLLAMA_HOST`: Ollama server location (default: http://localhost:11434)
- API keys stored in Redis under `api_keys:{provider}` pattern

## Development Workflow

1. **Making Changes**: Follow existing patterns in the codebase
   - Use the repository pattern for data access
   - Implement proper error handling with `UnifiedIntelligenceError`
   - Add visual feedback for user-facing operations
   - Maintain instance isolation in Redis keys

2. **Testing Changes**:
   - Write Rust unit tests for new functionality
   - Use test scripts in `unified-intelligence/test-scripts/` for integration testing
   - Verify MCP protocol compliance with `minimal_test.py`

3. **Code Style**:
   - Follow Rust naming conventions
   - Use descriptive variable names
   - Document public APIs with doc comments
   - Keep functions focused and single-purpose

## Important Notes

- The system is in active development (Phase 4A as of recent commits)
- Redis backup/restore scripts are available in `scripts/` directory
- The embedding service requires either OpenAI or Groq API keys
- MCP integration requires proper stdio transport setup
- Check HANDOFF_DOCUMENTATION.md for detailed continuation instructions