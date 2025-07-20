# UnifiedMind RAG System

**Version**: 0.3.0 (rmcp)  
**Status**: ✅ Operational  
**Last Updated**: July 19, 2025  
**Author**: CC (Claude Code)

A cost-optimized Retrieval-Augmented Generation (RAG) system built for the LegacyMind Federation. Provides semantic search across stored thoughts with intelligent caching and synthesis capabilities.

## 🎯 Key Features

- **Semantic Search**: Vector similarity search across 688+ indexed thoughts
- **Optimized Defaults**: Testing-driven parameters (threshold: 0.35, limit: 20) for quality results
- **Cost Optimization**: Redis caching minimizes OpenAI API costs
- **Query Enhancement**: Groq expands queries with synonyms and related terms  
- **Result Synthesis**: Groq generates comprehensive answers from search results
- **Federation Support**: Search across multiple Claude instances (CC, DT, CCS, CCB)
- **Weighted Scoring**: Combines semantic, temporal, and usage scores

## 🏗️ Architecture

### Cost-Optimized RAG Flow

```
Query → Groq Enhancement → Redis Cache Check → OpenAI Embedding → Qdrant Search → Groq Synthesis
```

## Prerequisites

- Rust 1.70+
- Redis server running (with password authentication)
- Qdrant server running on port 6334
- OpenAI API key for embedding generation
- Groq API key for query enhancement and synthesis
- Docker for running Redis and Qdrant

## Installation

1. Clone and build:
```bash
cd /Users/samuelatagana/Projects/LegacyMind/unified-mind
cargo build --release
```

2. Set environment variables:
```bash
export OPENAI_API_KEY="sk-..."      # Required for embeddings
export GROQ_API_KEY="gsk_..."       # Required for query enhancement/synthesis
export REDIS_PASSWORD="password"    # Required for Redis auth
export REDIS_HOST="localhost"       # Optional, defaults to localhost
export REDIS_PORT="6379"            # Optional, defaults to 6379
export QDRANT_HOST="localhost"      # Optional, defaults to localhost
export QDRANT_PORT="6334"           # Optional, defaults to 6334
export INSTANCE_ID="CC"             # Optional, defaults to CC
```

3. Add to Claude Desktop config:
```json
{
  "mcpServers": {
    "unified-mind": {
      "command": "/Users/samuelatagana/Projects/LegacyMind/unified-mind/target/release/unified-mind",
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "GROQ_API_KEY": "gsk_...",
        "REDIS_PASSWORD": "your-password",
        "INSTANCE_ID": "CC"
      }
    }
  }
}
```

## Usage

The `um_recall` tool accepts the following parameters:

- `query` (required): Search query for semantic similarity
- `limit`: Maximum results to return (default: 20)
- `threshold`: Minimum similarity score 0.0-1.0 (default: 0.35)
- `search_all_instances`: Search across all instances (default: false)
- `instance_filter`: Array of instance IDs to search (e.g., ["CC", "DT"])
- `category_filter`: Filter by category (technical, strategic, operational, relationship)
- `tags_filter`: Array of tags to filter by
- `deep_search`: Currently unused, reserved for future multi-model support

Example:
```
um_recall("Redis vector search implementation", limit=10, threshold=0.5)
```

## Architecture

- **Semantic Search**: Uses OpenAI embeddings for vector similarity search
- **Weighted Scoring**: 
  - Semantic similarity: 50%
  - Temporal relevance: 30% (exponential decay over 30 days)
  - Usage frequency: 20% (based on access patterns)
- **L1 Cache**: Redis caching with 1-hour TTL for repeated queries
- **Connection Pooling**: Efficient resource management for Redis
- **Async Processing**: Non-blocking operations using Tokio runtime

## Collection Structure

Each instance has two collections:
- `{INSTANCE}_thoughts`: Main thought storage
- `{INSTANCE}_identity`: Identity and profile information

Payload fields:
- `content`: The thought text
- `category`: Classification (technical, strategic, etc.)
- `tags`: Array of string tags
- `instance_id`: Source instance
- `created_at`: ISO timestamp
- `updated_at`: ISO timestamp
- `importance`: 1-10 scale
- `relevance`: 1-10 scale

## Development

Enable debug logging:
```bash
export RUST_LOG=unified_mind=debug,rmcp=debug
```

Run tests:
```bash
cargo test
```

## 📊 Performance Metrics

- **Search Speed**: ~400-500ms per query
- **Collection Size**: 688 indexed thoughts (CC_thoughts)
- **Embedding Dimensions**: 1536 (OpenAI text-embedding-3-small)
- **Cache Hit Rate**: High due to 7-day TTL
- **Memory Usage**: Minimal (embeddings cached in Redis)
- **Optimal Threshold**: 0.35 (based on testing - filters noise below this level)
- **Optimal Limit**: 20 (most queries return 10-15 quality results)

## 🔧 Technical Implementation

### Key Fixes (July 19, 2025)

1. **Numeric Point ID Handling**
   ```rust
   // Fixed: Extract UUID from payload for numeric point IDs
   Some(point_id::PointIdOptions::Num(num)) => {
       if let Some(thought_id_value) = json_payload.get("thought_id") {
           Uuid::parse_str(thought_id_str)?
       }
   }
   ```

2. **Field Mapping Corrections**
   ```rust
   // Fixed: Use correct field names from Qdrant payload
   instance_id: json_payload.get("instance")  // was "instance_id"
   created_at: json_payload.get("processed_at")  // was "created_at"
   ```

3. **Search Request Configuration**
   ```rust
   let search_request = SearchPoints {
       collection_name: collection.clone(),
       vector: query_embedding.clone(),
       limit: params.limit as u64,
       score_threshold: Some(params.threshold),
       vector_name: None,  // Default vector for collections
       // ...
   };
   ```

## 🔍 Debugging

### Debug Logging

The system includes comprehensive logging:
```rust
info!("Generated embedding with {} dimensions", query_embedding.len());
info!("Searching with vector of dimension {} in collection {}", query_embedding.len(), collection);
info!("Search returned {} results from {}", results.result.len(), collection);
```

### Testing

```bash
# Test basic search
curl -X POST http://localhost:3000/um_recall \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5}'

# Verify Qdrant data
curl http://localhost:6333/collections/CC_thoughts
```

## 💡 Cost Optimization

### Redis Caching Strategy

- **Embedding Cache**: 7-day TTL reduces OpenAI API calls
- **Query Result Cache**: Short-term caching for repeated queries
- **Usage Tracking**: Metadata for scoring and analytics

### API Usage Minimization

- **Smart Caching**: Aggressive caching with reasonable TTLs
- **Groq for Enhancement**: Cost-effective query expansion
- **Groq for Synthesis**: Cheaper than GPT-4 for result compilation
- **OpenAI Only for Embeddings**: Most cost-effective embedding model

## 🚨 Status

✅ **OPERATIONAL** - The UnifiedMind RAG system is fully functional as of July 19, 2025. All major issues have been resolved:

- ✅ Vector search returns results (was 0 results)
- ✅ Numeric point ID parsing fixed
- ✅ Field mapping corrected
- ✅ Groq integration for query enhancement and synthesis
- ✅ Redis caching operational
- ✅ 688 thoughts indexed and searchable

## 🔮 Future Enhancements

- [ ] Local embedding models (e.g., sentence-transformers)
- [ ] Dynamic collection management
- [ ] Advanced filtering and faceted search
- [ ] Real-time indexing for new thoughts
- [ ] Performance metrics dashboard
- [ ] Cost tracking and budgeting

## 📚 Related Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Detailed system architecture
- [Qdrant Expert Documentation](/Users/samuelatagana/LegacyMind_Vault/Experts/Qdrant/)
- [RAG Implementation Plan](/Users/samuelatagana/LegacyMind_Vault/Claude/CC/20250719-RAG-Implementation-Plan.md)

---

**The UnifiedMind RAG system is now fully operational and ready for production use across the LegacyMind Federation.**