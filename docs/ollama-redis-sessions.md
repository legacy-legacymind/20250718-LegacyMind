# Ollama Redis-Backed Conversation Sessions

## Overview

This document provides a comprehensive guide for implementing persistent conversation state for Ollama using Redis as the storage backend. The implementation extends the existing `ollama-quick.sh` script to support multi-turn conversations with memory.

## Architecture

### Components

1. **Redis Storage Layer**: Stores conversation history and session metadata
2. **Ollama API Integration**: Uses the `/api/chat` endpoint for context-aware responses
3. **Session Manager**: Python script that handles session lifecycle
4. **Shell Wrapper**: Maintains backward compatibility with existing scripts

### Data Flow

```
User Input → Session Manager → Redis (Store) → Ollama API (with context) → Response → Redis (Store) → User
```

## Redis Data Structures

### Recommended: Sorted Sets + Hashes Hybrid

We use a hybrid approach for optimal performance:

1. **Sorted Set** (`session:{id}:messages`): Maintains message ordering by timestamp
2. **Hash** (`session:{id}:meta`): Stores session metadata

#### Structure Example:

```redis
# Sorted set for message ordering
session:abc123:messages = {
  '{"role":"user","content":"Hello","timestamp":1234567890}': 1234567890,
  '{"role":"assistant","content":"Hi!","timestamp":1234567891}': 1234567891
}

# Hash for session metadata
session:abc123:meta = {
  "created_at": "1234567890",
  "last_activity": "1234567891",
  "message_count": "2",
  "name": "Python Help Session"
}
```

### Alternative Approaches Comparison

| Structure | Pros | Cons | Use Case |
|-----------|------|------|----------|
| **Lists** | Simple, maintains order | No unique constraints, limited queries | Simple message queues |
| **Sorted Sets** | Efficient range queries, unique entries | More complex than lists | Time-based data with ordering |
| **Streams** | Built for time-series, automatic IDs | Append-only, complex for updates | Event logging, audit trails |
| **Hashes** | Flexible field updates | No inherent ordering | Object storage |

## Implementation Details

### 1. Session Management

```python
# Session ID Generation (cryptographically secure)
session_id = secrets.token_urlsafe(16)  # Generates 16-byte URL-safe token

# TTL Strategy
default_ttl = 3600  # 1 hour
# Refresh on each interaction to keep active sessions alive
```

### 2. Message Storage Pattern

```python
def add_message(session_id, role, content):
    timestamp = time.time()
    message_data = json.dumps({
        "role": role,
        "content": content,
        "timestamp": timestamp
    })
    
    # Store in sorted set
    redis.zadd(f"session:{session_id}:messages", {message_data: timestamp})
    
    # Update metadata
    redis.hincrby(f"session:{session_id}:meta", "message_count", 1)
    redis.hset(f"session:{session_id}:meta", "last_activity", timestamp)
    
    # Refresh TTL
    redis.expire(f"session:{session_id}:messages", ttl)
    redis.expire(f"session:{session_id}:meta", ttl)
```

### 3. Ollama API Integration

```python
# Chat endpoint structure
request = {
    "model": "qwen2.5-coder:1.5b",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help?"},
        {"role": "user", "content": "Tell me about Python"}
    ],
    "stream": False,
    "options": {
        "temperature": 0.7,
        "num_ctx": 4096  # Context window size
    }
}
```

## Usage Examples

### Command Line Interface

```bash
# Start new session
./ollama-chat.sh -n "Hello, let's talk about Python"

# Continue existing session
./ollama-chat.sh -s abc123def456 "What about list comprehensions?"

# List all sessions
./ollama-chat.sh -l

# View session history
./ollama-session.py --history abc123def456

# Delete old sessions (older than 24 hours)
./ollama-session.py --clean 24

# Use specific model
./ollama-chat.sh -s abc123def456 -m llama3.2 "Explain decorators"
```

### Python API Usage

```python
from ollama_session import OllamaSessionManager

# Initialize
manager = OllamaSessionManager()

# Create session with system prompt
session_id = manager.create_session(
    name="Python Tutorial",
    system_prompt="You are a Python tutor. Provide clear, concise examples."
)

# Chat
response = manager.chat(session_id, "How do I read a file?")
print(response)

# Get conversation history
history = manager.get_conversation_history(session_id)
for msg in history:
    print(f"{msg['role']}: {msg['content']}")
```

## Performance Optimization

### 1. Context Window Management

```python
# Limit conversation history to recent messages
def get_recent_messages(session_id, limit=20):
    # Get only the most recent messages to fit in context window
    return redis.zrange(f"session:{session_id}:messages", -limit, -1)
```

### 2. Redis Connection Pooling

```python
# Use connection pool for better performance
pool = redis.ConnectionPool(
    host='localhost',
    port=6379,
    max_connections=10
)
redis_client = redis.StrictRedis(connection_pool=pool)
```

### 3. Message Pruning Strategy

```python
def prune_old_messages(session_id, keep_recent=50):
    # Get total message count
    total = redis.zcard(f"session:{session_id}:messages")
    
    if total > keep_recent:
        # Remove oldest messages
        redis.zremrangebyrank(f"session:{session_id}:messages", 0, total - keep_recent - 1)
```

## Advanced Features

### 1. Session Branching

```python
def branch_session(source_id, branch_at_message=None):
    """Create a new session branch from existing conversation"""
    new_id = create_session()
    
    # Copy messages up to branch point
    messages = get_conversation_history(source_id)
    if branch_at_message:
        messages = messages[:branch_at_message]
    
    for msg in messages:
        add_message(new_id, msg['role'], msg['content'])
    
    return new_id
```

### 2. Search Within Sessions

```python
def search_sessions(query, user_sessions=None):
    """Search across multiple sessions"""
    results = []
    sessions = user_sessions or list_all_sessions()
    
    for session_id in sessions:
        messages = get_conversation_history(session_id)
        for i, msg in enumerate(messages):
            if query.lower() in msg['content'].lower():
                results.append({
                    'session_id': session_id,
                    'message_index': i,
                    'message': msg
                })
    
    return results
```

### 3. Export/Import Sessions

```python
def export_session(session_id):
    """Export session to JSON"""
    return {
        'metadata': redis.hgetall(f"session:{session_id}:meta"),
        'messages': get_conversation_history(session_id)
    }

def import_session(session_data):
    """Import session from JSON"""
    session_id = create_session()
    
    # Import metadata
    if 'metadata' in session_data:
        redis.hset(f"session:{session_id}:meta", mapping=session_data['metadata'])
    
    # Import messages
    for msg in session_data.get('messages', []):
        add_message(session_id, msg['role'], msg['content'])
    
    return session_id
```

## Error Handling

### Common Issues and Solutions

1. **Redis Connection Failed**
   ```python
   try:
       redis.ping()
   except redis.ConnectionError:
       # Fallback to ollama-quick.sh
       subprocess.run(['./ollama-quick.sh', prompt])
   ```

2. **Context Window Exceeded**
   ```python
   if len(messages) > MAX_CONTEXT_MESSAGES:
       # Summarize older messages or truncate
       messages = summarize_and_truncate(messages)
   ```

3. **Session Not Found**
   ```python
   if not redis.exists(f"session:{session_id}:meta"):
       # Create new session or return error
       raise SessionNotFoundError(f"Session {session_id} not found")
   ```

## Security Considerations

1. **Session ID Security**: Use `secrets.token_urlsafe()` for cryptographically secure IDs
2. **Input Validation**: Sanitize user inputs before storing in Redis
3. **TTL Management**: Implement automatic cleanup to prevent data accumulation
4. **Access Control**: Consider implementing user-based session isolation

## Monitoring and Maintenance

### Redis Memory Usage

```bash
# Monitor Redis memory
redis-cli INFO memory

# Set memory limit in redis.conf
maxmemory 1gb
maxmemory-policy allkeys-lru
```

### Session Analytics

```python
def get_session_stats():
    """Get usage statistics"""
    stats = {
        'total_sessions': 0,
        'total_messages': 0,
        'avg_messages_per_session': 0,
        'oldest_session': None,
        'most_active_session': None
    }
    
    sessions = list_all_sessions()
    stats['total_sessions'] = len(sessions)
    
    for session in sessions:
        msg_count = int(redis.hget(f"session:{session['id']}:meta", "message_count") or 0)
        stats['total_messages'] += msg_count
    
    if stats['total_sessions'] > 0:
        stats['avg_messages_per_session'] = stats['total_messages'] / stats['total_sessions']
    
    return stats
```

## Integration with Existing Tools

The implementation maintains full backward compatibility:

```bash
# Original usage still works
./ollama-quick.sh "What is Python?"

# New session-aware wrapper
./ollama-chat.sh "What is Python?"  # Creates session automatically
./ollama-chat.sh -s SESSION_ID "Tell me more"  # Continues conversation
```

## Future Enhancements

1. **Multi-user Support**: Add user authentication and session isolation
2. **Web Interface**: Build a web UI for session management
3. **Model Switching**: Allow changing models mid-conversation
4. **Conversation Summarization**: Automatic summarization for long conversations
5. **Vector Storage**: Integration with vector databases for semantic search
6. **Conversation Templates**: Pre-defined conversation starters and flows