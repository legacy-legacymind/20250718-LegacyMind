#!/usr/bin/env python3.11
"""
Run Feedback Processor - Phase 1
Simple script to run the feedback processor as a service
"""

import asyncio
import argparse
import signal
import sys
from feedback_processor import FeedbackProcessor
from feedback_monitor import FeedbackMonitor

class FeedbackService:
    """Service wrapper for the feedback processor."""
    
    def __init__(self):
        self.processor = None
        self.monitor = None
        self.running = False
    
    async def start(self, monitor_interval: int = 60):
        """Start the feedback service."""
        print("🚀 Starting Feedback Processing Service...")
        
        try:
            # Initialize processor
            self.processor = FeedbackProcessor()
            await self.processor.initialize()
            
            # Initialize monitor
            self.monitor = FeedbackMonitor()
            await self.monitor.initialize()
            
            # Setup signal handlers
            self._setup_signal_handlers()
            
            self.running = True
            
            # Start monitoring task
            monitor_task = asyncio.create_task(
                self._periodic_monitoring(monitor_interval)
            )
            
            # Start processing task
            process_task = asyncio.create_task(
                self.processor.start_processing()
            )
            
            print("✅ Feedback service started successfully")
            print("   Press Ctrl+C to stop")
            
            # Wait for tasks to complete
            await asyncio.gather(monitor_task, process_task)
            
        except KeyboardInterrupt:
            print("\n🛑 Received interrupt signal")
            await self.stop()
            
        except Exception as e:
            print(f"❌ Service error: {e}")
            await self.stop()
            raise
    
    async def _periodic_monitoring(self, interval: int):
        """Periodically print monitoring information."""
        while self.running:
            try:
                # Print processor stats
                if self.processor:
                    stats = await self.processor.get_stats()
                    print(f"📊 Processed: {stats['events_processed']}, "
                          f"Failed: {stats['events_failed']}, "
                          f"Uptime: {stats['uptime_seconds']:.0f}s")
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                print(f"⚠️ Monitoring error: {e}")
                await asyncio.sleep(interval)
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            print(f"\n🛑 Received signal {signum}")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def stop(self):
        """Stop the feedback service."""
        print("🛑 Stopping feedback service...")
        
        self.running = False
        
        if self.processor:
            await self.processor.stop()
        
        print("✅ Feedback service stopped")

async def run_test():
    """Run the feedback setup test."""
    print("🧪 Running feedback system test...")
    
    # Import and run the test
    from test_feedback_setup import main as test_main
    return await test_main()

async def run_monitor(watch: bool = False, interval: int = 30):
    """Run the feedback monitor."""
    monitor = FeedbackMonitor()
    
    try:
        await monitor.initialize()
        
        if watch:
            await monitor.watch_dashboard(interval)
        else:
            await monitor.print_dashboard()
            
    except Exception as e:
        print(f"❌ Monitor error: {e}")
        return 1
    
    return 0

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Feedback Processing Service')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start the feedback processor')
    start_parser.add_argument('--monitor-interval', '-i', type=int, default=60,
                             help='Monitoring interval in seconds (default: 60)')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test the feedback system setup')
    
    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor feedback system')
    monitor_parser.add_argument('--watch', '-w', action='store_true',
                               help='Watch mode - continuously update')
    monitor_parser.add_argument('--interval', '-i', type=int, default=30,
                               help='Update interval in seconds (default: 30)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'start':
        service = FeedbackService()
        await service.start(args.monitor_interval)
        return 0
        
    elif args.command == 'test':
        return await run_test()
        
    elif args.command == 'monitor':
        return await run_monitor(args.watch, args.interval)
    
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main()))