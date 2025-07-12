# Vector Set Semantic Search

This implementation adds semantic search capabilities to the UnifiedThink system using Redis 8.0's new Vector Set data structure.

## Features

### 1. Vector Set Methods in `redis.rs`
- `init_vector_set()` - Creates a vector set for storing 384-dimensional embeddings
- `add_thought_vector()` - Adds thought embeddings when saving thoughts
- `search_similar_thoughts()` - Performs semantic similarity search using cosine distance
- `get_vector_set_info()` - Retrieves vector set information for monitoring

### 2. Embedding Generation in `embeddings.rs`
- TF-IDF inspired approach for demonstration purposes
- Generates 384-dimensional embeddings to match common embedding models
- Features include:
  - Term frequency calculation
  - Positional features (beginning/end emphasis)
  - Character-level features (length, special chars, digits, capitals)
  - Unit-length normalization for cosine similarity

### 3. Repository Integration
- Automatically generates and stores embeddings when saving thoughts
- New `search_thoughts_semantic()` method for semantic search
- Graceful fallback when Vector Sets module is not available

### 4. API Enhancement
- Added `semantic_search` parameter to `ui_recall` tool
- When `semantic_search: true`, uses vector similarity instead of text search
- Response includes search method indicator

## Usage

### Enable Semantic Search
```json
{
  "method": "ui_recall",
  "params": {
    "query": "machine learning algorithms",
    "limit": 10,
    "semantic_search": true
  }
}
```

### Regular Text Search (default)
```json
{
  "method": "ui_recall",
  "params": {
    "query": "machine learning algorithms",
    "limit": 10
  }
}
```

## Requirements

- Redis 8.0+ with Vector Sets module (optional - gracefully degrades if not available)
- The system will work without the Vector Sets module but semantic search will return empty results

## Error Handling

All vector operations include proper error handling:
- Module not available: Operations are skipped, system continues normally
- Invalid dimensions: Returns validation error
- Vector set doesn't exist: Automatically created on first use

## Testing

Use the provided `test_vector_search.py` script to test the functionality:
```bash
python test_vector_search.py | cargo run
```

This will:
1. Add several test thoughts with related and unrelated content
2. Perform both text and semantic searches
3. Compare the results to verify semantic similarity matching

## Future Improvements

For production use, consider:
1. Using real embedding models (e.g., sentence-transformers)
2. Implementing embedding caching
3. Adding vector index configuration options
4. Supporting different similarity metrics
5. Batch vector operations for performance