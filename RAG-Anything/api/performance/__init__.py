#!/usr/bin/env python3
"""
性能优化模块 - RAG-Anything API Phase 4
提供统一的性能优化功能
"""

from .unified_cache_manager import (
    UnifiedCacheManager,
    get_cache_manager,
    CacheLevel,
    CacheStrategy
)

from .gpu_resource_manager import (
    GPUResourceManager,
    get_gpu_manager,
    TaskPriority,
    ResourceType
)

from .performance_optimizer import (
    PerformanceOptimizer,
    get_performance_optimizer,
    OptimizationStrategy,
    PerformanceProfile
)

__all__ = [
    # 缓存管理
    'UnifiedCacheManager',
    'get_cache_manager',
    'CacheLevel',
    'CacheStrategy',
    
    # GPU资源管理
    'GPUResourceManager',
    'get_gpu_manager',
    'TaskPriority',
    'ResourceType',
    
    # 性能优化
    'PerformanceOptimizer',
    'get_performance_optimizer',
    'OptimizationStrategy',
    'PerformanceProfile'
]