#!/usr/bin/env python3.11
"""
Tag Hierarchy Manager - Phase 3 Implementation
Advanced tag organization with parent-child relationships and semantic clustering
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
import redis
from collections import defaultdict, Counter
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TagHierarchyManager:
    """
    Manage advanced tag hierarchies with parent-child relationships.
    
    Phase 3 Features:
    - Hierarchical tag structure with inheritance
    - Automatic parent tag suggestion based on patterns
    - Tag merging and consolidation
    - Semantic tag clustering
    - Hierarchical search with tag expansion
    - Tag usage statistics and optimization recommendations
    """
    
    def __init__(self, redis_url: str = None):
        """Initialize the tag hierarchy manager."""
        self.redis_url = redis_url or self._get_redis_url()
        self.client = None
        self.instances = ['CC', 'CCD', 'CCI']
        
        # Predefined hierarchies (can be dynamically updated)
        self.base_hierarchies = {
            # Technology hierarchy
            'technology': {
                'database': ['redis', 'postgres', 'mysql', 'mongodb', 'sqlite', 'qdrant'],
                'programming': ['python', 'rust', 'javascript', 'typescript', 'go', 'java'],
                'frontend': ['react', 'vue', 'angular', 'html', 'css', 'javascript'],
                'backend': ['api', 'server', 'microservices', 'rest', 'graphql'],
                'infrastructure': ['docker', 'kubernetes', 'aws', 'azure', 'gcp', 'nginx'],
                'ai_ml': ['machine learning', 'nlp', 'neural networks', 'deep learning', 'embedding'],
            },
            
            # Architecture hierarchy  
            'architecture': {
                'patterns': ['microservices', 'monolith', 'mvc', 'event-driven', 'layered'],
                'components': ['api', 'database', 'cache', 'queue', 'load balancer'],
                'principles': ['solid', 'dry', 'kiss', 'separation of concerns'],
                'styles': ['rest', 'soap', 'graphql', 'rpc', 'event-sourcing'],
            },
            
            # Process hierarchy
            'process': {
                'development': ['coding', 'testing', 'debugging', 'refactoring', 'review'],
                'deployment': ['ci/cd', 'staging', 'production', 'rollback', 'monitoring'],
                'management': ['planning', 'estimation', 'tracking', 'reporting'],
                'quality': ['testing', 'linting', 'coverage', 'performance', 'security'],
            },
            
            # Domain hierarchy
            'domain': {
                'business': ['requirements', 'stakeholders', 'processes', 'rules'],
                'technical': ['implementation', 'architecture', 'performance', 'maintenance'],
                'operational': ['monitoring', 'deployment', 'scaling', 'troubleshooting'],
                'strategic': ['planning', 'roadmap', 'vision', 'goals', 'priorities'],
            }
        }
        
        # Configuration
        self.config = {
            'min_tag_frequency_for_hierarchy': 3,  # Minimum uses to consider for hierarchy
            'similarity_threshold': 0.7,           # Threshold for tag similarity
            'max_hierarchy_depth': 4,              # Maximum depth of hierarchy
            'auto_merge_threshold': 0.9,           # Auto-merge tags above this similarity
            'tag_consolidation_min_freq': 5,       # Min frequency for consolidation
        }
    
    def _get_redis_url(self) -> str:
        """Get Redis URL from environment."""
        password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        return f"redis://:{password}@localhost:6379/0"
    
    async def initialize(self):
        """Initialize Redis connection and load base hierarchies."""
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            await asyncio.to_thread(self.client.ping)
            
            # Initialize base hierarchies in Redis
            await self._initialize_base_hierarchies()
            
            logger.info("✅ Tag hierarchy manager initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            raise
    
    async def _initialize_base_hierarchies(self):
        """Load base hierarchies into Redis."""
        try:
            hierarchy_key = "global:tag_hierarchies"
            
            # Store hierarchies as JSON
            hierarchy_data = json.dumps(self.base_hierarchies)
            await asyncio.to_thread(
                self.client.set,
                hierarchy_key,
                hierarchy_data
            )
            
            # Build reverse lookup (child -> parents)
            reverse_lookup = {}
            for root, categories in self.base_hierarchies.items():
                for category, tags in categories.items():
                    for tag in tags:
                        if tag not in reverse_lookup:
                            reverse_lookup[tag] = []
                        reverse_lookup[tag].append(f"{root}.{category}")
            
            reverse_key = "global:tag_parents"
            reverse_data = json.dumps(reverse_lookup)
            await asyncio.to_thread(
                self.client.set,
                reverse_key,
                reverse_data
            )
            
            logger.debug("✅ Initialized base tag hierarchies")
            
        except Exception as e:
            logger.error(f"❌ Error initializing hierarchies: {e}")
    
    async def build_dynamic_hierarchy(self, instance: str = None) -> Dict[str, Any]:
        """
        Build dynamic tag hierarchy based on usage patterns and co-occurrence.
        
        Args:
            instance: Optional instance to analyze (if None, analyzes all)
            
        Returns:
            Dynamic hierarchy structure and statistics
        """
        try:
            instances_to_analyze = [instance] if instance else self.instances
            hierarchy_results = {}
            
            for inst in instances_to_analyze:
                logger.info(f"🔄 Building dynamic hierarchy for {inst}...")
                
                # Get tag usage statistics
                tag_stats = await self._get_tag_usage_stats(inst)
                
                # Analyze tag co-occurrence patterns  
                cooccurrence_patterns = await self._analyze_tag_cooccurrence(inst, tag_stats)
                
                # Build hierarchy based on patterns
                dynamic_hierarchy = await self._build_hierarchy_from_patterns(
                    inst, tag_stats, cooccurrence_patterns
                )
                
                # Merge with base hierarchy
                merged_hierarchy = await self._merge_hierarchies(dynamic_hierarchy)
                
                hierarchy_results[inst] = {
                    'tag_count': len(tag_stats),
                    'hierarchy_depth': self._calculate_hierarchy_depth(merged_hierarchy),
                    'dynamic_categories': len(dynamic_hierarchy),
                    'merged_hierarchy': merged_hierarchy,
                    'usage_stats': tag_stats,
                    'patterns': cooccurrence_patterns
                }
                
                # Store hierarchy for instance
                await self._store_instance_hierarchy(inst, merged_hierarchy)
                
                logger.info(f"✅ Built hierarchy for {inst}: {len(tag_stats)} tags, "
                           f"{len(dynamic_hierarchy)} dynamic categories")
            
            return {
                'status': 'completed',
                'timestamp': datetime.now().isoformat(),
                'instances': hierarchy_results
            }
            
        except Exception as e:
            logger.error(f"❌ Error building dynamic hierarchy: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _get_tag_usage_stats(self, instance: str) -> Dict[str, Dict[str, Any]]:
        """Get comprehensive tag usage statistics."""
        try:
            # Get tag popularity from Redis
            popularity_key = f"{instance}:tag_popularity"
            popular_tags = await asyncio.to_thread(
                self.client.zrevrange,
                popularity_key,
                0,
                -1,
                withscores=True
            )
            
            tag_stats = {}
            for tag, count in popular_tags:
                tag_stats[tag] = {
                    'usage_count': int(count),
                    'frequency_rank': len(tag_stats) + 1,
                    'normalized_frequency': 0.0  # Will be calculated below
                }
            
            # Normalize frequencies
            if tag_stats:
                max_count = max(stats['usage_count'] for stats in tag_stats.values())
                for tag, stats in tag_stats.items():
                    stats['normalized_frequency'] = stats['usage_count'] / max_count
            
            return tag_stats
            
        except Exception as e:
            logger.error(f"❌ Error getting tag usage stats: {e}")
            return {}
    
    async def _analyze_tag_cooccurrence(self, instance: str, tag_stats: Dict) -> Dict[str, Any]:
        """Analyze tag co-occurrence patterns for hierarchy building."""
        try:
            # Get co-occurrence data
            cooccur_key = f"{instance}:tag_cooccurrence"
            cooccur_data = await asyncio.to_thread(self.client.hgetall, cooccur_key)
            
            # Parse co-occurrence pairs
            tag_relationships = defaultdict(lambda: defaultdict(int))
            
            for pair_key, count in cooccur_data.items():
                if ':' in pair_key:
                    tag1, tag2 = pair_key.split(':', 1)
                    count_val = int(count)
                    
                    tag_relationships[tag1][tag2] = count_val
                    tag_relationships[tag2][tag1] = count_val  # Symmetric
            
            # Find potential parent-child relationships
            potential_hierarchies = {}
            
            for tag, related_tags in tag_relationships.items():
                if tag not in tag_stats:
                    continue
                
                # A tag might be a parent if it co-occurs with many other tags
                # and has high usage frequency
                tag_frequency = tag_stats[tag]['usage_count']
                related_count = len(related_tags)
                
                if (tag_frequency >= self.config['min_tag_frequency_for_hierarchy'] and
                    related_count >= 3):  # Co-occurs with at least 3 other tags
                    
                    # Potential parent tag
                    children = []
                    for related_tag, cooccur_count in related_tags.items():
                        if (related_tag in tag_stats and
                            cooccur_count >= 2 and  # Minimum co-occurrence
                            tag_stats[related_tag]['usage_count'] <= tag_frequency):
                            children.append({
                                'tag': related_tag,
                                'cooccurrence': cooccur_count,
                                'strength': cooccur_count / tag_frequency
                            })
                    
                    if children:
                        potential_hierarchies[tag] = sorted(
                            children, 
                            key=lambda x: x['strength'], 
                            reverse=True
                        )
            
            return {
                'tag_relationships': dict(tag_relationships),
                'potential_hierarchies': potential_hierarchies,
                'relationship_count': len(tag_relationships)
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing tag co-occurrence: {e}")
            return {}
    
    async def _build_hierarchy_from_patterns(self, instance: str, tag_stats: Dict, patterns: Dict) -> Dict[str, List[str]]:
        """Build dynamic hierarchy from analyzed patterns."""
        try:
            dynamic_hierarchy = {}
            potential_hierarchies = patterns.get('potential_hierarchies', {})
            
            for parent_tag, children_data in potential_hierarchies.items():
                # Filter children by strength threshold
                strong_children = [
                    child['tag'] for child in children_data
                    if child['strength'] > 0.2  # At least 20% co-occurrence rate
                ]
                
                if len(strong_children) >= 2:  # Need at least 2 children
                    dynamic_hierarchy[parent_tag] = strong_children[:10]  # Limit to top 10
            
            # Look for semantic groupings based on tag names
            semantic_groups = await self._find_semantic_groups(tag_stats)
            
            # Merge semantic groups into hierarchy
            for group_name, group_tags in semantic_groups.items():
                if group_name not in dynamic_hierarchy:
                    dynamic_hierarchy[group_name] = group_tags
                else:
                    # Merge with existing
                    existing_tags = set(dynamic_hierarchy[group_name])
                    new_tags = set(group_tags)
                    dynamic_hierarchy[group_name] = list(existing_tags.union(new_tags))
            
            return dynamic_hierarchy
            
        except Exception as e:
            logger.error(f"❌ Error building hierarchy from patterns: {e}")
            return {}
    
    async def _find_semantic_groups(self, tag_stats: Dict) -> Dict[str, List[str]]:
        """Find semantic groups based on tag name patterns."""
        try:
            semantic_groups = {}
            tags = list(tag_stats.keys())
            
            # Group by common prefixes/suffixes
            prefix_groups = defaultdict(list)
            suffix_groups = defaultdict(list)
            
            for tag in tags:
                # Check for common prefixes (3+ characters)
                if len(tag) > 5:
                    prefix = tag[:3]
                    if len([t for t in tags if t.startswith(prefix)]) >= 2:
                        prefix_groups[f"{prefix}_group"].append(tag)
                
                # Check for common suffixes
                if len(tag) > 5:
                    suffix = tag[-3:]
                    if len([t for t in tags if t.endswith(suffix)]) >= 2:
                        suffix_groups[f"{suffix}_group"].append(tag)
            
            # Group by semantic patterns
            patterns = {
                'config_group': [tag for tag in tags if 'config' in tag or 'setting' in tag],
                'error_group': [tag for tag in tags if 'error' in tag or 'fail' in tag or 'bug' in tag],
                'performance_group': [tag for tag in tags if 'performance' in tag or 'speed' in tag or 'optimization' in tag],
                'security_group': [tag for tag in tags if 'security' in tag or 'auth' in tag or 'permission' in tag],
                'test_group': [tag for tag in tags if 'test' in tag or 'spec' in tag or 'mock' in tag],
                'data_group': [tag for tag in tags if 'data' in tag or 'database' in tag or 'storage' in tag],
                'network_group': [tag for tag in tags if 'network' in tag or 'http' in tag or 'api' in tag or 'endpoint' in tag],
                'ui_group': [tag for tag in tags if 'ui' in tag or 'interface' in tag or 'component' in tag or 'view' in tag],
            }
            
            # Only keep groups with 2+ tags
            for group_name, group_tags in patterns.items():
                if len(group_tags) >= 2:
                    semantic_groups[group_name] = group_tags
            
            return semantic_groups
            
        except Exception as e:
            logger.error(f"❌ Error finding semantic groups: {e}")
            return {}
    
    async def _merge_hierarchies(self, dynamic_hierarchy: Dict) -> Dict[str, Any]:
        """Merge dynamic hierarchy with base hierarchy."""
        try:
            # Get base hierarchy
            hierarchy_key = "global:tag_hierarchies"
            base_data = await asyncio.to_thread(self.client.get, hierarchy_key)
            
            if base_data:
                base_hierarchy = json.loads(base_data)
            else:
                base_hierarchy = self.base_hierarchies
            
            # Create merged structure
            merged = {}
            
            # Start with base hierarchy
            for root, categories in base_hierarchy.items():
                merged[root] = dict(categories)
            
            # Add dynamic categories
            if 'dynamic' not in merged:
                merged['dynamic'] = {}
            
            for category, tags in dynamic_hierarchy.items():
                merged['dynamic'][category] = tags
            
            return merged
            
        except Exception as e:
            logger.error(f"❌ Error merging hierarchies: {e}")
            return dynamic_hierarchy
    
    def _calculate_hierarchy_depth(self, hierarchy: Dict) -> int:
        """Calculate maximum depth of hierarchy."""
        max_depth = 0
        
        def traverse(node, depth):
            nonlocal max_depth
            max_depth = max(max_depth, depth)
            
            if isinstance(node, dict):
                for child in node.values():
                    traverse(child, depth + 1)
        
        traverse(hierarchy, 0)
        return max_depth
    
    async def _store_instance_hierarchy(self, instance: str, hierarchy: Dict):
        """Store hierarchy for specific instance."""
        try:
            hierarchy_key = f"{instance}:tag_hierarchy"
            hierarchy_data = json.dumps(hierarchy)
            
            await asyncio.to_thread(
                self.client.set,
                hierarchy_key,
                hierarchy_data
            )
            
            # Store flattened lookup for quick access
            flattened = {}
            
            def flatten(node, path=""):
                if isinstance(node, dict):
                    for key, value in node.items():
                        new_path = f"{path}.{key}" if path else key
                        flatten(value, new_path)
                elif isinstance(node, list):
                    for tag in node:
                        flattened[tag] = path
            
            flatten(hierarchy)
            
            lookup_key = f"{instance}:tag_hierarchy_lookup"
            lookup_data = json.dumps(flattened)
            
            await asyncio.to_thread(
                self.client.set,
                lookup_key,
                lookup_data
            )
            
            logger.debug(f"✅ Stored hierarchy for {instance}")
            
        except Exception as e:
            logger.error(f"❌ Error storing hierarchy: {e}")
    
    async def get_tag_parents(self, tag: str, instance: str = None) -> List[str]:
        """
        Get parent categories for a given tag.
        
        Args:
            tag: Tag to find parents for
            instance: Instance to check (if None, checks global)
            
        Returns:
            List of parent category paths
        """
        try:
            if instance:
                lookup_key = f"{instance}:tag_hierarchy_lookup"
            else:
                lookup_key = "global:tag_parents"
            
            lookup_data = await asyncio.to_thread(self.client.get, lookup_key)
            
            if lookup_data:
                lookup = json.loads(lookup_data)
                return lookup.get(tag, [])
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Error getting tag parents: {e}")
            return []
    
    async def get_tag_children(self, parent_tag: str, instance: str = None) -> List[str]:
        """
        Get child tags for a given parent tag.
        
        Args:
            parent_tag: Parent tag to find children for
            instance: Instance to check (if None, checks global)
            
        Returns:
            List of child tags
        """
        try:
            if instance:
                hierarchy_key = f"{instance}:tag_hierarchy"
            else:
                hierarchy_key = "global:tag_hierarchies"
            
            hierarchy_data = await asyncio.to_thread(self.client.get, hierarchy_key)
            
            if hierarchy_data:
                hierarchy = json.loads(hierarchy_data)
                
                # Search through hierarchy
                def find_children(node):
                    if isinstance(node, dict):
                        if parent_tag in node:
                            return node[parent_tag]
                        for value in node.values():
                            result = find_children(value)
                            if result:
                                return result
                    return None
                
                return find_children(hierarchy) or []
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Error getting tag children: {e}")
            return []
    
    async def expand_tag_search(self, tags: List[str], instance: str, include_parents: bool = True, include_children: bool = True) -> List[str]:
        """
        Expand tag list to include hierarchical relationships.
        
        Args:
            tags: Original tags to expand
            instance: Instance to check hierarchy in
            include_parents: Whether to include parent tags
            include_children: Whether to include child tags
            
        Returns:
            Expanded list of tags
        """
        try:
            expanded_tags = set(tags)
            
            for tag in tags:
                if include_parents:
                    parents = await self.get_tag_parents(tag, instance)
                    for parent_path in parents:
                        # Extract individual parent tags from path
                        parent_parts = parent_path.split('.')
                        expanded_tags.update(parent_parts)
                
                if include_children:
                    children = await self.get_tag_children(tag, instance)
                    expanded_tags.update(children)
            
            return list(expanded_tags)
            
        except Exception as e:
            logger.error(f"❌ Error expanding tag search: {e}")
            return tags
    
    async def suggest_tag_improvements(self, instance: str) -> Dict[str, Any]:
        """Suggest tag improvements based on hierarchy analysis."""
        try:
            suggestions = {
                'merge_candidates': [],
                'hierarchy_gaps': [],
                'orphaned_tags': [],
                'overused_tags': [],
                'underused_categories': []
            }
            
            # Get tag stats and hierarchy
            tag_stats = await self._get_tag_usage_stats(instance)
            
            hierarchy_key = f"{instance}:tag_hierarchy"
            hierarchy_data = await asyncio.to_thread(self.client.get, hierarchy_key)
            
            if hierarchy_data:
                hierarchy = json.loads(hierarchy_data)
                
                # Find orphaned tags (not in hierarchy)
                all_hierarchy_tags = set()
                
                def collect_tags(node):
                    if isinstance(node, list):
                        all_hierarchy_tags.update(node)
                    elif isinstance(node, dict):
                        for value in node.values():
                            collect_tags(value)
                
                collect_tags(hierarchy)
                
                for tag in tag_stats.keys():
                    if tag not in all_hierarchy_tags:
                        suggestions['orphaned_tags'].append({
                            'tag': tag,
                            'usage_count': tag_stats[tag]['usage_count']
                        })
                
                # Find merge candidates (similar tags)
                tags_list = list(tag_stats.keys())
                for i, tag1 in enumerate(tags_list):
                    for tag2 in tags_list[i+1:]:
                        similarity = self._calculate_tag_similarity(tag1, tag2)
                        if similarity > self.config['auto_merge_threshold']:
                            suggestions['merge_candidates'].append({
                                'tag1': tag1,
                                'tag2': tag2,
                                'similarity': similarity,
                                'combined_usage': tag_stats[tag1]['usage_count'] + tag_stats[tag2]['usage_count']
                            })
                
                # Find overused tags (might need subcategories)
                avg_usage = sum(stats['usage_count'] for stats in tag_stats.values()) / len(tag_stats) if tag_stats else 0
                for tag, stats in tag_stats.items():
                    if stats['usage_count'] > avg_usage * 3:  # 3x above average
                        suggestions['overused_tags'].append({
                            'tag': tag,
                            'usage_count': stats['usage_count'],
                            'ratio_to_average': stats['usage_count'] / max(1, avg_usage)
                        })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"❌ Error suggesting improvements: {e}")
            return {}
    
    def _calculate_tag_similarity(self, tag1: str, tag2: str) -> float:
        """Calculate similarity between two tags."""
        try:
            # Simple string similarity based on common characters
            set1 = set(tag1.lower())
            set2 = set(tag2.lower())
            
            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))
            
            if union == 0:
                return 0.0
            
            jaccard = intersection / union
            
            # Also consider edit distance
            def levenshtein_distance(s1, s2):
                if len(s1) < len(s2):
                    return levenshtein_distance(s2, s1)
                
                if len(s2) == 0:
                    return len(s1)
                
                previous_row = list(range(len(s2) + 1))
                for i, c1 in enumerate(s1):
                    current_row = [i + 1]
                    for j, c2 in enumerate(s2):
                        insertions = previous_row[j + 1] + 1
                        deletions = current_row[j] + 1
                        substitutions = previous_row[j] + (c1 != c2)
                        current_row.append(min(insertions, deletions, substitutions))
                    previous_row = current_row
                
                return previous_row[-1]
            
            edit_distance = levenshtein_distance(tag1.lower(), tag2.lower())
            max_len = max(len(tag1), len(tag2))
            edit_similarity = 1 - (edit_distance / max_len) if max_len > 0 else 0
            
            # Combine similarities
            return (jaccard + edit_similarity) / 2
            
        except Exception as e:
            logger.warning(f"⚠️ Error calculating similarity: {e}")
            return 0.0

# Utility functions

async def rebuild_all_hierarchies(redis_url: str = None) -> Dict[str, Any]:
    """Rebuild hierarchies for all instances."""
    manager = TagHierarchyManager(redis_url)
    
    try:
        await manager.initialize()
        result = await manager.build_dynamic_hierarchy()
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to rebuild hierarchies: {e}")
        return {'status': 'failed', 'error': str(e)}
    
    finally:
        if manager.client:
            manager.client.close()

async def main():
    """Main function for testing tag hierarchy manager."""
    manager = TagHierarchyManager()
    
    try:
        await manager.initialize()
        
        print("🧪 Testing tag hierarchy manager...")
        
        # Build dynamic hierarchy
        result = await manager.build_dynamic_hierarchy('CCD')
        print(f"🏗️ Hierarchy build result: {json.dumps(result, indent=2)}")
        
        # Test tag expansion
        test_tags = ['python', 'redis']
        expanded = await manager.expand_tag_search(test_tags, 'CCD')
        print(f"🔍 Tag expansion for {test_tags}: {expanded}")
        
        # Get improvement suggestions
        suggestions = await manager.suggest_tag_improvements('CCD')
        print(f"💡 Improvement suggestions: {json.dumps(suggestions, indent=2)}")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        
    finally:
        if manager.client:
            manager.client.close()

if __name__ == "__main__":
    asyncio.run(main())