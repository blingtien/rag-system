#!/usr/bin/env python3
"""
性能优化协调器 - RAG-Anything API Phase 4
整合缓存、内存、GPU管理，提供统一的性能优化接口
"""

import os
import asyncio
import time
import logging
from typing import Dict, Any, Optional, List, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import psutil

from .unified_cache_manager import get_cache_manager, CacheLevel
from .gpu_resource_manager import get_gpu_manager, TaskPriority
from ..memory.memory_manager import get_memory_manager
from ..processing.concurrent_batch_processor import get_batch_processor

logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """优化策略"""
    SPEED = "speed"          # 速度优先
    MEMORY = "memory"        # 内存优先
    BALANCED = "balanced"    # 平衡模式
    QUALITY = "quality"      # 质量优先


@dataclass
class PerformanceProfile:
    """性能配置文件"""
    name: str
    strategy: OptimizationStrategy
    cache_aggressive: bool = True
    max_concurrent: int = 4
    gpu_enabled: bool = True
    compression_enabled: bool = False
    batch_size: int = 10
    memory_limit_mb: int = 2048


class PerformanceOptimizer:
    """
    性能优化协调器
    
    功能：
    1. 统一管理所有性能组件
    2. 动态性能调优
    3. 智能资源分配
    4. 性能瓶颈检测
    5. 自动优化建议
    """
    
    def __init__(self, initial_profile: Optional[PerformanceProfile] = None):
        # 获取各个管理器实例
        self.cache_manager = get_cache_manager()
        self.gpu_manager = get_gpu_manager()
        self.memory_manager = get_memory_manager()
        self.batch_processor = get_batch_processor()
        
        # 当前性能配置
        self.current_profile = initial_profile or self._get_default_profile()
        
        # 性能监控数据
        self.performance_data = {
            "request_times": [],
            "memory_usage": [],
            "gpu_usage": [],
            "cache_hits": [],
            "batch_throughput": []
        }
        
        # 优化建议
        self.optimization_suggestions = []
        
        # 自动调优状态
        self.auto_tuning_enabled = os.getenv("AUTO_TUNING_ENABLED", "true").lower() == "true"
        self.last_tuning = datetime.now()
        self.tuning_interval = timedelta(minutes=15)
        
        # 性能阈值
        self.thresholds = {
            "high_memory_percent": 85,
            "low_cache_hit_rate": 30,
            "slow_response_ms": 5000,
            "gpu_memory_threshold": 90
        }
        
        # 启动监控和调优任务
        asyncio.create_task(self._start_monitoring())
        
        logger.info(f"性能优化器初始化完成：策略={self.current_profile.strategy.value}")
    
    def _get_default_profile(self) -> PerformanceProfile:
        """获取默认性能配置"""
        strategy = os.getenv("OPTIMIZATION_STRATEGY", "balanced").lower()
        
        profiles = {
            "speed": PerformanceProfile(
                name="speed",
                strategy=OptimizationStrategy.SPEED,
                cache_aggressive=True,
                max_concurrent=8,
                gpu_enabled=True,
                compression_enabled=False,
                batch_size=20,
                memory_limit_mb=4096
            ),
            "memory": PerformanceProfile(
                name="memory",
                strategy=OptimizationStrategy.MEMORY,
                cache_aggressive=False,
                max_concurrent=2,
                gpu_enabled=False,
                compression_enabled=True,
                batch_size=5,
                memory_limit_mb=1024
            ),
            "balanced": PerformanceProfile(
                name="balanced",
                strategy=OptimizationStrategy.BALANCED,
                cache_aggressive=True,
                max_concurrent=4,
                gpu_enabled=True,
                compression_enabled=False,
                batch_size=10,
                memory_limit_mb=2048
            ),
            "quality": PerformanceProfile(
                name="quality",
                strategy=OptimizationStrategy.QUALITY,
                cache_aggressive=False,
                max_concurrent=2,
                gpu_enabled=True,
                compression_enabled=False,
                batch_size=5,
                memory_limit_mb=3072
            )
        }
        
        return profiles.get(strategy, profiles["balanced"])
    
    async def _start_monitoring(self):
        """启动性能监控"""
        while True:
            try:
                await self._collect_performance_data()
                
                # 检查是否需要自动调优
                if self.auto_tuning_enabled:
                    if datetime.now() - self.last_tuning > self.tuning_interval:
                        await self._auto_tune()
                        self.last_tuning = datetime.now()
                
                await asyncio.sleep(30)  # 每30秒收集一次数据
            except Exception as e:
                logger.error(f"性能监控错误: {e}")
                await asyncio.sleep(60)
    
    async def _collect_performance_data(self):
        """收集性能数据"""
        # 内存使用
        memory_stats = await self.memory_manager.get_memory_stats()
        self.performance_data["memory_usage"].append({
            "timestamp": datetime.now(),
            "current_mb": memory_stats.get("current_memory_mb", 0),
            "documents": memory_stats.get("documents_count", 0),
            "tasks": memory_stats.get("tasks_count", 0)
        })
        
        # 缓存统计
        cache_stats = self.cache_manager.get_statistics()
        self.performance_data["cache_hits"].append({
            "timestamp": datetime.now(),
            "l1_hit_rate": cache_stats["l1_cache"]["hit_rate"],
            "cache_size_mb": cache_stats["performance"]["cache_size_mb"]
        })
        
        # GPU使用
        if self.gpu_manager.gpu_available:
            gpu_stats = self.gpu_manager.get_statistics()
            self.performance_data["gpu_usage"].append({
                "timestamp": datetime.now(),
                "gpu_tasks": gpu_stats.get("gpu_tasks", 0),
                "avg_gpu_time": gpu_stats.get("avg_gpu_time", 0),
                "peak_memory": gpu_stats.get("peak_memory_usage", 0)
            })
        
        # 批处理吞吐量
        batch_stats = self.batch_processor.get_performance_stats()
        self.performance_data["batch_throughput"].append({
            "timestamp": datetime.now(),
            "files_per_second": batch_stats.get("average_files_per_second", 0),
            "concurrent_efficiency": batch_stats.get("concurrent_efficiency", 0)
        })
        
        # 限制历史数据大小
        max_history = 1000
        for key in self.performance_data:
            if len(self.performance_data[key]) > max_history:
                self.performance_data[key] = self.performance_data[key][-max_history:]
    
    async def _auto_tune(self):
        """自动性能调优"""
        logger.info("开始自动性能调优...")
        
        suggestions = []
        adjustments = []
        
        # 分析最近的性能数据
        recent_memory = self._get_recent_avg("memory_usage", "current_mb", 10)
        recent_cache_hit = self._get_recent_avg("cache_hits", "l1_hit_rate", 10)
        recent_throughput = self._get_recent_avg("batch_throughput", "files_per_second", 10)
        
        # 内存压力检测
        if recent_memory > self.thresholds["high_memory_percent"] * 20:  # 假设20MB = 1%
            suggestions.append("内存使用过高，建议减少并发或启用压缩")
            if self.current_profile.max_concurrent > 2:
                self.current_profile.max_concurrent -= 1
                adjustments.append(f"降低并发数到 {self.current_profile.max_concurrent}")
            
            if not self.current_profile.compression_enabled:
                self.current_profile.compression_enabled = True
                adjustments.append("启用压缩")
        
        # 缓存效率检测
        if recent_cache_hit < self.thresholds["low_cache_hit_rate"]:
            suggestions.append(f"缓存命中率低 ({recent_cache_hit:.1f}%)，建议优化缓存策略")
            if not self.current_profile.cache_aggressive:
                self.current_profile.cache_aggressive = True
                adjustments.append("启用激进缓存策略")
        
        # 吞吐量优化
        if recent_throughput < 1.0 and self.current_profile.max_concurrent < 8:
            suggestions.append("处理吞吐量低，建议增加并发")
            self.current_profile.max_concurrent += 1
            adjustments.append(f"增加并发数到 {self.current_profile.max_concurrent}")
        
        # GPU使用优化
        if self.gpu_manager.gpu_available:
            gpu_stats = self.gpu_manager.get_statistics()
            if gpu_stats.get("cpu_fallback_tasks", 0) > gpu_stats.get("gpu_tasks", 0):
                suggestions.append("大量任务回退到CPU，建议优化GPU内存管理")
                # 触发GPU内存清理
                for i in range(self.gpu_manager.device_count):
                    await self.gpu_manager._cleanup_gpu_memory(i)
        
        # 应用调整
        if adjustments:
            logger.info(f"应用性能调整: {', '.join(adjustments)}")
            await self._apply_profile(self.current_profile)
        
        # 保存建议
        self.optimization_suggestions = suggestions
        
        if suggestions:
            logger.info(f"性能优化建议: {'; '.join(suggestions)}")
    
    def _get_recent_avg(self, data_key: str, field: str, count: int) -> float:
        """获取最近N个数据点的平均值"""
        data = self.performance_data.get(data_key, [])
        if not data:
            return 0
        
        recent = data[-count:] if len(data) >= count else data
        values = [d.get(field, 0) for d in recent]
        
        return sum(values) / len(values) if values else 0
    
    async def _apply_profile(self, profile: PerformanceProfile):
        """应用性能配置"""
        # 更新批处理器并发数
        self.batch_processor.max_concurrent = profile.max_concurrent
        self.batch_processor.semaphore = asyncio.Semaphore(profile.max_concurrent)
        
        # 更新内存管理器限制
        self.memory_manager.memory_warning_threshold_mb = profile.memory_limit_mb
        
        # 更新缓存策略
        if profile.cache_aggressive:
            self.cache_manager.config["l1_max_size"] = 2000
            self.cache_manager.config["l1_ttl_seconds"] = 7200
        else:
            self.cache_manager.config["l1_max_size"] = 500
            self.cache_manager.config["l1_ttl_seconds"] = 1800
        
        logger.info(f"已应用性能配置: {profile.name}")
    
    async def optimize_document_processing(self, 
                                          file_path: str,
                                          file_size: int) -> Dict[str, Any]:
        """
        优化文档处理
        
        返回优化建议和配置
        """
        recommendations = {
            "use_gpu": False,
            "use_cache": True,
            "batch_size": self.current_profile.batch_size,
            "parser": "auto",
            "compression": self.current_profile.compression_enabled
        }
        
        # 根据文件大小决定处理策略
        size_mb = file_size / (1024 * 1024)
        
        if size_mb < 1:
            # 小文件：优先速度
            recommendations["use_cache"] = True
            recommendations["batch_size"] = 20
        elif size_mb < 10:
            # 中等文件：平衡处理
            recommendations["use_gpu"] = self.gpu_manager.gpu_available
            recommendations["batch_size"] = 10
        else:
            # 大文件：优先稳定性
            recommendations["use_gpu"] = True
            recommendations["batch_size"] = 5
            recommendations["compression"] = True
        
        # 检查GPU可用性
        if recommendations["use_gpu"]:
            can_use = await self.gpu_manager._can_use_gpu(size_mb * 1.5)
            recommendations["use_gpu"] = can_use
        
        # 检查缓存
        cache_key_components = {
            "file_path": file_path,
            "file_size": file_size
        }
        cached = await self.cache_manager.get(key_components=cache_key_components)
        recommendations["cache_available"] = cached is not None
        
        return recommendations
    
    async def optimize_batch_processing(self, 
                                       file_paths: List[str]) -> Dict[str, Any]:
        """
        优化批处理
        
        返回批处理优化配置
        """
        total_files = len(file_paths)
        
        # 根据文件数量调整策略
        if total_files < 10:
            batch_config = {
                "max_concurrent": min(total_files, 4),
                "enable_smart_scheduling": True,
                "group_by_type": True
            }
        elif total_files < 50:
            batch_config = {
                "max_concurrent": 6,
                "enable_smart_scheduling": True,
                "group_by_type": True
            }
        else:
            batch_config = {
                "max_concurrent": 8,
                "enable_smart_scheduling": True,
                "group_by_type": True
            }
        
        # 根据当前系统负载调整
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent
        
        if cpu_percent > 80 or memory_percent > 85:
            batch_config["max_concurrent"] = max(2, batch_config["max_concurrent"] // 2)
            logger.warning(f"系统负载高，降低并发到 {batch_config['max_concurrent']}")
        
        return batch_config
    
    async def get_performance_report(self) -> Dict[str, Any]:
        """
        获取性能报告
        """
        # 收集各组件的统计
        cache_stats = self.cache_manager.get_statistics()
        memory_stats = await self.memory_manager.get_memory_stats()
        batch_stats = self.batch_processor.get_performance_stats()
        
        gpu_stats = None
        if self.gpu_manager.gpu_available:
            gpu_stats = self.gpu_manager.get_statistics()
        
        # 计算关键指标
        recent_memory = self._get_recent_avg("memory_usage", "current_mb", 10)
        recent_cache_hit = self._get_recent_avg("cache_hits", "l1_hit_rate", 10)
        recent_throughput = self._get_recent_avg("batch_throughput", "files_per_second", 10)
        
        # 生成报告
        report = {
            "summary": {
                "current_profile": self.current_profile.name,
                "strategy": self.current_profile.strategy.value,
                "auto_tuning": self.auto_tuning_enabled,
                "last_tuning": self.last_tuning.isoformat() if self.last_tuning else None
            },
            "key_metrics": {
                "memory_usage_mb": recent_memory,
                "cache_hit_rate": recent_cache_hit,
                "throughput_files_per_sec": recent_throughput,
                "concurrent_tasks": self.current_profile.max_concurrent
            },
            "cache_performance": {
                "l1_items": cache_stats["l1_cache"]["items"],
                "l1_hit_rate": cache_stats["l1_cache"]["hit_rate"],
                "total_size_mb": cache_stats["l1_cache"]["size_mb"],
                "evictions": cache_stats["total_evictions"]
            },
            "memory_performance": {
                "current_mb": memory_stats.get("current_memory_mb", 0),
                "peak_mb": memory_stats.get("peak_memory_mb", 0),
                "documents": memory_stats.get("documents_count", 0),
                "tasks": memory_stats.get("tasks_count", 0),
                "cleanups": memory_stats.get("cleanup_count", 0)
            },
            "batch_performance": {
                "total_batches": batch_stats.get("total_batches", 0),
                "total_files": batch_stats.get("total_files_processed", 0),
                "avg_files_per_sec": batch_stats.get("average_files_per_second", 0),
                "concurrent_efficiency": batch_stats.get("concurrent_efficiency", 0)
            },
            "optimization_suggestions": self.optimization_suggestions,
            "timestamps": {
                "report_generated": datetime.now().isoformat(),
                "monitoring_started": (datetime.now() - timedelta(
                    minutes=len(self.performance_data.get("memory_usage", [])) * 0.5
                )).isoformat()
            }
        }
        
        # 添加GPU统计（如果可用）
        if gpu_stats:
            report["gpu_performance"] = {
                "total_tasks": gpu_stats.get("total_tasks", 0),
                "gpu_tasks": gpu_stats.get("gpu_tasks", 0),
                "cpu_fallback": gpu_stats.get("cpu_fallback_tasks", 0),
                "avg_gpu_time": gpu_stats.get("avg_gpu_time", 0),
                "peak_memory_mb": gpu_stats.get("peak_memory_usage", 0),
                "oom_prevented": gpu_stats.get("oom_prevented", 0)
            }
        
        return report
    
    async def apply_optimization_strategy(self, strategy: str) -> bool:
        """
        应用优化策略
        
        Args:
            strategy: 策略名称 (speed/memory/balanced/quality)
        
        Returns:
            是否成功
        """
        try:
            profile = self._get_profile_by_name(strategy)
            if profile:
                self.current_profile = profile
                await self._apply_profile(profile)
                logger.info(f"已切换到优化策略: {strategy}")
                return True
            else:
                logger.error(f"未知的优化策略: {strategy}")
                return False
        except Exception as e:
            logger.error(f"应用优化策略失败: {e}")
            return False
    
    def _get_profile_by_name(self, name: str) -> Optional[PerformanceProfile]:
        """根据名称获取性能配置"""
        profiles = {
            "speed": PerformanceProfile(
                name="speed",
                strategy=OptimizationStrategy.SPEED,
                cache_aggressive=True,
                max_concurrent=8,
                gpu_enabled=True,
                compression_enabled=False,
                batch_size=20,
                memory_limit_mb=4096
            ),
            "memory": PerformanceProfile(
                name="memory",
                strategy=OptimizationStrategy.MEMORY,
                cache_aggressive=False,
                max_concurrent=2,
                gpu_enabled=False,
                compression_enabled=True,
                batch_size=5,
                memory_limit_mb=1024
            ),
            "balanced": PerformanceProfile(
                name="balanced",
                strategy=OptimizationStrategy.BALANCED,
                cache_aggressive=True,
                max_concurrent=4,
                gpu_enabled=True,
                compression_enabled=False,
                batch_size=10,
                memory_limit_mb=2048
            ),
            "quality": PerformanceProfile(
                name="quality",
                strategy=OptimizationStrategy.QUALITY,
                cache_aggressive=False,
                max_concurrent=2,
                gpu_enabled=True,
                compression_enabled=False,
                batch_size=5,
                memory_limit_mb=3072
            )
        }
        return profiles.get(name)
    
    def get_current_strategy(self) -> str:
        """获取当前优化策略"""
        return self.current_profile.strategy.value
    
    async def cleanup(self):
        """清理资源"""
        await self.cache_manager.clear_all()
        await self.memory_manager.cleanup()
        await self.gpu_manager.cleanup()
        logger.info("性能优化器已清理")


# 全局性能优化器实例
_performance_optimizer: Optional[PerformanceOptimizer] = None


def get_performance_optimizer() -> PerformanceOptimizer:
    """获取全局性能优化器实例"""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer()
    return _performance_optimizer


# 导出主要接口
__all__ = [
    'PerformanceOptimizer', 
    'get_performance_optimizer', 
    'OptimizationStrategy', 
    'PerformanceProfile'
]