#!/usr/bin/env python3
"""
Comprehensive Batch Processing Optimization Test Runner
批量处理优化综合测试运行器

This script orchestrates all batch processing optimization tests and provides
a comprehensive validation report for the implemented optimizations.

Test Suite Coverage:
1. Batch API endpoint functionality
2. Performance comparison (individual vs batch)
3. Intelligent caching effectiveness
4. Enhanced error handling and recovery
5. Real-time progress tracking with WebSocket
6. Frontend integration patterns
7. System health monitoring

Author: Claude Code
Date: 2025-08-23
"""

import asyncio
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import logging
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import individual test suites
try:
    from test_batch_processing_optimizations import BatchProcessingTestSuite, run_comprehensive_batch_tests
    from test_batch_performance_optimization import BatchProcessingBenchmark
    from test_intelligent_cache_system import CacheEffectivenessTest
    from test_enhanced_error_handling import ErrorScenarioTest
    from test_progress_tracking_websocket import ProgressTrackingTest
    from test_frontend_integration_patterns import FrontendIntegrationTest
    from test_system_health_monitoring import SystemHealthTest
except ImportError as e:
    logger.error(f"Failed to import test modules: {e}")
    print("❌ Failed to import test modules. Make sure all test files are present.")
    sys.exit(1)

API_BASE_URL = "http://localhost:8001"


class ComprehensiveTestRunner:
    """Comprehensive test runner for all batch processing optimization tests"""
    
    def __init__(self):
        self.test_results = {
            "test_run_info": {
                "start_time": datetime.now().isoformat(),
                "test_suite_version": "1.0.0",
                "purpose": "Validate batch processing optimizations"
            },
            "test_suite_results": {},
            "overall_summary": {},
            "recommendations": []
        }
    
    async def check_server_health(self) -> bool:
        """Check if API server is healthy before running tests"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{API_BASE_URL}/health")
                if response.status_code == 200:
                    logger.info("✅ API server is healthy and ready for testing")
                    return True
                else:
                    logger.error(f"❌ API server health check failed: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"❌ Cannot connect to API server: {e}")
            return False
    
    async def run_batch_processing_tests(self) -> Dict:
        """Run comprehensive batch processing tests"""
        logger.info("🧪 Running batch processing optimization tests...")
        
        try:
            # This runs the comprehensive test suite from the main test file
            results = await run_comprehensive_batch_tests()
            
            return {
                "test_name": "batch_processing_optimizations",
                "success": True,
                "results": results
            }
        except Exception as e:
            logger.error(f"Batch processing tests failed: {e}")
            return {
                "test_name": "batch_processing_optimizations",
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    async def run_performance_benchmark_tests(self) -> Dict:
        """Run performance benchmark tests"""
        logger.info("🏃 Running performance benchmark tests...")
        
        try:
            async with BatchProcessingBenchmark() as benchmark:
                results = await benchmark.run_comprehensive_performance_tests()
                
            return {
                "test_name": "performance_benchmarks",
                "success": True,
                "results": results
            }
        except Exception as e:
            logger.error(f"Performance benchmark tests failed: {e}")
            return {
                "test_name": "performance_benchmarks",
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    async def run_cache_effectiveness_tests(self) -> Dict:
        """Run intelligent cache system tests"""
        logger.info("💾 Running cache effectiveness tests...")
        
        try:
            async with CacheEffectivenessTest() as cache_test:
                results = await cache_test.run_comprehensive_cache_tests()
                
            return {
                "test_name": "cache_effectiveness",
                "success": True,
                "results": results
            }
        except Exception as e:
            logger.error(f"Cache effectiveness tests failed: {e}")
            return {
                "test_name": "cache_effectiveness",
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    async def run_error_handling_tests(self) -> Dict:
        """Run enhanced error handling tests"""
        logger.info("🛡️ Running error handling tests...")
        
        try:
            async with ErrorScenarioTest() as error_test:
                results = await error_test.run_comprehensive_error_tests()
                
            return {
                "test_name": "error_handling",
                "success": True,
                "results": results
            }
        except Exception as e:
            logger.error(f"Error handling tests failed: {e}")
            return {
                "test_name": "error_handling",
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    async def run_progress_tracking_tests(self) -> Dict:
        """Run progress tracking and WebSocket tests"""
        logger.info("📈 Running progress tracking tests...")
        
        try:
            async with ProgressTrackingTest() as progress_test:
                results = await progress_test.run_comprehensive_progress_tests()
                
            return {
                "test_name": "progress_tracking",
                "success": True,
                "results": results
            }
        except Exception as e:
            logger.error(f"Progress tracking tests failed: {e}")
            return {
                "test_name": "progress_tracking",
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    async def run_frontend_integration_tests(self) -> Dict:
        """Run frontend integration pattern tests"""
        logger.info("🌐 Running frontend integration tests...")
        
        try:
            async with FrontendIntegrationTest() as frontend_test:
                results = await frontend_test.run_comprehensive_frontend_integration_tests()
                
            return {
                "test_name": "frontend_integration",
                "success": True,
                "results": results
            }
        except Exception as e:
            logger.error(f"Frontend integration tests failed: {e}")
            return {
                "test_name": "frontend_integration",
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    async def run_system_health_tests(self) -> Dict:
        """Run system health monitoring tests"""
        logger.info("🏥 Running system health monitoring tests...")
        
        try:
            async with SystemHealthTest() as health_test:
                results = await health_test.run_comprehensive_health_monitoring_tests()
                
            return {
                "test_name": "system_health_monitoring",
                "success": True,
                "results": results
            }
        except Exception as e:
            logger.error(f"System health monitoring tests failed: {e}")
            return {
                "test_name": "system_health_monitoring",
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    def analyze_test_results(self) -> None:
        """Analyze all test results and generate overall assessment"""
        logger.info("📊 Analyzing comprehensive test results...")
        
        results = self.test_results["test_suite_results"]
        
        # Count successful vs failed test suites
        successful_suites = sum(1 for suite in results.values() if suite.get("success", False))
        total_suites = len(results)
        
        # Extract key metrics from each test suite
        optimization_metrics = {
            "performance_improvements": [],
            "cache_effectiveness": [],
            "error_handling_quality": [],
            "progress_tracking_accuracy": [],
            "frontend_compatibility": [],
            "system_health_reliability": []
        }
        
        # Performance metrics
        if "performance_benchmarks" in results and results["performance_benchmarks"]["success"]:
            perf_data = results["performance_benchmarks"]["results"]
            if "performance_analysis" in perf_data:
                analysis = perf_data["performance_analysis"]
                if "overall_performance" in analysis:
                    perf_metrics = analysis["overall_performance"]
                    optimization_metrics["performance_improvements"].append({
                        "avg_docs_per_second": perf_metrics.get("avg_docs_per_second", 0),
                        "peak_docs_per_second": perf_metrics.get("peak_docs_per_second", 0)
                    })
        
        # Cache effectiveness metrics
        if "cache_effectiveness" in results and results["cache_effectiveness"]["success"]:
            cache_data = results["cache_effectiveness"]["results"]
            if "overall_assessment" in cache_data:
                cache_assessment = cache_data["overall_assessment"]
                optimization_metrics["cache_effectiveness"].append({
                    "system_health": cache_assessment.get("cache_system_health", "unknown"),
                    "performance_impact": cache_assessment.get("performance_impact", "unknown")
                })
        
        # Error handling quality
        if "error_handling" in results and results["error_handling"]["success"]:
            error_data = results["error_handling"]["results"]
            if "overall_assessment" in error_data:
                error_assessment = error_data["overall_assessment"]
                optimization_metrics["error_handling_quality"].append({
                    "quality": error_assessment.get("error_handling_quality", "unknown"),
                    "resilience": error_assessment.get("system_resilience", "unknown"),
                    "pass_rate": error_assessment.get("overall_pass_rate", 0)
                })
        
        # Progress tracking accuracy
        if "progress_tracking" in results and results["progress_tracking"]["success"]:
            progress_data = results["progress_tracking"]["results"]
            if "overall_assessment" in progress_data:
                progress_assessment = progress_data["overall_assessment"]
                optimization_metrics["progress_tracking_accuracy"].append({
                    "websocket_reliability": progress_assessment.get("websocket_reliability", "unknown"),
                    "progress_accuracy": progress_assessment.get("progress_accuracy", "unknown"),
                    "effectiveness": progress_assessment.get("overall_effectiveness", "unknown")
                })
        
        # Frontend compatibility
        if "frontend_integration" in results and results["frontend_integration"]["success"]:
            frontend_data = results["frontend_integration"]["results"]
            if "overall_assessment" in frontend_data:
                frontend_assessment = frontend_data["overall_assessment"]
                optimization_metrics["frontend_compatibility"].append({
                    "integration_quality": frontend_assessment.get("overall_integration_quality", "unknown"),
                    "workflow_compatibility": frontend_assessment.get("workflow_compatibility", "unknown"),
                    "api_quality": frontend_assessment.get("api_response_quality", "unknown")
                })
        
        # System health reliability
        if "system_health_monitoring" in results and results["system_health_monitoring"]["success"]:
            health_data = results["system_health_monitoring"]["results"]
            if "overall_assessment" in health_data:
                health_assessment = health_data["overall_assessment"]
                optimization_metrics["system_health_reliability"].append({
                    "overall_quality": health_assessment.get("overall_health_system_quality", "unknown"),
                    "endpoint_quality": health_assessment.get("endpoint_quality", "unknown"),
                    "load_resilience": health_assessment.get("load_resilience", "unknown")
                })
        
        # Generate overall summary
        self.test_results["overall_summary"] = {
            "test_suite_success_rate": successful_suites / max(total_suites, 1),
            "successful_test_suites": successful_suites,
            "total_test_suites": total_suites,
            "optimization_metrics": optimization_metrics,
            "overall_optimization_assessment": self.assess_overall_optimization_quality(optimization_metrics)
        }
        
        # Generate recommendations
        self.generate_recommendations()
    
    def assess_overall_optimization_quality(self, metrics: Dict) -> Dict:
        """Assess overall quality of batch processing optimizations"""
        assessment = {
            "performance_optimization": "unknown",
            "reliability_optimization": "unknown", 
            "user_experience_optimization": "unknown",
            "system_monitoring_optimization": "unknown",
            "overall_optimization_success": "unknown"
        }
        
        # Assess performance optimization
        if metrics["performance_improvements"]:
            # If we have performance data, assess it
            perf_data = metrics["performance_improvements"][0]
            docs_per_sec = perf_data.get("avg_docs_per_second", 0)
            if docs_per_sec > 2:
                assessment["performance_optimization"] = "excellent"
            elif docs_per_sec > 1:
                assessment["performance_optimization"] = "good"
            else:
                assessment["performance_optimization"] = "needs_improvement"
        
        # Assess reliability optimization (error handling + cache + health)
        reliability_indicators = []
        
        if metrics["error_handling_quality"]:
            error_data = metrics["error_handling_quality"][0]
            if error_data["pass_rate"] > 0.8:
                reliability_indicators.append("good")
            elif error_data["pass_rate"] > 0.6:
                reliability_indicators.append("fair")
            else:
                reliability_indicators.append("poor")
        
        if metrics["cache_effectiveness"]:
            cache_data = metrics["cache_effectiveness"][0]
            if cache_data["system_health"] in ["excellent", "good"]:
                reliability_indicators.append("good")
            else:
                reliability_indicators.append("fair")
        
        if reliability_indicators:
            good_reliability = reliability_indicators.count("good")
            if good_reliability >= len(reliability_indicators) * 0.8:
                assessment["reliability_optimization"] = "excellent"
            elif good_reliability >= len(reliability_indicators) * 0.6:
                assessment["reliability_optimization"] = "good"
            else:
                assessment["reliability_optimization"] = "needs_improvement"
        
        # Assess user experience optimization (progress tracking + frontend)
        ux_indicators = []
        
        if metrics["progress_tracking_accuracy"]:
            progress_data = metrics["progress_tracking_accuracy"][0]
            if progress_data["effectiveness"] in ["excellent", "good"]:
                ux_indicators.append("good")
            else:
                ux_indicators.append("fair")
        
        if metrics["frontend_compatibility"]:
            frontend_data = metrics["frontend_compatibility"][0]
            if frontend_data["integration_quality"] in ["excellent", "good"]:
                ux_indicators.append("good")
            else:
                ux_indicators.append("fair")
        
        if ux_indicators:
            good_ux = ux_indicators.count("good")
            if good_ux >= len(ux_indicators) * 0.8:
                assessment["user_experience_optimization"] = "excellent"
            elif good_ux >= len(ux_indicators) * 0.6:
                assessment["user_experience_optimization"] = "good"
            else:
                assessment["user_experience_optimization"] = "needs_improvement"
        
        # Assess system monitoring optimization
        if metrics["system_health_reliability"]:
            health_data = metrics["system_health_reliability"][0]
            if health_data["overall_quality"] == "excellent":
                assessment["system_monitoring_optimization"] = "excellent"
            elif health_data["overall_quality"] == "good":
                assessment["system_monitoring_optimization"] = "good"
            else:
                assessment["system_monitoring_optimization"] = "needs_improvement"
        
        # Overall assessment
        optimization_areas = [
            assessment["performance_optimization"],
            assessment["reliability_optimization"],
            assessment["user_experience_optimization"],
            assessment["system_monitoring_optimization"]
        ]
        
        excellent_count = optimization_areas.count("excellent")
        good_count = optimization_areas.count("good")
        known_count = len([area for area in optimization_areas if area != "unknown"])
        
        if known_count > 0:
            success_ratio = (excellent_count + good_count) / known_count
            
            if success_ratio >= 0.8:
                assessment["overall_optimization_success"] = "highly_successful"
            elif success_ratio >= 0.6:
                assessment["overall_optimization_success"] = "successful"
            else:
                assessment["overall_optimization_success"] = "partially_successful"
        
        return assessment
    
    def generate_recommendations(self) -> None:
        """Generate recommendations based on test results"""
        recommendations = []
        
        results = self.test_results["test_suite_results"]
        
        # Check each test suite for specific recommendations
        for suite_name, suite_result in results.items():
            if not suite_result.get("success", False):
                recommendations.append(f"Fix failures in {suite_name} test suite")
                continue
            
            # Extract recommendations from successful test results
            if "results" in suite_result:
                suite_data = suite_result["results"]
                
                # Look for assessment recommendations
                if "overall_assessment" in suite_data:
                    assessment = suite_data["overall_assessment"]
                    if "recommendations" in assessment:
                        for rec in assessment["recommendations"]:
                            recommendations.append(f"{suite_name}: {rec}")
        
        # Add general recommendations based on overall assessment
        overall_assessment = self.test_results["overall_summary"]["overall_optimization_assessment"]
        
        if overall_assessment["performance_optimization"] == "needs_improvement":
            recommendations.append("Consider optimizing batch processing performance further")
        
        if overall_assessment["reliability_optimization"] == "needs_improvement":
            recommendations.append("Improve system reliability through better error handling and caching")
        
        if overall_assessment["user_experience_optimization"] == "needs_improvement":
            recommendations.append("Enhance user experience through better progress tracking and frontend integration")
        
        if overall_assessment["system_monitoring_optimization"] == "needs_improvement":
            recommendations.append("Improve system health monitoring and resource tracking")
        
        # Remove duplicates and store
        self.test_results["recommendations"] = list(set(recommendations))
    
    async def run_all_tests(self) -> Dict:
        """Run all batch processing optimization tests"""
        print("🚀 RAG-Anything Batch Processing Optimization - Comprehensive Test Suite")
        print("=" * 80)
        print("Validating all implemented batch processing optimizations:")
        print("  ✅ Backend Batch Processing Optimization")
        print("  ✅ Frontend Integration Fix")  
        print("  ✅ Intelligent Caching")
        print("  ✅ Enhanced Error Handling & Progress")
        print("  ✅ System Health Monitoring")
        print()
        
        # Check server health first
        if not await self.check_server_health():
            print("❌ API server is not available. Please start the server and try again.")
            return self.test_results
        
        print("🧪 Starting comprehensive test execution...")
        print()
        
        # Define test suite order and execution
        test_suites = [
            ("Batch Processing Optimizations", self.run_batch_processing_tests),
            ("Performance Benchmarks", self.run_performance_benchmark_tests),
            ("Cache Effectiveness", self.run_cache_effectiveness_tests),
            ("Error Handling", self.run_error_handling_tests),
            ("Progress Tracking", self.run_progress_tracking_tests),
            ("Frontend Integration", self.run_frontend_integration_tests),
            ("System Health Monitoring", self.run_system_health_tests)
        ]
        
        # Run each test suite
        for i, (suite_name, test_func) in enumerate(test_suites, 1):
            print(f"{i}️⃣ Running {suite_name} Tests...")
            
            suite_start_time = time.time()
            
            try:
                suite_result = await test_func()
                suite_execution_time = time.time() - suite_start_time
                
                suite_result["execution_time"] = suite_execution_time
                self.test_results["test_suite_results"][suite_result["test_name"]] = suite_result
                
                if suite_result["success"]:
                    print(f"   ✅ {suite_name} completed successfully in {suite_execution_time:.1f}s")
                else:
                    print(f"   ❌ {suite_name} failed after {suite_execution_time:.1f}s")
                    if "error" in suite_result:
                        print(f"      Error: {suite_result['error']}")
                
            except Exception as e:
                suite_execution_time = time.time() - suite_start_time
                print(f"   ❌ {suite_name} failed with exception after {suite_execution_time:.1f}s")
                print(f"      Error: {e}")
                
                self.test_results["test_suite_results"][f"failed_{suite_name.lower().replace(' ', '_')}"] = {
                    "test_name": suite_name.lower().replace(' ', '_'),
                    "success": False,
                    "error": str(e),
                    "execution_time": suite_execution_time,
                    "traceback": traceback.format_exc()
                }
            
            print()  # Add spacing between test suites
        
        # Analyze results
        self.analyze_test_results()
        
        # Add completion timestamp
        self.test_results["test_run_info"]["end_time"] = datetime.now().isoformat()
        self.test_results["test_run_info"]["total_execution_time"] = sum(
            suite.get("execution_time", 0) 
            for suite in self.test_results["test_suite_results"].values()
        )
        
        return self.test_results
    
    def print_comprehensive_summary(self) -> None:
        """Print comprehensive test summary"""
        print("=" * 80)
        print("📊 COMPREHENSIVE BATCH PROCESSING OPTIMIZATION TEST RESULTS")
        print("=" * 80)
        
        summary = self.test_results["overall_summary"]
        
        # Test suite success summary
        print(f"\n🎯 Test Suite Execution Summary:")
        print(f"   Successful Test Suites: {summary['successful_test_suites']}/{summary['total_test_suites']}")
        print(f"   Success Rate: {summary['test_suite_success_rate']:.1%}")
        print(f"   Total Execution Time: {self.test_results['test_run_info']['total_execution_time']:.1f}s")
        
        # Optimization assessment
        optimization = summary["overall_optimization_assessment"]
        print(f"\n🚀 Batch Processing Optimization Assessment:")
        print(f"   Performance Optimization: {optimization['performance_optimization'].replace('_', ' ').upper()}")
        print(f"   Reliability Optimization: {optimization['reliability_optimization'].replace('_', ' ').upper()}")
        print(f"   User Experience Optimization: {optimization['user_experience_optimization'].replace('_', ' ').upper()}")
        print(f"   System Monitoring Optimization: {optimization['system_monitoring_optimization'].replace('_', ' ').upper()}")
        print(f"   Overall Success: {optimization['overall_optimization_success'].replace('_', ' ').upper()}")
        
        # Detailed test suite results
        print(f"\n📋 Detailed Test Suite Results:")
        for suite_name, suite_result in self.test_results["test_suite_results"].items():
            status = "✅" if suite_result["success"] else "❌"
            execution_time = suite_result.get("execution_time", 0)
            print(f"   {status} {suite_name.replace('_', ' ').title()}: {execution_time:.1f}s")
            
            if not suite_result["success"] and "error" in suite_result:
                print(f"      Error: {suite_result['error']}")
        
        # Recommendations
        if self.test_results["recommendations"]:
            print(f"\n💡 Recommendations for Further Improvement:")
            for i, recommendation in enumerate(self.test_results["recommendations"], 1):
                print(f"   {i}. {recommendation}")
        else:
            print(f"\n✅ Excellent! No recommendations - all optimizations are working perfectly!")
        
        # Key metrics summary
        metrics = summary["optimization_metrics"]
        print(f"\n📈 Key Performance Indicators:")
        
        if metrics["performance_improvements"]:
            perf = metrics["performance_improvements"][0]
            print(f"   Average Processing Speed: {perf.get('avg_docs_per_second', 0):.2f} docs/sec")
            print(f"   Peak Processing Speed: {perf.get('peak_docs_per_second', 0):.2f} docs/sec")
        
        if metrics["cache_effectiveness"]:
            cache = metrics["cache_effectiveness"][0] 
            print(f"   Cache System Health: {cache['system_health'].replace('_', ' ').title()}")
            print(f"   Cache Performance Impact: {cache['performance_impact'].replace('_', ' ').title()}")
        
        if metrics["error_handling_quality"]:
            error = metrics["error_handling_quality"][0]
            print(f"   Error Handling Pass Rate: {error['pass_rate']:.1%}")
        
        print(f"\n📄 Detailed results saved to: batch_optimization_comprehensive_results.json")


async def main():
    """Main test runner execution"""
    runner = ComprehensiveTestRunner()
    
    try:
        # Run all tests
        test_results = await runner.run_all_tests()
        
        # Save comprehensive results
        results_file = Path("batch_optimization_comprehensive_results.json")
        with open(results_file, "w") as f:
            json.dump(test_results, f, indent=2, default=str)
        
        # Print comprehensive summary
        runner.print_comprehensive_summary()
        
        print(f"\n🏁 Comprehensive batch processing optimization testing completed!")
        
        # Set exit code based on results
        success_rate = test_results["overall_summary"]["test_suite_success_rate"]
        if success_rate >= 0.8:
            print("✅ Overall test result: SUCCESS")
            sys.exit(0)
        else:
            print("⚠️ Overall test result: PARTIAL SUCCESS")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Test runner failed: {e}")
        print(f"❌ Test runner failed: {e}")
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    print("🧪 RAG-Anything Batch Processing Optimization - Comprehensive Test Suite")
    print("This suite validates all the key optimizations implemented:")
    print("  • Backend batch processing with RAGAnything integration")
    print("  • Frontend API integration patterns")
    print("  • Intelligent caching and performance tracking")
    print("  • Enhanced error handling and recovery")
    print("  • Real-time progress tracking with WebSocket")
    print("  • System health monitoring and resource management")
    print()
    print("⚠️ Make sure the RAG API server is running on localhost:8001 before starting tests.")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Test execution interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)