#!/usr/bin/env python3
"""
Enhanced embedding service with Groq fallback
Uses Groq LLM to generate semantic descriptions as fallback
"""

import sys
import json
import os
import redis
import numpy as np
from openai import OpenAI
import hashlib
import asyncio
from typing import Optional, List, Dict
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmbeddingServiceWithFallback:
    def __init__(self, redis_url: str, openai_api_key: str, groq_api_key: Optional[str], instance: str):
        """Initialize embedding service with fallback support"""
        self.redis_client = redis.from_url(redis_url)
        self.openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        self.groq_api_key = groq_api_key
        self.instance = instance
        
        # Initialize Groq client if available
        self.groq_client = None
        if groq_api_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=groq_api_key)
                logger.info("Groq client initialized for fallback")
            except ImportError:
                logger.warning("Groq library not installed. Run: pip install groq")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")
    
    def _preprocess_text(self, text: str) -> str:
        """Clean and normalize text before embedding generation"""
        if not text:
            return ""
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        # Remove excessive punctuation
        text = re.sub(r'[.]{2,}', '.', text)
        text = re.sub(r'[!]{2,}', '!', text)
        text = re.sub(r'[?]{2,}', '?', text)
        
        return text
    
    def generate_embedding_openai(self, text: str) -> Optional[List[float]]:
        """Generate embedding using OpenAI (primary)"""
        if not self.openai_client:
            return None
            
        try:
            # Preprocess text before sending to API
            processed_text = self._preprocess_text(text)
            
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=processed_text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding generation failed: {e}")
            return None
    
    def generate_embedding_groq_fallback(self, text: str) -> Optional[List[float]]:
        """Generate pseudo-embedding using Groq LLM as fallback"""
        if not self.groq_client:
            return None
            
        try:
            # Use Groq to generate semantic features
            prompt = f"""Analyze this text and provide 10 semantic features as numbers from -1 to 1:
            Text: "{text[:500]}"
            
            Features to analyze:
            1. Technical complexity (-1=simple, 1=complex)
            2. Emotional tone (-1=negative, 1=positive)
            3. Abstractness (-1=concrete, 1=abstract)
            4. Formality (-1=casual, 1=formal)
            5. Urgency (-1=low, 1=high)
            6. Specificity (-1=general, 1=specific)
            7. Actionability (-1=passive, 1=actionable)
            8. Clarity (-1=unclear, 1=clear)
            9. Innovation (-1=conventional, 1=innovative)
            10. Scope (-1=narrow, 1=broad)
            
            Respond with just 10 numbers separated by commas."""
            
            response = self.groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=50
            )
            
            # Parse response - extract numbers from the text
            features_str = response.choices[0].message.content.strip()
            import re
            # Extract all numbers (including negative) from the response
            numbers = re.findall(r'-?\d+\.?\d*', features_str)
            features = [float(x) for x in numbers][:10]
            
            # Ensure we have exactly 10 features
            while len(features) < 10:
                features.append(0.0)
            
            # Create a 1536-dim embedding with these features repeated and hashed
            # This is a hack but maintains compatibility
            embedding = self._expand_features_to_embedding(features, text)
            
            logger.info("Generated Groq fallback embedding")
            return embedding
            
        except Exception as e:
            logger.error(f"Groq fallback embedding failed: {e}")
            return None
    
    def _expand_features_to_embedding(self, features: List[float], text: str) -> List[float]:
        """Expand semantic features to full embedding dimension"""
        # Create deterministic pseudo-random embedding based on text hash
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        seed = int(text_hash[:8], 16)
        np.random.seed(seed)
        
        # Generate base embedding
        base_embedding = np.random.randn(1536) * 0.1  # Small random values
        
        # Inject semantic features at regular intervals
        feature_stride = 1536 // len(features)
        for i, feature in enumerate(features):
            start_idx = i * feature_stride
            end_idx = min((i + 1) * feature_stride, 1536)
            base_embedding[start_idx:end_idx] += feature * 0.2
        
        # Normalize
        norm = np.linalg.norm(base_embedding)
        if norm > 0:
            base_embedding = base_embedding / norm
            
        return base_embedding.tolist()
    
    def _calculate_similarity(self, embedding1: List[float], provider1: str, embedding2: List[float], provider2: str) -> float:
        """Calculate similarity between embeddings, handling mixed providers properly"""
        try:
            a = np.array(embedding1)
            b = np.array(embedding2)
            
            # For OpenAI embeddings, use dot product (they are pre-normalized)
            if provider1 == "openai" and provider2 == "openai":
                return np.dot(a, b)
            
            # For mixed providers or Groq embeddings, use full cosine similarity
            else:
                norm_a = np.linalg.norm(a)
                norm_b = np.linalg.norm(b)
                if norm_a == 0 or norm_b == 0:
                    return 0.0
                return np.dot(a, b) / (norm_a * norm_b)
                
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    def generate_embedding(self, text: str, include_identity: bool = False) -> Dict[str, any]:
        """Generate embedding with fallback support and optional identity context"""
        embedding_text = text
        
        # Add identity context if requested
        if include_identity:
            instance_roles = {
                "CCD": "Database & Architecture Specialist",
                "CC": "Primary Claude Code Instance", 
                "CCI": "UnifiedIntelligence Specialist",
                "DT": "Claude Desktop Instance",
                "CCB": "Split-off Instance"
            }
            role = instance_roles.get(self.instance, "Federation Instance")
            identity_prefix = f"{self.instance} {role}: "
            embedding_text = identity_prefix + text
        
        # Try primary (OpenAI)
        embedding = self.generate_embedding_openai(embedding_text)
        provider = "openai"
        
        # Fallback to Groq if needed
        if embedding is None and self.groq_client:
            logger.warning("OpenAI failed, using Groq fallback")
            embedding = self.generate_embedding_groq_fallback(embedding_text)
            provider = "groq_fallback"
        
        # Return result with metadata
        return {
            "embedding": embedding,
            "provider": provider,
            "dimensions": len(embedding) if embedding else 0,
            "included_identity": include_identity
        }
    
    def store_thought_embedding(self, thought_id: str, content: str, timestamp: int, include_identity: bool = False) -> Dict[str, any]:
        """Store thought with embedding, tracking provider"""
        try:
            result = self.generate_embedding(content, include_identity=include_identity)
            if result["embedding"] is None:
                return {"success": False, "error": "All providers failed"}
            
            # Store embedding with provider metadata
            embedding_data = {
                "thought_id": thought_id,
                "content": content,
                "embedding": result["embedding"],
                "timestamp": timestamp,
                "instance": self.instance,
                "provider": result["provider"],
                "included_identity": result["included_identity"]
            }
            
            # Store in Redis
            key = f"{self.instance}:embeddings:{thought_id}"
            self.redis_client.set(key, json.dumps(embedding_data))
            
            # Also store in sorted set for quick retrieval
            set_key = f"{self.instance}:embedding_index"
            self.redis_client.zadd(set_key, {thought_id: timestamp})
            
            # Track provider metrics
            metrics_key = f"embedding_metrics:{result['provider']}"
            self.redis_client.hincrby(metrics_key, "count", 1)
            
            return {
                "success": True,
                "provider": result["provider"],
                "dimensions": result["dimensions"]
            }
            
        except Exception as e:
            logger.error(f"Error storing thought embedding: {e}")
            return {"success": False, "error": str(e)}
    
    def create_identity_embedding(self, identity_content: str) -> Dict[str, any]:
        """Create an identity-enhanced embedding for identity-related content"""
        import uuid
        import time
        thought_id = f"identity_{uuid.uuid4().hex[:8]}"
        timestamp = int(time.time())
        
        return self.store_thought_embedding(
            thought_id=thought_id,
            content=identity_content,
            timestamp=timestamp,
            include_identity=True
        )
    
    def semantic_search(self, query: str, limit: int = 10, threshold: float = 0.5) -> List[Dict[str, any]]:
        """Perform semantic search with mixed provider support"""
        try:
            query_result = self.generate_embedding(query)
            if query_result["embedding"] is None:
                return []
            
            query_embedding = query_result["embedding"]
            query_provider = query_result["provider"]
            
            # Get all stored embeddings
            pattern = f"{self.instance}:embeddings:*"
            keys = self.redis_client.keys(pattern)
            
            similarities = []
            for key in keys:
                data_str = self.redis_client.get(key)
                if data_str:
                    data = json.loads(data_str)
                    stored_embedding = data["embedding"]
                    stored_provider = data.get("provider", "unknown")
                    
                    # Calculate similarity with provider awareness
                    similarity = self._calculate_similarity(
                        query_embedding, query_provider,
                        stored_embedding, stored_provider
                    )
                    
                    if similarity >= threshold:
                        similarities.append({
                            "thought_id": data["thought_id"],
                            "content": data["content"],
                            "timestamp": data["timestamp"],
                            "similarity": similarity,
                            "provider": stored_provider
                        })
            
            # Sort by similarity and return top results
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            return similarities[:limit]
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []

def main():
    """Test the embedding service with fallback"""
    if len(sys.argv) < 2:
        print("Usage: python3 embedding_service_with_fallback.py test")
        sys.exit(1)
    
    if sys.argv[1] == "test":
        # Get configuration
        redis_password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        redis_url = f"redis://:{redis_password}@localhost:6379/0"
        
        # Get API keys from Redis
        temp_redis = redis.from_url(redis_url)
        openai_key = temp_redis.get('config:openai_api_key')
        groq_key = temp_redis.get('config:groq_api_key')
        
        if openai_key:
            openai_key = openai_key.decode('utf-8') if isinstance(openai_key, bytes) else openai_key
        if groq_key:
            groq_key = groq_key.decode('utf-8') if isinstance(groq_key, bytes) else groq_key
        
        # Create service
        service = EmbeddingServiceWithFallback(redis_url, openai_key, groq_key, "Claude")
        
        # Test embedding generation
        test_text = "This is a test of the embedding service with Groq fallback capabilities."
        
        print("Testing embedding generation...")
        print(f"OpenAI available: {service.openai_client is not None}")
        print(f"Groq available: {service.groq_client is not None}")
        
        # Test with OpenAI
        result = service.store_thought_embedding("test-fallback-1", test_text, int(time.time()))
        print(f"Result: {result}")
        
        # Test fallback by temporarily disabling OpenAI
        service.openai_client = None
        result = service.store_thought_embedding("test-fallback-2", test_text, int(time.time()))
        print(f"Fallback result: {result}")

if __name__ == "__main__":
    import time
    main()