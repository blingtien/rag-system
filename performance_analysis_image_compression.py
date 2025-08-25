#!/usr/bin/env python3
"""
Comprehensive Performance Analysis for Image Compression Fix Implementation

This script evaluates various performance aspects of the image compression utilities
including processing overhead, scalability, API performance impact, and resource utilization.
"""

import os
import sys
import time
import json
import asyncio
import psutil
import threading
import multiprocessing
import tracemalloc
import gc
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from dataclasses import dataclass, asdict
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import logging
import tempfile
import base64
from PIL import Image
import io

# Add RAG-Anything to path
sys.path.insert(0, '/home/ragsvr/projects/ragsystem/RAG-Anything')

# Import the modules to analyze
from raganything.image_utils import (
    validate_and_compress_image,
    calculate_estimated_base64_size,
    validate_payload_size,
    ImageCompressionSettings
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics"""
    operation: str
    duration_seconds: float
    cpu_usage_percent: float
    memory_used_mb: float
    memory_peak_mb: float
    io_reads: int
    io_writes: int
    thread_count: int
    file_size_kb: float
    compressed_size_kb: float
    compression_ratio: float
    success: bool
    error: Optional[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class PerformanceAnalyzer:
    """Comprehensive performance analyzer for image compression"""
    
    def __init__(self, output_dir: str = "./performance_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.metrics: List[PerformanceMetrics] = []
        self.test_images: Dict[str, Path] = {}
        self.process = psutil.Process()
        
    def generate_test_images(self) -> Dict[str, Path]:
        """Generate test images of various sizes and types"""
        test_images = {}
        temp_dir = Path(tempfile.mkdtemp(prefix="perf_test_images_"))
        
        sizes = [
            ("tiny", (100, 100)),
            ("small", (500, 500)),
            ("medium", (1024, 1024)),
            ("large", (2048, 2048)),
            ("huge", (4096, 4096))
        ]
        
        for size_name, dimensions in sizes:
            # Create RGB image with random content
            img_array = np.random.randint(0, 255, (*dimensions, 3), dtype=np.uint8)
            img = Image.fromarray(img_array)
            
            # Save in different formats
            for fmt in ['JPEG', 'PNG']:
                filename = f"test_{size_name}.{fmt.lower()}"
                filepath = temp_dir / filename
                img.save(filepath, format=fmt, quality=95 if fmt == 'JPEG' else None)
                test_images[f"{size_name}_{fmt.lower()}"] = filepath
                
                # Log file size
                file_size_kb = filepath.stat().st_size / 1024
                logger.info(f"Generated {filename}: {file_size_kb:.1f}KB")
        
        self.test_images = test_images
        return test_images
    
    def measure_resource_usage(self) -> Dict[str, Any]:
        """Measure current resource usage"""
        memory_info = self.process.memory_info()
        io_counters = self.process.io_counters()
        
        return {
            'cpu_percent': self.process.cpu_percent(interval=0.1),
            'memory_rss_mb': memory_info.rss / 1024 / 1024,
            'memory_vms_mb': memory_info.vms / 1024 / 1024,
            'io_read_count': io_counters.read_count,
            'io_write_count': io_counters.write_count,
            'thread_count': self.process.num_threads(),
            'open_files': len(self.process.open_files())
        }
    
    def profile_single_compression(self, image_path: Path, max_size_kb: int = 200) -> PerformanceMetrics:
        """Profile a single image compression operation"""
        # Start resource monitoring
        gc.collect()
        tracemalloc.start()
        start_resources = self.measure_resource_usage()
        start_time = time.perf_counter()
        
        success = False
        error = None
        compressed_size_kb = 0
        
        try:
            # Perform compression
            result = validate_and_compress_image(
                str(image_path),
                max_size_kb=max_size_kb,
                force_compression=True
            )
            
            if result:
                success = True
                compressed_size_kb = len(result) / 1024
            else:
                error = "Compression returned None"
                
        except Exception as e:
            error = str(e)
            logger.error(f"Compression failed: {e}")
        
        # End measurements
        end_time = time.perf_counter()
        end_resources = self.measure_resource_usage()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Calculate metrics
        duration = end_time - start_time
        original_size_kb = image_path.stat().st_size / 1024
        
        metrics = PerformanceMetrics(
            operation=f"compress_{image_path.name}",
            duration_seconds=duration,
            cpu_usage_percent=end_resources['cpu_percent'],
            memory_used_mb=current / 1024 / 1024,
            memory_peak_mb=peak / 1024 / 1024,
            io_reads=end_resources['io_read_count'] - start_resources['io_read_count'],
            io_writes=end_resources['io_write_count'] - start_resources['io_write_count'],
            thread_count=end_resources['thread_count'],
            file_size_kb=original_size_kb,
            compressed_size_kb=compressed_size_kb,
            compression_ratio=original_size_kb / compressed_size_kb if compressed_size_kb > 0 else 0,
            success=success,
            error=error
        )
        
        self.metrics.append(metrics)
        return metrics
    
    async def test_concurrent_processing(self, concurrency_levels: List[int]) -> Dict[str, List[float]]:
        """Test performance under different concurrency levels"""
        results = {}
        
        for concurrency in concurrency_levels:
            logger.info(f"Testing concurrency level: {concurrency}")
            
            # Select test images
            test_subset = list(self.test_images.values())[:concurrency]
            
            # Measure concurrent execution
            start_time = time.perf_counter()
            tasks = []
            
            for img_path in test_subset:
                task = asyncio.create_task(
                    asyncio.to_thread(self.profile_single_compression, img_path)
                )
                tasks.append(task)
            
            metrics_list = await asyncio.gather(*tasks)
            total_time = time.perf_counter() - start_time
            
            # Calculate aggregate metrics
            avg_duration = np.mean([m.duration_seconds for m in metrics_list])
            total_memory = sum(m.memory_peak_mb for m in metrics_list)
            success_rate = sum(1 for m in metrics_list if m.success) / len(metrics_list)
            
            results[f"concurrency_{concurrency}"] = {
                'total_time': total_time,
                'avg_duration': avg_duration,
                'total_memory_mb': total_memory,
                'success_rate': success_rate,
                'throughput': len(metrics_list) / total_time
            }
            
            # Small delay between tests
            await asyncio.sleep(1)
        
        return results
    
    def test_memory_leak(self, iterations: int = 100) -> Dict[str, Any]:
        """Test for memory leaks over multiple iterations"""
        memory_usage = []
        test_image = list(self.test_images.values())[0]  # Use first test image
        
        gc.collect()
        initial_memory = self.process.memory_info().rss / 1024 / 1024
        
        for i in range(iterations):
            # Perform compression
            validate_and_compress_image(str(test_image), force_compression=True)
            
            # Measure memory every 10 iterations
            if i % 10 == 0:
                gc.collect()
                current_memory = self.process.memory_info().rss / 1024 / 1024
                memory_usage.append(current_memory)
                
                if i % 20 == 0:
                    logger.info(f"Iteration {i}: Memory = {current_memory:.1f}MB")
        
        gc.collect()
        final_memory = self.process.memory_info().rss / 1024 / 1024
        
        # Calculate memory growth
        memory_growth = final_memory - initial_memory
        avg_growth_per_iteration = memory_growth / iterations
        
        return {
            'initial_memory_mb': initial_memory,
            'final_memory_mb': final_memory,
            'memory_growth_mb': memory_growth,
            'avg_growth_per_iteration_mb': avg_growth_per_iteration,
            'memory_samples': memory_usage,
            'potential_leak': avg_growth_per_iteration > 0.1  # Flag if >100KB per iteration
        }
    
    def benchmark_compression_algorithms(self) -> Dict[str, Dict[str, float]]:
        """Benchmark different compression quality settings"""
        results = {}
        test_image = list(self.test_images.values())[2]  # Use medium size image
        
        quality_levels = [20, 40, 60, 80, 95]
        
        for quality in quality_levels:
            # Temporarily modify settings
            original_quality = ImageCompressionSettings.INITIAL_QUALITY['default']
            ImageCompressionSettings.INITIAL_QUALITY['default'] = quality
            
            metrics = self.profile_single_compression(test_image, max_size_kb=500)
            
            results[f"quality_{quality}"] = {
                'duration_seconds': metrics.duration_seconds,
                'compressed_size_kb': metrics.compressed_size_kb,
                'compression_ratio': metrics.compression_ratio,
                'memory_used_mb': metrics.memory_used_mb
            }
            
            # Restore original setting
            ImageCompressionSettings.INITIAL_QUALITY['default'] = original_quality
        
        return results
    
    def analyze_critical_path(self) -> Dict[str, float]:
        """Analyze time spent in different parts of the compression process"""
        test_image = list(self.test_images.values())[1]  # Use small image
        
        timings = {}
        
        # Time file reading
        start = time.perf_counter()
        with open(test_image, 'rb') as f:
            raw_data = f.read()
        timings['file_read'] = time.perf_counter() - start
        
        # Time base64 encoding
        start = time.perf_counter()
        encoded = base64.b64encode(raw_data).decode('utf-8')
        timings['base64_encode'] = time.perf_counter() - start
        
        # Time PIL operations
        start = time.perf_counter()
        with Image.open(test_image) as img:
            if img.size[0] > 1024:
                ratio = 1024 / img.size[0]
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
        timings['image_resize'] = time.perf_counter() - start
        
        # Time JPEG compression at different qualities
        with Image.open(test_image) as img:
            for quality in [85, 60, 40]:
                start = time.perf_counter()
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=quality, optimize=True)
                timings[f'jpeg_compress_q{quality}'] = time.perf_counter() - start
        
        # Calculate percentages
        total_time = sum(timings.values())
        percentages = {k: (v / total_time * 100) for k, v in timings.items()}
        
        return {
            'raw_timings': timings,
            'percentages': percentages,
            'total_time': total_time
        }
    
    def test_payload_validation(self) -> Dict[str, Any]:
        """Test payload size validation performance"""
        results = {}
        
        # Create payloads of different sizes
        payload_sizes = [10, 50, 100, 200, 500, 1000]  # KB
        
        for size_kb in payload_sizes:
            # Create a dummy payload
            dummy_data = {
                'data': 'x' * (size_kb * 1024),
                'metadata': {'size': size_kb}
            }
            
            # Measure validation time
            start = time.perf_counter()
            is_valid, actual_size = validate_payload_size(dummy_data, max_size_kb=500)
            duration = time.perf_counter() - start
            
            results[f"payload_{size_kb}kb"] = {
                'duration_seconds': duration,
                'is_valid': is_valid,
                'actual_size_kb': actual_size,
                'throughput_mb_per_sec': (size_kb / 1024) / duration if duration > 0 else 0
            }
        
        return results
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': len(self.metrics),
                'successful_tests': sum(1 for m in self.metrics if m.success),
                'failed_tests': sum(1 for m in self.metrics if not m.success),
                'avg_duration': np.mean([m.duration_seconds for m in self.metrics]) if self.metrics else 0,
                'avg_compression_ratio': np.mean([m.compression_ratio for m in self.metrics if m.compression_ratio > 0]) if self.metrics else 0,
                'avg_memory_used_mb': np.mean([m.memory_used_mb for m in self.metrics]) if self.metrics else 0,
                'max_memory_peak_mb': max([m.memory_peak_mb for m in self.metrics]) if self.metrics else 0
            },
            'detailed_metrics': [asdict(m) for m in self.metrics],
            'optimization_recommendations': self.generate_optimization_recommendations()
        }
        
        # Save report
        report_path = self.output_dir / f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved to: {report_path}")
        return report
    
    def generate_optimization_recommendations(self) -> List[Dict[str, str]]:
        """Generate optimization recommendations based on analysis"""
        recommendations = []
        
        if self.metrics:
            avg_duration = np.mean([m.duration_seconds for m in self.metrics])
            avg_memory = np.mean([m.memory_used_mb for m in self.metrics])
            
            # Performance recommendations
            if avg_duration > 1.0:
                recommendations.append({
                    'category': 'Performance',
                    'severity': 'High',
                    'issue': f'Average compression time is {avg_duration:.2f}s',
                    'recommendation': 'Consider implementing async processing with a queue system for better throughput'
                })
            
            if avg_memory > 100:
                recommendations.append({
                    'category': 'Memory',
                    'severity': 'Medium',
                    'issue': f'Average memory usage is {avg_memory:.1f}MB',
                    'recommendation': 'Implement memory pooling and reuse PIL Image objects where possible'
                })
            
            # Check for failed compressions
            failure_rate = sum(1 for m in self.metrics if not m.success) / len(self.metrics)
            if failure_rate > 0.1:
                recommendations.append({
                    'category': 'Reliability',
                    'severity': 'High',
                    'issue': f'Failure rate is {failure_rate:.1%}',
                    'recommendation': 'Implement better error handling and fallback strategies'
                })
        
        # Caching recommendations
        recommendations.append({
            'category': 'Caching',
            'severity': 'Medium',
            'issue': 'No caching mechanism detected',
            'recommendation': 'Implement LRU cache for frequently accessed images to avoid recompression'
        })
        
        # Async recommendations
        recommendations.append({
            'category': 'Architecture',
            'severity': 'Low',
            'issue': 'Synchronous processing may block API responses',
            'recommendation': 'Consider background task queue (Celery/RQ) for compression operations'
        })
        
        return recommendations
    
    def visualize_results(self):
        """Create visualization of performance metrics"""
        if not self.metrics:
            logger.warning("No metrics to visualize")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle('Image Compression Performance Analysis', fontsize=16)
        
        # Duration vs File Size
        ax1 = axes[0, 0]
        file_sizes = [m.file_size_kb for m in self.metrics]
        durations = [m.duration_seconds for m in self.metrics]
        ax1.scatter(file_sizes, durations, alpha=0.6)
        ax1.set_xlabel('Original File Size (KB)')
        ax1.set_ylabel('Compression Duration (seconds)')
        ax1.set_title('Processing Time vs File Size')
        ax1.grid(True, alpha=0.3)
        
        # Compression Ratios
        ax2 = axes[0, 1]
        ratios = [m.compression_ratio for m in self.metrics if m.compression_ratio > 0]
        ax2.hist(ratios, bins=20, edgecolor='black', alpha=0.7)
        ax2.set_xlabel('Compression Ratio')
        ax2.set_ylabel('Frequency')
        ax2.set_title('Distribution of Compression Ratios')
        ax2.grid(True, alpha=0.3)
        
        # Memory Usage
        ax3 = axes[1, 0]
        memory_used = [m.memory_used_mb for m in self.metrics]
        memory_peak = [m.memory_peak_mb for m in self.metrics]
        x_pos = np.arange(len(self.metrics))
        ax3.bar(x_pos, memory_used, alpha=0.6, label='Used')
        ax3.bar(x_pos, memory_peak, alpha=0.6, label='Peak')
        ax3.set_xlabel('Test Number')
        ax3.set_ylabel('Memory (MB)')
        ax3.set_title('Memory Usage per Test')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # Success Rate by Size
        ax4 = axes[1, 1]
        size_categories = ['<100KB', '100-500KB', '500KB-1MB', '>1MB']
        success_rates = []
        
        for category in size_categories:
            category_metrics = []
            if category == '<100KB':
                category_metrics = [m for m in self.metrics if m.file_size_kb < 100]
            elif category == '100-500KB':
                category_metrics = [m for m in self.metrics if 100 <= m.file_size_kb < 500]
            elif category == '500KB-1MB':
                category_metrics = [m for m in self.metrics if 500 <= m.file_size_kb < 1024]
            else:
                category_metrics = [m for m in self.metrics if m.file_size_kb >= 1024]
            
            if category_metrics:
                rate = sum(1 for m in category_metrics if m.success) / len(category_metrics)
                success_rates.append(rate * 100)
            else:
                success_rates.append(0)
        
        ax4.bar(size_categories, success_rates, color=['green' if r >= 90 else 'orange' if r >= 70 else 'red' for r in success_rates])
        ax4.set_ylabel('Success Rate (%)')
        ax4.set_title('Success Rate by File Size Category')
        ax4.set_ylim(0, 105)
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save figure
        fig_path = self.output_dir / f"performance_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(fig_path, dpi=150, bbox_inches='tight')
        logger.info(f"Visualization saved to: {fig_path}")
        plt.close()


async def run_comprehensive_analysis():
    """Run the complete performance analysis suite"""
    analyzer = PerformanceAnalyzer()
    
    print("\n" + "="*60)
    print("COMPREHENSIVE PERFORMANCE ANALYSIS")
    print("Image Compression Fix Implementation")
    print("="*60 + "\n")
    
    # Generate test images
    print("1. Generating test images...")
    test_images = analyzer.generate_test_images()
    print(f"   Generated {len(test_images)} test images\n")
    
    # Test individual compressions
    print("2. Testing individual compression performance...")
    for name, path in list(test_images.items())[:5]:  # Test first 5
        metrics = analyzer.profile_single_compression(path)
        print(f"   {name}: {metrics.duration_seconds:.3f}s, "
              f"Ratio: {metrics.compression_ratio:.2f}x, "
              f"Memory: {metrics.memory_peak_mb:.1f}MB")
    print()
    
    # Test concurrent processing
    print("3. Testing concurrent processing scalability...")
    concurrency_results = await analyzer.test_concurrent_processing([1, 2, 4, 8])
    for level, results in concurrency_results.items():
        print(f"   {level}: Throughput={results['throughput']:.2f} img/s, "
              f"Memory={results['total_memory_mb']:.1f}MB")
    print()
    
    # Test for memory leaks
    print("4. Testing for memory leaks (100 iterations)...")
    leak_results = analyzer.test_memory_leak(iterations=100)
    print(f"   Memory growth: {leak_results['memory_growth_mb']:.2f}MB")
    print(f"   Potential leak: {'YES' if leak_results['potential_leak'] else 'NO'}")
    print()
    
    # Benchmark compression algorithms
    print("5. Benchmarking compression quality settings...")
    algo_results = analyzer.benchmark_compression_algorithms()
    for quality, results in algo_results.items():
        print(f"   {quality}: Time={results['duration_seconds']:.3f}s, "
              f"Size={results['compressed_size_kb']:.1f}KB")
    print()
    
    # Analyze critical path
    print("6. Analyzing critical path timings...")
    critical_path = analyzer.analyze_critical_path()
    for operation, percentage in critical_path['percentages'].items():
        print(f"   {operation}: {percentage:.1f}%")
    print()
    
    # Test payload validation
    print("7. Testing payload size validation...")
    payload_results = analyzer.test_payload_validation()
    for size, results in payload_results.items():
        print(f"   {size}: {results['duration_seconds']*1000:.2f}ms, "
              f"Valid={results['is_valid']}")
    print()
    
    # Generate report and visualization
    print("8. Generating performance report and visualizations...")
    report = analyzer.generate_report()
    analyzer.visualize_results()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total tests run: {report['summary']['total_tests']}")
    print(f"Success rate: {report['summary']['successful_tests']/report['summary']['total_tests']*100:.1f}%")
    print(f"Avg compression time: {report['summary']['avg_duration']:.3f}s")
    print(f"Avg compression ratio: {report['summary']['avg_compression_ratio']:.2f}x")
    print(f"Avg memory usage: {report['summary']['avg_memory_used_mb']:.1f}MB")
    print(f"Max memory peak: {report['summary']['max_memory_peak_mb']:.1f}MB")
    
    print("\n" + "="*60)
    print("TOP OPTIMIZATION RECOMMENDATIONS")
    print("="*60)
    for i, rec in enumerate(report['optimization_recommendations'][:3], 1):
        print(f"\n{i}. [{rec['severity']}] {rec['category']}")
        print(f"   Issue: {rec['issue']}")
        print(f"   Recommendation: {rec['recommendation']}")
    
    print("\n" + "="*60)
    print("Analysis complete! Check ./performance_results/ for detailed reports.")
    print("="*60 + "\n")
    
    return report


if __name__ == "__main__":
    # Run the analysis
    asyncio.run(run_comprehensive_analysis())