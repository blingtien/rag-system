#!/usr/bin/env python3
"""
Cache Statistics Tracker for RAGAnything API Server
Tracks cache performance metrics and provides insights
"""

import time
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from pathlib import Path
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheHitMetrics:
    """Metrics for a single cache hit"""
    file_path: str
    file_size: int
    cache_key: str
    hit_time: float
    file_type: str
    parser_type: str
    time_saved_seconds: float = 0.0


@dataclass
class CacheMissMetrics:
    """Metrics for a single cache miss"""
    file_path: str
    file_size: int
    cache_key: str
    miss_time: float
    file_type: str
    parser_type: str
    processing_time_seconds: float = 0.0


@dataclass
class CacheStatistics:
    """Comprehensive cache statistics"""
    
    # Hit/Miss Counts
    total_hits: int = 0
    total_misses: int = 0
    
    # Performance Metrics
    total_time_saved_seconds: float = 0.0
    total_processing_time_seconds: float = 0.0
    average_cache_lookup_time: float = 0.0
    
    # File Type Statistics
    hits_by_file_type: Dict[str, int] = field(default_factory=dict)
    misses_by_file_type: Dict[str, int] = field(default_factory=dict)
    
    # Parser Statistics
    hits_by_parser: Dict[str, int] = field(default_factory=dict)
    misses_by_parser: Dict[str, int] = field(default_factory=dict)
    
    # Size Statistics
    total_cached_file_size: int = 0
    average_cached_file_size: float = 0.0
    
    # Temporal Statistics
    first_cache_access: Optional[float] = None
    last_cache_access: Optional[float] = None
    
    # Cache Efficiency
    cache_hit_ratio: float = 0.0
    efficiency_improvement: float = 0.0
    
    def update_ratios(self):
        """Update calculated ratios and metrics"""
        total_operations = self.total_hits + self.total_misses
        if total_operations > 0:
            self.cache_hit_ratio = self.total_hits / total_operations * 100
            
        if self.total_processing_time_seconds > 0:
            self.efficiency_improvement = (
                self.total_time_saved_seconds / 
                (self.total_processing_time_seconds + self.total_time_saved_seconds)
            ) * 100
            
        if self.total_hits > 0:
            self.average_cached_file_size = self.total_cached_file_size / self.total_hits


class CacheStatsTracker:
    """Advanced cache statistics tracker with performance analytics"""
    
    def __init__(self, storage_dir: str = None):
        self.storage_dir = storage_dir or os.getenv("WORKING_DIR", "./rag_storage")
        self.stats_file = os.path.join(self.storage_dir, "cache_statistics.json")
        
        # In-memory statistics
        self.statistics = CacheStatistics()
        self.recent_hits: List[CacheHitMetrics] = []
        self.recent_misses: List[CacheMissMetrics] = []
        self.max_recent_records = 1000
        
        # Tracking state
        self.session_start_time = time.time()
        self.is_enabled = True
        
        # Load existing statistics
        self._load_statistics()
        
        logger.info("Cache statistics tracker initialized")
    
    def _get_file_extension(self, file_path: str) -> str:
        """Extract file extension for categorization"""
        return Path(file_path).suffix.lower() or "no_extension"
    
    def _load_statistics(self):
        """Load statistics from persistent storage"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Load main statistics
                if "statistics" in data:
                    stats_data = data["statistics"]
                    self.statistics = CacheStatistics(
                        total_hits=stats_data.get("total_hits", 0),
                        total_misses=stats_data.get("total_misses", 0),
                        total_time_saved_seconds=stats_data.get("total_time_saved_seconds", 0.0),
                        total_processing_time_seconds=stats_data.get("total_processing_time_seconds", 0.0),
                        average_cache_lookup_time=stats_data.get("average_cache_lookup_time", 0.0),
                        hits_by_file_type=stats_data.get("hits_by_file_type", {}),
                        misses_by_file_type=stats_data.get("misses_by_file_type", {}),
                        hits_by_parser=stats_data.get("hits_by_parser", {}),
                        misses_by_parser=stats_data.get("misses_by_parser", {}),
                        total_cached_file_size=stats_data.get("total_cached_file_size", 0),
                        average_cached_file_size=stats_data.get("average_cached_file_size", 0.0),
                        first_cache_access=stats_data.get("first_cache_access"),
                        last_cache_access=stats_data.get("last_cache_access"),
                        cache_hit_ratio=stats_data.get("cache_hit_ratio", 0.0),
                        efficiency_improvement=stats_data.get("efficiency_improvement", 0.0),
                    )
                
                # Load recent records (limit to prevent memory issues)
                if "recent_hits" in data:
                    hits_data = data["recent_hits"][-self.max_recent_records:]
                    self.recent_hits = [
                        CacheHitMetrics(**hit) for hit in hits_data
                    ]
                
                if "recent_misses" in data:
                    misses_data = data["recent_misses"][-self.max_recent_records:]
                    self.recent_misses = [
                        CacheMissMetrics(**miss) for miss in misses_data
                    ]
                
                logger.info(f"Loaded cache statistics: {self.statistics.total_hits} hits, {self.statistics.total_misses} misses")
        
        except Exception as e:
            logger.warning(f"Could not load cache statistics: {e}")
            self.statistics = CacheStatistics()
    
    def _save_statistics(self):
        """Save statistics to persistent storage"""
        if not self.is_enabled:
            return
            
        try:
            os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)
            
            # Update calculated metrics before saving
            self.statistics.update_ratios()
            
            data = {
                "statistics": asdict(self.statistics),
                "recent_hits": [asdict(hit) for hit in self.recent_hits[-100:]],  # Save only last 100
                "recent_misses": [asdict(miss) for miss in self.recent_misses[-100:]],  # Save only last 100
                "session_info": {
                    "session_start_time": self.session_start_time,
                    "last_updated": time.time(),
                    "version": "1.0"
                }
            }
            
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Could not save cache statistics: {e}")
    
    def record_cache_hit(
        self, 
        file_path: str, 
        file_size: int, 
        cache_key: str,
        parser_type: str = "unknown",
        estimated_time_saved: float = 0.0
    ):
        """Record a cache hit with performance metrics"""
        if not self.is_enabled:
            return
            
        current_time = time.time()
        file_type = self._get_file_extension(file_path)
        
        # Create hit metrics
        hit_metrics = CacheHitMetrics(
            file_path=file_path,
            file_size=file_size,
            cache_key=cache_key[:16] + "..." if len(cache_key) > 16 else cache_key,
            hit_time=current_time,
            file_type=file_type,
            parser_type=parser_type,
            time_saved_seconds=estimated_time_saved
        )
        
        # Update statistics
        self.statistics.total_hits += 1
        self.statistics.total_time_saved_seconds += estimated_time_saved
        self.statistics.total_cached_file_size += file_size
        
        # Update file type stats
        self.statistics.hits_by_file_type[file_type] = (
            self.statistics.hits_by_file_type.get(file_type, 0) + 1
        )
        
        # Update parser stats
        self.statistics.hits_by_parser[parser_type] = (
            self.statistics.hits_by_parser.get(parser_type, 0) + 1
        )
        
        # Update temporal tracking
        if self.statistics.first_cache_access is None:
            self.statistics.first_cache_access = current_time
        self.statistics.last_cache_access = current_time
        
        # Add to recent hits (with size limit)
        self.recent_hits.append(hit_metrics)
        if len(self.recent_hits) > self.max_recent_records:
            self.recent_hits = self.recent_hits[-self.max_recent_records:]
        
        # Update ratios
        self.statistics.update_ratios()
        
        logger.info(
            f"Cache HIT: {Path(file_path).name} ({file_size/1024:.1f}KB) "
            f"saved ~{estimated_time_saved:.1f}s [Parser: {parser_type}]"
        )
        
        # Periodically save statistics
        if self.statistics.total_hits % 10 == 0:
            self._save_statistics()
    
    def record_cache_miss(
        self, 
        file_path: str, 
        file_size: int, 
        cache_key: str,
        parser_type: str = "unknown",
        processing_time: float = 0.0
    ):
        """Record a cache miss with performance metrics"""
        if not self.is_enabled:
            return
            
        current_time = time.time()
        file_type = self._get_file_extension(file_path)
        
        # Create miss metrics
        miss_metrics = CacheMissMetrics(
            file_path=file_path,
            file_size=file_size,
            cache_key=cache_key[:16] + "..." if len(cache_key) > 16 else cache_key,
            miss_time=current_time,
            file_type=file_type,
            parser_type=parser_type,
            processing_time_seconds=processing_time
        )
        
        # Update statistics
        self.statistics.total_misses += 1
        self.statistics.total_processing_time_seconds += processing_time
        
        # Update file type stats
        self.statistics.misses_by_file_type[file_type] = (
            self.statistics.misses_by_file_type.get(file_type, 0) + 1
        )
        
        # Update parser stats
        self.statistics.misses_by_parser[parser_type] = (
            self.statistics.misses_by_parser.get(parser_type, 0) + 1
        )
        
        # Update temporal tracking
        if self.statistics.first_cache_access is None:
            self.statistics.first_cache_access = current_time
        self.statistics.last_cache_access = current_time
        
        # Add to recent misses (with size limit)
        self.recent_misses.append(miss_metrics)
        if len(self.recent_misses) > self.max_recent_records:
            self.recent_misses = self.recent_misses[-self.max_recent_records:]
        
        # Update ratios
        self.statistics.update_ratios()
        
        logger.info(
            f"Cache MISS: {Path(file_path).name} ({file_size/1024:.1f}KB) "
            f"processed in {processing_time:.1f}s [Parser: {parser_type}]"
        )
        
        # Periodically save statistics
        if self.statistics.total_misses % 10 == 0:
            self._save_statistics()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        if not self.is_enabled:
            return {"enabled": False, "message": "Cache statistics tracking is disabled"}
        
        # Update ratios before returning
        self.statistics.update_ratios()
        
        # Calculate total operations
        total_operations = self.statistics.total_hits + self.statistics.total_misses
        
        # Calculate session statistics
        session_duration = time.time() - self.session_start_time
        session_hits = len([h for h in self.recent_hits if h.hit_time >= self.session_start_time])
        session_misses = len([m for m in self.recent_misses if m.miss_time >= self.session_start_time])
        
        # Get top file types
        all_file_types = set(
            list(self.statistics.hits_by_file_type.keys()) + 
            list(self.statistics.misses_by_file_type.keys())
        )
        
        file_type_stats = []
        for file_type in all_file_types:
            hits = self.statistics.hits_by_file_type.get(file_type, 0)
            misses = self.statistics.misses_by_file_type.get(file_type, 0)
            total = hits + misses
            hit_ratio = (hits / total * 100) if total > 0 else 0
            
            file_type_stats.append({
                "file_type": file_type,
                "hits": hits,
                "misses": misses,
                "total": total,
                "hit_ratio": round(hit_ratio, 1)
            })
        
        file_type_stats.sort(key=lambda x: x["total"], reverse=True)
        
        # Get parser statistics
        all_parsers = set(
            list(self.statistics.hits_by_parser.keys()) + 
            list(self.statistics.misses_by_parser.keys())
        )
        
        parser_stats = []
        for parser in all_parsers:
            hits = self.statistics.hits_by_parser.get(parser, 0)
            misses = self.statistics.misses_by_parser.get(parser, 0)
            total = hits + misses
            hit_ratio = (hits / total * 100) if total > 0 else 0
            
            parser_stats.append({
                "parser": parser,
                "hits": hits,
                "misses": misses,
                "total": total,
                "hit_ratio": round(hit_ratio, 1)
            })
        
        parser_stats.sort(key=lambda x: x["total"], reverse=True)
        
        return {
            "enabled": True,
            "overall_statistics": {
                "total_operations": total_operations,
                "cache_hits": self.statistics.total_hits,
                "cache_misses": self.statistics.total_misses,
                "hit_ratio_percent": round(self.statistics.cache_hit_ratio, 1),
                "total_time_saved_seconds": round(self.statistics.total_time_saved_seconds, 2),
                "total_processing_time_seconds": round(self.statistics.total_processing_time_seconds, 2),
                "efficiency_improvement_percent": round(self.statistics.efficiency_improvement, 1),
                "average_cached_file_size_kb": round(self.statistics.average_cached_file_size / 1024, 1) if self.statistics.average_cached_file_size else 0
            },
            "session_statistics": {
                "session_duration_seconds": round(session_duration, 1),
                "session_hits": session_hits,
                "session_misses": session_misses,
                "session_hit_ratio": round((session_hits / max(session_hits + session_misses, 1)) * 100, 1)
            },
            "file_type_breakdown": file_type_stats[:10],  # Top 10 file types
            "parser_breakdown": parser_stats,
            "recent_activity": {
                "recent_hits_count": len(self.recent_hits),
                "recent_misses_count": len(self.recent_misses),
                "last_cache_access": datetime.fromtimestamp(
                    self.statistics.last_cache_access
                ).isoformat() if self.statistics.last_cache_access else None
            },
            "cache_health": {
                "status": "excellent" if self.statistics.cache_hit_ratio >= 70 else
                         "good" if self.statistics.cache_hit_ratio >= 50 else 
                         "fair" if self.statistics.cache_hit_ratio >= 30 else "poor",
                "recommendations": self._get_cache_recommendations()
            }
        }
    
    def _get_cache_recommendations(self) -> List[str]:
        """Get recommendations for improving cache performance"""
        recommendations = []
        
        total_operations = self.statistics.total_hits + self.statistics.total_misses
        
        if self.statistics.cache_hit_ratio < 30:
            recommendations.append("Consider processing more similar files to improve cache efficiency")
        
        if total_operations < 10:
            recommendations.append("More operations needed for meaningful cache statistics")
        
        # Check for frequently missed file types
        for file_type, misses in self.statistics.misses_by_file_type.items():
            hits = self.statistics.hits_by_file_type.get(file_type, 0)
            if misses > hits * 2 and misses > 5:
                recommendations.append(f"Consider optimizing parsing for {file_type} files (high miss rate)")
        
        if self.statistics.efficiency_improvement < 20 and self.statistics.total_hits > 10:
            recommendations.append("Cache is working but with limited time savings - consider file deduplication")
        
        return recommendations
    
    def get_recent_activity(self, limit: int = 50) -> Dict[str, Any]:
        """Get recent cache activity"""
        recent_hits = [asdict(hit) for hit in self.recent_hits[-limit:]]
        recent_misses = [asdict(miss) for miss in self.recent_misses[-limit:]]
        
        # Convert timestamps to readable format
        for hit in recent_hits:
            hit["hit_time_readable"] = datetime.fromtimestamp(hit["hit_time"]).strftime("%Y-%m-%d %H:%M:%S")
            
        for miss in recent_misses:
            miss["miss_time_readable"] = datetime.fromtimestamp(miss["miss_time"]).strftime("%Y-%m-%d %H:%M:%S")
        
        return {
            "recent_hits": recent_hits,
            "recent_misses": recent_misses,
            "total_recent": len(recent_hits) + len(recent_misses)
        }
    
    def clear_statistics(self):
        """Clear all cache statistics"""
        logger.info("Clearing cache statistics")
        self.statistics = CacheStatistics()
        self.recent_hits.clear()
        self.recent_misses.clear()
        self.session_start_time = time.time()
        self._save_statistics()
    
    def enable_tracking(self):
        """Enable cache statistics tracking"""
        self.is_enabled = True
        logger.info("Cache statistics tracking enabled")
    
    def disable_tracking(self):
        """Disable cache statistics tracking"""
        self.is_enabled = False
        logger.info("Cache statistics tracking disabled")
    
    def finalize(self):
        """Save final statistics"""
        self._save_statistics()
        logger.info("Cache statistics tracker finalized")


# Global cache statistics tracker instance
cache_stats_tracker: Optional[CacheStatsTracker] = None


def get_cache_stats_tracker(storage_dir: str = None) -> CacheStatsTracker:
    """Get or create the global cache statistics tracker"""
    global cache_stats_tracker
    if cache_stats_tracker is None:
        cache_stats_tracker = CacheStatsTracker(storage_dir)
    return cache_stats_tracker


def initialize_cache_tracking(storage_dir: str = None):
    """Initialize cache statistics tracking"""
    global cache_stats_tracker
    cache_stats_tracker = CacheStatsTracker(storage_dir)
    return cache_stats_tracker