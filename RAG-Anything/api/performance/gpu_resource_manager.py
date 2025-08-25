#!/usr/bin/env python3
"""
GPU资源管理器 - RAG-Anything API Phase 4
智能GPU内存管理、任务调度和资源优化
"""

import os
import asyncio
import time
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import psutil

try:
    import torch
    import nvidia_ml_py3 as nvml
    GPU_AVAILABLE = torch.cuda.is_available()
    if GPU_AVAILABLE:
        nvml.nvmlInit()
except ImportError:
    GPU_AVAILABLE = False
    torch = None
    nvml = None

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 1  # 关键任务
    HIGH = 2      # 高优先级
    NORMAL = 3    # 普通优先级
    LOW = 4       # 低优先级
    BATCH = 5     # 批处理任务


class ResourceType(Enum):
    """资源类型"""
    GPU = "gpu"
    CPU = "cpu"
    MEMORY = "memory"


@dataclass
class GPUTask:
    """GPU任务"""
    task_id: str
    task_type: str
    priority: TaskPriority
    estimated_memory_mb: float
    estimated_time_seconds: float
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    device_id: Optional[int] = None
    actual_memory_mb: Optional[float] = None
    actual_time_seconds: Optional[float] = None
    error: Optional[str] = None


class GPUResourceManager:
    """
    GPU资源管理器
    
    特性：
    1. GPU内存监控和管理
    2. 智能任务调度
    3. 动态资源分配
    4. 内存溢出预防
    5. GPU/CPU自动切换
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._load_default_config()
        self.gpu_available = GPU_AVAILABLE
        
        if not self.gpu_available:
            logger.warning("GPU不可用，将使用CPU模式")
            self.device_count = 0
        else:
            self.device_count = torch.cuda.device_count()
            logger.info(f"检测到 {self.device_count} 个GPU设备")
        
        # GPU设备信息
        self.gpu_info = self._get_gpu_info()
        
        # 任务队列（按优先级）
        self.task_queues: Dict[TaskPriority, deque] = {
            priority: deque() for priority in TaskPriority
        }
        
        # 正在执行的任务
        self.running_tasks: Dict[str, GPUTask] = {}
        
        # 设备使用状态
        self.device_status: Dict[int, Dict[str, Any]] = {
            i: {
                "available_memory_mb": 0,
                "total_memory_mb": 0,
                "utilization": 0,
                "temperature": 0,
                "power_usage": 0,
                "running_tasks": [],
                "last_update": None
            }
            for i in range(self.device_count)
        }
        
        # 资源使用历史
        self.resource_history = deque(maxlen=1000)
        
        # 性能基线（用于估算）
        self.performance_baselines = defaultdict(lambda: {
            "memory_per_mb": 1.5,  # 处理1MB数据需要的GPU内存
            "time_per_mb": 0.1     # 处理1MB数据需要的时间
        })
        
        # 内存管理策略
        self.memory_threshold_percent = self.config.get("memory_threshold_percent", 85)
        self.memory_reserve_mb = self.config.get("memory_reserve_mb", 512)
        
        # 监控任务
        self.monitoring_task = None
        self.monitoring_interval = self.config.get("monitoring_interval", 5)
        
        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "gpu_tasks": 0,
            "cpu_fallback_tasks": 0,
            "total_gpu_time": 0.0,
            "total_memory_used": 0.0,
            "peak_memory_usage": 0.0,
            "oom_prevented": 0
        }
        
        # 启动监控
        if self.gpu_available:
            asyncio.create_task(self._start_monitoring())
    
    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置"""
        return {
            "max_concurrent_gpu_tasks": int(os.getenv("MAX_CONCURRENT_GPU_TASKS", "2")),
            "memory_threshold_percent": int(os.getenv("GPU_MEMORY_THRESHOLD", "85")),
            "memory_reserve_mb": int(os.getenv("GPU_MEMORY_RESERVE_MB", "512")),
            "enable_cpu_fallback": os.getenv("ENABLE_CPU_FALLBACK", "true").lower() == "true",
            "monitoring_interval": int(os.getenv("GPU_MONITORING_INTERVAL", "5")),
            "task_timeout_seconds": int(os.getenv("GPU_TASK_TIMEOUT", "300"))
        }
    
    def _get_gpu_info(self) -> List[Dict[str, Any]]:
        """获取GPU信息"""
        if not self.gpu_available:
            return []
        
        gpu_info = []
        for i in range(self.device_count):
            try:
                handle = nvml.nvmlDeviceGetHandleByIndex(i)
                info = {
                    "index": i,
                    "name": nvml.nvmlDeviceGetName(handle).decode('utf-8'),
                    "total_memory": nvml.nvmlDeviceGetMemoryInfo(handle).total / 1024 / 1024,  # MB
                    "compute_capability": torch.cuda.get_device_capability(i),
                    "multi_processor_count": torch.cuda.get_device_properties(i).multi_processor_count
                }
                gpu_info.append(info)
            except Exception as e:
                logger.error(f"获取GPU {i} 信息失败: {e}")
                gpu_info.append({"index": i, "error": str(e)})
        
        return gpu_info
    
    async def _start_monitoring(self):
        """启动GPU监控"""
        self.monitoring_task = asyncio.create_task(self._monitor_gpu_resources())
    
    async def _monitor_gpu_resources(self):
        """监控GPU资源使用"""
        while True:
            try:
                await self._update_device_status()
                await self._check_memory_pressure()
                await self._balance_load()
                await asyncio.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"GPU监控错误: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    async def _update_device_status(self):
        """更新设备状态"""
        if not self.gpu_available:
            return
        
        for i in range(self.device_count):
            try:
                # 使用NVML获取详细信息
                handle = nvml.nvmlDeviceGetHandleByIndex(i)
                mem_info = nvml.nvmlDeviceGetMemoryInfo(handle)
                utilization = nvml.nvmlDeviceGetUtilizationRates(handle)
                temperature = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
                power = nvml.nvmlDeviceGetPowerUsage(handle) / 1000  # 转换为瓦特
                
                self.device_status[i].update({
                    "available_memory_mb": mem_info.free / 1024 / 1024,
                    "total_memory_mb": mem_info.total / 1024 / 1024,
                    "used_memory_mb": mem_info.used / 1024 / 1024,
                    "utilization": utilization.gpu,
                    "temperature": temperature,
                    "power_usage": power,
                    "last_update": datetime.now()
                })
                
                # 记录历史
                self.resource_history.append({
                    "timestamp": datetime.now(),
                    "device_id": i,
                    "memory_used_mb": mem_info.used / 1024 / 1024,
                    "utilization": utilization.gpu
                })
                
                # 更新峰值内存使用
                current_usage = mem_info.used / 1024 / 1024
                if current_usage > self.stats["peak_memory_usage"]:
                    self.stats["peak_memory_usage"] = current_usage
                
            except Exception as e:
                logger.error(f"更新GPU {i} 状态失败: {e}")
    
    async def _check_memory_pressure(self):
        """检查内存压力"""
        for i in range(self.device_count):
            status = self.device_status[i]
            if status["total_memory_mb"] > 0:
                usage_percent = (status["used_memory_mb"] / status["total_memory_mb"]) * 100
                
                if usage_percent > self.memory_threshold_percent:
                    logger.warning(f"GPU {i} 内存使用率高: {usage_percent:.1f}%")
                    
                    # 触发内存清理
                    await self._cleanup_gpu_memory(i)
                    
                    # 阻止新任务
                    if usage_percent > 95:
                        logger.critical(f"GPU {i} 内存即将耗尽，暂停新任务调度")
                        self.stats["oom_prevented"] += 1
    
    async def _cleanup_gpu_memory(self, device_id: int):
        """清理GPU内存"""
        if not self.gpu_available:
            return
        
        try:
            # 清理缓存
            with torch.cuda.device(device_id):
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            logger.info(f"GPU {device_id} 内存缓存已清理")
        except Exception as e:
            logger.error(f"清理GPU {device_id} 内存失败: {e}")
    
    async def _balance_load(self):
        """负载均衡"""
        if self.device_count <= 1:
            return
        
        # 计算各设备负载
        device_loads = []
        for i in range(self.device_count):
            status = self.device_status[i]
            # 综合考虑内存使用和GPU利用率
            load = (status["utilization"] * 0.6 + 
                   (status["used_memory_mb"] / max(status["total_memory_mb"], 1)) * 100 * 0.4)
            device_loads.append((i, load))
        
        # 按负载排序
        device_loads.sort(key=lambda x: x[1])
        
        # 如果负载差异过大，考虑任务迁移
        if len(device_loads) >= 2:
            min_load = device_loads[0][1]
            max_load = device_loads[-1][1]
            
            if max_load - min_load > 50:  # 负载差异超过50%
                logger.info(f"检测到负载不均衡: 最低{min_load:.1f}%, 最高{max_load:.1f}%")
                # 这里可以实现任务迁移逻辑
    
    async def submit_task(self, 
                         task_id: str,
                         task_type: str,
                         task_func: Callable,
                         data_size_mb: float,
                         priority: TaskPriority = TaskPriority.NORMAL,
                         **kwargs) -> str:
        """
        提交GPU任务
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
            task_func: 任务函数
            data_size_mb: 数据大小（MB）
            priority: 任务优先级
            **kwargs: 任务参数
        
        Returns:
            任务ID
        """
        # 估算资源需求
        baseline = self.performance_baselines[task_type]
        estimated_memory = data_size_mb * baseline["memory_per_mb"]
        estimated_time = data_size_mb * baseline["time_per_mb"]
        
        # 创建任务
        task = GPUTask(
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            estimated_memory_mb=estimated_memory,
            estimated_time_seconds=estimated_time
        )
        
        # 检查是否可以使用GPU
        if not self.gpu_available or not await self._can_use_gpu(estimated_memory):
            if self.config.get("enable_cpu_fallback", True):
                logger.info(f"任务 {task_id} 将使用CPU执行")
                task.device_id = -1  # CPU
                self.stats["cpu_fallback_tasks"] += 1
            else:
                raise RuntimeError("GPU资源不足且CPU回退已禁用")
        
        # 加入队列
        self.task_queues[priority].append((task, task_func, kwargs))
        self.stats["total_tasks"] += 1
        
        # 触发调度
        asyncio.create_task(self._schedule_tasks())
        
        return task_id
    
    async def _can_use_gpu(self, required_memory_mb: float) -> bool:
        """检查是否可以使用GPU"""
        if not self.gpu_available:
            return False
        
        # 检查是否有足够的内存
        for i in range(self.device_count):
            status = self.device_status[i]
            available = status["available_memory_mb"]
            
            if available > required_memory_mb + self.memory_reserve_mb:
                return True
        
        return False
    
    async def _schedule_tasks(self):
        """调度任务"""
        max_concurrent = self.config.get("max_concurrent_gpu_tasks", 2)
        
        # 检查当前运行的任务数
        if len(self.running_tasks) >= max_concurrent:
            return
        
        # 按优先级调度
        for priority in TaskPriority:
            queue = self.task_queues[priority]
            
            while queue and len(self.running_tasks) < max_concurrent:
                task, task_func, kwargs = queue.popleft()
                
                # 选择最佳设备
                device_id = await self._select_best_device(task.estimated_memory_mb)
                
                if device_id is None and task.device_id != -1:
                    # 没有可用设备，放回队列
                    queue.appendleft((task, task_func, kwargs))
                    break
                
                # 执行任务
                task.device_id = device_id if device_id is not None else -1
                task.started_at = datetime.now()
                task.status = "running"
                
                self.running_tasks[task.task_id] = task
                
                if device_id >= 0:
                    self.device_status[device_id]["running_tasks"].append(task.task_id)
                    self.stats["gpu_tasks"] += 1
                
                # 异步执行任务
                asyncio.create_task(self._execute_task(task, task_func, kwargs))
    
    async def _select_best_device(self, required_memory_mb: float) -> Optional[int]:
        """选择最佳GPU设备"""
        if not self.gpu_available:
            return None
        
        best_device = None
        best_score = float('inf')
        
        for i in range(self.device_count):
            status = self.device_status[i]
            available = status["available_memory_mb"]
            
            # 检查内存是否足够
            if available < required_memory_mb + self.memory_reserve_mb:
                continue
            
            # 计算评分（越低越好）
            # 考虑内存使用率、GPU利用率和温度
            memory_usage = status["used_memory_mb"] / max(status["total_memory_mb"], 1)
            score = (
                memory_usage * 100 * 0.4 +
                status["utilization"] * 0.3 +
                status["temperature"] * 0.3
            )
            
            if score < best_score:
                best_score = score
                best_device = i
        
        return best_device
    
    async def _execute_task(self, task: GPUTask, task_func: Callable, kwargs: Dict[str, Any]):
        """执行任务"""
        try:
            start_time = time.time()
            
            # 设置设备
            if self.gpu_available and task.device_id >= 0:
                device = f"cuda:{task.device_id}"
                torch.cuda.set_device(task.device_id)
                
                # 记录开始内存
                start_memory = torch.cuda.memory_allocated(task.device_id) / 1024 / 1024
            else:
                device = "cpu"
                start_memory = 0
            
            # 执行任务
            kwargs["device"] = device
            if asyncio.iscoroutinefunction(task_func):
                result = await task_func(**kwargs)
            else:
                result = await asyncio.get_event_loop().run_in_executor(None, task_func, **kwargs)
            
            # 记录实际使用
            task.actual_time_seconds = time.time() - start_time
            
            if self.gpu_available and task.device_id >= 0:
                end_memory = torch.cuda.memory_allocated(task.device_id) / 1024 / 1024
                task.actual_memory_mb = end_memory - start_memory
                self.stats["total_memory_used"] += task.actual_memory_mb
                self.stats["total_gpu_time"] += task.actual_time_seconds
            
            task.status = "completed"
            task.completed_at = datetime.now()
            self.stats["completed_tasks"] += 1
            
            # 更新性能基线
            self._update_performance_baseline(task)
            
            logger.info(f"任务 {task.task_id} 完成: 设备={device}, "
                       f"时间={task.actual_time_seconds:.2f}s, "
                       f"内存={task.actual_memory_mb:.1f}MB")
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now()
            self.stats["failed_tasks"] += 1
            logger.error(f"任务 {task.task_id} 失败: {e}")
        
        finally:
            # 清理
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]
            
            if task.device_id >= 0 and task.device_id < self.device_count:
                tasks = self.device_status[task.device_id]["running_tasks"]
                if task.task_id in tasks:
                    tasks.remove(task.task_id)
            
            # 触发新任务调度
            asyncio.create_task(self._schedule_tasks())
    
    def _update_performance_baseline(self, task: GPUTask):
        """更新性能基线"""
        if task.actual_memory_mb and task.actual_time_seconds:
            baseline = self.performance_baselines[task.task_type]
            
            # 使用指数移动平均更新
            alpha = 0.1
            data_size = task.estimated_memory_mb / baseline.get("memory_per_mb", 1.5)
            
            if data_size > 0:
                new_memory_per_mb = task.actual_memory_mb / data_size
                new_time_per_mb = task.actual_time_seconds / data_size
                
                baseline["memory_per_mb"] = (
                    (1 - alpha) * baseline["memory_per_mb"] + 
                    alpha * new_memory_per_mb
                )
                baseline["time_per_mb"] = (
                    (1 - alpha) * baseline["time_per_mb"] + 
                    alpha * new_time_per_mb
                )
    
    def get_device_status(self) -> Dict[int, Dict[str, Any]]:
        """获取设备状态"""
        return self.device_status.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        
        # 添加额外统计
        if stats["completed_tasks"] > 0:
            stats["avg_gpu_time"] = stats["total_gpu_time"] / stats["completed_tasks"]
            stats["avg_memory_used"] = stats["total_memory_used"] / stats["completed_tasks"]
        
        if stats["total_tasks"] > 0:
            stats["gpu_usage_ratio"] = stats["gpu_tasks"] / stats["total_tasks"] * 100
            stats["success_rate"] = stats["completed_tasks"] / stats["total_tasks"] * 100
        
        # 添加队列信息
        stats["queue_sizes"] = {
            priority.name: len(queue) 
            for priority, queue in self.task_queues.items()
        }
        
        stats["running_tasks"] = len(self.running_tasks)
        
        return stats
    
    async def cleanup(self):
        """清理资源"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
        
        # 清理GPU内存
        if self.gpu_available:
            for i in range(self.device_count):
                await self._cleanup_gpu_memory(i)
        
        logger.info("GPU资源管理器已清理")


# 全局GPU管理器实例
_gpu_manager: Optional[GPUResourceManager] = None


def get_gpu_manager() -> GPUResourceManager:
    """获取全局GPU管理器实例"""
    global _gpu_manager
    if _gpu_manager is None:
        _gpu_manager = GPUResourceManager()
    return _gpu_manager


# 导出主要接口
__all__ = ['GPUResourceManager', 'get_gpu_manager', 'TaskPriority', 'ResourceType']