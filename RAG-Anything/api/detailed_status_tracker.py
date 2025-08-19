#!/usr/bin/env python3
"""
Detailed Status Tracker for RAG-Anything API
详细的文档解析状态跟踪器，提供类似终端的详细进度信息
"""

import asyncio
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class ProcessingStage(Enum):
    """处理阶段枚举"""
    PARSING = "parsing"
    CONTENT_ANALYSIS = "content_analysis"
    TEXT_PROCESSING = "text_processing"
    IMAGE_PROCESSING = "image_processing"
    TABLE_PROCESSING = "table_processing"
    EQUATION_PROCESSING = "equation_processing"
    GRAPH_BUILDING = "graph_building"
    INDEXING = "indexing"
    COMPLETED = "completed"

@dataclass
class ContentStats:
    """内容统计信息"""
    total_blocks: int = 0
    text_blocks: int = 0
    image_blocks: int = 0
    table_blocks: int = 0
    equation_blocks: int = 0
    other_blocks: int = 0
    
    def update_from_content_list(self, content_list: List[Dict[str, Any]]):
        """从content_list更新统计信息"""
        self.total_blocks = len(content_list)
        self.text_blocks = 0
        self.image_blocks = 0
        self.table_blocks = 0
        self.equation_blocks = 0
        self.other_blocks = 0
        
        for block in content_list:
            if isinstance(block, dict):
                block_type = block.get("type", "unknown")
                if block_type == "text":
                    self.text_blocks += 1
                elif block_type == "image":
                    self.image_blocks += 1
                elif block_type == "table":
                    self.table_blocks += 1
                elif block_type in ["equation", "formula"]:
                    self.equation_blocks += 1
                else:
                    self.other_blocks += 1

@dataclass
class ProcessingProgress:
    """处理进度信息"""
    current_item: int = 0
    total_items: int = 0
    current_type: str = ""
    description: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def percentage(self) -> float:
        """进度百分比"""
        if self.total_items == 0:
            return 0.0
        return (self.current_item / self.total_items) * 100
    
    @property
    def elapsed_time(self) -> float:
        """已用时间（秒）"""
        if not self.started_at:
            return 0.0
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()

@dataclass
class DetailedStatus:
    """详细状态信息"""
    task_id: str
    file_name: str
    file_size: int
    parser_used: str = ""
    parser_reason: str = ""
    
    # 当前阶段
    current_stage: ProcessingStage = ProcessingStage.PARSING
    stage_progress: Dict[ProcessingStage, ProcessingProgress] = field(default_factory=dict)
    
    # 内容统计
    content_stats: ContentStats = field(default_factory=ContentStats)
    
    # 整体状态
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # 详细日志
    processing_logs: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_log(self, level: str, message: str, details: Optional[Dict[str, Any]] = None):
        """添加处理日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "details": details or {}
        }
        self.processing_logs.append(log_entry)
        
        # 保持日志数量在合理范围内
        if len(self.processing_logs) > 100:
            self.processing_logs = self.processing_logs[-50:]
    
    def start_stage(self, stage: ProcessingStage, total_items: int = 0, description: str = ""):
        """开始新阶段"""
        self.current_stage = stage
        progress = ProcessingProgress(
            current_item=0,
            total_items=total_items,
            description=description,
            started_at=datetime.now()
        )
        self.stage_progress[stage] = progress
        
        self.add_log("INFO", f"开始阶段: {stage.value}", {
            "total_items": total_items,
            "description": description
        })
    
    def update_stage_progress(self, current_item: int, current_type: str = "", description: str = ""):
        """更新当前阶段进度"""
        if self.current_stage in self.stage_progress:
            progress = self.stage_progress[self.current_stage]
            progress.current_item = current_item
            progress.current_type = current_type
            if description:
                progress.description = description
            
            self.add_log("DEBUG", f"进度更新: {current_item}/{progress.total_items} - {current_type}", {
                "percentage": progress.percentage,
                "elapsed_time": progress.elapsed_time
            })
    
    def complete_stage(self, stage: ProcessingStage):
        """完成阶段"""
        if stage in self.stage_progress:
            self.stage_progress[stage].completed_at = datetime.now()
            self.add_log("INFO", f"完成阶段: {stage.value}", {
                "elapsed_time": self.stage_progress[stage].elapsed_time
            })
    
    def complete_processing(self):
        """完成整个处理过程"""
        self.current_stage = ProcessingStage.COMPLETED
        self.completed_at = datetime.now()
        self.add_log("SUCCESS", "文档处理完成", {
            "total_time": (self.completed_at - self.started_at).total_seconds()
        })
    
    def set_error(self, error_message: str):
        """设置错误状态"""
        self.error_message = error_message
        self.add_log("ERROR", f"处理失败: {error_message}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于API传输"""
        return {
            "task_id": self.task_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "parser_used": self.parser_used,
            "parser_reason": self.parser_reason,
            "current_stage": self.current_stage.value,
            "content_stats": {
                "total_blocks": self.content_stats.total_blocks,
                "text_blocks": self.content_stats.text_blocks,
                "image_blocks": self.content_stats.image_blocks,
                "table_blocks": self.content_stats.table_blocks,
                "equation_blocks": self.content_stats.equation_blocks,
                "other_blocks": self.content_stats.other_blocks,
            },
            "stage_progress": {
                stage.value: {
                    "current_item": progress.current_item,
                    "total_items": progress.total_items,
                    "current_type": progress.current_type,
                    "description": progress.description,
                    "percentage": progress.percentage,
                    "elapsed_time": progress.elapsed_time,
                    "completed": progress.completed_at is not None
                }
                for stage, progress in self.stage_progress.items()
            },
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "processing_logs": self.processing_logs[-10:],  # 只返回最近10条日志
            "total_elapsed_time": (
                (self.completed_at or datetime.now()) - self.started_at
            ).total_seconds()
        }

class DetailedStatusTracker:
    """详细状态跟踪器管理器"""
    
    def __init__(self):
        self.active_statuses: Dict[str, DetailedStatus] = {}
        self.status_callbacks: Dict[str, List[callable]] = {}
    
    def create_status(self, task_id: str, file_name: str, file_size: int, 
                     parser_used: str = "", parser_reason: str = "") -> DetailedStatus:
        """创建新的状态跟踪"""
        status = DetailedStatus(
            task_id=task_id,
            file_name=file_name,
            file_size=file_size,
            parser_used=parser_used,
            parser_reason=parser_reason
        )
        self.active_statuses[task_id] = status
        return status
    
    def get_status(self, task_id: str) -> Optional[DetailedStatus]:
        """获取状态"""
        return self.active_statuses.get(task_id)
    
    def remove_status(self, task_id: str):
        """移除状态"""
        if task_id in self.active_statuses:
            del self.active_statuses[task_id]
        if task_id in self.status_callbacks:
            del self.status_callbacks[task_id]
    
    def add_status_callback(self, task_id: str, callback: callable):
        """添加状态变更回调"""
        if task_id not in self.status_callbacks:
            self.status_callbacks[task_id] = []
        self.status_callbacks[task_id].append(callback)
    
    async def notify_status_change(self, task_id: str):
        """通知状态变更"""
        if task_id in self.status_callbacks:
            status = self.get_status(task_id)
            if status:
                status_dict = status.to_dict()
                for callback in self.status_callbacks[task_id]:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(status_dict)
                        else:
                            callback(status_dict)
                    except Exception as e:
                        logger.error(f"Status callback error: {e}")

# 全局状态跟踪器实例
detailed_tracker = DetailedStatusTracker()

class StatusLogger:
    """状态日志记录器，用于拦截RAGAnything的日志"""
    
    def __init__(self, task_id: str, tracker: DetailedStatusTracker):
        self.task_id = task_id
        self.tracker = tracker
    
    async def log_parsing_complete(self, content_list: List[Dict[str, Any]]):
        """记录解析完成"""
        status = self.tracker.get_status(self.task_id)
        if status:
            status.content_stats.update_from_content_list(content_list)
            status.complete_stage(ProcessingStage.PARSING)
            status.add_log("SUCCESS", f"解析完成！提取了 {len(content_list)} 个内容块", {
                "content_distribution": {
                    "text": status.content_stats.text_blocks,
                    "image": status.content_stats.image_blocks,
                    "table": status.content_stats.table_blocks,
                    "equation": status.content_stats.equation_blocks,
                    "other": status.content_stats.other_blocks
                }
            })
            await self.tracker.notify_status_change(self.task_id)
    
    async def log_multimodal_processing_start(self, total_items: int):
        """记录多模态处理开始"""
        status = self.tracker.get_status(self.task_id)
        if status:
            # 根据内容类型确定具体的处理阶段
            if status.content_stats.image_blocks > 0:
                status.start_stage(ProcessingStage.IMAGE_PROCESSING, total_items, "处理图片内容")
            elif status.content_stats.table_blocks > 0:
                status.start_stage(ProcessingStage.TABLE_PROCESSING, total_items, "处理表格内容")
            elif status.content_stats.equation_blocks > 0:
                status.start_stage(ProcessingStage.EQUATION_PROCESSING, total_items, "处理公式内容")
            else:
                status.start_stage(ProcessingStage.CONTENT_ANALYSIS, total_items, "分析内容")
            await self.tracker.notify_status_change(self.task_id)
    
    async def log_item_processing(self, current_item: int, total_items: int, content_type: str):
        """记录单个项目处理"""
        status = self.tracker.get_status(self.task_id)
        if status:
            status.update_stage_progress(
                current_item=current_item,
                current_type=content_type,
                description=f"正在处理第 {current_item}/{total_items} 个 {content_type} 内容"
            )
            await self.tracker.notify_status_change(self.task_id)
    
    async def log_descriptions_generated(self, successful: int, total: int):
        """记录描述生成完成"""
        status = self.tracker.get_status(self.task_id)
        if status:
            status.add_log("INFO", f"生成描述完成: {successful}/{total} 个项目成功处理")
            await self.tracker.notify_status_change(self.task_id)
    
    async def log_graph_building_start(self):
        """记录知识图谱构建开始"""
        status = self.tracker.get_status(self.task_id)
        if status:
            status.start_stage(ProcessingStage.GRAPH_BUILDING, 1, "构建知识图谱")
            await self.tracker.notify_status_change(self.task_id)
    
    async def log_indexing_start(self):
        """记录索引创建开始"""
        status = self.tracker.get_status(self.task_id)
        if status:
            status.start_stage(ProcessingStage.INDEXING, 1, "创建索引")
            await self.tracker.notify_status_change(self.task_id)
    
    async def log_processing_complete(self):
        """记录处理完成"""
        status = self.tracker.get_status(self.task_id)
        if status:
            status.complete_processing()
            await self.tracker.notify_status_change(self.task_id)
    
    async def log_error(self, error_message: str):
        """记录错误"""
        status = self.tracker.get_status(self.task_id)
        if status:
            status.set_error(error_message)
            await self.tracker.notify_status_change(self.task_id)