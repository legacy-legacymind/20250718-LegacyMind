# OPENAI API Key Configuration

The unified-intelligence service now supports multiple ways to configure the OPENAI_API_KEY for vector embeddings:

## 1. Environment Variable (Primary Method)

When starting the service, pass the API key as an environment variable:

```bash
OPENAI_API_KEY="your-api-key" ./target/release/unified-intelligence
```

This is automatically done by Claude Desktop when configured in `DT_claude.json`.

## 2. Redis Storage (Persistent Method)

The service automatically stores the API key in Redis on startup if provided via environment variable. The key is stored with a 24-hour expiration and can be refreshed on service restart.

To manually set the API key in Redis:

```bash
./set_api_key.py "your-api-key"
```

Or from a file:
```bash
cat api_key.txt | ./set_api_key.py
```

## 3. How It Works

1. **On Service Startup**: 
   - If `OPENAI_API_KEY` is in the environment, it's stored in Redis at `config:openai_api_key`
   - The key expires after 24 hours but is refreshed on each service restart

2. **When Creating Embeddings**:
   - The RedisVLService first checks Redis for the API key
   - Falls back to environment variable if not found in Redis
   - The Python embedding script also checks both sources

3. **Benefits**:
   - API key persists across service restarts
   - Can be updated without modifying configuration files
   - Shared across all instances using the same Redis

## Security Notes

- The API key is stored in Redis with the same security as other data
- Ensure Redis is properly secured with authentication
- Don't commit API keys to version control
- Use environment variables or the set_api_key.py utility instead