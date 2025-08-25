#!/usr/bin/env python3
"""
性能监控中间件
集成请求性能监控、资源使用监控和性能异常检测
"""

import time
import asyncio
import psutil
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import deque, defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .unified_logging import LoggerFactory, LogCategory
from .error_tracking import error_tracker, trace_span, SpanType
from .debug_tools import debug_profiler


class PerformanceMonitor(BaseHTTPMiddleware):
    """
    性能监控中间件
    
    功能:
    1. 请求性能监控
    2. 资源使用监控  
    3. 慢查询检测
    4. 性能异常告警
    5. 性能趋势分析
    """
    
    def __init__(self, app, slow_request_threshold: float = 5000, enable_resource_monitoring: bool = True):
        super().__init__(app)
        self.logger = LoggerFactory.get_logger("performance_monitor")
        self.slow_request_threshold = slow_request_threshold  # 毫秒
        self.enable_resource_monitoring = enable_resource_monitoring
        
        # 性能指标收集
        self.request_metrics: Dict[str, Any] = defaultdict(lambda: {
            'count': 0,
            'total_duration': 0,
            'min_duration': float('inf'),
            'max_duration': 0,
            'error_count': 0
        })
        
        # 慢请求记录
        self.slow_requests: deque = deque(maxlen=100)
        
        # 系统资源监控
        self.resource_samples: deque = deque(maxlen=60)  # 最近60个采样点
        self.last_resource_check = datetime.now()
        
        # 性能告警
        self.performance_alerts: deque = deque(maxlen=50)
    
    async def dispatch(self, request: Request, call_next):
        """监控请求性能"""
        start_time = time.time()
        
        # 获取请求标识
        method = request.method
        path = str(request.url.path)
        endpoint_key = f"{method} {path}"
        
        # 开始性能追踪跨度
        async with trace_span(f"request_{endpoint_key}", SpanType.HTTP_REQUEST) as span:
            span.add_tag("method", method)
            span.add_tag("path", path)
            
            # 开始请求分析（如果启用调试）
            profile = None
            if debug_profiler.enable_profiling:
                request_id = getattr(request.state, 'request_id', 'unknown')
                profile = debug_profiler.start_request_profiling(request_id, method, path)
            
            # 采集开始时的资源使用
            start_memory = self._get_memory_usage() if self.enable_resource_monitoring else None
            
            try:
                # 执行请求
                response = await call_next(request)
                status_code = response.status_code
                
                # 计算执行时间
                duration_ms = (time.time() - start_time) * 1000
                
                # 添加性能相关的响应头
                response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
                
                # 更新性能指标
                await self._update_metrics(endpoint_key, duration_ms, status_code, start_memory)
                
                # 检查慢请求
                if duration_ms > self.slow_request_threshold:
                    await self._handle_slow_request(endpoint_key, duration_ms, status_code, request)
                
                # 完成请求分析
                if profile:
                    debug_profiler.finish_request_profiling(
                        profile.request_id, status_code, len(response.body) if hasattr(response, 'body') else 0
                    )
                
                # 记录性能日志
                await self.logger.log_request(method, path, status_code, duration_ms)
                
                return response
                
            except Exception as e:
                # 错误情况下也记录性能指标
                duration_ms = (time.time() - start_time) * 1000
                await self._update_metrics(endpoint_key, duration_ms, 500, start_memory, is_error=True)
                
                if profile:
                    debug_profiler.finish_request_profiling(profile.request_id, 500)
                
                # 记录错误日志
                await self.logger.error(
                    f"Request failed: {method} {path}",
                    category=LogCategory.REQUEST,
                    duration_ms=duration_ms,
                    error_details={'error': str(e)}
                )
                
                raise
    
    async def _update_metrics(self, endpoint_key: str, duration_ms: float, 
                            status_code: int, start_memory: Optional[float] = None, is_error: bool = False):
        """更新性能指标"""
        metrics = self.request_metrics[endpoint_key]
        
        # 更新基本统计
        metrics['count'] += 1
        metrics['total_duration'] += duration_ms
        metrics['min_duration'] = min(metrics['min_duration'], duration_ms)
        metrics['max_duration'] = max(metrics['max_duration'], duration_ms)
        
        if is_error or status_code >= 400:
            metrics['error_count'] += 1
        
        # 计算平均响应时间
        metrics['avg_duration'] = metrics['total_duration'] / metrics['count']
        metrics['error_rate'] = (metrics['error_count'] / metrics['count']) * 100
        
        # 更新最后更新时间
        metrics['last_updated'] = datetime.now().isoformat()
        
        # 资源监控
        if self.enable_resource_monitoring and start_memory is not None:
            current_memory = self._get_memory_usage()
            memory_delta = current_memory - start_memory
            
            if memory_delta > 100:  # 内存增长超过100MB
                await self._handle_memory_spike(endpoint_key, memory_delta, duration_ms)
    
    async def _handle_slow_request(self, endpoint_key: str, duration_ms: float, 
                                 status_code: int, request: Request):
        """处理慢请求"""
        slow_request_info = {
            'endpoint': endpoint_key,
            'duration_ms': duration_ms,
            'status_code': status_code,
            'timestamp': datetime.now().isoformat(),
            'query_params': dict(request.query_params) if request.query_params else {},
            'user_agent': request.headers.get('user-agent', ''),
            'client_ip': request.client.host if request.client else 'unknown'
        }
        
        self.slow_requests.append(slow_request_info)
        
        # 记录慢请求日志
        await self.logger.warning(
            f"Slow request detected: {endpoint_key} took {duration_ms:.2f}ms",
            category=LogCategory.PERFORMANCE,
            duration_ms=duration_ms,
            tags={'endpoint': endpoint_key, 'status_code': status_code}
        )
        
        # 生成性能告警
        if duration_ms > self.slow_request_threshold * 2:  # 超过阈值2倍
            await self._create_performance_alert(
                'VERY_SLOW_REQUEST',
                f"Extremely slow request: {endpoint_key} took {duration_ms:.2f}ms",
                {'endpoint': endpoint_key, 'duration_ms': duration_ms}
            )
    
    async def _handle_memory_spike(self, endpoint_key: str, memory_delta: float, duration_ms: float):
        """处理内存激增"""
        await self.logger.warning(
            f"Memory spike detected: {endpoint_key} used {memory_delta:.1f}MB additional memory",
            category=LogCategory.PERFORMANCE,
            tags={'endpoint': endpoint_key, 'memory_delta_mb': memory_delta}
        )
        
        await self._create_performance_alert(
            'MEMORY_SPIKE',
            f"High memory usage: {endpoint_key} used {memory_delta:.1f}MB",
            {'endpoint': endpoint_key, 'memory_delta_mb': memory_delta, 'duration_ms': duration_ms}
        )
    
    async def _create_performance_alert(self, alert_type: str, message: str, context: Dict[str, Any]):
        """创建性能告警"""
        alert = {
            'type': alert_type,
            'message': message,
            'context': context,
            'timestamp': datetime.now().isoformat(),
            'severity': self._get_alert_severity(alert_type)
        }
        
        self.performance_alerts.append(alert)
        
        # 记录告警日志
        await self.logger.error(
            f"Performance Alert: {message}",
            category=LogCategory.PERFORMANCE,
            tags={'alert_type': alert_type, 'severity': alert['severity']}
        )
    
    def _get_alert_severity(self, alert_type: str) -> str:
        """获取告警严重程度"""
        severity_map = {
            'SLOW_REQUEST': 'medium',
            'VERY_SLOW_REQUEST': 'high',
            'MEMORY_SPIKE': 'high',
            'HIGH_ERROR_RATE': 'high',
            'SYSTEM_RESOURCE_HIGH': 'critical'
        }
        return severity_map.get(alert_type, 'medium')
    
    def _get_memory_usage(self) -> float:
        """获取当前内存使用量（MB）"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)  # 转换为MB
        except:
            return 0.0
    
    async def _collect_system_resources(self):
        """收集系统资源使用情况"""
        now = datetime.now()
        if (now - self.last_resource_check).total_seconds() < 10:  # 10秒采样一次
            return
        
        try:
            cpu_usage = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            resource_sample = {
                'timestamp': now.isoformat(),
                'cpu_usage': cpu_usage,
                'memory_usage': memory.percent,
                'memory_available_gb': memory.available / (1024**3),
                'disk_usage': disk.percent,
                'disk_free_gb': disk.free / (1024**3)
            }
            
            self.resource_samples.append(resource_sample)
            self.last_resource_check = now
            
            # 检查资源使用告警
            await self._check_resource_alerts(resource_sample)
            
        except Exception as e:
            await self.logger.warning(f"Failed to collect system resources: {str(e)}")
    
    async def _check_resource_alerts(self, resource_sample: Dict[str, Any]):
        """检查资源使用告警"""
        if resource_sample['cpu_usage'] > 90:
            await self._create_performance_alert(
                'SYSTEM_RESOURCE_HIGH',
                f"High CPU usage: {resource_sample['cpu_usage']:.1f}%",
                {'resource': 'cpu', 'value': resource_sample['cpu_usage']}
            )
        
        if resource_sample['memory_usage'] > 90:
            await self._create_performance_alert(
                'SYSTEM_RESOURCE_HIGH',
                f"High memory usage: {resource_sample['memory_usage']:.1f}%",
                {'resource': 'memory', 'value': resource_sample['memory_usage']}
            )
        
        if resource_sample['disk_usage'] > 95:
            await self._create_performance_alert(
                'SYSTEM_RESOURCE_HIGH',
                f"High disk usage: {resource_sample['disk_usage']:.1f}%",
                {'resource': 'disk', 'value': resource_sample['disk_usage']}
            )
    
    # 数据查询方法
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        total_requests = sum(m['count'] for m in self.request_metrics.values())
        total_errors = sum(m['error_count'] for m in self.request_metrics.values())
        
        avg_response_times = [m['avg_duration'] for m in self.request_metrics.values() if m['count'] > 0]
        overall_avg_response_time = sum(avg_response_times) / len(avg_response_times) if avg_response_times else 0
        
        return {
            'total_requests': total_requests,
            'total_errors': total_errors,
            'global_error_rate': (total_errors / total_requests * 100) if total_requests > 0 else 0,
            'overall_avg_response_time': overall_avg_response_time,
            'slow_requests_count': len(self.slow_requests),
            'performance_alerts_count': len(self.performance_alerts),
            'monitored_endpoints': len(self.request_metrics)
        }
    
    def get_endpoint_metrics(self, limit: int = 20) -> Dict[str, Any]:
        """获取端点性能指标"""
        # 按请求数量排序
        sorted_metrics = sorted(
            self.request_metrics.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        
        return dict(sorted_metrics[:limit])
    
    def get_slow_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取慢请求列表"""
        return list(self.slow_requests)[-limit:]
    
    def get_performance_alerts(self, limit: int = 30) -> List[Dict[str, Any]]:
        """获取性能告警"""
        return list(self.performance_alerts)[-limit:]
    
    def get_system_resource_history(self, limit: int = 60) -> List[Dict[str, Any]]:
        """获取系统资源使用历史"""
        return list(self.resource_samples)[-limit:]
    
    def clear_metrics(self):
        """清空性能指标"""
        self.request_metrics.clear()
        self.slow_requests.clear()
        self.performance_alerts.clear()
        self.resource_samples.clear()


# 全局性能监控实例
performance_monitor: Optional[PerformanceMonitor] = None


def create_performance_monitor(slow_request_threshold: float = 5000, 
                             enable_resource_monitoring: bool = True) -> PerformanceMonitor:
    """创建性能监控中间件实例"""
    global performance_monitor
    performance_monitor = PerformanceMonitor(
        None, slow_request_threshold, enable_resource_monitoring
    )
    return performance_monitor


def get_performance_monitor() -> Optional[PerformanceMonitor]:
    """获取全局性能监控实例"""
    return performance_monitor