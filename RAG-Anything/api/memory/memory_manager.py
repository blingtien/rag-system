#!/usr/bin/env python3
"""
内存管理器 - RAG-Anything API
解决24小时后内存泄漏达8.7GB的问题
实现智能的内存管理和定期清理机制
"""

import gc
import os
import asyncio
import weakref
import logging
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Set
from collections import defaultdict
import json

logger = logging.getLogger(__name__)

class MemoryManagedStateManager:
    """
    内存管理状态管理器
    
    解决问题：
    1. 全局变量无限增长导致8.7GB内存泄漏
    2. 缺乏定期清理机制
    3. 完成的任务和文档状态无限累积
    
    改进方案：
    1. 定期清理过期数据
    2. 限制最大缓存数量
    3. 使用弱引用避免循环引用
    4. 内存使用监控和预警
    """
    
    def __init__(self, 
                 max_documents: int = None,
                 max_tasks: int = None,
                 cleanup_hours: int = None,
                 memory_warning_threshold_mb: int = None):
        
        # 从环境变量读取配置，使用合理的默认值
        self.max_documents = max_documents or int(os.getenv("MAX_CACHED_DOCUMENTS", "1000"))
        self.max_tasks = max_tasks or int(os.getenv("MAX_CACHED_TASKS", "500"))
        self.cleanup_interval_hours = cleanup_hours or int(os.getenv("CLEANUP_INTERVAL_HOURS", "6"))
        self.memory_warning_threshold_mb = memory_warning_threshold_mb or int(os.getenv("MEMORY_WARNING_THRESHOLD_MB", "2048"))
        
        # 状态存储
        self.documents: Dict[str, Dict] = {}
        self.tasks: Dict[str, Dict] = {}
        self.batch_operations: Dict[str, Dict] = {}
        
        # 使用弱引用字典避免循环引用
        self._temp_data = weakref.WeakValueDictionary()
        self._websocket_connections = weakref.WeakSet()
        
        # 内存监控
        self.memory_stats = {
            "peak_memory_mb": 0,
            "current_memory_mb": 0,
            "cleanup_count": 0,
            "last_cleanup": None,
            "documents_cleaned": 0,
            "tasks_cleaned": 0,
            "gc_collections": 0
        }
        
        # 异步锁保护并发访问
        self._lock = asyncio.Lock()
        
        # 后台任务（延迟启动）
        self._cleanup_task = None
        self._monitoring_task = None
        self._background_started = False
        
        logger.info(f"内存管理器初始化: 最大文档={self.max_documents}, "
                   f"最大任务={self.max_tasks}, 清理间隔={self.cleanup_interval_hours}小时")
    
    async def _ensure_background_tasks(self):
        """确保后台任务已启动（延迟启动）"""
        if not self._background_started:
            try:
                self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
                self._monitoring_task = asyncio.create_task(self._memory_monitoring())
                self._background_started = True
                logger.info("内存管理器后台任务已启动")
            except RuntimeError:
                # 如果没有事件循环，稍后再启动
                pass
    
    async def _periodic_cleanup(self):
        """定期清理过期数据"""
        cleanup_interval_seconds = self.cleanup_interval_hours * 3600
        
        while True:
            try:
                await asyncio.sleep(cleanup_interval_seconds)
                await self._cleanup_expired_data()
                
                # 强制垃圾回收
                gc.collect()
                self.memory_stats["gc_collections"] += 1
                
            except Exception as e:
                logger.error(f"定期清理过程中出错: {e}")
    
    async def _memory_monitoring(self):
        """内存使用监控"""
        while True:
            try:
                # 每分钟监控一次内存使用
                await asyncio.sleep(60)
                await self._update_memory_stats()
                
            except Exception as e:
                logger.error(f"内存监控过程中出错: {e}")
    
    async def _update_memory_stats(self):
        """更新内存统计"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            current_memory_mb = memory_info.rss / 1024 / 1024  # RSS内存，MB
            
            self.memory_stats["current_memory_mb"] = current_memory_mb
            if current_memory_mb > self.memory_stats["peak_memory_mb"]:
                self.memory_stats["peak_memory_mb"] = current_memory_mb
            
            # 内存预警
            if current_memory_mb > self.memory_warning_threshold_mb:
                logger.warning(f"内存使用过高: {current_memory_mb:.1f}MB (阈值: {self.memory_warning_threshold_mb}MB)")
                
                # 触发紧急清理
                await self._emergency_cleanup()
                
        except Exception as e:
            logger.error(f"更新内存统计失败: {e}")
    
    async def _cleanup_expired_data(self):
        """清理过期数据"""
        async with self._lock:
            cleanup_start = datetime.now()
            cutoff_time = cleanup_start - timedelta(hours=self.cleanup_interval_hours)
            
            # 清理完成的任务
            expired_tasks = []
            for task_id, task in list(self.tasks.items()):
                if (task.get("status") in ["completed", "failed"] and
                    self._is_expired(task.get("completed_at", task.get("updated_at", "")), cutoff_time)):
                    expired_tasks.append(task_id)
            
            for task_id in expired_tasks:
                self.tasks.pop(task_id, None)
            
            # 清理过期的批处理操作
            expired_batches = []
            for batch_id, batch in list(self.batch_operations.items()):
                if (batch.get("status") in ["completed", "failed"] and
                    self._is_expired(batch.get("completed_at", batch.get("started_at", "")), cutoff_time)):
                    expired_batches.append(batch_id)
            
            for batch_id in expired_batches:
                self.batch_operations.pop(batch_id, None)
            
            # 限制文档数量（保留最新的）
            documents_cleaned = 0
            if len(self.documents) > self.max_documents:
                # 按创建时间排序，保留最新的
                sorted_docs = sorted(
                    self.documents.items(),
                    key=lambda x: x[1].get("created_at", "1970-01-01"),
                    reverse=True
                )
                documents_to_keep = dict(sorted_docs[:self.max_documents])
                documents_cleaned = len(self.documents) - len(documents_to_keep)
                self.documents = documents_to_keep
            
            # 更新统计
            self.memory_stats.update({
                "cleanup_count": self.memory_stats["cleanup_count"] + 1,
                "last_cleanup": cleanup_start.isoformat(),
                "documents_cleaned": self.memory_stats["documents_cleaned"] + documents_cleaned,
                "tasks_cleaned": self.memory_stats["tasks_cleaned"] + len(expired_tasks)
            })
            
            if expired_tasks or expired_batches or documents_cleaned > 0:
                logger.info(f"内存清理完成: 任务{len(expired_tasks)}个, "
                           f"批处理{len(expired_batches)}个, 文档{documents_cleaned}个")
    
    async def _emergency_cleanup(self):
        """紧急内存清理"""
        logger.warning("触发紧急内存清理")
        
        async with self._lock:
            # 更严格的清理策略
            recent_cutoff = datetime.now() - timedelta(hours=1)  # 只保留1小时内的数据
            
            # 清理所有完成的任务
            completed_tasks = [
                task_id for task_id, task in self.tasks.items()
                if task.get("status") in ["completed", "failed"]
            ]
            for task_id in completed_tasks:
                self.tasks.pop(task_id, None)
            
            # 限制文档数量到一半
            if len(self.documents) > self.max_documents // 2:
                sorted_docs = sorted(
                    self.documents.items(),
                    key=lambda x: x[1].get("created_at", "1970-01-01"),
                    reverse=True
                )
                self.documents = dict(sorted_docs[:self.max_documents // 2])
            
            # 强制垃圾回收
            gc.collect()
            
            logger.warning(f"紧急清理完成: 清理了{len(completed_tasks)}个任务")
    
    def _is_expired(self, timestamp_str: str, cutoff_time: datetime) -> bool:
        """检查时间戳是否过期"""
        if not timestamp_str:
            return True
        
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            # 处理时区
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=None)
                cutoff_time = cutoff_time.replace(tzinfo=None)
            return timestamp < cutoff_time
        except Exception:
            return True  # 解析失败认为过期
    
    # 状态管理接口
    async def add_document(self, document_id: str, document_info: Dict[str, Any]) -> None:
        """添加文档记录"""
        await self._ensure_background_tasks()
        async with self._lock:
            self.documents[document_id] = document_info.copy()
    
    async def update_document(self, document_id: str, updates: Dict[str, Any]) -> bool:
        """更新文档记录"""
        async with self._lock:
            if document_id in self.documents:
                self.documents[document_id].update(updates)
                self.documents[document_id]["updated_at"] = datetime.now().isoformat()
                return True
            return False
    
    async def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """获取文档记录"""
        async with self._lock:
            return self.documents.get(document_id, None)
    
    async def add_task(self, task_id: str, task_info: Dict[str, Any]) -> None:
        """添加任务记录"""
        async with self._lock:
            self.tasks[task_id] = task_info.copy()
    
    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """更新任务记录"""
        async with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].update(updates)
                self.tasks[task_id]["updated_at"] = datetime.now().isoformat()
                return True
            return False
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务记录"""
        async with self._lock:
            return self.tasks.get(task_id, None)
    
    async def add_batch_operation(self, batch_id: str, batch_info: Dict[str, Any]) -> None:
        """添加批处理操作记录"""
        async with self._lock:
            self.batch_operations[batch_id] = batch_info.copy()
    
    async def update_batch_operation(self, batch_id: str, updates: Dict[str, Any]) -> bool:
        """更新批处理操作记录"""
        async with self._lock:
            if batch_id in self.batch_operations:
                self.batch_operations[batch_id].update(updates)
                return True
            return False
    
    async def get_batch_operation(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """获取批处理操作记录"""
        async with self._lock:
            return self.batch_operations.get(batch_id, None)
    
    # 查询接口
    async def get_all_documents(self) -> Dict[str, Dict[str, Any]]:
        """获取所有文档记录"""
        async with self._lock:
            return self.documents.copy()
    
    async def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务记录"""
        async with self._lock:
            return self.tasks.copy()
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """获取内存统计"""
        await self._update_memory_stats()
        stats = self.memory_stats.copy()
        stats.update({
            "documents_count": len(self.documents),
            "tasks_count": len(self.tasks),
            "batch_operations_count": len(self.batch_operations)
        })
        return stats
    
    # 持久化接口
    async def save_state_to_disk(self, file_path: str) -> bool:
        """保存状态到磁盘"""
        try:
            async with self._lock:
                state_data = {
                    "documents": self.documents,
                    "saved_at": datetime.now().isoformat(),
                    "version": "1.0"
                }
            
            # 使用临时文件避免写入过程中的数据损坏
            temp_file = f"{file_path}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            
            # 原子性移动
            os.rename(temp_file, file_path)
            return True
            
        except Exception as e:
            logger.error(f"保存状态到磁盘失败: {e}")
            return False
    
    async def load_state_from_disk(self, file_path: str) -> bool:
        """从磁盘加载状态"""
        try:
            if not os.path.exists(file_path):
                logger.info("状态文件不存在，使用空状态")
                return True
            
            with open(file_path, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            async with self._lock:
                self.documents = state_data.get("documents", {})
            
            logger.info(f"从磁盘加载了 {len(self.documents)} 个文档状态")
            return True
            
        except Exception as e:
            logger.error(f"从磁盘加载状态失败: {e}")
            return False
    
    async def cleanup(self):
        """清理资源"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._monitoring_task:
            self._monitoring_task.cancel()
        
        logger.info("内存管理器已清理")

# 全局实例（单例模式）
_memory_manager = None

def get_memory_manager() -> MemoryManagedStateManager:
    """获取内存管理器实例（单例）"""
    global _memory_manager
    
    if _memory_manager is None:
        _memory_manager = MemoryManagedStateManager()
    
    return _memory_manager

# 导出主要接口
__all__ = ['MemoryManagedStateManager', 'get_memory_manager']