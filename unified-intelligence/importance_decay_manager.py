#!/usr/bin/env python3.11
"""
Importance Decay Manager - Phase 3 Implementation
Manage time-based importance decay for thought relevance scoring
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
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImportanceDecayManager:
    """
    Manage importance decay for thoughts based on time and usage patterns.
    
    Phase 3 Features:
    - Exponential decay based on time since creation
    - Usage-based decay modulation (active thoughts decay slower)
    - Context-based importance preservation
    - Batch decay processing for performance
    - Decay curve customization per thought category
    """
    
    def __init__(self, redis_url: str = None):
        """Initialize the importance decay manager."""
        self.redis_url = redis_url or self._get_redis_url()
        self.client = None
        self.instances = ['CC', 'CCD', 'CCI']
        
        # Decay configuration parameters
        self.decay_config = {
            'base_half_life_days': 30,        # Base half-life for importance decay
            'usage_protection_factor': 0.5,   # How much usage slows decay (0-1)
            'min_importance_threshold': 0.1,  # Minimum importance to maintain
            'decay_batch_size': 100,          # Thoughts to process per batch
            'recent_activity_window_days': 7, # Window for "recent" activity
            'category_multipliers': {         # Decay rate multipliers by category
                'critical': 0.3,              # Critical thoughts decay 3x slower
                'strategic': 0.5,             # Strategic thoughts decay 2x slower
                'technical': 0.7,             # Technical thoughts decay ~1.4x slower
                'operational': 1.0,           # Operational thoughts decay normally
                'relationship': 0.8,          # Relationship thoughts decay ~1.25x slower
            },
            'usage_decay_curve': {            # Usage frequency impact on decay
                'never_accessed': 2.0,        # Never accessed thoughts decay 2x faster
                'rarely_accessed': 1.5,       # < 1 access per week
                'occasionally_accessed': 1.0, # 1-3 accesses per week
                'frequently_accessed': 0.6,   # 4-10 accesses per week
                'highly_accessed': 0.3,       # > 10 accesses per week
            }
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
            logger.info("✅ Importance decay manager initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            raise
    
    async def calculate_decay_factor(self, thought_metadata: Dict[str, Any]) -> float:
        """
        Calculate decay factor for a thought based on age, usage, and category.
        
        Args:
            thought_metadata: Thought metadata including creation time, category, etc.
            
        Returns:
            Decay factor (0.0 to 1.0, where 1.0 = no decay)
        """
        try:
            # Get creation time
            created_at = thought_metadata.get('created_at')
            if not created_at:
                return 1.0  # No decay if no creation time
            
            try:
                created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return 1.0  # No decay if invalid timestamp
            
            # Calculate age in days
            now = datetime.now(created_time.tzinfo) if created_time.tzinfo else datetime.now()
            age_days = (now - created_time).total_seconds() / (24 * 3600)
            
            if age_days <= 0:
                return 1.0  # No decay for future timestamps
            
            # Get base decay parameters
            base_half_life = self.decay_config['base_half_life_days']
            
            # Apply category-based decay rate modification
            category = thought_metadata.get('category', 'operational')
            category_multiplier = self.decay_config['category_multipliers'].get(category, 1.0)
            adjusted_half_life = base_half_life / category_multiplier
            
            # Calculate base exponential decay
            base_decay = math.exp(-math.log(2) * age_days / adjusted_half_life)
            
            # Apply usage-based decay protection
            usage_factor = await self._calculate_usage_protection_factor(thought_metadata)
            
            # Combine factors
            final_decay_factor = base_decay * (1 - self.decay_config['usage_protection_factor'] * (1 - usage_factor))
            
            # Ensure minimum threshold
            final_decay_factor = max(
                self.decay_config['min_importance_threshold'],
                final_decay_factor
            )
            
            return min(1.0, final_decay_factor)
            
        except Exception as e:
            logger.error(f"❌ Error calculating decay factor: {e}")
            return 1.0  # Default to no decay on error
    
    async def _calculate_usage_protection_factor(self, thought_metadata: Dict[str, Any]) -> float:
        """Calculate how much usage protects against decay (0.0 = no protection, 1.0 = full protection)."""
        try:
            # This would typically look at access patterns from feedback events
            # For now, we'll use simplified logic based on available metadata
            
            # Check for recent access indicators
            last_accessed = thought_metadata.get('last_accessed')
            if last_accessed:
                try:
                    last_access_time = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))
                    days_since_access = (datetime.now() - last_access_time).total_seconds() / (24 * 3600)
                    
                    if days_since_access <= self.decay_config['recent_activity_window_days']:
                        return 0.8  # High protection for recently accessed thoughts
                    elif days_since_access <= 30:
                        return 0.5  # Medium protection for moderately recent access
                    else:
                        return 0.2  # Low protection for old access
                except (ValueError, AttributeError):
                    pass
            
            # Fallback to importance-based protection
            importance = float(thought_metadata.get('importance', 5))
            if importance >= 8:
                return 0.7  # High importance provides good protection
            elif importance >= 6:
                return 0.4  # Medium importance provides some protection
            else:
                return 0.1  # Low importance provides minimal protection
                
        except Exception as e:
            logger.warning(f"⚠️ Error calculating usage protection: {e}")
            return 0.3  # Default moderate protection
    
    async def process_decay_for_instance(self, instance: str, max_thoughts: int = None) -> Dict[str, Any]:
        """
        Process importance decay for all thoughts in an instance.
        
        Args:
            instance: Instance to process
            max_thoughts: Maximum number of thoughts to process (for testing)
            
        Returns:
            Processing results and statistics
        """
        try:
            logger.info(f"🔄 Processing importance decay for {instance}...")
            
            # Get all thoughts with metadata
            meta_pattern = f"{instance}:thought_meta:*"
            meta_keys = await asyncio.to_thread(self.client.keys, meta_pattern)
            
            if max_thoughts:
                meta_keys = meta_keys[:max_thoughts]
            
            processed_count = 0
            updated_count = 0
            errors = []
            
            # Process in batches for performance
            batch_size = self.decay_config['decay_batch_size']
            
            for i in range(0, len(meta_keys), batch_size):
                batch_keys = meta_keys[i:i + batch_size]
                batch_results = await self._process_decay_batch(instance, batch_keys)
                
                processed_count += batch_results['processed']
                updated_count += batch_results['updated']
                errors.extend(batch_results['errors'])
                
                # Brief pause between batches
                if i + batch_size < len(meta_keys):
                    await asyncio.sleep(0.1)
            
            result = {
                'instance': instance,
                'total_thoughts': len(meta_keys),
                'processed_count': processed_count,
                'updated_count': updated_count,
                'error_count': len(errors),
                'errors': errors[:10],  # Limit error list
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Processed decay for {instance}: {updated_count}/{processed_count} thoughts updated")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error processing decay for {instance}: {e}")
            return {'instance': instance, 'error': str(e)}
    
    async def _process_decay_batch(self, instance: str, meta_keys: List[str]) -> Dict[str, Any]:
        """Process a batch of thoughts for decay."""
        processed = 0
        updated = 0
        errors = []
        
        for meta_key in meta_keys:
            try:
                thought_id = meta_key.split(':')[-1]
                
                # Get thought metadata
                metadata = await asyncio.to_thread(self.client.hgetall, meta_key)
                
                if not metadata:
                    continue
                
                processed += 1
                
                # Get current importance
                current_importance = float(metadata.get('importance', 5.0))
                original_importance = float(metadata.get('original_importance', current_importance))
                
                # Calculate decay factor
                decay_factor = await self.calculate_decay_factor(metadata)
                
                # Apply decay to original importance
                new_importance = original_importance * decay_factor
                
                # Only update if there's a significant change
                if abs(new_importance - current_importance) > 0.1:
                    # Update metadata
                    updated_metadata = {
                        **metadata,
                        'importance': str(round(new_importance, 2)),
                        'original_importance': str(original_importance),
                        'decay_factor': str(round(decay_factor, 3)),
                        'last_decay_update': datetime.now().isoformat()
                    }
                    
                    await asyncio.to_thread(
                        self.client.hset,
                        meta_key,
                        mapping=updated_metadata
                    )
                    
                    # Update relevance ranking if it exists
                    ranking_key = f"{instance}:relevance_ranking"
                    if await asyncio.to_thread(self.client.exists, ranking_key):
                        await asyncio.to_thread(
                            self.client.zadd,
                            ranking_key,
                            {thought_id: new_importance}
                        )
                    
                    updated += 1
                    logger.debug(f"✅ Updated importance for {thought_id}: {current_importance} -> {new_importance}")
                
            except Exception as e:
                errors.append(f"{meta_key}: {str(e)}")
                logger.warning(f"⚠️ Error processing decay for {meta_key}: {e}")
        
        return {
            'processed': processed,
            'updated': updated,
            'errors': errors
        }
    
    async def analyze_decay_patterns(self, instance: str = None) -> Dict[str, Any]:
        """
        Analyze decay patterns across thoughts.
        
        Args:
            instance: Optional instance to analyze (if None, analyzes all)
            
        Returns:
            Decay pattern analysis results
        """
        try:
            instances_to_analyze = [instance] if instance else self.instances
            analysis_results = {}
            
            for inst in instances_to_analyze:
                logger.info(f"📊 Analyzing decay patterns for {inst}...")
                
                # Get all thought metadata
                meta_pattern = f"{inst}:thought_meta:*"
                meta_keys = await asyncio.to_thread(self.client.keys, meta_pattern)
                
                decay_stats = {
                    'total_thoughts': len(meta_keys),
                    'by_category': defaultdict(list),
                    'by_age_group': defaultdict(list),
                    'by_decay_level': defaultdict(int),
                    'recent_updates': 0
                }
                
                recent_threshold = datetime.now() - timedelta(days=1)
                
                for meta_key in meta_keys:
                    try:
                        metadata = await asyncio.to_thread(self.client.hgetall, meta_key)
                        
                        if not metadata:
                            continue
                        
                        current_importance = float(metadata.get('importance', 5.0))
                        original_importance = float(metadata.get('original_importance', current_importance))
                        decay_factor = float(metadata.get('decay_factor', 1.0))
                        category = metadata.get('category', 'operational')
                        
                        # Calculate age group
                        created_at = metadata.get('created_at')
                        if created_at:
                            try:
                                created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                age_days = (datetime.now() - created_time).total_seconds() / (24 * 3600)
                                
                                if age_days < 7:
                                    age_group = 'week_old'
                                elif age_days < 30:
                                    age_group = 'month_old'
                                elif age_days < 90:
                                    age_group = 'quarter_old'
                                else:
                                    age_group = 'older'
                            except:
                                age_group = 'unknown'
                        else:
                            age_group = 'unknown'
                        
                        # Categorize by decay level
                        if decay_factor > 0.9:
                            decay_level = 'minimal'
                        elif decay_factor > 0.7:
                            decay_level = 'moderate'
                        elif decay_factor > 0.5:
                            decay_level = 'significant'
                        else:
                            decay_level = 'heavy'
                        
                        # Record statistics
                        decay_stats['by_category'][category].append({
                            'current_importance': current_importance,
                            'original_importance': original_importance,
                            'decay_factor': decay_factor
                        })
                        
                        decay_stats['by_age_group'][age_group].append({
                            'importance': current_importance,
                            'decay_factor': decay_factor
                        })
                        
                        decay_stats['by_decay_level'][decay_level] += 1
                        
                        # Check for recent updates
                        last_update = metadata.get('last_decay_update')
                        if last_update:
                            try:
                                update_time = datetime.fromisoformat(last_update)
                                if update_time > recent_threshold:
                                    decay_stats['recent_updates'] += 1
                            except:
                                pass
                    
                    except Exception as e:
                        logger.warning(f"⚠️ Error analyzing {meta_key}: {e}")
                
                # Calculate summary statistics
                summary_stats = await self._calculate_decay_summary_stats(decay_stats)
                decay_stats.update(summary_stats)
                
                analysis_results[inst] = decay_stats
            
            return {
                'status': 'completed',
                'timestamp': datetime.now().isoformat(),
                'instances': analysis_results
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing decay patterns: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _calculate_decay_summary_stats(self, decay_stats: Dict) -> Dict[str, Any]:
        """Calculate summary statistics from decay data."""
        try:
            summary = {
                'avg_decay_by_category': {},
                'avg_importance_by_age': {},
                'decay_distribution': {}
            }
            
            # Average decay by category
            for category, thoughts in decay_stats['by_category'].items():
                if thoughts:
                    avg_decay = sum(t['decay_factor'] for t in thoughts) / len(thoughts)
                    avg_importance = sum(t['current_importance'] for t in thoughts) / len(thoughts)
                    summary['avg_decay_by_category'][category] = {
                        'avg_decay_factor': round(avg_decay, 3),
                        'avg_current_importance': round(avg_importance, 2),
                        'thought_count': len(thoughts)
                    }
            
            # Average importance by age group
            for age_group, thoughts in decay_stats['by_age_group'].items():
                if thoughts:
                    avg_importance = sum(t['importance'] for t in thoughts) / len(thoughts)
                    avg_decay = sum(t['decay_factor'] for t in thoughts) / len(thoughts)
                    summary['avg_importance_by_age'][age_group] = {
                        'avg_importance': round(avg_importance, 2),
                        'avg_decay_factor': round(avg_decay, 3),
                        'thought_count': len(thoughts)
                    }
            
            # Decay level distribution
            total_thoughts = sum(decay_stats['by_decay_level'].values())
            if total_thoughts > 0:
                for level, count in decay_stats['by_decay_level'].items():
                    summary['decay_distribution'][level] = {
                        'count': count,
                        'percentage': round((count / total_thoughts) * 100, 1)
                    }
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error calculating summary stats: {e}")
            return {}
    
    async def reset_thought_importance(self, thought_id: str, instance: str, new_importance: float = None) -> bool:
        """
        Reset a thought's importance, optionally to a new value.
        
        Args:
            thought_id: ID of the thought to reset
            instance: Instance containing the thought
            new_importance: New importance value (if None, resets to original)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            meta_key = f"{instance}:thought_meta:{thought_id}"
            metadata = await asyncio.to_thread(self.client.hgetall, meta_key)
            
            if not metadata:
                logger.warning(f"⚠️ No metadata found for {thought_id}")
                return False
            
            if new_importance is not None:
                # Set new importance
                reset_importance = new_importance
                original_importance = new_importance
            else:
                # Reset to original importance
                original_importance = float(metadata.get('original_importance', 5.0))
                reset_importance = original_importance
            
            # Update metadata
            updated_metadata = {
                **metadata,
                'importance': str(reset_importance),
                'original_importance': str(original_importance),
                'decay_factor': '1.0',
                'last_decay_update': datetime.now().isoformat(),
                'importance_reset_at': datetime.now().isoformat()
            }
            
            await asyncio.to_thread(
                self.client.hset,
                meta_key,
                mapping=updated_metadata
            )
            
            # Update relevance ranking
            ranking_key = f"{instance}:relevance_ranking"
            if await asyncio.to_thread(self.client.exists, ranking_key):
                await asyncio.to_thread(
                    self.client.zadd,
                    ranking_key,
                    {thought_id: reset_importance}
                )
            
            logger.info(f"✅ Reset importance for {thought_id} to {reset_importance}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error resetting importance for {thought_id}: {e}")
            return False

# Utility functions

async def process_decay_all_instances(redis_url: str = None) -> Dict[str, Any]:
    """Process decay for all federation instances."""
    manager = ImportanceDecayManager(redis_url)
    
    try:
        await manager.initialize()
        
        results = {}
        for instance in manager.instances:
            result = await manager.process_decay_for_instance(instance)
            results[instance] = result
        
        return {
            'status': 'completed',
            'timestamp': datetime.now().isoformat(),
            'results': results
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to process decay: {e}")
        return {'status': 'failed', 'error': str(e)}
    
    finally:
        if manager.client:
            manager.client.close()

async def main():
    """Main function for testing importance decay manager."""
    manager = ImportanceDecayManager()
    
    try:
        await manager.initialize()
        
        print("🧪 Testing importance decay manager...")
        
        # Process decay for CCD instance
        result = await manager.process_decay_for_instance('CCD', max_thoughts=10)
        print(f"⚙️ Decay processing result: {json.dumps(result, indent=2)}")
        
        # Analyze decay patterns
        analysis = await manager.analyze_decay_patterns('CCD')
        print(f"📊 Decay pattern analysis: {json.dumps(analysis, indent=2)}")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        
    finally:
        if manager.client:
            manager.client.close()

if __name__ == "__main__":
    asyncio.run(main())