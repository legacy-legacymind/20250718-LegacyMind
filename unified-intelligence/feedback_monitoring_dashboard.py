#!/usr/bin/env python3.11
"""
Feedback Monitoring Dashboard - Phase 4 Implementation
Comprehensive monitoring and visualization for the feedback loop system
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import redis
from collections import defaultdict, Counter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FeedbackMonitoringDashboard:
    """
    Comprehensive monitoring dashboard for the feedback loop system.
    
    Phase 4 Features:
    - Real-time system health monitoring
    - Performance metrics and trends
    - Search quality analytics
    - Tag usage and hierarchy effectiveness
    - Relevance score distribution analysis
    - Federation-wide insights
    - Automated alerting and recommendations
    """
    
    def __init__(self, redis_url: str = None):
        """Initialize the monitoring dashboard."""
        self.redis_url = redis_url or self._get_redis_url()
        self.client = None
        self.instances = ['CC', 'CCD', 'CCI']
        
        # Monitoring configuration
        self.config = {
            'health_check_interval_seconds': 30,
            'metrics_retention_hours': 168,    # 7 days
            'alert_thresholds': {
                'error_rate': 0.05,             # 5% error rate threshold
                'processing_lag_seconds': 300,   # 5 minute lag threshold
                'search_quality_drop': 0.2,     # 20% quality drop threshold
                'memory_usage_percent': 85,     # 85% memory usage threshold
            },
            'trending_window_hours': 24,        # Window for trend analysis
            'dashboard_refresh_seconds': 5,     # Dashboard refresh interval
        }
    
    def _get_redis_url(self) -> str:
        """Get Redis URL from environment."""
        password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        return f"redis://:{password}@localhost:6379/0"
    
    async def initialize(self):
        """Initialize Redis connection and monitoring setup."""
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            await asyncio.to_thread(self.client.ping)
            
            # Initialize monitoring keys
            await self._initialize_monitoring_keys()
            
            logger.info("✅ Feedback monitoring dashboard initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            raise
    
    async def _initialize_monitoring_keys(self):
        """Initialize monitoring data structures in Redis."""
        try:
            # Create monitoring timestamp
            monitoring_key = "feedback_monitoring:status"
            await asyncio.to_thread(
                self.client.hset,
                monitoring_key,
                mapping={
                    'initialized_at': datetime.now().isoformat(),
                    'dashboard_version': '1.0.0',
                    'monitoring_instances': json.dumps(self.instances)
                }
            )
            
            logger.debug("✅ Initialized monitoring keys")
            
        except Exception as e:
            logger.error(f"❌ Error initializing monitoring keys: {e}")
    
    async def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health overview.
        
        Returns:
            System health metrics and status
        """
        try:
            health_data = {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'healthy',
                'instances': {},
                'federation_health': {},
                'alerts': []
            }
            
            total_errors = 0
            total_processed = 0
            
            for instance in self.instances:
                instance_health = await self._get_instance_health(instance)
                health_data['instances'][instance] = instance_health
                
                # Aggregate federation metrics
                total_errors += instance_health.get('error_count', 0)
                total_processed += instance_health.get('events_processed', 0)
                
                # Check for alerts
                alerts = await self._check_instance_alerts(instance, instance_health)
                health_data['alerts'].extend(alerts)
            
            # Calculate federation-wide metrics
            error_rate = total_errors / max(1, total_processed)
            
            health_data['federation_health'] = {
                'total_events_processed': total_processed,
                'total_errors': total_errors,
                'error_rate': round(error_rate, 4),
                'active_instances': len([
                    inst for inst, health in health_data['instances'].items()
                    if health.get('status') == 'active'
                ])
            }
            
            # Determine overall status
            if error_rate > self.config['alert_thresholds']['error_rate']:
                health_data['overall_status'] = 'degraded'
            
            if len(health_data['alerts']) > 0:
                health_data['overall_status'] = 'warning'
            
            return health_data
            
        except Exception as e:
            logger.error(f"❌ Error getting system health: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    async def _get_instance_health(self, instance: str) -> Dict[str, Any]:
        """Get health metrics for a specific instance."""
        try:
            health = {
                'instance': instance,
                'status': 'unknown',
                'events_processed': 0,
                'error_count': 0,
                'last_activity': None,
                'processing_rate': 0.0,
                'memory_usage': 0,
                'queue_depth': 0
            }
            
            # Check feedback stream health
            stream_key = f"{instance}:feedback_events"
            try:
                stream_info = await asyncio.to_thread(self.client.xinfo_stream, stream_key)
                health['queue_depth'] = stream_info.get('length', 0)
                health['last_activity'] = stream_info.get('last-generated-id', 'unknown')
                health['status'] = 'active'
            except:
                health['status'] = 'inactive'
            
            # Get processing statistics from relevance calculator
            relevance_key = f"{instance}:relevance_ranking"
            try:
                relevance_count = await asyncio.to_thread(self.client.zcard, relevance_key)
                health['thoughts_with_relevance'] = relevance_count
            except:
                health['thoughts_with_relevance'] = 0
            
            # Get tag statistics
            tag_key = f"{instance}:tag_popularity"
            try:
                tag_count = await asyncio.to_thread(self.client.zcard, tag_key)
                health['total_tags'] = tag_count
            except:
                health['total_tags'] = 0
            
            # Get search quality metrics
            quality_key = f"{instance}:search_quality"
            try:
                recent_searches = await asyncio.to_thread(self.client.lrange, quality_key, 0, 9)
                if recent_searches:
                    search_data = [json.loads(search) for search in recent_searches]
                    avg_results = sum(s.get('results_count', 0) for s in search_data) / len(search_data)
                    health['avg_search_results'] = round(avg_results, 2)
                else:
                    health['avg_search_results'] = 0
            except:
                health['avg_search_results'] = 0
            
            return health
            
        except Exception as e:
            logger.error(f"❌ Error getting health for {instance}: {e}")
            return {'instance': instance, 'status': 'error', 'error': str(e)}
    
    async def _check_instance_alerts(self, instance: str, health_data: Dict) -> List[Dict[str, Any]]:
        """Check for alerts based on instance health data."""
        alerts = []
        
        try:
            # Check error rate
            error_rate = health_data.get('error_count', 0) / max(1, health_data.get('events_processed', 1))
            if error_rate > self.config['alert_thresholds']['error_rate']:
                alerts.append({
                    'type': 'error_rate',
                    'severity': 'warning',
                    'instance': instance,
                    'message': f"High error rate: {error_rate:.1%}",
                    'value': error_rate,
                    'threshold': self.config['alert_thresholds']['error_rate']
                })
            
            # Check queue depth
            queue_depth = health_data.get('queue_depth', 0)
            if queue_depth > 1000:  # Arbitrary threshold
                alerts.append({
                    'type': 'queue_depth',
                    'severity': 'info',
                    'instance': instance,
                    'message': f"High queue depth: {queue_depth} events",
                    'value': queue_depth
                })
            
            # Check search quality
            avg_results = health_data.get('avg_search_results', 0)
            if avg_results < 1:  # Very low search results
                alerts.append({
                    'type': 'search_quality',
                    'severity': 'warning',
                    'instance': instance,
                    'message': f"Low search results: {avg_results} avg",
                    'value': avg_results
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"❌ Error checking alerts for {instance}: {e}")
            return []
    
    async def get_performance_metrics(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Get performance metrics and trends.
        
        Args:
            hours_back: Hours of data to analyze
            
        Returns:
            Performance metrics and trend analysis
        """
        try:
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'analysis_window_hours': hours_back,
                'instances': {},
                'federation_trends': {},
                'recommendations': []
            }
            
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            for instance in self.instances:
                instance_metrics = await self._get_instance_performance(instance, cutoff_time)
                metrics['instances'][instance] = instance_metrics
            
            # Calculate federation trends
            federation_trends = await self._calculate_federation_trends(metrics['instances'])
            metrics['federation_trends'] = federation_trends
            
            # Generate recommendations
            recommendations = await self._generate_performance_recommendations(metrics)
            metrics['recommendations'] = recommendations
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error getting performance metrics: {e}")
            return {'error': str(e)}
    
    async def _get_instance_performance(self, instance: str, cutoff_time: datetime) -> Dict[str, Any]:
        """Get performance metrics for a specific instance."""
        try:
            perf_data = {
                'search_performance': {},
                'relevance_updates': 0,
                'tag_operations': 0,
                'feedback_processed': 0,
                'trends': {}
            }
            
            # Analyze search performance
            search_quality_key = f"{instance}:search_quality"
            recent_searches = await asyncio.to_thread(self.client.lrange, search_quality_key, 0, -1)
            
            search_metrics = []
            for search_json in recent_searches:
                try:
                    search_data = json.loads(search_json)
                    search_time = datetime.fromisoformat(search_data['timestamp'])
                    
                    if search_time >= cutoff_time:
                        search_metrics.append(search_data)
                except:
                    continue
            
            if search_metrics:
                perf_data['search_performance'] = {
                    'total_searches': len(search_metrics),
                    'avg_results_per_search': sum(s.get('results_count', 0) for s in search_metrics) / len(search_metrics),
                    'avg_query_length': sum(s.get('query_length', 0) for s in search_metrics) / len(search_metrics),
                    'searches_per_hour': len(search_metrics) / max(1, (datetime.now() - cutoff_time).total_seconds() / 3600)
                }
            
            # Get relevance score distribution
            relevance_key = f"{instance}:relevance_ranking"
            relevance_scores = await asyncio.to_thread(
                self.client.zrange, relevance_key, 0, -1, withscores=True
            )
            
            if relevance_scores:
                scores = [score for _, score in relevance_scores]
                perf_data['relevance_distribution'] = {
                    'total_thoughts': len(scores),
                    'avg_relevance': sum(scores) / len(scores),
                    'min_relevance': min(scores),
                    'max_relevance': max(scores),
                    'score_std_dev': self._calculate_std_dev(scores)
                }
            
            # Tag usage trends
            tag_popularity_key = f"{instance}:tag_popularity"
            top_tags = await asyncio.to_thread(
                self.client.zrevrange, tag_popularity_key, 0, 9, withscores=True
            )
            
            if top_tags:
                perf_data['tag_trends'] = {
                    'total_unique_tags': await asyncio.to_thread(self.client.zcard, tag_popularity_key),
                    'top_tags': [{'tag': tag, 'usage': int(count)} for tag, count in top_tags],
                    'tag_diversity': len(top_tags) / max(1, sum(count for _, count in top_tags))
                }
            
            return perf_data
            
        except Exception as e:
            logger.error(f"❌ Error getting performance for {instance}: {e}")
            return {'error': str(e)}
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if not values:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
    
    async def _calculate_federation_trends(self, instance_data: Dict) -> Dict[str, Any]:
        """Calculate trends across federation instances."""
        try:
            trends = {
                'search_activity': {},
                'relevance_health': {},
                'tag_usage': {},
                'cross_instance_patterns': {}
            }
            
            # Aggregate search activity
            total_searches = sum(
                inst_data.get('search_performance', {}).get('total_searches', 0)
                for inst_data in instance_data.values()
                if 'error' not in inst_data
            )
            
            avg_results_federation = []
            for inst_data in instance_data.values():
                if 'error' not in inst_data and 'search_performance' in inst_data:
                    avg_results = inst_data['search_performance'].get('avg_results_per_search', 0)
                    if avg_results > 0:
                        avg_results_federation.append(avg_results)
            
            trends['search_activity'] = {
                'federation_total_searches': total_searches,
                'avg_results_across_instances': sum(avg_results_federation) / max(1, len(avg_results_federation)),
                'active_search_instances': len(avg_results_federation)
            }
            
            # Aggregate relevance health
            total_thoughts = sum(
                inst_data.get('relevance_distribution', {}).get('total_thoughts', 0)
                for inst_data in instance_data.values()
                if 'error' not in inst_data
            )
            
            avg_relevance_scores = []
            for inst_data in instance_data.values():
                if 'error' not in inst_data and 'relevance_distribution' in inst_data:
                    avg_rel = inst_data['relevance_distribution'].get('avg_relevance', 0)
                    if avg_rel > 0:
                        avg_relevance_scores.append(avg_rel)
            
            trends['relevance_health'] = {
                'federation_total_thoughts': total_thoughts,
                'avg_relevance_federation': sum(avg_relevance_scores) / max(1, len(avg_relevance_scores)),
                'instances_with_relevance': len(avg_relevance_scores)
            }
            
            return trends
            
        except Exception as e:
            logger.error(f"❌ Error calculating federation trends: {e}")
            return {}
    
    async def _generate_performance_recommendations(self, metrics: Dict) -> List[Dict[str, Any]]:
        """Generate performance optimization recommendations."""
        recommendations = []
        
        try:
            federation_trends = metrics.get('federation_trends', {})
            
            # Check search quality
            avg_results = federation_trends.get('search_activity', {}).get('avg_results_across_instances', 0)
            if avg_results < 2:
                recommendations.append({
                    'type': 'search_quality',
                    'priority': 'high',
                    'title': 'Low search result quality',
                    'description': f'Average search results ({avg_results:.1f}) below optimal threshold',
                    'actions': [
                        'Review embedding quality and coverage',
                        'Analyze search query patterns',
                        'Consider relevance score thresholds'
                    ]
                })
            
            # Check relevance score distribution
            avg_relevance = federation_trends.get('relevance_health', {}).get('avg_relevance_federation', 0)
            if avg_relevance < 3:
                recommendations.append({
                    'type': 'relevance_scoring',
                    'priority': 'medium',
                    'title': 'Low relevance scores',
                    'description': f'Average relevance score ({avg_relevance:.1f}) indicates poor thought ranking',
                    'actions': [
                        'Review relevance calculation parameters',
                        'Increase usage tracking accuracy',
                        'Adjust importance decay settings'
                    ]
                })
            
            # Check instance activity
            active_instances = federation_trends.get('search_activity', {}).get('active_search_instances', 0)
            total_instances = len(self.instances)
            if active_instances < total_instances:
                recommendations.append({
                    'type': 'federation_health',
                    'priority': 'medium',
                    'title': 'Inactive federation instances',
                    'description': f'Only {active_instances}/{total_instances} instances showing search activity',
                    'actions': [
                        'Check inactive instance configurations',
                        'Verify embedding coverage',
                        'Review feedback stream setup'
                    ]
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"❌ Error generating recommendations: {e}")
            return []
    
    async def get_search_quality_analytics(self, instance: str = None) -> Dict[str, Any]:
        """
        Get detailed search quality analytics.
        
        Args:
            instance: Optional instance filter
            
        Returns:
            Search quality metrics and analysis
        """
        try:
            instances_to_analyze = [instance] if instance else self.instances
            analytics = {
                'timestamp': datetime.now().isoformat(),
                'instances': {},
                'quality_trends': {},
                'query_patterns': {}
            }
            
            for inst in instances_to_analyze:
                inst_analytics = await self._analyze_instance_search_quality(inst)
                analytics['instances'][inst] = inst_analytics
            
            # Analyze quality trends across instances
            quality_trends = await self._analyze_search_quality_trends(analytics['instances'])
            analytics['quality_trends'] = quality_trends
            
            # Analyze query patterns
            query_patterns = await self._analyze_query_patterns(analytics['instances'])
            analytics['query_patterns'] = query_patterns
            
            return analytics
            
        except Exception as e:
            logger.error(f"❌ Error getting search quality analytics: {e}")
            return {'error': str(e)}
    
    async def _analyze_instance_search_quality(self, instance: str) -> Dict[str, Any]:
        """Analyze search quality for a specific instance."""
        try:
            quality_data = {
                'recent_searches': [],
                'quality_score': 0.0,
                'result_distribution': {},
                'query_effectiveness': {}
            }
            
            # Get recent search data
            quality_key = f"{instance}:search_quality"
            recent_searches = await asyncio.to_thread(self.client.lrange, quality_key, 0, 99)
            
            search_results = []
            query_lengths = []
            result_counts = []
            
            for search_json in recent_searches:
                try:
                    search_data = json.loads(search_json)
                    search_results.append(search_data)
                    
                    query_lengths.append(search_data.get('query_length', 0))
                    result_counts.append(search_data.get('results_count', 0))
                except:
                    continue
            
            if search_results:
                quality_data['recent_searches'] = search_results[:10]  # Latest 10
                
                # Calculate quality score
                avg_results = sum(result_counts) / len(result_counts)
                result_consistency = 1 - (self._calculate_std_dev(result_counts) / max(1, avg_results))
                quality_score = min(1.0, (avg_results / 5) * result_consistency)  # Normalize to 0-1
                
                quality_data['quality_score'] = round(quality_score, 3)
                
                # Result distribution
                quality_data['result_distribution'] = {
                    'avg_results': round(avg_results, 2),
                    'min_results': min(result_counts),
                    'max_results': max(result_counts),
                    'zero_result_rate': sum(1 for count in result_counts if count == 0) / len(result_counts)
                }
                
                # Query effectiveness
                quality_data['query_effectiveness'] = {
                    'avg_query_length': round(sum(query_lengths) / len(query_lengths), 1),
                    'effective_queries': sum(1 for count in result_counts if count > 0),
                    'effectiveness_rate': sum(1 for count in result_counts if count > 0) / len(result_counts)
                }
            
            return quality_data
            
        except Exception as e:
            logger.error(f"❌ Error analyzing search quality for {instance}: {e}")
            return {'error': str(e)}
    
    async def _analyze_search_quality_trends(self, instance_data: Dict) -> Dict[str, Any]:
        """Analyze search quality trends across instances."""
        try:
            trends = {
                'federation_quality_score': 0.0,
                'quality_by_instance': {},
                'trend_direction': 'stable',
                'areas_for_improvement': []
            }
            
            quality_scores = []
            for instance, data in instance_data.items():
                if 'error' not in data:
                    score = data.get('quality_score', 0)
                    quality_scores.append(score)
                    trends['quality_by_instance'][instance] = score
            
            if quality_scores:
                federation_score = sum(quality_scores) / len(quality_scores)
                trends['federation_quality_score'] = round(federation_score, 3)
                
                # Determine trend direction (simplified)
                if federation_score > 0.7:
                    trends['trend_direction'] = 'improving'
                elif federation_score < 0.3:
                    trends['trend_direction'] = 'declining'
                
                # Identify improvement areas
                if federation_score < 0.5:
                    trends['areas_for_improvement'].append('Overall search effectiveness')
                
                zero_result_rates = [
                    data.get('result_distribution', {}).get('zero_result_rate', 0)
                    for data in instance_data.values()
                    if 'error' not in data
                ]
                
                if zero_result_rates and sum(zero_result_rates) / len(zero_result_rates) > 0.2:
                    trends['areas_for_improvement'].append('Query matching accuracy')
            
            return trends
            
        except Exception as e:
            logger.error(f"❌ Error analyzing quality trends: {e}")
            return {}
    
    async def _analyze_query_patterns(self, instance_data: Dict) -> Dict[str, Any]:
        """Analyze query patterns across instances."""
        try:
            patterns = {
                'common_query_lengths': {},
                'effectiveness_by_length': {},
                'query_complexity_trends': {}
            }
            
            all_query_lengths = []
            length_effectiveness = defaultdict(list)
            
            for instance, data in instance_data.items():
                if 'error' not in data and 'recent_searches' in data:
                    for search in data['recent_searches']:
                        query_length = search.get('query_length', 0)
                        result_count = search.get('results_count', 0)
                        
                        all_query_lengths.append(query_length)
                        length_effectiveness[query_length].append(result_count)
            
            if all_query_lengths:
                length_counter = Counter(all_query_lengths)
                patterns['common_query_lengths'] = dict(length_counter.most_common(10))
                
                # Effectiveness by length
                for length, results in length_effectiveness.items():
                    if len(results) >= 3:  # Minimum sample size
                        avg_effectiveness = sum(results) / len(results)
                        patterns['effectiveness_by_length'][length] = round(avg_effectiveness, 2)
            
            return patterns
            
        except Exception as e:
            logger.error(f"❌ Error analyzing query patterns: {e}")
            return {}
    
    async def generate_dashboard_report(self) -> str:
        """Generate a comprehensive dashboard report in text format."""
        try:
            report_lines = []
            report_lines.append("=" * 80)
            report_lines.append("🔍 FEEDBACK LOOP MONITORING DASHBOARD")
            report_lines.append("=" * 80)
            report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("")
            
            # System Health Section
            health = await self.get_system_health()
            report_lines.append("📊 SYSTEM HEALTH")
            report_lines.append("-" * 40)
            report_lines.append(f"Overall Status: {health.get('overall_status', 'unknown').upper()}")
            
            federation_health = health.get('federation_health', {})
            report_lines.append(f"Total Events Processed: {federation_health.get('total_events_processed', 0):,}")
            report_lines.append(f"Error Rate: {federation_health.get('error_rate', 0):.2%}")
            report_lines.append(f"Active Instances: {federation_health.get('active_instances', 0)}/{len(self.instances)}")
            report_lines.append("")
            
            # Instance Details
            report_lines.append("🏛️ INSTANCE STATUS")
            report_lines.append("-" * 40)
            for instance, instance_health in health.get('instances', {}).items():
                status = instance_health.get('status', 'unknown')
                status_emoji = "✅" if status == 'active' else "❌" if status == 'error' else "⚠️"
                
                report_lines.append(f"{status_emoji} {instance}:")
                report_lines.append(f"   Status: {status}")
                report_lines.append(f"   Queue Depth: {instance_health.get('queue_depth', 0)}")
                report_lines.append(f"   Thoughts with Relevance: {instance_health.get('thoughts_with_relevance', 0)}")
                report_lines.append(f"   Total Tags: {instance_health.get('total_tags', 0)}")
                report_lines.append(f"   Avg Search Results: {instance_health.get('avg_search_results', 0)}")
            
            report_lines.append("")
            
            # Alerts Section
            alerts = health.get('alerts', [])
            if alerts:
                report_lines.append("🚨 ACTIVE ALERTS")
                report_lines.append("-" * 40)
                for alert in alerts:
                    severity_emoji = "🔴" if alert['severity'] == 'error' else "🟡" if alert['severity'] == 'warning' else "🔵"
                    report_lines.append(f"{severity_emoji} {alert['instance']}: {alert['message']}")
                report_lines.append("")
            
            # Performance Metrics
            performance = await self.get_performance_metrics(24)
            federation_trends = performance.get('federation_trends', {})
            
            report_lines.append("📈 PERFORMANCE METRICS (24h)")
            report_lines.append("-" * 40)
            
            search_activity = federation_trends.get('search_activity', {})
            report_lines.append(f"Federation Total Searches: {search_activity.get('federation_total_searches', 0)}")
            report_lines.append(f"Avg Results Per Search: {search_activity.get('avg_results_across_instances', 0):.1f}")
            
            relevance_health = federation_trends.get('relevance_health', {})
            report_lines.append(f"Total Thoughts with Relevance: {relevance_health.get('federation_total_thoughts', 0)}")
            report_lines.append(f"Avg Relevance Score: {relevance_health.get('avg_relevance_federation', 0):.1f}")
            report_lines.append("")
            
            # Recommendations
            recommendations = performance.get('recommendations', [])
            if recommendations:
                report_lines.append("💡 RECOMMENDATIONS")
                report_lines.append("-" * 40)
                for rec in recommendations:
                    priority_emoji = "🔴" if rec['priority'] == 'high' else "🟡" if rec['priority'] == 'medium' else "🟢"
                    report_lines.append(f"{priority_emoji} {rec['title']}")
                    report_lines.append(f"   {rec['description']}")
                    for action in rec.get('actions', []):
                        report_lines.append(f"   • {action}")
                    report_lines.append("")
            
            report_lines.append("=" * 80)
            
            return "\n".join(report_lines)
            
        except Exception as e:
            logger.error(f"❌ Error generating dashboard report: {e}")
            return f"Error generating report: {e}"

# Utility functions for dashboard operations

async def run_health_check(redis_url: str = None) -> Dict[str, Any]:
    """Run a quick health check."""
    dashboard = FeedbackMonitoringDashboard(redis_url)
    
    try:
        await dashboard.initialize()
        health = await dashboard.get_system_health()
        return health
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return {'status': 'failed', 'error': str(e)}
    
    finally:
        if dashboard.client:
            dashboard.client.close()

async def generate_monitoring_report(redis_url: str = None) -> str:
    """Generate a comprehensive monitoring report."""
    dashboard = FeedbackMonitoringDashboard(redis_url)
    
    try:
        await dashboard.initialize()
        report = await dashboard.generate_dashboard_report()
        return report
        
    except Exception as e:
        logger.error(f"❌ Report generation failed: {e}")
        return f"Report generation failed: {e}"
    
    finally:
        if dashboard.client:
            dashboard.client.close()

async def main():
    """Main function for testing monitoring dashboard."""
    dashboard = FeedbackMonitoringDashboard()
    
    try:
        await dashboard.initialize()
        
        print("🧪 Testing feedback monitoring dashboard...")
        
        # Generate full dashboard report
        report = await dashboard.generate_dashboard_report()
        print(report)
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        
    finally:
        if dashboard.client:
            dashboard.client.close()

if __name__ == "__main__":
    asyncio.run(main())