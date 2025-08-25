#!/usr/bin/env python3
"""
高效的WebSocket连接池管理器
支持连接重用、负载均衡、自动扩缩容和连接健康监控

功能特性:
1. 连接池管理和重用
2. 智能负载均衡
3. 连接健康监控和自动恢复
4. 动态扩缩容
5. 连接统计和性能监控
6. 内存优化和资源清理
"""

import asyncio
import time
import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import weakref

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from middleware.unified_logging import LoggerFactory, LogCategory


class ConnectionStatus(Enum):
    """连接状态"""
    IDLE = "idle"                    # 空闲可用
    BUSY = "busy"                    # 繁忙中
    CONNECTING = "connecting"        # 连接中
    DISCONNECTED = "disconnected"    # 已断开
    ERROR = "error"                  # 错误状态
    RECOVERING = "recovering"        # 恢复中


class PoolStrategy(Enum):
    """连接池策略"""
    ROUND_ROBIN = "round_robin"      # 轮询
    LEAST_CONNECTIONS = "least_conn" # 最少连接数
    WEIGHTED_ROUND_ROBIN = "weighted_rr"  # 加权轮询
    RANDOM = "random"                # 随机
    HASH_BASED = "hash"              # 基于哈希


@dataclass
class ConnectionMetrics:
    """连接性能指标"""
    total_messages_sent: int = 0
    total_messages_received: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    average_response_time: float = 0.0
    last_activity_time: float = field(default_factory=time.time)
    error_count: int = 0
    reconnect_count: int = 0
    uptime_seconds: float = 0.0
    
    def update_activity(self):
        """更新活动时间"""
        self.last_activity_time = time.time()
    
    def is_stale(self, timeout_seconds: int = 300) -> bool:
        """检查连接是否过期"""
        return (time.time() - self.last_activity_time) > timeout_seconds


@dataclass
class PooledConnection:
    """池化连接对象"""
    connection_id: str
    websocket: WebSocket
    client_info: Dict[str, Any]
    created_at: datetime
    status: ConnectionStatus = ConnectionStatus.CONNECTING
    metrics: ConnectionMetrics = field(default_factory=ConnectionMetrics)
    pool_id: str = ""
    weight: float = 1.0
    max_concurrent_operations: int = 100
    current_operations: int = 0
    subscription_topics: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        """初始化后处理"""
        self.metrics.update_activity()
    
    @property
    def is_available(self) -> bool:
        """检查连接是否可用"""
        return (self.status == ConnectionStatus.IDLE and 
                self.websocket.client_state == WebSocketState.CONNECTED and
                self.current_operations < self.max_concurrent_operations)
    
    @property
    def load_factor(self) -> float:
        """计算负载因子"""
        if self.max_concurrent_operations == 0:
            return 1.0
        return self.current_operations / self.max_concurrent_operations
    
    @property
    def connection_score(self) -> float:
        """计算连接评分（用于负载均衡）"""
        base_score = self.weight
        load_penalty = self.load_factor * 0.3
        error_penalty = min(self.metrics.error_count * 0.1, 0.5)
        response_penalty = min(self.metrics.average_response_time * 0.01, 0.2)
        
        return max(base_score - load_penalty - error_penalty - response_penalty, 0.1)
    
    async def acquire_operation(self) -> bool:
        """获取操作权限"""
        if self.current_operations >= self.max_concurrent_operations:
            return False
        
        self.current_operations += 1
        self.status = ConnectionStatus.BUSY if self.current_operations > 0 else ConnectionStatus.IDLE
        self.metrics.update_activity()
        return True
    
    async def release_operation(self):
        """释放操作权限"""
        self.current_operations = max(0, self.current_operations - 1)
        self.status = ConnectionStatus.IDLE if self.current_operations == 0 else ConnectionStatus.BUSY
        self.metrics.update_activity()
    
    async def send_message(self, message: str) -> bool:
        """发送消息"""
        try:
            if not self.is_available and self.current_operations == 0:
                return False
            
            start_time = time.time()
            await self.websocket.send_text(message)
            
            # 更新指标
            response_time = time.time() - start_time
            self.metrics.total_messages_sent += 1
            self.metrics.total_bytes_sent += len(message.encode())
            
            # 更新平均响应时间
            if self.metrics.average_response_time == 0:
                self.metrics.average_response_time = response_time
            else:
                self.metrics.average_response_time = (
                    self.metrics.average_response_time * 0.7 + response_time * 0.3
                )
            
            self.metrics.update_activity()
            return True
            
        except Exception as e:
            self.metrics.error_count += 1
            self.status = ConnectionStatus.ERROR
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'connection_id': self.connection_id,
            'pool_id': self.pool_id,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'client_info': self.client_info,
            'metrics': {
                'messages_sent': self.metrics.total_messages_sent,
                'messages_received': self.metrics.total_messages_received,
                'bytes_sent': self.metrics.total_bytes_sent,
                'bytes_received': self.metrics.total_bytes_received,
                'avg_response_time': round(self.metrics.average_response_time, 4),
                'error_count': self.metrics.error_count,
                'reconnect_count': self.metrics.reconnect_count,
                'uptime_seconds': (datetime.now() - self.created_at).total_seconds()
            },
            'performance': {
                'load_factor': round(self.load_factor, 3),
                'connection_score': round(self.connection_score, 3),
                'weight': self.weight,
                'current_operations': self.current_operations,
                'max_operations': self.max_concurrent_operations
            },
            'subscriptions': list(self.subscription_topics)
        }


class WebSocketConnectionPool:
    """
    WebSocket连接池管理器
    
    提供高效的连接管理、负载均衡和自动扩缩容功能
    """
    
    def __init__(self, 
                 pool_id: str,
                 min_connections: int = 2,
                 max_connections: int = 100,
                 strategy: PoolStrategy = PoolStrategy.LEAST_CONNECTIONS):
        
        self.pool_id = pool_id
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.strategy = strategy
        
        # 连接存储
        self.connections: Dict[str, PooledConnection] = {}
        self.available_connections: deque = deque()
        self.busy_connections: Set[str] = set()
        
        # 负载均衡状态
        self.round_robin_index = 0
        self.connection_weights: Dict[str, float] = {}
        
        # 监控和统计
        self.pool_stats = {
            'total_created': 0,
            'total_destroyed': 0,
            'current_size': 0,
            'peak_size': 0,
            'total_operations': 0,
            'failed_operations': 0,
            'average_pool_utilization': 0.0,
            'created_at': datetime.now().isoformat()
        }
        
        # 配置参数
        self.connection_timeout = 300  # 连接超时时间(秒)
        self.health_check_interval = 60  # 健康检查间隔(秒)
        self.scale_check_interval = 30   # 扩缩容检查间隔(秒)
        self.max_idle_time = 600        # 最大空闲时间(秒)
        
        # 扩缩容参数
        self.scale_up_threshold = 0.8    # 扩容阈值
        self.scale_down_threshold = 0.3  # 缩容阈值
        self.scale_up_step = 2          # 扩容步长
        self.scale_down_step = 1        # 缩容步长
        
        # 日志和任务
        self.logger = LoggerFactory.get_logger(f"websocket_pool_{pool_id}")
        self.background_tasks: List[asyncio.Task] = []
        self.is_running = False
        
        # 订阅管理
        self.topic_subscribers: Dict[str, Set[str]] = defaultdict(set)
        self.subscriber_topics: Dict[str, Set[str]] = defaultdict(set)
    
    async def start(self):
        """启动连接池"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 启动后台任务
        self.background_tasks = [
            asyncio.create_task(self._health_check_loop()),
            asyncio.create_task(self._auto_scale_loop()),
            asyncio.create_task(self._statistics_update_loop())
        ]
        
        await self.logger.info(f"WebSocket连接池 {self.pool_id} 已启动")
    
    async def stop(self):
        """停止连接池"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 停止后台任务
        for task in self.background_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有连接
        await self._close_all_connections()
        
        await self.logger.info(f"WebSocket连接池 {self.pool_id} 已停止")
    
    async def add_connection(self, websocket: WebSocket, client_info: Dict[str, Any]) -> str:
        """添加连接到池中"""
        if len(self.connections) >= self.max_connections:
            await self.logger.warning(
                f"连接池已达到最大容量 {self.max_connections}",
                category=LogCategory.WEBSOCKET
            )
            return None
        
        # 生成连接ID
        connection_id = self._generate_connection_id(client_info)
        
        # 创建池化连接
        pooled_conn = PooledConnection(
            connection_id=connection_id,
            websocket=websocket,
            client_info=client_info,
            created_at=datetime.now(),
            pool_id=self.pool_id
        )
        
        # 设置连接权重
        pooled_conn.weight = self._calculate_connection_weight(client_info)
        
        # 添加到池中
        self.connections[connection_id] = pooled_conn
        self.available_connections.append(connection_id)
        
        # 更新统计
        self.pool_stats['total_created'] += 1
        self.pool_stats['current_size'] = len(self.connections)
        self.pool_stats['peak_size'] = max(self.pool_stats['peak_size'], 
                                         self.pool_stats['current_size'])
        
        await self.logger.info(
            f"新连接添加到池中: {connection_id} (总数: {len(self.connections)})",
            category=LogCategory.WEBSOCKET
        )
        
        return connection_id
    
    async def get_connection(self, selection_key: Optional[str] = None) -> Optional[PooledConnection]:
        """获取可用连接"""
        if not self.connections:
            return None
        
        connection_id = await self._select_connection(selection_key)
        if not connection_id:
            return None
        
        conn = self.connections[connection_id]
        
        # 获取操作权限
        if await conn.acquire_operation():
            # 移动到繁忙列表
            if connection_id in self.available_connections:
                self.available_connections.remove(connection_id)
            self.busy_connections.add(connection_id)
            
            self.pool_stats['total_operations'] += 1
            return conn
        
        return None
    
    async def release_connection(self, connection_id: str):
        """释放连接"""
        if connection_id not in self.connections:
            return
        
        conn = self.connections[connection_id]
        await conn.release_operation()
        
        # 移回可用列表
        if conn.current_operations == 0:
            self.busy_connections.discard(connection_id)
            if connection_id not in self.available_connections:
                self.available_connections.append(connection_id)
    
    async def remove_connection(self, connection_id: str):
        """移除连接"""
        if connection_id not in self.connections:
            return
        
        conn = self.connections[connection_id]
        
        # 清理订阅
        for topic in conn.subscription_topics:
            self.topic_subscribers[topic].discard(connection_id)
            self.subscriber_topics[connection_id].discard(topic)
        
        # 从各个列表中移除
        if connection_id in self.available_connections:
            self.available_connections.remove(connection_id)
        self.busy_connections.discard(connection_id)
        
        # 关闭连接
        try:
            if conn.websocket.client_state == WebSocketState.CONNECTED:
                await conn.websocket.close()
        except Exception as e:
            await self.logger.debug(f"关闭连接时出错: {str(e)}")
        
        # 从池中移除
        del self.connections[connection_id]
        
        # 更新统计
        self.pool_stats['total_destroyed'] += 1
        self.pool_stats['current_size'] = len(self.connections)
        
        await self.logger.debug(
            f"连接已从池中移除: {connection_id} (剩余: {len(self.connections)})",
            category=LogCategory.WEBSOCKET
        )
    
    async def broadcast_to_topic(self, topic: str, message: str) -> int:
        """向特定主题的订阅者广播消息"""
        if topic not in self.topic_subscribers:
            return 0
        
        subscriber_ids = self.topic_subscribers[topic].copy()
        successful_sends = 0
        
        for connection_id in subscriber_ids:
            conn = self.connections.get(connection_id)
            if conn and conn.is_available:
                if await conn.send_message(message):
                    successful_sends += 1
                else:
                    # 发送失败，可能需要移除连接
                    await self._handle_connection_error(connection_id)
        
        return successful_sends
    
    async def subscribe_to_topic(self, connection_id: str, topic: str):
        """订阅主题"""
        if connection_id in self.connections:
            conn = self.connections[connection_id]
            conn.subscription_topics.add(topic)
            self.topic_subscribers[topic].add(connection_id)
            self.subscriber_topics[connection_id].add(topic)
            
            await self.logger.debug(
                f"连接 {connection_id} 订阅主题: {topic}",
                category=LogCategory.WEBSOCKET
            )
    
    async def unsubscribe_from_topic(self, connection_id: str, topic: str):
        """取消订阅主题"""
        if connection_id in self.connections:
            conn = self.connections[connection_id]
            conn.subscription_topics.discard(topic)
            self.topic_subscribers[topic].discard(connection_id)
            self.subscriber_topics[connection_id].discard(topic)
            
            await self.logger.debug(
                f"连接 {connection_id} 取消订阅主题: {topic}",
                category=LogCategory.WEBSOCKET
            )
    
    async def _select_connection(self, selection_key: Optional[str] = None) -> Optional[str]:
        """根据策略选择连接"""
        available_conns = [cid for cid in self.available_connections 
                          if cid in self.connections and self.connections[cid].is_available]
        
        if not available_conns:
            return None
        
        if self.strategy == PoolStrategy.ROUND_ROBIN:
            return await self._round_robin_select(available_conns)
        elif self.strategy == PoolStrategy.LEAST_CONNECTIONS:
            return await self._least_connections_select(available_conns)
        elif self.strategy == PoolStrategy.WEIGHTED_ROUND_ROBIN:
            return await self._weighted_round_robin_select(available_conns)
        elif self.strategy == PoolStrategy.RANDOM:
            return await self._random_select(available_conns)
        elif self.strategy == PoolStrategy.HASH_BASED:
            return await self._hash_based_select(available_conns, selection_key)
        
        return available_conns[0]  # 默认返回第一个
    
    async def _round_robin_select(self, available_conns: List[str]) -> str:
        """轮询选择"""
        if not available_conns:
            return None
        
        selected = available_conns[self.round_robin_index % len(available_conns)]
        self.round_robin_index += 1
        return selected
    
    async def _least_connections_select(self, available_conns: List[str]) -> str:
        """最少连接数选择"""
        if not available_conns:
            return None
        
        min_connections = float('inf')
        selected = None
        
        for conn_id in available_conns:
            conn = self.connections[conn_id]
            if conn.current_operations < min_connections:
                min_connections = conn.current_operations
                selected = conn_id
        
        return selected
    
    async def _weighted_round_robin_select(self, available_conns: List[str]) -> str:
        """加权轮询选择"""
        if not available_conns:
            return None
        
        # 基于连接评分进行加权选择
        best_score = -1
        selected = None
        
        for conn_id in available_conns:
            conn = self.connections[conn_id]
            score = conn.connection_score
            if score > best_score:
                best_score = score
                selected = conn_id
        
        return selected
    
    async def _random_select(self, available_conns: List[str]) -> str:
        """随机选择"""
        import random
        return random.choice(available_conns) if available_conns else None
    
    async def _hash_based_select(self, available_conns: List[str], key: Optional[str]) -> str:
        """基于哈希的选择"""
        if not available_conns or not key:
            return available_conns[0] if available_conns else None
        
        hash_value = int(hashlib.md5(key.encode()).hexdigest(), 16)
        index = hash_value % len(available_conns)
        return available_conns[index]
    
    def _generate_connection_id(self, client_info: Dict[str, Any]) -> str:
        """生成连接ID"""
        import uuid
        base_id = str(uuid.uuid4())[:8]
        
        # 包含客户端信息以便调试
        client_hash = hashlib.md5(
            f"{client_info.get('ip', 'unknown')}{client_info.get('user_agent', 'unknown')}".encode()
        ).hexdigest()[:8]
        
        return f"{self.pool_id}_{base_id}_{client_hash}"
    
    def _calculate_connection_weight(self, client_info: Dict[str, Any]) -> float:
        """计算连接权重"""
        weight = 1.0
        
        # 可以根据客户端信息调整权重
        # 例如：优先级客户端给更高权重
        priority = client_info.get('priority', 'normal')
        if priority == 'high':
            weight = 2.0
        elif priority == 'low':
            weight = 0.5
        
        return weight
    
    async def _handle_connection_error(self, connection_id: str):
        """处理连接错误"""
        if connection_id not in self.connections:
            return
        
        conn = self.connections[connection_id]
        conn.metrics.error_count += 1
        conn.status = ConnectionStatus.ERROR
        
        self.pool_stats['failed_operations'] += 1
        
        # 如果错误过多，移除连接
        if conn.metrics.error_count > 5:
            await self.remove_connection(connection_id)
            await self.logger.warning(
                f"连接因错误过多被移除: {connection_id}",
                category=LogCategory.WEBSOCKET
            )
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self.is_running:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._perform_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(f"健康检查出错: {str(e)}")
    
    async def _perform_health_check(self):
        """执行健康检查"""
        stale_connections = []
        error_connections = []
        
        for conn_id, conn in self.connections.items():
            # 检查过期连接
            if conn.metrics.is_stale(self.connection_timeout):
                stale_connections.append(conn_id)
            
            # 检查连接状态
            if (conn.websocket.client_state != WebSocketState.CONNECTED or
                conn.status == ConnectionStatus.ERROR):
                error_connections.append(conn_id)
        
        # 移除过期和错误连接
        for conn_id in set(stale_connections + error_connections):
            await self.remove_connection(conn_id)
        
        if stale_connections or error_connections:
            await self.logger.info(
                f"健康检查移除连接: 过期={len(stale_connections)}, 错误={len(error_connections)}",
                category=LogCategory.WEBSOCKET
            )
    
    async def _auto_scale_loop(self):
        """自动扩缩容循环"""
        while self.is_running:
            try:
                await asyncio.sleep(self.scale_check_interval)
                await self._check_auto_scale()
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(f"自动扩缩容检查出错: {str(e)}")
    
    async def _check_auto_scale(self):
        """检查是否需要自动扩缩容"""
        current_size = len(self.connections)
        if current_size == 0:
            return
        
        # 计算利用率
        busy_count = len(self.busy_connections)
        utilization = busy_count / current_size
        
        # 扩容检查
        if (utilization > self.scale_up_threshold and 
            current_size < self.max_connections):
            
            target_size = min(current_size + self.scale_up_step, self.max_connections)
            await self.logger.info(
                f"触发扩容: 利用率={utilization:.2f}, 目标大小={target_size}",
                category=LogCategory.WEBSOCKET
            )
        
        # 缩容检查
        elif (utilization < self.scale_down_threshold and 
              current_size > self.min_connections):
            
            target_size = max(current_size - self.scale_down_step, self.min_connections)
            idle_connections = [cid for cid in self.available_connections 
                              if self.connections[cid].metrics.is_stale(self.max_idle_time)]
            
            # 移除空闲时间最长的连接
            for conn_id in idle_connections[:self.scale_down_step]:
                await self.remove_connection(conn_id)
            
            if idle_connections:
                await self.logger.info(
                    f"执行缩容: 利用率={utilization:.2f}, 移除连接={len(idle_connections[:self.scale_down_step])}",
                    category=LogCategory.WEBSOCKET
                )
    
    async def _statistics_update_loop(self):
        """统计信息更新循环"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # 每分钟更新一次
                await self._update_statistics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(f"统计更新出错: {str(e)}")
    
    async def _update_statistics(self):
        """更新统计信息"""
        if not self.connections:
            return
        
        # 计算平均利用率
        total_operations = sum(conn.current_operations for conn in self.connections.values())
        max_operations = sum(conn.max_concurrent_operations for conn in self.connections.values())
        
        if max_operations > 0:
            utilization = total_operations / max_operations
            self.pool_stats['average_pool_utilization'] = utilization
    
    async def _close_all_connections(self):
        """关闭所有连接"""
        connection_ids = list(self.connections.keys())
        for conn_id in connection_ids:
            await self.remove_connection(conn_id)
    
    def get_pool_statistics(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        current_time = datetime.now()
        
        return {
            'pool_id': self.pool_id,
            'strategy': self.strategy.value,
            'size': {
                'current': len(self.connections),
                'available': len(self.available_connections),
                'busy': len(self.busy_connections),
                'min_configured': self.min_connections,
                'max_configured': self.max_connections,
                'peak_reached': self.pool_stats['peak_size']
            },
            'operations': {
                'total_performed': self.pool_stats['total_operations'],
                'failed_operations': self.pool_stats['failed_operations'],
                'success_rate': (
                    ((self.pool_stats['total_operations'] - self.pool_stats['failed_operations']) 
                     / self.pool_stats['total_operations'] * 100)
                    if self.pool_stats['total_operations'] > 0 else 100.0
                )
            },
            'connections': {
                'total_created': self.pool_stats['total_created'],
                'total_destroyed': self.pool_stats['total_destroyed'],
                'average_utilization': round(self.pool_stats['average_pool_utilization'], 3)
            },
            'topics': {
                'total_topics': len(self.topic_subscribers),
                'total_subscriptions': sum(len(subs) for subs in self.topic_subscribers.values())
            },
            'uptime_seconds': (current_time - datetime.fromisoformat(self.pool_stats['created_at'])).total_seconds()
        }
    
    def get_connection_details(self) -> List[Dict[str, Any]]:
        """获取所有连接详情"""
        return [conn.to_dict() for conn in self.connections.values()]


class WebSocketConnectionPoolManager:
    """
    WebSocket连接池管理器
    管理多个连接池实例
    """
    
    def __init__(self):
        self.pools: Dict[str, WebSocketConnectionPool] = {}
        self.logger = LoggerFactory.get_logger("websocket_pool_manager")
        
        # 默认池配置
        self.default_pool_config = {
            'min_connections': 2,
            'max_connections': 50,
            'strategy': PoolStrategy.LEAST_CONNECTIONS
        }
    
    async def create_pool(self, pool_id: str, **config) -> WebSocketConnectionPool:
        """创建连接池"""
        if pool_id in self.pools:
            await self.logger.warning(f"连接池 {pool_id} 已存在")
            return self.pools[pool_id]
        
        pool_config = {**self.default_pool_config, **config}
        pool = WebSocketConnectionPool(pool_id, **pool_config)
        
        self.pools[pool_id] = pool
        await pool.start()
        
        await self.logger.info(f"创建连接池: {pool_id}")
        return pool
    
    async def get_pool(self, pool_id: str) -> Optional[WebSocketConnectionPool]:
        """获取连接池"""
        return self.pools.get(pool_id)
    
    async def remove_pool(self, pool_id: str):
        """移除连接池"""
        if pool_id not in self.pools:
            return
        
        pool = self.pools[pool_id]
        await pool.stop()
        del self.pools[pool_id]
        
        await self.logger.info(f"移除连接池: {pool_id}")
    
    async def get_all_statistics(self) -> Dict[str, Any]:
        """获取所有池的统计信息"""
        stats = {
            'pool_count': len(self.pools),
            'pools': {}
        }
        
        for pool_id, pool in self.pools.items():
            stats['pools'][pool_id] = pool.get_pool_statistics()
        
        return stats
    
    async def shutdown_all(self):
        """关闭所有连接池"""
        pool_ids = list(self.pools.keys())
        for pool_id in pool_ids:
            await self.remove_pool(pool_id)


# 全局连接池管理器实例
connection_pool_manager = WebSocketConnectionPoolManager()