#!/usr/bin/env python3
"""
调试工具和开发环境支持
提供详细的调试信息、性能分析和开发者友好的错误展示
"""

import os
import json
import time
import psutil
import traceback
import inspect
import sys
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextvars import ContextVar

from fastapi import Request
from middleware.error_tracking import error_tracker, trace_context


# 调试上下文
debug_context: ContextVar[str] = ContextVar('debug_context', default='')


@dataclass
class SystemMetrics:
    """系统性能指标"""
    cpu_usage: float
    memory_usage: float
    memory_available: float
    disk_usage: float
    disk_free: float
    load_average: Optional[List[float]] = None
    process_count: int = 0
    python_version: str = ""
    
    def __post_init__(self):
        if not self.python_version:
            self.python_version = sys.version
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'memory_available_gb': self.memory_available,
            'disk_usage': self.disk_usage,
            'disk_free_gb': self.disk_free,
            'load_average': self.load_average,
            'process_count': self.process_count,
            'python_version': self.python_version
        }


@dataclass
class RequestProfile:
    """请求性能分析"""
    request_id: str
    method: str
    path: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status_code: Optional[int] = None
    response_size: Optional[int] = None
    
    # 性能细节
    db_queries: List[Dict[str, Any]] = field(default_factory=list)
    cache_operations: List[Dict[str, Any]] = field(default_factory=list)
    external_api_calls: List[Dict[str, Any]] = field(default_factory=list)
    
    # 系统资源使用
    memory_peak: Optional[float] = None
    cpu_time: Optional[float] = None
    
    def finish(self, status_code: int, response_size: int = 0):
        """完成请求分析"""
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.status_code = status_code
        self.response_size = response_size
    
    def add_db_query(self, query_type: str, table: str, duration_ms: float, rows: int = 0):
        """添加数据库查询记录"""
        self.db_queries.append({
            'type': query_type,
            'table': table,
            'duration_ms': duration_ms,
            'rows': rows,
            'timestamp': datetime.now().isoformat()
        })
    
    def add_cache_operation(self, operation: str, key: str, duration_ms: float, hit: bool = False):
        """添加缓存操作记录"""
        self.cache_operations.append({
            'operation': operation,
            'key': key,
            'duration_ms': duration_ms,
            'hit': hit,
            'timestamp': datetime.now().isoformat()
        })
    
    def add_external_api_call(self, url: str, method: str, duration_ms: float, status_code: int):
        """添加外部API调用记录"""
        self.external_api_calls.append({
            'url': url,
            'method': method,
            'duration_ms': duration_ms,
            'status_code': status_code,
            'timestamp': datetime.now().isoformat()
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'request_id': self.request_id,
            'method': self.method,
            'path': self.path,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_ms': self.duration_ms,
            'status_code': self.status_code,
            'response_size': self.response_size,
            'db_queries': self.db_queries,
            'cache_operations': self.cache_operations,
            'external_api_calls': self.external_api_calls,
            'memory_peak': self.memory_peak,
            'cpu_time': self.cpu_time
        }


@dataclass
class ErrorAnalysis:
    """错误分析信息"""
    error_id: str
    error_type: str
    error_message: str
    stack_trace: str
    local_variables: Dict[str, Any]
    function_context: Dict[str, Any]
    request_context: Optional[Dict[str, Any]] = None
    similar_errors: List[str] = field(default_factory=list)
    suggested_fixes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'error_id': self.error_id,
            'error_type': self.error_type,
            'error_message': self.error_message,
            'stack_trace': self.stack_trace,
            'local_variables': self.local_variables,
            'function_context': self.function_context,
            'request_context': self.request_context,
            'similar_errors': self.similar_errors,
            'suggested_fixes': self.suggested_fixes
        }


class DebugProfiler:
    """调试和性能分析器"""
    
    def __init__(self):
        self.is_debug_mode = os.getenv("DEBUG", "false").lower() == "true"
        self.is_development = os.getenv("ENVIRONMENT", "production").lower() in ["development", "dev"]
        self.enable_profiling = os.getenv("ENABLE_PROFILING", "false").lower() == "true"
        
        # 性能数据收集
        self.request_profiles: Dict[str, RequestProfile] = {}
        self.system_metrics_history: deque = deque(maxlen=100)
        self.slow_requests: deque = deque(maxlen=50)
        self.error_analyses: Dict[str, ErrorAnalysis] = {}
        
        # 统计数据
        self.endpoint_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'total_requests': 0,
            'total_duration_ms': 0,
            'avg_duration_ms': 0,
            'error_count': 0,
            'success_rate': 100.0
        })
        
        # 性能基准
        self.performance_thresholds = {
            'slow_request_ms': 5000,
            'very_slow_request_ms': 10000,
            'high_memory_mb': 500,
            'high_cpu_percent': 80
        }
    
    def start_request_profiling(self, request_id: str, method: str, path: str) -> RequestProfile:
        """开始请求分析"""
        profile = RequestProfile(
            request_id=request_id,
            method=method,
            path=path,
            start_time=datetime.now()
        )
        
        if self.enable_profiling:
            self.request_profiles[request_id] = profile
        
        return profile
    
    def finish_request_profiling(self, request_id: str, status_code: int, response_size: int = 0):
        """完成请求分析"""
        if request_id not in self.request_profiles:
            return
        
        profile = self.request_profiles[request_id]
        profile.finish(status_code, response_size)
        
        # 更新端点统计
        endpoint_key = f"{profile.method} {profile.path}"
        stats = self.endpoint_stats[endpoint_key]
        stats['total_requests'] += 1
        stats['total_duration_ms'] += profile.duration_ms or 0
        stats['avg_duration_ms'] = stats['total_duration_ms'] / stats['total_requests']
        
        if status_code >= 400:
            stats['error_count'] += 1
        
        stats['success_rate'] = ((stats['total_requests'] - stats['error_count']) / 
                               stats['total_requests'] * 100)
        
        # 检查慢请求
        if profile.duration_ms and profile.duration_ms > self.performance_thresholds['slow_request_ms']:
            self.slow_requests.append(profile.to_dict())
        
        # 清理完成的profile
        del self.request_profiles[request_id]
    
    def analyze_error(self, error: Exception, request_id: str, 
                     request_context: Optional[Dict[str, Any]] = None) -> ErrorAnalysis:
        """深度错误分析"""
        error_id = f"{request_id}_{int(time.time())}"
        
        # 获取调用栈
        tb = traceback.extract_tb(error.__traceback__)
        stack_trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        
        # 分析局部变量（仅在调试模式下）
        local_variables = {}
        function_context = {}
        
        if self.is_debug_mode and error.__traceback__:
            frame = error.__traceback__.tb_frame
            try:
                # 获取错误发生处的局部变量
                local_variables = {
                    k: self._sanitize_variable(v) 
                    for k, v in frame.f_locals.items() 
                    if not k.startswith('_')
                }
                
                # 获取函数上下文
                function_context = {
                    'function_name': frame.f_code.co_name,
                    'filename': frame.f_code.co_filename,
                    'line_number': frame.f_lineno,
                    'argument_names': frame.f_code.co_varnames
                }
            except Exception:
                # 避免在错误分析中出现新的错误
                pass
        
        # 生成修复建议
        suggested_fixes = self._generate_fix_suggestions(error, stack_trace)
        
        error_analysis = ErrorAnalysis(
            error_id=error_id,
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=stack_trace,
            local_variables=local_variables,
            function_context=function_context,
            request_context=request_context,
            suggested_fixes=suggested_fixes
        )
        
        if self.is_debug_mode:
            self.error_analyses[error_id] = error_analysis
        
        return error_analysis
    
    def _sanitize_variable(self, value: Any) -> Any:
        """净化变量值，避免敏感信息泄露"""
        if isinstance(value, str):
            # 过滤敏感字符串
            sensitive_patterns = ['password', 'token', 'key', 'secret', 'auth']
            value_lower = value.lower()
            if any(pattern in value_lower for pattern in sensitive_patterns):
                return '[FILTERED]'
            # 限制字符串长度
            return value[:200] + '...' if len(value) > 200 else value
        elif isinstance(value, (int, float, bool, type(None))):
            return value
        elif isinstance(value, (list, tuple)):
            return [self._sanitize_variable(item) for item in value[:10]]  # 限制数组长度
        elif isinstance(value, dict):
            return {
                k: self._sanitize_variable(v) 
                for k, v in list(value.items())[:10]  # 限制字典大小
                if not str(k).lower() in ['password', 'token', 'key', 'secret']
            }
        else:
            return str(type(value).__name__)
    
    def _generate_fix_suggestions(self, error: Exception, stack_trace: str) -> List[str]:
        """生成错误修复建议"""
        suggestions = []
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # 基于错误类型的建议
        if error_type == "FileNotFoundError":
            suggestions.append("检查文件路径是否正确")
            suggestions.append("确认文件是否存在")
            suggestions.append("检查文件权限")
        
        elif error_type == "PermissionError":
            suggestions.append("检查文件或目录权限")
            suggestions.append("确认当前用户有足够的访问权限")
        
        elif error_type == "ConnectionError":
            suggestions.append("检查网络连接")
            suggestions.append("确认目标服务是否可达")
            suggestions.append("检查防火墙设置")
        
        elif error_type == "TimeoutError":
            suggestions.append("增加超时时间")
            suggestions.append("检查网络延迟")
            suggestions.append("优化请求处理逻辑")
        
        elif "memory" in error_message or "out of memory" in error_message:
            suggestions.append("减少内存使用")
            suggestions.append("检查是否存在内存泄漏")
            suggestions.append("增加系统内存")
        
        elif "database" in error_message or "sql" in error_message:
            suggestions.append("检查数据库连接")
            suggestions.append("验证SQL语句语法")
            suggestions.append("检查数据库权限")
        
        elif "validation" in error_message:
            suggestions.append("检查输入数据格式")
            suggestions.append("验证必填字段")
            suggestions.append("确认数据类型正确")
        
        # 基于错误消息的建议
        if "module" in error_message and "not found" in error_message:
            suggestions.append("安装缺失的Python包")
            suggestions.append("检查Python环境和路径")
        
        if "json" in error_message:
            suggestions.append("检查JSON格式是否正确")
            suggestions.append("验证JSON数据完整性")
        
        return suggestions[:5]  # 限制建议数量
    
    def get_system_metrics(self) -> SystemMetrics:
        """获取系统性能指标"""
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            metrics = SystemMetrics(
                cpu_usage=psutil.cpu_percent(interval=0.1),
                memory_usage=memory.percent,
                memory_available=memory.available / (1024**3),  # GB
                disk_usage=disk.percent,
                disk_free=disk.free / (1024**3),  # GB
                process_count=len(psutil.pids())
            )
            
            # 获取系统负载（仅Linux/Unix）
            if hasattr(os, 'getloadavg'):
                metrics.load_average = list(os.getloadavg())
            
            # 缓存指标历史
            self.system_metrics_history.append({
                'timestamp': datetime.now().isoformat(),
                'metrics': metrics.to_dict()
            })
            
            return metrics
        except Exception:
            # 返回默认值以避免影响主流程
            return SystemMetrics(0, 0, 0, 0, 0)
    
    def get_debug_info(self, request_id: Optional[str] = None) -> Dict[str, Any]:
        """获取调试信息"""
        if not self.is_debug_mode:
            return {'debug_mode': False}
        
        debug_info = {
            'debug_mode': True,
            'development_mode': self.is_development,
            'profiling_enabled': self.enable_profiling,
            'system_metrics': self.get_system_metrics().to_dict(),
            'endpoint_statistics': dict(self.endpoint_stats),
            'slow_requests_count': len(self.slow_requests),
            'error_analyses_count': len(self.error_analyses)
        }
        
        # 添加请求特定信息
        if request_id:
            profile = self.request_profiles.get(request_id)
            if profile:
                debug_info['current_request_profile'] = profile.to_dict()
            
            # 添加调用链信息
            if error_tracker:
                trace_id = trace_context.get('')
                if trace_id:
                    trace = error_tracker.get_trace(trace_id)
                    if trace:
                        debug_info['trace_info'] = trace.to_dict()
        
        return debug_info
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        return {
            'slow_requests': list(self.slow_requests),
            'endpoint_stats': dict(self.endpoint_stats),
            'system_metrics_history': list(self.system_metrics_history)[-10:],
            'performance_summary': {
                'total_endpoints': len(self.endpoint_stats),
                'slow_requests_count': len(self.slow_requests),
                'avg_response_time': self._calculate_global_avg_response_time(),
                'error_rate': self._calculate_global_error_rate()
            }
        }
    
    def _calculate_global_avg_response_time(self) -> float:
        """计算全局平均响应时间"""
        if not self.endpoint_stats:
            return 0.0
        
        total_time = sum(stats['total_duration_ms'] for stats in self.endpoint_stats.values())
        total_requests = sum(stats['total_requests'] for stats in self.endpoint_stats.values())
        
        return total_time / total_requests if total_requests > 0 else 0.0
    
    def _calculate_global_error_rate(self) -> float:
        """计算全局错误率"""
        if not self.endpoint_stats:
            return 0.0
        
        total_errors = sum(stats['error_count'] for stats in self.endpoint_stats.values())
        total_requests = sum(stats['total_requests'] for stats in self.endpoint_stats.values())
        
        return (total_errors / total_requests * 100) if total_requests > 0 else 0.0
    
    def clear_debug_data(self):
        """清除调试数据"""
        self.request_profiles.clear()
        self.system_metrics_history.clear()
        self.slow_requests.clear()
        self.error_analyses.clear()
        self.endpoint_stats.clear()


# 全局调试分析器实例
debug_profiler = DebugProfiler()


# 装饰器和上下文管理器
def debug_trace(operation_name: str):
    """调试追踪装饰器"""
    def decorator(func: Callable) -> Callable:
        if not debug_profiler.is_debug_mode:
            return func  # 生产环境直接返回原函数
        
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # 记录性能信息
                if duration_ms > debug_profiler.performance_thresholds['slow_request_ms']:
                    debug_profiler.slow_requests.append({
                        'operation': operation_name,
                        'function': func.__name__,
                        'duration_ms': duration_ms,
                        'timestamp': datetime.now().isoformat()
                    })
                
                return result
            except Exception as e:
                # 分析错误
                error_analysis = debug_profiler.analyze_error(
                    e, f"trace_{int(time.time())}", 
                    {'operation': operation_name, 'function': func.__name__}
                )
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                if duration_ms > debug_profiler.performance_thresholds['slow_request_ms']:
                    debug_profiler.slow_requests.append({
                        'operation': operation_name,
                        'function': func.__name__,
                        'duration_ms': duration_ms,
                        'timestamp': datetime.now().isoformat()
                    })
                
                return result
            except Exception as e:
                error_analysis = debug_profiler.analyze_error(
                    e, f"trace_{int(time.time())}", 
                    {'operation': operation_name, 'function': func.__name__}
                )
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# 便捷函数
def is_debug_mode() -> bool:
    """检查是否为调试模式"""
    return debug_profiler.is_debug_mode


def is_development_mode() -> bool:
    """检查是否为开发模式"""
    return debug_profiler.is_development


def get_debug_info(request_id: Optional[str] = None) -> Dict[str, Any]:
    """获取调试信息"""
    return debug_profiler.get_debug_info(request_id)


def should_show_sensitive_info() -> bool:
    """判断是否应该显示敏感信息"""
    return debug_profiler.is_debug_mode and debug_profiler.is_development