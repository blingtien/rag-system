#!/usr/bin/env python3
"""
错误追踪和调用链分析系统
提供跨服务的错误关联和调试支持
"""

import os
import json
import uuid
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from contextvars import ContextVar

# 调用链追踪上下文
trace_context: ContextVar[str] = ContextVar('trace_context', default='')
span_context: ContextVar[str] = ContextVar('span_context', default='')


class TraceLevel(Enum):
    """追踪级别"""
    DEBUG = "debug"
    INFO = "info" 
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SpanType(Enum):
    """跨度类型"""
    HTTP_REQUEST = "http_request"
    DATABASE_QUERY = "database_query"
    EXTERNAL_API = "external_api"
    DOCUMENT_PROCESSING = "document_processing"
    BATCH_OPERATION = "batch_operation"
    WEBSOCKET_CONNECTION = "websocket_connection"
    CACHE_OPERATION = "cache_operation"
    FILE_OPERATION = "file_operation"


@dataclass
class TraceSpan:
    """调用链跨度"""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    operation_name: str
    span_type: SpanType
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: str = "started"  # started, success, error
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    stack_trace: Optional[str] = None
    
    def finish(self, status: str = "success", error: Optional[str] = None, stack_trace: Optional[str] = None):
        """结束跨度"""
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.status = status
        if error:
            self.error = error
        if stack_trace:
            self.stack_trace = stack_trace
    
    def add_log(self, level: str, message: str, fields: Optional[Dict[str, Any]] = None):
        """添加日志"""
        self.logs.append({
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            'fields': fields or {}
        })
    
    def add_tag(self, key: str, value: Any):
        """添加标签"""
        self.tags[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'span_id': self.span_id,
            'trace_id': self.trace_id,
            'parent_span_id': self.parent_span_id,
            'operation_name': self.operation_name,
            'span_type': self.span_type.value,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_ms': self.duration_ms,
            'status': self.status,
            'tags': self.tags,
            'logs': self.logs,
            'error': self.error,
            'stack_trace': self.stack_trace
        }


@dataclass
class Trace:
    """完整的调用链"""
    trace_id: str
    spans: Dict[str, TraceSpan] = field(default_factory=dict)
    root_span_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    total_spans: int = 0
    error_spans: int = 0
    status: str = "active"  # active, completed, error
    
    def add_span(self, span: TraceSpan):
        """添加跨度"""
        self.spans[span.span_id] = span
        self.total_spans = len(self.spans)
        
        if not self.root_span_id and not span.parent_span_id:
            self.root_span_id = span.span_id
            self.start_time = span.start_time
        
        if span.status == "error":
            self.error_spans += 1
            self.status = "error"
    
    def get_span(self, span_id: str) -> Optional[TraceSpan]:
        """获取跨度"""
        return self.spans.get(span_id)
    
    def get_root_span(self) -> Optional[TraceSpan]:
        """获取根跨度"""
        return self.spans.get(self.root_span_id) if self.root_span_id else None
    
    def get_span_hierarchy(self) -> Dict[str, Any]:
        """获取跨度层次结构"""
        hierarchy = {}
        
        def build_children(span_id: str) -> List[Dict[str, Any]]:
            children = []
            for span in self.spans.values():
                if span.parent_span_id == span_id:
                    child_data = span.to_dict()
                    child_data['children'] = build_children(span.span_id)
                    children.append(child_data)
            return children
        
        if self.root_span_id:
            root_span = self.spans[self.root_span_id]
            hierarchy = root_span.to_dict()
            hierarchy['children'] = build_children(self.root_span_id)
        
        return hierarchy
    
    def complete_trace(self):
        """完成调用链"""
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        
        if self.status != "error":
            self.status = "completed"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'trace_id': self.trace_id,
            'root_span_id': self.root_span_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_ms': self.duration_ms,
            'total_spans': self.total_spans,
            'error_spans': self.error_spans,
            'status': self.status,
            'hierarchy': self.get_span_hierarchy()
        }


class ErrorTracker:
    """
    错误追踪器
    
    功能:
    1. 分布式调用链追踪
    2. 错误关联分析
    3. 性能监控
    4. 调试信息收集
    """
    
    def __init__(self, max_traces: int = 1000, max_trace_age_hours: int = 24):
        self.logger = logging.getLogger(__name__)
        self.traces: Dict[str, Trace] = {}
        self.active_spans: Dict[str, TraceSpan] = {}
        self.max_traces = max_traces
        self.max_trace_age = timedelta(hours=max_trace_age_hours)
        
        # 错误统计
        self.error_patterns: Dict[str, int] = defaultdict(int)
        self.slow_operations: deque = deque(maxlen=100)
        self.frequent_errors: deque = deque(maxlen=100)
        
        # 定期清理
        self._last_cleanup = datetime.now()
        
    def start_trace(self, operation_name: str, span_type: SpanType = SpanType.HTTP_REQUEST, 
                   trace_id: Optional[str] = None, parent_span_id: Optional[str] = None,
                   tags: Optional[Dict[str, Any]] = None) -> TraceSpan:
        """开始新的调用链或跨度"""
        if not trace_id:
            trace_id = str(uuid.uuid4())
        
        span_id = str(uuid.uuid4())
        
        # 创建跨度
        span = TraceSpan(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            span_type=span_type,
            start_time=datetime.now(),
            tags=tags or {}
        )
        
        # 设置上下文
        trace_context.set(trace_id)
        span_context.set(span_id)
        
        # 获取或创建调用链
        if trace_id not in self.traces:
            self.traces[trace_id] = Trace(trace_id=trace_id)
        
        # 添加跨度到调用链
        self.traces[trace_id].add_span(span)
        self.active_spans[span_id] = span
        
        # 定期清理（同步调用）
        if datetime.now() - self._last_cleanup > timedelta(minutes=5):
            try:
                import asyncio
                asyncio.create_task(self._periodic_cleanup())
            except:
                pass  # 如果无法创建task，跳过清理
        
        return span
    
    def get_current_span(self) -> Optional[TraceSpan]:
        """获取当前跨度"""
        span_id = span_context.get('')
        return self.active_spans.get(span_id) if span_id else None
    
    def get_current_trace_id(self) -> Optional[str]:
        """获取当前调用链ID"""
        return trace_context.get('') or None
    
    def finish_span(self, span_id: Optional[str] = None, status: str = "success", 
                   error: Optional[str] = None, stack_trace: Optional[str] = None):
        """结束跨度"""
        if not span_id:
            span_id = span_context.get('')
        
        if span_id and span_id in self.active_spans:
            span = self.active_spans[span_id]
            span.finish(status, error, stack_trace)
            
            # 记录性能和错误统计
            if span.duration_ms and span.duration_ms > 5000:  # 超过5秒的慢操作
                self.slow_operations.append({
                    'trace_id': span.trace_id,
                    'span_id': span.span_id,
                    'operation': span.operation_name,
                    'duration_ms': span.duration_ms,
                    'timestamp': datetime.now().isoformat()
                })
            
            if status == "error":
                error_pattern = f"{span.span_type.value}:{span.operation_name}"
                self.error_patterns[error_pattern] += 1
                
                self.frequent_errors.append({
                    'trace_id': span.trace_id,
                    'span_id': span.span_id,
                    'operation': span.operation_name,
                    'error': error,
                    'timestamp': datetime.now().isoformat()
                })
            
            # 从活跃跨度中移除
            del self.active_spans[span_id]
            
            # 检查调用链是否完成
            trace = self.traces.get(span.trace_id)
            if trace and all(s.status != "started" for s in trace.spans.values()):
                trace.complete_trace()
    
    def add_span_log(self, message: str, level: str = "info", 
                    fields: Optional[Dict[str, Any]] = None, span_id: Optional[str] = None):
        """向跨度添加日志"""
        if not span_id:
            span_id = span_context.get('')
        
        if span_id and span_id in self.active_spans:
            self.active_spans[span_id].add_log(level, message, fields)
    
    def add_span_tag(self, key: str, value: Any, span_id: Optional[str] = None):
        """向跨度添加标签"""
        if not span_id:
            span_id = span_context.get('')
        
        if span_id and span_id in self.active_spans:
            self.active_spans[span_id].add_tag(key, value)
    
    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """获取调用链"""
        return self.traces.get(trace_id)
    
    def get_trace_by_error(self, error_pattern: str) -> List[Trace]:
        """根据错误模式获取相关调用链"""
        matching_traces = []
        for trace in self.traces.values():
            for span in trace.spans.values():
                if span.error and error_pattern.lower() in span.error.lower():
                    matching_traces.append(trace)
                    break
        return matching_traces
    
    def get_slow_operations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取慢操作列表"""
        return list(self.slow_operations)[-limit:]
    
    def get_frequent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取频繁错误列表"""
        return list(self.frequent_errors)[-limit:]
    
    def get_error_patterns(self) -> Dict[str, int]:
        """获取错误模式统计"""
        return dict(self.error_patterns)
    
    def get_active_traces_count(self) -> int:
        """获取活跃调用链数量"""
        return len([t for t in self.traces.values() if t.status == "active"])
    
    def get_traces_summary(self) -> Dict[str, Any]:
        """获取调用链摘要"""
        total_traces = len(self.traces)
        error_traces = len([t for t in self.traces.values() if t.status == "error"])
        active_traces = len([t for t in self.traces.values() if t.status == "active"])
        
        avg_duration = 0
        if self.traces:
            durations = [t.duration_ms for t in self.traces.values() if t.duration_ms]
            if durations:
                avg_duration = sum(durations) / len(durations)
        
        return {
            'total_traces': total_traces,
            'error_traces': error_traces,
            'active_traces': active_traces,
            'success_rate': ((total_traces - error_traces) / total_traces * 100) if total_traces > 0 else 100,
            'avg_duration_ms': avg_duration,
            'active_spans': len(self.active_spans),
            'error_patterns': len(self.error_patterns)
        }
    
    async def _periodic_cleanup(self):
        """定期清理过期数据"""
        now = datetime.now()
        if (now - self._last_cleanup) < timedelta(minutes=10):
            return
        
        self._last_cleanup = now
        cutoff_time = now - self.max_trace_age
        
        # 清理过期调用链
        expired_traces = []
        for trace_id, trace in self.traces.items():
            if trace.start_time and trace.start_time < cutoff_time:
                expired_traces.append(trace_id)
        
        for trace_id in expired_traces:
            del self.traces[trace_id]
        
        # 限制调用链数量
        if len(self.traces) > self.max_traces:
            # 保留最新的调用链
            sorted_traces = sorted(
                self.traces.items(),
                key=lambda x: x[1].start_time or datetime.min,
                reverse=True
            )
            self.traces = dict(sorted_traces[:self.max_traces])
        
        self.logger.debug(f"Cleaned up {len(expired_traces)} expired traces")
    
    def export_trace_data(self, trace_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """导出调用链数据"""
        if trace_ids:
            traces = [self.traces[tid] for tid in trace_ids if tid in self.traces]
        else:
            traces = list(self.traces.values())
        
        return [trace.to_dict() for trace in traces]
    
    def clear_all_data(self):
        """清除所有数据"""
        self.traces.clear()
        self.active_spans.clear()
        self.error_patterns.clear()
        self.slow_operations.clear()
        self.frequent_errors.clear()


# 全局错误追踪器实例
error_tracker = ErrorTracker()


# 上下文管理器和装饰器
class trace_span:
    """跨度追踪上下文管理器"""
    
    def __init__(self, operation_name: str, span_type: SpanType = SpanType.HTTP_REQUEST,
                 tags: Optional[Dict[str, Any]] = None):
        self.operation_name = operation_name
        self.span_type = span_type
        self.tags = tags
        self.span: Optional[TraceSpan] = None
    
    async def __aenter__(self) -> TraceSpan:
        self.span = error_tracker.start_trace(
            self.operation_name, 
            self.span_type,
            trace_context.get(''),
            span_context.get(''),
            self.tags
        )
        return self.span
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            status = "error" if exc_type else "success"
            error = str(exc_val) if exc_val else None
            stack_trace = None
            
            if exc_type:
                import traceback
                stack_trace = ''.join(traceback.format_exception(exc_type, exc_val, exc_tb))
            
            error_tracker.finish_span(
                self.span.span_id, 
                status, 
                error, 
                stack_trace
            )


def traced_operation(operation_name: str, span_type: SpanType = SpanType.HTTP_REQUEST):
    """调用链追踪装饰器"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                async with trace_span(operation_name, span_type):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                # 同步函数的简单追踪
                span = error_tracker.start_trace(operation_name, span_type)
                try:
                    result = func(*args, **kwargs)
                    error_tracker.finish_span(span.span_id, "success")
                    return result
                except Exception as e:
                    error_tracker.finish_span(span.span_id, "error", str(e))
                    raise
            return sync_wrapper
    return decorator