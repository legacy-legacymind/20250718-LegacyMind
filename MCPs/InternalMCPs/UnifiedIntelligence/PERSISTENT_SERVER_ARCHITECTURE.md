# UnifiedIntelligence Persistent Server Architecture

## Overview

The UnifiedIntelligence MCP has been upgraded to support a persistent server architecture that dramatically improves performance by eliminating startup overhead. This reduces operation time from ~10s to ~50ms.

## Architecture Components

### 1. Persistent Server (`src/index.js serve`)
- Runs as a long-lived process managed by PM2
- Listens on Unix socket: `/tmp/unified-intelligence.sock`
- Maintains persistent Redis connections with connection pooling
- Handles multiple concurrent requests efficiently

### 2. Connection Manager (`src/shared/redis-manager.js`)
- Single unified Redis connection with built-in pooling
- Connection pool size: min 2, max 10
- Automatic reconnection with exponential backoff
- Circuit breaker pattern for fault tolerance

### 3. Client Connector (`src/connector.js`)
- Bridges stdin/stdout to Unix socket
- Handles connection failures gracefully
- Buffers messages during reconnection attempts
- Compatible with MCP protocol

### 4. Process Management (`ecosystem.config.js`)
- PM2 configuration for production deployment
- Auto-restart on failure
- Memory limit: 500MB
- Graceful shutdown support
- Log management

## Usage

### Starting the Server

```bash
# Using PM2 (recommended for production)
npm run start:server

# Direct server mode (for testing)
node src/index.js serve
```

### Connecting to the Server

```bash
# Use the connector as a drop-in replacement
node src/connector.js

# Or use the client wrapper
./unified-intelligence-client
```

### Managing the Server

```bash
# Check server status
npm run status:server

# View logs
npm run logs:server

# Restart server
npm run restart:server

# Stop server
npm run stop:server
```

## Performance Improvements

1. **Startup Time**: Eliminated ~10s Redis connection overhead
2. **Response Time**: Reduced from 10s to 50ms per operation
3. **Connection Pooling**: Reuses connections for better throughput
4. **Concurrent Requests**: Handles multiple requests simultaneously

## Docker Support

The Dockerfile has been updated to use PM2:

```dockerfile
CMD ["pm2-runtime", "start", "ecosystem.config.js"]
```

## Testing

Run the performance test to verify improvements:

```bash
./test-persistent-server.js
```

This will:
- Start the server
- Measure response times
- Compare with direct startup time
- Show performance improvement metrics

## Migration Notes

1. The persistent server is backward compatible - the original stdio mode still works
2. The connector provides a transparent bridge, so existing integrations work unchanged
3. Redis connection is now managed centrally for better resource utilization

## Troubleshooting

1. **Server not starting**: Check if port is already in use or permissions on `/tmp`
2. **Connection refused**: Ensure server is running with `npm run status:server`
3. **High memory usage**: Check PM2 logs and adjust memory limit in ecosystem.config.js
4. **Redis connection issues**: Check REDIS_URL environment variable and Redis server status