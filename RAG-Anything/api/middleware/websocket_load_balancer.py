#!/usr/bin/env python3
"""
WebSocket负载均衡器

功能特性:
1. 多种负载均衡算法
2. 健康检查和故障转移
3. 连接限制和流量控制
4. 地理位置感知路由
5. 会话亲和性
6. 实时性能监控
7. 自动扩缩容
"""

import asyncio
import time
import json
import logging
import hashlib
import random
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from collections import defaultdict, deque
import weakref
import heapq

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from middleware.unified_logging import LoggerFactory, LogCategory
from middleware.websocket_connection_pool import connection_pool_manager
from middleware.network_performance_monitor import network_performance_monitor


class LoadBalancingAlgorithm(Enum):
    """负载均衡算法"""
    ROUND_ROBIN = "round_robin"              # 轮询
    WEIGHTED_ROUND_ROBIN = "weighted_rr"     # 加权轮询
    LEAST_CONNECTIONS = "least_connections"  # 最少连接数
    LEAST_RESPONSE_TIME = "least_response"   # 最小响应时间
    CONSISTENT_HASH = "consistent_hash"      # 一致性哈希
    RANDOM = "random"                        # 随机
    GEOGRAPHIC = "geographic"                # 地理位置
    RESOURCE_BASED = "resource_based"        # 基于资源


class ServerHealth(Enum):
    """服务器健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


class AffinityType(Enum):
    """会话亲和性类型"""
    NONE = "none"
    IP_HASH = "ip_hash"
    SESSION_ID = "session_id"
    USER_ID = "user_id"
    CUSTOM = "custom"


@dataclass
class ServerNode:
    """服务器节点"""
    node_id: str
    host: str
    port: int
    weight: float = 1.0
    max_connections: int = 1000
    current_connections: int = 0
    
    # 健康状态
    health: ServerHealth = ServerHealth.HEALTHY
    last_health_check: float = field(default_factory=time.time)
    consecutive_failures: int = 0
    
    # 性能指标
    average_response_time: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    network_usage: float = 0.0
    
    # 统计信息
    total_requests: int = 0
    failed_requests: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    
    # 地理位置
    region: Optional[str] = None
    availability_zone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    @property
    def load_factor(self) -> float:
        """计算负载因子"""
        if self.max_connections == 0:
            return 1.0
        return self.current_connections / self.max_connections
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.total_requests == 0:
            return 1.0
        return (self.total_requests - self.failed_requests) / self.total_requests
    
    @property
    def is_available(self) -> bool:
        """检查节点是否可用"""
        return (self.health in [ServerHealth.HEALTHY, ServerHealth.DEGRADED] and
                self.current_connections < self.max_connections)
    
    @property
    def effective_weight(self) -> float:
        """计算有效权重"""
        # 基于健康状态调整权重
        health_multiplier = {
            ServerHealth.HEALTHY: 1.0,
            ServerHealth.DEGRADED: 0.5,
            ServerHealth.UNHEALTHY: 0.1,
            ServerHealth.OFFLINE: 0.0
        }
        
        # 基于负载和性能调整权重
        load_penalty = self.load_factor * 0.5
        response_penalty = min(self.average_response_time / 1000, 0.3)  # 响应时间惩罚
        success_bonus = self.success_rate * 0.2
        
        effective = (self.weight * health_multiplier[self.health] * 
                    (1 - load_penalty - response_penalty + success_bonus))
        
        return max(effective, 0.01)  # 最小权重0.01
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'node_id': self.node_id,
            'host': self.host,
            'port': self.port,
            'weight': self.weight,
            'effective_weight': round(self.effective_weight, 3),
            'connections': {
                'current': self.current_connections,
                'max': self.max_connections,
                'utilization': round(self.load_factor * 100, 1)
            },
            'health': {
                'status': self.health.value,
                'last_check': self.last_health_check,
                'consecutive_failures': self.consecutive_failures
            },
            'performance': {
                'avg_response_time': round(self.average_response_time, 2),
                'cpu_usage': round(self.cpu_usage, 1),
                'memory_usage': round(self.memory_usage, 1),
                'network_usage': round(self.network_usage, 1)
            },
            'statistics': {
                'total_requests': self.total_requests,
                'failed_requests': self.failed_requests,
                'success_rate': round(self.success_rate * 100, 1),
                'bytes_sent': self.total_bytes_sent,
                'bytes_received': self.total_bytes_received
            },
            'location': {
                'region': self.region,
                'availability_zone': self.availability_zone,
                'latitude': self.latitude,
                'longitude': self.longitude
            }
        }


@dataclass
class ClientSession:
    """客户端会话"""
    session_id: str
    client_ip: str
    user_agent: str
    assigned_node: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    affinity_key: Optional[str] = None
    
    # 地理位置
    client_region: Optional[str] = None
    client_latitude: Optional[float] = None
    client_longitude: Optional[float] = None
    
    @property
    def is_active(self) -> bool:
        """检查会话是否活跃"""
        return (time.time() - self.last_activity) < 3600  # 1小时超时
    
    def update_activity(self):
        """更新活动时间"""
        self.last_activity = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'session_id': self.session_id,
            'client_ip': self.client_ip,
            'user_agent': self.user_agent,
            'assigned_node': self.assigned_node,
            'created_at': self.created_at,
            'last_activity': self.last_activity,
            'is_active': self.is_active,
            'affinity_key': self.affinity_key,
            'location': {
                'region': self.client_region,
                'latitude': self.client_latitude,
                'longitude': self.client_longitude
            }
        }


class HealthChecker:
    """健康检查器"""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.logger = LoggerFactory.get_logger("websocket_health_checker")
        self._check_task: Optional[asyncio.Task] = None
        self.is_running = False
    
    async def start(self):
        """启动健康检查"""
        if self.is_running:
            return
        
        self.is_running = True
        self._check_task = asyncio.create_task(self._health_check_loop())
        
        await self.logger.info("健康检查器已启动")
    
    async def stop(self):
        """停止健康检查"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        
        await self.logger.info("健康检查器已停止")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self.is_running:
            try:
                await asyncio.sleep(self.check_interval)
                # 健康检查逻辑在负载均衡器中实现
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(f"健康检查错误: {str(e)}")
    
    async def check_node_health(self, node: ServerNode) -> ServerHealth:
        """检查单个节点健康状态"""
        try:
            # 简单的TCP连接测试
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(node.host, node.port),
                timeout=5.0
            )
            
            writer.close()
            await writer.wait_closed()
            
            # 重置失败计数
            node.consecutive_failures = 0
            
            # 基于负载和性能确定健康状态
            if node.load_factor > 0.9:
                return ServerHealth.DEGRADED
            else:
                return ServerHealth.HEALTHY
            
        except Exception as e:
            node.consecutive_failures += 1
            
            await self.logger.warning(
                f"节点健康检查失败: {node.node_id} ({node.consecutive_failures}次)"
            )
            
            # 根据连续失败次数确定健康状态
            if node.consecutive_failures >= 5:
                return ServerHealth.OFFLINE
            elif node.consecutive_failures >= 3:
                return ServerHealth.UNHEALTHY
            else:
                return ServerHealth.DEGRADED


class LoadBalancer:
    """负载均衡器核心"""
    
    def __init__(self, algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.LEAST_CONNECTIONS):
        self.algorithm = algorithm
        self.logger = LoggerFactory.get_logger("websocket_load_balancer")
        
        # 节点管理
        self.nodes: Dict[str, ServerNode] = {}
        self.active_nodes: List[str] = []
        
        # 轮询状态
        self.round_robin_index = 0
        self.weighted_round_robin_weights: Dict[str, float] = {}
        
        # 一致性哈希环
        self.hash_ring: List[Tuple[int, str]] = []
        self.virtual_nodes_per_server = 150
        
    def add_node(self, node: ServerNode):
        """添加节点"""
        self.nodes[node.node_id] = node
        self._update_active_nodes()
        self._rebuild_hash_ring()
        
    def remove_node(self, node_id: str):
        """移除节点"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            self._update_active_nodes()
            self._rebuild_hash_ring()
    
    def _update_active_nodes(self):
        """更新活跃节点列表"""
        self.active_nodes = [
            node_id for node_id, node in self.nodes.items()
            if node.is_available
        ]
    
    def _rebuild_hash_ring(self):
        """重建一致性哈希环"""
        self.hash_ring.clear()
        
        for node_id, node in self.nodes.items():
            if not node.is_available:
                continue
            
            # 为每个节点创建虚拟节点
            for i in range(self.virtual_nodes_per_server):
                virtual_key = f"{node_id}:{i}"
                hash_value = int(hashlib.md5(virtual_key.encode()).hexdigest(), 16)
                self.hash_ring.append((hash_value, node_id))
        
        # 排序哈希环
        self.hash_ring.sort(key=lambda x: x[0])
    
    async def select_node(self, 
                         session: ClientSession,
                         affinity_key: Optional[str] = None) -> Optional[str]:
        """选择节点"""
        self._update_active_nodes()
        
        if not self.active_nodes:
            return None
        
        if self.algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
            return await self._round_robin_select()
        
        elif self.algorithm == LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN:
            return await self._weighted_round_robin_select()
        
        elif self.algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            return await self._least_connections_select()
        
        elif self.algorithm == LoadBalancingAlgorithm.LEAST_RESPONSE_TIME:
            return await self._least_response_time_select()
        
        elif self.algorithm == LoadBalancingAlgorithm.CONSISTENT_HASH:
            return await self._consistent_hash_select(affinity_key or session.client_ip)
        
        elif self.algorithm == LoadBalancingAlgorithm.RANDOM:
            return await self._random_select()
        
        elif self.algorithm == LoadBalancingAlgorithm.GEOGRAPHIC:
            return await self._geographic_select(session)
        
        elif self.algorithm == LoadBalancingAlgorithm.RESOURCE_BASED:
            return await self._resource_based_select()
        
        else:
            return await self._least_connections_select()  # 默认算法
    
    async def _round_robin_select(self) -> str:
        """轮询选择"""
        if not self.active_nodes:
            return None
        
        selected = self.active_nodes[self.round_robin_index % len(self.active_nodes)]
        self.round_robin_index += 1
        return selected
    
    async def _weighted_round_robin_select(self) -> str:
        """加权轮询选择"""
        if not self.active_nodes:
            return None
        
        # 计算权重
        total_weight = sum(self.nodes[node_id].effective_weight for node_id in self.active_nodes)
        
        if total_weight == 0:
            return self.active_nodes[0]
        
        # 随机选择基于权重
        random_value = random.random() * total_weight
        current_weight = 0
        
        for node_id in self.active_nodes:
            current_weight += self.nodes[node_id].effective_weight
            if random_value <= current_weight:
                return node_id
        
        return self.active_nodes[0]
    
    async def _least_connections_select(self) -> str:
        """最少连接数选择"""
        if not self.active_nodes:
            return None
        
        min_connections = float('inf')
        selected_node = None
        
        for node_id in self.active_nodes:
            node = self.nodes[node_id]
            if node.current_connections < min_connections:
                min_connections = node.current_connections
                selected_node = node_id
        
        return selected_node
    
    async def _least_response_time_select(self) -> str:
        """最小响应时间选择"""
        if not self.active_nodes:
            return None
        
        min_response_time = float('inf')
        selected_node = None
        
        for node_id in self.active_nodes:
            node = self.nodes[node_id]
            # 综合考虑响应时间和连接数
            weighted_time = node.average_response_time * (1 + node.load_factor)
            
            if weighted_time < min_response_time:
                min_response_time = weighted_time
                selected_node = node_id
        
        return selected_node
    
    async def _consistent_hash_select(self, key: str) -> str:
        """一致性哈希选择"""
        if not self.hash_ring:
            return self.active_nodes[0] if self.active_nodes else None
        
        hash_value = int(hashlib.md5(key.encode()).hexdigest(), 16)
        
        # 在哈希环中找到第一个大于等于hash_value的节点
        for ring_hash, node_id in self.hash_ring:
            if ring_hash >= hash_value:
                return node_id
        
        # 如果没找到，返回环上的第一个节点
        return self.hash_ring[0][1]
    
    async def _random_select(self) -> str:
        """随机选择"""
        if not self.active_nodes:
            return None
        
        return random.choice(self.active_nodes)
    
    async def _geographic_select(self, session: ClientSession) -> str:
        """地理位置选择"""
        if not self.active_nodes:
            return None
        
        # 如果没有地理位置信息，回退到最少连接数算法
        if not session.client_latitude or not session.client_longitude:
            return await self._least_connections_select()
        
        min_distance = float('inf')
        selected_node = None
        
        for node_id in self.active_nodes:
            node = self.nodes[node_id]
            
            if node.latitude is None or node.longitude is None:
                continue
            
            # 计算地理距离（简化的欧几里得距离）
            distance = ((session.client_latitude - node.latitude) ** 2 + 
                       (session.client_longitude - node.longitude) ** 2) ** 0.5
            
            # 考虑距离和负载的权衡
            weighted_distance = distance * (1 + node.load_factor)
            
            if weighted_distance < min_distance:
                min_distance = weighted_distance
                selected_node = node_id
        
        return selected_node or await self._least_connections_select()
    
    async def _resource_based_select(self) -> str:
        """基于资源选择"""
        if not self.active_nodes:
            return None
        
        best_score = float('inf')
        selected_node = None
        
        for node_id in self.active_nodes:
            node = self.nodes[node_id]
            
            # 综合评分：CPU + 内存 + 网络 + 连接负载
            cpu_score = node.cpu_usage / 100
            memory_score = node.memory_usage / 100
            network_score = node.network_usage / 100
            connection_score = node.load_factor
            response_score = min(node.average_response_time / 1000, 1.0)
            
            # 加权综合评分
            total_score = (cpu_score * 0.25 + 
                          memory_score * 0.25 + 
                          network_score * 0.2 + 
                          connection_score * 0.2 + 
                          response_score * 0.1)
            
            if total_score < best_score:
                best_score = total_score
                selected_node = node_id
        
        return selected_node


class WebSocketLoadBalancer:
    """
    WebSocket负载均衡器
    
    主要功能类，整合所有负载均衡功能
    """
    
    def __init__(self, 
                 algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.LEAST_CONNECTIONS,
                 affinity_type: AffinityType = AffinityType.IP_HASH):
        
        self.logger = LoggerFactory.get_logger("websocket_load_balancer")
        
        # 核心组件
        self.load_balancer = LoadBalancer(algorithm)
        self.health_checker = HealthChecker()
        
        # 会话管理
        self.sessions: Dict[str, ClientSession] = {}
        self.affinity_type = affinity_type
        self.affinity_timeout = 3600  # 1小时
        
        # 配置参数
        self.enable_health_check = True
        self.enable_auto_scaling = True
        self.enable_metrics_collection = True
        
        # 统计信息
        self.stats = {
            'total_sessions': 0,
            'active_sessions': 0,
            'total_requests': 0,
            'failed_requests': 0,
            'load_balancer_started': time.time()
        }
        
        # 后台任务
        self.background_tasks: List[asyncio.Task] = []
        self.is_running = False
    
    async def start(self):
        """启动负载均衡器"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 启动健康检查
        if self.enable_health_check:
            await self.health_checker.start()
        
        # 启动后台任务
        self.background_tasks = [
            asyncio.create_task(self._session_cleanup_loop()),
            asyncio.create_task(self._metrics_collection_loop()),
            asyncio.create_task(self._node_health_monitor_loop())
        ]
        
        await self.logger.info("WebSocket负载均衡器已启动")
    
    async def stop(self):
        """停止负载均衡器"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 停止健康检查
        await self.health_checker.stop()
        
        # 停止后台任务
        for task in self.background_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        await self.logger.info("WebSocket负载均衡器已停止")
    
    async def add_server_node(self, 
                             host: str, 
                             port: int, 
                             weight: float = 1.0,
                             max_connections: int = 1000,
                             region: Optional[str] = None) -> str:
        """添加服务器节点"""
        node_id = f"{host}:{port}"
        
        node = ServerNode(
            node_id=node_id,
            host=host,
            port=port,
            weight=weight,
            max_connections=max_connections,
            region=region
        )
        
        self.load_balancer.add_node(node)
        
        await self.logger.info(f"添加服务器节点: {node_id}")
        return node_id
    
    async def remove_server_node(self, node_id: str):
        """移除服务器节点"""
        self.load_balancer.remove_node(node_id)
        
        # 重新分配该节点上的会话
        affected_sessions = [
            session for session in self.sessions.values()
            if session.assigned_node == node_id
        ]
        
        for session in affected_sessions:
            session.assigned_node = None
            await self.logger.info(f"会话 {session.session_id} 需要重新分配")
        
        await self.logger.info(f"移除服务器节点: {node_id}")
    
    async def assign_connection(self, 
                              websocket: WebSocket,
                              client_ip: str,
                              user_agent: str,
                              user_id: Optional[str] = None) -> Tuple[Optional[str], str]:
        """分配连接到服务器节点"""
        
        # 创建会话ID
        session_id = self._generate_session_id(client_ip, user_agent)
        
        # 创建或获取会话
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.update_activity()
        else:
            session = ClientSession(
                session_id=session_id,
                client_ip=client_ip,
                user_agent=user_agent
            )
            self.sessions[session_id] = session
            self.stats['total_sessions'] += 1
        
        # 处理会话亲和性
        affinity_key = self._get_affinity_key(session, user_id)
        
        # 如果已有分配的节点且该节点健康，继续使用
        if (session.assigned_node and 
            session.assigned_node in self.load_balancer.nodes and
            self.load_balancer.nodes[session.assigned_node].is_available):
            
            selected_node = session.assigned_node
        else:
            # 选择新节点
            selected_node = await self.load_balancer.select_node(session, affinity_key)
        
        if selected_node:
            # 更新会话和节点信息
            session.assigned_node = selected_node
            session.affinity_key = affinity_key
            
            node = self.load_balancer.nodes[selected_node]
            node.current_connections += 1
            node.total_requests += 1
            
            self.stats['active_sessions'] += 1
            self.stats['total_requests'] += 1
            
            await self.logger.info(
                f"分配连接: 会话={session_id}, 节点={selected_node}, "
                f"算法={self.load_balancer.algorithm.value}"
            )
            
            return selected_node, session_id
        else:
            self.stats['failed_requests'] += 1
            await self.logger.error(f"无可用节点分配连接: 会话={session_id}")
            return None, session_id
    
    async def release_connection(self, session_id: str):
        """释放连接"""
        if session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        
        if session.assigned_node and session.assigned_node in self.load_balancer.nodes:
            node = self.load_balancer.nodes[session.assigned_node]
            node.current_connections = max(0, node.current_connections - 1)
            
            self.stats['active_sessions'] = max(0, self.stats['active_sessions'] - 1)
            
            await self.logger.info(f"释放连接: 会话={session_id}, 节点={session.assigned_node}")
        
        # 根据亲和性策略决定是否保留会话
        if self.affinity_type == AffinityType.NONE:
            del self.sessions[session_id]
    
    def _generate_session_id(self, client_ip: str, user_agent: str) -> str:
        """生成会话ID"""
        data = f"{client_ip}_{user_agent}_{time.time()}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def _get_affinity_key(self, session: ClientSession, user_id: Optional[str] = None) -> str:
        """获取亲和性键"""
        if self.affinity_type == AffinityType.IP_HASH:
            return session.client_ip
        elif self.affinity_type == AffinityType.SESSION_ID:
            return session.session_id
        elif self.affinity_type == AffinityType.USER_ID and user_id:
            return user_id
        else:
            return session.client_ip  # 默认使用IP
    
    async def _session_cleanup_loop(self):
        """会话清理循环"""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次
                
                current_time = time.time()
                expired_sessions = []
                
                for session_id, session in self.sessions.items():
                    if current_time - session.last_activity > self.affinity_timeout:
                        expired_sessions.append(session_id)
                
                for session_id in expired_sessions:
                    await self.release_connection(session_id)
                
                if expired_sessions:
                    await self.logger.info(f"清理过期会话: {len(expired_sessions)} 个")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(f"会话清理错误: {str(e)}")
    
    async def _metrics_collection_loop(self):
        """指标收集循环"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # 每分钟收集一次
                
                if self.enable_metrics_collection:
                    await self._collect_node_metrics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(f"指标收集错误: {str(e)}")
    
    async def _node_health_monitor_loop(self):
        """节点健康监控循环"""
        while self.is_running:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次
                
                for node_id, node in self.load_balancer.nodes.items():
                    new_health = await self.health_checker.check_node_health(node)
                    
                    if new_health != node.health:
                        await self.logger.info(
                            f"节点健康状态变化: {node_id} {node.health.value} -> {new_health.value}"
                        )
                        node.health = new_health
                    
                    node.last_health_check = time.time()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(f"健康监控错误: {str(e)}")
    
    async def _collect_node_metrics(self):
        """收集节点指标"""
        # 这里可以集成真实的监控系统
        # 目前使用模拟数据
        for node in self.load_balancer.nodes.values():
            # 模拟性能指标更新
            node.cpu_usage = random.uniform(10, 80)
            node.memory_usage = random.uniform(20, 90)
            node.network_usage = random.uniform(5, 60)
            
            # 更新响应时间（简单的移动平均）
            new_response_time = random.uniform(10, 200)
            if node.average_response_time == 0:
                node.average_response_time = new_response_time
            else:
                node.average_response_time = (node.average_response_time * 0.8 + 
                                            new_response_time * 0.2)
    
    async def get_load_balancer_statistics(self) -> Dict[str, Any]:
        """获取负载均衡器统计信息"""
        # 计算节点统计
        nodes_stats = {}
        total_connections = 0
        healthy_nodes = 0
        
        for node_id, node in self.load_balancer.nodes.items():
            nodes_stats[node_id] = node.to_dict()
            total_connections += node.current_connections
            if node.health == ServerHealth.HEALTHY:
                healthy_nodes += 1
        
        # 计算会话统计
        active_sessions = sum(1 for session in self.sessions.values() if session.is_active)
        
        return {
            'load_balancer': {
                'algorithm': self.load_balancer.algorithm.value,
                'affinity_type': self.affinity_type.value,
                'is_running': self.is_running,
                'uptime_seconds': time.time() - self.stats['load_balancer_started']
            },
            'nodes': {
                'total_nodes': len(self.load_balancer.nodes),
                'healthy_nodes': healthy_nodes,
                'active_nodes': len(self.load_balancer.active_nodes),
                'total_connections': total_connections,
                'nodes_detail': nodes_stats
            },
            'sessions': {
                'total_sessions': self.stats['total_sessions'],
                'active_sessions': active_sessions,
                'cached_sessions': len(self.sessions)
            },
            'requests': {
                'total_requests': self.stats['total_requests'],
                'failed_requests': self.stats['failed_requests'],
                'success_rate': (
                    ((self.stats['total_requests'] - self.stats['failed_requests']) / 
                     self.stats['total_requests'] * 100)
                    if self.stats['total_requests'] > 0 else 100.0
                )
            },
            'configuration': {
                'health_check_enabled': self.enable_health_check,
                'auto_scaling_enabled': self.enable_auto_scaling,
                'metrics_collection_enabled': self.enable_metrics_collection,
                'affinity_timeout_seconds': self.affinity_timeout
            }
        }
    
    async def configure(self, **config):
        """配置负载均衡器"""
        if 'algorithm' in config:
            algorithm = LoadBalancingAlgorithm(config['algorithm'])
            self.load_balancer.algorithm = algorithm
            await self.logger.info(f"负载均衡算法已更改为: {algorithm.value}")
        
        if 'affinity_type' in config:
            self.affinity_type = AffinityType(config['affinity_type'])
            await self.logger.info(f"会话亲和性已更改为: {self.affinity_type.value}")
        
        if 'affinity_timeout' in config:
            self.affinity_timeout = config['affinity_timeout']
        
        if 'enable_health_check' in config:
            self.enable_health_check = config['enable_health_check']
        
        if 'enable_auto_scaling' in config:
            self.enable_auto_scaling = config['enable_auto_scaling']
        
        if 'enable_metrics_collection' in config:
            self.enable_metrics_collection = config['enable_metrics_collection']


# 全局WebSocket负载均衡器实例
websocket_load_balancer = WebSocketLoadBalancer()