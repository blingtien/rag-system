#!/usr/bin/env python3
"""
WebSocket可靠性保证层

功能特性:
1. 消息确认机制 (ACK/NACK)
2. 自动重传机制 (ARQ)
3. 优先级队列管理
4. 消息顺序保证
5. 流量控制
6. 连接恢复和状态同步
7. QoS (服务质量) 保证
"""

import asyncio
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, IntEnum
from collections import defaultdict, deque
import heapq
import uuid
import weakref

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from middleware.unified_logging import LoggerFactory, LogCategory


class MessageType(Enum):
    """消息类型"""
    DATA = "data"                    # 数据消息
    ACK = "ack"                     # 确认消息
    NACK = "nack"                   # 否定确认
    HEARTBEAT = "heartbeat"         # 心跳消息
    CONTROL = "control"             # 控制消息
    SYNC = "sync"                   # 同步消息
    BATCH = "batch"                 # 批量消息


class QoSLevel(IntEnum):
    """服务质量级别"""
    AT_MOST_ONCE = 0    # 最多一次（不保证到达）
    AT_LEAST_ONCE = 1   # 至少一次（保证到达，可能重复）
    EXACTLY_ONCE = 2    # 恰好一次（保证到达且不重复）


class MessagePriority(IntEnum):
    """消息优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class ReliabilityMode(Enum):
    """可靠性模式"""
    SIMPLE = "simple"           # 简单模式
    RELIABLE = "reliable"       # 可靠模式
    ORDERED = "ordered"         # 有序模式
    TRANSACTIONAL = "transactional"  # 事务模式


@dataclass
class ReliableMessage:
    """可靠消息"""
    message_id: str
    sequence_number: int
    content: Any
    message_type: MessageType
    qos_level: QoSLevel
    priority: MessagePriority
    created_at: float
    expires_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    ack_required: bool = True
    ordered: bool = False
    transaction_id: Optional[str] = None
    
    # 可靠性控制
    send_attempts: List[float] = field(default_factory=list)
    last_sent_at: Optional[float] = None
    acknowledged_at: Optional[float] = None
    
    @property
    def is_expired(self) -> bool:
        """检查消息是否过期"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    @property
    def is_retry_eligible(self) -> bool:
        """检查是否可以重试"""
        return (self.retry_count < self.max_retries and 
                not self.is_expired and 
                self.acknowledged_at is None)
    
    @property
    def next_retry_delay(self) -> float:
        """计算下次重试延迟（指数退避）"""
        base_delay = 1.0  # 基础延迟1秒
        max_delay = 30.0  # 最大延迟30秒
        delay = min(base_delay * (2 ** self.retry_count), max_delay)
        
        # 添加随机抖动
        import random
        jitter = delay * 0.1 * random.random()
        return delay + jitter
    
    def to_wire_format(self) -> Dict[str, Any]:
        """转换为网络传输格式"""
        return {
            'id': self.message_id,
            'seq': self.sequence_number,
            'type': self.message_type.value,
            'qos': self.qos_level.value,
            'priority': self.priority.value,
            'content': self.content,
            'ack_required': self.ack_required,
            'ordered': self.ordered,
            'transaction_id': self.transaction_id,
            'timestamp': self.created_at
        }
    
    @classmethod
    def from_wire_format(cls, data: Dict[str, Any]) -> 'ReliableMessage':
        """从网络传输格式创建消息"""
        return cls(
            message_id=data['id'],
            sequence_number=data['seq'],
            content=data['content'],
            message_type=MessageType(data['type']),
            qos_level=QoSLevel(data['qos']),
            priority=MessagePriority(data['priority']),
            created_at=data['timestamp'],
            ack_required=data.get('ack_required', True),
            ordered=data.get('ordered', False),
            transaction_id=data.get('transaction_id')
        )


@dataclass
class AcknowledgmentMessage:
    """确认消息"""
    message_id: str
    sequence_number: int
    ack_type: MessageType  # ACK or NACK
    reason: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_wire_format(self) -> Dict[str, Any]:
        """转换为网络传输格式"""
        return {
            'type': self.ack_type.value,
            'message_id': self.message_id,
            'seq': self.sequence_number,
            'reason': self.reason,
            'timestamp': self.timestamp
        }


class PriorityQueue:
    """优先级队列"""
    
    def __init__(self):
        self.heap: List[Tuple[int, int, ReliableMessage]] = []
        self.entry_counter = 0
        
    def put(self, message: ReliableMessage):
        """添加消息到队列"""
        # 使用负优先级实现最大堆（高优先级先出）
        priority = -message.priority.value
        heapq.heappush(self.heap, (priority, self.entry_counter, message))
        self.entry_counter += 1
    
    def get(self) -> Optional[ReliableMessage]:
        """获取最高优先级消息"""
        if not self.heap:
            return None
        _, _, message = heapq.heappop(self.heap)
        return message
    
    def peek(self) -> Optional[ReliableMessage]:
        """查看最高优先级消息（不移除）"""
        if not self.heap:
            return None
        return self.heap[0][2]
    
    def remove(self, message_id: str) -> bool:
        """移除指定消息"""
        for i, (_, _, msg) in enumerate(self.heap):
            if msg.message_id == message_id:
                del self.heap[i]
                heapq.heapify(self.heap)
                return True
        return False
    
    def size(self) -> int:
        """获取队列大小"""
        return len(self.heap)
    
    def clear(self):
        """清空队列"""
        self.heap.clear()
        self.entry_counter = 0


class FlowController:
    """流量控制器"""
    
    def __init__(self, 
                 window_size: int = 100,
                 max_rate_per_second: int = 1000):
        
        self.window_size = window_size          # 滑动窗口大小
        self.max_rate_per_second = max_rate_per_second  # 最大发送率
        
        # 滑动窗口
        self.send_window: Set[int] = set()
        self.ack_window: Set[int] = set()
        
        # 流量控制
        self.send_times: deque = deque()
        self.current_rate = 0.0
        
        # 序列号管理
        self.next_sequence = 0
        self.last_acked_sequence = -1
        
    def can_send(self) -> bool:
        """检查是否可以发送消息"""
        # 检查窗口大小
        if len(self.send_window) >= self.window_size:
            return False
        
        # 检查发送速率
        current_time = time.time()
        self._update_rate(current_time)
        
        return self.current_rate < self.max_rate_per_second
    
    def allocate_sequence(self) -> int:
        """分配序列号"""
        seq = self.next_sequence
        self.next_sequence += 1
        self.send_window.add(seq)
        return seq
    
    def acknowledge_message(self, sequence: int):
        """确认消息"""
        if sequence in self.send_window:
            self.send_window.remove(sequence)
            self.ack_window.add(sequence)
            
            # 更新最后确认的序列号
            if sequence > self.last_acked_sequence:
                self.last_acked_sequence = sequence
    
    def _update_rate(self, current_time: float):
        """更新发送速率"""
        # 移除1秒前的记录
        while self.send_times and current_time - self.send_times[0] > 1.0:
            self.send_times.popleft()
        
        # 记录当前发送时间
        self.send_times.append(current_time)
        self.current_rate = len(self.send_times)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取流量控制统计"""
        return {
            'window_size': self.window_size,
            'current_window_usage': len(self.send_window),
            'max_rate_per_second': self.max_rate_per_second,
            'current_rate': self.current_rate,
            'next_sequence': self.next_sequence,
            'last_acked_sequence': self.last_acked_sequence,
            'window_utilization': len(self.send_window) / self.window_size * 100
        }


class ReliabilitySession:
    """可靠性会话"""
    
    def __init__(self, 
                 connection_id: str,
                 websocket: WebSocket,
                 mode: ReliabilityMode = ReliabilityMode.RELIABLE):
        
        self.connection_id = connection_id
        self.websocket = websocket
        self.mode = mode
        
        # 消息队列
        self.outbound_queue = PriorityQueue()
        self.pending_acks: Dict[str, ReliableMessage] = {}
        self.received_messages: Dict[int, ReliableMessage] = {}
        
        # 流量控制
        self.flow_controller = FlowController()
        
        # 有序处理
        self.expected_sequence = 0
        self.out_of_order_messages: Dict[int, ReliableMessage] = {}
        
        # 事务支持
        self.active_transactions: Dict[str, List[ReliableMessage]] = {}
        
        # 统计信息
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'messages_acknowledged': 0,
            'messages_retried': 0,
            'messages_lost': 0,
            'average_rtt': 0.0,  # 往返时间
            'session_start': time.time()
        }
        
        # 任务管理
        self.retry_task: Optional[asyncio.Task] = None
        self.is_active = False
        
        # 日志
        self.logger = LoggerFactory.get_logger(f"reliability_session_{connection_id}")
    
    async def start(self):
        """启动会话"""
        if self.is_active:
            return
        
        self.is_active = True
        self.retry_task = asyncio.create_task(self._retry_loop())
        
        await self.logger.info(f"可靠性会话已启动: {self.connection_id} (模式: {self.mode.value})")
    
    async def stop(self):
        """停止会话"""
        if not self.is_active:
            return
        
        self.is_active = False
        
        if self.retry_task:
            self.retry_task.cancel()
            try:
                await self.retry_task
            except asyncio.CancelledError:
                pass
        
        await self.logger.info(f"可靠性会话已停止: {self.connection_id}")
    
    async def send_message(self, 
                          content: Any,
                          qos_level: QoSLevel = QoSLevel.AT_LEAST_ONCE,
                          priority: MessagePriority = MessagePriority.NORMAL,
                          expires_in: Optional[int] = None,
                          ordered: bool = False,
                          transaction_id: Optional[str] = None) -> Optional[str]:
        """发送可靠消息"""
        
        # 流量控制检查
        if not self.flow_controller.can_send():
            await self.logger.warning(f"流量控制限制: {self.connection_id}")
            return None
        
        # 创建消息
        message_id = str(uuid.uuid4())
        sequence_number = self.flow_controller.allocate_sequence()
        
        message = ReliableMessage(
            message_id=message_id,
            sequence_number=sequence_number,
            content=content,
            message_type=MessageType.DATA,
            qos_level=qos_level,
            priority=priority,
            created_at=time.time(),
            expires_at=time.time() + expires_in if expires_in else None,
            ack_required=(qos_level > QoSLevel.AT_MOST_ONCE),
            ordered=ordered,
            transaction_id=transaction_id
        )
        
        # 事务处理
        if transaction_id:
            if transaction_id not in self.active_transactions:
                self.active_transactions[transaction_id] = []
            self.active_transactions[transaction_id].append(message)
        
        # 添加到发送队列
        self.outbound_queue.put(message)
        
        # 立即尝试发送
        await self._process_outbound_queue()
        
        return message_id
    
    async def receive_message(self, data: Dict[str, Any]) -> Optional[ReliableMessage]:
        """接收消息"""
        try:
            message_type = MessageType(data.get('type', 'data'))
            
            if message_type in [MessageType.ACK, MessageType.NACK]:
                await self._handle_acknowledgment(data)
                return None
            
            # 创建可靠消息
            message = ReliableMessage.from_wire_format(data)
            
            # QoS处理
            if message.qos_level == QoSLevel.AT_MOST_ONCE:
                # 最多一次：直接处理，不发送确认
                self.stats['messages_received'] += 1
                return message
            
            elif message.qos_level == QoSLevel.AT_LEAST_ONCE:
                # 至少一次：发送确认，可能重复处理
                await self._send_acknowledgment(message, MessageType.ACK)
                self.stats['messages_received'] += 1
                return message
            
            elif message.qos_level == QoSLevel.EXACTLY_ONCE:
                # 恰好一次：去重处理
                if message.sequence_number in self.received_messages:
                    # 重复消息，只发送确认
                    await self._send_acknowledgment(message, MessageType.ACK)
                    return None
                
                self.received_messages[message.sequence_number] = message
                await self._send_acknowledgment(message, MessageType.ACK)
                
                # 有序处理
                if message.ordered:
                    return await self._handle_ordered_message(message)
                else:
                    self.stats['messages_received'] += 1
                    return message
        
        except Exception as e:
            await self.logger.error(f"接收消息失败: {str(e)}")
            return None
    
    async def commit_transaction(self, transaction_id: str) -> bool:
        """提交事务"""
        if transaction_id not in self.active_transactions:
            return False
        
        messages = self.active_transactions[transaction_id]
        
        # 等待所有消息确认
        for message in messages:
            if message.message_id in self.pending_acks:
                # 消息还未确认
                return False
        
        # 清理事务
        del self.active_transactions[transaction_id]
        
        await self.logger.info(f"事务已提交: {transaction_id} ({len(messages)} 消息)")
        return True
    
    async def rollback_transaction(self, transaction_id: str) -> bool:
        """回滚事务"""
        if transaction_id not in self.active_transactions:
            return False
        
        messages = self.active_transactions[transaction_id]
        
        # 从待确认列表中移除
        for message in messages:
            self.pending_acks.pop(message.message_id, None)
            self.outbound_queue.remove(message.message_id)
        
        # 清理事务
        del self.active_transactions[transaction_id]
        
        await self.logger.info(f"事务已回滚: {transaction_id} ({len(messages)} 消息)")
        return True
    
    async def _process_outbound_queue(self):
        """处理发送队列"""
        while self.is_active and self.outbound_queue.size() > 0:
            if not self.flow_controller.can_send():
                break
            
            message = self.outbound_queue.get()
            if message is None:
                break
            
            # 检查消息是否过期
            if message.is_expired:
                self.stats['messages_lost'] += 1
                continue
            
            # 发送消息
            try:
                wire_data = message.to_wire_format()
                json_data = json.dumps(wire_data, ensure_ascii=False)
                
                await self.websocket.send_text(json_data)
                
                # 记录发送时间
                message.last_sent_at = time.time()
                message.send_attempts.append(message.last_sent_at)
                self.stats['messages_sent'] += 1
                
                # 需要确认的消息加入待确认列表
                if message.ack_required:
                    self.pending_acks[message.message_id] = message
                
            except Exception as e:
                await self.logger.error(f"发送消息失败: {str(e)}")
                # 重新加入队列
                self.outbound_queue.put(message)
                break
    
    async def _handle_acknowledgment(self, data: Dict[str, Any]):
        """处理确认消息"""
        message_id = data.get('message_id')
        ack_type = MessageType(data.get('type'))
        sequence = data.get('seq')
        
        if message_id in self.pending_acks:
            message = self.pending_acks[message_id]
            
            if ack_type == MessageType.ACK:
                # 确认成功
                message.acknowledged_at = time.time()
                self.flow_controller.acknowledge_message(sequence)
                
                # 计算RTT
                if message.last_sent_at:
                    rtt = message.acknowledged_at - message.last_sent_at
                    self._update_rtt(rtt)
                
                # 从待确认列表移除
                del self.pending_acks[message_id]
                self.stats['messages_acknowledged'] += 1
                
            elif ack_type == MessageType.NACK:
                # 确认失败，重新发送
                reason = data.get('reason', 'Unknown error')
                await self.logger.warning(f"消息NACK: {message_id}, 原因: {reason}")
                
                if message.is_retry_eligible:
                    message.retry_count += 1
                    self.outbound_queue.put(message)
                    self.stats['messages_retried'] += 1
                else:
                    # 重试次数耗尽
                    del self.pending_acks[message_id]
                    self.stats['messages_lost'] += 1
    
    async def _handle_ordered_message(self, message: ReliableMessage) -> Optional[ReliableMessage]:
        """处理有序消息"""
        if message.sequence_number == self.expected_sequence:
            # 正确的下一条消息
            self.expected_sequence += 1
            self.stats['messages_received'] += 1
            
            # 检查是否有后续的乱序消息可以处理
            while self.expected_sequence in self.out_of_order_messages:
                next_message = self.out_of_order_messages[self.expected_sequence]
                del self.out_of_order_messages[self.expected_sequence]
                self.expected_sequence += 1
                self.stats['messages_received'] += 1
                # TODO: 处理后续消息
            
            return message
        
        elif message.sequence_number > self.expected_sequence:
            # 乱序消息，暂存
            self.out_of_order_messages[message.sequence_number] = message
            return None
        
        else:
            # 重复或过期消息
            return None
    
    async def _send_acknowledgment(self, message: ReliableMessage, ack_type: MessageType):
        """发送确认消息"""
        ack = AcknowledgmentMessage(
            message_id=message.message_id,
            sequence_number=message.sequence_number,
            ack_type=ack_type
        )
        
        try:
            wire_data = ack.to_wire_format()
            json_data = json.dumps(wire_data, ensure_ascii=False)
            await self.websocket.send_text(json_data)
            
        except Exception as e:
            await self.logger.error(f"发送确认失败: {str(e)}")
    
    async def _retry_loop(self):
        """重试循环"""
        while self.is_active:
            try:
                await asyncio.sleep(1.0)  # 每秒检查一次
                await self._check_retries()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(f"重试循环错误: {str(e)}")
    
    async def _check_retries(self):
        """检查需要重试的消息"""
        current_time = time.time()
        retry_messages = []
        
        for message_id, message in list(self.pending_acks.items()):
            if message.is_expired:
                # 消息过期
                del self.pending_acks[message_id]
                self.stats['messages_lost'] += 1
                continue
            
            if (message.last_sent_at and 
                current_time - message.last_sent_at > message.next_retry_delay and
                message.is_retry_eligible):
                
                retry_messages.append(message)
        
        # 重新发送需要重试的消息
        for message in retry_messages:
            message.retry_count += 1
            self.outbound_queue.put(message)
            self.stats['messages_retried'] += 1
    
    def _update_rtt(self, rtt: float):
        """更新平均往返时间"""
        if self.stats['average_rtt'] == 0.0:
            self.stats['average_rtt'] = rtt
        else:
            # 指数移动平均
            self.stats['average_rtt'] = self.stats['average_rtt'] * 0.8 + rtt * 0.2
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        return {
            'connection_id': self.connection_id,
            'mode': self.mode.value,
            'statistics': self.stats,
            'flow_control': self.flow_controller.get_statistics(),
            'queues': {
                'outbound_queue_size': self.outbound_queue.size(),
                'pending_acks': len(self.pending_acks),
                'out_of_order_messages': len(self.out_of_order_messages),
                'active_transactions': len(self.active_transactions)
            },
            'session_duration': time.time() - self.stats['session_start']
        }


class WebSocketReliabilityManager:
    """
    WebSocket可靠性管理器
    管理所有可靠性会话
    """
    
    def __init__(self):
        self.sessions: Dict[str, ReliabilitySession] = {}
        self.logger = LoggerFactory.get_logger("websocket_reliability_manager")
        
        # 全局统计
        self.global_stats = {
            'total_sessions': 0,
            'active_sessions': 0,
            'total_messages_processed': 0,
            'total_messages_lost': 0,
            'average_success_rate': 0.0
        }
    
    async def create_session(self, 
                           connection_id: str,
                           websocket: WebSocket,
                           mode: ReliabilityMode = ReliabilityMode.RELIABLE) -> ReliabilitySession:
        """创建可靠性会话"""
        
        if connection_id in self.sessions:
            await self.logger.warning(f"会话已存在: {connection_id}")
            return self.sessions[connection_id]
        
        session = ReliabilitySession(connection_id, websocket, mode)
        self.sessions[connection_id] = session
        
        await session.start()
        
        self.global_stats['total_sessions'] += 1
        self.global_stats['active_sessions'] += 1
        
        await self.logger.info(f"创建可靠性会话: {connection_id} (模式: {mode.value})")
        return session
    
    async def get_session(self, connection_id: str) -> Optional[ReliabilitySession]:
        """获取会话"""
        return self.sessions.get(connection_id)
    
    async def remove_session(self, connection_id: str):
        """移除会话"""
        if connection_id not in self.sessions:
            return
        
        session = self.sessions[connection_id]
        await session.stop()
        del self.sessions[connection_id]
        
        self.global_stats['active_sessions'] -= 1
        
        await self.logger.info(f"移除可靠性会话: {connection_id}")
    
    async def broadcast_reliable_message(self,
                                       content: Any,
                                       qos_level: QoSLevel = QoSLevel.AT_LEAST_ONCE,
                                       priority: MessagePriority = MessagePriority.NORMAL,
                                       connection_filter: Optional[Callable[[str], bool]] = None) -> Dict[str, str]:
        """广播可靠消息"""
        
        results = {}
        
        for connection_id, session in self.sessions.items():
            if connection_filter and not connection_filter(connection_id):
                continue
            
            try:
                message_id = await session.send_message(
                    content=content,
                    qos_level=qos_level,
                    priority=priority
                )
                results[connection_id] = message_id
                
            except Exception as e:
                await self.logger.error(f"广播消息失败 {connection_id}: {str(e)}")
                results[connection_id] = None
        
        return results
    
    async def get_all_statistics(self) -> Dict[str, Any]:
        """获取所有统计信息"""
        session_stats = {}
        total_messages_processed = 0
        total_messages_lost = 0
        
        for connection_id, session in self.sessions.items():
            stats = session.get_session_statistics()
            session_stats[connection_id] = stats
            
            total_messages_processed += stats['statistics']['messages_sent']
            total_messages_lost += stats['statistics']['messages_lost']
        
        # 更新全局统计
        self.global_stats['total_messages_processed'] = total_messages_processed
        self.global_stats['total_messages_lost'] = total_messages_lost
        
        if total_messages_processed > 0:
            self.global_stats['average_success_rate'] = (
                (total_messages_processed - total_messages_lost) / 
                total_messages_processed * 100
            )
        
        return {
            'global_statistics': self.global_stats,
            'sessions': session_stats
        }
    
    async def shutdown_all_sessions(self):
        """关闭所有会话"""
        connection_ids = list(self.sessions.keys())
        for connection_id in connection_ids:
            await self.remove_session(connection_id)


# 全局可靠性管理器实例
reliability_manager = WebSocketReliabilityManager()