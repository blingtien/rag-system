"""
FastAPI Dependency Injection
Centralized management of application dependencies
"""

from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException

from config.settings import Settings, get_settings
from services.document_service import DocumentService
from services.processing_service import ProcessingService
from services.batch_service import BatchService
from services.query_service import QueryService
from services.task_service import TaskService
from services.system_service import SystemService
from storage.state_manager import StateManager
from websockets.manager import WebSocketManager
from core.initialization import RAGInitializer

# Global instances (initialized during startup)
_rag_initializer: Optional[RAGInitializer] = None
_state_manager: Optional[StateManager] = None
_websocket_manager: Optional[WebSocketManager] = None

# Service instances (lazy-loaded)
_document_service: Optional[DocumentService] = None
_processing_service: Optional[ProcessingService] = None
_batch_service: Optional[BatchService] = None
_query_service: Optional[QueryService] = None
_task_service: Optional[TaskService] = None
_system_service: Optional[SystemService] = None


async def initialize_dependencies(settings: Settings) -> None:
    """Initialize global dependencies during startup"""
    global _rag_initializer, _state_manager, _websocket_manager
    
    # Initialize core components
    _rag_initializer = RAGInitializer(settings)
    await _rag_initializer.initialize()
    
    _state_manager = StateManager(settings.working_dir_path)
    await _state_manager.load_state()
    
    _websocket_manager = WebSocketManager()


async def cleanup_dependencies() -> None:
    """Cleanup dependencies during shutdown"""
    global _websocket_manager, _state_manager
    
    if _websocket_manager:
        await _websocket_manager.disconnect_all()
    
    if _state_manager:
        await _state_manager.save_state()


# Dependency providers
def get_rag_initializer() -> RAGInitializer:
    """Get RAG initializer instance"""
    if _rag_initializer is None:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    return _rag_initializer


def get_state_manager() -> StateManager:
    """Get state manager instance"""
    if _state_manager is None:
        raise HTTPException(status_code=503, detail="State manager not initialized")
    return _state_manager


def get_websocket_manager() -> WebSocketManager:
    """Get WebSocket manager instance"""
    if _websocket_manager is None:
        raise HTTPException(status_code=503, detail="WebSocket manager not initialized")
    return _websocket_manager


@lru_cache()
def get_document_service(
    settings: Settings = Depends(get_settings),
    state_manager: StateManager = Depends(get_state_manager),
    rag_initializer: RAGInitializer = Depends(get_rag_initializer)
) -> DocumentService:
    """Get document service instance"""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService(settings, state_manager, rag_initializer)
    return _document_service


@lru_cache()
def get_processing_service(
    settings: Settings = Depends(get_settings),
    document_service: DocumentService = Depends(get_document_service),
    task_service: 'TaskService' = Depends(lambda: get_task_service()),  # Forward reference
    websocket_manager: WebSocketManager = Depends(get_websocket_manager)
) -> ProcessingService:
    """Get processing service instance"""
    global _processing_service
    if _processing_service is None:
        _processing_service = ProcessingService(
            settings, document_service, task_service, websocket_manager
        )
    return _processing_service


@lru_cache()
def get_batch_service(
    settings: Settings = Depends(get_settings),
    processing_service: ProcessingService = Depends(get_processing_service),
    state_manager: StateManager = Depends(get_state_manager)
) -> BatchService:
    """Get batch service instance"""
    global _batch_service
    if _batch_service is None:
        _batch_service = BatchService(settings, processing_service, state_manager)
    return _batch_service


@lru_cache()
def get_query_service(
    rag_initializer: RAGInitializer = Depends(get_rag_initializer),
    task_service: 'TaskService' = Depends(lambda: get_task_service())  # Forward reference
) -> QueryService:
    """Get query service instance"""
    global _query_service
    if _query_service is None:
        _query_service = QueryService(rag_initializer, task_service)
    return _query_service


@lru_cache()
def get_task_service(
    state_manager: StateManager = Depends(get_state_manager),
    websocket_manager: WebSocketManager = Depends(get_websocket_manager)
) -> TaskService:
    """Get task service instance"""
    global _task_service
    if _task_service is None:
        _task_service = TaskService(state_manager, websocket_manager)
    return _task_service


@lru_cache()
def get_system_service(
    settings: Settings = Depends(get_settings),
    state_manager: StateManager = Depends(get_state_manager),
    rag_initializer: RAGInitializer = Depends(get_rag_initializer)
) -> SystemService:
    """Get system service instance"""
    global _system_service
    if _system_service is None:
        _system_service = SystemService(settings, state_manager, rag_initializer)
    return _system_service