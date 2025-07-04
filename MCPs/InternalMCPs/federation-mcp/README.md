# Federation MCP

A Model Context Protocol (MCP) server that coordinates CCMCP (Claude Code MCP) and GMCP (Gemini MCP) agents for parallel task execution, intelligent routing, and fallback handling.

## 🎯 Overview

The Federation MCP acts as an intelligent coordinator between two powerful AI agents:
- **CCMCP**: Claude Code agent for implementation, coding, and file operations
- **GMCP**: Gemini agent for analysis, research, and large context processing

By orchestrating these agents in parallel or sequential workflows, the Federation MCP maximizes efficiency and provides robust fallback mechanisms.

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│                 │    │                  │    │                 │
│     Client      │◄──►│  Federation MCP  │◄──►│    Task Router  │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │  Execution Manager  │
                    └─────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
            ┌─────────────┐         ┌─────────────┐
            │    CCMCP    │         │    GMCP     │
            │  (Claude)   │         │  (Gemini)   │
            └─────────────┘         └─────────────┘
```

## 🚀 Features

### Core Capabilities
- **Parallel Execution**: Run both agents simultaneously for maximum efficiency
- **Intelligent Routing**: Automatically route tasks to the most suitable agent
- **Fallback Handling**: Seamless failover when one agent is unavailable
- **Performance Optimization**: Track and optimize execution patterns
- **Error Recovery**: Robust error handling with retry mechanisms

### Execution Strategies
1. **Parallel**: Execute both agents simultaneously
2. **Sequential**: Run analysis first, then implementation
3. **Fallback**: Primary agent with backup option

### Task Types
- **Research & Build**: GMCP researches, CCMCP implements
- **Analyze & Document**: GMCP analyzes code, CCMCP creates docs
- **Validation & Fixes**: GMCP reviews, CCMCP implements fixes
- **Large File Analysis**: GMCP processes large files, CCMCP handles specifics

## 🔧 Installation

### Prerequisites
- Node.js 18 or higher
- TypeScript
- Access to Claude Code MCP
- Gemini CLI installed and configured

### Setup
```bash
# Clone and navigate to the federation-mcp directory
cd /Users/samuelatagana/Documents/LegacyMind/System/MCPs/InternalMCPs/federation-mcp

# Install dependencies
npm install

# Build TypeScript
npm run build

# Copy and configure environment
cp .env.example .env
# Edit .env with your specific settings

# Test the installation
npm test
```

### Configuration
Edit `.env` file to configure timeouts, endpoints, and behavior:

```env
# Timeout settings (in milliseconds)
CCMCP_TIMEOUT=120000      # 2 minutes for Claude Code
GMCP_TIMEOUT=300000       # 5 minutes for Gemini (longer context)
PARALLEL_TIMEOUT=180000   # 3 minutes for parallel execution

# Fallback settings
FALLBACK_ENABLED=true

# Debug and logging
DEBUG_MODE=false
NODE_ENV=production
```

## 📋 Available Tools

### 1. `parallel_task`
Execute custom tasks using both agents in parallel or sequential mode.

```json
{
  "name": "parallel_task",
  "arguments": {
    "title": "Custom Task",
    "description": "Description of the task",
    "ccmcpTask": "Task for Claude Code",
    "gmcpTask": "Task for Gemini",
    "executionStrategy": "parallel",
    "aggregationStrategy": "merge"
  }
}
```

### 2. `research_and_build`
Research with Gemini and implement with Claude Code.

```json
{
  "name": "research_and_build",
  "arguments": {
    "topic": "REST API Design",
    "researchQuery": "What are the best practices?",
    "buildInstructions": "Create API structure",
    "executionMode": "sequential",
    "includeFileAnalysis": true,
    "filePaths": ["./src/api.js"]
  }
}
```

### 3. `analyze_and_document`
Analyze codebase with Gemini and create documentation with Claude Code.

```json
{
  "name": "analyze_and_document",
  "arguments": {
    "target": "Authentication System",
    "filePaths": ["./src/auth/", "./src/middleware/"],
    "analysisPrompt": "Analyze security patterns",
    "documentationPrompt": "Create security documentation",
    "documentationType": "TECHNICAL_GUIDE",
    "outputFormat": "markdown"
  }
}
```

### 4. `validation_and_fixes`
Validate with Gemini and implement fixes with Claude Code.

```json
{
  "name": "validation_and_fixes",
  "arguments": {
    "target": "Database Schema",
    "filePaths": ["./schema.sql"],
    "validationCriteria": "Check for security issues",
    "fixInstructions": "Implement security fixes",
    "validationType": "SECURITY_AUDIT",
    "autoFix": false,
    "sandboxTest": true
  }
}
```

## 🔄 Execution Workflows

### Parallel Workflow
```
┌─────────────┐    ┌─────────────┐
│    GMCP     │    │    CCMCP    │
│ (Research)  │    │ (Implement) │
│             │    │             │
└──────┬──────┘    └──────┬──────┘
       │                  │
       └────────┬─────────┘
                ▼
        ┌─────────────┐
        │  Aggregate  │
        │   Results   │
        └─────────────┘
```

### Sequential Workflow
```
┌─────────────┐
│    GMCP     │
│ (Research)  │
│             │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    CCMCP    │
│ (Implement) │
│             │
└─────────────┘
```

### Fallback Workflow
```
┌─────────────┐     ┌─────────────┐
│   Primary   │────▶│  Fallback   │
│   Agent     │     │    Agent    │
│  (Fails)    │     │ (Succeeds)  │
└─────────────┘     └─────────────┘
```

## ⚡ Performance Characteristics

### Timing Expectations
- **Parallel Execution**: ~60% faster than sequential for independent tasks
- **Sequential Execution**: Better for dependent tasks (analysis → implementation)
- **Fallback Overhead**: <500ms additional latency

### Resource Usage
- **Memory**: Moderate (both agents run simultaneously in parallel mode)
- **CPU**: Low (coordination layer is lightweight)
- **Network**: Dependent on agent implementations

### Scalability
- **Concurrent Tasks**: Up to 5 parallel federation tasks
- **Queue Management**: Built-in task queuing for overflow
- **Error Recovery**: Automatic retry with exponential backoff

## 🧪 Testing

### Run All Tests
```bash
npm test
```

### Run Specific Tests
```bash
# Basic functionality test
node tests/test-federation.js

# Performance and parallel execution test
node tests/test-parallel-execution.js
```

### Performance Benchmarking
The test suite includes comprehensive performance benchmarks:
- Single task execution times
- Concurrent task handling
- Sequential vs parallel comparison
- Fallback mechanism validation
- Load testing capabilities

## 🐳 Docker Deployment

### Build Docker Image
```bash
docker build -t federation-mcp .
```

### Run Container
```bash
docker run -d \
  --name federation-mcp \
  -e CCMCP_TIMEOUT=120000 \
  -e GMCP_TIMEOUT=300000 \
  -e DEBUG_MODE=false \
  federation-mcp
```

### Docker Compose
```yaml
version: '3.8'
services:
  federation-mcp:
    build: .
    environment:
      - NODE_ENV=production
      - CCMCP_TIMEOUT=120000
      - GMCP_TIMEOUT=300000
      - FALLBACK_ENABLED=true
    restart: unless-stopped
```

## 🔍 Monitoring and Debugging

### Debug Mode
Enable detailed logging by setting `DEBUG_MODE=true` in your `.env` file.

### Log Analysis
The Federation MCP provides structured logging:
```json
{
  "timestamp": "2025-07-03T18:33:09.000Z",
  "level": "INFO",
  "message": "Executing tool",
  "context": {
    "tool": "parallel_task",
    "executionTime": 1205,
    "ccmcpSuccess": true,
    "gmcpSuccess": true
  }
}
```

### Performance Metrics
Track key performance indicators:
- Task execution times
- Success rates by agent
- Fallback activation frequency
- Concurrent task performance

## 🛠️ Integration Examples

### With Claude Desktop
Add to your Claude Desktop MCP configuration:
```json
{
  "mcpServers": {
    "federation": {
      "command": "node",
      "args": ["/path/to/federation-mcp/dist/index.js"]
    }
  }
}
```

### With Other MCP Servers
The Federation MCP can coordinate with other MCP servers in your stack:
```json
{
  "mcpServers": {
    "federation": { "command": "node", "args": ["federation-mcp/dist/index.js"] },
    "knowledge": { "command": "node", "args": ["unified-knowledge-mcp/dist/index.js"] },
    "workflow": { "command": "node", "args": ["unified-workflow/src/index.js"] }
  }
}
```

## 🔧 Advanced Configuration

### Custom Execution Strategies
You can extend the Federation MCP with custom execution strategies by implementing the `ExecutionStrategy` interface:

```typescript
import { ExecutionStrategy, TaskDefinition, FederationContext } from './types/index.js';

export class CustomStrategy implements ExecutionStrategy {
  name = 'custom';
  
  async execute(task: TaskDefinition, context: FederationContext) {
    // Custom execution logic
  }
}
```

### Agent-Specific Optimizations
- **CCMCP**: Optimized for file operations, code generation, and precise edits
- **GMCP**: Optimized for large context analysis, research, and complex reasoning

### Error Handling Strategies
1. **Immediate Fallback**: Switch to backup agent on first failure
2. **Retry with Backoff**: Attempt primary agent multiple times before fallback
3. **Circuit Breaker**: Temporarily disable failing agents

## 📊 Use Cases

### Development Workflows
1. **Code Review Process**:
   - GMCP: Analyze code for issues, patterns, security concerns
   - CCMCP: Implement specific fixes and improvements

2. **Documentation Generation**:
   - GMCP: Understand codebase structure and functionality
   - CCMCP: Generate formatted documentation files

3. **Feature Development**:
   - GMCP: Research best practices and design patterns
   - CCMCP: Implement the feature with proper code structure

### System Administration
1. **Configuration Management**:
   - GMCP: Analyze system requirements and constraints
   - CCMCP: Generate and deploy configuration files

2. **Troubleshooting**:
   - GMCP: Analyze logs and system state for root cause
   - CCMCP: Implement fixes and monitoring solutions

### Research and Analysis
1. **Technology Evaluation**:
   - GMCP: Research technologies, compare options, analyze trade-offs
   - CCMCP: Create proof-of-concept implementations

2. **Performance Optimization**:
   - GMCP: Analyze performance bottlenecks and patterns
   - CCMCP: Implement optimizations and benchmarks

## 🤝 Contributing

### Development Setup
```bash
# Install development dependencies
npm install

# Run in development mode
npm run dev

# Build for production
npm run build
```

### Code Style
- TypeScript with strict mode enabled
- ESM modules
- Comprehensive error handling
- Structured logging

### Testing Guidelines
- Unit tests for core functionality
- Integration tests for agent coordination
- Performance tests for execution strategies
- Error scenario testing

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Troubleshooting

### Common Issues

1. **Agent Not Available**
   ```
   Error: Agent 'ccmcp' is not available
   ```
   - Ensure CCMCP server is running and accessible
   - Check network connectivity and firewall settings

2. **Timeout Errors**
   ```
   Error: Task timed out after 120000ms
   ```
   - Increase timeout values in `.env` file
   - Optimize task complexity

3. **Memory Issues**
   ```
   Error: JavaScript heap out of memory
   ```
   - Reduce concurrent task limits
   - Implement task queuing

### Debug Commands
```bash
# Test agent connectivity
node -e "import('./dist/managers/CCMCPManager.js').then(m => new m.CCMCPManager().ping())"

# Validate configuration
node -e "import('./dist/utils/config.js').then(c => c.validateConfig(c.config))"

# Check server health
curl -f http://localhost:3000/health || echo "Server not responding"
```

### Support
For issues and questions:
1. Check the troubleshooting section above
2. Review the test suite for usage examples
3. Examine debug logs with `DEBUG_MODE=true`
4. Create an issue with detailed error information

---

🚀 **Ready to coordinate your AI agents with Federation MCP!**