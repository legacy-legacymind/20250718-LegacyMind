#!/usr/bin/env python3.11
"""
Relevance Score Calculator - Phase 2 Implementation
Calculate and update relevance scores based on usage patterns and feedback
"""

import asyncio
import json
import logging
import math
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import redis
import numpy as np
from collections import defaultdict, Counter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RelevanceCalculator:
    """
    Calculate and update relevance scores based on usage patterns and feedback.
    
    Core Features:
    - Access frequency and recency scoring
    - Explicit feedback signal processing
    - Query-thought relevance mapping
    - Cross-instance usage pattern analysis
    - Importance score decay over time
    """
    
    def __init__(self, redis_url: str = None):
        """Initialize the relevance calculator."""
        self.redis_url = redis_url or self._get_redis_url()
        self.client = None
        self.instances = ['CC', 'CCD', 'CCI']
        
        # Scoring parameters (configurable)
        self.scoring_params = {
            'view_weight': 0.3,          # Weight for thought views
            'use_weight': 0.7,           # Weight for thought usage
            'recency_factor': 0.8,       # Exponential decay for recency
            'feedback_multiplier': 2.0,  # Boost for explicit positive feedback
            'negative_feedback_penalty': 0.5,  # Penalty for negative feedback
            'min_relevance_score': 0.1,  # Minimum relevance score
            'max_relevance_score': 10.0, # Maximum relevance score
            'importance_decay_days': 30, # Days for importance to decay by half
        }
        
        # Cache for frequently accessed data
        self.cache = {
            'thought_stats': {},
            'query_patterns': {},
            'last_update': None
        }
    
    def _get_redis_url(self) -> str:
        """Get Redis URL from environment."""
        password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        return f"redis://:{password}@localhost:6379/0"
    
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            await asyncio.to_thread(self.client.ping)
            logger.info("✅ Relevance calculator initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            raise
    
    async def calculate_thought_relevance(self, thought_id: str, instance: str = None) -> Dict[str, Any]:
        """
        Calculate comprehensive relevance score for a specific thought.
        
        Args:
            thought_id: The ID of the thought to score
            instance: Optional instance filter (if None, uses all instances)
            
        Returns:
            Dictionary with relevance metrics and scores
        """
        try:
            # Get all instances to check if instance not specified
            instances_to_check = [instance] if instance else self.instances
            
            total_score = 0.0
            metrics = {
                'thought_id': thought_id,
                'total_views': 0,
                'total_uses': 0,
                'explicit_feedback_count': 0,
                'positive_feedback_count': 0,
                'negative_feedback_count': 0,
                'last_accessed': None,
                'relevance_score': 0.0,
                'importance_score': 5.0,  # Default importance
                'recency_factor': 1.0,
                'instances': {}
            }
            
            # Calculate metrics for each instance
            for inst in instances_to_check:
                inst_metrics = await self._calculate_instance_relevance(thought_id, inst)
                metrics['instances'][inst] = inst_metrics
                
                # Aggregate totals
                metrics['total_views'] += inst_metrics['views']
                metrics['total_uses'] += inst_metrics['uses']
                metrics['explicit_feedback_count'] += inst_metrics['feedback_count']
                metrics['positive_feedback_count'] += inst_metrics['positive_feedback']
                metrics['negative_feedback_count'] += inst_metrics['negative_feedback']
                
                # Track most recent access
                if inst_metrics['last_accessed']:
                    if not metrics['last_accessed'] or inst_metrics['last_accessed'] > metrics['last_accessed']:
                        metrics['last_accessed'] = inst_metrics['last_accessed']
            
            # Get thought metadata (importance, tags, etc.)
            metadata = await self._get_thought_metadata(thought_id, instances_to_check[0] if len(instances_to_check) == 1 else 'CCD')
            if metadata:
                metrics['importance_score'] = metadata.get('importance', 5.0)
                metrics['tags'] = metadata.get('tags', [])
                metrics['created_at'] = metadata.get('created_at')
            
            # Calculate combined relevance score
            base_score = await self._calculate_base_relevance_score(metrics)
            recency_score = await self._calculate_recency_factor(metrics['last_accessed'], metrics.get('created_at'))
            feedback_score = await self._calculate_feedback_score(metrics)
            importance_factor = await self._calculate_importance_factor(metrics['importance_score'], metrics.get('created_at'))
            
            # Combine all factors
            final_score = base_score * recency_score * feedback_score * importance_factor
            
            # Apply bounds
            final_score = max(self.scoring_params['min_relevance_score'], 
                             min(self.scoring_params['max_relevance_score'], final_score))
            
            metrics['relevance_score'] = round(final_score, 3)
            metrics['recency_factor'] = round(recency_score, 3)
            metrics['base_score'] = round(base_score, 3)
            metrics['feedback_score'] = round(feedback_score, 3)
            metrics['importance_factor'] = round(importance_factor, 3)
            
            # Store updated relevance score
            await self._store_relevance_score(thought_id, instance or 'ALL', metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error calculating relevance for {thought_id}: {e}")
            return {'thought_id': thought_id, 'error': str(e)}
    
    async def _calculate_instance_relevance(self, thought_id: str, instance: str) -> Dict[str, Any]:
        """Calculate relevance metrics for a specific instance."""
        metrics = {
            'views': 0,
            'uses': 0,
            'feedback_count': 0,
            'positive_feedback': 0,
            'negative_feedback': 0,
            'last_accessed': None,
            'search_appearances': 0
        }
        
        try:
            # Count thought access events from feedback streams
            stream_key = f"{instance}:feedback_events"
            
            # Read all events from stream (this could be optimized with time ranges)
            try:
                events = await asyncio.to_thread(
                    self.client.xrange,
                    stream_key,
                    '-',
                    '+',
                    count=10000  # Limit to prevent memory issues
                )
                
                for event_id, fields in events:
                    event_type = fields.get('event_type')
                    event_thought_id = fields.get('thought_id')
                    
                    if event_thought_id == thought_id:
                        timestamp = self._parse_timestamp(fields.get('timestamp'))
                        
                        if event_type == 'thought_accessed':
                            action = fields.get('action', 'viewed')
                            if action == 'viewed':
                                metrics['views'] += 1
                            elif action in ['used', 'used_in_context']:
                                metrics['uses'] += 1
                            
                            # Update last accessed
                            if not metrics['last_accessed'] or timestamp > metrics['last_accessed']:
                                metrics['last_accessed'] = timestamp
                                
                        elif event_type == 'feedback_provided':
                            feedback = fields.get('feedback', 'neutral')
                            metrics['feedback_count'] += 1
                            
                            if feedback in ['relevant', 'useful', 'helpful']:
                                metrics['positive_feedback'] += 1
                            elif feedback in ['irrelevant', 'useless', 'unhelpful']:
                                metrics['negative_feedback'] += 1
                        
                        elif event_type == 'search_performed':
                            # This thought appeared in search results
                            metrics['search_appearances'] += 1
                
            except redis.RedisError as e:
                logger.warning(f"⚠️ Could not read feedback events for {instance}: {e}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error calculating instance relevance for {instance}:{thought_id}: {e}")
            return metrics
    
    async def _get_thought_metadata(self, thought_id: str, instance: str) -> Optional[Dict]:
        """Get thought metadata including importance, tags, creation time."""
        try:
            meta_key = f"{instance}:thought_meta:{thought_id}"
            
            # Try to get metadata
            metadata = await asyncio.to_thread(self.client.hgetall, meta_key)
            
            if metadata:
                # Parse JSON fields if they exist
                for key in ['tags', 'category']:
                    if key in metadata:
                        try:
                            metadata[key] = json.loads(metadata[key])
                        except (json.JSONDecodeError, TypeError):
                            pass
                
                # Convert numeric fields
                for key in ['importance', 'relevance']:
                    if key in metadata:
                        try:
                            metadata[key] = float(metadata[key])
                        except (ValueError, TypeError):
                            pass
                
                return metadata
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Could not get metadata for {thought_id}: {e}")
            return None
    
    async def _calculate_base_relevance_score(self, metrics: Dict) -> float:
        """Calculate base relevance score from usage patterns."""
        views = metrics['total_views']
        uses = metrics['total_uses']
        
        if views == 0 and uses == 0:
            return self.scoring_params['min_relevance_score']
        
        # Calculate weighted score
        view_score = views * self.scoring_params['view_weight']
        use_score = uses * self.scoring_params['use_weight']
        
        # Apply logarithmic scaling to prevent score explosion
        total_interactions = views + uses
        if total_interactions > 0:
            base_score = (view_score + use_score) * math.log(1 + total_interactions)
        else:
            base_score = self.scoring_params['min_relevance_score']
        
        return max(self.scoring_params['min_relevance_score'], base_score)
    
    async def _calculate_recency_factor(self, last_accessed: Optional[datetime], created_at: Optional[str]) -> float:
        """Calculate recency factor based on last access time."""
        if not last_accessed:
            # If never accessed, use creation time if available
            if created_at:
                try:
                    created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    last_accessed = created_time
                except (ValueError, AttributeError):
                    return 0.5  # Default for no access info
            else:
                return 0.5  # Default for no access info
        
        # Calculate days since last access
        now = datetime.now(last_accessed.tzinfo) if last_accessed.tzinfo else datetime.now()
        days_since_access = (now - last_accessed).total_seconds() / (24 * 3600)
        
        # Exponential decay based on recency
        recency_factor = math.exp(-days_since_access * (1 - self.scoring_params['recency_factor']))
        
        return max(0.1, min(1.0, recency_factor))
    
    async def _calculate_feedback_score(self, metrics: Dict) -> float:
        """Calculate feedback score multiplier."""
        positive = metrics['positive_feedback_count']
        negative = metrics['negative_feedback_count']
        
        if positive == 0 and negative == 0:
            return 1.0  # Neutral - no feedback
        
        # Calculate net feedback ratio
        total_feedback = positive + negative
        if total_feedback == 0:
            return 1.0
        
        positive_ratio = positive / total_feedback
        
        # Apply feedback multiplier
        if positive_ratio > 0.6:  # Mostly positive
            return self.scoring_params['feedback_multiplier']
        elif positive_ratio < 0.4:  # Mostly negative
            return self.scoring_params['negative_feedback_penalty']
        else:
            return 1.0  # Neutral feedback
    
    async def _calculate_importance_factor(self, importance: float, created_at: Optional[str]) -> float:
        """Calculate importance factor with decay over time."""
        if not created_at:
            return importance / 10.0  # Normalize to 0-1 range
        
        try:
            created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            now = datetime.now(created_time.tzinfo) if created_time.tzinfo else datetime.now()
            days_since_creation = (now - created_time).total_seconds() / (24 * 3600)
            
            # Apply importance decay
            decay_factor = math.exp(-days_since_creation / self.scoring_params['importance_decay_days'])
            
            # Normalize importance (1-10 scale to 0.1-1.0 factor)
            normalized_importance = (importance / 10.0)
            
            return normalized_importance * decay_factor
            
        except (ValueError, AttributeError):
            return importance / 10.0  # Fallback to basic normalization
    
    async def _store_relevance_score(self, thought_id: str, instance: str, metrics: Dict):
        """Store calculated relevance score for future use."""
        try:
            relevance_key = f"{instance}:relevance:{thought_id}"
            
            # Store relevance data
            relevance_data = {
                'score': metrics['relevance_score'],
                'last_calculated': datetime.now().isoformat(),
                'total_views': metrics['total_views'],
                'total_uses': metrics['total_uses'],
                'feedback_score': metrics.get('feedback_score', 1.0),
                'recency_factor': metrics.get('recency_factor', 1.0),
                'importance_factor': metrics.get('importance_factor', 0.5)
            }
            
            await asyncio.to_thread(
                self.client.hset,
                relevance_key,
                mapping=relevance_data
            )
            
            # Also update sorted set for quick retrieval of top thoughts
            relevance_ranking_key = f"{instance}:relevance_ranking"
            await asyncio.to_thread(
                self.client.zadd,
                relevance_ranking_key,
                {thought_id: metrics['relevance_score']}
            )
            
            logger.debug(f"✅ Stored relevance score for {thought_id}: {metrics['relevance_score']}")
            
        except Exception as e:
            logger.error(f"❌ Error storing relevance score for {thought_id}: {e}")
    
    async def calculate_query_similarity(self, query1: str, query2: str) -> float:
        """
        Calculate similarity between two search queries using simple text similarity.
        Future enhancement: use embedding similarity.
        """
        try:
            # Simple word overlap similarity
            words1 = set(query1.lower().split())
            words2 = set(query2.lower().split())
            
            if not words1 or not words2:
                return 0.0
            
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            jaccard_similarity = len(intersection) / len(union) if union else 0.0
            
            return jaccard_similarity
            
        except Exception as e:
            logger.error(f"❌ Error calculating query similarity: {e}")
            return 0.0
    
    async def build_query_clusters(self, instance: str = None) -> Dict[str, List[str]]:
        """
        Build clusters of similar queries for relevance sharing.
        """
        try:
            instances_to_process = [instance] if instance else self.instances
            all_queries = []
            
            # Extract unique queries from feedback events
            for inst in instances_to_process:
                stream_key = f"{inst}:feedback_events"
                
                try:
                    events = await asyncio.to_thread(
                        self.client.xrange,
                        stream_key,
                        '-',
                        '+',
                        count=5000
                    )
                    
                    for event_id, fields in events:
                        if fields.get('event_type') == 'search_performed':
                            query = fields.get('query', '').strip()
                            if query and len(query) > 3:  # Filter out very short queries
                                all_queries.append(query)
                                
                except redis.RedisError as e:
                    logger.warning(f"⚠️ Could not read queries from {inst}: {e}")
            
            # Remove duplicates and cluster by similarity
            unique_queries = list(set(all_queries))
            clusters = {}
            processed = set()
            
            for i, query in enumerate(unique_queries):
                if query in processed:
                    continue
                
                cluster = [query]
                processed.add(query)
                
                # Find similar queries
                for j, other_query in enumerate(unique_queries[i+1:], i+1):
                    if other_query in processed:
                        continue
                    
                    similarity = await self.calculate_query_similarity(query, other_query)
                    if similarity > 0.3:  # Similarity threshold
                        cluster.append(other_query)
                        processed.add(other_query)
                
                if len(cluster) > 1:  # Only keep clusters with multiple queries
                    cluster_name = f"cluster_{len(clusters)}"
                    clusters[cluster_name] = cluster
            
            logger.info(f"✅ Built {len(clusters)} query clusters from {len(unique_queries)} unique queries")
            return clusters
            
        except Exception as e:
            logger.error(f"❌ Error building query clusters: {e}")
            return {}
    
    async def get_top_relevant_thoughts(self, instance: str, limit: int = 10) -> List[Dict]:
        """Get top relevant thoughts for an instance."""
        try:
            relevance_ranking_key = f"{instance}:relevance_ranking"
            
            # Get top thoughts by relevance score
            top_thoughts = await asyncio.to_thread(
                self.client.zrevrange,
                relevance_ranking_key,
                0,
                limit - 1,
                withscores=True
            )
            
            results = []
            for thought_id, score in top_thoughts:
                # Get detailed relevance info
                relevance_key = f"{instance}:relevance:{thought_id}"
                relevance_data = await asyncio.to_thread(self.client.hgetall, relevance_key)
                
                if relevance_data:
                    result = {
                        'thought_id': thought_id,
                        'relevance_score': float(score),
                        **relevance_data
                    }
                    results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error getting top relevant thoughts for {instance}: {e}")
            return []
    
    async def update_relevance_for_instance(self, instance: str, max_thoughts: int = 1000) -> Dict[str, Any]:
        """Update relevance scores for all thoughts in an instance."""
        try:
            logger.info(f"🔄 Updating relevance scores for {instance}...")
            
            # Get all thought IDs for this instance
            thought_pattern = f"{instance}:thoughts:*"
            thought_keys = await asyncio.to_thread(
                self.client.keys,
                thought_pattern
            )
            
            # Extract thought IDs
            thought_ids = [key.split(':')[-1] for key in thought_keys[:max_thoughts]]
            
            updated_count = 0
            errors = []
            
            for thought_id in thought_ids:
                try:
                    relevance_metrics = await self.calculate_thought_relevance(thought_id, instance)
                    if 'error' not in relevance_metrics:
                        updated_count += 1
                    else:
                        errors.append(f"{thought_id}: {relevance_metrics['error']}")
                        
                except Exception as e:
                    errors.append(f"{thought_id}: {str(e)}")
            
            result = {
                'instance': instance,
                'total_thoughts': len(thought_ids),
                'updated_count': updated_count,
                'error_count': len(errors),
                'errors': errors[:10],  # Limit error list
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Updated {updated_count}/{len(thought_ids)} relevance scores for {instance}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error updating relevance for {instance}: {e}")
            return {'instance': instance, 'error': str(e)}
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse timestamp string to datetime object."""
        if not timestamp_str:
            return None
        
        try:
            # Handle various timestamp formats
            if timestamp_str.endswith('Z'):
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            elif '+' in timestamp_str or timestamp_str.endswith('UTC'):
                return datetime.fromisoformat(timestamp_str.replace('UTC', '').strip())
            else:
                return datetime.fromisoformat(timestamp_str)
                
        except (ValueError, AttributeError):
            return None

# Utility functions for testing and batch operations

async def batch_update_relevance(redis_url: str = None, instances: List[str] = None) -> Dict[str, Any]:
    """Batch update relevance scores for multiple instances."""
    calculator = RelevanceCalculator(redis_url)
    
    try:
        await calculator.initialize()
        
        target_instances = instances or calculator.instances
        results = {}
        
        for instance in target_instances:
            result = await calculator.update_relevance_for_instance(instance)
            results[instance] = result
        
        return {
            'status': 'completed',
            'timestamp': datetime.now().isoformat(),
            'results': results
        }
        
    except Exception as e:
        logger.error(f"❌ Batch update failed: {e}")
        return {'status': 'failed', 'error': str(e)}
    
    finally:
        if calculator.client:
            calculator.client.close()

async def main():
    """Main function for testing relevance calculator."""
    calculator = RelevanceCalculator()
    
    try:
        await calculator.initialize()
        
        # Test relevance calculation
        print("🧪 Testing relevance calculation...")
        
        # Update relevance for CCD instance
        result = await calculator.update_relevance_for_instance('CCD', max_thoughts=10)
        print(f"📊 Update result: {json.dumps(result, indent=2)}")
        
        # Get top relevant thoughts
        top_thoughts = await calculator.get_top_relevant_thoughts('CCD', limit=5)
        print(f"🏆 Top relevant thoughts: {json.dumps(top_thoughts, indent=2)}")
        
        # Build query clusters
        clusters = await calculator.build_query_clusters('CCD')
        print(f"🔗 Query clusters: {json.dumps(clusters, indent=2)}")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        
    finally:
        if calculator.client:
            calculator.client.close()

if __name__ == "__main__":
    asyncio.run(main())