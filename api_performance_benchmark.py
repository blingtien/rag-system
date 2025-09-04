#!/usr/bin/env python3
"""
RAG-Anything API Performance Benchmark Script
Comprehensive endpoint performance analysis with real measurements
"""

import asyncio
import aiohttp
import time
import json
import statistics
import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIPerformanceBenchmark:
    """Comprehensive API performance benchmarking suite"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.results: List[Dict[str, Any]] = []
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300))
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def measure_endpoint(
        self, 
        method: str, 
        path: str, 
        iterations: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """Measure single endpoint performance"""
        response_times = []
        memory_usage = []
        cpu_usage = []
        success_count = 0
        errors = []
        
        process = psutil.Process()
        
        logger.info(f"Benchmarking {method} {path} ({iterations} iterations)")
        
        for i in range(iterations):
            start_memory = process.memory_info().rss / 1024 / 1024  # MB
            start_cpu = psutil.cpu_percent(interval=None)
            start_time = time.time()
            
            try:
                async with self.session.request(method, f"{self.base_url}{path}", **kwargs) as response:
                    response_data = await response.text()
                    
                    end_time = time.time()
                    end_memory = process.memory_info().rss / 1024 / 1024  # MB
                    end_cpu = psutil.cpu_percent(interval=None)
                    
                    response_time = end_time - start_time
                    memory_delta = end_memory - start_memory
                    cpu_delta = end_cpu - start_cpu
                    
                    response_times.append(response_time)
                    memory_usage.append(memory_delta)
                    cpu_usage.append(cpu_delta)
                    
                    if response.status < 400:
                        success_count += 1
                    else:
                        errors.append(f"HTTP {response.status}: {response_data}")
                        
            except Exception as e:
                errors.append(str(e))
                logger.warning(f"Request {i+1} failed: {e}")
            
            # Small delay between requests
            if i < iterations - 1:
                await asyncio.sleep(0.1)
        
        # Calculate statistics
        if response_times:
            stats = {
                "endpoint": f"{method} {path}",
                "iterations": iterations,
                "success_rate": success_count / iterations * 100,
                "response_time_stats": {
                    "min": min(response_times),
                    "max": max(response_times), 
                    "mean": statistics.mean(response_times),
                    "median": statistics.median(response_times),
                    "p95": self._percentile(response_times, 95),
                    "p99": self._percentile(response_times, 99),
                },
                "resource_usage": {
                    "avg_memory_delta_mb": statistics.mean(memory_usage) if memory_usage else 0,
                    "max_memory_delta_mb": max(memory_usage) if memory_usage else 0,
                    "avg_cpu_delta": statistics.mean(cpu_usage) if cpu_usage else 0,
                },
                "errors": errors,
                "timestamp": datetime.now().isoformat()
            }
        else:
            stats = {
                "endpoint": f"{method} {path}",
                "iterations": iterations,
                "success_rate": 0,
                "response_time_stats": None,
                "resource_usage": None,
                "errors": errors,
                "timestamp": datetime.now().isoformat()
            }
        
        self.results.append(stats)
        return stats
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    async def test_api_availability(self) -> bool:
        """Test if API is running and responsive"""
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    logger.info("API is available and responsive")
                    return True
                else:
                    logger.error(f"API health check failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"API is not available: {e}")
            return False
    
    async def benchmark_core_endpoints(self) -> Dict[str, Any]:
        """Benchmark core API endpoints for performance analysis"""
        
        if not await self.test_api_availability():
            return {"error": "API not available", "results": []}
        
        logger.info("Starting comprehensive API performance benchmark")
        
        # Define endpoints to benchmark
        endpoints_to_test = [
            {"method": "GET", "path": "/health", "iterations": 50},
            {"method": "GET", "path": "/api/system/status", "iterations": 30}, 
            {"method": "GET", "path": "/api/system/parser-stats", "iterations": 20},
            {"method": "GET", "path": "/api/v1/tasks", "iterations": 30},
            {"method": "GET", "path": "/api/v1/documents", "iterations": 30},
            {"method": "GET", "path": "/api/v1/cache/status", "iterations": 20},
            {"method": "GET", "path": "/api/v1/batch-operations", "iterations": 20},
            {"method": "GET", "path": "/api/v1/system/health", "iterations": 15},
        ]
        
        # Run benchmarks
        benchmark_start = time.time()
        
        for endpoint_config in endpoints_to_test:
            try:
                await self.measure_endpoint(**endpoint_config)
                logger.info(f"Completed benchmark for {endpoint_config['method']} {endpoint_config['path']}")
            except Exception as e:
                logger.error(f"Benchmark failed for {endpoint_config['path']}: {e}")
        
        total_benchmark_time = time.time() - benchmark_start
        
        # Analyze results
        analysis = self.analyze_performance_results()
        
        return {
            "benchmark_metadata": {
                "total_time": total_benchmark_time,
                "endpoints_tested": len(endpoints_to_test),
                "timestamp": datetime.now().isoformat(),
                "api_base_url": self.base_url
            },
            "performance_analysis": analysis,
            "detailed_results": self.results
        }
    
    def analyze_performance_results(self) -> Dict[str, Any]:
        """Analyze benchmark results and categorize performance"""
        
        if not self.results:
            return {"error": "No benchmark results to analyze"}
        
        # Categorize endpoints by performance
        fast_endpoints = []     # < 100ms
        medium_endpoints = []   # 100ms - 1s
        slow_endpoints = []     # > 1s
        
        total_successful = 0
        total_tests = 0
        
        for result in self.results:
            if result.get("response_time_stats"):
                mean_time = result["response_time_stats"]["mean"] * 1000  # Convert to ms
                p95_time = result["response_time_stats"]["p95"] * 1000
                endpoint_name = result["endpoint"]
                
                total_tests += result["iterations"]
                total_successful += int(result["success_rate"] / 100 * result["iterations"])
                
                endpoint_perf = {
                    "endpoint": endpoint_name,
                    "mean_ms": round(mean_time, 2),
                    "p95_ms": round(p95_time, 2),
                    "success_rate": result["success_rate"]
                }
                
                if mean_time < 100:
                    fast_endpoints.append(endpoint_perf)
                elif mean_time < 1000:
                    medium_endpoints.append(endpoint_perf)
                else:
                    slow_endpoints.append(endpoint_perf)
        
        # Calculate overall statistics
        all_response_times = []
        for result in self.results:
            if result.get("response_time_stats"):
                # Approximate individual response times from statistics
                mean_time = result["response_time_stats"]["mean"]
                iterations = result["iterations"]
                all_response_times.extend([mean_time] * iterations)
        
        overall_stats = {}
        if all_response_times:
            overall_stats = {
                "overall_mean_ms": round(statistics.mean(all_response_times) * 1000, 2),
                "overall_p95_ms": round(self._percentile(all_response_times, 95) * 1000, 2),
                "overall_p99_ms": round(self._percentile(all_response_times, 99) * 1000, 2),
                "total_success_rate": round(total_successful / max(total_tests, 1) * 100, 1)
            }
        
        # Generate performance assessment
        performance_grade = "A"
        issues = []
        recommendations = []
        
        if len(slow_endpoints) > 0:
            performance_grade = "C"
            issues.append(f"{len(slow_endpoints)} endpoints slower than 1s")
            recommendations.append("Optimize slow endpoints with caching or async processing")
        
        if overall_stats.get("overall_p95_ms", 0) > 500:
            if performance_grade == "A":
                performance_grade = "B"
            issues.append(f"P95 response time: {overall_stats.get('overall_p95_ms')}ms")
            recommendations.append("Implement response time optimization")
        
        if overall_stats.get("total_success_rate", 100) < 95:
            performance_grade = "D"
            issues.append(f"Low success rate: {overall_stats.get('total_success_rate')}%")
            recommendations.append("Investigate and fix API reliability issues")
        
        return {
            "performance_grade": performance_grade,
            "overall_statistics": overall_stats,
            "endpoint_categories": {
                "fast_endpoints": fast_endpoints,
                "medium_endpoints": medium_endpoints, 
                "slow_endpoints": slow_endpoints
            },
            "performance_issues": issues,
            "optimization_recommendations": recommendations,
            "benchmark_summary": {
                "total_endpoints_tested": len(self.results),
                "endpoints_available": len([r for r in self.results if r["success_rate"] > 0]),
                "endpoints_failed": len([r for r in self.results if r["success_rate"] == 0])
            }
        }
    
    def save_results(self, output_file: str = None):
        """Save benchmark results to file"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"/home/ragsvr/projects/ragsystem/performance_results/api_benchmark_{timestamp}.json"
        
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "benchmark_results": self.results,
                    "analysis": self.analyze_performance_results(),
                    "metadata": {
                        "timestamp": datetime.now().isoformat(),
                        "tool": "API Performance Benchmark",
                        "version": "1.0"
                    }
                }, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Benchmark results saved to: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
            return None


async def main():
    """Run API performance benchmark"""
    print("🚀 RAG-Anything API Performance Benchmark")
    print("=" * 60)
    
    async with APIPerformanceBenchmark() as benchmark:
        # Run comprehensive benchmark
        results = await benchmark.benchmark_core_endpoints()
        
        # Save results
        output_file = benchmark.save_results()
        
        # Display summary
        print("\n📊 Benchmark Results Summary")
        print("=" * 40)
        
        if "performance_analysis" in results:
            analysis = results["performance_analysis"]
            
            print(f"Performance Grade: {analysis.get('performance_grade', 'N/A')}")
            print(f"Endpoints Tested: {analysis.get('benchmark_summary', {}).get('total_endpoints_tested', 0)}")
            print(f"Endpoints Available: {analysis.get('benchmark_summary', {}).get('endpoints_available', 0)}")
            
            if analysis.get('overall_statistics'):
                stats = analysis['overall_statistics']
                print(f"Overall Mean Response: {stats.get('overall_mean_ms', 0)}ms")
                print(f"P95 Response Time: {stats.get('overall_p95_ms', 0)}ms")
                print(f"Success Rate: {stats.get('total_success_rate', 0)}%")
            
            # Show endpoint categories
            categories = analysis.get('endpoint_categories', {})
            print(f"\n🟢 Fast Endpoints (< 100ms): {len(categories.get('fast_endpoints', []))}")
            print(f"🟡 Medium Endpoints (100ms-1s): {len(categories.get('medium_endpoints', []))}")  
            print(f"🔴 Slow Endpoints (> 1s): {len(categories.get('slow_endpoints', []))}")
            
            # Show issues and recommendations
            issues = analysis.get('performance_issues', [])
            if issues:
                print(f"\n⚠️  Performance Issues:")
                for issue in issues:
                    print(f"  - {issue}")
            
            recommendations = analysis.get('optimization_recommendations', [])
            if recommendations:
                print(f"\n💡 Recommendations:")
                for rec in recommendations:
                    print(f"  - {rec}")
        
        if output_file:
            print(f"\n📁 Detailed results saved to: {output_file}")
        
        print(f"\nBenchmark completed in {results.get('benchmark_metadata', {}).get('total_time', 0):.2f}s")


if __name__ == "__main__":
    asyncio.run(main())