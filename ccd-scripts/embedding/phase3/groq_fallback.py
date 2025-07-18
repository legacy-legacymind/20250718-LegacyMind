#!/usr/bin/env python3
"""
Groq fallback implementation for Phase 3 embedding service
Uses Groq LLM to generate semantic features when OpenAI fails
"""

import os
import json
import redis
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import time

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️ Groq not available. Install with: pip install groq")


class GroqEmbeddingFallback:
    """
    Fallback embedding service using Groq LLM for semantic feature extraction
    """
    
    def __init__(self, redis_url: str, groq_api_key: Optional[str] = None):
        self.redis_url = redis_url
        self.redis = redis.from_url(redis_url, decode_responses=True)
        
        # Initialize Groq client
        self.groq_client = None
        if GROQ_AVAILABLE and groq_api_key:
            try:
                self.groq_client = Groq(api_key=groq_api_key)
                print("✅ Groq fallback initialized")
            except Exception as e:
                print(f"⚠️ Groq initialization failed: {e}")
                
        # Fallback metrics
        self.metrics = {
            'fallback_calls': 0,
            'fallback_successes': 0,
            'fallback_failures': 0,
            'semantic_features_generated': 0
        }
        
    def is_available(self) -> bool:
        """Check if Groq fallback is available"""
        return GROQ_AVAILABLE and self.groq_client is not None
    
    async def generate_semantic_features(self, content: str) -> Optional[List[float]]:
        """
        Generate semantic features using Groq LLM
        Returns normalized 1536-dimensional vector for compatibility
        """
        if not self.is_available():
            return None
            
        self.metrics['fallback_calls'] += 1
        
        try:
            # Use Groq to extract semantic features
            prompt = f"""
            Extract key semantic features from this text as a structured analysis:
            
            Text: "{content}"
            
            Provide a JSON response with semantic features including:
            - main_topics: list of 3-5 main topics
            - sentiment: positive/negative/neutral with confidence
            - entities: important entities mentioned
            - concepts: abstract concepts present
            - technical_terms: any technical or specialized terms
            - emotional_tone: emotional characteristics
            - complexity: text complexity level (1-10)
            - keywords: 5-10 most important keywords
            
            Keep response concise and structured.
            """
            
            response = self.groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            # Parse the response
            semantic_data = response.choices[0].message.content
            
            # Convert semantic features to embedding-like vector
            embedding = self._convert_to_embedding(content, semantic_data)
            
            if embedding:
                self.metrics['fallback_successes'] += 1
                self.metrics['semantic_features_generated'] += 1
                
                # Store in Redis with fallback flag
                self._store_fallback_embedding(content, embedding)
                
                return embedding
            else:
                self.metrics['fallback_failures'] += 1
                return None
                
        except Exception as e:
            print(f"❌ Groq fallback failed: {e}")
            self.metrics['fallback_failures'] += 1
            return None
    
    def _convert_to_embedding(self, content: str, semantic_data: str) -> Optional[List[float]]:
        """
        Convert semantic features to 1536-dimensional embedding
        Uses deterministic hashing and semantic analysis
        """
        try:
            # Create base vector using content hash
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            
            # Convert hash to numeric values
            base_vector = []
            for i in range(0, len(content_hash), 2):
                hex_pair = content_hash[i:i+2]
                base_vector.append(int(hex_pair, 16) / 255.0)
            
            # Extend to 1536 dimensions
            while len(base_vector) < 1536:
                base_vector.extend(base_vector[:min(32, 1536 - len(base_vector))])
            
            # Trim to exact size
            base_vector = base_vector[:1536]
            
            # Apply semantic modifications based on LLM response
            semantic_features = self._extract_semantic_features(semantic_data)
            
            # Modify vector based on semantic features
            for i, feature in enumerate(semantic_features):
                if i < len(base_vector):
                    base_vector[i] = (base_vector[i] + feature) / 2.0
            
            # Normalize to unit vector (like OpenAI embeddings)
            magnitude = np.linalg.norm(base_vector)
            if magnitude > 0:
                base_vector = [x / magnitude for x in base_vector]
            
            return base_vector
            
        except Exception as e:
            print(f"❌ Error converting to embedding: {e}")
            return None
    
    def _extract_semantic_features(self, semantic_data: str) -> List[float]:
        """Extract numeric features from semantic analysis"""
        features = []
        
        try:
            # Try to parse as JSON
            if semantic_data.strip().startswith('{'):
                data = json.loads(semantic_data)
                
                # Extract features from structured data
                if 'sentiment' in data:
                    sentiment = data['sentiment']
                    if 'positive' in sentiment.lower():
                        features.extend([0.7, 0.3, 0.1])
                    elif 'negative' in sentiment.lower():
                        features.extend([0.1, 0.3, 0.7])
                    else:
                        features.extend([0.5, 0.5, 0.5])
                
                if 'complexity' in data:
                    complexity = float(data.get('complexity', 5)) / 10.0
                    features.extend([complexity] * 10)
                
                if 'main_topics' in data:
                    topic_count = len(data['main_topics'])
                    features.extend([topic_count / 10.0] * 20)
                
        except:
            # Fallback to simple hashing
            pass
        
        # Generate additional features from text length and characteristics
        text_length = len(semantic_data)
        features.extend([
            text_length / 1000.0,  # Length feature
            len(semantic_data.split()) / 100.0,  # Word count feature
            semantic_data.count(',') / 10.0,  # Complexity feature
        ])
        
        # Pad or trim to reasonable size
        while len(features) < 100:
            features.append(0.5)
        
        return features[:100]
    
    def _store_fallback_embedding(self, content: str, embedding: List[float]):
        """Store fallback embedding with metadata"""
        try:
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            # Store in Redis with fallback flag
            embedding_data = {
                'embedding': embedding,
                'provider': 'groq_fallback',
                'timestamp': datetime.utcnow().isoformat(),
                'content_hash': content_hash,
                'dimensions': len(embedding)
            }
            
            self.redis.hset(
                "fallback_embeddings",
                content_hash,
                json.dumps(embedding_data)
            )
            
            # Update metrics
            self.redis.hincrby("embedding_metrics", "groq_fallback_embeddings", 1)
            
        except Exception as e:
            print(f"⚠️ Error storing fallback embedding: {e}")
    
    def get_fallback_metrics(self) -> Dict[str, Any]:
        """Get fallback usage metrics"""
        return {
            'fallback_calls': self.metrics['fallback_calls'],
            'fallback_successes': self.metrics['fallback_successes'],
            'fallback_failures': self.metrics['fallback_failures'],
            'success_rate': (
                self.metrics['fallback_successes'] / self.metrics['fallback_calls'] * 100
                if self.metrics['fallback_calls'] > 0 else 0
            ),
            'semantic_features_generated': self.metrics['semantic_features_generated']
        }


async def test_groq_fallback():
    """Test Groq fallback functionality"""
    print("🧪 Testing Groq Fallback...")
    
    # Get Redis URL and Groq API key
    redis_password = os.getenv("REDIS_PASSWORD", "")
    redis_url = f"redis://:{redis_password}@localhost:6379" if redis_password else "redis://localhost:6379"
    
    # Get Groq API key from Redis
    r = redis.from_url(redis_url, decode_responses=True)
    groq_api_key = r.get("config:groq_api_key")
    
    if not groq_api_key:
        print("❌ No Groq API key found in Redis")
        return
    
    # Initialize fallback
    fallback = GroqEmbeddingFallback(redis_url, groq_api_key)
    
    if not fallback.is_available():
        print("❌ Groq fallback not available")
        return
    
    # Test embedding generation
    test_content = "Phase 3 embedding optimization with Groq fallback for resilience"
    
    print(f"📝 Testing with content: {test_content}")
    
    start_time = time.time()
    embedding = await fallback.generate_semantic_features(test_content)
    elapsed = time.time() - start_time
    
    if embedding:
        print(f"✅ Generated {len(embedding)}-dimensional embedding in {elapsed:.3f}s")
        print(f"📊 Embedding range: [{min(embedding):.3f}, {max(embedding):.3f}]")
        
        # Show metrics
        metrics = fallback.get_fallback_metrics()
        print(f"📈 Fallback metrics: {metrics}")
        
    else:
        print("❌ Failed to generate embedding")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_groq_fallback())