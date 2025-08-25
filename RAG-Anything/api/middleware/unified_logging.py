#!/usr/bin/env python3
"""
统一日志系统
整合WebSocket日志处理、智能日志处理和错误追踪
提供结构化、实时、可追踪的日志记录
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Set, Callable, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from contextvars import ContextVar

# 导入现有的日志组件
from websocket_log_handler import websocket_log_handler, get_log_summary, get_core_progress, clear_logs
from middleware.error_tracking import error_tracker, trace_context, span_context

# 日志上下文
logger_context: ContextVar[str] = ContextVar('logger_context', default='')


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogCategory(Enum):
    """日志分类"""
    SYSTEM = "system"
    REQUEST = "request"
    PROCESSING = "processing"
    DATABASE = "database"
    CACHE = "cache"
    WEBSOCKET = "websocket"
    BATCH = "batch"
    ERROR = "error"
    PERFORMANCE = "performance"
    SECURITY = "security"


@dataclass
class LogEntry:
    """统一日志条目"""
    log_id: str
    timestamp: datetime
    level: LogLevel
    category: LogCategory
    message: str
    logger_name: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    operation: Optional[str] = None
    duration_ms: Optional[float] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    error_details: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'log_id': self.log_id,
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value,
            'category': self.category.value,
            'message': self.message,
            'logger_name': self.logger_name,
            'trace_id': self.trace_id,
            'span_id': self.span_id,
            'request_id': self.request_id,
            'user_id': self.user_id,
            'operation': self.operation,
            'duration_ms': self.duration_ms,
            'tags': self.tags,
            'context': self.context,
            'error_details': self.error_details,
            'stack_trace': self.stack_trace
        }
    
    def to_websocket_format(self) -> Dict[str, Any]:
        """转换为WebSocket格式"""
        return {
            'type': 'log',
            'id': self.log_id,
            'level': self.level.value,
            'category': self.category.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'trace_id': self.trace_id,
            'span_id': self.span_id,
            'operation': self.operation,
            'duration_ms': self.duration_ms,
            'tags': self.tags
        }


class UnifiedLogger:
    """
    统一日志记录器
    
    功能:
    1. 结构化日志记录
    2. 调用链关联
    3. WebSocket实时推送
    4. 智能日志过滤
    5. 性能监控
    6. 错误聚合
    """
    
    def __init__(self, name: str = __name__):
        self.name = name
        self.logger = logging.getLogger(name)
        self.log_handlers: List[Callable] = []
        self.websocket_handler = websocket_log_handler
        
        # 日志缓存和过滤
        self.recent_logs: List[LogEntry] = []
        self.max_recent_logs = 1000
        self.duplicate_log_cache: Dict[str, datetime] = {}
        self.duplicate_threshold_seconds = 60
        
        # 性能监控
        self.slow_operations: List[Dict[str, Any]] = []
        self.error_aggregation: Dict[str, Dict[str, Any]] = {}
        
    def add_handler(self, handler: Callable[[LogEntry], None]):
        """添加日志处理器"""
        self.log_handlers.append(handler)
    
    def remove_handler(self, handler: Callable[[LogEntry], None]):
        """移除日志处理器"""
        if handler in self.log_handlers:
            self.log_handlers.remove(handler)
    
    def _create_log_entry(
        self,
        level: LogLevel,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        operation: Optional[str] = None,
        duration_ms: Optional[float] = None,
        tags: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        error_details: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None
    ) -> LogEntry:
        """创建日志条目"""
        import uuid
        
        # 获取追踪信息
        trace_id = trace_context.get('') if trace_context else None
        span_id = span_context.get('') if span_context else None
        request_id = logger_context.get('') if logger_context else None
        
        # 从错误追踪器获取更多上下文
        current_span = error_tracker.get_current_span()
        if current_span:
            if not operation:
                operation = current_span.operation_name
            if not context:
                context = current_span.tags.copy()
        
        log_entry = LogEntry(
            log_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            level=level,
            category=category,
            message=message,
            logger_name=self.name,
            trace_id=trace_id,
            span_id=span_id,
            request_id=request_id,
            operation=operation,
            duration_ms=duration_ms,
            tags=tags or {},
            context=context or {},
            error_details=error_details,
            stack_trace=stack_trace
        )
        
        return log_entry
    
    def _should_log(self, log_entry: LogEntry) -> bool:
        """判断是否应该记录日志（去重过滤）"""
        # 创建去重键
        dedup_key = f"{log_entry.level.value}:{log_entry.category.value}:{hash(log_entry.message)}"
        
        now = datetime.now()
        last_logged = self.duplicate_log_cache.get(dedup_key)
        
        if last_logged and (now - last_logged).total_seconds() < self.duplicate_threshold_seconds:
            return False  # 重复日志，跳过
        
        self.duplicate_log_cache[dedup_key] = now
        return True
    
    async def _process_log_entry(self, log_entry: LogEntry):
        """处理日志条目"""
        # 去重过滤
        if not self._should_log(log_entry):
            return
        
        # 添加到最近日志
        self.recent_logs.append(log_entry)
        if len(self.recent_logs) > self.max_recent_logs:
            self.recent_logs.pop(0)
        
        # 性能监控
        if log_entry.duration_ms and log_entry.duration_ms > 5000:  # 超过5秒
            self.slow_operations.append({
                'log_id': log_entry.log_id,
                'operation': log_entry.operation,
                'duration_ms': log_entry.duration_ms,
                'timestamp': log_entry.timestamp.isoformat(),
                'trace_id': log_entry.trace_id
            })
        
        # 错误聚合
        if log_entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            error_key = f"{log_entry.category.value}:{log_entry.operation or 'unknown'}"
            if error_key not in self.error_aggregation:
                self.error_aggregation[error_key] = {
                    'count': 0,
                    'first_seen': log_entry.timestamp.isoformat(),
                    'last_seen': log_entry.timestamp.isoformat(),
                    'sample_message': log_entry.message,
                    'sample_trace_id': log_entry.trace_id
                }
            
            self.error_aggregation[error_key]['count'] += 1
            self.error_aggregation[error_key]['last_seen'] = log_entry.timestamp.isoformat()
        
        # 发送到原生日志系统
        self.logger.log(
            getattr(logging, log_entry.level.value.upper()),
            log_entry.message,
            extra=log_entry.to_dict()
        )
        
        # 发送到自定义处理器
        for handler in self.log_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(log_entry)
                else:
                    handler(log_entry)
            except Exception as e:
                # 避免日志处理器的错误影响主流程
                print(f"Log handler error: {e}")
        
        # 发送到WebSocket（集成现有的websocket_log_handler）
        await self._send_to_websocket(log_entry)
        
        # 添加到调用链
        if error_tracker and log_entry.span_id:
            error_tracker.add_span_log(
                log_entry.message,
                log_entry.level.value,
                log_entry.context,
                log_entry.span_id
            )
    
    async def _send_to_websocket(self, log_entry: LogEntry):
        """发送到WebSocket客户端"""
        if self.websocket_handler and self.websocket_handler.websocket_clients:
            ws_data = log_entry.to_websocket_format()
            try:
                await self.websocket_handler._broadcast_to_websockets(ws_data)
            except Exception as e:
                # WebSocket发送失败不应影响主流程
                print(f"WebSocket broadcast error: {e}")
    
    # 各级别日志方法
    async def debug(self, message: str, **kwargs):
        """记录调试日志"""
        log_entry = self._create_log_entry(LogLevel.DEBUG, message, **kwargs)
        await self._process_log_entry(log_entry)
    
    async def info(self, message: str, **kwargs):
        """记录信息日志"""
        log_entry = self._create_log_entry(LogLevel.INFO, message, **kwargs)
        await self._process_log_entry(log_entry)
    
    async def warning(self, message: str, **kwargs):
        """记录警告日志"""
        log_entry = self._create_log_entry(LogLevel.WARNING, message, **kwargs)
        await self._process_log_entry(log_entry)
    
    async def error(self, message: str, **kwargs):
        """记录错误日志"""
        log_entry = self._create_log_entry(LogLevel.ERROR, message, **kwargs)
        await self._process_log_entry(log_entry)
    
    async def critical(self, message: str, **kwargs):
        """记录严重错误日志"""
        log_entry = self._create_log_entry(LogLevel.CRITICAL, message, **kwargs)
        await self._process_log_entry(log_entry)
    
    # 特殊用途日志方法
    async def log_request(self, method: str, path: str, status_code: int, 
                         duration_ms: float, user_id: Optional[str] = None):
        """记录请求日志"""
        await self.info(
            f"{method} {path} - {status_code}",
            category=LogCategory.REQUEST,
            operation=f"{method} {path}",
            duration_ms=duration_ms,
            tags={
                'http_method': method,
                'path': path,
                'status_code': status_code,
                'user_id': user_id
            }
        )
    
    async def log_processing(self, operation: str, document_id: str, 
                           duration_ms: Optional[float] = None, status: str = "success"):
        """记录文档处理日志"""
        await self.info(
            f"Document processing {status}: {document_id}",
            category=LogCategory.PROCESSING,
            operation=operation,
            duration_ms=duration_ms,
            tags={
                'document_id': document_id,
                'status': status
            }
        )
    
    async def log_batch_operation(self, batch_id: str, operation: str, 
                                count: int, duration_ms: Optional[float] = None):
        """记录批量操作日志"""
        await self.info(
            f"Batch {operation}: {count} items",
            category=LogCategory.BATCH,
            operation=f"batch_{operation}",
            duration_ms=duration_ms,
            tags={
                'batch_id': batch_id,
                'operation': operation,
                'item_count': count
            }
        )
    
    async def log_database_query(self, query_type: str, table: str, 
                               duration_ms: float, rows_affected: Optional[int] = None):
        """记录数据库查询日志"""
        await self.debug(
            f"DB {query_type} on {table}",
            category=LogCategory.DATABASE,
            operation=f"db_{query_type}",
            duration_ms=duration_ms,
            tags={
                'query_type': query_type,
                'table': table,
                'rows_affected': rows_affected
            }
        )
    
    async def log_cache_operation(self, operation: str, key: str, 
                                hit: Optional[bool] = None, duration_ms: Optional[float] = None):
        """记录缓存操作日志"""
        await self.debug(
            f"Cache {operation}: {key}",
            category=LogCategory.CACHE,
            operation=f"cache_{operation}",
            duration_ms=duration_ms,
            tags={
                'cache_operation': operation,
                'cache_key': key,
                'cache_hit': hit
            }
        )
    
    async def log_websocket_event(self, event_type: str, client_id: Optional[str] = None,
                                message: Optional[str] = None):
        """记录WebSocket事件日志"""
        await self.info(
            f"WebSocket {event_type}: {client_id or 'unknown'}",
            category=LogCategory.WEBSOCKET,
            operation=f"ws_{event_type}",
            tags={
                'event_type': event_type,
                'client_id': client_id,
                'message': message
            }
        )
    
    async def log_security_event(self, event_type: str, user_id: Optional[str] = None,
                               ip_address: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """记录安全事件日志"""
        await self.warning(
            f"Security event: {event_type}",
            category=LogCategory.SECURITY,
            operation=f"security_{event_type}",
            tags={
                'event_type': event_type,
                'user_id': user_id,
                'ip_address': ip_address
            },
            context=details or {}
        )
    
    # 查询和统计方法
    def get_recent_logs(self, limit: int = 100, level: Optional[LogLevel] = None,
                       category: Optional[LogCategory] = None) -> List[Dict[str, Any]]:
        """获取最近的日志"""
        logs = self.recent_logs
        
        if level:
            logs = [log for log in logs if log.level == level]
        
        if category:
            logs = [log for log in logs if log.category == category]
        
        return [log.to_dict() for log in logs[-limit:]]
    
    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要"""
        return {
            'total_errors': len(self.error_aggregation),
            'error_patterns': dict(self.error_aggregation),
            'recent_errors_count': len([
                log for log in self.recent_logs 
                if log.level in [LogLevel.ERROR, LogLevel.CRITICAL]
                and (datetime.now() - log.timestamp).total_seconds() < 3600
            ])
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        return {
            'slow_operations': self.slow_operations[-10:],  # 最近10个慢操作
            'avg_duration': self._calculate_avg_duration(),
            'operation_counts': self._get_operation_counts()
        }
    
    def _calculate_avg_duration(self) -> float:
        """计算平均操作时长"""
        durations = [log.duration_ms for log in self.recent_logs if log.duration_ms]
        return sum(durations) / len(durations) if durations else 0
    
    def _get_operation_counts(self) -> Dict[str, int]:
        """获取操作统计"""
        counts = {}
        for log in self.recent_logs:
            if log.operation:
                counts[log.operation] = counts.get(log.operation, 0) + 1
        return counts
    
    def clear_logs(self):
        """清除日志缓存"""
        self.recent_logs.clear()
        self.duplicate_log_cache.clear()
        self.slow_operations.clear()
        self.error_aggregation.clear()
    
    # 集成现有的WebSocket日志功能
    def get_websocket_log_summary(self):
        """获取WebSocket日志摘要"""
        return get_log_summary()
    
    def get_websocket_core_progress(self):
        """获取核心进度信息"""
        return get_core_progress()
    
    def clear_websocket_logs(self):
        """清空WebSocket日志"""
        clear_logs()


class LoggerFactory:
    """日志记录器工厂"""
    
    _loggers: Dict[str, UnifiedLogger] = {}
    
    @classmethod
    def get_logger(cls, name: str = __name__) -> UnifiedLogger:
        """获取或创建日志记录器"""
        if name not in cls._loggers:
            cls._loggers[name] = UnifiedLogger(name)
        return cls._loggers[name]
    
    @classmethod
    def configure_logging(cls, level: str = "INFO", enable_debug: bool = False):
        """配置全局日志"""
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 配置WebSocket日志
        from websocket_log_handler import setup_websocket_logging
        setup_websocket_logging()


# 全局日志实例
default_logger = LoggerFactory.get_logger("raganything.unified")


# 便捷函数
async def log_info(message: str, **kwargs):
    """记录信息日志"""
    await default_logger.info(message, **kwargs)


async def log_error(message: str, **kwargs):
    """记录错误日志"""
    await default_logger.error(message, **kwargs)


async def log_warning(message: str, **kwargs):
    """记录警告日志"""
    await default_logger.warning(message, **kwargs)


async def log_debug(message: str, **kwargs):
    """记录调试日志"""
    await default_logger.debug(message, **kwargs)


def set_logger_context(context_id: str):
    """设置日志上下文"""
    logger_context.set(context_id)


def get_logger_context() -> str:
    """获取日志上下文"""
    return logger_context.get('')