#!/usr/bin/env python3
"""
Cache-Enhanced Document Processor
Integrates cache statistics tracking with RAGAnything processing
"""

import os
import time
import hashlib
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Callable
import logging

from cache_statistics import get_cache_stats_tracker, CacheStatsTracker
from enhanced_error_handler import enhanced_error_handler, ErrorInfo, ErrorCategory
from advanced_progress_tracker import advanced_progress_tracker, ProcessingPhase, ProgressStatus

logger = logging.getLogger(__name__)


class CacheEnhancedProcessor:
    """
    Processor wrapper that adds intelligent caching metrics and management
    to RAGAnything processing operations
    """
    
    def __init__(self, rag_instance=None, storage_dir: str = None):
        self.rag_instance = rag_instance
        self.cache_tracker = get_cache_stats_tracker(storage_dir)
        
        # Cache configuration from environment
        self.cache_enabled = os.getenv("ENABLE_PARSE_CACHE", "true").lower() == "true"
        self.llm_cache_enabled = os.getenv("ENABLE_LLM_CACHE", "true").lower() == "true"
        self.cache_size_limit = int(os.getenv("CACHE_SIZE_LIMIT", "1000"))
        self.cache_ttl_hours = int(os.getenv("CACHE_TTL_HOURS", "24"))
        
        logger.info(f"Cache-enhanced processor initialized - Parse Cache: {self.cache_enabled}, LLM Cache: {self.llm_cache_enabled}")
    
    def _estimate_processing_time(self, file_path: str, file_size: int, parser_type: str) -> float:
        """
        Estimate processing time based on file size and type
        This helps calculate time savings from cache hits
        """
        # Base processing time estimates (in seconds)
        base_times = {
            ".pdf": 2.0,      # PDFs typically take longer
            ".docx": 1.5,     # Office docs moderate time
            ".doc": 2.0,      # Older office format
            ".txt": 0.3,      # Text files are fastest
            ".md": 0.3,       # Markdown files fast
            ".pptx": 3.0,     # Presentations can be complex
            ".ppt": 3.5,      # Older presentation format
            ".xlsx": 1.0,     # Spreadsheets moderate
            ".xls": 1.2,      # Older spreadsheet format
        }
        
        file_ext = Path(file_path).suffix.lower()
        base_time = base_times.get(file_ext, 1.0)  # Default 1 second
        
        # Scale by file size (MB)
        size_mb = file_size / (1024 * 1024)
        size_factor = 1.0 + (size_mb * 0.2)  # 20% more time per MB
        
        # Parser-specific adjustments
        parser_factors = {
            "mineru": 1.2,     # MinerU is more thorough
            "docling": 1.0,    # Docling baseline
            "direct_text": 0.1, # Direct processing is fastest
        }
        
        parser_factor = parser_factors.get(parser_type, 1.0)
        
        estimated_time = base_time * size_factor * parser_factor
        return max(0.1, estimated_time)  # Minimum 0.1 seconds
    
    def _get_parser_from_config(self, **kwargs) -> str:
        """Extract parser information from processing configuration"""
        # Try to get parser from various possible sources
        parser = kwargs.get("parser", self.rag_instance.config.parser if self.rag_instance else "unknown")
        
        # Check for direct processing indicators
        if kwargs.get("direct_processing"):
            return "direct_text"
        
        return parser
    
    async def process_document_with_cache_tracking(
        self, 
        file_path: str, 
        **kwargs
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Process document with comprehensive cache tracking
        
        Returns:
            Tuple of (processing_result, cache_metrics)
        """
        if not self.rag_instance:
            raise ValueError("RAGAnything instance not provided")
        
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = file_path_obj.stat().st_size
        parser_type = self._get_parser_from_config(**kwargs)
        
        # Generate cache key (similar to RAGAnything's method)
        cache_key = await self._generate_cache_key(file_path, **kwargs)
        
        # Estimate processing time for metrics
        estimated_processing_time = self._estimate_processing_time(file_path, file_size, parser_type)
        
        # Track processing start
        process_start_time = time.time()
        cache_metrics = {
            "cache_key": cache_key[:16] + "...",
            "file_size": file_size,
            "parser_type": parser_type,
            "estimated_processing_time": estimated_processing_time,
            "cache_hit": False,
            "processing_time": 0.0,
            "time_saved": 0.0
        }
        
        try:
            # Check if this would be a cache hit by trying the RAGAnything cache
            cached_result = None
            if self.cache_enabled and hasattr(self.rag_instance, '_get_cached_result'):
                try:
                    cached_result = await self.rag_instance._get_cached_result(
                        cache_key, file_path_obj, **kwargs
                    )
                except Exception as e:
                    logger.debug(f"Cache check failed: {e}")
                    cached_result = None
            
            if cached_result is not None:
                # Cache HIT
                cache_lookup_time = time.time() - process_start_time
                
                cache_metrics.update({
                    "cache_hit": True,
                    "processing_time": cache_lookup_time,
                    "time_saved": estimated_processing_time
                })
                
                # Record cache hit
                self.cache_tracker.record_cache_hit(
                    file_path=file_path,
                    file_size=file_size,
                    cache_key=cache_key,
                    parser_type=parser_type,
                    estimated_time_saved=estimated_processing_time
                )
                
                logger.info(f"⚡ CACHE HIT: {file_path_obj.name} - Saved ~{estimated_processing_time:.1f}s")
                
                return cached_result, cache_metrics
            
            else:
                # Cache MISS - Process the document
                logger.info(f"🔄 CACHE MISS: {file_path_obj.name} - Processing with {parser_type}")
                
                # Call the actual RAGAnything processing
                result = await self.rag_instance.process_document_complete(
                    file_path=file_path,
                    **kwargs
                )
                
                actual_processing_time = time.time() - process_start_time
                
                cache_metrics.update({
                    "cache_hit": False,
                    "processing_time": actual_processing_time,
                    "time_saved": 0.0
                })
                
                # Record cache miss
                self.cache_tracker.record_cache_miss(
                    file_path=file_path,
                    file_size=file_size,
                    cache_key=cache_key,
                    parser_type=parser_type,
                    processing_time=actual_processing_time
                )
                
                logger.info(f"✅ PROCESSING COMPLETE: {file_path_obj.name} - {actual_processing_time:.1f}s")
                
                return result, cache_metrics
                
        except Exception as e:
            # Record failed processing
            processing_time = time.time() - process_start_time
            cache_metrics.update({
                "cache_hit": False,
                "processing_time": processing_time,
                "error": str(e)
            })
            
            logger.error(f"❌ PROCESSING FAILED: {file_path_obj.name} - {str(e)}")
            raise
    
    async def _generate_cache_key(self, file_path: str, **kwargs) -> str:
        """
        Generate cache key similar to RAGAnything's method
        This ensures consistency with the actual cache system
        """
        file_path_obj = Path(file_path)
        
        try:
            file_stat = file_path_obj.stat()
            mtime = int(file_stat.st_mtime)
        except OSError:
            mtime = 0
        
        # Create configuration for cache key
        config = {
            "file_path": str(file_path_obj),
            "mtime": mtime,
            "parser": kwargs.get("parser", self.rag_instance.config.parser if self.rag_instance else "unknown"),
            "parse_method": kwargs.get("parse_method", "auto"),
            "device": kwargs.get("device", "cpu"),
            "lang": kwargs.get("lang", "en"),
        }
        
        # Add other relevant kwargs
        for key in ["formula", "table", "backend", "start_page", "end_page"]:
            if key in kwargs:
                config[key] = kwargs[key]
        
        # Generate hash
        import json
        config_str = json.dumps(config, sort_keys=True, ensure_ascii=False)
        cache_key = hashlib.md5(config_str.encode()).hexdigest()
        
        return cache_key
    
    async def batch_process_with_cache_tracking(
        self,
        file_paths: List[str],
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process multiple documents with comprehensive cache tracking
        
        Returns detailed cache performance metrics for the batch
        """
        batch_start_time = time.time()
        
        # Initialize batch metrics
        batch_metrics = {
            "total_files": len(file_paths),
            "cache_hits": 0,
            "cache_misses": 0,
            "total_time_saved": 0.0,
            "total_processing_time": 0.0,
            "files_processed": 0,
            "files_failed": 0,
            "cache_hit_ratio": 0.0,
            "efficiency_improvement": 0.0,
            "file_results": []
        }
        
        logger.info(f"🚀 Starting batch processing with cache tracking: {len(file_paths)} files")
        
        # Use RAGAnything's batch processing if available
        if hasattr(self.rag_instance, 'process_documents_with_rag_batch'):
            try:
                # Track cache states before batch processing
                initial_stats = self.cache_tracker.get_statistics()
                initial_hits = initial_stats.get("overall_statistics", {}).get("cache_hits", 0)
                initial_misses = initial_stats.get("overall_statistics", {}).get("cache_misses", 0)
                
                # Estimate time savings by checking cache for each file
                estimated_savings = 0.0
                for file_path in file_paths:
                    try:
                        file_size = Path(file_path).stat().st_size
                        parser_type = self._get_parser_from_config(**kwargs)
                        cache_key = await self._generate_cache_key(file_path, **kwargs)
                        
                        # Check if file would be a cache hit
                        if self.cache_enabled and hasattr(self.rag_instance, '_get_cached_result'):
                            try:
                                cached_result = await self.rag_instance._get_cached_result(
                                    cache_key, Path(file_path), **kwargs
                                )
                                if cached_result:
                                    estimated_time_saved = self._estimate_processing_time(
                                        file_path, file_size, parser_type
                                    )
                                    estimated_savings += estimated_time_saved
                                    
                                    # Pre-record the cache hit for accurate tracking
                                    self.cache_tracker.record_cache_hit(
                                        file_path=file_path,
                                        file_size=file_size,
                                        cache_key=cache_key,
                                        parser_type=parser_type,
                                        estimated_time_saved=estimated_time_saved
                                    )
                            except Exception:
                                pass  # Will be processed normally
                    except Exception:
                        continue  # Skip files that can't be analyzed
                
                # Process the batch using RAGAnything
                logger.info(f"📊 Estimated cache savings: {estimated_savings:.1f}s")
                batch_result = await self.rag_instance.process_documents_with_rag_batch(
                    file_paths=file_paths,
                    **kwargs
                )
                
                # Calculate final cache metrics
                final_stats = self.cache_tracker.get_statistics()
                final_hits = final_stats.get("overall_statistics", {}).get("cache_hits", 0)
                final_misses = final_stats.get("overall_statistics", {}).get("cache_misses", 0)
                
                batch_cache_hits = final_hits - initial_hits
                batch_cache_misses = final_misses - initial_misses
                
                batch_processing_time = time.time() - batch_start_time
                
                # Update batch metrics
                batch_metrics.update({
                    "cache_hits": batch_cache_hits,
                    "cache_misses": batch_cache_misses,
                    "total_time_saved": estimated_savings,
                    "total_processing_time": batch_processing_time,
                    "files_processed": batch_result.get("successful_rag_files", 0),
                    "files_failed": len(file_paths) - batch_result.get("successful_rag_files", 0),
                    "cache_hit_ratio": (batch_cache_hits / max(batch_cache_hits + batch_cache_misses, 1)) * 100,
                    "efficiency_improvement": (estimated_savings / max(batch_processing_time + estimated_savings, 1)) * 100
                })
                
                # Create detailed results
                for file_path in file_paths:
                    file_result = batch_result.get("rag_results", {}).get(file_path, {})
                    processed = file_result.get("processed", False)
                    error = file_result.get("error", None)
                    
                    batch_metrics["file_results"].append({
                        "file_path": file_path,
                        "file_name": Path(file_path).name,
                        "file_size": Path(file_path).stat().st_size if Path(file_path).exists() else 0,
                        "processed": processed,
                        "error": error,
                        "cache_estimated": file_path in [p for p in file_paths if Path(p).exists()]  # Simplified
                    })
                
                # Enhance batch result with cache metrics
                batch_result["cache_metrics"] = batch_metrics
                
                logger.info(
                    f"🎉 Batch processing complete: "
                    f"{batch_cache_hits} cache hits, {batch_cache_misses} misses, "
                    f"{estimated_savings:.1f}s saved"
                )
                
                return batch_result
                
            except Exception as e:
                logger.error(f"Batch processing with cache tracking failed: {e}")
                raise
        else:
            # Fallback to individual processing
            logger.warning("Batch processing not available, using individual processing")
            batch_result = {
                "successful_rag_files": 0,
                "rag_results": {},
                "cache_metrics": batch_metrics
            }
            
            for file_path in file_paths:
                try:
                    result, file_cache_metrics = await self.process_document_with_cache_tracking(
                        file_path, **kwargs
                    )
                    
                    batch_metrics["files_processed"] += 1
                    if file_cache_metrics["cache_hit"]:
                        batch_metrics["cache_hits"] += 1
                        batch_metrics["total_time_saved"] += file_cache_metrics["time_saved"]
                    else:
                        batch_metrics["cache_misses"] += 1
                    
                    batch_metrics["total_processing_time"] += file_cache_metrics["processing_time"]
                    
                    batch_result["rag_results"][file_path] = {"processed": True}
                    batch_result["successful_rag_files"] += 1
                    
                except Exception as e:
                    batch_metrics["files_failed"] += 1
                    batch_result["rag_results"][file_path] = {
                        "processed": False, 
                        "error": str(e)
                    }
            
            # Update final metrics
            total_operations = batch_metrics["cache_hits"] + batch_metrics["cache_misses"]
            if total_operations > 0:
                batch_metrics["cache_hit_ratio"] = (batch_metrics["cache_hits"] / total_operations) * 100
            
            total_time = batch_metrics["total_processing_time"] + batch_metrics["total_time_saved"]
            if total_time > 0:
                batch_metrics["efficiency_improvement"] = (batch_metrics["total_time_saved"] / total_time) * 100
            
            batch_result["cache_metrics"] = batch_metrics
            
            return batch_result
    
    async def _process_with_enhanced_error_handling(
        self,
        file_paths: List[str],
        batch_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process files with enhanced error handling and progress reporting
        """
        try:
            # Call RAGAnything batch processing
            batch_result = await self.rag_instance.process_documents_with_rag_batch(
                file_paths=file_paths,
                **kwargs
            )
            
            # Update progress to RAG integration
            await advanced_progress_tracker.update_batch_phase(batch_id, ProcessingPhase.RAG_INTEGRATION)
            
            return batch_result
            
        except Exception as e:
            # Categorize and handle the error
            error_info = enhanced_error_handler.categorize_error(e, {
                "batch_id": batch_id,
                "file_count": len(file_paths),
                "operation": "rag_batch_processing"
            })
            
            logger.error(f"RAG batch processing failed: {error_info.user_message}")
            
            # Mark all files as failed with specific error
            for file_path in file_paths:
                await advanced_progress_tracker.update_file_progress(
                    batch_id, file_path, ProgressStatus.FAILED,
                    error_message=error_info.user_message
                )
            
            # Return failed batch result
            return {
                "successful_rag_files": 0,
                "rag_results": {file_path: {"processed": False, "error": error_info.user_message} 
                              for file_path in file_paths},
                "error": error_info.user_message,
                "error_category": error_info.category.value
            }
    
    async def _update_file_results(self, batch_id: str, batch_result: Dict[str, Any], file_paths: List[str]):
        """
        Update individual file progress based on batch results
        """
        rag_results = batch_result.get("rag_results", {})
        
        for file_path in file_paths:
            file_result = rag_results.get(file_path, {})
            processed = file_result.get("processed", False)
            error = file_result.get("error")
            
            if processed:
                await advanced_progress_tracker.update_file_progress(
                    batch_id, file_path, ProgressStatus.COMPLETED,
                    progress_percent=100.0
                )
            else:
                await advanced_progress_tracker.update_file_progress(
                    batch_id, file_path, ProgressStatus.FAILED,
                    progress_percent=0.0,
                    error_message=error or "处理失败"
                )
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        return self.cache_tracker.get_statistics()
    
    def get_cache_activity(self, limit: int = 50) -> Dict[str, Any]:
        """Get recent cache activity"""
        return self.cache_tracker.get_recent_activity(limit)
    
    def clear_cache_statistics(self):
        """Clear cache statistics"""
        self.cache_tracker.clear_statistics()
    
    def is_cache_enabled(self) -> Dict[str, bool]:
        """Check cache enablement status"""
        return {
            "parse_cache_enabled": self.cache_enabled,
            "llm_cache_enabled": self.llm_cache_enabled,
            "statistics_tracking_enabled": self.cache_tracker.is_enabled
        }