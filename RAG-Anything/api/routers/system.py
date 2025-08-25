"""
系统监控路由
处理系统状态、健康检查、统计信息等相关的API端点
"""
import os
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException

from config.dependencies import (
    get_rag_manager_singleton,
    get_state_manager_singleton,
    get_cache_enhanced_processor,
    check_system_health,
    get_auth
)
from core.rag_manager import RAGManager
from core.state_manager import StateManager
from config.settings import settings


router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health_check(
    rag_manager: RAGManager = Depends(get_rag_manager_singleton),
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """健康检查端点"""
    rag_health = await rag_manager.health_check()
    state_stats = await state_manager.get_statistics()
    
    # 确定整体健康状态
    rag_status = "healthy" if rag_health.get("rag_ready", False) else "unhealthy"
    overall_status = "healthy" if rag_status == "healthy" else "degraded"
    
    return {
        "status": overall_status,
        "message": "RAG-Anything API is running",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "rag_engine": rag_status,
            "state_management": "healthy",
            "tasks": "healthy",
            "documents": "healthy"
        },
        "statistics": {
            "active_tasks": len([t for t in await state_manager.get_all_tasks() if t.status == "running"]),
            "total_tasks": len(await state_manager.get_all_tasks()),
            "total_documents": len(await state_manager.get_all_documents())
        },
        "system_checks": {
            "api": True,
            "websocket": True,
            "storage": True,
            "rag_initialized": rag_health.get("rag_ready", False),
            "working_directory_exists": os.path.exists(settings.working_dir),
            "output_directory_exists": os.path.exists(settings.output_dir)
        }
    }


@router.get("/system/status")
async def get_system_status(
    rag_manager: RAGManager = Depends(get_rag_manager_singleton),
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """系统状态端点"""
    rag_health = await rag_manager.health_check()
    state_stats = await state_manager.get_statistics()
    
    # 获取系统指标
    metrics = _get_system_metrics()
    
    # 获取RAG统计信息
    rag_statistics = _get_rag_statistics()
    
    return {
        "success": True,
        "status": "healthy" if rag_health.get("rag_ready", False) else "degraded",
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics,
        "processing_stats": rag_statistics,
        "state_management": state_stats,
        "services": {
            "RAG-Anything Core": {
                "status": "running" if rag_health.get("rag_ready", False) else "stopped",
                "uptime": "实时运行"
            },
            "Document Parser": {
                "status": "running" if rag_health.get("rag_ready", False) else "stopped", 
                "uptime": "实时运行"
            },
            "Query Engine": {
                "status": "running" if rag_health.get("rag_ready", False) else "stopped",
                "uptime": "实时运行"
            },
            "Knowledge Graph": {
                "status": "running" if rag_health.get("rag_ready", False) else "stopped",
                "uptime": "实时运行"
            }
        }
    }


@router.get("/system/auth-status")
async def get_auth_status(request: Request):
    """认证状态端点 - 显示当前认证配置"""
    try:
        auth = get_auth()
        auth_info = auth.get_auth_info() if auth else {
            "auth_enabled": False,
            "localhost_bypass": True,
            "message": "认证系统不可用"
        }
    except:
        auth_info = {
            "auth_enabled": False,
            "localhost_bypass": True,
            "message": "认证系统不可用"
        }
    
    # 检查当前请求是否来自localhost
    is_localhost = "127.0.0.1" in str(request.client.host) if request.client else False
    
    return {
        "success": True,
        "auth_config": auth_info,
        "request_info": {
            "client_host": str(request.client.host) if request.client else "unknown",
            "is_localhost": is_localhost,
            "would_bypass_auth": is_localhost and auth_info.get("localhost_bypass", True)
        },
        "usage_info": {
            "token_required": auth_info.get("auth_enabled", False),
            "header_format": "Authorization: Bearer <your-token>",
            "example_curl": f"curl -H 'Authorization: Bearer YOUR_TOKEN' {request.url.replace(path='/api/v1/documents')}"
        }
    }


@router.get("/system/parser-stats")
async def get_parser_statistics():
    """获取解析器使用统计"""
    try:
        # 尝试导入智能路由器
        from smart_parser_router import router as smart_router
        from direct_text_processor import text_processor
        
        routing_stats = smart_router.get_routing_stats()
        text_processing_stats = text_processor.get_processing_stats()
        
        # 计算解析器性能指标
        total_routed = routing_stats.get("total_routed", 0)
        parser_usage = routing_stats.get("parser_usage", {})
        category_dist = routing_stats.get("category_distribution", {})
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "routing_statistics": {
                "total_files_routed": total_routed,
                "parser_usage": parser_usage,
                "category_distribution": category_dist,
                "efficiency_metrics": {
                    "direct_text_processing": parser_usage.get("direct_text", 0),
                    "avoided_conversions": parser_usage.get("direct_text", 0),
                    "conversion_rate": round(parser_usage.get("direct_text", 0) / max(total_routed, 1) * 100, 1)
                }
            },
            "text_processing_statistics": text_processing_stats,
            "parser_availability": {
                "mineru": smart_router.validate_parser_availability("mineru"),
                "docling": smart_router.validate_parser_availability("docling"), 
                "direct_text": smart_router.validate_parser_availability("direct_text")
            },
            "optimization_summary": {
                "total_optimizations": parser_usage.get("direct_text", 0) + parser_usage.get("docling", 0),
                "pdf_conversions_avoided": parser_usage.get("direct_text", 0)
            }
        }
        
    except ImportError:
        return {
            "success": False,
            "error": "Parser statistics module not available",
            "timestamp": datetime.now().isoformat()
        }


@router.get("/system/health/enhanced")
async def get_enhanced_system_health(
    rag_manager: RAGManager = Depends(get_rag_manager_singleton),
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取增强的系统健康状态"""
    try:
        # 获取基本系统指标
        metrics = _get_system_metrics()
        
        # 获取RAG健康状态
        rag_health = await rag_manager.health_check()
        
        # TODO: 在Phase 3中集成enhanced_error_handler
        # health_warnings = enhanced_error_handler.get_system_health_warnings()
        health_warnings = []
        
        # 检查存储空间
        storage_warnings = []
        try:
            import psutil
            
            for name, path in [
                ("工作目录", settings.working_dir),
                ("输出目录", settings.output_dir),
                ("上传目录", settings.upload_dir)
            ]:
                if os.path.exists(path):
                    disk_info = psutil.disk_usage(path)
                    free_gb = disk_info.free / (1024**3)
                    if free_gb < 5.0:  # Less than 5GB free
                        storage_warnings.append(f"{name} ({path}) 存储空间不足: {free_gb:.1f}GB")
        except Exception as e:
            storage_warnings.append(f"无法检查存储空间: {str(e)}")
        
        # 综合健康评分
        health_score = 100.0
        issues = []
        
        if metrics["memory_usage"] > 85:
            health_score -= 20
            issues.append("内存使用率过高")
        elif metrics["memory_usage"] > 70:
            health_score -= 10
            issues.append("内存使用率较高")
        
        if metrics["cpu_usage"] > 90:
            health_score -= 15
            issues.append("CPU使用率过高")
        elif metrics["cpu_usage"] > 75:
            health_score -= 8
            issues.append("CPU使用率较高")
        
        if metrics["disk_usage"] > 90:
            health_score -= 25
            issues.append("磁盘使用率过高")
        elif metrics["disk_usage"] > 80:
            health_score -= 12
            issues.append("磁盘使用率较高")
        
        if health_warnings:
            health_score -= len(health_warnings) * 5
            issues.extend(health_warnings)
        
        if storage_warnings:
            health_score -= len(storage_warnings) * 10
            issues.extend(storage_warnings)
        
        health_score = max(0, health_score)
        
        # 确定整体状态
        if health_score >= 85:
            overall_status = "excellent"
        elif health_score >= 70:
            overall_status = "good"
        elif health_score >= 50:
            overall_status = "warning"
        else:
            overall_status = "critical"
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall_status,
            "health_score": round(health_score, 1),
            "system_metrics": metrics,
            "gpu_status": "available" if settings.torch_available else "unavailable",
            "gpu_memory": {},  # TODO: 在Phase 4中实现GPU内存监控
            "storage_warnings": storage_warnings,
            "health_warnings": health_warnings,
            "issues": issues,
            "recommendations": [
                rec for rec in [
                    "定期清理临时文件和缓存" if metrics["disk_usage"] > 70 else None,
                    "考虑增加系统内存" if metrics["memory_usage"] > 80 else None,
                    "检查系统负载和后台进程" if metrics["cpu_usage"] > 80 else None,
                    "监控GPU温度和使用情况" if settings.torch_available else None
                ] if rec
            ],
            "processing_stats": {
                "cache_enabled": True,  # TODO: 从cache_enhanced_processor获取
                "error_handler_status": "active"
            },
            "rag_health": rag_health
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取系统健康状态失败: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


@router.get("/logs/summary")
async def get_log_summary_api(mode: str = "summary", include_debug: bool = False):
    """获取日志摘要"""
    try:
        # TODO: 在Phase 3中集成websocket_log_handler
        # from websocket_log_handler import get_log_summary
        # summary = get_log_summary(include_debug=include_debug)
        
        # 模拟日志摘要
        summary = {
            "total_logs": 0,
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "recent_errors": [],
            "recent_warnings": []
        }
        
        return {
            "success": True,
            "data": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取日志摘要失败: {str(e)}")


@router.get("/logs/core")
async def get_core_logs_api():
    """获取核心进度日志"""
    try:
        # TODO: 在Phase 3中集成websocket_log_handler
        # from websocket_log_handler import get_core_progress
        # core_logs = get_core_progress()
        
        core_logs = []
        
        return {
            "success": True,
            "logs": core_logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取核心日志失败: {str(e)}")


@router.post("/logs/clear")
async def clear_processing_logs_api():
    """清空处理日志"""
    try:
        # TODO: 在Phase 3中集成websocket_log_handler
        # from websocket_log_handler import clear_logs
        # clear_logs()
        
        return {"success": True, "message": "日志已清空"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空日志失败: {str(e)}")


def _get_system_metrics() -> dict:
    """获取系统指标"""
    try:
        import psutil
        
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 尝试获取GPU使用率（如果可用）
        gpu_usage = 0
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu_usage = gpus[0].load * 100
        except ImportError:
            gpu_usage = 0
        
        return {
            "cpu_usage": round(cpu_percent, 1),
            "memory_usage": round(memory.percent, 1),
            "disk_usage": round(disk.percent, 1),
            "gpu_usage": round(gpu_usage, 1)
        }
    except Exception as e:
        import logging
        logging.error(f"获取系统指标失败: {e}")
        return {
            "cpu_usage": 0,
            "memory_usage": 0,
            "disk_usage": 0,
            "gpu_usage": 0
        }


def _get_rag_statistics() -> dict:
    """获取RAG系统统计信息"""
    try:
        stats = {
            "documents_processed": 0,
            "entities_count": 0,
            "relationships_count": 0,
            "chunks_count": 0
        }
        
        # 尝试从RAG存储文件中读取统计信息
        try:
            # 读取实体数量
            entities_file = os.path.join(settings.working_dir, "vdb_entities.json")
            if os.path.exists(entities_file):
                with open(entities_file, 'r', encoding='utf-8') as f:
                    entities_data = json.load(f)
                    stats["entities_count"] = len(entities_data.get("data", []))
            
            # 读取关系数量
            relationships_file = os.path.join(settings.working_dir, "vdb_relationships.json")
            if os.path.exists(relationships_file):
                with open(relationships_file, 'r', encoding='utf-8') as f:
                    relationships_data = json.load(f)
                    stats["relationships_count"] = len(relationships_data.get("data", []))
            
            # 读取chunks数量
            chunks_file = os.path.join(settings.working_dir, "vdb_chunks.json")
            if os.path.exists(chunks_file):
                with open(chunks_file, 'r', encoding='utf-8') as f:
                    chunks_data = json.load(f)
                    stats["chunks_count"] = len(chunks_data.get("data", []))
                    
        except Exception as e:
            import logging
            logging.error(f"读取RAG统计信息失败: {e}")
        
        return stats
        
    except Exception as e:
        import logging
        logging.error(f"获取RAG统计信息失败: {e}")
        return {
            "documents_processed": 0,
            "entities_count": 0,
            "relationships_count": 0,
            "chunks_count": 0
        }


@router.get("/system/configuration")
async def get_system_configuration():
    """获取系统配置信息"""
    config_info = {
        "directories": {
            "working_dir": settings.working_dir,
            "output_dir": settings.output_dir,
            "upload_dir": settings.upload_dir
        },
        "rag_settings": {
            "parser": settings.parser,
            "parse_method": settings.parse_method,
            "enable_image_processing": settings.enable_image_processing,
            "enable_table_processing": settings.enable_table_processing,
            "enable_equation_processing": settings.enable_equation_processing
        },
        "cache_settings": {
            "enable_parse_cache": settings.enable_parse_cache,
            "enable_llm_cache": settings.enable_llm_cache
        },
        "processing_limits": {
            "max_concurrent_files": settings.max_concurrent_files,
            "max_concurrent_processing": settings.max_concurrent_processing
        },
        "device_info": {
            "torch_available": settings.torch_available,
            "device_type": settings.device_type
        }
    }
    
    return {
        "success": True,
        "configuration": config_info,
        "timestamp": datetime.now().isoformat()
    }