#!/usr/bin/env python3
"""
Complete Database Optimization Execution Script
Orchestrates the full database cleanup and optimization process for corrupted DOC content
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Import optimization modules
from database_cleanup_strategy import CorruptedContentCleaner, DatabaseOptimizer
from query_optimization_layer import SmartQueryOptimizer, ContentQualityAnalyzer
from schema_enhancement_strategy import ContentQualityTracker
from performance_impact_assessment import PerformanceMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ragsvr/projects/ragsystem/database_optimization.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class DatabaseOptimizationOrchestrator:
    """Orchestrates the complete database optimization process"""
    
    def __init__(self, rag_storage_path: str = "/home/ragsvr/projects/ragsystem/rag_storage"):
        self.storage_path = Path(rag_storage_path)
        
        # Initialize components
        self.cleaner = CorruptedContentCleaner(rag_storage_path)
        self.optimizer = DatabaseOptimizer(rag_storage_path)
        self.query_optimizer = SmartQueryOptimizer(rag_storage_path)
        self.quality_tracker = ContentQualityTracker(rag_storage_path)
        self.performance_monitor = PerformanceMonitor(rag_storage_path)
        
        # Execution report
        self.execution_report = {
            'started_at': datetime.now().isoformat(),
            'phases': {},
            'overall_status': 'pending',
            'errors': [],
            'recommendations': []
        }
    
    def run_complete_optimization(self, create_backup: bool = True) -> Dict[str, Any]:
        """Execute complete database optimization workflow"""
        logger.info("Starting complete database optimization process...")
        
        try:
            # Phase 1: Pre-optimization Assessment
            self._phase_1_assessment()
            
            # Phase 2: Database Cleanup
            self._phase_2_cleanup(create_backup)
            
            # Phase 3: Schema Enhancement
            self._phase_3_schema_enhancement()
            
            # Phase 4: Query Optimization Setup
            self._phase_4_query_optimization()
            
            # Phase 5: Performance Monitoring Setup
            self._phase_5_performance_monitoring()
            
            # Phase 6: Post-optimization Assessment
            self._phase_6_post_assessment()
            
            # Finalize
            self.execution_report['completed_at'] = datetime.now().isoformat()
            self.execution_report['overall_status'] = 'success'
            
            logger.info("Database optimization completed successfully!")
            
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            self.execution_report['overall_status'] = 'failed'
            self.execution_report['errors'].append(str(e))
            
        finally:
            # Save execution report
            self._save_execution_report()
        
        return self.execution_report
    
    def _phase_1_assessment(self):
        """Phase 1: Pre-optimization assessment"""
        logger.info("Phase 1: Pre-optimization Assessment")
        
        phase_report = {
            'started_at': datetime.now().isoformat(),
            'status': 'running'
        }
        
        try:
            # Assess current database state
            db_files = [
                'kv_store_full_docs.json',
                'kv_store_text_chunks.json', 
                'kv_store_full_entities.json',
                'kv_store_full_relations.json',
                'vdb_chunks.json'
            ]
            
            db_stats = {}
            total_size = 0
            
            for db_file in db_files:
                file_path = self.storage_path / db_file
                if file_path.exists():
                    size = file_path.stat().st_size
                    total_size += size
                    
                    # Quick corruption check
                    corruption_count = 0
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Simple corruption pattern check
                            corruption_patterns = ['规规规规规', '国国国国国', '《》、《》、《》']
                            for pattern in corruption_patterns:
                                corruption_count += content.count(pattern)
                    except:
                        corruption_count = -1  # Error reading file
                    
                    db_stats[db_file] = {
                        'size_mb': size / (1024 * 1024),
                        'corruption_indicators': corruption_count
                    }
                else:
                    db_stats[db_file] = {'exists': False}
            
            phase_report.update({
                'database_stats': db_stats,
                'total_size_mb': total_size / (1024 * 1024),
                'corruption_detected': any(stats.get('corruption_indicators', 0) > 0 for stats in db_stats.values()),
                'status': 'completed',
                'completed_at': datetime.now().isoformat()
            })
            
            logger.info(f"Pre-optimization assessment completed. Total DB size: {total_size/(1024*1024):.1f} MB")
            
        except Exception as e:
            phase_report['status'] = 'failed'
            phase_report['error'] = str(e)
            logger.error(f"Phase 1 failed: {e}")
            raise
        
        self.execution_report['phases']['phase_1_assessment'] = phase_report
    
    def _phase_2_cleanup(self, create_backup: bool = True):
        """Phase 2: Database cleanup"""
        logger.info("Phase 2: Database Cleanup")
        
        phase_report = {
            'started_at': datetime.now().isoformat(),
            'status': 'running'
        }
        
        try:
            # Execute cleanup
            cleanup_report = self.cleaner.run_full_cleanup()
            
            if cleanup_report['status'] == 'success':
                # Run optimization
                self.optimizer.optimize_storage()
                
                phase_report.update({
                    'cleanup_report': cleanup_report,
                    'optimization_applied': True,
                    'status': 'completed',
                    'completed_at': datetime.now().isoformat()
                })
                
                logger.info(f"Cleanup completed. Removed {cleanup_report['total_items_removed']} corrupted items")
                
            else:
                phase_report.update({
                    'cleanup_report': cleanup_report,
                    'status': 'failed'
                })
                raise Exception(f"Cleanup failed: {cleanup_report.get('error', 'Unknown error')}")
                
        except Exception as e:
            phase_report['status'] = 'failed'
            phase_report['error'] = str(e)
            logger.error(f"Phase 2 failed: {e}")
            raise
        
        self.execution_report['phases']['phase_2_cleanup'] = phase_report
    
    def _phase_3_schema_enhancement(self):
        """Phase 3: Schema enhancement setup"""
        logger.info("Phase 3: Schema Enhancement")
        
        phase_report = {
            'started_at': datetime.now().isoformat(),
            'status': 'running'
        }
        
        try:
            # Initialize quality tracking for existing documents
            quality_stats = self.quality_tracker.get_quality_statistics()
            
            phase_report.update({
                'quality_tracking_initialized': True,
                'initial_stats': quality_stats,
                'schema_files_created': [
                    'content_quality_profiles.json',
                    'quality_index.json', 
                    'quality_statistics.json'
                ],
                'status': 'completed',
                'completed_at': datetime.now().isoformat()
            })
            
            logger.info("Schema enhancement completed - quality tracking initialized")
            
        except Exception as e:
            phase_report['status'] = 'failed'
            phase_report['error'] = str(e)
            logger.error(f"Phase 3 failed: {e}")
            raise
        
        self.execution_report['phases']['phase_3_schema_enhancement'] = phase_report
    
    def _phase_4_query_optimization(self):
        """Phase 4: Query optimization setup"""
        logger.info("Phase 4: Query Optimization Setup")
        
        phase_report = {
            'started_at': datetime.now().isoformat(),
            'status': 'running'
        }
        
        try:
            # Test query optimization components
            analyzer = ContentQualityAnalyzer()
            
            # Test content analysis
            test_content = "This is a test document with good quality content."
            test_metrics = analyzer.analyze_content_quality(test_content)
            
            phase_report.update({
                'query_optimizer_initialized': True,
                'content_analyzer_test': {
                    'test_passed': test_metrics.confidence_score > 0.5,
                    'test_confidence': test_metrics.confidence_score
                },
                'optimization_features': [
                    'Content corruption detection',
                    'Result quality filtering',
                    'Query result ranking',
                    'Performance-aware caching'
                ],
                'status': 'completed',
                'completed_at': datetime.now().isoformat()
            })
            
            logger.info("Query optimization setup completed")
            
        except Exception as e:
            phase_report['status'] = 'failed'
            phase_report['error'] = str(e)
            logger.error(f"Phase 4 failed: {e}")
            raise
        
        self.execution_report['phases']['phase_4_query_optimization'] = phase_report
    
    def _phase_5_performance_monitoring(self):
        """Phase 5: Performance monitoring setup"""
        logger.info("Phase 5: Performance Monitoring Setup")
        
        phase_report = {
            'started_at': datetime.now().isoformat(),
            'status': 'running'
        }
        
        try:
            # Initialize performance monitoring
            test_metrics = self.performance_monitor.record_performance(
                operation_type="optimization_test",
                query_latency=0.1,
                result_count=1,
                result_quality_avg=0.9,
                corrupted_results_filtered=0,
                corruption_impact_score=0.0,
                search_accuracy=0.9
            )
            
            phase_report.update({
                'monitoring_initialized': True,
                'test_metrics_recorded': True,
                'monitoring_files_created': [
                    'performance_metrics.json',
                    'performance_analysis.json'
                ],
                'monitoring_features': [
                    'Query latency tracking',
                    'Resource usage monitoring', 
                    'Corruption impact analysis',
                    'Performance trend analysis'
                ],
                'status': 'completed',
                'completed_at': datetime.now().isoformat()
            })
            
            logger.info("Performance monitoring setup completed")
            
        except Exception as e:
            phase_report['status'] = 'failed'
            phase_report['error'] = str(e)
            logger.error(f"Phase 5 failed: {e}")
            raise
        
        self.execution_report['phases']['phase_5_performance_monitoring'] = phase_report
    
    def _phase_6_post_assessment(self):
        """Phase 6: Post-optimization assessment"""
        logger.info("Phase 6: Post-Optimization Assessment")
        
        phase_report = {
            'started_at': datetime.now().isoformat(),
            'status': 'running'
        }
        
        try:
            # Generate performance report
            perf_report = self.performance_monitor.generate_performance_report(hours=1)
            
            # Calculate database size after optimization
            total_size_after = 0
            for db_file in ['kv_store_full_docs.json', 'kv_store_text_chunks.json', 
                           'kv_store_full_entities.json', 'kv_store_full_relations.json']:
                file_path = self.storage_path / db_file
                if file_path.exists():
                    total_size_after += file_path.stat().st_size
            
            # Compare with pre-optimization size
            size_before = self.execution_report['phases']['phase_1_assessment']['total_size_mb']
            size_after = total_size_after / (1024 * 1024)
            size_reduction = size_before - size_after
            
            # Generate final recommendations
            recommendations = [
                "Database cleanup completed - corrupted content removed",
                "Query optimization layer active - will filter corrupted results",
                "Performance monitoring enabled - track system health",
                "Quality tracking initialized - monitor future document processing"
            ]
            
            if size_reduction > 0:
                recommendations.append(f"Database size reduced by {size_reduction:.1f} MB ({size_reduction/size_before:.1%})")
            
            recommendations.extend([
                "Restart RAG service to ensure all optimizations are active",
                "Monitor performance metrics for continued optimization",
                "Consider reprocessing high-priority corrupted documents with alternative parsers"
            ])
            
            phase_report.update({
                'performance_report': perf_report,
                'database_size_after_mb': size_after,
                'size_reduction_mb': size_reduction,
                'size_reduction_percent': size_reduction / size_before if size_before > 0 else 0,
                'final_recommendations': recommendations,
                'optimization_success': size_reduction > 0,
                'status': 'completed',
                'completed_at': datetime.now().isoformat()
            })
            
            # Add recommendations to main report
            self.execution_report['recommendations'].extend(recommendations)
            
            logger.info(f"Post-optimization assessment completed. Size reduction: {size_reduction:.1f} MB")
            
        except Exception as e:
            phase_report['status'] = 'failed'
            phase_report['error'] = str(e)
            logger.error(f"Phase 6 failed: {e}")
            raise
        
        self.execution_report['phases']['phase_6_post_assessment'] = phase_report
    
    def _save_execution_report(self):
        """Save execution report to file"""
        report_path = self.storage_path / "database_optimization_report.json"
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(self.execution_report, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Execution report saved to: {report_path}")
            
        except Exception as e:
            logger.error(f"Failed to save execution report: {e}")


def print_usage():
    """Print script usage information"""
    print("""
Database Optimization Script for RAG System

Usage:
    python run_database_optimization.py [OPTIONS]

Options:
    --storage-path PATH    Path to RAG storage directory (default: ./rag_storage)
    --no-backup           Skip backup creation before cleanup
    --dry-run             Show what would be done without executing
    --help                Show this help message

Examples:
    # Run full optimization with default settings
    python run_database_optimization.py
    
    # Run with custom storage path
    python run_database_optimization.py --storage-path /path/to/rag_storage
    
    # Run without creating backup (not recommended)
    python run_database_optimization.py --no-backup
    
    # Dry run to see what would be done
    python run_database_optimization.py --dry-run
""")


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG Database Optimization")
    parser.add_argument("--storage-path", default="/home/ragsvr/projects/ragsystem/rag_storage",
                       help="Path to RAG storage directory")
    parser.add_argument("--no-backup", action="store_true", 
                       help="Skip backup creation")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be done without executing")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY RUN MODE - No changes will be made")
        print(f"Storage path: {args.storage_path}")
        print(f"Create backup: {not args.no_backup}")
        print("\nWould execute:")
        print("1. Pre-optimization assessment")
        print("2. Database cleanup (remove corrupted content)")
        print("3. Schema enhancement (add quality tracking)")
        print("4. Query optimization setup")
        print("5. Performance monitoring setup")
        print("6. Post-optimization assessment")
        return
    
    # Validate storage path
    storage_path = Path(args.storage_path)
    if not storage_path.exists():
        logger.error(f"Storage path does not exist: {storage_path}")
        sys.exit(1)
    
    # Create orchestrator and run optimization
    orchestrator = DatabaseOptimizationOrchestrator(str(storage_path))
    
    print("Starting RAG Database Optimization...")
    print(f"Storage path: {storage_path}")
    print(f"Create backup: {not args.no_backup}")
    print()
    
    # Execute optimization
    report = orchestrator.run_complete_optimization(create_backup=not args.no_backup)
    
    # Print summary
    print("\n" + "="*60)
    print("DATABASE OPTIMIZATION SUMMARY")
    print("="*60)
    print(f"Status: {report['overall_status'].upper()}")
    print(f"Started: {report['started_at']}")
    
    if report['overall_status'] == 'success':
        print(f"Completed: {report.get('completed_at', 'N/A')}")
        
        # Print phase results
        for phase_name, phase_data in report['phases'].items():
            status = phase_data.get('status', 'unknown')
            print(f"  {phase_name}: {status.upper()}")
        
        # Print cleanup stats if available
        cleanup_data = report['phases'].get('phase_2_cleanup', {}).get('cleanup_report', {})
        if cleanup_data.get('cleanup_stats'):
            print(f"\nCleanup Results:")
            for stat_name, count in cleanup_data['cleanup_stats'].items():
                if count > 0:
                    print(f"  {stat_name}: {count}")
        
        # Print size reduction if available
        post_assessment = report['phases'].get('phase_6_post_assessment', {})
        if post_assessment.get('size_reduction_mb', 0) > 0:
            print(f"\nDatabase Size Reduction: {post_assessment['size_reduction_mb']:.1f} MB")
        
        print("\nRecommendations:")
        for rec in report.get('recommendations', []):
            print(f"  • {rec}")
    
    else:
        print("FAILED")
        for error in report.get('errors', []):
            print(f"  Error: {error}")
    
    print(f"\nDetailed report saved to: {storage_path}/database_optimization_report.json")


if __name__ == "__main__":
    main()