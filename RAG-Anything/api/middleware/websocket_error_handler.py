#!/usr/bin/env python3
"""
WebSocket错误处理和连接管理
提供健壮的WebSocket连接管理、错误处理和自动重连机制
"""

import json
import asyncio
import logging
import traceback
from typing import Dict, Any, List, Optional, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from contextvars import ContextVar

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from middleware.unified_logging import LoggerFactory, LogCategory
from middleware.error_tracking import error_tracker, trace_span, SpanType


# WebSocket上下文
websocket_context: ContextVar[str] = ContextVar('websocket_context', default='')


class ConnectionState(Enum):
    """连接状态"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


class MessageType(Enum):
    """消息类型"""
    LOG = "log"
    ERROR = "error"
    PROGRESS = "progress"
    STATUS = "status"
    HEARTBEAT = "heartbeat"
    RECONNECT = "reconnect"
    CLOSE = "close"


@dataclass
class WebSocketClient:
    """WebSocket客户端信息"""
    client_id: str
    websocket: WebSocket
    connected_at: datetime
    last_heartbeat: datetime
    state: ConnectionState = ConnectionState.CONNECTING
    error_count: int = 0
    total_messages_sent: int = 0
    total_messages_received: int = 0
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    subscriptions: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        self.last_heartbeat = self.connected_at
    
    def is_active(self) -> bool:
        """检查连接是否活跃"""
        return (self.state == ConnectionState.CONNECTED and 
                self.websocket.client_state == WebSocketState.CONNECTED)
    
    def is_stale(self, timeout_seconds: int = 60) -> bool:
        """检查连接是否过期"""
        return (datetime.now() - self.last_heartbeat).total_seconds() > timeout_seconds
    
    def update_heartbeat(self):
        """更新心跳时间"""
        self.last_heartbeat = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'client_id': self.client_id,
            'connected_at': self.connected_at.isoformat(),
            'last_heartbeat': self.last_heartbeat.isoformat(),
            'state': self.state.value,
            'error_count': self.error_count,
            'total_messages_sent': self.total_messages_sent,
            'total_messages_received': self.total_messages_received,
            'user_agent': self.user_agent,
            'ip_address': self.ip_address,
            'subscriptions': list(self.subscriptions)
        }


@dataclass
class WebSocketMessage:
    """WebSocket消息"""
    message_type: MessageType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    client_id: Optional[str] = None
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps({
            'type': self.message_type.value,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'client_id': self.client_id
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'WebSocketMessage':
        """从JSON字符串创建消息"""
        data = json.loads(json_str)
        return cls(
            message_type=MessageType(data['type']),
            data=data['data'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            client_id=data.get('client_id')
        )


class WebSocketErrorHandler:
    """
    WebSocket错误处理器
    
    功能:
    1. 连接管理和监控
    2. 错误处理和恢复
    3. 自动重连机制
    4. 心跳检测
    5. 消息队列和重试
    6. 连接池管理
    """
    
    def __init__(self):
        self.logger = LoggerFactory.get_logger("websocket_handler")
        self.clients: Dict[str, WebSocketClient] = {}
        self.message_queues: Dict[str, List[WebSocketMessage]] = {}
        
        # 配置参数
        self.heartbeat_interval = 30  # 心跳间隔（秒）
        self.connection_timeout = 120  # 连接超时（秒）
        self.max_message_queue_size = 100
        self.max_reconnect_attempts = 5
        self.reconnect_delay_base = 2  # 重连延迟基数（秒）
        
        # 统计信息
        self.total_connections = 0
        self.total_disconnections = 0
        self.total_errors = 0
        self.connection_history: List[Dict[str, Any]] = []
        
        # 后台任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
    async def start_background_tasks(self):
        """启动后台任务"""
        if not self._heartbeat_task:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop_background_tasks(self):
        """停止后台任务"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def handle_connection(self, websocket: WebSocket, client_id: str) -> WebSocketClient:
        """处理新连接"""
        async with trace_span(f"websocket_connect_{client_id}", SpanType.WEBSOCKET_CONNECTION):
            try:
                await websocket.accept()
                
                # 创建客户端记录
                client = WebSocketClient(
                    client_id=client_id,
                    websocket=websocket,
                    connected_at=datetime.now(),
                    user_agent=websocket.headers.get("user-agent"),
                    ip_address=websocket.client.host if websocket.client else None
                )
                
                client.state = ConnectionState.CONNECTED
                self.clients[client_id] = client
                self.total_connections += 1
                
                # 记录连接历史
                self.connection_history.append({
                    'client_id': client_id,
                    'event': 'connected',
                    'timestamp': datetime.now().isoformat(),
                    'ip_address': client.ip_address,
                    'user_agent': client.user_agent
                })
                
                # 发送欢迎消息
                welcome_message = WebSocketMessage(
                    message_type=MessageType.STATUS,
                    data={
                        'status': 'connected',
                        'client_id': client_id,
                        'server_time': datetime.now().isoformat(),
                        'heartbeat_interval': self.heartbeat_interval
                    },
                    client_id=client_id
                )
                
                await self.send_message_to_client(client_id, welcome_message)
                
                await self.logger.log_websocket_event("connect", client_id, f"Connected from {client.ip_address}")
                
                return client
                
            except Exception as e:
                await self.logger.error(
                    f"WebSocket connection failed: {str(e)}",
                    category=LogCategory.WEBSOCKET,
                    error_details={'client_id': client_id, 'error': str(e)},
                    stack_trace=traceback.format_exc()
                )
                raise
    
    async def handle_disconnection(self, client_id: str, code: Optional[int] = None, 
                                 reason: Optional[str] = None):
        """处理连接断开"""
        if client_id not in self.clients:
            return
        
        client = self.clients[client_id]
        client.state = ConnectionState.DISCONNECTING
        
        try:
            # 记录断开事件
            self.connection_history.append({
                'client_id': client_id,
                'event': 'disconnected',
                'timestamp': datetime.now().isoformat(),
                'code': code,
                'reason': reason,
                'duration_seconds': (datetime.now() - client.connected_at).total_seconds()
            })
            
            await self.logger.log_websocket_event(
                "disconnect", 
                client_id, 
                f"Disconnected: {reason or 'Unknown reason'}"
            )
            
            # 清理客户端资源
            await self._cleanup_client(client_id)
            
        except Exception as e:
            await self.logger.error(
                f"Error handling disconnection: {str(e)}",
                category=LogCategory.WEBSOCKET,
                error_details={'client_id': client_id}
            )
        finally:
            # 从客户端列表中移除
            if client_id in self.clients:
                del self.clients[client_id]
            self.total_disconnections += 1
    
    async def handle_message(self, client_id: str, message: str) -> bool:
        """处理接收到的消息"""
        if client_id not in self.clients:
            return False
        
        client = self.clients[client_id]
        
        try:
            # 解析消息
            ws_message = WebSocketMessage.from_json(message)
            client.total_messages_received += 1
            client.update_heartbeat()
            
            # 处理不同类型的消息
            if ws_message.message_type == MessageType.HEARTBEAT:
                await self._handle_heartbeat(client_id, ws_message)
            elif ws_message.message_type == MessageType.STATUS:
                await self._handle_status_message(client_id, ws_message)
            else:
                await self.logger.debug(
                    f"Received message from {client_id}: {ws_message.message_type.value}",
                    category=LogCategory.WEBSOCKET
                )
            
            return True
            
        except json.JSONDecodeError as e:
            await self.logger.warning(
                f"Invalid JSON from client {client_id}: {str(e)}",
                category=LogCategory.WEBSOCKET
            )
            client.error_count += 1
            return False
        except Exception as e:
            await self.logger.error(
                f"Error handling message from {client_id}: {str(e)}",
                category=LogCategory.WEBSOCKET,
                error_details={'client_id': client_id, 'message': message[:100]}
            )
            client.error_count += 1
            return False
    
    async def send_message_to_client(self, client_id: str, message: WebSocketMessage) -> bool:
        """发送消息给指定客户端"""
        if client_id not in self.clients:
            # 将消息添加到队列等待重连
            await self._queue_message(client_id, message)
            return False
        
        client = self.clients[client_id]
        
        if not client.is_active():
            await self._queue_message(client_id, message)
            return False
        
        try:
            message.client_id = client_id
            json_message = message.to_json()
            
            await client.websocket.send_text(json_message)
            client.total_messages_sent += 1
            
            return True
            
        except WebSocketDisconnect:
            await self.handle_disconnection(client_id, reason="WebSocket disconnected")
            return False
        except Exception as e:
            await self.logger.error(
                f"Error sending message to {client_id}: {str(e)}",
                category=LogCategory.WEBSOCKET,
                error_details={'client_id': client_id, 'message_type': message.message_type.value}
            )
            client.error_count += 1
            return False
    
    async def broadcast_message(self, message: WebSocketMessage, 
                              subscription_filter: Optional[str] = None) -> int:
        """广播消息给所有客户端"""
        sent_count = 0
        
        for client_id, client in self.clients.items():
            # 检查订阅过滤器
            if subscription_filter and subscription_filter not in client.subscriptions:
                continue
            
            if await self.send_message_to_client(client_id, message):
                sent_count += 1
        
        return sent_count
    
    async def send_error_to_client(self, client_id: str, error_code: str, 
                                 error_message: str, details: Optional[Dict[str, Any]] = None):
        """发送错误消息给客户端"""
        error_msg = WebSocketMessage(
            message_type=MessageType.ERROR,
            data={
                'error_code': error_code,
                'error_message': error_message,
                'details': details or {},
                'timestamp': datetime.now().isoformat()
            }
        )
        
        await self.send_message_to_client(client_id, error_msg)
    
    async def _handle_heartbeat(self, client_id: str, message: WebSocketMessage):
        """处理心跳消息"""
        client = self.clients[client_id]
        client.update_heartbeat()
        
        # 发送心跳响应
        pong_message = WebSocketMessage(
            message_type=MessageType.HEARTBEAT,
            data={
                'type': 'pong',
                'server_time': datetime.now().isoformat(),
                'client_stats': {
                    'messages_sent': client.total_messages_sent,
                    'messages_received': client.total_messages_received,
                    'connection_duration': (datetime.now() - client.connected_at).total_seconds()
                }
            }
        )
        
        await self.send_message_to_client(client_id, pong_message)
    
    async def _handle_status_message(self, client_id: str, message: WebSocketMessage):
        """处理状态消息"""
        client = self.clients[client_id]
        data = message.data
        
        # 处理订阅管理
        if 'subscribe' in data:
            subscriptions = data['subscribe']
            if isinstance(subscriptions, list):
                client.subscriptions.update(subscriptions)
                await self.logger.debug(
                    f"Client {client_id} subscribed to: {subscriptions}",
                    category=LogCategory.WEBSOCKET
                )
        
        if 'unsubscribe' in data:
            unsubscriptions = data['unsubscribe']
            if isinstance(unsubscriptions, list):
                client.subscriptions.difference_update(unsubscriptions)
                await self.logger.debug(
                    f"Client {client_id} unsubscribed from: {unsubscriptions}",
                    category=LogCategory.WEBSOCKET
                )
    
    async def _queue_message(self, client_id: str, message: WebSocketMessage):
        """将消息添加到队列"""
        if client_id not in self.message_queues:
            self.message_queues[client_id] = []
        
        queue = self.message_queues[client_id]
        
        # 限制队列大小
        if len(queue) >= self.max_message_queue_size:
            queue.pop(0)  # 移除最旧的消息
        
        queue.append(message)
    
    async def _send_queued_messages(self, client_id: str):
        """发送队列中的消息"""
        if client_id not in self.message_queues:
            return
        
        queue = self.message_queues[client_id]
        sent_messages = []
        
        for message in queue:
            if await self.send_message_to_client(client_id, message):
                sent_messages.append(message)
            else:
                break  # 如果发送失败，停止发送剩余消息
        
        # 移除已发送的消息
        for sent_message in sent_messages:
            queue.remove(sent_message)
        
        if not queue:
            del self.message_queues[client_id]
    
    async def _cleanup_client(self, client_id: str):
        """清理客户端资源"""
        try:
            # 清理消息队列
            if client_id in self.message_queues:
                del self.message_queues[client_id]
            
            await self.logger.debug(
                f"Cleaned up client {client_id}",
                category=LogCategory.WEBSOCKET
            )
            
        except Exception as e:
            await self.logger.error(
                f"Error cleaning up client {client_id}: {str(e)}",
                category=LogCategory.WEBSOCKET
            )
    
    async def _heartbeat_loop(self):
        """心跳检测循环"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                stale_clients = []
                for client_id, client in self.clients.items():
                    if client.is_stale(self.connection_timeout):
                        stale_clients.append(client_id)
                
                # 断开过期的连接
                for client_id in stale_clients:
                    await self.handle_disconnection(
                        client_id, 
                        reason=f"Connection timeout ({self.connection_timeout}s)"
                    )
                    await self.logger.warning(
                        f"Disconnected stale client: {client_id}",
                        category=LogCategory.WEBSOCKET
                    )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(
                    f"Error in heartbeat loop: {str(e)}",
                    category=LogCategory.WEBSOCKET
                )
    
    async def _cleanup_loop(self):
        """清理循环"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次
                
                # 限制连接历史记录数量
                if len(self.connection_history) > 1000:
                    self.connection_history = self.connection_history[-500:]
                
                # 清理空的消息队列
                empty_queues = [
                    client_id for client_id, queue in self.message_queues.items() 
                    if not queue
                ]
                for client_id in empty_queues:
                    del self.message_queues[client_id]
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(
                    f"Error in cleanup loop: {str(e)}",
                    category=LogCategory.WEBSOCKET
                )
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计"""
        active_connections = len([c for c in self.clients.values() if c.is_active()])
        
        return {
            'total_connections': self.total_connections,
            'active_connections': active_connections,
            'total_disconnections': self.total_disconnections,
            'total_errors': self.total_errors,
            'queued_messages': sum(len(queue) for queue in self.message_queues.values()),
            'connection_success_rate': (
                (self.total_connections - self.total_errors) / self.total_connections * 100
                if self.total_connections > 0 else 100
            )
        }
    
    def get_client_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """获取客户端信息"""
        if client_id not in self.clients:
            return None
        
        return self.clients[client_id].to_dict()
    
    def get_all_clients_info(self) -> List[Dict[str, Any]]:
        """获取所有客户端信息"""
        return [client.to_dict() for client in self.clients.values()]


# 全局WebSocket错误处理器实例
websocket_error_handler = WebSocketErrorHandler()


# 便捷函数
async def send_log_to_websocket(log_data: Dict[str, Any]):
    """发送日志到WebSocket客户端"""
    log_message = WebSocketMessage(
        message_type=MessageType.LOG,
        data=log_data
    )
    
    await websocket_error_handler.broadcast_message(log_message, subscription_filter="logs")


async def send_error_to_websocket(error_data: Dict[str, Any]):
    """发送错误到WebSocket客户端"""
    error_message = WebSocketMessage(
        message_type=MessageType.ERROR,
        data=error_data
    )
    
    await websocket_error_handler.broadcast_message(error_message)


async def send_progress_to_websocket(progress_data: Dict[str, Any]):
    """发送进度到WebSocket客户端"""
    progress_message = WebSocketMessage(
        message_type=MessageType.PROGRESS,
        data=progress_data
    )
    
    await websocket_error_handler.broadcast_message(progress_message, subscription_filter="progress")