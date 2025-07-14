# unified-intelligence-vector-service.py - RedisVL integration for UnifiedIntelligence
import asyncio
import json
import redis
from redisvl.index import SearchIndex
from redisvl.query import VectorQuery, FilterQuery
from redisvl.schema import IndexSchema
from redisvl.utils.vectorize import OpenAITextVectorizer
from redisvl.extensions.cache.llm import SemanticCache


class UnifiedIntelligenceVectorService:
    def __init__(self, redis_url: str, openai_api_key: str, instance: str):
        self.redis = redis.from_url(redis_url, password="legacymind_redis_pass")
        self.instance = instance
        
        # OpenAI vectorizer with efficient model
        self.vectorizer = OpenAITextVectorizer(
            model="text-embedding-3-small",  # 1536 dims, $0.02/1M tokens
            api_config={"api_key": openai_api_key}
        )
        
        # Thought index schema
        self.thought_schema = IndexSchema.from_dict({
            "index": {
                "name": f"thoughts_{instance}",
                "prefix": f"{instance}/thoughts/",
                "storage_type": "json"
            },
            "fields": [
                {"name": "instance", "type": "tag"},
                {"name": "thought_id", "type": "tag"},
                {"name": "chain_id", "type": "tag"},
                {"name": "timestamp", "type": "text"},
                {"name": "thought_number", "type": "numeric"},
                {"name": "content", "type": "text"},
                {"name": "embedding", "type": "vector", "attrs": {
                    "algorithm": "hnsw",      # Better than FLAT for scale
                    "dims": 1536,
                    "distance_metric": "cosine",
                    "datatype": "float32",
                    "m": 16,                  # HNSW connection count
                    "ef_construction": 200    # HNSW build quality
                }}
            ]
        })
        
        # Semantic cache for query optimization
        self.query_cache = SemanticCache(
            name=f"query_cache_{instance}",
            prefix=f"{instance}/cache/",
            redis_url=f"{redis_url}?password=legacymind_redis_pass",
            vectorizer=self.vectorizer,  # Use OpenAI vectorizer to avoid HF dependency
            distance_threshold=0.1,  # Very similar queries
            ttl=3600  # 1 hour cache
        )
        
        # Initialize indexes with Redis connection
        self.thought_index = SearchIndex(self.thought_schema, redis_client=self.redis)
        
    async def initialize(self):
        """Create indexes if they don't exist"""
        self.thought_index.create(overwrite=False)
        
    async def embed_thought(self, thought_id: str, content: str, metadata: dict):
        """Embed and store a thought with RedisVL"""
        # Generate embedding - vectorizer.embed is synchronous
        embedding = self.vectorizer.embed(content)
        
        # Prepare document
        doc = {
            "instance": self.instance,
            "thought_id": thought_id,
            "chain_id": metadata.get("chain_id", ""),
            "timestamp": metadata.get("timestamp", ""),
            "thought_number": metadata.get("thought_number", 0),
            "content": content,
            "embedding": embedding
        }
        
        # Store with RedisVL - handles all Redis operations
        self.thought_index.load([doc])
        
    async def semantic_search(self, query: str, limit: int = 10, threshold: float = 0.5) -> list:
        """Semantic search with caching"""
        # Check cache first - SemanticCache.check is synchronous
        cached_result = self.query_cache.check(query)
        if cached_result:
            # cached_result is already parsed, not JSON string
            return cached_result if isinstance(cached_result, list) else json.loads(cached_result)
        
        # Generate query embedding - vectorizer.embed is synchronous
        query_embedding = self.vectorizer.embed(query)
        
        # Create vector query with instance filter
        vector_query = VectorQuery(
            vector=query_embedding,
            vector_field_name="embedding",
            num_results=limit,
            return_fields=["thought_id", "content", "chain_id", "timestamp"],
        )
        
        # Add instance filter using RedisVL's filter system
        from redisvl.query.filter import Tag
        vector_query.set_filter(Tag("instance") == self.instance)
        
        # Execute search
        results = self.thought_index.query(vector_query)
        
        # Process results with similarity filtering
        processed_results = []
        for result in results:
            similarity = 1 - float(result["vector_distance"])
            if similarity >= threshold:
                processed_results.append({
                    "thought_id": result["thought_id"],
                    "content": result["content"],
                    "chain_id": result.get("chain_id"),
                    "timestamp": result.get("timestamp"),
                    "similarity": similarity
                })
        
        # Cache results - cache.store is synchronous  
        self.query_cache.store(query, json.dumps(processed_results))
        
        return processed_results
        
    async def hybrid_search(self, query: str, limit: int = 10) -> list:
        """Combine text and semantic search with intelligent reranking"""
        # Text search using RedisVL FilterQuery
        filter_query = FilterQuery(
            return_fields=["thought_id", "content", "chain_id", "timestamp"],
            filter_expression=f"@content:{query}",
            num_results=limit * 2  # Get more for reranking
        )
        
        text_results = self.thought_index.query(filter_query)
        
        # Semantic search
        semantic_results = await self.semantic_search(query, limit)
        
        # Intelligent merge with score boosting
        combined_results = {}
        
        # Add text results
        for result in text_results:
            thought_id = result["thought_id"]
            combined_results[thought_id] = {
                **result,
                "text_match": True,
                "semantic_match": False,
                "combined_score": 1.0  # Perfect text match
            }
            
        # Add semantic results with score boosting for dual matches
        for result in semantic_results:
            thought_id = result["thought_id"]
            if thought_id in combined_results:
                # Boost dual matches
                combined_results[thought_id]["semantic_match"] = True
                combined_results[thought_id]["combined_score"] = max(
                    combined_results[thought_id]["combined_score"],
                    result["similarity"] * 1.2  # 20% boost for dual matches
                )
            else:
                combined_results[thought_id] = {
                    **result,
                    "text_match": False,
                    "semantic_match": True,
                    "combined_score": result["similarity"]
                }
        
        # Sort by combined score and return top results
        final_results = sorted(
            combined_results.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )[:limit]
        
        return final_results