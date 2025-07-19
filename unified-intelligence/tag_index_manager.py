#!/usr/bin/env python3.11
"""
Tag Index Manager - Phase 2 Implementation
Maintain efficient tag-based indexes and metadata organization
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
import redis
from collections import defaultdict, Counter
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer

# Download required NLTK data (run once)
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)
    nltk.download('stopwords', quiet=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TagIndexManager:
    """
    Manage tag-based indexes and metadata organization.
    
    Core Features:
    - Automatic tag extraction from thought content
    - Tag hierarchy management
    - Tag popularity tracking
    - Tag co-occurrence analysis
    - Tag suggestion system
    - Efficient tag-based search indexes
    """
    
    def __init__(self, redis_url: str = None):
        """Initialize the tag index manager."""
        self.redis_url = redis_url or self._get_redis_url()
        self.client = None
        self.instances = ['CC', 'CCD', 'CCI']
        
        # NLP components
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words('english'))
        
        # Tag extraction patterns
        self.technical_patterns = {
            'technology': [
                r'\b(redis|python|rust|javascript|typescript|react|vue|angular)\b',
                r'\b(docker|kubernetes|k8s|nginx|apache)\b',
                r'\b(postgres|mysql|mongodb|sqlite|database)\b',
                r'\b(aws|azure|gcp|cloud|serverless)\b',
                r'\b(api|rest|graphql|grpc|http|https)\b',
                r'\b(git|github|gitlab|bitbucket|version control)\b'
            ],
            'concepts': [
                r'\b(algorithm|data structure|pattern|architecture)\b',
                r'\b(performance|optimization|scalability|efficiency)\b',
                r'\b(security|authentication|authorization|encryption)\b',
                r'\b(testing|debugging|monitoring|logging)\b',
                r'\b(deployment|ci/cd|pipeline|automation)\b'
            ],
            'domains': [
                r'\b(frontend|backend|fullstack|devops|ml|ai)\b',
                r'\b(web development|mobile|desktop|embedded)\b',
                r'\b(machine learning|artificial intelligence|nlp)\b',
                r'\b(blockchain|cryptocurrency|web3)\b'
            ]
        }
        
        # Tag hierarchy definitions
        self.tag_hierarchies = {
            'database': ['redis', 'postgres', 'mysql', 'mongodb', 'sqlite'],
            'programming': ['python', 'rust', 'javascript', 'typescript', 'go'],
            'frontend': ['react', 'vue', 'angular', 'html', 'css'],
            'infrastructure': ['docker', 'kubernetes', 'aws', 'azure', 'gcp'],
            'ai': ['machine learning', 'nlp', 'neural networks', 'deep learning'],
            'architecture': ['microservices', 'api', 'patterns', 'design'],
            'process': ['testing', 'ci/cd', 'deployment', 'monitoring']
        }
        
        # Configuration
        self.config = {
            'min_tag_length': 2,
            'max_tag_length': 50,
            'max_tags_per_thought': 20,
            'tag_popularity_threshold': 3,  # Minimum occurrences to suggest
            'similarity_threshold': 0.7,    # For tag merging suggestions
            'auto_tag_confidence': 0.8      # Confidence threshold for auto-tagging
        }
    
    def _get_redis_url(self) -> str:
        """Get Redis URL from environment."""
        password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        return f"redis://:{password}@localhost:6379/0"
    
    async def initialize(self):
        """Initialize Redis connection and tag indexes."""
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            await asyncio.to_thread(self.client.ping)
            logger.info("✅ Tag index manager initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            raise
    
    async def rebuild_tag_indexes(self, instance: str = None) -> Dict[str, Any]:
        """
        Rebuild tag indexes for specified instance or all instances.
        
        Args:
            instance: Optional instance to rebuild (if None, rebuilds all)
            
        Returns:
            Dictionary with rebuild statistics and results
        """
        try:
            instances_to_process = [instance] if instance else self.instances
            results = {}
            
            for inst in instances_to_process:
                logger.info(f"🔄 Rebuilding tag indexes for {inst}...")
                
                inst_result = await self._rebuild_instance_tags(inst)
                results[inst] = inst_result
                
                logger.info(f"✅ Rebuilt {inst}: {inst_result['tags_processed']} tags, "
                           f"{inst_result['thoughts_processed']} thoughts")
            
            # Build cross-instance statistics
            overall_stats = await self._calculate_overall_tag_stats(results)
            
            return {
                'status': 'completed',
                'timestamp': datetime.now().isoformat(),
                'instances': results,
                'overall': overall_stats
            }
            
        except Exception as e:
            logger.error(f"❌ Error rebuilding tag indexes: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _rebuild_instance_tags(self, instance: str) -> Dict[str, Any]:
        """Rebuild tag indexes for a specific instance."""
        try:
            # Clear existing tag indexes
            await self._clear_instance_tag_indexes(instance)
            
            # Get all thoughts for this instance
            thought_pattern = f"{instance}:thoughts:*"
            thought_keys = await asyncio.to_thread(self.client.keys, thought_pattern)
            
            thoughts_processed = 0
            tags_processed = 0
            tag_stats = defaultdict(int)
            tag_cooccurrences = defaultdict(lambda: defaultdict(int))
            
            for thought_key in thought_keys:
                thought_id = thought_key.split(':')[-1]
                
                try:
                    # Get thought content
                    thought_content = await asyncio.to_thread(self.client.get, thought_key)
                    
                    if thought_content:
                        # Extract tags from content
                        extracted_tags = await self.extract_tags_from_content(thought_content)
                        
                        # Get existing manual tags
                        meta_key = f"{instance}:thought_meta:{thought_id}"
                        metadata = await asyncio.to_thread(self.client.hgetall, meta_key)
                        
                        existing_tags = []
                        if metadata and 'tags' in metadata:
                            try:
                                existing_tags = json.loads(metadata['tags'])
                            except (json.JSONDecodeError, TypeError):
                                pass
                        
                        # Combine extracted and existing tags
                        all_tags = list(set(extracted_tags + existing_tags))
                        all_tags = [tag for tag in all_tags if self._is_valid_tag(tag)]
                        
                        if all_tags:
                            # Update thought metadata with combined tags
                            await self._update_thought_tags(instance, thought_id, all_tags)
                            
                            # Update tag indexes
                            await self._update_tag_indexes(instance, thought_id, all_tags)
                            
                            # Update statistics
                            for tag in all_tags:
                                tag_stats[tag.lower()] += 1
                                tags_processed += 1
                            
                            # Update co-occurrence matrix
                            for i, tag1 in enumerate(all_tags):
                                for tag2 in all_tags[i+1:]:
                                    tag_cooccurrences[tag1.lower()][tag2.lower()] += 1
                                    tag_cooccurrences[tag2.lower()][tag1.lower()] += 1
                        
                        thoughts_processed += 1
                        
                except Exception as e:
                    logger.warning(f"⚠️ Error processing thought {thought_id}: {e}")
            
            # Store tag statistics
            await self._store_tag_statistics(instance, tag_stats, tag_cooccurrences)
            
            return {
                'thoughts_processed': thoughts_processed,
                'tags_processed': tags_processed,
                'unique_tags': len(tag_stats),
                'top_tags': dict(Counter(tag_stats).most_common(10))
            }
            
        except Exception as e:
            logger.error(f"❌ Error rebuilding {instance} tags: {e}")
            return {'error': str(e)}
    
    async def extract_tags_from_content(self, content: str) -> List[str]:
        """
        Extract tags automatically from thought content using NLP and patterns.
        
        Args:
            content: The thought content to analyze
            
        Returns:
            List of extracted tags
        """
        try:
            tags = set()
            content_lower = content.lower()
            
            # 1. Extract technical terms using regex patterns
            for category, patterns in self.technical_patterns.items():
                for pattern in patterns:
                    matches = re.findall(pattern, content_lower, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            tags.update([m for m in match if m])
                        else:
                            tags.add(match)
            
            # 2. Extract significant nouns and phrases
            try:
                # Tokenize and extract meaningful words
                tokens = word_tokenize(content_lower)
                
                # Filter tokens
                significant_words = [
                    word for word in tokens 
                    if (len(word) >= self.config['min_tag_length'] and 
                        word.isalpha() and 
                        word not in self.stop_words and
                        not word.isdigit())
                ]
                
                # Add words that appear multiple times
                word_counts = Counter(significant_words)
                for word, count in word_counts.items():
                    if count > 1 and len(word) > 3:
                        tags.add(word)
                
            except Exception as e:
                logger.warning(f"⚠️ NLP processing error: {e}")
            
            # 3. Extract phrases in quotes or emphasis
            quoted_phrases = re.findall(r'["\']([^"\']+)["\']', content)
            for phrase in quoted_phrases:
                if 2 <= len(phrase.split()) <= 3:  # Short phrases only
                    tags.add(phrase.lower().strip())
            
            # 4. Extract camelCase and snake_case identifiers
            camel_case = re.findall(r'\b[a-z]+(?:[A-Z][a-z]+)+\b', content)
            snake_case = re.findall(r'\b[a-z]+(?:_[a-z]+)+\b', content)
            
            for identifier in camel_case + snake_case:
                if len(identifier) > 3:
                    tags.add(identifier.lower())
            
            # 5. Clean and validate tags
            cleaned_tags = []
            for tag in tags:
                cleaned_tag = self._clean_tag(tag)
                if cleaned_tag and self._is_valid_tag(cleaned_tag):
                    cleaned_tags.append(cleaned_tag)
            
            # Limit number of tags
            return cleaned_tags[:self.config['max_tags_per_thought']]
            
        except Exception as e:
            logger.error(f"❌ Error extracting tags from content: {e}")
            return []
    
    def _clean_tag(self, tag: str) -> Optional[str]:
        """Clean and normalize a tag."""
        if not tag:
            return None
        
        # Remove extra whitespace and convert to lowercase
        tag = tag.strip().lower()
        
        # Remove special characters except hyphens and underscores
        tag = re.sub(r'[^\w\s\-_]', '', tag)
        
        # Replace multiple whitespace with single space
        tag = re.sub(r'\s+', ' ', tag)
        
        # Remove leading/trailing hyphens or underscores
        tag = tag.strip('-_')
        
        return tag if tag else None
    
    def _is_valid_tag(self, tag: str) -> bool:
        """Check if a tag is valid according to our criteria."""
        if not tag:
            return False
        
        # Length check
        if len(tag) < self.config['min_tag_length'] or len(tag) > self.config['max_tag_length']:
            return False
        
        # Must contain at least one letter
        if not re.search(r'[a-zA-Z]', tag):
            return False
        
        # Skip very common words that aren't useful as tags
        common_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        if tag in common_words:
            return False
        
        return True
    
    async def _clear_instance_tag_indexes(self, instance: str):
        """Clear existing tag indexes for an instance."""
        try:
            # Get all tag index keys
            tag_keys_pattern = f"{instance}:tags:*"
            tag_keys = await asyncio.to_thread(self.client.keys, tag_keys_pattern)
            
            if tag_keys:
                await asyncio.to_thread(self.client.delete, *tag_keys)
            
            # Clear tag statistics
            stats_keys = [
                f"{instance}:tag_stats",
                f"{instance}:tag_cooccurrence",
                f"{instance}:tag_hierarchy"
            ]
            
            existing_stats = await asyncio.to_thread(self.client.keys, f"{instance}:tag_*")
            if existing_stats:
                await asyncio.to_thread(self.client.delete, *existing_stats)
            
        except Exception as e:
            logger.warning(f"⚠️ Error clearing tag indexes for {instance}: {e}")
    
    async def _update_thought_tags(self, instance: str, thought_id: str, tags: List[str]):
        """Update thought metadata with tags."""
        try:
            meta_key = f"{instance}:thought_meta:{thought_id}"
            
            # Get existing metadata
            metadata = await asyncio.to_thread(self.client.hgetall, meta_key)
            
            # Update tags
            metadata['tags'] = json.dumps(tags)
            metadata['tag_count'] = str(len(tags))
            metadata['last_tag_update'] = datetime.now().isoformat()
            
            # Store updated metadata
            await asyncio.to_thread(self.client.hset, meta_key, mapping=metadata)
            
        except Exception as e:
            logger.error(f"❌ Error updating tags for {thought_id}: {e}")
    
    async def _update_tag_indexes(self, instance: str, thought_id: str, tags: List[str]):
        """Update tag-based indexes."""
        try:
            for tag in tags:
                tag_key = f"{instance}:tags:{tag.lower()}"
                
                # Add thought ID to tag set
                await asyncio.to_thread(self.client.sadd, tag_key, thought_id)
                
                # Update tag popularity (sorted set for ranking)
                popularity_key = f"{instance}:tag_popularity"
                await asyncio.to_thread(self.client.zincrby, popularity_key, 1, tag.lower())
            
        except Exception as e:
            logger.error(f"❌ Error updating tag indexes: {e}")
    
    async def _store_tag_statistics(self, instance: str, tag_stats: Dict, cooccurrences: Dict):
        """Store tag statistics and co-occurrence data."""
        try:
            # Store tag statistics
            stats_key = f"{instance}:tag_stats"
            if tag_stats:
                await asyncio.to_thread(
                    self.client.hset,
                    stats_key,
                    mapping={tag: count for tag, count in tag_stats.items()}
                )
            
            # Store co-occurrence matrix (sample for performance)
            cooccur_key = f"{instance}:tag_cooccurrence"
            
            # Only store high co-occurrence pairs to save space
            high_cooccur = {}
            for tag1, related_tags in cooccurrences.items():
                for tag2, count in related_tags.items():
                    if count >= 2:  # Minimum co-occurrence threshold
                        pair_key = f"{tag1}:{tag2}"
                        high_cooccur[pair_key] = str(count)
            
            if high_cooccur:
                await asyncio.to_thread(self.client.hset, cooccur_key, mapping=high_cooccur)
            
        except Exception as e:
            logger.error(f"❌ Error storing tag statistics: {e}")
    
    async def suggest_tags(self, content: str, instance: str = 'CCD', limit: int = 10) -> List[Dict[str, Any]]:
        """
        Suggest tags for given content based on existing patterns and popularity.
        
        Args:
            content: Content to analyze for tag suggestions
            instance: Instance to base suggestions on
            limit: Maximum number of suggestions
            
        Returns:
            List of tag suggestions with confidence scores
        """
        try:
            suggestions = []
            
            # 1. Extract potential tags from content
            potential_tags = await self.extract_tags_from_content(content)
            
            # 2. Get tag popularity data
            popularity_key = f"{instance}:tag_popularity"
            popular_tags = await asyncio.to_thread(
                self.client.zrevrange,
                popularity_key,
                0,
                100,
                withscores=True
            )
            
            popularity_dict = {tag: score for tag, score in popular_tags}
            
            # 3. Score each potential tag
            for tag in potential_tags:
                confidence = 0.5  # Base confidence
                
                # Boost if tag is popular
                if tag in popularity_dict:
                    popularity_score = popularity_dict[tag]
                    confidence += min(0.4, popularity_score / 10.0)  # Max 0.4 boost
                
                # Boost if tag matches technical patterns
                for category, patterns in self.technical_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, tag, re.IGNORECASE):
                            confidence += 0.2
                            break
                
                # Boost if tag is in hierarchy
                for parent, children in self.tag_hierarchies.items():
                    if tag in children:
                        confidence += 0.15
                        break
                
                suggestions.append({
                    'tag': tag,
                    'confidence': min(1.0, confidence),
                    'reason': self._get_suggestion_reason(tag, popularity_dict)
                })
            
            # 4. Add related tags based on co-occurrence
            related_tags = await self._get_related_tags(potential_tags, instance)
            for tag, score in related_tags:
                if tag not in [s['tag'] for s in suggestions]:
                    suggestions.append({
                        'tag': tag,
                        'confidence': min(0.8, score),
                        'reason': 'Related to content topics'
                    })
            
            # 5. Sort by confidence and return top suggestions
            suggestions.sort(key=lambda x: x['confidence'], reverse=True)
            return suggestions[:limit]
            
        except Exception as e:
            logger.error(f"❌ Error suggesting tags: {e}")
            return []
    
    def _get_suggestion_reason(self, tag: str, popularity_dict: Dict) -> str:
        """Get human-readable reason for tag suggestion."""
        reasons = []
        
        if tag in popularity_dict:
            count = int(popularity_dict[tag])
            reasons.append(f"Popular tag (used {count} times)")
        
        # Check technical patterns
        for category, patterns in self.technical_patterns.items():
            for pattern in patterns:
                if re.search(pattern, tag, re.IGNORECASE):
                    reasons.append(f"Technical term ({category})")
                    break
        
        # Check hierarchies
        for parent, children in self.tag_hierarchies.items():
            if tag in children:
                reasons.append(f"Part of {parent} category")
                break
        
        return '; '.join(reasons) if reasons else 'Extracted from content'
    
    async def _get_related_tags(self, tags: List[str], instance: str, limit: int = 5) -> List[Tuple[str, float]]:
        """Get tags that frequently co-occur with the given tags."""
        try:
            cooccur_key = f"{instance}:tag_cooccurrence"
            related_scores = defaultdict(float)
            
            for tag in tags:
                # Get co-occurrence data for this tag
                pattern = f"{tag.lower()}:*"
                cooccur_data = self.client.hscan_iter(cooccur_key, match=pattern)
                
                for pair_key, count in cooccur_data:
                    if ':' in pair_key:
                        _, related_tag = pair_key.split(':', 1)
                        if related_tag not in tags:  # Don't suggest tags already present
                            related_scores[related_tag] += float(count) / 10.0  # Normalize
            
            # Sort by score and return top related tags
            sorted_related = sorted(related_scores.items(), key=lambda x: x[1], reverse=True)
            return sorted_related[:limit]
            
        except Exception as e:
            logger.warning(f"⚠️ Error getting related tags: {e}")
            return []
    
    async def get_tag_hierarchy(self, instance: str = None) -> Dict[str, Any]:
        """Get tag hierarchy information for visualization."""
        try:
            instances_to_check = [instance] if instance else self.instances
            hierarchy_data = {}
            
            for inst in instances_to_check:
                # Get tag popularity
                popularity_key = f"{inst}:tag_popularity"
                popular_tags = await asyncio.to_thread(
                    self.client.zrevrange,
                    popularity_key,
                    0,
                    50,
                    withscores=True
                )
                
                # Organize into hierarchy
                inst_hierarchy = {}
                
                for parent, children in self.tag_hierarchies.items():
                    inst_hierarchy[parent] = {
                        'children': [],
                        'total_count': 0
                    }
                    
                    for tag, count in popular_tags:
                        if tag in children:
                            inst_hierarchy[parent]['children'].append({
                                'tag': tag,
                                'count': int(count)
                            })
                            inst_hierarchy[parent]['total_count'] += int(count)
                
                # Add uncategorized tags
                categorized_tags = set()
                for children in self.tag_hierarchies.values():
                    categorized_tags.update(children)
                
                uncategorized = []
                for tag, count in popular_tags:
                    if tag not in categorized_tags:
                        uncategorized.append({
                            'tag': tag,
                            'count': int(count)
                        })
                
                if uncategorized:
                    inst_hierarchy['uncategorized'] = {
                        'children': uncategorized[:20],  # Limit uncategorized
                        'total_count': sum(item['count'] for item in uncategorized)
                    }
                
                hierarchy_data[inst] = inst_hierarchy
            
            return hierarchy_data
            
        except Exception as e:
            logger.error(f"❌ Error getting tag hierarchy: {e}")
            return {}
    
    async def search_by_tags(self, tags: List[str], instance: str, operator: str = 'AND') -> List[str]:
        """
        Search for thoughts by tags using set operations.
        
        Args:
            tags: List of tags to search for
            instance: Instance to search in
            operator: 'AND' for intersection, 'OR' for union
            
        Returns:
            List of thought IDs matching the tag criteria
        """
        try:
            if not tags:
                return []
            
            # Get thought IDs for each tag
            tag_sets = []
            for tag in tags:
                tag_key = f"{instance}:tags:{tag.lower()}"
                thought_ids = await asyncio.to_thread(self.client.smembers, tag_key)
                tag_sets.append(set(thought_ids))
            
            # Apply set operations
            if operator.upper() == 'AND':
                # Intersection - thoughts that have ALL tags
                result_set = tag_sets[0]
                for tag_set in tag_sets[1:]:
                    result_set = result_set.intersection(tag_set)
            else:  # OR
                # Union - thoughts that have ANY of the tags
                result_set = set()
                for tag_set in tag_sets:
                    result_set = result_set.union(tag_set)
            
            return list(result_set)
            
        except Exception as e:
            logger.error(f"❌ Error searching by tags: {e}")
            return []
    
    async def get_tag_statistics(self, instance: str = None) -> Dict[str, Any]:
        """Get comprehensive tag statistics."""
        try:
            instances_to_check = [instance] if instance else self.instances
            stats = {}
            
            for inst in instances_to_check:
                # Get basic stats
                stats_key = f"{inst}:tag_stats"
                tag_stats = await asyncio.to_thread(self.client.hgetall, stats_key)
                
                # Get popularity ranking
                popularity_key = f"{inst}:tag_popularity"
                popular_tags = await asyncio.to_thread(
                    self.client.zrevrange,
                    popularity_key,
                    0,
                    10,
                    withscores=True
                )
                
                # Calculate coverage
                total_thoughts = len(await asyncio.to_thread(
                    self.client.keys, f"{inst}:thoughts:*"
                ))
                
                tagged_thoughts = len(await asyncio.to_thread(
                    self.client.keys, f"{inst}:thought_meta:*"
                ))
                
                coverage = (tagged_thoughts / max(1, total_thoughts)) * 100
                
                stats[inst] = {
                    'total_tags': len(tag_stats),
                    'total_thoughts': total_thoughts,
                    'tagged_thoughts': tagged_thoughts,
                    'coverage_percentage': round(coverage, 2),
                    'top_tags': [{'tag': tag, 'count': int(count)} for tag, count in popular_tags],
                    'timestamp': datetime.now().isoformat()
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting tag statistics: {e}")
            return {}

# Utility functions

async def batch_tag_rebuild(redis_url: str = None, instances: List[str] = None) -> Dict[str, Any]:
    """Batch rebuild tag indexes for multiple instances."""
    manager = TagIndexManager(redis_url)
    
    try:
        await manager.initialize()
        result = await manager.rebuild_tag_indexes()
        return result
        
    except Exception as e:
        logger.error(f"❌ Batch tag rebuild failed: {e}")
        return {'status': 'failed', 'error': str(e)}
    
    finally:
        if manager.client:
            manager.client.close()

async def main():
    """Main function for testing tag index manager."""
    manager = TagIndexManager()
    
    try:
        await manager.initialize()
        
        print("🧪 Testing tag index manager...")
        
        # Test tag extraction
        test_content = """
        I'm implementing a Redis-based semantic search system using Python and FastAPI.
        The architecture includes vector embeddings, relevance scoring, and tag-based filtering.
        We're using Docker for containerization and deploying on AWS.
        """
        
        extracted_tags = await manager.extract_tags_from_content(test_content)
        print(f"📋 Extracted tags: {extracted_tags}")
        
        # Test tag suggestions
        suggestions = await manager.suggest_tags(test_content, 'CCD')
        print(f"💡 Tag suggestions: {json.dumps(suggestions, indent=2)}")
        
        # Test index rebuild (limited)
        # result = await manager.rebuild_tag_indexes('CCD')
        # print(f"🔄 Rebuild result: {json.dumps(result, indent=2)}")
        
        # Test statistics
        stats = await manager.get_tag_statistics('CCD')
        print(f"📊 Tag statistics: {json.dumps(stats, indent=2)}")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        
    finally:
        if manager.client:
            manager.client.close()

if __name__ == "__main__":
    asyncio.run(main())