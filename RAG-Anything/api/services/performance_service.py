"""
性能监控和优化服务
提供实时性能监控、资源管理、缓存优化等功能
"""
import asyncio
import os
import psutil
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from threading import RLock
import json

# 尝试导入GPU相关库
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import GPUtil
    GPUTIL_AVAILABLE = True
except ImportError:
    GPUTIL_AVAILABLE = False

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float  
    memory_available: int
    disk_usage: float
    disk_io_read: float
    disk_io_write: float
    network_io_sent: float
    network_io_recv: float
    gpu_usage: float = 0.0
    gpu_memory_used: float = 0.0
    gpu_memory_total: float = 0.0
    active_processes: int = 0
    context_switches: int = 0


@dataclass
class PerformanceAlert:
    """性能告警数据类"""
    alert_id: str
    alert_type: str
    severity: str  # "low", "medium", "high", "critical"
    message: str
    metrics: Dict[str, Any]
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class PerformanceCache:
    """高性能缓存管理器"""
    
    def __init__(self, max_size: int = 10000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.access_times: Dict[str, datetime] = {}
        self.lock = RLock()
        
    def get(self, key: str) -> Optional[Any]:
        """获取缓存项"""
        with self.lock:
            if key not in self.cache:
                return None
            
            value, created_at = self.cache[key]
            
            # 检查TTL
            if datetime.now() - created_at > timedelta(seconds=self.ttl_seconds):
                self._remove_key(key)
                return None
            
            # 更新访问时间
            self.access_times[key] = datetime.now()
            return value
    
    def set(self, key: str, value: Any) -> None:
        """设置缓存项"""
        with self.lock:
            current_time = datetime.now()
            
            # 检查是否需要清理空间
            if len(self.cache) >= self.max_size:
                self._evict_lru()
            
            self.cache[key] = (value, current_time)
            self.access_times[key] = current_time
    
    def _remove_key(self, key: str) -> None:
        """删除缓存项"""
        self.cache.pop(key, None)
        self.access_times.pop(key, None)
    
    def _evict_lru(self) -> None:
        """移除最少使用的缓存项"""
        if not self.access_times:
            return
        
        lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
        self._remove_key(lru_key)
    
    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            return {
                "total_items": len(self.cache),
                "max_size": self.max_size,
                "usage_ratio": len(self.cache) / self.max_size,
                "ttl_seconds": self.ttl_seconds
            }


class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self):
        self.memory_samples: List[Tuple[datetime, float]] = []
        self.max_samples = 1000
        self.leak_threshold = 100  # MB增长被认为可能的内存泄漏
        
    def record_memory_usage(self) -> float:
        """记录当前内存使用情况"""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)
        
        current_time = datetime.now()
        self.memory_samples.append((current_time, memory_mb))
        
        # 保持样本数量在限制内
        if len(self.memory_samples) > self.max_samples:
            self.memory_samples = self.memory_samples[-self.max_samples:]
        
        return memory_mb
    
    def detect_memory_leak(self) -> Optional[Dict[str, Any]]:
        """检测可能的内存泄漏"""
        if len(self.memory_samples) < 10:
            return None
        
        # 取最近10个样本和10分钟前的样本进行比较
        recent_samples = self.memory_samples[-10:]
        older_samples = [s for s in self.memory_samples if 
                        datetime.now() - s[0] > timedelta(minutes=10)]
        
        if not older_samples:
            return None
        
        recent_avg = sum(s[1] for s in recent_samples) / len(recent_samples)
        older_avg = sum(s[1] for s in older_samples[-10:]) / min(len(older_samples), 10)
        
        growth = recent_avg - older_avg
        
        if growth > self.leak_threshold:
            return {
                "potential_leak": True,
                "memory_growth_mb": growth,
                "recent_avg_mb": recent_avg,
                "older_avg_mb": older_avg,
                "sample_count": len(self.memory_samples)
            }
        
        return None


class ResourceOptimizer:
    """资源优化器"""
    
    def __init__(self):
        self.optimization_cache = PerformanceCache(max_size=1000, ttl_seconds=300)
        
    def optimize_batch_size(self, available_memory_mb: float, file_count: int, avg_file_size_mb: float) -> int:
        """根据可用内存优化批处理大小"""
        # 为系统保留30%内存
        usable_memory = available_memory_mb * 0.7
        
        # 估算每个文件处理需要的内存（文件大小的3倍用于处理缓冲）
        memory_per_file = avg_file_size_mb * 3
        
        # 计算最优批大小
        if memory_per_file <= 0:
            return min(file_count, 10)  # 默认批大小
        
        optimal_batch_size = int(usable_memory / memory_per_file)
        
        # 限制在合理范围内
        optimal_batch_size = max(1, min(optimal_batch_size, min(file_count, 20)))
        
        return optimal_batch_size
    
    def optimize_worker_count(self, cpu_count: int, current_load: float) -> int:
        """根据CPU状态优化工作线程数"""
        if current_load > 80:
            # 高负载时减少工作线程
            return max(1, cpu_count // 2)
        elif current_load < 50:
            # 低负载时可以增加工作线程
            return min(cpu_count * 2, 16)
        else:
            # 中等负载时使用默认配置
            return cpu_count
    
    def should_use_gpu(self, task_size: int, gpu_available: bool, gpu_memory_free: float) -> bool:
        """判断是否应该使用GPU处理"""
        if not gpu_available or not TORCH_AVAILABLE:
            return False
        
        # GPU内存不足时不使用
        if gpu_memory_free < 1024:  # 至少需要1GB显存
            return False
        
        # 小任务不值得GPU开销
        if task_size < 5:
            return False
        
        return True


class PerformanceService:
    """性能监控和优化服务"""
    
    def __init__(self):
        self.metrics_history: List[PerformanceMetrics] = []
        self.alerts: List[PerformanceAlert] = []
        self.memory_monitor = MemoryMonitor()
        self.resource_optimizer = ResourceOptimizer()
        self.performance_cache = PerformanceCache()
        
        # 性能阈值配置
        self.thresholds = {
            "cpu_usage_warning": 75.0,
            "cpu_usage_critical": 90.0,
            "memory_usage_warning": 80.0,
            "memory_usage_critical": 95.0,
            "disk_usage_warning": 85.0,
            "disk_usage_critical": 95.0,
            "gpu_usage_warning": 85.0,
            "gpu_usage_critical": 95.0
        }
        
        # 启动后台监控任务
        self._monitoring_task = None
        self._start_background_monitoring()
    
    def _start_background_monitoring(self):
        """启动后台性能监控"""
        async def monitor_loop():
            while True:
                try:
                    await self.collect_metrics()
                    await self.check_alerts()
                    await asyncio.sleep(30)  # 每30秒收集一次指标
                except Exception as e:
                    logger.error(f"性能监控循环错误: {e}")
                    await asyncio.sleep(60)  # 出错后等待更长时间
        
        # 在当前事件循环中启动任务
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                return
            self._monitoring_task = loop.create_task(monitor_loop())
        except RuntimeError:
            # 事件循环尚未启动，稍后启动
            pass
    
    async def collect_metrics(self) -> PerformanceMetrics:
        """收集系统性能指标"""
        try:
            # CPU和内存信息
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # 磁盘I/O统计
            disk_io = psutil.disk_io_counters()
            disk_io_read = disk_io.read_bytes if disk_io else 0
            disk_io_write = disk_io.write_bytes if disk_io else 0
            
            # 网络I/O统计
            network_io = psutil.net_io_counters()
            network_io_sent = network_io.bytes_sent if network_io else 0
            network_io_recv = network_io.bytes_recv if network_io else 0
            
            # GPU信息
            gpu_usage = 0.0
            gpu_memory_used = 0.0
            gpu_memory_total = 0.0
            
            if TORCH_AVAILABLE and torch.cuda.is_available():
                try:
                    gpu_usage = torch.cuda.utilization()
                    gpu_memory_used = torch.cuda.memory_allocated() / (1024**3)  # GB
                    gpu_memory_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB
                except Exception as e:
                    logger.debug(f"GPU信息获取失败: {e}")
            
            elif GPUTIL_AVAILABLE:
                try:
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        gpu = gpus[0]
                        gpu_usage = gpu.load * 100
                        gpu_memory_used = gpu.memoryUsed / 1024  # GB
                        gpu_memory_total = gpu.memoryTotal / 1024  # GB
                except Exception as e:
                    logger.debug(f"GPUtil信息获取失败: {e}")
            
            # 进程信息
            active_processes = len(psutil.pids())
            context_switches = psutil.cpu_stats().ctx_switches
            
            metrics = PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_usage=cpu_usage,
                memory_usage=memory.percent,
                memory_available=memory.available,
                disk_usage=disk.percent,
                disk_io_read=disk_io_read,
                disk_io_write=disk_io_write,
                network_io_sent=network_io_sent,
                network_io_recv=network_io_recv,
                gpu_usage=gpu_usage,
                gpu_memory_used=gpu_memory_used,
                gpu_memory_total=gpu_memory_total,
                active_processes=active_processes,
                context_switches=context_switches
            )
            
            # 记录内存使用情况
            self.memory_monitor.record_memory_usage()
            
            # 保存指标历史
            self.metrics_history.append(metrics)
            
            # 限制历史记录数量
            if len(self.metrics_history) > 1000:
                self.metrics_history = self.metrics_history[-1000:]
            
            return metrics
            
        except Exception as e:
            logger.error(f"收集性能指标时出错: {e}")
            # 返回默认指标
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_usage=0.0,
                memory_usage=0.0,
                memory_available=0,
                disk_usage=0.0,
                disk_io_read=0.0,
                disk_io_write=0.0,
                network_io_sent=0.0,
                network_io_recv=0.0
            )
    
    async def check_alerts(self) -> List[PerformanceAlert]:
        """检查性能告警"""
        if not self.metrics_history:
            return []
        
        latest_metrics = self.metrics_history[-1]
        new_alerts = []
        
        # CPU使用率告警
        if latest_metrics.cpu_usage > self.thresholds["cpu_usage_critical"]:
            alert = self._create_alert(
                "cpu_usage_critical",
                "critical",
                f"CPU使用率过高: {latest_metrics.cpu_usage:.1f}%",
                {"cpu_usage": latest_metrics.cpu_usage}
            )
            new_alerts.append(alert)
        elif latest_metrics.cpu_usage > self.thresholds["cpu_usage_warning"]:
            alert = self._create_alert(
                "cpu_usage_warning",
                "medium",
                f"CPU使用率较高: {latest_metrics.cpu_usage:.1f}%",
                {"cpu_usage": latest_metrics.cpu_usage}
            )
            new_alerts.append(alert)
        
        # 内存使用率告警
        if latest_metrics.memory_usage > self.thresholds["memory_usage_critical"]:
            alert = self._create_alert(
                "memory_usage_critical",
                "critical",
                f"内存使用率过高: {latest_metrics.memory_usage:.1f}%",
                {"memory_usage": latest_metrics.memory_usage}
            )
            new_alerts.append(alert)
        elif latest_metrics.memory_usage > self.thresholds["memory_usage_warning"]:
            alert = self._create_alert(
                "memory_usage_warning",
                "medium",
                f"内存使用率较高: {latest_metrics.memory_usage:.1f}%",
                {"memory_usage": latest_metrics.memory_usage}
            )
            new_alerts.append(alert)
        
        # 内存泄漏检测
        leak_info = self.memory_monitor.detect_memory_leak()
        if leak_info and leak_info.get("potential_leak"):
            alert = self._create_alert(
                "memory_leak_detected",
                "high",
                f"检测到可能的内存泄漏: 增长 {leak_info['memory_growth_mb']:.1f}MB",
                leak_info
            )
            new_alerts.append(alert)
        
        # GPU告警
        if latest_metrics.gpu_usage > self.thresholds["gpu_usage_critical"]:
            alert = self._create_alert(
                "gpu_usage_critical",
                "high",
                f"GPU使用率过高: {latest_metrics.gpu_usage:.1f}%",
                {"gpu_usage": latest_metrics.gpu_usage}
            )
            new_alerts.append(alert)
        
        # 磁盘空间告警
        if latest_metrics.disk_usage > self.thresholds["disk_usage_critical"]:
            alert = self._create_alert(
                "disk_usage_critical",
                "critical",
                f"磁盘使用率过高: {latest_metrics.disk_usage:.1f}%",
                {"disk_usage": latest_metrics.disk_usage}
            )
            new_alerts.append(alert)
        
        # 添加新告警到历史记录
        self.alerts.extend(new_alerts)
        
        # 限制告警历史数量
        if len(self.alerts) > 1000:
            self.alerts = self.alerts[-1000:]
        
        return new_alerts
    
    def _create_alert(self, alert_type: str, severity: str, message: str, metrics: Dict[str, Any]) -> PerformanceAlert:
        """创建性能告警"""
        import uuid
        return PerformanceAlert(
            alert_id=str(uuid.uuid4()),
            alert_type=alert_type,
            severity=severity,
            message=message,
            metrics=metrics,
            timestamp=datetime.now()
        )
    
    async def get_current_metrics(self) -> PerformanceMetrics:
        """获取当前性能指标"""
        return await self.collect_metrics()
    
    async def get_metrics_history(self, hours: int = 24) -> List[PerformanceMetrics]:
        """获取指定时间段的性能指标历史"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [m for m in self.metrics_history if m.timestamp > cutoff_time]
    
    async def get_active_alerts(self) -> List[PerformanceAlert]:
        """获取活跃的性能告警"""
        return [alert for alert in self.alerts if not alert.resolved]
    
    async def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        current_metrics = await self.get_current_metrics()
        active_alerts = await self.get_active_alerts()
        
        # 计算24小时平均值
        recent_metrics = await self.get_metrics_history(24)
        
        if recent_metrics:
            avg_cpu = sum(m.cpu_usage for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_usage for m in recent_metrics) / len(recent_metrics)
            avg_gpu = sum(m.gpu_usage for m in recent_metrics) / len(recent_metrics)
        else:
            avg_cpu = avg_memory = avg_gpu = 0.0
        
        return {
            "current_metrics": asdict(current_metrics),
            "active_alerts_count": len(active_alerts),
            "critical_alerts_count": len([a for a in active_alerts if a.severity == "critical"]),
            "24h_averages": {
                "cpu_usage": avg_cpu,
                "memory_usage": avg_memory,
                "gpu_usage": avg_gpu
            },
            "cache_stats": self.performance_cache.get_stats(),
            "optimization_recommendations": await self._generate_optimization_recommendations()
        }
    
    async def _generate_optimization_recommendations(self) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        if not self.metrics_history:
            return recommendations
        
        latest_metrics = self.metrics_history[-1]
        
        if latest_metrics.cpu_usage > 80:
            recommendations.append("考虑减少并发处理任务数量或升级CPU")
        
        if latest_metrics.memory_usage > 85:
            recommendations.append("考虑增加系统内存或优化内存使用")
        
        if latest_metrics.disk_usage > 90:
            recommendations.append("清理磁盘空间或扩展存储容量")
        
        if latest_metrics.gpu_usage > 90 and latest_metrics.gpu_memory_used > latest_metrics.gpu_memory_total * 0.9:
            recommendations.append("GPU资源紧张，考虑减少GPU任务或升级显卡")
        
        # 检查内存泄漏
        leak_info = self.memory_monitor.detect_memory_leak()
        if leak_info and leak_info.get("potential_leak"):
            recommendations.append("检测到可能的内存泄漏，建议检查长期运行的任务")
        
        return recommendations
    
    async def optimize_for_batch_processing(self, file_count: int, total_size_mb: float) -> Dict[str, Any]:
        """为批量处理优化系统参数"""
        current_metrics = await self.get_current_metrics()
        
        # 获取系统资源信息
        memory = psutil.virtual_memory()
        available_memory_mb = memory.available / (1024 * 1024)
        cpu_count = psutil.cpu_count()
        
        avg_file_size = total_size_mb / file_count if file_count > 0 else 0
        
        # 优化批处理参数
        optimal_batch_size = self.resource_optimizer.optimize_batch_size(
            available_memory_mb, file_count, avg_file_size
        )
        
        optimal_workers = self.resource_optimizer.optimize_worker_count(
            cpu_count, current_metrics.cpu_usage
        )
        
        # GPU使用建议
        gpu_available = TORCH_AVAILABLE and torch.cuda.is_available()
        gpu_memory_free = current_metrics.gpu_memory_total - current_metrics.gpu_memory_used
        should_use_gpu = self.resource_optimizer.should_use_gpu(
            file_count, gpu_available, gpu_memory_free * 1024  # 转换为MB
        )
        
        return {
            "optimal_batch_size": optimal_batch_size,
            "optimal_worker_count": optimal_workers,
            "should_use_gpu": should_use_gpu,
            "current_system_load": {
                "cpu_usage": current_metrics.cpu_usage,
                "memory_usage": current_metrics.memory_usage,
                "available_memory_mb": available_memory_mb,
                "gpu_usage": current_metrics.gpu_usage
            },
            "optimization_rationale": {
                "memory_per_file_estimate": avg_file_size * 3,
                "total_memory_needed": optimal_batch_size * avg_file_size * 3,
                "memory_safety_margin": "30%"
            }
        }
    
    async def cleanup_old_data(self, days: int = 7) -> Dict[str, int]:
        """清理旧的性能数据"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        # 清理指标历史
        old_metrics_count = len(self.metrics_history)
        self.metrics_history = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        cleaned_metrics = old_metrics_count - len(self.metrics_history)
        
        # 清理告警历史
        old_alerts_count = len(self.alerts)
        self.alerts = [a for a in self.alerts if a.timestamp > cutoff_time]
        cleaned_alerts = old_alerts_count - len(self.alerts)
        
        # 清理缓存
        self.performance_cache.clear()
        
        return {
            "cleaned_metrics": cleaned_metrics,
            "cleaned_alerts": cleaned_alerts,
            "cache_cleared": True
        }
    
    async def shutdown(self):
        """关闭性能监控服务"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass


# 全局性能服务实例
_performance_service_instance = None

def get_performance_service() -> PerformanceService:
    """获取性能服务实例（单例模式）"""
    global _performance_service_instance
    if _performance_service_instance is None:
        _performance_service_instance = PerformanceService()
    return _performance_service_instance