#!/usr/bin/env python3
"""
网络优化套件 - 集成所有网络和WebSocket优化功能

功能模块集成:
1. WebSocket连接池管理
2. 消息压缩和批量传输
3. 可靠性保证层
4. HTTP/2优化
5. 网络性能监控
6. 负载均衡
7. 统一管理和配置接口
"""

import asyncio
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
try:
    from fastapi.middleware.base import BaseHTTPMiddleware
except ImportError:
    from starlette.middleware.base import BaseHTTPMiddleware

from middleware.unified_logging import LoggerFactory, LogCategory
from middleware.websocket_connection_pool import connection_pool_manager, WebSocketConnectionPoolManager
from middleware.websocket_message_optimizer import message_optimizer, WebSocketMessageOptimizer, MessagePriority
from middleware.websocket_reliability_layer import reliability_manager, WebSocketReliabilityManager, QoSLevel
from middleware.http2_optimization import HTTP2OptimizationMiddleware, get_http2_optimization_middleware, set_http2_optimization_middleware
from middleware.network_performance_monitor import network_performance_monitor, NetworkPerformanceMonitor, DiagnosticLevel
from middleware.websocket_load_balancer import websocket_load_balancer, WebSocketLoadBalancer, LoadBalancingAlgorithm


class OptimizationLevel(Enum):
    """优化级别"""
    BASIC = "basic"           # 基础优化
    STANDARD = "standard"     # 标准优化
    ADVANCED = "advanced"     # 高级优化
    ENTERPRISE = "enterprise" # 企业级优化


@dataclass
class NetworkOptimizationConfig:
    """网络优化配置"""
    optimization_level: OptimizationLevel = OptimizationLevel.STANDARD
    
    # WebSocket连接池配置
    enable_connection_pooling: bool = True
    max_connections_per_pool: int = 100
    min_connections_per_pool: int = 2
    
    # 消息优化配置
    enable_message_compression: bool = True
    enable_message_batching: bool = True
    enable_message_deduplication: bool = True
    
    # 可靠性配置
    enable_reliability_layer: bool = True
    default_qos_level: QoSLevel = QoSLevel.AT_LEAST_ONCE
    enable_message_acknowledgment: bool = True
    
    # HTTP/2配置
    enable_http2_optimization: bool = True
    enable_server_push: bool = True
    enable_header_compression: bool = True
    
    # 性能监控配置
    enable_performance_monitoring: bool = True
    monitoring_interval_seconds: int = 60
    enable_network_diagnostics: bool = True
    
    # 负载均衡配置
    enable_load_balancing: bool = False  # 默认关闭，单节点部署
    load_balancing_algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.LEAST_CONNECTIONS
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'optimization_level': self.optimization_level.value,
            'connection_pooling': {
                'enabled': self.enable_connection_pooling,
                'max_connections': self.max_connections_per_pool,
                'min_connections': self.min_connections_per_pool
            },
            'message_optimization': {
                'compression_enabled': self.enable_message_compression,
                'batching_enabled': self.enable_message_batching,
                'deduplication_enabled': self.enable_message_deduplication
            },
            'reliability': {
                'enabled': self.enable_reliability_layer,
                'default_qos': self.default_qos_level.value,
                'acknowledgment_enabled': self.enable_message_acknowledgment
            },
            'http2': {
                'enabled': self.enable_http2_optimization,
                'server_push_enabled': self.enable_server_push,
                'header_compression_enabled': self.enable_header_compression
            },
            'monitoring': {
                'enabled': self.enable_performance_monitoring,
                'interval_seconds': self.monitoring_interval_seconds,
                'diagnostics_enabled': self.enable_network_diagnostics
            },
            'load_balancing': {
                'enabled': self.enable_load_balancing,
                'algorithm': self.load_balancing_algorithm.value
            }
        }


class NetworkOptimizationSuite:
    """
    网络优化套件 - 统一管理所有网络优化功能
    """
    
    def __init__(self, config: Optional[NetworkOptimizationConfig] = None):
        self.config = config or NetworkOptimizationConfig()
        self.logger = LoggerFactory.get_logger("network_optimization_suite")
        
        # 组件管理
        self.connection_pool_manager: Optional[WebSocketConnectionPoolManager] = None
        self.message_optimizer: Optional[WebSocketMessageOptimizer] = None
        self.reliability_manager: Optional[WebSocketReliabilityManager] = None
        self.http2_middleware: Optional[HTTP2OptimizationMiddleware] = None
        self.performance_monitor: Optional[NetworkPerformanceMonitor] = None
        self.load_balancer: Optional[WebSocketLoadBalancer] = None
        
        # 运行状态
        self.is_initialized = False
        self.is_running = False
        self.initialization_time: Optional[float] = None
        
        # 统计信息
        self.stats = {
            'total_optimized_connections': 0,
            'total_compressed_messages': 0,
            'total_reliable_messages': 0,
            'total_http2_streams': 0,
            'suite_start_time': None
        }
    
    async def initialize(self):
        """初始化优化套件"""
        if self.is_initialized:
            return
        
        start_time = time.time()
        await self.logger.info("开始初始化网络优化套件...")
        
        try:
            # 1. 初始化连接池管理器
            if self.config.enable_connection_pooling:
                self.connection_pool_manager = connection_pool_manager
                await self.logger.info("✓ WebSocket连接池管理器已初始化")
            
            # 2. 初始化消息优化器
            if (self.config.enable_message_compression or 
                self.config.enable_message_batching or 
                self.config.enable_message_deduplication):
                
                self.message_optimizer = message_optimizer
                
                # 配置消息优化器
                self.message_optimizer.configure(
                    enable_compression=self.config.enable_message_compression,
                    enable_batching=self.config.enable_message_batching,
                    enable_deduplication=self.config.enable_message_deduplication
                )
                await self.logger.info("✓ WebSocket消息优化器已初始化")
            
            # 3. 初始化可靠性管理器
            if self.config.enable_reliability_layer:
                self.reliability_manager = reliability_manager
                await self.logger.info("✓ WebSocket可靠性管理器已初始化")
            
            # 4. 初始化HTTP/2优化中间件
            if self.config.enable_http2_optimization:
                # HTTP/2中间件将在FastAPI应用中添加
                await self.logger.info("✓ HTTP/2优化中间件已准备")
            
            # 5. 初始化性能监控器
            if self.config.enable_performance_monitoring:
                self.performance_monitor = network_performance_monitor
                await self.logger.info("✓ 网络性能监控器已初始化")
            
            # 6. 初始化负载均衡器（如果启用）
            if self.config.enable_load_balancing:
                self.load_balancer = websocket_load_balancer
                await self.load_balancer.configure(
                    algorithm=self.config.load_balancing_algorithm.value
                )
                await self.logger.info("✓ WebSocket负载均衡器已初始化")
            
            self.is_initialized = True
            self.initialization_time = time.time() - start_time
            
            await self.logger.info(
                f"网络优化套件初始化完成 (耗时: {self.initialization_time:.2f}秒)"
            )
            
        except Exception as e:
            await self.logger.error(f"网络优化套件初始化失败: {str(e)}")
            raise
    
    async def start(self):
        """启动优化套件"""
        if not self.is_initialized:
            await self.initialize()
        
        if self.is_running:
            return
        
        await self.logger.info("启动网络优化套件...")
        
        try:
            # 启动性能监控
            if self.performance_monitor:
                await self.performance_monitor.start_monitoring()
            
            # 启动负载均衡器
            if self.load_balancer:
                await self.load_balancer.start()
            
            self.is_running = True
            self.stats['suite_start_time'] = time.time()
            
            await self.logger.info("网络优化套件已启动")
            
        except Exception as e:
            await self.logger.error(f"网络优化套件启动失败: {str(e)}")
            raise
    
    async def stop(self):
        """停止优化套件"""
        if not self.is_running:
            return
        
        await self.logger.info("停止网络优化套件...")
        
        try:
            # 停止性能监控
            if self.performance_monitor:
                await self.performance_monitor.stop_monitoring()
            
            # 停止负载均衡器
            if self.load_balancer:
                await self.load_balancer.stop()
            
            # 关闭所有连接池
            if self.connection_pool_manager:
                await self.connection_pool_manager.shutdown_all()
            
            # 关闭所有可靠性会话
            if self.reliability_manager:
                await self.reliability_manager.shutdown_all_sessions()
            
            self.is_running = False
            await self.logger.info("网络优化套件已停止")
            
        except Exception as e:
            await self.logger.error(f"网络优化套件停止时出错: {str(e)}")
    
    async def optimize_websocket_connection(self, 
                                          websocket: WebSocket,
                                          connection_id: str,
                                          client_info: Dict[str, Any]) -> Dict[str, Any]:
        """优化WebSocket连接"""
        optimization_result = {
            'connection_id': connection_id,
            'optimizations_applied': [],
            'performance_metrics': {}
        }
        
        try:
            # 1. 连接池管理
            if self.connection_pool_manager:
                pool = await self.connection_pool_manager.get_pool("default")
                if not pool:
                    pool = await self.connection_pool_manager.create_pool("default")
                
                pool_connection_id = await pool.add_connection(websocket, client_info)
                if pool_connection_id:
                    optimization_result['optimizations_applied'].append('connection_pooling')
                    optimization_result['pool_connection_id'] = pool_connection_id
            
            # 2. 可靠性会话
            if self.reliability_manager:
                session = await self.reliability_manager.create_session(
                    connection_id=connection_id,
                    websocket=websocket
                )
                if session:
                    optimization_result['optimizations_applied'].append('reliability_layer')
                    optimization_result['reliability_session_id'] = connection_id
            
            # 3. 负载均衡（如果启用）
            if self.load_balancer:
                node_id, session_id = await self.load_balancer.assign_connection(
                    websocket=websocket,
                    client_ip=client_info.get('ip', 'unknown'),
                    user_agent=client_info.get('user_agent', 'unknown')
                )
                if node_id:
                    optimization_result['optimizations_applied'].append('load_balancing')
                    optimization_result['assigned_node'] = node_id
                    optimization_result['session_id'] = session_id
            
            # 更新统计
            self.stats['total_optimized_connections'] += 1
            
            await self.logger.info(
                f"WebSocket连接已优化: {connection_id}, "
                f"应用优化: {optimization_result['optimizations_applied']}"
            )
            
            return optimization_result
            
        except Exception as e:
            await self.logger.error(f"WebSocket连接优化失败: {str(e)}")
            optimization_result['error'] = str(e)
            return optimization_result
    
    async def optimize_message(self, 
                             message_content: str,
                             connection_id: str,
                             priority: MessagePriority = MessagePriority.NORMAL) -> Optional[Any]:
        """优化消息传输"""
        if not self.message_optimizer:
            return message_content
        
        try:
            optimized_result = await self.message_optimizer.optimize_message(
                content=message_content,
                connection_id=connection_id,
                priority=priority
            )
            
            if optimized_result:
                self.stats['total_compressed_messages'] += 1
                return optimized_result
            
            return message_content
            
        except Exception as e:
            await self.logger.error(f"消息优化失败: {str(e)}")
            return message_content
    
    async def send_reliable_message(self,
                                  connection_id: str,
                                  content: Any,
                                  qos_level: Optional[QoSLevel] = None) -> Optional[str]:
        """发送可靠消息"""
        if not self.reliability_manager:
            return None
        
        try:
            session = await self.reliability_manager.get_session(connection_id)
            if not session:
                return None
            
            qos = qos_level or self.config.default_qos_level
            
            message_id = await session.send_message(
                content=content,
                qos_level=qos
            )
            
            if message_id:
                self.stats['total_reliable_messages'] += 1
            
            return message_id
            
        except Exception as e:
            await self.logger.error(f"可靠消息发送失败: {str(e)}")
            return None
    
    async def cleanup_connection(self, connection_id: str):
        """清理连接资源"""
        try:
            # 清理连接池连接
            if self.connection_pool_manager:
                for pool_id, pool in self.connection_pool_manager.pools.items():
                    if connection_id in pool.connections:
                        await pool.remove_connection(connection_id)
            
            # 清理可靠性会话
            if self.reliability_manager:
                await self.reliability_manager.remove_session(connection_id)
            
            # 清理负载均衡会话
            if self.load_balancer:
                await self.load_balancer.release_connection(connection_id)
            
            await self.logger.debug(f"连接资源已清理: {connection_id}")
            
        except Exception as e:
            await self.logger.error(f"连接清理失败: {str(e)}")
    
    async def run_network_diagnostics(self, level: DiagnosticLevel = DiagnosticLevel.STANDARD) -> Dict[str, Any]:
        """运行网络诊断"""
        if not self.performance_monitor:
            return {'error': 'Performance monitor not enabled'}
        
        try:
            diagnostic_results = await self.performance_monitor.run_diagnostics(level)
            
            return {
                'diagnostic_level': level.name,
                'test_count': len(diagnostic_results),
                'results': [result.to_dict() for result in diagnostic_results],
                'summary': self._summarize_diagnostic_results(diagnostic_results)
            }
            
        except Exception as e:
            await self.logger.error(f"网络诊断失败: {str(e)}")
            return {'error': str(e)}
    
    def _summarize_diagnostic_results(self, results) -> Dict[str, Any]:
        """汇总诊断结果"""
        passed = sum(1 for r in results if r.status == 'passed')
        warnings = sum(1 for r in results if r.status == 'warning')
        failed = sum(1 for r in results if r.status == 'failed')
        errors = sum(1 for r in results if r.status == 'error')
        
        return {
            'total_tests': len(results),
            'passed': passed,
            'warnings': warnings,
            'failed': failed,
            'errors': errors,
            'success_rate': round(passed / len(results) * 100, 1) if results else 0
        }
    
    async def get_optimization_statistics(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        stats = {
            'suite_info': {
                'optimization_level': self.config.optimization_level.value,
                'is_initialized': self.is_initialized,
                'is_running': self.is_running,
                'initialization_time_seconds': self.initialization_time,
                'uptime_seconds': (time.time() - self.stats['suite_start_time']) 
                                if self.stats['suite_start_time'] else 0
            },
            'configuration': self.config.to_dict(),
            'global_statistics': self.stats.copy()
        }
        
        # 收集各组件统计
        try:
            # 连接池统计
            if self.connection_pool_manager:
                pool_stats = await self.connection_pool_manager.get_all_statistics()
                stats['connection_pools'] = pool_stats
            
            # 消息优化统计
            if self.message_optimizer:
                optimizer_stats = self.message_optimizer.get_optimization_statistics()
                stats['message_optimization'] = optimizer_stats
            
            # 可靠性统计
            if self.reliability_manager:
                reliability_stats = await self.reliability_manager.get_all_statistics()
                stats['reliability'] = reliability_stats
            
            # HTTP/2统计
            http2_middleware = get_http2_optimization_middleware()
            if http2_middleware:
                http2_stats = await http2_middleware.get_optimization_statistics()
                stats['http2_optimization'] = http2_stats
            
            # 性能监控统计
            if self.performance_monitor:
                monitoring_stats = await self.performance_monitor.get_monitoring_statistics()
                stats['performance_monitoring'] = monitoring_stats
            
            # 负载均衡统计
            if self.load_balancer:
                lb_stats = await self.load_balancer.get_load_balancer_statistics()
                stats['load_balancing'] = lb_stats
        
        except Exception as e:
            stats['statistics_collection_error'] = str(e)
            await self.logger.error(f"统计信息收集失败: {str(e)}")
        
        return stats
    
    async def configure(self, **config_updates):
        """动态配置优化套件"""
        try:
            # 更新配置
            for key, value in config_updates.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            
            # 应用配置到各组件
            if self.message_optimizer and 'message_optimization' in config_updates:
                msg_config = config_updates['message_optimization']
                self.message_optimizer.configure(**msg_config)
            
            if self.load_balancer and 'load_balancing' in config_updates:
                lb_config = config_updates['load_balancing']
                await self.load_balancer.configure(**lb_config)
            
            http2_middleware = get_http2_optimization_middleware()
            if http2_middleware and 'http2' in config_updates:
                http2_config = config_updates['http2']
                await http2_middleware.configure(**http2_config)
            
            await self.logger.info("网络优化套件配置已更新")
            
        except Exception as e:
            await self.logger.error(f"配置更新失败: {str(e)}")
            raise
    
    def create_fastapi_middleware(self, app: FastAPI):
        """为FastAPI应用创建中间件"""
        
        # 添加HTTP/2优化中间件
        if self.config.enable_http2_optimization:
            http2_middleware = HTTP2OptimizationMiddleware(app)
            set_http2_optimization_middleware(http2_middleware)
            app.add_middleware(HTTP2OptimizationMiddleware)
        
        # 添加自定义网络优化中间件
        @app.middleware("http")
        async def network_optimization_middleware(request: Request, call_next):
            # 在这里可以添加HTTP层面的优化
            response = await call_next(request)
            
            # 添加优化相关的响应头
            response.headers["X-Network-Optimization"] = "enabled"
            response.headers["X-Optimization-Level"] = self.config.optimization_level.value
            
            return response
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        return {
            'status': 'healthy' if (self.is_initialized and self.is_running) else 'unhealthy',
            'components': {
                'connection_pooling': self.connection_pool_manager is not None,
                'message_optimization': self.message_optimizer is not None,
                'reliability_layer': self.reliability_manager is not None,
                'http2_optimization': get_http2_optimization_middleware() is not None,
                'performance_monitoring': self.performance_monitor is not None,
                'load_balancing': self.load_balancer is not None
            },
            'timestamp': datetime.now().isoformat()
        }


# 全局网络优化套件实例
network_optimization_suite = NetworkOptimizationSuite()


# 便捷函数
async def initialize_network_optimizations(
    app: FastAPI,
    config: Optional[NetworkOptimizationConfig] = None
):
    """初始化网络优化功能"""
    global network_optimization_suite
    
    if config:
        network_optimization_suite.config = config
    
    await network_optimization_suite.initialize()
    await network_optimization_suite.start()
    
    # 为FastAPI应用添加中间件
    network_optimization_suite.create_fastapi_middleware(app)


async def cleanup_network_optimizations():
    """清理网络优化功能"""
    await network_optimization_suite.stop()


def get_network_optimization_suite() -> NetworkOptimizationSuite:
    """获取网络优化套件实例"""
    return network_optimization_suite