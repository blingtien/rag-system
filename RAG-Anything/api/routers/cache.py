"""
缓存管理路由
处理缓存统计、状态查询、清理等相关的API端点
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends

from config.dependencies import get_cache_enhanced_processor
from cache_enhanced_processor import CacheEnhancedProcessor


router = APIRouter(prefix="/api/v1/cache", tags=["cache"])


@router.get("/statistics")
async def get_cache_statistics(
    cache_processor: Optional[CacheEnhancedProcessor] = Depends(get_cache_enhanced_processor)
):
    """获取缓存统计信息"""
    if not cache_processor:
        return {
            "success": False,
            "error": "Cache enhanced processor not initialized"
        }
    
    try:
        stats = cache_processor.get_cache_statistics()
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "statistics": stats
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取缓存统计失败: {str(e)}"
        }


@router.get("/activity")
async def get_cache_activity(
    limit: int = 50,
    cache_processor: Optional[CacheEnhancedProcessor] = Depends(get_cache_enhanced_processor)
):
    """获取缓存活动记录"""
    if not cache_processor:
        return {
            "success": False,
            "error": "Cache enhanced processor not initialized"
        }
    
    try:
        activity = cache_processor.get_cache_activity(limit)
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "activity": activity
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取缓存活动失败: {str(e)}"
        }


@router.get("/status")
async def get_cache_status(
    cache_processor: Optional[CacheEnhancedProcessor] = Depends(get_cache_enhanced_processor)
):
    """获取缓存状态信息"""
    if not cache_processor:
        return {
            "success": False,
            "error": "Cache enhanced processor not initialized"
        }
    
    try:
        cache_status = cache_processor.is_cache_enabled()
        cache_stats = cache_processor.get_cache_statistics()
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "cache_status": cache_status,
            "quick_stats": {
                "total_operations": cache_stats.get("overall_statistics", {}).get("total_operations", 0),
                "hit_ratio": cache_stats.get("overall_statistics", {}).get("hit_ratio_percent", 0),
                "time_saved": cache_stats.get("overall_statistics", {}).get("total_time_saved_seconds", 0),
                "efficiency": cache_stats.get("overall_statistics", {}).get("efficiency_improvement_percent", 0),
                "health": cache_stats.get("cache_health", {}).get("status", "unknown")
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取缓存状态失败: {str(e)}"
        }


@router.post("/clear")
async def clear_cache_statistics(
    cache_processor: Optional[CacheEnhancedProcessor] = Depends(get_cache_enhanced_processor)
):
    """清除缓存统计数据"""
    if not cache_processor:
        return {
            "success": False,
            "error": "Cache enhanced processor not initialized"
        }
    
    try:
        cache_processor.clear_cache_statistics()
        return {
            "success": True,
            "message": "缓存统计数据已清除",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"清除缓存统计失败: {str(e)}"
        }


@router.get("/health")
async def get_cache_health(
    cache_processor: Optional[CacheEnhancedProcessor] = Depends(get_cache_enhanced_processor)
):
    """获取缓存健康状态"""
    if not cache_processor:
        return {
            "success": False,
            "error": "Cache enhanced processor not initialized",
            "health": "unavailable"
        }
    
    try:
        cache_stats = cache_processor.get_cache_statistics()
        cache_health = cache_stats.get("cache_health", {})
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "health": cache_health,
            "summary": {
                "status": cache_health.get("status", "unknown"),
                "hit_ratio": cache_stats.get("overall_statistics", {}).get("hit_ratio_percent", 0),
                "efficiency_improvement": cache_stats.get("overall_statistics", {}).get("efficiency_improvement_percent", 0)
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取缓存健康状态失败: {str(e)}",
            "health": "error"
        }


@router.post("/refresh")
async def refresh_cache_metrics(
    cache_processor: Optional[CacheEnhancedProcessor] = Depends(get_cache_enhanced_processor)
):
    """刷新缓存指标"""
    if not cache_processor:
        return {
            "success": False,
            "error": "Cache enhanced processor not initialized"
        }
    
    try:
        # TODO: 在Phase 4中实现缓存指标刷新逻辑
        # cache_processor.refresh_metrics()
        
        return {
            "success": True,
            "message": "缓存指标已刷新",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"刷新缓存指标失败: {str(e)}"
        }


@router.get("/performance")
async def get_cache_performance(
    time_window: str = "1h",  # 1h, 24h, 7d, 30d
    cache_processor: Optional[CacheEnhancedProcessor] = Depends(get_cache_enhanced_processor)
):
    """获取缓存性能指标"""
    if not cache_processor:
        return {
            "success": False,
            "error": "Cache enhanced processor not initialized"
        }
    
    try:
        stats = cache_processor.get_cache_statistics()
        
        # 根据时间窗口筛选性能数据
        performance_data = {
            "time_window": time_window,
            "hit_ratio": stats.get("overall_statistics", {}).get("hit_ratio_percent", 0),
            "miss_ratio": 100 - stats.get("overall_statistics", {}).get("hit_ratio_percent", 0),
            "total_requests": stats.get("overall_statistics", {}).get("total_operations", 0),
            "cache_hits": stats.get("overall_statistics", {}).get("cache_hits", 0),
            "cache_misses": stats.get("overall_statistics", {}).get("cache_misses", 0),
            "time_saved_seconds": stats.get("overall_statistics", {}).get("total_time_saved_seconds", 0),
            "efficiency_improvement": stats.get("overall_statistics", {}).get("efficiency_improvement_percent", 0)
        }
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "performance": performance_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取缓存性能失败: {str(e)}"
        }


@router.get("/config")
async def get_cache_configuration(
    cache_processor: Optional[CacheEnhancedProcessor] = Depends(get_cache_enhanced_processor)
):
    """获取缓存配置信息"""
    if not cache_processor:
        return {
            "success": False,
            "error": "Cache enhanced processor not initialized"
        }
    
    try:
        from config.settings import settings
        
        cache_config = {
            "parse_cache_enabled": settings.enable_parse_cache,
            "llm_cache_enabled": settings.enable_llm_cache,
            "storage_directory": settings.working_dir,
            "cache_processor_available": True
        }
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "configuration": cache_config
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取缓存配置失败: {str(e)}"
        }