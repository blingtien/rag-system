#!/usr/bin/env python3
"""
HTTP/2 优化中间件

功能特性:
1. HTTP/2 多路复用优化
2. Server Push 机制
3. 流量控制和优先级
4. HPACK 头部压缩
5. 连接复用和管理
6. 性能监控和优化建议
"""

import asyncio
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from collections import defaultdict, deque
import weakref
import gzip
import zlib

from fastapi import Request, Response
try:
    from fastapi.middleware.base import BaseHTTPMiddleware
except ImportError:
    from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Send, Scope

from middleware.unified_logging import LoggerFactory, LogCategory


class HTTP2StreamState(Enum):
    """HTTP/2 流状态"""
    IDLE = "idle"
    RESERVED_LOCAL = "reserved_local"
    RESERVED_REMOTE = "reserved_remote" 
    OPEN = "open"
    HALF_CLOSED_LOCAL = "half_closed_local"
    HALF_CLOSED_REMOTE = "half_closed_remote"
    CLOSED = "closed"


class HTTP2Priority(IntEnum):
    """HTTP/2 流优先级"""
    LOWEST = 0
    LOW = 64
    NORMAL = 128
    HIGH = 192
    HIGHEST = 255


class PushStrategy(Enum):
    """Server Push策略"""
    AGGRESSIVE = "aggressive"    # 激进推送
    CONSERVATIVE = "conservative"  # 保守推送
    ADAPTIVE = "adaptive"        # 自适应推送
    DISABLED = "disabled"        # 禁用推送


@dataclass
class HTTP2Stream:
    """HTTP/2 流对象"""
    stream_id: int
    state: HTTP2StreamState
    priority: HTTP2Priority
    dependency: Optional[int] = None
    weight: int = 16
    created_at: float = field(default_factory=time.time)
    
    # 流量控制
    local_window_size: int = 65535
    remote_window_size: int = 65535
    
    # 性能指标
    bytes_sent: int = 0
    bytes_received: int = 0
    frames_sent: int = 0
    frames_received: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    @property
    def is_active(self) -> bool:
        """检查流是否活跃"""
        return self.state in [
            HTTP2StreamState.OPEN,
            HTTP2StreamState.HALF_CLOSED_LOCAL,
            HTTP2StreamState.HALF_CLOSED_REMOTE
        ]
    
    @property
    def duration(self) -> float:
        """获取流持续时间"""
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.time()
        return end - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'stream_id': self.stream_id,
            'state': self.state.value,
            'priority': self.priority.value,
            'dependency': self.dependency,
            'weight': self.weight,
            'window_size': {
                'local': self.local_window_size,
                'remote': self.remote_window_size
            },
            'bytes': {
                'sent': self.bytes_sent,
                'received': self.bytes_received
            },
            'frames': {
                'sent': self.frames_sent,
                'received': self.frames_received
            },
            'duration': self.duration,
            'throughput': {
                'sent_bps': self.bytes_sent / max(self.duration, 0.001),
                'received_bps': self.bytes_received / max(self.duration, 0.001)
            }
        }


@dataclass
class PushPromise:
    """Server Push 承诺"""
    promised_stream_id: int
    parent_stream_id: int
    method: str
    path: str
    headers: Dict[str, str]
    priority: HTTP2Priority
    created_at: float = field(default_factory=time.time)
    pushed_at: Optional[float] = None
    accepted: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'promised_stream_id': self.promised_stream_id,
            'parent_stream_id': self.parent_stream_id,
            'method': self.method,
            'path': self.path,
            'headers': self.headers,
            'priority': self.priority.value,
            'created_at': self.created_at,
            'pushed_at': self.pushed_at,
            'accepted': self.accepted,
            'push_delay': (self.pushed_at - self.created_at) if self.pushed_at else None
        }


class HTTP2ConnectionManager:
    """HTTP/2 连接管理器"""
    
    def __init__(self, connection_id: str):
        self.connection_id = connection_id
        self.logger = LoggerFactory.get_logger(f"http2_connection_{connection_id}")
        
        # 流管理
        self.streams: Dict[int, HTTP2Stream] = {}
        self.next_stream_id = 1
        self.max_concurrent_streams = 100
        
        # 流量控制
        self.connection_window_size = 65535
        self.initial_window_size = 65535
        
        # Server Push管理
        self.push_promises: Dict[int, PushPromise] = {}
        self.push_cache: Dict[str, Any] = {}  # 推送缓存
        self.push_strategy = PushStrategy.ADAPTIVE
        
        # HPACK表
        self.header_table: List[Tuple[str, str]] = []
        self.header_table_size = 4096
        self.header_compression_stats = {
            'original_size': 0,
            'compressed_size': 0,
            'compression_ratio': 0.0
        }
        
        # 性能统计
        self.stats = {
            'streams_created': 0,
            'streams_closed': 0,
            'frames_sent': 0,
            'frames_received': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'push_promises_sent': 0,
            'push_promises_accepted': 0,
            'goaway_sent': False,
            'connection_start': time.time()
        }
        
        # 优先级树
        self.priority_tree: Dict[int, Set[int]] = defaultdict(set)
        
    def create_stream(self, 
                     priority: HTTP2Priority = HTTP2Priority.NORMAL,
                     dependency: Optional[int] = None,
                     weight: int = 16) -> int:
        """创建新流"""
        
        if len(self.streams) >= self.max_concurrent_streams:
            raise ValueError("已达到最大并发流数量")
        
        stream_id = self.next_stream_id
        self.next_stream_id += 2  # 客户端使用奇数，服务器使用偶数
        
        stream = HTTP2Stream(
            stream_id=stream_id,
            state=HTTP2StreamState.IDLE,
            priority=priority,
            dependency=dependency,
            weight=weight
        )
        
        self.streams[stream_id] = stream
        self.stats['streams_created'] += 1
        
        # 更新优先级树
        if dependency:
            self.priority_tree[dependency].add(stream_id)
        
        return stream_id
    
    def close_stream(self, stream_id: int):
        """关闭流"""
        if stream_id not in self.streams:
            return
        
        stream = self.streams[stream_id]
        stream.state = HTTP2StreamState.CLOSED
        stream.end_time = time.time()
        
        # 清理优先级树
        self.priority_tree.pop(stream_id, None)
        for parent_id, children in self.priority_tree.items():
            children.discard(stream_id)
        
        # 移除流（可选，用于内存管理）
        # del self.streams[stream_id]
        
        self.stats['streams_closed'] += 1
    
    def update_window_size(self, stream_id: int, delta: int):
        """更新窗口大小"""
        if stream_id == 0:
            # 连接级别窗口更新
            self.connection_window_size += delta
        else:
            # 流级别窗口更新
            if stream_id in self.streams:
                stream = self.streams[stream_id]
                stream.local_window_size += delta
    
    def get_stream_priority_weight(self, stream_id: int) -> float:
        """计算流的优先级权重"""
        if stream_id not in self.streams:
            return 1.0
        
        stream = self.streams[stream_id]
        base_weight = stream.weight / 256.0
        priority_weight = stream.priority.value / 255.0
        
        # 考虑依赖关系
        dependency_weight = 1.0
        if stream.dependency and stream.dependency in self.streams:
            parent_stream = self.streams[stream.dependency]
            dependency_weight = parent_stream.weight / 256.0
        
        return base_weight * priority_weight * dependency_weight
    
    def compress_headers(self, headers: Dict[str, str]) -> bytes:
        """HPACK头部压缩"""
        original_size = sum(len(k) + len(v) for k, v in headers.items())
        self.header_compression_stats['original_size'] += original_size
        
        # 简化的头部压缩（实际应使用HPACK算法）
        header_data = json.dumps(headers, separators=(',', ':')).encode()
        compressed_data = gzip.compress(header_data)
        
        compressed_size = len(compressed_data)
        self.header_compression_stats['compressed_size'] += compressed_size
        
        if self.header_compression_stats['original_size'] > 0:
            self.header_compression_stats['compression_ratio'] = (
                1.0 - (self.header_compression_stats['compressed_size'] / 
                      self.header_compression_stats['original_size'])
            )
        
        return compressed_data
    
    def can_push_resource(self, path: str, parent_stream_id: int) -> bool:
        """检查是否可以推送资源"""
        if self.push_strategy == PushStrategy.DISABLED:
            return False
        
        # 检查推送缓存
        if path in self.push_cache:
            cache_entry = self.push_cache[path]
            if time.time() - cache_entry['timestamp'] < 3600:  # 1小时缓存
                return False  # 已推送过，不需要重复推送
        
        # 检查流状态
        if parent_stream_id not in self.streams:
            return False
        
        parent_stream = self.streams[parent_stream_id]
        if not parent_stream.is_active:
            return False
        
        # 检查并发限制
        active_pushes = sum(1 for promise in self.push_promises.values() 
                           if not promise.accepted)
        if active_pushes >= 10:  # 最大10个并发推送
            return False
        
        return True
    
    def create_push_promise(self, 
                           parent_stream_id: int,
                           method: str,
                           path: str,
                           headers: Dict[str, str],
                           priority: HTTP2Priority = HTTP2Priority.LOW) -> Optional[int]:
        """创建Server Push承诺"""
        
        if not self.can_push_resource(path, parent_stream_id):
            return None
        
        promised_stream_id = self.next_stream_id
        self.next_stream_id += 2
        
        promise = PushPromise(
            promised_stream_id=promised_stream_id,
            parent_stream_id=parent_stream_id,
            method=method,
            path=path,
            headers=headers,
            priority=priority
        )
        
        self.push_promises[promised_stream_id] = promise
        self.stats['push_promises_sent'] += 1
        
        # 添加到推送缓存
        self.push_cache[path] = {
            'timestamp': time.time(),
            'stream_id': promised_stream_id
        }
        
        return promised_stream_id
    
    def accept_push_promise(self, promised_stream_id: int):
        """接受推送承诺"""
        if promised_stream_id in self.push_promises:
            promise = self.push_promises[promised_stream_id]
            promise.accepted = True
            promise.pushed_at = time.time()
            self.stats['push_promises_accepted'] += 1
    
    def get_connection_statistics(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        active_streams = sum(1 for stream in self.streams.values() if stream.is_active)
        
        # 计算平均流持续时间
        completed_streams = [s for s in self.streams.values() if s.end_time is not None]
        avg_stream_duration = (
            sum(s.duration for s in completed_streams) / len(completed_streams)
            if completed_streams else 0.0
        )
        
        # 计算推送接受率
        push_acceptance_rate = (
            (self.stats['push_promises_accepted'] / self.stats['push_promises_sent'] * 100)
            if self.stats['push_promises_sent'] > 0 else 0.0
        )
        
        return {
            'connection_id': self.connection_id,
            'streams': {
                'total_created': self.stats['streams_created'],
                'total_closed': self.stats['streams_closed'],
                'currently_active': active_streams,
                'max_concurrent': self.max_concurrent_streams,
                'utilization': (active_streams / self.max_concurrent_streams * 100)
            },
            'frames': {
                'sent': self.stats['frames_sent'],
                'received': self.stats['frames_received']
            },
            'bytes': {
                'sent': self.stats['bytes_sent'],
                'received': self.stats['bytes_received']
            },
            'flow_control': {
                'connection_window_size': self.connection_window_size,
                'initial_window_size': self.initial_window_size
            },
            'server_push': {
                'promises_sent': self.stats['push_promises_sent'],
                'promises_accepted': self.stats['push_promises_accepted'],
                'acceptance_rate': push_acceptance_rate,
                'cached_resources': len(self.push_cache)
            },
            'header_compression': self.header_compression_stats,
            'performance': {
                'connection_duration': time.time() - self.stats['connection_start'],
                'average_stream_duration': avg_stream_duration,
                'throughput': {
                    'sent_bps': self.stats['bytes_sent'] / max(time.time() - self.stats['connection_start'], 1),
                    'received_bps': self.stats['bytes_received'] / max(time.time() - self.stats['connection_start'], 1)
                }
            }
        }


class HTTP2OptimizationMiddleware(BaseHTTPMiddleware):
    """
    HTTP/2 优化中间件
    
    提供HTTP/2特性的优化和监控
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = LoggerFactory.get_logger("http2_optimization")
        
        # 连接管理
        self.connections: Dict[str, HTTP2ConnectionManager] = {}
        
        # 全局配置
        self.enable_server_push = True
        self.enable_header_compression = True
        self.max_concurrent_streams = 100
        self.initial_window_size = 65535
        
        # 推送规则
        self.push_rules = {
            'css': {'priority': HTTP2Priority.HIGH, 'preload': True},
            'js': {'priority': HTTP2Priority.HIGH, 'preload': True},
            'woff2': {'priority': HTTP2Priority.NORMAL, 'preload': True},
            'png': {'priority': HTTP2Priority.LOW, 'preload': False},
            'jpg': {'priority': HTTP2Priority.LOW, 'preload': False}
        }
        
        # 性能统计
        self.global_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'total_streams': 0,
            'total_push_promises': 0,
            'optimization_enabled': True
        }
        
        # 后台任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """启动清理任务"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """清理循环"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次
                await self._cleanup_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(f"清理任务错误: {str(e)}")
    
    async def _cleanup_connections(self):
        """清理不活跃的连接"""
        current_time = time.time()
        inactive_connections = []
        
        for conn_id, conn_mgr in self.connections.items():
            connection_age = current_time - conn_mgr.stats['connection_start']
            active_streams = sum(1 for stream in conn_mgr.streams.values() if stream.is_active)
            
            # 如果连接超过1小时且没有活跃流，标记为不活跃
            if connection_age > 3600 and active_streams == 0:
                inactive_connections.append(conn_id)
        
        for conn_id in inactive_connections:
            del self.connections[conn_id]
            self.global_stats['active_connections'] -= 1
            await self.logger.info(f"清理不活跃连接: {conn_id}")
    
    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 生成连接ID
        connection_id = self._get_connection_id(request)
        
        # 获取或创建连接管理器
        if connection_id not in self.connections:
            await self._create_connection(connection_id, request)
        
        conn_mgr = self.connections[connection_id]
        
        # 创建流
        stream_id = conn_mgr.create_stream()
        stream = conn_mgr.streams[stream_id]
        stream.start_time = time.time()
        stream.state = HTTP2StreamState.OPEN
        
        # 处理Server Push
        push_promises = []
        if self.enable_server_push:
            push_promises = await self._handle_server_push(request, conn_mgr, stream_id)
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 更新流统计
            stream.state = HTTP2StreamState.HALF_CLOSED_REMOTE
            stream.bytes_sent = len(response.body) if hasattr(response, 'body') else 0
            
            # 添加HTTP/2相关头部
            if self.enable_header_compression:
                response.headers["x-http2-stream-id"] = str(stream_id)
                response.headers["x-http2-connection-id"] = connection_id
                
                if push_promises:
                    response.headers["x-http2-push-promises"] = str(len(push_promises))
            
            # 更新连接统计
            conn_mgr.stats['frames_sent'] += 1
            conn_mgr.stats['bytes_sent'] += stream.bytes_sent
            
            return response
            
        except Exception as e:
            await self.logger.error(f"HTTP/2处理错误: {str(e)}")
            raise
        finally:
            # 关闭流
            stream.end_time = time.time()
            conn_mgr.close_stream(stream_id)
    
    def _get_connection_id(self, request: Request) -> str:
        """生成连接ID"""
        # 基于客户端IP和User-Agent生成连接ID
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        import hashlib
        connection_hash = hashlib.md5(f"{client_ip}_{user_agent}".encode()).hexdigest()
        return f"http2_{connection_hash[:16]}"
    
    async def _create_connection(self, connection_id: str, request: Request):
        """创建新连接"""
        conn_mgr = HTTP2ConnectionManager(connection_id)
        
        # 根据客户端能力调整配置
        http_version = getattr(request.scope, 'http_version', '1.1')
        if http_version.startswith('2'):
            conn_mgr.max_concurrent_streams = self.max_concurrent_streams
            conn_mgr.initial_window_size = self.initial_window_size
        
        # 检测推送策略
        user_agent = request.headers.get("user-agent", "").lower()
        if "mobile" in user_agent:
            conn_mgr.push_strategy = PushStrategy.CONSERVATIVE
        elif "chrome" in user_agent or "firefox" in user_agent:
            conn_mgr.push_strategy = PushStrategy.ADAPTIVE
        else:
            conn_mgr.push_strategy = PushStrategy.DISABLED
        
        self.connections[connection_id] = conn_mgr
        self.global_stats['total_connections'] += 1
        self.global_stats['active_connections'] += 1
        
        await self.logger.info(f"创建HTTP/2连接: {connection_id}")
    
    async def _handle_server_push(self, 
                                 request: Request, 
                                 conn_mgr: HTTP2ConnectionManager,
                                 parent_stream_id: int) -> List[int]:
        """处理Server Push"""
        push_promises = []
        
        # 分析请求路径，确定需要推送的资源
        path = request.url.path
        resources_to_push = self._analyze_push_resources(path)
        
        for resource_path, resource_info in resources_to_push.items():
            if conn_mgr.can_push_resource(resource_path, parent_stream_id):
                # 创建推送承诺
                headers = {
                    'content-type': resource_info['content_type'],
                    'cache-control': 'public, max-age=3600'
                }
                
                promised_stream_id = conn_mgr.create_push_promise(
                    parent_stream_id=parent_stream_id,
                    method='GET',
                    path=resource_path,
                    headers=headers,
                    priority=resource_info['priority']
                )
                
                if promised_stream_id:
                    push_promises.append(promised_stream_id)
                    await self.logger.debug(f"创建推送承诺: {resource_path}")
        
        return push_promises
    
    def _analyze_push_resources(self, path: str) -> Dict[str, Dict[str, Any]]:
        """分析需要推送的资源"""
        resources = {}
        
        # 根据页面路径确定关键资源
        if path == "/" or path.endswith('.html'):
            # 主页或HTML页面，推送CSS和JS
            resources.update({
                '/static/css/main.css': {
                    'content_type': 'text/css',
                    'priority': HTTP2Priority.HIGH
                },
                '/static/js/main.js': {
                    'content_type': 'application/javascript',
                    'priority': HTTP2Priority.HIGH
                },
                '/static/fonts/main.woff2': {
                    'content_type': 'font/woff2',
                    'priority': HTTP2Priority.NORMAL
                }
            })
        
        elif path.startswith('/api/'):
            # API请求，可能推送相关资源
            if 'documents' in path:
                resources.update({
                    '/static/css/documents.css': {
                        'content_type': 'text/css',
                        'priority': HTTP2Priority.NORMAL
                    }
                })
        
        return resources
    
    async def get_optimization_statistics(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        connection_stats = {}
        total_streams = 0
        total_push_promises = 0
        
        for conn_id, conn_mgr in self.connections.items():
            stats = conn_mgr.get_connection_statistics()
            connection_stats[conn_id] = stats
            total_streams += stats['streams']['total_created']
            total_push_promises += stats['server_push']['promises_sent']
        
        self.global_stats.update({
            'active_connections': len(self.connections),
            'total_streams': total_streams,
            'total_push_promises': total_push_promises
        })
        
        return {
            'global_statistics': self.global_stats,
            'connections': connection_stats,
            'configuration': {
                'server_push_enabled': self.enable_server_push,
                'header_compression_enabled': self.enable_header_compression,
                'max_concurrent_streams': self.max_concurrent_streams,
                'initial_window_size': self.initial_window_size
            },
            'push_rules': self.push_rules
        }
    
    async def configure(self, **config):
        """配置HTTP/2优化参数"""
        if 'enable_server_push' in config:
            self.enable_server_push = config['enable_server_push']
        
        if 'enable_header_compression' in config:
            self.enable_header_compression = config['enable_header_compression']
        
        if 'max_concurrent_streams' in config:
            self.max_concurrent_streams = config['max_concurrent_streams']
        
        if 'initial_window_size' in config:
            self.initial_window_size = config['initial_window_size']
        
        if 'push_rules' in config:
            self.push_rules.update(config['push_rules'])
        
        await self.logger.info("HTTP/2优化配置已更新")
    
    async def shutdown(self):
        """关闭中间件"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 清理所有连接
        self.connections.clear()
        await self.logger.info("HTTP/2优化中间件已关闭")


# 全局HTTP/2优化中间件实例
http2_optimization_middleware = None

def get_http2_optimization_middleware() -> Optional[HTTP2OptimizationMiddleware]:
    """获取HTTP/2优化中间件实例"""
    return http2_optimization_middleware

def set_http2_optimization_middleware(middleware: HTTP2OptimizationMiddleware):
    """设置HTTP/2优化中间件实例"""
    global http2_optimization_middleware
    http2_optimization_middleware = middleware