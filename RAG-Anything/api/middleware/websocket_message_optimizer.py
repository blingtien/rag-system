#!/usr/bin/env python3
"""
WebSocket消息压缩和批量传输优化器

功能特性:
1. 消息压缩 (gzip, deflate, brotli)
2. 批量消息聚合和传输
3. 消息去重和优化
4. 智能消息队列管理
5. 传输性能监控
6. 自适应压缩策略
"""

import asyncio
import gzip
import zlib
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import weakref

from fastapi import WebSocket

from middleware.unified_logging import LoggerFactory, LogCategory

try:
    import brotli
    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False


class CompressionType(Enum):
    """压缩类型"""
    NONE = "none"
    GZIP = "gzip"
    DEFLATE = "deflate"
    BROTLI = "brotli"


class MessagePriority(Enum):
    """消息优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class BatchStrategy(Enum):
    """批量策略"""
    SIZE_BASED = "size"      # 基于大小
    TIME_BASED = "time"      # 基于时间
    COUNT_BASED = "count"    # 基于数量
    ADAPTIVE = "adaptive"    # 自适应


@dataclass
class MessageMetadata:
    """消息元数据"""
    message_id: str
    content_hash: str
    size_bytes: int
    priority: MessagePriority
    created_at: float
    expires_at: Optional[float] = None
    retry_count: int = 0
    compression_ratio: float = 0.0
    
    @property
    def is_expired(self) -> bool:
        """检查消息是否过期"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


@dataclass
class OptimizedMessage:
    """优化的消息对象"""
    content: str
    metadata: MessageMetadata
    original_content: Optional[str] = None
    compression_type: CompressionType = CompressionType.NONE
    is_batched: bool = False
    batch_id: Optional[str] = None
    
    def to_wire_format(self) -> Dict[str, Any]:
        """转换为网络传输格式"""
        return {
            'id': self.metadata.message_id,
            'content': self.content,
            'metadata': {
                'size': self.metadata.size_bytes,
                'priority': self.metadata.priority.value,
                'created_at': self.metadata.created_at,
                'compression': self.compression_type.value,
                'batched': self.is_batched,
                'batch_id': self.batch_id
            }
        }


@dataclass
class BatchedMessages:
    """批量消息"""
    batch_id: str
    messages: List[OptimizedMessage]
    created_at: float
    total_size: int = 0
    compression_ratio: float = 0.0
    
    def __post_init__(self):
        self.total_size = sum(msg.metadata.size_bytes for msg in self.messages)
    
    def to_wire_format(self) -> Dict[str, Any]:
        """转换为网络传输格式"""
        return {
            'type': 'batch',
            'batch_id': self.batch_id,
            'count': len(self.messages),
            'total_size': self.total_size,
            'compression_ratio': self.compression_ratio,
            'messages': [msg.to_wire_format() for msg in self.messages]
        }


class MessageCompressor:
    """消息压缩器"""
    
    def __init__(self):
        self.logger = LoggerFactory.get_logger("websocket_compressor")
        
        # 压缩配置
        self.min_compression_size = 1024  # 最小压缩大小(字节)
        self.compression_threshold = 0.1   # 压缩阈值(10%以下不压缩)
        
        # 压缩算法优先级
        self.compression_priority = [
            CompressionType.BROTLI if BROTLI_AVAILABLE else None,
            CompressionType.GZIP,
            CompressionType.DEFLATE
        ]
        self.compression_priority = [c for c in self.compression_priority if c]
        
        # 压缩统计
        self.compression_stats = {
            'total_messages': 0,
            'compressed_messages': 0,
            'total_original_size': 0,
            'total_compressed_size': 0,
            'compression_attempts': defaultdict(int),
            'compression_successes': defaultdict(int)
        }
    
    async def compress_message(self, content: str, 
                             preferred_type: Optional[CompressionType] = None) -> Tuple[str, CompressionType, float]:
        """压缩消息内容"""
        original_size = len(content.encode())
        self.compression_stats['total_messages'] += 1
        self.compression_stats['total_original_size'] += original_size
        
        # 检查是否需要压缩
        if original_size < self.min_compression_size:
            return content, CompressionType.NONE, 0.0
        
        best_compressed = content
        best_type = CompressionType.NONE
        best_ratio = 0.0
        
        # 尝试不同的压缩算法
        compression_types = [preferred_type] if preferred_type else self.compression_priority
        
        for comp_type in compression_types:
            if comp_type is None:
                continue
                
            try:
                self.compression_stats['compression_attempts'][comp_type.value] += 1
                
                if comp_type == CompressionType.GZIP:
                    compressed = await self._gzip_compress(content)
                elif comp_type == CompressionType.DEFLATE:
                    compressed = await self._deflate_compress(content)
                elif comp_type == CompressionType.BROTLI and BROTLI_AVAILABLE:
                    compressed = await self._brotli_compress(content)
                else:
                    continue
                
                compressed_size = len(compressed)
                compression_ratio = 1.0 - (compressed_size / original_size)
                
                # 检查压缩效果
                if compression_ratio > self.compression_threshold:
                    if compression_ratio > best_ratio:
                        best_compressed = compressed
                        best_type = comp_type
                        best_ratio = compression_ratio
                        self.compression_stats['compression_successes'][comp_type.value] += 1
                
            except Exception as e:
                try:
                    await self.logger.warning(f"压缩失败 {comp_type.value}: {str(e)}")
                except:
                    pass
                continue
        
        # 更新统计
        if best_type != CompressionType.NONE:
            self.compression_stats['compressed_messages'] += 1
            self.compression_stats['total_compressed_size'] += len(best_compressed.encode() if isinstance(best_compressed, str) else best_compressed)
        else:
            self.compression_stats['total_compressed_size'] += original_size
        
        return best_compressed, best_type, best_ratio
    
    async def decompress_message(self, content: Union[str, bytes], 
                               compression_type: CompressionType) -> str:
        """解压缩消息内容"""
        if compression_type == CompressionType.NONE:
            return content if isinstance(content, str) else content.decode()
        
        try:
            if compression_type == CompressionType.GZIP:
                return await self._gzip_decompress(content)
            elif compression_type == CompressionType.DEFLATE:
                return await self._deflate_decompress(content)
            elif compression_type == CompressionType.BROTLI and BROTLI_AVAILABLE:
                return await self._brotli_decompress(content)
            else:
                raise ValueError(f"不支持的压缩类型: {compression_type}")
                
        except Exception as e:
            try:
                await self.logger.error(f"解压缩失败 {compression_type.value}: {str(e)}")
            except:
                pass
            raise
    
    async def _gzip_compress(self, content: str) -> bytes:
        """GZIP压缩"""
        return await asyncio.to_thread(gzip.compress, content.encode())
    
    async def _gzip_decompress(self, content: Union[str, bytes]) -> str:
        """GZIP解压缩"""
        if isinstance(content, str):
            content = content.encode()
        decompressed = await asyncio.to_thread(gzip.decompress, content)
        return decompressed.decode()
    
    async def _deflate_compress(self, content: str) -> bytes:
        """Deflate压缩"""
        return await asyncio.to_thread(zlib.compress, content.encode())
    
    async def _deflate_decompress(self, content: Union[str, bytes]) -> str:
        """Deflate解压缩"""
        if isinstance(content, str):
            content = content.encode()
        decompressed = await asyncio.to_thread(zlib.decompress, content)
        return decompressed.decode()
    
    async def _brotli_compress(self, content: str) -> bytes:
        """Brotli压缩"""
        if not BROTLI_AVAILABLE:
            raise ValueError("Brotli不可用")
        return await asyncio.to_thread(brotli.compress, content.encode())
    
    async def _brotli_decompress(self, content: Union[str, bytes]) -> str:
        """Brotli解压缩"""
        if not BROTLI_AVAILABLE:
            raise ValueError("Brotli不可用")
        if isinstance(content, str):
            content = content.encode()
        decompressed = await asyncio.to_thread(brotli.decompress, content)
        return decompressed.decode()
    
    def get_compression_statistics(self) -> Dict[str, Any]:
        """获取压缩统计信息"""
        stats = self.compression_stats.copy()
        
        if stats['total_original_size'] > 0:
            stats['overall_compression_ratio'] = 1.0 - (stats['total_compressed_size'] / stats['total_original_size'])
        else:
            stats['overall_compression_ratio'] = 0.0
        
        stats['compression_rate'] = (stats['compressed_messages'] / stats['total_messages'] * 100 
                                   if stats['total_messages'] > 0 else 0.0)
        
        return stats


class MessageBatcher:
    """消息批处理器"""
    
    def __init__(self, strategy: BatchStrategy = BatchStrategy.ADAPTIVE):
        self.strategy = strategy
        self.logger = LoggerFactory.get_logger("websocket_batcher")
        
        # 批处理配置
        self.max_batch_size = 64 * 1024     # 64KB
        self.max_batch_count = 50           # 最多50条消息
        self.max_batch_age = 100           # 100ms
        self.min_batch_count = 2            # 最少2条消息才批处理
        
        # 批处理队列
        self.pending_batches: Dict[str, List[OptimizedMessage]] = defaultdict(list)
        self.batch_timers: Dict[str, asyncio.Task] = {}
        
        # 批处理统计
        self.batch_stats = {
            'total_batches': 0,
            'total_messages_batched': 0,
            'average_batch_size': 0.0,
            'average_compression_ratio': 0.0,
            'batch_efficiency': 0.0
        }
    
    async def add_message_to_batch(self, connection_id: str, 
                                  message: OptimizedMessage) -> Optional[BatchedMessages]:
        """添加消息到批处理队列"""
        batch_key = self._get_batch_key(connection_id, message)
        self.pending_batches[batch_key].append(message)
        
        # 检查是否需要立即发送批处理
        if await self._should_send_batch(batch_key):
            return await self._create_and_send_batch(batch_key)
        
        # 设置批处理定时器
        await self._set_batch_timer(batch_key)
        return None
    
    async def force_flush_batch(self, connection_id: str) -> List[BatchedMessages]:
        """强制刷新指定连接的所有批处理"""
        batches = []
        keys_to_remove = []
        
        for batch_key in list(self.pending_batches.keys()):
            if batch_key.startswith(connection_id):
                if self.pending_batches[batch_key]:
                    batch = await self._create_and_send_batch(batch_key)
                    if batch:
                        batches.append(batch)
                keys_to_remove.append(batch_key)
        
        # 清理
        for key in keys_to_remove:
            self.pending_batches.pop(key, None)
            if key in self.batch_timers:
                self.batch_timers[key].cancel()
                del self.batch_timers[key]
        
        return batches
    
    def _get_batch_key(self, connection_id: str, message: OptimizedMessage) -> str:
        """获取批处理键"""
        # 基于连接ID和消息优先级分组
        return f"{connection_id}_{message.metadata.priority.value}"
    
    async def _should_send_batch(self, batch_key: str) -> bool:
        """判断是否应该发送批处理"""
        batch_messages = self.pending_batches[batch_key]
        
        if not batch_messages:
            return False
        
        # 基于策略判断
        if self.strategy == BatchStrategy.COUNT_BASED:
            return len(batch_messages) >= self.max_batch_count
        
        elif self.strategy == BatchStrategy.SIZE_BASED:
            total_size = sum(msg.metadata.size_bytes for msg in batch_messages)
            return total_size >= self.max_batch_size
        
        elif self.strategy == BatchStrategy.TIME_BASED:
            oldest_message = min(batch_messages, key=lambda m: m.metadata.created_at)
            return (time.time() - oldest_message.metadata.created_at) * 1000 >= self.max_batch_age
        
        elif self.strategy == BatchStrategy.ADAPTIVE:
            # 自适应策略：综合考虑多个因素
            message_count = len(batch_messages)
            total_size = sum(msg.metadata.size_bytes for msg in batch_messages)
            oldest_message = min(batch_messages, key=lambda m: m.metadata.created_at)
            age_ms = (time.time() - oldest_message.metadata.created_at) * 1000
            
            # 检查任一条件满足
            return (message_count >= self.max_batch_count or
                   total_size >= self.max_batch_size or
                   age_ms >= self.max_batch_age)
        
        return False
    
    async def _create_and_send_batch(self, batch_key: str) -> Optional[BatchedMessages]:
        """创建并发送批处理"""
        messages = self.pending_batches.get(batch_key, [])
        if len(messages) < self.min_batch_count:
            return None
        
        # 创建批处理ID
        batch_id = self._generate_batch_id()
        
        # 创建批处理对象
        batch = BatchedMessages(
            batch_id=batch_id,
            messages=messages,
            created_at=time.time()
        )
        
        # 标记消息为已批处理
        for msg in messages:
            msg.is_batched = True
            msg.batch_id = batch_id
        
        # 清理队列
        self.pending_batches[batch_key] = []
        if batch_key in self.batch_timers:
            self.batch_timers[batch_key].cancel()
            del self.batch_timers[batch_key]
        
        # 更新统计
        self.batch_stats['total_batches'] += 1
        self.batch_stats['total_messages_batched'] += len(messages)
        self._update_batch_statistics(batch)
        
        return batch
    
    async def _set_batch_timer(self, batch_key: str):
        """设置批处理定时器"""
        if batch_key in self.batch_timers:
            return  # 定时器已存在
        
        async def timer_callback():
            try:
                await asyncio.sleep(self.max_batch_age / 1000)  # 转换为秒
                if batch_key in self.pending_batches and self.pending_batches[batch_key]:
                    await self._create_and_send_batch(batch_key)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                try:
                    await self.logger.error(f"批处理定时器错误: {str(e)}")
                except:
                    pass
            finally:
                self.batch_timers.pop(batch_key, None)
        
        self.batch_timers[batch_key] = asyncio.create_task(timer_callback())
    
    def _generate_batch_id(self) -> str:
        """生成批处理ID"""
        import uuid
        return f"batch_{int(time.time() * 1000)}_{str(uuid.uuid4())[:8]}"
    
    def _update_batch_statistics(self, batch: BatchedMessages):
        """更新批处理统计"""
        # 计算平均批处理大小
        total_batches = self.batch_stats['total_batches']
        if total_batches > 0:
            self.batch_stats['average_batch_size'] = (
                self.batch_stats['total_messages_batched'] / total_batches
            )
        
        # 计算批处理效率
        single_message_overhead = len(batch.messages) * 50  # 假设每条消息50字节开销
        batch_overhead = 200  # 批处理开销200字节
        efficiency = 1.0 - (batch_overhead / (batch.total_size + single_message_overhead))
        
        if self.batch_stats['batch_efficiency'] == 0.0:
            self.batch_stats['batch_efficiency'] = efficiency
        else:
            self.batch_stats['batch_efficiency'] = (
                self.batch_stats['batch_efficiency'] * 0.8 + efficiency * 0.2
            )
    
    def get_batch_statistics(self) -> Dict[str, Any]:
        """获取批处理统计信息"""
        stats = self.batch_stats.copy()
        stats['pending_batches'] = len(self.pending_batches)
        stats['active_timers'] = len(self.batch_timers)
        return stats


class MessageDeduplicator:
    """消息去重器"""
    
    def __init__(self, cache_size: int = 10000, cache_ttl: int = 300):
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        
        # 去重缓存
        self.message_hashes: Dict[str, float] = {}  # hash -> timestamp
        self.hash_queue: deque = deque()  # 用于LRU清理
        
        # 去重统计
        self.dedup_stats = {
            'total_messages': 0,
            'duplicate_messages': 0,
            'cache_hits': 0,
            'cache_size': 0
        }
    
    def is_duplicate(self, message_hash: str) -> bool:
        """检查消息是否重复"""
        self.dedup_stats['total_messages'] += 1
        current_time = time.time()
        
        # 清理过期缓存
        self._cleanup_expired_hashes(current_time)
        
        # 检查是否重复
        if message_hash in self.message_hashes:
            self.dedup_stats['duplicate_messages'] += 1
            self.dedup_stats['cache_hits'] += 1
            return True
        
        # 添加到缓存
        self.message_hashes[message_hash] = current_time
        self.hash_queue.append((message_hash, current_time))
        
        # 限制缓存大小
        if len(self.message_hashes) > self.cache_size:
            self._evict_oldest_hash()
        
        self.dedup_stats['cache_size'] = len(self.message_hashes)
        return False
    
    def _cleanup_expired_hashes(self, current_time: float):
        """清理过期的哈希值"""
        expired_hashes = []
        for hash_value, timestamp in self.message_hashes.items():
            if current_time - timestamp > self.cache_ttl:
                expired_hashes.append(hash_value)
        
        for hash_value in expired_hashes:
            self.message_hashes.pop(hash_value, None)
        
        # 清理队列
        while self.hash_queue and current_time - self.hash_queue[0][1] > self.cache_ttl:
            self.hash_queue.popleft()
    
    def _evict_oldest_hash(self):
        """驱逐最旧的哈希值"""
        if self.hash_queue:
            hash_value, _ = self.hash_queue.popleft()
            self.message_hashes.pop(hash_value, None)
    
    def get_deduplication_statistics(self) -> Dict[str, Any]:
        """获取去重统计信息"""
        stats = self.dedup_stats.copy()
        if stats['total_messages'] > 0:
            stats['duplicate_rate'] = stats['duplicate_messages'] / stats['total_messages'] * 100
        else:
            stats['duplicate_rate'] = 0.0
        
        return stats


class WebSocketMessageOptimizer:
    """
    WebSocket消息优化器
    
    集成消息压缩、批处理和去重功能
    """
    
    def __init__(self):
        try:
            self.logger = LoggerFactory.get_logger("websocket_optimizer")
        except Exception:
            import logging
            self.logger = logging.getLogger("websocket_optimizer")
        
        # 组件初始化
        self.compressor = MessageCompressor()
        self.batcher = MessageBatcher()
        self.deduplicator = MessageDeduplicator()
        
        # 优化配置
        self.enable_compression = True
        self.enable_batching = True
        self.enable_deduplication = True
        
        # 性能统计
        self.optimizer_stats = {
            'total_messages_processed': 0,
            'total_bytes_saved': 0,
            'optimization_ratio': 0.0,
            'processing_time_ms': 0.0
        }
    
    async def optimize_message(self, content: str, 
                             connection_id: str,
                             priority: MessagePriority = MessagePriority.NORMAL,
                             expires_in: Optional[int] = None) -> Optional[Union[OptimizedMessage, BatchedMessages]]:
        """优化消息"""
        start_time = time.time()
        
        try:
            # 创建消息ID和哈希
            message_id = self._generate_message_id()
            content_hash = self._calculate_content_hash(content)
            
            # 去重检查
            if self.enable_deduplication and self.deduplicator.is_duplicate(content_hash):
                try:
                    await self.logger.debug(f"消息去重: {message_id}")
                except:
                    pass
                return None
            
            # 创建元数据
            metadata = MessageMetadata(
                message_id=message_id,
                content_hash=content_hash,
                size_bytes=len(content.encode()),
                priority=priority,
                created_at=time.time(),
                expires_at=time.time() + expires_in if expires_in else None
            )
            
            # 消息压缩
            compressed_content = content
            compression_type = CompressionType.NONE
            compression_ratio = 0.0
            
            if self.enable_compression:
                compressed_content, compression_type, compression_ratio = await self.compressor.compress_message(content)
                metadata.compression_ratio = compression_ratio
            
            # 创建优化消息
            optimized_message = OptimizedMessage(
                content=compressed_content if isinstance(compressed_content, str) else compressed_content.decode() if isinstance(compressed_content, bytes) else str(compressed_content),
                metadata=metadata,
                original_content=content,
                compression_type=compression_type
            )
            
            # 批处理
            result = optimized_message
            if self.enable_batching and priority != MessagePriority.CRITICAL:
                batch_result = await self.batcher.add_message_to_batch(connection_id, optimized_message)
                if batch_result:
                    result = batch_result
            
            # 更新统计
            processing_time = (time.time() - start_time) * 1000
            self._update_optimizer_statistics(metadata.size_bytes, compression_ratio, processing_time)
            
            return result
            
        except Exception as e:
            try:
                await self.logger.error(f"消息优化失败: {str(e)}")
            except:
                pass
            return None
    
    async def send_optimized_message(self, websocket: WebSocket, 
                                   optimized_data: Union[OptimizedMessage, BatchedMessages]) -> bool:
        """发送优化的消息"""
        try:
            if isinstance(optimized_data, BatchedMessages):
                # 发送批处理消息
                wire_data = optimized_data.to_wire_format()
            else:
                # 发送单条消息
                wire_data = optimized_data.to_wire_format()
            
            # 转换为JSON并发送
            json_data = json.dumps(wire_data, ensure_ascii=False)
            await websocket.send_text(json_data)
            
            return True
            
        except Exception as e:
            try:
                await self.logger.error(f"发送优化消息失败: {str(e)}")
            except:
                pass
            return False
    
    async def flush_pending_messages(self, connection_id: str) -> List[BatchedMessages]:
        """刷新待处理的消息"""
        return await self.batcher.force_flush_batch(connection_id)
    
    def _generate_message_id(self) -> str:
        """生成消息ID"""
        import uuid
        return f"msg_{int(time.time() * 1000)}_{str(uuid.uuid4())[:8]}"
    
    def _calculate_content_hash(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _update_optimizer_statistics(self, original_size: int, compression_ratio: float, processing_time: float):
        """更新优化统计"""
        self.optimizer_stats['total_messages_processed'] += 1
        
        bytes_saved = int(original_size * compression_ratio)
        self.optimizer_stats['total_bytes_saved'] += bytes_saved
        
        # 更新平均处理时间
        current_avg = self.optimizer_stats['processing_time_ms']
        count = self.optimizer_stats['total_messages_processed']
        self.optimizer_stats['processing_time_ms'] = (current_avg * (count - 1) + processing_time) / count
        
        # 更新总体优化率
        if original_size > 0:
            self.optimizer_stats['optimization_ratio'] = (
                self.optimizer_stats['total_bytes_saved'] / 
                (self.optimizer_stats['total_messages_processed'] * original_size) * 100
            )
    
    def get_optimization_statistics(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        return {
            'optimizer': self.optimizer_stats,
            'compression': self.compressor.get_compression_statistics(),
            'batching': self.batcher.get_batch_statistics(),
            'deduplication': self.deduplicator.get_deduplication_statistics()
        }
    
    def configure(self, **config):
        """配置优化器"""
        if 'enable_compression' in config:
            self.enable_compression = config['enable_compression']
        if 'enable_batching' in config:
            self.enable_batching = config['enable_batching']
        if 'enable_deduplication' in config:
            self.enable_deduplication = config['enable_deduplication']
        
        # 配置压缩器
        if 'min_compression_size' in config:
            self.compressor.min_compression_size = config['min_compression_size']
        if 'compression_threshold' in config:
            self.compressor.compression_threshold = config['compression_threshold']
        
        # 配置批处理器
        if 'batch_strategy' in config:
            self.batcher.strategy = config['batch_strategy']
        if 'max_batch_size' in config:
            self.batcher.max_batch_size = config['max_batch_size']
        if 'max_batch_count' in config:
            self.batcher.max_batch_count = config['max_batch_count']
        if 'max_batch_age' in config:
            self.batcher.max_batch_age = config['max_batch_age']


# 全局消息优化器实例
message_optimizer = WebSocketMessageOptimizer()