"""
依赖注入配置
管理应用中所有依赖的创建和生命周期
"""
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException

from config.settings import settings
from core.rag_manager import get_rag_manager, RAGManager
from core.state_manager import get_state_manager, StateManager
from cache_enhanced_processor import CacheEnhancedProcessor


# 核心依赖 - 单例模式
@lru_cache()
def get_settings():
    """获取应用设置（单例）"""
    return settings


@lru_cache()
def get_state_manager_singleton() -> StateManager:
    """获取状态管理器（单例）"""
    return get_state_manager()


@lru_cache()
def get_rag_manager_singleton() -> RAGManager:
    """获取RAG管理器（单例）"""
    return get_rag_manager()


# 异步依赖
async def get_rag_instance(
    rag_manager: RAGManager = Depends(get_rag_manager_singleton)
):
    """获取RAG实例"""
    rag_instance = await rag_manager.get_rag_instance()
    if rag_instance is None:
        raise HTTPException(
            status_code=503, 
            detail="RAG系统未初始化或初始化失败"
        )
    return rag_instance


async def get_cache_enhanced_processor(
    rag_manager: RAGManager = Depends(get_rag_manager_singleton)
) -> Optional[CacheEnhancedProcessor]:
    """获取缓存增强处理器"""
    return await rag_manager.get_cache_enhanced_processor()


# 存储库依赖（暂时保持简单，后续可以扩展）
def get_document_repository(
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取文档存储库"""
    # 这里可以返回一个专门的DocumentRepository实例
    # 目前直接返回状态管理器，后续可以重构
    return state_manager


def get_task_repository(
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取任务存储库"""
    return state_manager


def get_batch_repository(
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取批量操作存储库"""
    return state_manager


# 服务层依赖
async def get_document_service(
    state_manager: StateManager = Depends(get_state_manager_singleton),
    rag_manager: RAGManager = Depends(get_rag_manager_singleton)
):
    """获取文档服务"""
    from services.document_service import DocumentService
    from utils.secure_file_handler import get_secure_file_handler
    
    secure_handler = get_secure_file_handler()
    return DocumentService(state_manager, rag_manager, secure_handler)


async def get_processing_service(
    state_manager: StateManager = Depends(get_state_manager_singleton),
    rag_manager: RAGManager = Depends(get_rag_manager_singleton)
):
    """获取处理服务"""
    from services.processing_service import ProcessingService
    return ProcessingService(state_manager, rag_manager)


async def get_batch_service(
    state_manager: StateManager = Depends(get_state_manager_singleton),
    rag_manager: RAGManager = Depends(get_rag_manager_singleton),
    processing_service = Depends(get_processing_service)
):
    """获取批量操作服务"""
    from services.batch_service import BatchService
    return BatchService(state_manager, rag_manager, processing_service)


async def get_query_service(
    state_manager: StateManager = Depends(get_state_manager_singleton),
    rag_manager: RAGManager = Depends(get_rag_manager_singleton)
):
    """获取查询服务"""
    from services.query_service import QueryService
    from config.settings import settings
    
    return QueryService(
        state_manager,
        rag_manager,
        enable_cache=settings.enable_query_cache,
        cache_ttl_hours=settings.query_cache_ttl_hours
    )


async def get_monitoring_service(
    state_manager: StateManager = Depends(get_state_manager_singleton),
    rag_manager: RAGManager = Depends(get_rag_manager_singleton)
):
    """获取监控服务"""
    from services.monitoring_service import MonitoringService
    return MonitoringService(state_manager, rag_manager)


# 工具函数依赖
def get_websocket_manager(
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取WebSocket管理器"""
    return state_manager  # 暂时使用状态管理器，后续可以创建专门的WebSocketManager


# 认证依赖（复用现有的认证系统）
try:
    from auth.simple_auth import get_current_user_optional, get_current_user_required, get_auth
    
    # 重新导出认证依赖
    __all__ = [
        "get_settings",
        "get_state_manager_singleton", 
        "get_rag_manager_singleton",
        "get_rag_instance",
        "get_cache_enhanced_processor",
        "get_document_repository",
        "get_task_repository", 
        "get_batch_repository",
        "get_websocket_manager",
        "get_document_service",
        "get_processing_service",
        "get_batch_service",
        "get_query_service",
        "get_monitoring_service",
        "get_current_user_optional",
        "get_current_user_required",
        "get_auth"
    ]
    
except ImportError:
    # 如果认证模块不可用，提供默认实现
    def get_current_user_optional():
        return None
    
    def get_current_user_required():
        raise HTTPException(status_code=401, detail="认证系统不可用")
        
    def get_auth():
        return None
    
    __all__ = [
        "get_settings",
        "get_state_manager_singleton",
        "get_rag_manager_singleton", 
        "get_rag_instance",
        "get_cache_enhanced_processor",
        "get_document_repository",
        "get_task_repository",
        "get_batch_repository",
        "get_websocket_manager",
        "get_document_service",
        "get_processing_service",
        "get_batch_service",
        "get_query_service",
        "get_monitoring_service"
    ]


# 健康检查依赖
async def check_system_health(
    rag_manager: RAGManager = Depends(get_rag_manager_singleton),
    state_manager: StateManager = Depends(get_state_manager_singleton)
) -> dict:
    """系统健康检查"""
    rag_health = await rag_manager.health_check()
    state_stats = await state_manager.get_statistics()
    
    return {
        "rag_system": rag_health,
        "state_management": {
            "status": "healthy",
            "statistics": state_stats
        },
        "overall_status": "healthy" if rag_health.get("rag_ready", False) else "degraded"
    }