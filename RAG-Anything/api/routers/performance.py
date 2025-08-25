#!/usr/bin/env python3
"""
Performance Monitoring Router - Complete Implementation
Phase 4: Performance optimization integration with modern architecture
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Depends, Body
from pydantic import BaseModel, Field

from services.performance_service import get_performance_service, PerformanceService
from middleware.performance_middleware import get_performance_middleware, PerformanceMiddleware

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/performance",
    tags=["performance"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"}
    }
)


# Pydantic models
class PerformanceMetricsResponse(BaseModel):
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    memory_available: int
    disk_usage: float
    gpu_usage: float = 0.0
    gpu_memory_used: float = 0.0
    gpu_memory_total: float = 0.0
    active_processes: int
    context_switches: int


class RequestPerformanceResponse(BaseModel):
    request_id: str
    method: str
    path: str
    processing_time: float
    status_code: int
    memory_usage: Dict[str, float]
    performance_category: str
    timestamp: datetime
    is_slow_request: bool
    is_memory_intensive: bool


@router.get(
    "/metrics/current",
    response_model=PerformanceMetricsResponse,
    summary="获取当前系统性能指标"
)
async def get_current_metrics(
    performance_service: PerformanceService = Depends(get_performance_service)
):
    """获取当前系统性能指标"""
    try:
        metrics = await performance_service.get_current_metrics()
        return PerformanceMetricsResponse(
            timestamp=metrics.timestamp,
            cpu_usage=metrics.cpu_usage,
            memory_usage=metrics.memory_usage,
            memory_available=metrics.memory_available,
            disk_usage=metrics.disk_usage,
            gpu_usage=metrics.gpu_usage,
            gpu_memory_used=metrics.gpu_memory_used,
            gpu_memory_total=metrics.gpu_memory_total,
            active_processes=metrics.active_processes,
            context_switches=metrics.context_switches
        )
    except Exception as e:
        logger.error(f"获取当前性能指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取性能指标失败: {str(e)}")


@router.get(
    "/metrics/history",
    response_model=List[PerformanceMetricsResponse],
    summary="获取历史性能指标"
)
async def get_metrics_history(
    hours: int = Query(24, description="时间范围（小时）", ge=1, le=168),
    performance_service: PerformanceService = Depends(get_performance_service)
):
    """获取历史性能指标"""
    try:
        metrics_list = await performance_service.get_metrics_history(hours)
        return [
            PerformanceMetricsResponse(
                timestamp=m.timestamp,
                cpu_usage=m.cpu_usage,
                memory_usage=m.memory_usage,
                memory_available=m.memory_available,
                disk_usage=m.disk_usage,
                gpu_usage=m.gpu_usage,
                gpu_memory_used=m.gpu_memory_used,
                gpu_memory_total=m.gpu_memory_total,
                active_processes=m.active_processes,
                context_switches=m.context_switches
            )
            for m in metrics_list
        ]
    except Exception as e:
        logger.error(f"获取历史性能指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取历史指标失败: {str(e)}")


@router.get("/summary", summary="获取性能摘要")
async def get_performance_summary(
    performance_service: PerformanceService = Depends(get_performance_service)
):
    """获取性能摘要"""
    try:
        summary = await performance_service.get_performance_summary()
        return {"status": "success", "data": summary}
    except Exception as e:
        logger.error(f"获取性能摘要失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取摘要失败: {str(e)}")


@router.post("/optimize/batch", summary="批量处理优化建议")
async def get_batch_optimization(
    file_count: int = Query(..., description="文件数量", ge=1),
    total_size_mb: float = Query(..., description="文件总大小（MB）", ge=0.1),
    performance_service: PerformanceService = Depends(get_performance_service)
):
    """获取批量处理优化建议"""
    try:
        optimization = await performance_service.optimize_for_batch_processing(
            file_count=file_count,
            total_size_mb=total_size_mb
        )
        return {"status": "success", "data": optimization}
    except Exception as e:
        logger.error(f"获取批量优化建议失败: {e}")
        raise HTTPException(status_code=500, detail=f"优化建议生成失败: {str(e)}")


@router.get(
    "/requests/slow",
    response_model=List[RequestPerformanceResponse],
    summary="获取慢请求列表"
)
async def get_slow_requests(
    limit: int = Query(50, description="返回记录数量", ge=1, le=1000)
):
    """获取慢请求列表"""
    try:
        middleware = get_performance_middleware()
        if not middleware:
            raise HTTPException(status_code=503, detail="性能监控中间件未初始化")
        
        slow_requests = middleware.get_slow_requests(limit)
        return [
            RequestPerformanceResponse(
                request_id=req["request_id"],
                method=req["method"],
                path=req["path"],
                processing_time=req["processing_time"],
                status_code=req["status_code"],
                memory_usage=req["memory_usage"],
                performance_category=req["performance_category"],
                timestamp=datetime.fromisoformat(req["timestamp"]),
                is_slow_request=req["is_slow_request"],
                is_memory_intensive=req["is_memory_intensive"]
            )
            for req in slow_requests
        ]
    except Exception as e:
        logger.error(f"获取慢请求失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取慢请求失败: {str(e)}")


@router.get("/requests/summary", summary="获取请求性能摘要")
async def get_request_performance_summary(
    hours: int = Query(24, description="时间范围（小时）", ge=1, le=168)
):
    """获取请求性能摘要"""
    try:
        middleware = get_performance_middleware()
        if not middleware:
            raise HTTPException(status_code=503, detail="性能监控中间件未初始化")
        
        summary = middleware.get_performance_summary(hours)
        return {"status": "success", "data": summary}
    except Exception as e:
        logger.error(f"获取请求性能摘要失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取请求摘要失败: {str(e)}")


@router.post("/cleanup", summary="清理性能数据")
async def cleanup_performance_data(
    days: int = Query(7, description="保留天数", ge=1, le=30),
    performance_service: PerformanceService = Depends(get_performance_service)
):
    """清理性能数据"""
    try:
        cleanup_result = await performance_service.cleanup_old_data(days)
        
        middleware = get_performance_middleware()
        middleware_cleaned = 0
        if middleware:
            hours = days * 24
            middleware_cleaned = middleware.clear_old_metrics(hours)
        
        return {
            "status": "success",
            "message": "性能数据清理完成",
            "data": {
                **cleanup_result,
                "middleware_metrics_cleaned": middleware_cleaned,
                "retention_days": days
            }
        }
    except Exception as e:
        logger.error(f"清理性能数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据清理失败: {str(e)}")


@router.get("/health", summary="性能监控健康检查")
async def performance_health_check():
    """性能监控健康检查"""
    try:
        health_status = {
            "status": "healthy",
            "components": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # 检查性能服务
        try:
            performance_service = get_performance_service()
            current_metrics = await performance_service.get_current_metrics()
            health_status["components"]["performance_service"] = {
                "status": "healthy",
                "last_metrics_time": current_metrics.timestamp.isoformat()
            }
        except Exception as e:
            health_status["components"]["performance_service"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # 检查性能中间件
        try:
            middleware = get_performance_middleware()
            if middleware:
                summary = middleware.get_performance_summary(1)
                health_status["components"]["performance_middleware"] = {
                    "status": "healthy",
                    "total_requests_last_hour": summary.get("total_requests", 0)
                }
            else:
                health_status["components"]["performance_middleware"] = {
                    "status": "unhealthy",
                    "error": "Middleware not initialized"
                }
                health_status["status"] = "degraded"
        except Exception as e:
            health_status["components"]["performance_middleware"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        return health_status
    except Exception as e:
        logger.error(f"性能监控健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/dashboard", summary="性能监控仪表板数据")
async def get_performance_dashboard(
    hours: int = Query(24, description="时间范围（小时）", ge=1, le=168),
    performance_service: PerformanceService = Depends(get_performance_service)
):
    """获取性能监控仪表板数据"""
    try:
        # 获取系统性能摘要
        performance_summary = await performance_service.get_performance_summary()
        
        # 获取请求性能摘要
        middleware = get_performance_middleware()
        request_summary = {}
        if middleware:
            request_summary = middleware.get_performance_summary(hours)
        
        # 获取活跃告警
        alerts = await performance_service.get_active_alerts()
        
        # 获取历史指标
        history = await performance_service.get_metrics_history(hours)
        recent_metrics = history[-50:] if len(history) > 50 else history
        
        return {
            "status": "success",
            "data": {
                "system_performance": performance_summary,
                "request_performance": request_summary,
                "active_alerts": [
                    {
                        "alert_id": alert.alert_id,
                        "alert_type": alert.alert_type,
                        "severity": alert.severity,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat()
                    }
                    for alert in alerts
                ],
                "recent_metrics": [
                    {
                        "timestamp": m.timestamp.isoformat(),
                        "cpu_usage": m.cpu_usage,
                        "memory_usage": m.memory_usage,
                        "gpu_usage": m.gpu_usage,
                        "disk_usage": m.disk_usage
                    }
                    for m in recent_metrics
                ],
                "time_range_hours": hours,
                "last_updated": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"获取性能仪表板数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取仪表板数据失败: {str(e)}")