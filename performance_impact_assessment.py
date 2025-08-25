#!/usr/bin/env python3
"""
Performance Impact Assessment for Corrupted Content
Analyzes and monitors the impact of corrupted content on RAG system performance
"""

import json
import time
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics for RAG operations"""
    timestamp: str
    operation_type: str  # "query", "index", "insert", "cleanup"
    
    # Query Performance
    query_latency: float  # seconds
    result_count: int
    result_quality_avg: float
    corrupted_results_filtered: int
    
    # System Resource Usage
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_io_read: float
    disk_io_write: float
    
    # Database Performance
    db_size_mb: float
    index_fragmentation: float
    cache_hit_rate: float
    
    # Quality Impact
    corruption_impact_score: float  # 0-1, higher = more impact
    search_accuracy: float  # 0-1, higher = better accuracy
    user_satisfaction_proxy: float  # 0-1, based on result quality
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PerformanceMonitor:
    """Monitors and analyzes RAG system performance"""
    
    def __init__(self, storage_path: str = "/home/ragsvr/projects/ragsystem/rag_storage"):
        self.storage_path = Path(storage_path)
        self.metrics_path = self.storage_path / "performance_metrics.json"
        self.analysis_path = self.storage_path / "performance_analysis.json"
        
        # Performance baselines (to be established)
        self.baselines = {
            'query_latency': 1.0,  # seconds
            'memory_usage': 1024,  # MB
            'cpu_usage': 50,  # percent
            'result_quality': 0.7,  # average quality score
            'search_accuracy': 0.8  # search accuracy
        }
        
        # Initialize monitoring
        self._init_monitoring()
    
    def _init_monitoring(self):
        """Initialize performance monitoring files"""
        if not self.metrics_path.exists():
            with open(self.metrics_path, 'w', encoding='utf-8') as f:
                json.dump([], f)
            logger.info("Initialized performance metrics database")
        
        if not self.analysis_path.exists():
            with open(self.analysis_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'last_analysis': None,
                    'performance_trends': {},
                    'corruption_impact_analysis': {},
                    'recommendations': []
                }, f, indent=2)
            logger.info("Initialized performance analysis database")
    
    def record_performance(self, operation_type: str, query_latency: float = 0.0,
                          result_count: int = 0, result_quality_avg: float = 0.0,
                          corrupted_results_filtered: int = 0,
                          corruption_impact_score: float = 0.0,
                          search_accuracy: float = 0.0) -> PerformanceMetrics:
        """Record performance metrics for an operation"""
        
        # Get system metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk_io = psutil.disk_io_counters()
        
        # Get database size
        db_size_mb = self._calculate_db_size()
        
        # Create metrics object
        metrics = PerformanceMetrics(
            timestamp=datetime.now().isoformat(),
            operation_type=operation_type,
            query_latency=query_latency,
            result_count=result_count,
            result_quality_avg=result_quality_avg,
            corrupted_results_filtered=corrupted_results_filtered,
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / (1024 * 1024),
            disk_io_read=disk_io.read_bytes / (1024 * 1024) if disk_io else 0,
            disk_io_write=disk_io.write_bytes / (1024 * 1024) if disk_io else 0,
            db_size_mb=db_size_mb,
            index_fragmentation=0.0,  # Would need database-specific calculation
            cache_hit_rate=0.0,  # Would need cache-specific calculation
            corruption_impact_score=corruption_impact_score,
            search_accuracy=search_accuracy,
            user_satisfaction_proxy=result_quality_avg  # Simple proxy
        )
        
        # Save metrics
        self._save_metrics(metrics)
        
        return metrics
    
    def _calculate_db_size(self) -> float:
        """Calculate total database size in MB"""
        total_size = 0
        db_files = [
            'kv_store_full_docs.json',
            'kv_store_text_chunks.json',
            'kv_store_full_entities.json', 
            'kv_store_full_relations.json',
            'vdb_chunks.json',
            'graph_chunk_entity_relation.graphml'
        ]
        
        for db_file in db_files:
            file_path = self.storage_path / db_file
            if file_path.exists():
                total_size += file_path.stat().st_size
        
        return total_size / (1024 * 1024)  # Convert to MB
    
    def _save_metrics(self, metrics: PerformanceMetrics):
        """Save metrics to file"""
        # Load existing metrics
        with open(self.metrics_path, 'r', encoding='utf-8') as f:
            all_metrics = json.load(f)
        
        # Add new metrics
        all_metrics.append(metrics.to_dict())
        
        # Keep only last 10000 entries to prevent file bloat
        if len(all_metrics) > 10000:
            all_metrics = all_metrics[-10000:]
        
        # Save back
        with open(self.metrics_path, 'w', encoding='utf-8') as f:
            json.dump(all_metrics, f, indent=2)
    
    def get_recent_metrics(self, hours: int = 24) -> List[PerformanceMetrics]:
        """Get recent performance metrics"""
        with open(self.metrics_path, 'r', encoding='utf-8') as f:
            all_metrics = json.load(f)
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = []
        
        for metric_data in all_metrics:
            metric_time = datetime.fromisoformat(metric_data['timestamp'])
            if metric_time >= cutoff_time:
                recent_metrics.append(PerformanceMetrics(**metric_data))
        
        return recent_metrics
    
    def analyze_corruption_impact(self, timeframe_hours: int = 24) -> Dict[str, Any]:
        """Analyze the impact of corrupted content on performance"""
        metrics = self.get_recent_metrics(timeframe_hours)
        
        if not metrics:
            return {'error': 'No metrics available for analysis'}
        
        # Separate metrics by corruption impact
        high_corruption = [m for m in metrics if m.corruption_impact_score > 0.5]
        low_corruption = [m for m in metrics if m.corruption_impact_score <= 0.2]
        
        analysis = {
            'timeframe_hours': timeframe_hours,
            'total_operations': len(metrics),
            'high_corruption_operations': len(high_corruption),
            'low_corruption_operations': len(low_corruption),
            'corruption_impact_rate': len(high_corruption) / len(metrics) if metrics else 0
        }
        
        # Compare performance between high and low corruption scenarios
        if high_corruption and low_corruption:
            analysis['performance_comparison'] = {
                'query_latency': {
                    'high_corruption_avg': np.mean([m.query_latency for m in high_corruption]),
                    'low_corruption_avg': np.mean([m.query_latency for m in low_corruption]),
                    'degradation_factor': None
                },
                'memory_usage': {
                    'high_corruption_avg': np.mean([m.memory_used_mb for m in high_corruption]),
                    'low_corruption_avg': np.mean([m.memory_used_mb for m in low_corruption]),
                    'increase_factor': None
                },
                'result_quality': {
                    'high_corruption_avg': np.mean([m.result_quality_avg for m in high_corruption]),
                    'low_corruption_avg': np.mean([m.result_quality_avg for m in low_corruption]),
                    'quality_loss': None
                },
                'search_accuracy': {
                    'high_corruption_avg': np.mean([m.search_accuracy for m in high_corruption]),
                    'low_corruption_avg': np.mean([m.search_accuracy for m in low_corruption]),
                    'accuracy_loss': None
                }
            }
            
            # Calculate degradation factors
            comp = analysis['performance_comparison']
            
            # Query latency degradation
            if comp['query_latency']['low_corruption_avg'] > 0:
                comp['query_latency']['degradation_factor'] = (
                    comp['query_latency']['high_corruption_avg'] / 
                    comp['query_latency']['low_corruption_avg']
                )
            
            # Memory usage increase
            if comp['memory_usage']['low_corruption_avg'] > 0:
                comp['memory_usage']['increase_factor'] = (
                    comp['memory_usage']['high_corruption_avg'] / 
                    comp['memory_usage']['low_corruption_avg']
                )
            
            # Quality loss
            comp['result_quality']['quality_loss'] = (
                comp['result_quality']['low_corruption_avg'] - 
                comp['result_quality']['high_corruption_avg']
            )
            
            # Accuracy loss
            comp['search_accuracy']['accuracy_loss'] = (
                comp['search_accuracy']['low_corruption_avg'] - 
                comp['search_accuracy']['high_corruption_avg']
            )
        
        # Calculate corruption filtering statistics
        total_filtered = sum(m.corrupted_results_filtered for m in metrics)
        analysis['filtering_stats'] = {
            'total_corrupted_filtered': total_filtered,
            'avg_filtered_per_query': total_filtered / len(metrics) if metrics else 0,
            'max_filtered_single_query': max((m.corrupted_results_filtered for m in metrics), default=0)
        }
        
        # Performance trends
        if len(metrics) >= 10:  # Need sufficient data points
            analysis['trends'] = self._calculate_performance_trends(metrics)
        
        return analysis
    
    def _calculate_performance_trends(self, metrics: List[PerformanceMetrics]) -> Dict[str, Any]:
        """Calculate performance trends over time"""
        # Sort by timestamp
        metrics.sort(key=lambda m: m.timestamp)
        
        # Calculate trends using simple linear regression
        timestamps = [datetime.fromisoformat(m.timestamp).timestamp() for m in metrics]
        
        trends = {}
        
        # Query latency trend
        latencies = [m.query_latency for m in metrics if m.query_latency > 0]
        if len(latencies) >= 5:
            trend_slope = np.polyfit(timestamps[-len(latencies):], latencies, 1)[0]
            trends['query_latency'] = {
                'trend': 'increasing' if trend_slope > 0.01 else 'decreasing' if trend_slope < -0.01 else 'stable',
                'slope': trend_slope
            }
        
        # Memory usage trend
        memory_usage = [m.memory_used_mb for m in metrics]
        if len(memory_usage) >= 5:
            trend_slope = np.polyfit(timestamps[-len(memory_usage):], memory_usage, 1)[0]
            trends['memory_usage'] = {
                'trend': 'increasing' if trend_slope > 1 else 'decreasing' if trend_slope < -1 else 'stable',
                'slope': trend_slope
            }
        
        # Result quality trend
        quality_scores = [m.result_quality_avg for m in metrics if m.result_quality_avg > 0]
        if len(quality_scores) >= 5:
            trend_slope = np.polyfit(timestamps[-len(quality_scores):], quality_scores, 1)[0]
            trends['result_quality'] = {
                'trend': 'improving' if trend_slope > 0.01 else 'degrading' if trend_slope < -0.01 else 'stable',
                'slope': trend_slope
            }
        
        return trends
    
    def generate_performance_report(self, timeframe_hours: int = 24) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        metrics = self.get_recent_metrics(timeframe_hours)
        corruption_impact = self.analyze_corruption_impact(timeframe_hours)
        
        if not metrics:
            return {'error': 'No metrics available for report generation'}
        
        # Basic statistics
        query_metrics = [m for m in metrics if m.operation_type == 'query' and m.query_latency > 0]
        
        report = {
            'report_period': {
                'timeframe_hours': timeframe_hours,
                'start_time': min(m.timestamp for m in metrics),
                'end_time': max(m.timestamp for m in metrics),
                'total_operations': len(metrics)
            },
            'query_performance': {
                'total_queries': len(query_metrics),
                'avg_latency': np.mean([m.query_latency for m in query_metrics]) if query_metrics else 0,
                'p95_latency': np.percentile([m.query_latency for m in query_metrics], 95) if query_metrics else 0,
                'p99_latency': np.percentile([m.query_latency for m in query_metrics], 99) if query_metrics else 0,
                'avg_results_per_query': np.mean([m.result_count for m in query_metrics]) if query_metrics else 0
            },
            'resource_usage': {
                'avg_cpu_percent': np.mean([m.cpu_percent for m in metrics]),
                'max_cpu_percent': max(m.cpu_percent for m in metrics),
                'avg_memory_mb': np.mean([m.memory_used_mb for m in metrics]),
                'max_memory_mb': max(m.memory_used_mb for m in metrics),
                'avg_memory_percent': np.mean([m.memory_percent for m in metrics])
            },
            'database_metrics': {
                'current_size_mb': metrics[-1].db_size_mb if metrics else 0,
                'avg_size_mb': np.mean([m.db_size_mb for m in metrics]),
                'size_growth_mb': (metrics[-1].db_size_mb - metrics[0].db_size_mb) if len(metrics) > 1 else 0
            },
            'quality_metrics': {
                'avg_result_quality': np.mean([m.result_quality_avg for m in metrics if m.result_quality_avg > 0]),
                'avg_search_accuracy': np.mean([m.search_accuracy for m in metrics if m.search_accuracy > 0]),
                'total_corrupted_filtered': sum(m.corrupted_results_filtered for m in metrics),
                'corruption_filter_rate': np.mean([m.corrupted_results_filtered / max(m.result_count, 1) for m in query_metrics]) if query_metrics else 0
            },
            'corruption_impact_analysis': corruption_impact,
            'performance_alerts': self._generate_performance_alerts(metrics),
            'recommendations': self._generate_performance_recommendations(metrics, corruption_impact)
        }
        
        return report
    
    def _generate_performance_alerts(self, metrics: List[PerformanceMetrics]) -> List[Dict[str, Any]]:
        """Generate performance alerts based on thresholds"""
        alerts = []
        
        if not metrics:
            return alerts
        
        recent_metrics = metrics[-10:]  # Last 10 operations
        
        # High latency alert
        avg_latency = np.mean([m.query_latency for m in recent_metrics if m.query_latency > 0])
        if avg_latency > self.baselines['query_latency'] * 2:
            alerts.append({
                'type': 'high_latency',
                'severity': 'warning',
                'message': f"Query latency ({avg_latency:.2f}s) is {avg_latency/self.baselines['query_latency']:.1f}x baseline",
                'threshold_exceeded': self.baselines['query_latency'] * 2
            })
        
        # High memory usage alert
        avg_memory = np.mean([m.memory_used_mb for m in recent_metrics])
        if avg_memory > self.baselines['memory_usage'] * 2:
            alerts.append({
                'type': 'high_memory',
                'severity': 'warning',
                'message': f"Memory usage ({avg_memory:.0f}MB) is {avg_memory/self.baselines['memory_usage']:.1f}x baseline",
                'threshold_exceeded': self.baselines['memory_usage'] * 2
            })
        
        # Low quality alert
        avg_quality = np.mean([m.result_quality_avg for m in recent_metrics if m.result_quality_avg > 0])
        if avg_quality < self.baselines['result_quality'] * 0.7:
            alerts.append({
                'type': 'low_quality',
                'severity': 'critical',
                'message': f"Result quality ({avg_quality:.2f}) is below acceptable threshold",
                'threshold_exceeded': self.baselines['result_quality'] * 0.7
            })
        
        # High corruption impact alert
        avg_corruption_impact = np.mean([m.corruption_impact_score for m in recent_metrics])
        if avg_corruption_impact > 0.5:
            alerts.append({
                'type': 'high_corruption_impact',
                'severity': 'critical',
                'message': f"High corruption impact detected ({avg_corruption_impact:.2f})",
                'threshold_exceeded': 0.5
            })
        
        return alerts
    
    def _generate_performance_recommendations(self, metrics: List[PerformanceMetrics], 
                                           corruption_analysis: Dict[str, Any]) -> List[str]:
        """Generate performance improvement recommendations"""
        recommendations = []
        
        if not metrics:
            return recommendations
        
        # High corruption impact
        if corruption_analysis.get('corruption_impact_rate', 0) > 0.3:
            recommendations.append("High corruption rate detected - run database cleanup to remove corrupted content")
        
        # Performance degradation due to corruption
        perf_comp = corruption_analysis.get('performance_comparison', {})
        if perf_comp.get('query_latency', {}).get('degradation_factor', 1) > 1.5:
            recommendations.append("Query latency significantly impacted by corruption - implement query filtering")
        
        if perf_comp.get('result_quality', {}).get('quality_loss', 0) > 0.3:
            recommendations.append("Result quality severely impacted - consider reprocessing corrupted documents")
        
        # Resource usage
        avg_memory = np.mean([m.memory_used_mb for m in metrics])
        if avg_memory > self.baselines['memory_usage'] * 1.5:
            recommendations.append("High memory usage detected - consider database optimization or system upgrade")
        
        # Database size growth
        if len(metrics) > 1:
            size_growth = metrics[-1].db_size_mb - metrics[0].db_size_mb
            if size_growth > 100:  # More than 100MB growth
                recommendations.append("Significant database growth - consider archiving or cleanup of old data")
        
        # Query performance
        query_metrics = [m for m in metrics if m.operation_type == 'query' and m.query_latency > 0]
        if query_metrics:
            avg_latency = np.mean([m.query_latency for m in query_metrics])
            if avg_latency > self.baselines['query_latency'] * 1.5:
                recommendations.append("Query latency above baseline - consider index optimization or query tuning")
        
        return recommendations
    
    def save_analysis_report(self, report: Dict[str, Any]):
        """Save analysis report to file"""
        with open(self.analysis_path, 'w', encoding='utf-8') as f:
            json.dump({
                'last_analysis': datetime.now().isoformat(),
                'latest_report': report
            }, f, indent=2, ensure_ascii=False)


# Integration with query optimization
class PerformanceAwareQueryWrapper:
    """Query wrapper that monitors and optimizes based on performance"""
    
    def __init__(self, lightrag_instance, storage_path: str = "/home/ragsvr/projects/ragsystem/rag_storage"):
        self.lightrag = lightrag_instance
        self.monitor = PerformanceMonitor(storage_path)
    
    async def monitored_query(self, query: str, mode: str = "hybrid", **kwargs) -> Tuple[str, PerformanceMetrics]:
        """Execute query with performance monitoring"""
        start_time = time.time()
        
        try:
            # Execute query
            result = await self.lightrag.aquery(query, mode=mode, **kwargs)
            
            # Calculate performance metrics
            query_latency = time.time() - start_time
            
            # Simple quality estimation (would need more sophisticated analysis)
            result_quality = self._estimate_result_quality(result)
            corruption_impact = self._estimate_corruption_impact(result)
            
            # Record performance
            metrics = self.monitor.record_performance(
                operation_type="query",
                query_latency=query_latency,
                result_count=1,  # Single result for now
                result_quality_avg=result_quality,
                corrupted_results_filtered=0,  # Would need actual filtering data
                corruption_impact_score=corruption_impact,
                search_accuracy=result_quality  # Simple proxy
            )
            
            return result, metrics
            
        except Exception as e:
            # Record failed query
            query_latency = time.time() - start_time
            metrics = self.monitor.record_performance(
                operation_type="query_failed",
                query_latency=query_latency,
                result_count=0,
                result_quality_avg=0.0,
                corrupted_results_filtered=0,
                corruption_impact_score=1.0,  # Max impact for failed query
                search_accuracy=0.0
            )
            
            raise e
    
    def _estimate_result_quality(self, result: str) -> float:
        """Estimate result quality (simplified)"""
        if not result or len(result.strip()) == 0:
            return 0.0
        
        # Check for corruption patterns
        corruption_patterns = [r'[规]{10,}', r'[国]{10,}', r'[《》、]{10,}']
        
        for pattern in corruption_patterns:
            if len(__import__('re').findall(pattern, result)) > 0:
                return 0.2  # Low quality if corruption detected
        
        # Simple quality heuristics
        if len(result) < 50:
            return 0.4  # Short results might be low quality
        elif len(result) > 1000:
            return 0.9  # Long, detailed results likely high quality
        else:
            return 0.7  # Moderate quality
    
    def _estimate_corruption_impact(self, result: str) -> float:
        """Estimate corruption impact on result"""
        if not result:
            return 0.5
        
        corruption_patterns = [r'[规]{10,}', r'[国]{10,}', r'[《》、]{10,}']
        
        corruption_score = 0.0
        for pattern in corruption_patterns:
            matches = len(__import__('re').findall(pattern, result))
            if matches > 0:
                corruption_score += min(matches * 0.2, 1.0)
        
        return min(corruption_score, 1.0)
    
    def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance report"""
        return self.monitor.generate_performance_report(hours)


# Usage example and testing
def test_performance_monitoring():
    """Test performance monitoring functionality"""
    monitor = PerformanceMonitor()
    
    # Simulate some operations
    print("=== Performance Monitoring Test ===")
    
    # Simulate query with low corruption
    metrics1 = monitor.record_performance(
        operation_type="query",
        query_latency=0.5,
        result_count=5,
        result_quality_avg=0.8,
        corrupted_results_filtered=0,
        corruption_impact_score=0.1,
        search_accuracy=0.85
    )
    
    # Simulate query with high corruption
    metrics2 = monitor.record_performance(
        operation_type="query", 
        query_latency=2.1,
        result_count=3,
        result_quality_avg=0.3,
        corrupted_results_filtered=2,
        corruption_impact_score=0.8,
        search_accuracy=0.4
    )
    
    # Generate report
    report = monitor.generate_performance_report(hours=1)
    
    print(f"Query Performance:")
    print(f"  Average Latency: {report['query_performance']['avg_latency']:.2f}s")
    print(f"  Average Quality: {report['quality_metrics']['avg_result_quality']:.2f}")
    
    print(f"\nCorruption Impact:")
    corruption_analysis = report['corruption_impact_analysis']
    print(f"  Impact Rate: {corruption_analysis['corruption_impact_rate']:.2%}")
    print(f"  Total Filtered: {corruption_analysis['filtering_stats']['total_corrupted_filtered']}")
    
    print(f"\nRecommendations:")
    for rec in report['recommendations']:
        print(f"  - {rec}")


if __name__ == "__main__":
    test_performance_monitoring()