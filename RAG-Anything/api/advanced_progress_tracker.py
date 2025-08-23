#!/usr/bin/env python3
"""
Advanced Progress Tracker for RAG-Anything Batch Processing
Provides real-time progress updates, ETA calculations, and detailed progress reporting
"""

import os
import time
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ProcessingPhase(Enum):
    """Processing phases for batch operations"""
    INITIALIZATION = "initialization"
    VALIDATION = "validation"
    CACHE_CHECKING = "cache_checking"
    DOCUMENT_PARSING = "document_parsing"
    RAG_INTEGRATION = "rag_integration"
    COMPLETION = "completion"


class ProgressStatus(Enum):
    """Progress status for individual items"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CACHED = "cached"


@dataclass
class FileProgressInfo:
    """Progress information for individual files"""
    file_path: str
    file_name: str
    file_size: int
    status: ProgressStatus = ProgressStatus.PENDING
    phase: Optional[ProcessingPhase] = None
    progress_percent: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time: float = 0.0
    estimated_time: float = 0.0
    cache_hit: bool = False
    error_message: Optional[str] = None
    retry_count: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.file_path, str):
            self.file_name = Path(self.file_path).name


@dataclass
class BatchProgressInfo:
    """Progress information for batch operations"""
    batch_id: str
    operation_type: str
    total_files: int
    current_phase: ProcessingPhase = ProcessingPhase.INITIALIZATION
    overall_progress: float = 0.0
    started_at: datetime = field(default_factory=datetime.now)
    estimated_completion: Optional[datetime] = None
    files_completed: int = 0
    files_failed: int = 0
    files_cached: int = 0
    files_retrying: int = 0
    cache_hit_ratio: float = 0.0
    average_processing_time: float = 0.0
    throughput_files_per_minute: float = 0.0
    time_saved_from_cache: float = 0.0
    system_metrics: Dict[str, Any] = field(default_factory=dict)
    phase_timings: Dict[str, float] = field(default_factory=dict)
    file_progress: Dict[str, FileProgressInfo] = field(default_factory=dict)


class AdvancedProgressTracker:
    """
    Advanced progress tracker with real-time updates, ETA calculations, and WebSocket integration
    """
    
    def __init__(self):
        self.active_batches: Dict[str, BatchProgressInfo] = {}
        self.websocket_callbacks: List[Callable] = []
        self.progress_history: List[Dict[str, Any]] = []
        self.performance_baselines = self._load_performance_baselines()
        
    def _load_performance_baselines(self) -> Dict[str, Dict[str, float]]:
        """Load performance baselines for ETA calculations"""
        # Default baselines (processing time per MB by file type)
        baselines = {
            ".pdf": {"time_per_mb": 3.0, "variance": 1.5},
            ".docx": {"time_per_mb": 2.0, "variance": 1.0},
            ".doc": {"time_per_mb": 2.5, "variance": 1.2},
            ".txt": {"time_per_mb": 0.5, "variance": 0.2},
            ".md": {"time_per_mb": 0.5, "variance": 0.2},
            ".pptx": {"time_per_mb": 4.0, "variance": 2.0},
            ".ppt": {"time_per_mb": 4.5, "variance": 2.2},
            ".xlsx": {"time_per_mb": 1.5, "variance": 0.8},
            ".xls": {"time_per_mb": 2.0, "variance": 1.0},
        }
        
        # Try to load historical data if available
        try:
            baseline_file = os.path.join(os.getenv("WORKING_DIR", "/tmp"), "performance_baselines.json")
            if os.path.exists(baseline_file):
                with open(baseline_file, 'r') as f:
                    saved_baselines = json.load(f)
                    baselines.update(saved_baselines)
                    logger.info(f"Loaded performance baselines from {baseline_file}")
        except Exception as e:
            logger.warning(f"Failed to load performance baselines: {e}")
        
        return baselines
    
    def register_websocket_callback(self, callback: Callable):
        """Register a WebSocket callback for real-time updates"""
        self.websocket_callbacks.append(callback)
    
    def unregister_websocket_callback(self, callback: Callable):
        """Unregister a WebSocket callback"""
        if callback in self.websocket_callbacks:
            self.websocket_callbacks.remove(callback)
    
    async def create_batch_progress(
        self,
        batch_id: str,
        operation_type: str,
        file_paths: List[str]
    ) -> BatchProgressInfo:
        """Create a new batch progress tracker"""
        
        # Initialize file progress info
        file_progress = {}
        for file_path in file_paths:
            try:
                file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
                estimated_time = self._estimate_processing_time(file_path, file_size)
                
                file_progress[file_path] = FileProgressInfo(
                    file_path=file_path,
                    file_name=Path(file_path).name,
                    file_size=file_size,
                    estimated_time=estimated_time
                )
            except Exception as e:
                logger.warning(f"Failed to initialize progress for {file_path}: {e}")
                file_progress[file_path] = FileProgressInfo(
                    file_path=file_path,
                    file_name=Path(file_path).name,
                    file_size=0,
                    estimated_time=10.0  # Default estimate
                )
        
        # Create batch progress info
        batch_progress = BatchProgressInfo(
            batch_id=batch_id,
            operation_type=operation_type,
            total_files=len(file_paths),
            file_progress=file_progress
        )
        
        # Calculate initial ETA
        total_estimated_time = sum(fp.estimated_time for fp in file_progress.values())
        batch_progress.estimated_completion = datetime.now() + timedelta(seconds=total_estimated_time)
        
        self.active_batches[batch_id] = batch_progress
        
        # Send initial progress update
        await self._broadcast_progress_update(batch_id)
        
        return batch_progress
    
    def _estimate_processing_time(self, file_path: str, file_size: int) -> float:
        """Estimate processing time based on file type and size"""
        file_ext = Path(file_path).suffix.lower()
        baseline = self.performance_baselines.get(file_ext, {"time_per_mb": 2.0, "variance": 1.0})
        
        size_mb = max(file_size / (1024 * 1024), 0.1)  # Minimum 0.1 MB
        base_time = baseline["time_per_mb"] * size_mb
        
        # Add some variance based on system load and file type
        variance_factor = 1.0 + (baseline["variance"] * 0.3)
        estimated_time = base_time * variance_factor
        
        return max(estimated_time, 1.0)  # Minimum 1 second
    
    async def update_batch_phase(self, batch_id: str, phase: ProcessingPhase):
        """Update the current processing phase for a batch"""
        if batch_id not in self.active_batches:
            return
        
        batch = self.active_batches[batch_id]
        previous_phase = batch.current_phase
        batch.current_phase = phase
        
        # Record phase timing
        now = time.time()
        if previous_phase.value not in batch.phase_timings:
            batch.phase_timings[previous_phase.value] = now - batch.started_at.timestamp()
        
        # Update overall progress based on phase
        phase_progress_mapping = {
            ProcessingPhase.INITIALIZATION: 5.0,
            ProcessingPhase.VALIDATION: 10.0,
            ProcessingPhase.CACHE_CHECKING: 15.0,
            ProcessingPhase.DOCUMENT_PARSING: 30.0,  # Will be updated based on file progress
            ProcessingPhase.RAG_INTEGRATION: 80.0,   # Will be updated based on file progress
            ProcessingPhase.COMPLETION: 100.0
        }
        
        if phase != ProcessingPhase.DOCUMENT_PARSING and phase != ProcessingPhase.RAG_INTEGRATION:
            batch.overall_progress = max(batch.overall_progress, phase_progress_mapping.get(phase, batch.overall_progress))
        
        # Recalculate ETA
        await self._update_batch_eta(batch_id)
        await self._broadcast_progress_update(batch_id)
    
    async def update_file_progress(
        self,
        batch_id: str,
        file_path: str,
        status: ProgressStatus,
        progress_percent: float = 0.0,
        phase: Optional[ProcessingPhase] = None,
        error_message: Optional[str] = None,
        cache_hit: bool = False
    ):
        """Update progress for an individual file"""
        if batch_id not in self.active_batches:
            return
        
        batch = self.active_batches[batch_id]
        if file_path not in batch.file_progress:
            return
        
        file_info = batch.file_progress[file_path]
        previous_status = file_info.status
        
        # Update file information
        file_info.status = status
        file_info.progress_percent = progress_percent
        if phase:
            file_info.phase = phase
        if error_message:
            file_info.error_message = error_message
        if cache_hit:
            file_info.cache_hit = cache_hit
        
        # Update timing information
        now = datetime.now()
        if status == ProgressStatus.IN_PROGRESS and not file_info.started_at:
            file_info.started_at = now
        elif status in [ProgressStatus.COMPLETED, ProgressStatus.FAILED, ProgressStatus.CACHED]:
            if not file_info.completed_at:
                file_info.completed_at = now
            if file_info.started_at:
                file_info.processing_time = (now - file_info.started_at).total_seconds()
        elif status == ProgressStatus.RETRYING:
            file_info.retry_count += 1
        
        # Update batch counters
        await self._update_batch_counters(batch_id)
        await self._update_batch_eta(batch_id)
        await self._broadcast_progress_update(batch_id)
    
    async def _update_batch_counters(self, batch_id: str):
        """Update batch-level counters based on file statuses"""
        batch = self.active_batches[batch_id]
        
        # Count files by status
        completed = sum(1 for f in batch.file_progress.values() if f.status == ProgressStatus.COMPLETED)
        failed = sum(1 for f in batch.file_progress.values() if f.status == ProgressStatus.FAILED)
        cached = sum(1 for f in batch.file_progress.values() if f.cache_hit)
        retrying = sum(1 for f in batch.file_progress.values() if f.status == ProgressStatus.RETRYING)
        
        batch.files_completed = completed
        batch.files_failed = failed
        batch.files_cached = cached
        batch.files_retrying = retrying
        
        # Calculate cache hit ratio
        total_processed = completed + failed + cached
        if total_processed > 0:
            batch.cache_hit_ratio = (cached / total_processed) * 100
        
        # Calculate average processing time
        processing_times = [f.processing_time for f in batch.file_progress.values() 
                          if f.processing_time > 0 and not f.cache_hit]
        if processing_times:
            batch.average_processing_time = sum(processing_times) / len(processing_times)
        
        # Calculate throughput
        elapsed_time = (datetime.now() - batch.started_at).total_seconds()
        if elapsed_time > 0:
            batch.throughput_files_per_minute = (total_processed / elapsed_time) * 60
        
        # Calculate time saved from cache
        cache_time_savings = sum(f.estimated_time for f in batch.file_progress.values() if f.cache_hit)
        batch.time_saved_from_cache = cache_time_savings
        
        # Update overall progress for processing phases
        if batch.current_phase in [ProcessingPhase.DOCUMENT_PARSING, ProcessingPhase.RAG_INTEGRATION]:
            if batch.total_files > 0:
                file_progress_sum = sum(f.progress_percent for f in batch.file_progress.values())
                average_file_progress = file_progress_sum / batch.total_files
                
                if batch.current_phase == ProcessingPhase.DOCUMENT_PARSING:
                    batch.overall_progress = 15.0 + (average_file_progress * 0.35)  # 15% to 50%
                elif batch.current_phase == ProcessingPhase.RAG_INTEGRATION:
                    batch.overall_progress = 50.0 + (average_file_progress * 0.30)  # 50% to 80%
    
    async def _update_batch_eta(self, batch_id: str):
        """Update estimated completion time for a batch"""
        batch = self.active_batches[batch_id]
        
        # Count remaining files
        remaining_files = [f for f in batch.file_progress.values() 
                          if f.status in [ProgressStatus.PENDING, ProgressStatus.IN_PROGRESS, ProgressStatus.RETRYING]]
        
        if not remaining_files:
            batch.estimated_completion = datetime.now()
            return
        
        # Estimate remaining time
        if batch.average_processing_time > 0:
            # Use actual average processing time
            remaining_time = len(remaining_files) * batch.average_processing_time
        else:
            # Use estimated times
            remaining_time = sum(f.estimated_time for f in remaining_files)
        
        # Adjust for cache hits (they process much faster)
        cache_adjustment = batch.cache_hit_ratio / 100.0  # Cache hit ratio as decimal
        remaining_time *= (1.0 - (cache_adjustment * 0.8))  # 80% time reduction for cache hits
        
        # Add buffer for system overhead and current phase
        phase_buffers = {
            ProcessingPhase.INITIALIZATION: 1.2,
            ProcessingPhase.VALIDATION: 1.1,
            ProcessingPhase.CACHE_CHECKING: 1.1,
            ProcessingPhase.DOCUMENT_PARSING: 1.3,
            ProcessingPhase.RAG_INTEGRATION: 1.2,
            ProcessingPhase.COMPLETION: 1.0
        }
        buffer_factor = phase_buffers.get(batch.current_phase, 1.2)
        remaining_time *= buffer_factor
        
        batch.estimated_completion = datetime.now() + timedelta(seconds=remaining_time)
    
    async def _broadcast_progress_update(self, batch_id: str):
        """Broadcast progress update to WebSocket clients"""
        if batch_id not in self.active_batches:
            return
        
        batch = self.active_batches[batch_id]
        progress_data = self._serialize_batch_progress(batch)
        
        # Send to WebSocket clients
        disconnected_callbacks = []
        for callback in self.websocket_callbacks:
            try:
                await callback(progress_data)
            except Exception as e:
                logger.warning(f"WebSocket callback failed: {e}")
                disconnected_callbacks.append(callback)
        
        # Remove failed callbacks
        for callback in disconnected_callbacks:
            self.websocket_callbacks.remove(callback)
    
    def _serialize_batch_progress(self, batch: BatchProgressInfo) -> Dict[str, Any]:
        """Serialize batch progress for WebSocket transmission"""
        return {
            "type": "batch_progress",
            "batch_id": batch.batch_id,
            "operation_type": batch.operation_type,
            "current_phase": {
                "name": batch.current_phase.value,
                "display_name": self._get_phase_display_name(batch.current_phase),
                "icon": self._get_phase_icon(batch.current_phase)
            },
            "overall_progress": round(batch.overall_progress, 1),
            "eta": batch.estimated_completion.isoformat() if batch.estimated_completion else None,
            "eta_human": self._format_eta(batch.estimated_completion) if batch.estimated_completion else None,
            "statistics": {
                "total_files": batch.total_files,
                "files_completed": batch.files_completed,
                "files_failed": batch.files_failed,
                "files_cached": batch.files_cached,
                "files_retrying": batch.files_retrying,
                "cache_hit_ratio": round(batch.cache_hit_ratio, 1),
                "average_processing_time": round(batch.average_processing_time, 1),
                "throughput_files_per_minute": round(batch.throughput_files_per_minute, 1),
                "time_saved_from_cache": round(batch.time_saved_from_cache, 1)
            },
            "phase_timings": {k: round(v, 1) for k, v in batch.phase_timings.items()},
            "file_progress": [
                {
                    "file_name": f.file_name,
                    "file_size": f.file_size,
                    "status": f.status.value,
                    "progress_percent": round(f.progress_percent, 1),
                    "processing_time": round(f.processing_time, 1),
                    "cache_hit": f.cache_hit,
                    "error_message": f.error_message,
                    "retry_count": f.retry_count
                }
                for f in batch.file_progress.values()
            ],
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_phase_display_name(self, phase: ProcessingPhase) -> str:
        """Get user-friendly phase display name"""
        display_names = {
            ProcessingPhase.INITIALIZATION: "初始化",
            ProcessingPhase.VALIDATION: "验证文件",
            ProcessingPhase.CACHE_CHECKING: "检查缓存",
            ProcessingPhase.DOCUMENT_PARSING: "解析文档",
            ProcessingPhase.RAG_INTEGRATION: "集成到知识库",
            ProcessingPhase.COMPLETION: "完成处理"
        }
        return display_names.get(phase, phase.value)
    
    def _get_phase_icon(self, phase: ProcessingPhase) -> str:
        """Get phase icon for UI"""
        icons = {
            ProcessingPhase.INITIALIZATION: "settings",
            ProcessingPhase.VALIDATION: "verified",
            ProcessingPhase.CACHE_CHECKING: "cache",
            ProcessingPhase.DOCUMENT_PARSING: "description",
            ProcessingPhase.RAG_INTEGRATION: "integration_instructions",
            ProcessingPhase.COMPLETION: "check_circle"
        }
        return icons.get(phase, "play_circle")
    
    def _format_eta(self, eta: datetime) -> str:
        """Format ETA in human-readable format"""
        if not eta:
            return "未知"
        
        remaining = eta - datetime.now()
        
        if remaining.total_seconds() <= 0:
            return "即将完成"
        
        total_seconds = int(remaining.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}小时{minutes}分钟"
        elif minutes > 0:
            return f"{minutes}分钟{seconds}秒"
        else:
            return f"{seconds}秒"
    
    async def complete_batch(self, batch_id: str, success: bool = True):
        """Mark a batch as completed and clean up"""
        if batch_id not in self.active_batches:
            return
        
        batch = self.active_batches[batch_id]
        batch.current_phase = ProcessingPhase.COMPLETION
        batch.overall_progress = 100.0
        batch.estimated_completion = datetime.now()
        
        # Save performance data for future estimates
        await self._save_performance_data(batch)
        
        # Final progress update
        await self._broadcast_progress_update(batch_id)
        
        # Archive and cleanup
        self.progress_history.append(self._serialize_batch_progress(batch))
        if len(self.progress_history) > 100:  # Keep last 100 batch records
            self.progress_history.pop(0)
        
        del self.active_batches[batch_id]
    
    async def _save_performance_data(self, batch: BatchProgressInfo):
        """Save performance data for future ETA calculations"""
        try:
            # Update performance baselines based on actual processing times
            for file_info in batch.file_progress.values():
                if file_info.processing_time > 0 and not file_info.cache_hit and file_info.file_size > 0:
                    file_ext = Path(file_info.file_path).suffix.lower()
                    size_mb = file_info.file_size / (1024 * 1024)
                    time_per_mb = file_info.processing_time / size_mb
                    
                    if file_ext in self.performance_baselines:
                        # Update with exponential moving average
                        current_baseline = self.performance_baselines[file_ext]["time_per_mb"]
                        alpha = 0.1  # Learning rate
                        new_baseline = (1 - alpha) * current_baseline + alpha * time_per_mb
                        self.performance_baselines[file_ext]["time_per_mb"] = new_baseline
            
            # Save to disk
            baseline_file = os.path.join(os.getenv("WORKING_DIR", "/tmp"), "performance_baselines.json")
            with open(baseline_file, 'w') as f:
                json.dump(self.performance_baselines, f, indent=2)
                
        except Exception as e:
            logger.warning(f"Failed to save performance data: {e}")
    
    def get_batch_progress(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get current progress for a specific batch"""
        if batch_id not in self.active_batches:
            return None
        
        return self._serialize_batch_progress(self.active_batches[batch_id])
    
    def get_all_active_batches(self) -> List[Dict[str, Any]]:
        """Get progress for all active batches"""
        return [self._serialize_batch_progress(batch) for batch in self.active_batches.values()]
    
    def get_progress_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get historical progress data"""
        return self.progress_history[-limit:]
    
    async def cancel_batch(self, batch_id: str):
        """Cancel a batch operation"""
        if batch_id not in self.active_batches:
            return
        
        batch = self.active_batches[batch_id]
        
        # Mark remaining files as failed
        for file_info in batch.file_progress.values():
            if file_info.status in [ProgressStatus.PENDING, ProgressStatus.IN_PROGRESS, ProgressStatus.RETRYING]:
                file_info.status = ProgressStatus.FAILED
                file_info.error_message = "操作被用户取消"
        
        # Complete the batch
        await self.complete_batch(batch_id, success=False)


# Global progress tracker instance
advanced_progress_tracker = AdvancedProgressTracker()