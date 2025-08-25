#!/usr/bin/env python3
"""
统一缓存管理器 - RAG-Anything API Phase 4
实现多层缓存架构，智能缓存策略和统一管理
"""

import os
import time
import asyncio
import hashlib
import pickle
import json
from typing import Dict, Any, Optional, List, Tuple, Callable
from datetime import datetime, timedelta
from pathlib import Path
from collections import OrderedDict, defaultdict
from enum import Enum
import logging

import redis
import aioredis
from cachetools import TTLCache, LRUCache

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """缓存层级"""
    L1_MEMORY = "l1_memory"      # 内存缓存（最快）
    L2_REDIS = "l2_redis"        # Redis缓存（持久化）
    L3_DISK = "l3_disk"          # 磁盘缓存（大容量）


class CacheStrategy(Enum):
    """缓存策略"""
    LRU = "lru"                  # 最近最少使用
    LFU = "lfu"                  # 最不经常使用
    TTL = "ttl"                  # 时间过期
    ADAPTIVE = "adaptive"        # 自适应策略


class UnifiedCacheManager:
    """
    统一缓存管理器
    
    特性：
    1. 多层缓存架构（L1内存、L2 Redis、L3磁盘）
    2. 智能缓存策略（LRU、LFU、TTL、自适应）
    3. 缓存预热和失效机制
    4. 统一的缓存键管理
    5. 性能指标收集
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._load_default_config()
        
        # L1 内存缓存
        self.l1_cache = self._init_memory_cache()
        self.l1_stats = defaultdict(lambda: {"hits": 0, "misses": 0, "size": 0})
        
        # L2 Redis缓存
        self.redis_client = None
        self.redis_enabled = self.config.get("redis_enabled", False)
        if self.redis_enabled:
            self._init_redis_cache()
        
        # L3 磁盘缓存
        self.disk_cache_dir = Path(self.config.get("disk_cache_dir", "./cache"))
        self.disk_cache_dir.mkdir(parents=True, exist_ok=True)
        self.disk_cache_index = OrderedDict()  # 磁盘缓存索引
        self.max_disk_cache_size = self.config.get("max_disk_cache_gb", 10) * 1024 * 1024 * 1024
        
        # 缓存策略
        self.default_strategy = CacheStrategy[self.config.get("default_strategy", "ADAPTIVE")]
        self.access_history = defaultdict(list)  # 访问历史用于自适应策略
        
        # 性能监控
        self.performance_metrics = {
            "total_requests": 0,
            "l1_hit_rate": 0.0,
            "l2_hit_rate": 0.0,
            "l3_hit_rate": 0.0,
            "avg_response_time": 0.0,
            "cache_size_mb": 0.0,
            "evictions": 0
        }
        
        # 预热队列
        self.warmup_queue = asyncio.Queue()
        self.warmup_task = None
        
        logger.info(f"统一缓存管理器初始化完成：L1={self.config['l1_max_size']}项, "
                   f"Redis={self.redis_enabled}, 磁盘={self.max_disk_cache_size/1024/1024/1024:.1f}GB")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置"""
        return {
            "l1_max_size": int(os.getenv("CACHE_L1_MAX_SIZE", "1000")),
            "l1_ttl_seconds": int(os.getenv("CACHE_L1_TTL", "3600")),
            "redis_enabled": os.getenv("CACHE_REDIS_ENABLED", "false").lower() == "true",
            "redis_host": os.getenv("REDIS_HOST", "localhost"),
            "redis_port": int(os.getenv("REDIS_PORT", "6379")),
            "redis_db": int(os.getenv("REDIS_DB", "0")),
            "redis_ttl_seconds": int(os.getenv("CACHE_REDIS_TTL", "86400")),
            "disk_cache_dir": os.getenv("CACHE_DISK_DIR", "./cache"),
            "max_disk_cache_gb": float(os.getenv("CACHE_DISK_MAX_GB", "10")),
            "default_strategy": os.getenv("CACHE_STRATEGY", "ADAPTIVE"),
            "enable_compression": os.getenv("CACHE_COMPRESSION", "true").lower() == "true"
        }
    
    def _init_memory_cache(self) -> Dict[str, Any]:
        """初始化内存缓存"""
        max_size = self.config["l1_max_size"]
        ttl = self.config["l1_ttl_seconds"]
        
        # 使用TTL+LRU混合策略
        return TTLCache(maxsize=max_size, ttl=ttl)
    
    def _init_redis_cache(self):
        """初始化Redis缓存"""
        try:
            import redis
            self.redis_client = redis.Redis(
                host=self.config["redis_host"],
                port=self.config["redis_port"],
                db=self.config["redis_db"],
                decode_responses=False  # 使用二进制存储
            )
            # 测试连接
            self.redis_client.ping()
            logger.info("Redis缓存连接成功")
        except Exception as e:
            logger.warning(f"Redis缓存连接失败: {e}，将仅使用内存和磁盘缓存")
            self.redis_enabled = False
            self.redis_client = None
    
    def _generate_cache_key(self, key_components: Dict[str, Any]) -> str:
        """生成统一的缓存键"""
        # 确保键的一致性
        sorted_components = sorted(key_components.items())
        key_str = json.dumps(sorted_components, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    async def get(self, key: str, key_components: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """
        从缓存获取数据（多层查找）
        
        Args:
            key: 缓存键（可选，如果提供key_components会自动生成）
            key_components: 缓存键组件（用于生成缓存键）
        
        Returns:
            缓存的数据或None
        """
        start_time = time.time()
        self.performance_metrics["total_requests"] += 1
        
        # 生成缓存键
        if key_components:
            key = self._generate_cache_key(key_components)
        
        # L1 内存缓存查找
        value = self._get_from_l1(key)
        if value is not None:
            self.l1_stats[key]["hits"] += 1
            await self._update_access_history(key, CacheLevel.L1_MEMORY)
            self._update_response_time(time.time() - start_time)
            return value
        
        self.l1_stats[key]["misses"] += 1
        
        # L2 Redis缓存查找
        if self.redis_enabled:
            value = await self._get_from_l2(key)
            if value is not None:
                # 提升到L1缓存
                self._set_to_l1(key, value)
                await self._update_access_history(key, CacheLevel.L2_REDIS)
                self._update_response_time(time.time() - start_time)
                return value
        
        # L3 磁盘缓存查找
        value = await self._get_from_l3(key)
        if value is not None:
            # 提升到L1和L2缓存
            self._set_to_l1(key, value)
            if self.redis_enabled:
                await self._set_to_l2(key, value)
            await self._update_access_history(key, CacheLevel.L3_DISK)
            self._update_response_time(time.time() - start_time)
            return value
        
        self._update_response_time(time.time() - start_time)
        return None
    
    async def set(self, key: str, value: Any, 
                  key_components: Optional[Dict[str, Any]] = None,
                  ttl: Optional[int] = None,
                  levels: Optional[List[CacheLevel]] = None) -> bool:
        """
        设置缓存数据（多层写入）
        
        Args:
            key: 缓存键
            value: 要缓存的数据
            key_components: 缓存键组件
            ttl: 过期时间（秒）
            levels: 要写入的缓存层级列表
        
        Returns:
            是否成功
        """
        # 生成缓存键
        if key_components:
            key = self._generate_cache_key(key_components)
        
        # 默认写入所有层级
        if levels is None:
            levels = [CacheLevel.L1_MEMORY]
            if self.redis_enabled:
                levels.append(CacheLevel.L2_REDIS)
            # 大对象才写入磁盘
            if self._estimate_size(value) > 1024 * 1024:  # > 1MB
                levels.append(CacheLevel.L3_DISK)
        
        success = True
        
        # 写入各层缓存
        if CacheLevel.L1_MEMORY in levels:
            success &= self._set_to_l1(key, value, ttl)
        
        if CacheLevel.L2_REDIS in levels and self.redis_enabled:
            success &= await self._set_to_l2(key, value, ttl)
        
        if CacheLevel.L3_DISK in levels:
            success &= await self._set_to_l3(key, value, ttl)
        
        return success
    
    def _get_from_l1(self, key: str) -> Optional[Any]:
        """从L1内存缓存获取"""
        try:
            return self.l1_cache.get(key)
        except KeyError:
            return None
    
    def _set_to_l1(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """写入L1内存缓存"""
        try:
            self.l1_cache[key] = value
            self.l1_stats[key]["size"] = self._estimate_size(value)
            return True
        except Exception as e:
            logger.error(f"L1缓存写入失败: {e}")
            return False
    
    async def _get_from_l2(self, key: str) -> Optional[Any]:
        """从L2 Redis缓存获取"""
        if not self.redis_client:
            return None
        
        try:
            data = self.redis_client.get(f"rag:{key}")
            if data:
                return pickle.loads(data)
        except Exception as e:
            logger.error(f"L2缓存读取失败: {e}")
        return None
    
    async def _set_to_l2(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """写入L2 Redis缓存"""
        if not self.redis_client:
            return False
        
        try:
            data = pickle.dumps(value)
            ttl = ttl or self.config["redis_ttl_seconds"]
            self.redis_client.setex(f"rag:{key}", ttl, data)
            return True
        except Exception as e:
            logger.error(f"L2缓存写入失败: {e}")
            return False
    
    async def _get_from_l3(self, key: str) -> Optional[Any]:
        """从L3磁盘缓存获取"""
        cache_file = self.disk_cache_dir / f"{key}.cache"
        
        if not cache_file.exists():
            return None
        
        try:
            # 检查过期
            if key in self.disk_cache_index:
                expiry = self.disk_cache_index[key].get("expiry")
                if expiry and datetime.now() > expiry:
                    # 缓存已过期
                    cache_file.unlink()
                    del self.disk_cache_index[key]
                    return None
            
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"L3缓存读取失败: {e}")
            return None
    
    async def _set_to_l3(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """写入L3磁盘缓存"""
        cache_file = self.disk_cache_dir / f"{key}.cache"
        
        try:
            # 检查磁盘空间
            await self._manage_disk_cache_size()
            
            with open(cache_file, 'wb') as f:
                pickle.dump(value, f)
            
            # 更新索引
            self.disk_cache_index[key] = {
                "size": cache_file.stat().st_size,
                "created": datetime.now(),
                "expiry": datetime.now() + timedelta(seconds=ttl) if ttl else None,
                "access_count": 0
            }
            
            # 移到最后（LRU）
            self.disk_cache_index.move_to_end(key)
            
            return True
        except Exception as e:
            logger.error(f"L3缓存写入失败: {e}")
            return False
    
    async def _manage_disk_cache_size(self):
        """管理磁盘缓存大小"""
        total_size = sum(info["size"] for info in self.disk_cache_index.values())
        
        # 如果超过限制，删除最旧的缓存
        while total_size > self.max_disk_cache_size and len(self.disk_cache_index) > 0:
            # 删除最旧的（OrderedDict的第一个）
            oldest_key = next(iter(self.disk_cache_index))
            cache_file = self.disk_cache_dir / f"{oldest_key}.cache"
            
            if cache_file.exists():
                file_size = cache_file.stat().st_size
                cache_file.unlink()
                total_size -= file_size
                self.performance_metrics["evictions"] += 1
            
            del self.disk_cache_index[oldest_key]
    
    async def _update_access_history(self, key: str, level: CacheLevel):
        """更新访问历史（用于自适应策略）"""
        self.access_history[key].append({
            "time": datetime.now(),
            "level": level
        })
        
        # 限制历史记录数量
        if len(self.access_history[key]) > 100:
            self.access_history[key] = self.access_history[key][-100:]
    
    def _estimate_size(self, obj: Any) -> int:
        """估算对象大小"""
        try:
            return len(pickle.dumps(obj))
        except:
            return 0
    
    def _update_response_time(self, response_time: float):
        """更新响应时间统计"""
        alpha = 0.1  # 指数移动平均系数
        if self.performance_metrics["avg_response_time"] == 0:
            self.performance_metrics["avg_response_time"] = response_time
        else:
            self.performance_metrics["avg_response_time"] = (
                (1 - alpha) * self.performance_metrics["avg_response_time"] + 
                alpha * response_time
            )
    
    async def invalidate(self, key: str, key_components: Optional[Dict[str, Any]] = None) -> bool:
        """
        使缓存失效
        
        Args:
            key: 缓存键
            key_components: 缓存键组件
        
        Returns:
            是否成功
        """
        # 生成缓存键
        if key_components:
            key = self._generate_cache_key(key_components)
        
        success = True
        
        # 从所有层级删除
        try:
            if key in self.l1_cache:
                del self.l1_cache[key]
        except:
            success = False
        
        if self.redis_enabled and self.redis_client:
            try:
                self.redis_client.delete(f"rag:{key}")
            except:
                success = False
        
        cache_file = self.disk_cache_dir / f"{key}.cache"
        if cache_file.exists():
            try:
                cache_file.unlink()
                if key in self.disk_cache_index:
                    del self.disk_cache_index[key]
            except:
                success = False
        
        return success
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """
        使匹配模式的缓存失效
        
        Args:
            pattern: 缓存键模式
        
        Returns:
            失效的缓存数量
        """
        count = 0
        
        # L1缓存
        keys_to_delete = [k for k in self.l1_cache.keys() if pattern in str(k)]
        for key in keys_to_delete:
            try:
                del self.l1_cache[key]
                count += 1
            except:
                pass
        
        # L2 Redis缓存
        if self.redis_enabled and self.redis_client:
            try:
                for key in self.redis_client.scan_iter(f"rag:*{pattern}*"):
                    self.redis_client.delete(key)
                    count += 1
            except:
                pass
        
        # L3磁盘缓存
        for cache_file in self.disk_cache_dir.glob(f"*{pattern}*.cache"):
            try:
                cache_file.unlink()
                key = cache_file.stem
                if key in self.disk_cache_index:
                    del self.disk_cache_index[key]
                count += 1
            except:
                pass
        
        logger.info(f"失效了 {count} 个匹配 '{pattern}' 的缓存项")
        return count
    
    async def warmup(self, keys: List[str], loader_func: Callable) -> int:
        """
        缓存预热
        
        Args:
            keys: 要预热的缓存键列表
            loader_func: 数据加载函数
        
        Returns:
            预热的缓存数量
        """
        count = 0
        
        for key in keys:
            try:
                # 检查是否已缓存
                if await self.get(key) is None:
                    # 加载数据
                    data = await loader_func(key) if asyncio.iscoroutinefunction(loader_func) else loader_func(key)
                    if data is not None:
                        await self.set(key, data)
                        count += 1
            except Exception as e:
                logger.error(f"预热缓存 {key} 失败: {e}")
        
        logger.info(f"预热了 {count} 个缓存项")
        return count
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        # 计算命中率
        l1_total = sum(self.l1_stats[k]["hits"] + self.l1_stats[k]["misses"] 
                      for k in self.l1_stats)
        l1_hits = sum(self.l1_stats[k]["hits"] for k in self.l1_stats)
        
        self.performance_metrics["l1_hit_rate"] = (
            (l1_hits / l1_total * 100) if l1_total > 0 else 0
        )
        
        # 计算缓存大小
        l1_size = sum(self.l1_stats[k]["size"] for k in self.l1_stats)
        l3_size = sum(info["size"] for info in self.disk_cache_index.values())
        
        self.performance_metrics["cache_size_mb"] = (l1_size + l3_size) / 1024 / 1024
        
        return {
            "performance": self.performance_metrics,
            "l1_cache": {
                "items": len(self.l1_cache),
                "hit_rate": self.performance_metrics["l1_hit_rate"],
                "size_mb": l1_size / 1024 / 1024
            },
            "l2_cache": {
                "enabled": self.redis_enabled,
                "connected": self.redis_client is not None
            },
            "l3_cache": {
                "items": len(self.disk_cache_index),
                "size_mb": l3_size / 1024 / 1024,
                "max_size_gb": self.max_disk_cache_size / 1024 / 1024 / 1024
            },
            "strategy": self.default_strategy.value,
            "total_evictions": self.performance_metrics["evictions"]
        }
    
    async def clear_all(self):
        """清空所有缓存"""
        # L1
        self.l1_cache.clear()
        self.l1_stats.clear()
        
        # L2
        if self.redis_enabled and self.redis_client:
            try:
                for key in self.redis_client.scan_iter("rag:*"):
                    self.redis_client.delete(key)
            except:
                pass
        
        # L3
        for cache_file in self.disk_cache_dir.glob("*.cache"):
            try:
                cache_file.unlink()
            except:
                pass
        self.disk_cache_index.clear()
        
        logger.info("所有缓存已清空")


# 全局缓存管理器实例
_cache_manager: Optional[UnifiedCacheManager] = None


def get_cache_manager() -> UnifiedCacheManager:
    """获取全局缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = UnifiedCacheManager()
    return _cache_manager


# 导出主要接口
__all__ = ['UnifiedCacheManager', 'get_cache_manager', 'CacheLevel', 'CacheStrategy']