# ObsidianMCP

A high-performance Model Context Protocol (MCP) server for Obsidian vault operations, built in Rust as part of the LegacyMind Federation.

## Overview

ObsidianMCP provides secure, efficient access to Obsidian vaults through the Model Context Protocol, enabling AI assistants to read, search, and manage your knowledge base while maintaining strict security boundaries.

### Key Features

- **Secure Vault Access**: Sandboxed operations within configured vault boundaries
- **Efficient Search**: Fast file and content search with regex support
- **File Management**: Create, read, update, delete, and move files
- **Type Safety**: Built in Rust with comprehensive error handling
- **Federation Integration**: Compatible with LegacyMind's UnifiedMind/UnifiedIntelligence systems
- **MCP Compliance**: Full Model Context Protocol compatibility

## Quick Start

### Prerequisites

- Rust 1.70+ (with Cargo)
- An Obsidian vault or any directory with markdown files

### Installation

```bash
# Clone the repository
cd /Users/samuelatagana/Projects/LegacyMind/obsidian-mcp

# Build the project
cargo build --release

# Run the MCP server
cargo run
```

### Configuration

Create an `obsidian-mcp.toml` configuration file:

```toml
[vault]
root_path = "/path/to/your/obsidian/vault"
allowed_extensions = ["md", "txt", "json", "yaml", "yml"]
max_file_size = 10485760  # 10MB
enable_watching = false

[server]
name = "ObsidianMCP"
version = "0.1.0"

# Optional Redis integration for Federation
[redis]
url = "redis://localhost:6379"
pool_size = 10
key_prefix = "obsidian_mcp"
```

### Environment Variables

```bash
# Vault configuration
export OBSIDIAN_MCP_VAULT_ROOT_PATH="/path/to/vault"
export OBSIDIAN_MCP_VAULT_MAX_FILE_SIZE="10485760"

# Redis (optional)
export OBSIDIAN_MCP_REDIS_URL="redis://localhost:6379"
```

## Tools

### search
Search for files and content within the vault.

**Parameters:**
- `query`: Search query string
- `path_prefix`: Optional path prefix to limit scope
- `include_content`: Include file content in results
- `limit`: Maximum number of results (default: 50)
- `extensions`: File extensions to include

**Example:**
```json
{
  "query": "daily notes",
  "path_prefix": "Daily",
  "include_content": true,
  "limit": 10
}
```

### browse
Browse and read files from the vault.

**Parameters:**
- `path`: Relative path from vault root

**Example:**
```json
{
  "path": "Daily/2024-01-01.md"
}
```

## Architecture

### Project Structure
```
obsidian-mcp/
├── src/
│   ├── main.rs          # MCP server entry point
│   ├── service.rs       # Core service implementation
│   ├── handlers.rs      # MCP tool implementations
│   ├── vault.rs         # Vault operations manager
│   ├── models.rs        # Data structures and schemas
│   ├── config.rs        # Configuration management
│   └── error.rs         # Error handling
├── docs/                # Documentation
├── tests/               # Test files
├── Cargo.toml          # Dependencies and metadata
└── README.md           # This file
```

### Security Model

- **Path Validation**: All file operations are restricted to the configured vault
- **Extension Filtering**: Only allowed file types can be accessed
- **Size Limits**: Configurable maximum file sizes prevent resource exhaustion
- **Sandboxing**: No access outside vault boundaries

## Development

### Building

```bash
# Development build
cargo build

# Release build
cargo build --release

# Run tests
cargo test

# Check code quality
cargo clippy
cargo fmt
```

### Testing with Claude Code

```bash
# Start the MCP server
cargo run

# In another terminal, test with Claude Code CLI
# (Configure in your claude_desktop_config.json first)
```

### Federation Integration

This MCP integrates with the LegacyMind Federation:
- **UnifiedMind**: Thought capture and retrieval
- **UnifiedIntelligence**: Enhanced reasoning and analysis
- **Redis**: Shared state and caching

## Configuration Examples

### Claude Desktop Integration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "obsidian-mcp": {
      "command": "/path/to/obsidian-mcp/target/release/obsidian-mcp",
      "env": {
        "OBSIDIAN_MCP_VAULT_ROOT_PATH": "/path/to/your/vault"
      }
    }
  }
}
```

### Production Configuration

```toml
[vault]
root_path = "/home/user/knowledge-base"
allowed_extensions = ["md", "txt", "org"]
max_file_size = 52428800  # 50MB
enable_watching = true

[redis]
url = "redis://redis-server:6379"
pool_size = 20
key_prefix = "prod_obsidian_mcp"

[server]
name = "ProductionObsidianMCP"
```

## Roadmap

- [ ] **Phase 1**: Basic CRUD operations (in progress)
- [ ] **Phase 2**: Advanced search with semantic capabilities
- [ ] **Phase 3**: Real-time file watching and updates
- [ ] **Phase 4**: Canvas and graph operations
- [ ] **Phase 5**: Plugin and theme management

## Contributing

This project follows LegacyMind Federation standards:

1. Use `ui_think` for all significant design decisions
2. Maintain Redis integration for Federation compatibility
3. Follow Rust best practices and error handling patterns
4. Add comprehensive tests for new functionality

## License

MIT License - see LICENSE file for details.

## Support

- **Federation Support**: Integration questions and Federation compatibility
- **General Issues**: Bug reports and feature requests
- **Documentation**: API and usage documentation

---

**Created**: July 20, 2025 23:11 CDT  
**Author**: Federation CC (Claude Code)  
**Status**: Foundation Complete - Ready for CRUD Implementation