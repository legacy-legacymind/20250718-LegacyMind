#!/usr/bin/env python3.11
"""
Feedback Loop Monitor - Phase 1 Implementation
Basic monitoring for feedback system health and performance
"""

import asyncio
import json
import os
import time
from typing import Dict, List, Any
import redis
from datetime import datetime, timedelta
import argparse

class FeedbackMonitor:
    """
    Monitor feedback system health and performance.
    
    Phase 1 Implementation:
    - Stream health monitoring
    - Consumer group status
    - Basic metrics collection
    - Simple dashboard output
    """
    
    def __init__(self, redis_url: str = None):
        """Initialize the feedback monitor."""
        self.redis_url = redis_url or self._get_redis_url()
        self.client = None
        self.instances = ['CC', 'CCD', 'CCI']
        self.consumer_group = "feedback_processor"
    
    def _get_redis_url(self) -> str:
        """Get Redis URL from environment."""
        password = os.getenv('REDIS_PASSWORD', 'legacymind_redis_pass')
        return f"redis://:{password}@localhost:6379/0"
    
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            await asyncio.to_thread(self.client.ping)
            print("✅ Redis connection established")
            
        except Exception as e:
            print(f"❌ Failed to initialize: {e}")
            raise
    
    async def get_stream_health(self) -> Dict[str, Any]:
        """Get health status of all feedback streams."""
        health = {}
        
        for instance in self.instances:
            stream_key = f"{instance}:feedback_events"
            
            try:
                # Check if stream exists
                exists = await asyncio.to_thread(self.client.exists, stream_key)
                
                if not exists:
                    health[instance] = {
                        'status': 'missing',
                        'message': 'Stream does not exist',
                        'stream_key': stream_key
                    }
                    continue
                
                # Get stream info
                length = await asyncio.to_thread(self.client.xlen, stream_key)
                
                # Get consumer groups
                try:
                    groups = await asyncio.to_thread(self.client.xinfo_groups, stream_key)
                except redis.RedisError:
                    groups = []
                
                # Get consumer group info
                group_info = None
                if groups:
                    for group in groups:
                        if group['name'] == self.consumer_group:
                            group_info = group
                            break
                
                health[instance] = {
                    'status': 'healthy',
                    'stream_key': stream_key,
                    'length': length,
                    'groups_count': len(groups),
                    'group_info': group_info,
                    'timestamp': datetime.now().isoformat()
                }
                
            except Exception as e:
                health[instance] = {
                    'status': 'error',
                    'stream_key': stream_key,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
        
        return health
    
    async def get_consumer_status(self) -> Dict[str, Any]:
        """Get status of feedback consumers."""
        consumer_status = {}
        
        for instance in self.instances:
            stream_key = f"{instance}:feedback_events"
            
            try:
                # Check if stream exists
                exists = await asyncio.to_thread(self.client.exists, stream_key)
                if not exists:
                    consumer_status[instance] = {
                        'status': 'no_stream',
                        'message': 'Stream does not exist'
                    }
                    continue
                
                # Get consumers in the group
                try:
                    consumers = await asyncio.to_thread(
                        self.client.xinfo_consumers, 
                        stream_key, 
                        self.consumer_group
                    )
                    
                    consumer_status[instance] = {
                        'status': 'active' if consumers else 'no_consumers',
                        'consumers': consumers,
                        'consumer_count': len(consumers)
                    }
                    
                except redis.RedisError as e:
                    consumer_status[instance] = {
                        'status': 'no_group',
                        'error': str(e)
                    }
                    
            except Exception as e:
                consumer_status[instance] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return consumer_status
    
    async def get_processing_metrics(self) -> Dict[str, Any]:
        """Get processing metrics for feedback events."""
        metrics = {}
        
        for instance in self.instances:
            stream_key = f"{instance}:feedback_events"
            
            try:
                # Check if stream exists
                exists = await asyncio.to_thread(self.client.exists, stream_key)
                if not exists:
                    metrics[instance] = {
                        'total_events': 0,
                        'pending_events': 0,
                        'processed_events': 0,
                        'message': 'Stream does not exist'
                    }
                    continue
                
                # Get total events
                total_events = await asyncio.to_thread(self.client.xlen, stream_key)
                
                # Get pending events
                pending_events = 0
                try:
                    pending_info = await asyncio.to_thread(
                        self.client.xpending, 
                        stream_key, 
                        self.consumer_group
                    )
                    
                    if pending_info and len(pending_info) > 0:
                        pending_events = pending_info[0]  # Total pending count
                        
                except redis.RedisError:
                    pending_events = 0
                
                # Calculate processed events
                processed_events = max(0, total_events - pending_events)
                
                # Get recent activity (last 5 minutes)
                five_min_ago = int((datetime.now() - timedelta(minutes=5)).timestamp() * 1000)
                recent_events = 0
                
                try:
                    recent = await asyncio.to_thread(
                        self.client.xrange, 
                        stream_key, 
                        f"{five_min_ago}-0", 
                        "+",
                        count=1000
                    )
                    recent_events = len(recent)
                    
                except redis.RedisError:
                    recent_events = 0
                
                metrics[instance] = {
                    'total_events': total_events,
                    'pending_events': pending_events,
                    'processed_events': processed_events,
                    'recent_events_5min': recent_events,
                    'processing_rate': f"{(processed_events / max(1, total_events)) * 100:.1f}%"
                }
                
            except Exception as e:
                metrics[instance] = {
                    'error': str(e)
                }
        
        return metrics
    
    async def get_feedback_overview(self) -> Dict[str, Any]:
        """Get comprehensive feedback system overview."""
        overview = {
            'timestamp': datetime.now().isoformat(),
            'system_status': 'unknown',
            'stream_health': await self.get_stream_health(),
            'consumer_status': await self.get_consumer_status(),
            'processing_metrics': await self.get_processing_metrics()
        }
        
        # Determine overall system status
        healthy_streams = 0
        total_streams = len(self.instances)
        
        for instance, health in overview['stream_health'].items():
            if health['status'] == 'healthy':
                healthy_streams += 1
        
        if healthy_streams == total_streams:
            overview['system_status'] = 'healthy'
        elif healthy_streams > 0:
            overview['system_status'] = 'degraded'
        else:
            overview['system_status'] = 'unhealthy'
        
        return overview
    
    def format_dashboard(self, overview: Dict[str, Any]) -> str:
        """Format overview data as a readable dashboard."""
        dashboard = []
        
        # Header
        dashboard.append("=" * 60)
        dashboard.append("       FEEDBACK SYSTEM MONITORING DASHBOARD")
        dashboard.append("=" * 60)
        dashboard.append(f"📊 System Status: {overview['system_status'].upper()}")
        dashboard.append(f"🕐 Timestamp: {overview['timestamp']}")
        dashboard.append("")
        
        # Stream Health
        dashboard.append("🌊 STREAM HEALTH")
        dashboard.append("-" * 20)
        for instance, health in overview['stream_health'].items():
            status_icon = "✅" if health['status'] == 'healthy' else "❌"
            dashboard.append(f"{status_icon} {instance}: {health['status']}")
            
            if health['status'] == 'healthy':
                dashboard.append(f"   Length: {health['length']} events")
                dashboard.append(f"   Groups: {health['groups_count']}")
            elif health['status'] == 'missing':
                dashboard.append(f"   Stream: {health['stream_key']} (not created)")
            else:
                dashboard.append(f"   Error: {health.get('error', 'Unknown')}")
        
        dashboard.append("")
        
        # Consumer Status
        dashboard.append("👥 CONSUMER STATUS")
        dashboard.append("-" * 20)
        for instance, status in overview['consumer_status'].items():
            if status['status'] == 'active':
                dashboard.append(f"✅ {instance}: {status['consumer_count']} active consumers")
                for consumer in status['consumers']:
                    idle_time = consumer['idle'] / 1000 if consumer['idle'] > 0 else 0
                    dashboard.append(f"   - {consumer['name']}: {consumer['pending']} pending, {idle_time:.1f}s idle")
            else:
                dashboard.append(f"❌ {instance}: {status['status']}")
        
        dashboard.append("")
        
        # Processing Metrics
        dashboard.append("📈 PROCESSING METRICS")
        dashboard.append("-" * 20)
        for instance, metrics in overview['processing_metrics'].items():
            if 'error' not in metrics:
                dashboard.append(f"📊 {instance}:")
                dashboard.append(f"   Total Events: {metrics['total_events']}")
                dashboard.append(f"   Processed: {metrics['processed_events']} ({metrics['processing_rate']})")
                dashboard.append(f"   Pending: {metrics['pending_events']}")
                dashboard.append(f"   Recent (5min): {metrics['recent_events_5min']}")
            else:
                dashboard.append(f"❌ {instance}: {metrics['error']}")
        
        dashboard.append("")
        dashboard.append("=" * 60)
        
        return "\n".join(dashboard)
    
    async def print_dashboard(self):
        """Print the monitoring dashboard."""
        overview = await self.get_feedback_overview()
        dashboard = self.format_dashboard(overview)
        print(dashboard)
    
    async def watch_dashboard(self, interval: int = 30):
        """Continuously monitor and display dashboard."""
        print("🔄 Starting feedback system monitoring...")
        print("   Press Ctrl+C to stop")
        print()
        
        try:
            while True:
                # Clear screen (works on most terminals)
                os.system('clear' if os.name == 'posix' else 'cls')
                
                await self.print_dashboard()
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped")

async def main():
    """Main function for monitoring."""
    parser = argparse.ArgumentParser(description='Feedback System Monitor')
    parser.add_argument('--watch', '-w', action='store_true', 
                       help='Watch mode - continuously update dashboard')
    parser.add_argument('--interval', '-i', type=int, default=30,
                       help='Update interval in seconds (default: 30)')
    parser.add_argument('--json', '-j', action='store_true',
                       help='Output as JSON')
    
    args = parser.parse_args()
    
    monitor = FeedbackMonitor()
    
    try:
        await monitor.initialize()
        
        if args.watch:
            await monitor.watch_dashboard(args.interval)
        else:
            if args.json:
                overview = await monitor.get_feedback_overview()
                print(json.dumps(overview, indent=2))
            else:
                await monitor.print_dashboard()
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(asyncio.run(main()))