#!/usr/bin/env python3
"""
RAG-Anything API Real-time Performance Monitor
Continuously monitors API performance and resource usage
"""

import asyncio
import aiohttp
import psutil
import time
from datetime import datetime
import json

class APIPerformanceMonitor:
    def __init__(self, api_url="http://127.0.0.1:8000"):
        self.api_url = api_url
        self.session = None
        
    async def start_monitoring(self, interval_seconds=30):
        """Start continuous performance monitoring"""
        self.session = aiohttp.ClientSession()
        
        print("🔍 Starting RAG-Anything API Performance Monitoring")
        print(f"Target: {self.api_url}")
        print(f"Interval: {interval_seconds}s")
        print("-" * 60)
        
        try:
            while True:
                metrics = await self.collect_metrics()
                self.display_metrics(metrics)
                await asyncio.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
        finally:
            if self.session:
                await self.session.close()
    
    async def collect_metrics(self) -> dict:
        """Collect performance metrics"""
        timestamp = datetime.now()
        
        # System metrics
        system_metrics = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
        }
        
        # API health check
        api_metrics = await self.check_api_health()
        
        return {
            "timestamp": timestamp.isoformat(),
            "system": system_metrics,
            "api": api_metrics
        }
    
    async def check_api_health(self) -> dict:
        """Check API health and response time"""
        start_time = time.time()
        
        try:
            async with self.session.get(f"{self.api_url}/health", timeout=10) as response:
                response_time = (time.time() - start_time) * 1000
                
                if response.status == 200:
                    data = await response.json()
                    return {
                        "status": "healthy",
                        "response_time_ms": round(response_time, 2),
                        "details": data
                    }
                else:
                    return {
                        "status": "unhealthy", 
                        "response_time_ms": round(response_time, 2),
                        "error": f"HTTP {response.status}"
                    }
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                "status": "error",
                "response_time_ms": round(response_time, 2),
                "error": str(e)
            }
    
    def display_metrics(self, metrics: dict):
        """Display metrics in readable format"""
        timestamp = metrics["timestamp"]
        system = metrics["system"] 
        api = metrics["api"]
        
        print(f"\n⏰ {timestamp}")
        print(f"🖥️  System: CPU {system['cpu_percent']:.1f}% | Memory {system['memory_percent']:.1f}% | Disk {system['disk_percent']:.1f}%")
        print(f"🌐 API: {api['status']} | Response {api['response_time_ms']:.1f}ms")
        
        # Performance warnings
        if system['cpu_percent'] > 85:
            print("⚠️  HIGH CPU USAGE")
        if system['memory_percent'] > 85:
            print("⚠️  HIGH MEMORY USAGE") 
        if api['response_time_ms'] > 500:
            print("⚠️  SLOW API RESPONSE")
        if api['status'] != 'healthy':
            print(f"🚨 API ISSUE: {api.get('error', 'Unknown')}")

if __name__ == "__main__":
    monitor = APIPerformanceMonitor()
    asyncio.run(monitor.start_monitoring())
