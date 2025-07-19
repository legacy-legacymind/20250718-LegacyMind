#!/usr/bin/env python3.11
"""
Co-occurrence Analyzer - Phase 3 Implementation
Build and analyze thought co-occurrence patterns for context-aware search enhancement
"""

import asyncio
import json
import logging
import math
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
import redis
from collections import defaultdict, Counter
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CooccurrenceAnalyzer:
    """
    Analyze thought co-occurrence patterns for enhanced semantic search.
    
    Phase 3 Features:
    - Track thoughts accessed together in same search sessions
    - Build co-occurrence matrices for related thought suggestions
    - Context-aware relevance boosting based on current session
    - Temporal co-occurrence pattern analysis
    - Chain-level thought relationship mapping
    """
    
    def __init__(self, redis_url: str = None):
        """Initialize the co-occurrence analyzer."""
        self.redis_url = redis_url or self._get_redis_url()
        self.client = None
        self.instances = ['CC', 'CCD', 'CCI']
        
        # Configuration parameters
        self.config = {
            'min_cooccurrence_threshold': 2,  # Minimum co-occurrences to consider
            'temporal_window_hours': 24,      # Window for temporal analysis
            'max_related_suggestions': 10,    # Max related thoughts to suggest
            'decay_factor': 0.1,              # Decay factor for temporal analysis
            'session_timeout_minutes': 30,    # Session grouping timeout
            'boost_strength': 1.5,            # Boost multiplier for related thoughts
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
            logger.info("✅ Co-occurrence analyzer initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            raise
    
    async def build_cooccurrence_matrix(self, instance: str = None) -> Dict[str, Any]:
        """
        Build co-occurrence matrix from search session data.
        
        Args:
            instance: Optional instance to analyze (if None, analyzes all)
            
        Returns:
            Dictionary with co-occurrence statistics and matrix data
        """
        try:
            instances_to_analyze = [instance] if instance else self.instances
            matrix_data = {}
            
            for inst in instances_to_analyze:
                logger.info(f"🔄 Building co-occurrence matrix for {inst}...")
                
                inst_matrix = await self._build_instance_matrix(inst)
                matrix_data[inst] = inst_matrix
                
                logger.info(f"✅ Built matrix for {inst}: {inst_matrix['total_pairs']} pairs, "
                           f"{inst_matrix['unique_thoughts']} unique thoughts")
            
            # Build cross-instance patterns
            overall_stats = await self._calculate_cross_instance_patterns(matrix_data)
            
            return {
                'status': 'completed',
                'timestamp': datetime.now().isoformat(),
                'instances': matrix_data,
                'cross_instance': overall_stats
            }
            
        except Exception as e:
            logger.error(f"❌ Error building co-occurrence matrix: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _build_instance_matrix(self, instance: str) -> Dict[str, Any]:
        """Build co-occurrence matrix for a specific instance."""
        try:
            # Get all search sessions with accessed thoughts
            session_pattern = f"{instance}:search_sessions:*"
            session_keys = await asyncio.to_thread(self.client.keys, session_pattern)
            
            cooccurrence_counts = defaultdict(lambda: defaultdict(int))
            session_count = 0
            total_pairs = 0
            unique_thoughts = set()
            
            for session_key in session_keys:
                try:
                    # Get session access data
                    access_key = f"{session_key}:accessed"
                    accessed_thoughts = await asyncio.to_thread(self.client.hgetall, access_key)
                    
                    if len(accessed_thoughts) < 2:
                        continue  # Need at least 2 thoughts for co-occurrence
                    
                    thought_ids = list(accessed_thoughts.keys())
                    unique_thoughts.update(thought_ids)
                    
                    # Build pairs for this session
                    for i, thought1 in enumerate(thought_ids):
                        for thought2 in thought_ids[i+1:]:
                            # Sort pair to ensure consistency (A,B) same as (B,A)
                            pair = tuple(sorted([thought1, thought2]))
                            cooccurrence_counts[pair[0]][pair[1]] += 1
                            total_pairs += 1
                    
                    session_count += 1
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error processing session {session_key}: {e}")
            
            # Store co-occurrence matrix in Redis
            await self._store_cooccurrence_matrix(instance, cooccurrence_counts)
            
            # Calculate statistics
            significant_pairs = sum(
                1 for thought1_pairs in cooccurrence_counts.values()
                for count in thought1_pairs.values()
                if count >= self.config['min_cooccurrence_threshold']
            )
            
            return {
                'sessions_analyzed': session_count,
                'total_pairs': total_pairs,
                'unique_thoughts': len(unique_thoughts),
                'significant_pairs': significant_pairs,
                'matrix_density': significant_pairs / max(1, len(unique_thoughts) ** 2),
                'avg_cooccurrences_per_pair': total_pairs / max(1, significant_pairs)
            }
            
        except Exception as e:
            logger.error(f"❌ Error building matrix for {instance}: {e}")
            return {'error': str(e)}
    
    async def _store_cooccurrence_matrix(self, instance: str, matrix: Dict):
        """Store co-occurrence matrix in Redis for efficient retrieval."""
        try:
            matrix_key = f"{instance}:cooccurrence_matrix"
            
            # Clear existing matrix
            await asyncio.to_thread(self.client.delete, matrix_key)
            
            # Store significant co-occurrences
            matrix_data = {}
            for thought1, related_thoughts in matrix.items():
                for thought2, count in related_thoughts.items():
                    if count >= self.config['min_cooccurrence_threshold']:
                        pair_key = f"{thought1}:{thought2}"
                        matrix_data[pair_key] = str(count)
            
            if matrix_data:
                await asyncio.to_thread(
                    self.client.hset,
                    matrix_key,
                    mapping=matrix_data
                )
            
            # Also store as sorted sets for efficient retrieval
            for thought1, related_thoughts in matrix.items():
                related_key = f"{instance}:related_thoughts:{thought1}"
                
                # Clear existing related thoughts
                await asyncio.to_thread(self.client.delete, related_key)
                
                # Add related thoughts with co-occurrence scores
                related_scores = {}
                for thought2, count in related_thoughts.items():
                    if count >= self.config['min_cooccurrence_threshold']:
                        related_scores[thought2] = count
                
                if related_scores:
                    await asyncio.to_thread(
                        self.client.zadd,
                        related_key,
                        related_scores
                    )
                    # Expire after 7 days
                    await asyncio.to_thread(self.client.expire, related_key, 604800)
            
            logger.debug(f"✅ Stored co-occurrence matrix for {instance}")
            
        except Exception as e:
            logger.error(f"❌ Error storing co-occurrence matrix: {e}")
    
    async def get_related_thoughts(self, thought_id: str, instance: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get thoughts that co-occur with the given thought.
        
        Args:
            thought_id: The thought to find related thoughts for
            instance: Instance to search in
            limit: Maximum number of related thoughts to return
            
        Returns:
            List of related thoughts with co-occurrence scores
        """
        try:
            limit = limit or self.config['max_related_suggestions']
            related_key = f"{instance}:related_thoughts:{thought_id}"
            
            # Get related thoughts sorted by co-occurrence score
            related_thoughts = await asyncio.to_thread(
                self.client.zrevrange,
                related_key,
                0,
                limit - 1,
                withscores=True
            )
            
            results = []
            for related_id, score in related_thoughts:
                results.append({
                    'thought_id': related_id,
                    'cooccurrence_score': int(score),
                    'relatedness_strength': min(1.0, score / 10.0)  # Normalize to 0-1
                })
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error getting related thoughts for {thought_id}: {e}")
            return []
    
    async def calculate_context_boost(self, current_thoughts: List[str], candidate_thought: str, instance: str) -> float:
        """
        Calculate relevance boost for a candidate thought based on current context.
        
        Args:
            current_thoughts: Thoughts already accessed in current session
            candidate_thought: Thought being considered for search results
            instance: Instance to check co-occurrences in
            
        Returns:
            Boost factor (1.0 = no boost, >1.0 = positive boost)
        """
        try:
            if not current_thoughts:
                return 1.0
            
            boost_factor = 1.0
            total_cooccurrences = 0
            
            for current_thought in current_thoughts:
                # Check co-occurrence in both directions
                pair_key1 = f"{current_thought}:{candidate_thought}"
                pair_key2 = f"{candidate_thought}:{current_thought}"
                
                matrix_key = f"{instance}:cooccurrence_matrix"
                
                score1 = await asyncio.to_thread(self.client.hget, matrix_key, pair_key1)
                score2 = await asyncio.to_thread(self.client.hget, matrix_key, pair_key2)
                
                cooccurrence_score = max(
                    int(score1) if score1 else 0,
                    int(score2) if score2 else 0
                )
                
                total_cooccurrences += cooccurrence_score
            
            if total_cooccurrences > 0:
                # Apply boost based on total co-occurrences
                normalized_score = min(1.0, total_cooccurrences / (len(current_thoughts) * 5))
                boost_factor = 1.0 + (normalized_score * (self.config['boost_strength'] - 1.0))
            
            return boost_factor
            
        except Exception as e:
            logger.error(f"❌ Error calculating context boost: {e}")
            return 1.0
    
    async def analyze_temporal_patterns(self, instance: str, hours_back: int = None) -> Dict[str, Any]:
        """
        Analyze temporal co-occurrence patterns.
        
        Args:
            instance: Instance to analyze
            hours_back: Hours to look back (default from config)
            
        Returns:
            Temporal pattern analysis results
        """
        try:
            hours_back = hours_back or self.config['temporal_window_hours']
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            # Get recent search sessions
            session_pattern = f"{instance}:search_sessions:*"
            session_keys = await asyncio.to_thread(self.client.keys, session_pattern)
            
            temporal_cooccurrences = defaultdict(lambda: defaultdict(list))
            recent_sessions = []
            
            for session_key in session_keys:
                try:
                    session_data = await asyncio.to_thread(self.client.hgetall, session_key)
                    
                    if not session_data or 'timestamp' not in session_data:
                        continue
                    
                    session_time = datetime.fromisoformat(session_data['timestamp'])
                    
                    if session_time < cutoff_time:
                        continue
                    
                    # Get accessed thoughts for this session
                    access_key = f"{session_key}:accessed"
                    accessed_thoughts = await asyncio.to_thread(self.client.hgetall, access_key)
                    
                    if len(accessed_thoughts) >= 2:
                        thought_ids = list(accessed_thoughts.keys())
                        
                        # Record temporal co-occurrences
                        for i, thought1 in enumerate(thought_ids):
                            for thought2 in thought_ids[i+1:]:
                                pair = tuple(sorted([thought1, thought2]))
                                temporal_cooccurrences[pair[0]][pair[1]].append(session_time)
                        
                        recent_sessions.append({
                            'session_id': session_key.split(':')[-1],
                            'timestamp': session_time,
                            'thought_count': len(thought_ids)
                        })
                
                except Exception as e:
                    logger.warning(f"⚠️ Error processing temporal session {session_key}: {e}")
            
            # Calculate temporal statistics
            temporal_stats = {
                'analysis_window_hours': hours_back,
                'sessions_analyzed': len(recent_sessions),
                'total_temporal_pairs': sum(
                    len(times) for thought_pairs in temporal_cooccurrences.values()
                    for times in thought_pairs.values()
                ),
                'unique_temporal_pairs': sum(
                    len(thought_pairs) for thought_pairs in temporal_cooccurrences.values()
                ),
                'temporal_density': 0.0
            }
            
            # Calculate temporal clustering
            clustering_analysis = await self._analyze_temporal_clustering(temporal_cooccurrences)
            temporal_stats.update(clustering_analysis)
            
            return {
                'status': 'completed',
                'timestamp': datetime.now().isoformat(),
                'temporal_stats': temporal_stats,
                'recent_sessions': recent_sessions[-10:],  # Last 10 sessions
                'clustering': clustering_analysis
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing temporal patterns: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _analyze_temporal_clustering(self, temporal_cooccurrences: Dict) -> Dict[str, Any]:
        """Analyze clustering patterns in temporal co-occurrences."""
        try:
            cluster_analysis = {
                'time_clusters': {},
                'burst_periods': [],
                'steady_patterns': []
            }
            
            for thought1, related_thoughts in temporal_cooccurrences.items():
                for thought2, timestamps in related_thoughts.items():
                    if len(timestamps) < 2:
                        continue
                    
                    # Sort timestamps
                    sorted_times = sorted(timestamps)
                    
                    # Calculate time gaps between co-occurrences
                    gaps = []
                    for i in range(1, len(sorted_times)):
                        gap = (sorted_times[i] - sorted_times[i-1]).total_seconds() / 3600  # Hours
                        gaps.append(gap)
                    
                    avg_gap = sum(gaps) / len(gaps) if gaps else 0
                    
                    # Classify pattern
                    if avg_gap < 1:  # Less than 1 hour average gap
                        cluster_analysis['burst_periods'].append({
                            'thought_pair': (thought1, thought2),
                            'occurrences': len(timestamps),
                            'avg_gap_hours': avg_gap,
                            'first_occurrence': sorted_times[0].isoformat(),
                            'last_occurrence': sorted_times[-1].isoformat()
                        })
                    elif avg_gap > 6:  # More than 6 hours average gap
                        cluster_analysis['steady_patterns'].append({
                            'thought_pair': (thought1, thought2),
                            'occurrences': len(timestamps),
                            'avg_gap_hours': avg_gap
                        })
            
            return cluster_analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing temporal clustering: {e}")
            return {}
    
    async def _calculate_cross_instance_patterns(self, matrix_data: Dict) -> Dict[str, Any]:
        """Calculate patterns across federation instances."""
        try:
            cross_patterns = {
                'shared_thoughts': {},
                'instance_similarities': {},
                'federation_wide_stats': {}
            }
            
            # Find thoughts that appear in multiple instances
            all_thoughts = {}
            for instance, data in matrix_data.items():
                if 'error' not in data:
                    instance_thoughts = set()
                    # This would need to be extracted from the actual matrix data
                    # For now, placeholder logic
                    all_thoughts[instance] = instance_thoughts
            
            # Calculate instance similarity based on shared thought patterns
            instances = list(all_thoughts.keys())
            for i, inst1 in enumerate(instances):
                for inst2 in instances[i+1:]:
                    shared = len(all_thoughts[inst1].intersection(all_thoughts[inst2]))
                    total = len(all_thoughts[inst1].union(all_thoughts[inst2]))
                    similarity = shared / total if total > 0 else 0
                    
                    cross_patterns['instance_similarities'][f"{inst1}-{inst2}"] = {
                        'shared_thoughts': shared,
                        'total_unique_thoughts': total,
                        'similarity_score': similarity
                    }
            
            return cross_patterns
            
        except Exception as e:
            logger.error(f"❌ Error calculating cross-instance patterns: {e}")
            return {}
    
    async def get_cooccurrence_stats(self, instance: str = None) -> Dict[str, Any]:
        """Get comprehensive co-occurrence statistics."""
        try:
            instances_to_check = [instance] if instance else self.instances
            stats = {}
            
            for inst in instances_to_check:
                matrix_key = f"{inst}:cooccurrence_matrix"
                
                # Get matrix size
                matrix_size = await asyncio.to_thread(self.client.hlen, matrix_key)
                
                # Sample some high co-occurrence pairs
                all_pairs = await asyncio.to_thread(self.client.hgetall, matrix_key)
                
                if all_pairs:
                    # Sort by co-occurrence count
                    sorted_pairs = sorted(
                        all_pairs.items(),
                        key=lambda x: int(x[1]),
                        reverse=True
                    )
                    
                    top_pairs = sorted_pairs[:10]
                    avg_cooccurrence = sum(int(count) for _, count in all_pairs.items()) / len(all_pairs)
                else:
                    top_pairs = []
                    avg_cooccurrence = 0
                
                stats[inst] = {
                    'matrix_size': matrix_size,
                    'avg_cooccurrence_count': round(avg_cooccurrence, 2),
                    'top_cooccurrence_pairs': [
                        {'pair': pair.split(':'), 'count': int(count)}
                        for pair, count in top_pairs
                    ],
                    'timestamp': datetime.now().isoformat()
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting co-occurrence stats: {e}")
            return {}

# Utility functions

async def rebuild_all_cooccurrence_matrices(redis_url: str = None) -> Dict[str, Any]:
    """Rebuild co-occurrence matrices for all instances."""
    analyzer = CooccurrenceAnalyzer(redis_url)
    
    try:
        await analyzer.initialize()
        result = await analyzer.build_cooccurrence_matrix()
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to rebuild matrices: {e}")
        return {'status': 'failed', 'error': str(e)}
    
    finally:
        if analyzer.client:
            analyzer.client.close()

async def main():
    """Main function for testing co-occurrence analyzer."""
    analyzer = CooccurrenceAnalyzer()
    
    try:
        await analyzer.initialize()
        
        print("🧪 Testing co-occurrence analyzer...")
        
        # Build co-occurrence matrix
        result = await analyzer.build_cooccurrence_matrix('CCD')
        print(f"📊 Matrix build result: {json.dumps(result, indent=2)}")
        
        # Get co-occurrence statistics
        stats = await analyzer.get_cooccurrence_stats('CCD')
        print(f"📈 Co-occurrence stats: {json.dumps(stats, indent=2)}")
        
        # Test temporal analysis
        temporal_result = await analyzer.analyze_temporal_patterns('CCD')
        print(f"⏰ Temporal analysis: {json.dumps(temporal_result, indent=2)}")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        
    finally:
        if analyzer.client:
            analyzer.client.close()

if __name__ == "__main__":
    asyncio.run(main())