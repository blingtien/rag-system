#!/usr/bin/env python3
"""
RAG-Anything API Server - 重构版本
基于模块化架构的新版本，使用依赖注入和现代Python设计模式
Phase 3: 集成统一错误处理和监控系统
"""
import asyncio
import logging
import uvicorn
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 导入配置和核心组件
from config.settings import settings
from config.dependencies import get_state_manager_singleton, get_rag_manager_singleton
from core.state_manager import get_state_manager
from core.rag_manager import get_rag_manager

# 导入新的错误处理和监控中间件
from middleware import (
    create_error_handler_middleware, 
    websocket_error_handler,
    debug_profiler,
    error_tracker,
    LoggerFactory,
    default_logger,
    is_debug_mode
)

# 导入性能监控组件
from middleware.performance_middleware import PerformanceMiddleware, set_performance_middleware
from services.performance_service import get_performance_service

# 导入所有路由模块
from routers import documents, tasks, batch, query, system, websocket, cache, performance
from routers.error_dashboard import router as error_dashboard_router
from routers.network_optimization import router as network_optimization_router

# 导入网络优化组件
from middleware.network_optimization_suite import (
    initialize_network_optimizations,
    cleanup_network_optimizations,
    NetworkOptimizationConfig,
    OptimizationLevel
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("=== 服务器启动初始化开始 ===")
    
    try:
        # 初始化统一日志系统
        LoggerFactory.configure_logging(
            level="DEBUG" if is_debug_mode() else "INFO",
            enable_debug=is_debug_mode()
        )
        await default_logger.info("统一日志系统初始化完成")
        
        # 启动WebSocket错误处理器后台任务
        await websocket_error_handler.start_background_tasks()
        await default_logger.info("WebSocket错误处理器启动完成")
        
        # 初始化状态管理器
        state_manager = get_state_manager()
        await state_manager.load_state()
        await default_logger.info("状态管理器初始化完成")
        
        # 初始化RAG管理器
        rag_manager = get_rag_manager()
        await rag_manager.get_rag_instance()
        await default_logger.info("RAG管理器初始化完成")
        
        # Phase 3: 集成WebSocket日志处理器
        from websocket_log_handler import setup_websocket_logging
        setup_websocket_logging()
        await default_logger.info("WebSocket日志处理器集成完成")
        
        # 加载已存在的文档
        await _load_existing_documents(state_manager)
        
        documents_count = len(await state_manager.get_all_documents())
        await default_logger.info(f"=== 服务器启动完成，当前有 {documents_count} 个文档 ===")
        
        # Phase 4: 初始化性能监控服务
        performance_service = get_performance_service()
        await default_logger.info("性能监控服务初始化完成")
        
        # 启动性能监控
        if debug_profiler.enable_profiling:
            await default_logger.info("性能监控已启用")
        
        await default_logger.info(f"调试模式: {'开启' if is_debug_mode() else '关闭'}")
        
        # Phase 5: 初始化网络优化套件
        try:
            network_config = NetworkOptimizationConfig(
                optimization_level=OptimizationLevel.STANDARD,
                enable_message_compression=True,
                enable_message_batching=True,
                enable_performance_monitoring=True,
                enable_reliability_layer=True
            )
            await initialize_network_optimizations(app, network_config)
            await default_logger.info("网络优化套件初始化完成")
        except Exception as e:
            await default_logger.error(f"网络优化套件初始化失败: {str(e)}")
            # 网络优化失败不应该阻止服务器启动
        
    except Exception as e:
        await default_logger.error(f"服务器启动初始化失败: {str(e)}")
        logger.error(f"服务器启动初始化失败: {str(e)}")
        raise
    
    yield
    
    # 关闭时清理
    await default_logger.info("=== 服务器关闭清理开始 ===")
    
    try:
        # 停止WebSocket错误处理器后台任务
        await websocket_error_handler.stop_background_tasks()
        await default_logger.info("WebSocket错误处理器已关闭")
        
        # 清理WebSocket连接
        state_manager = get_state_manager()
        await state_manager.clear_websockets()
        
        # 关闭RAG系统
        rag_manager = get_rag_manager()
        await rag_manager.shutdown()
        
        # Phase 4: 关闭性能监控服务
        performance_service = get_performance_service()
        await performance_service.shutdown()
        await default_logger.info("性能监控服务已关闭")
        
        # Phase 5: 清理网络优化套件
        try:
            await cleanup_network_optimizations()
            await default_logger.info("网络优化套件已关闭")
        except Exception as e:
            await default_logger.error(f"网络优化套件关闭失败: {str(e)}")
        
        # 清理错误追踪数据（如果需要的话）
        # error_tracker.clear_all_data()
        
        await default_logger.info("=== 服务器关闭清理完成 ===")
        
    except Exception as e:
        await default_logger.error(f"服务器关闭清理失败: {str(e)}")
        logger.error(f"服务器关闭清理失败: {str(e)}")


# 创建FastAPI应用实例
app = FastAPI(
    title="RAG-Anything API",
    version="2.0.0",
    description="重构版本的RAG-Anything API服务器，采用模块化架构，集成统一错误处理和监控系统",
    lifespan=lifespan
)

# Phase 3: 添加统一错误处理中间件
error_handler_middleware = create_error_handler_middleware(enable_debug=is_debug_mode())
app.add_middleware(error_handler_middleware.__class__, enable_debug=is_debug_mode())

# Phase 4: 添加性能监控中间件
performance_middleware = PerformanceMiddleware(app)
set_performance_middleware(performance_middleware)
app.add_middleware(PerformanceMiddleware)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# 注册所有路由模块
app.include_router(documents.router)
app.include_router(tasks.router)
app.include_router(batch.router)
app.include_router(query.router)
app.include_router(system.router)
app.include_router(websocket.router)
app.include_router(cache.router)

# Phase 3: 注册错误监控Dashboard路由
app.include_router(error_dashboard_router)

# Phase 4: 注册性能监控路由
app.include_router(performance.router)

# Phase 5: 注册网络优化路由
app.include_router(network_optimization_router)


@app.get("/")
async def root():
    """根路径端点"""
    return {
        "message": "RAG-Anything API Server v2.0 - Refactored Edition",
        "version": "2.0.0",
        "architecture": "modular",
        "timestamp": datetime.now().isoformat(),
        "documentation": "/docs",
        "health_check": "/health"
    }


async def _load_existing_documents(state_manager):
    """从RAG存储和API状态文件中加载已存在的文档"""
    try:
        # 1. 首先从API状态文件加载
        # 这个逻辑已经在state_manager.load_state()中处理
        
        # 2. 从RAG系统中加载文档
        import os
        import json
        from core.state_manager import Document
        
        doc_status_file = os.path.join(settings.working_dir, "kv_store_doc_status.json")
        if not os.path.exists(doc_status_file):
            logger.info("没有找到现有RAG文档状态文件")
            return
        
        with open(doc_status_file, 'r', encoding='utf-8') as f:
            doc_status_data = json.load(f)
        
        logger.info(f"从RAG存储中发现 {len(doc_status_data)} 个已处理文档")
        
        # 获取已存在的文档
        existing_docs = await state_manager.get_all_documents()
        existing_rag_ids = {doc.rag_doc_id for doc in existing_docs if doc.rag_doc_id}
        
        # 只添加不存在的文档
        added_count = 0
        for doc_id, doc_info in doc_status_data.items():
            if doc_info.get('status') == 'processed' and doc_id not in existing_rag_ids:
                # 生成文档记录
                import uuid
                document_id = str(uuid.uuid4())
                file_name = os.path.basename(doc_info.get('file_path', f'document_{doc_id}'))
                
                document = Document(
                    document_id=document_id,
                    file_name=file_name,
                    file_path=doc_info.get('file_path', ''),
                    file_size=doc_info.get('content_length', 0),
                    status="completed",
                    created_at=doc_info.get('created_at', datetime.now().isoformat()),
                    updated_at=doc_info.get('updated_at', datetime.now().isoformat()),
                    processing_time=0,  # 历史文档没有处理时间记录
                    content_length=doc_info.get('content_length', 0),
                    chunks_count=doc_info.get('chunks_count', 0),
                    rag_doc_id=doc_id,  # 保存RAG系统的文档ID
                    content_summary=(doc_info.get('content_summary', '')[:100] + "...") if doc_info.get('content_summary') else ""
                )
                
                await state_manager.add_document(document)
                added_count += 1
                logger.info(f"加载已存在文档: {file_name} (chunks: {doc_info.get('chunks_count', 0)})")
        
        logger.info(f"新增 {added_count} 个RAG文档")
        
    except Exception as e:
        logger.error(f"加载RAG文档失败: {str(e)}")


def main():
    """主函数 - 启动服务器"""
    print("🚀 Starting RAG-Anything API Server v2.0 - Phase 3 Enhanced Edition")
    print("📋 Available endpoints:")
    print("   🔍 Health: http://127.0.0.1:8001/health")
    print("   📤 Upload: http://127.0.0.1:8001/api/v1/documents/upload") 
    print("   📤 Batch Upload: http://127.0.0.1:8001/api/v1/documents/upload/batch")
    print("   ▶️  Manual Process: http://127.0.0.1:8001/api/v1/documents/{document_id}/process")
    print("   ⚡ Batch Process: http://127.0.0.1:8001/api/v1/documents/process/batch")
    print("   📋 Tasks: http://127.0.0.1:8001/api/v1/tasks")
    print("   📊 Detailed Status: http://127.0.0.1:8001/api/v1/tasks/{task_id}/detailed-status")
    print("   📄 Docs: http://127.0.0.1:8001/api/v1/documents")
    print("   🔍 Query: http://127.0.0.1:8001/api/v1/query")
    print("   📊 System Status: http://127.0.0.1:8001/api/system/status")
    print("   📈 Parser Stats: http://127.0.0.1:8001/api/system/parser-stats")
    print("   📋 Batch Operations: http://127.0.0.1:8001/api/v1/batch-operations")
    print("   🔌 WebSocket: ws://127.0.0.1:8001/ws/task/{task_id}")
    print()
    print("💾 Cache Management:")
    print("   📈 Cache Statistics: http://127.0.0.1:8001/api/v1/cache/statistics")
    print("   📊 Cache Status: http://127.0.0.1:8001/api/v1/cache/status")
    print("   📋 Cache Activity: http://127.0.0.1:8001/api/v1/cache/activity")
    print("   🗑️  Clear Cache Stats: http://127.0.0.1:8001/api/v1/cache/clear")
    print()
    print("🔧 Phase 3: Error Handling & Monitoring Dashboard:")
    print("   📊 Dashboard Overview: http://127.0.0.1:8001/api/v1/debug/overview")
    print("   🔍 Error Analysis: http://127.0.0.1:8001/api/v1/debug/errors/analyze")
    print("   ⚡ Performance Analysis: http://127.0.0.1:8001/api/v1/debug/performance/analyze")
    print("   🔗 Trace Analysis: http://127.0.0.1:8001/api/v1/debug/traces/analyze")
    print("   📈 Realtime Status: http://127.0.0.1:8001/api/v1/debug/realtime/status")
    print("   💊 Health Check: http://127.0.0.1:8001/api/v1/debug/health")
    print("   ⚙️  Debug Config: http://127.0.0.1:8001/api/v1/debug/config")
    print("   🗑️  Cleanup Data: http://127.0.0.1:8001/api/v1/debug/cleanup")
    print()
    print("⚡ Phase 4: Performance Monitoring & Optimization:")
    print("   📊 Current Metrics: http://127.0.0.1:8001/api/v1/performance/metrics/current")
    print("   📈 Historical Data: http://127.0.0.1:8001/api/v1/performance/metrics/history")
    print("   📋 Performance Summary: http://127.0.0.1:8001/api/v1/performance/summary")
    print("   🚀 Batch Optimization: http://127.0.0.1:8001/api/v1/performance/optimize/batch")
    print("   🐌 Slow Requests: http://127.0.0.1:8001/api/v1/performance/requests/slow")
    print("   💾 Memory Intensive: http://127.0.0.1:8001/api/v1/performance/requests/memory-intensive")
    print("   📊 Request Summary: http://127.0.0.1:8001/api/v1/performance/requests/summary")
    print("   🧹 Data Cleanup: http://127.0.0.1:8001/api/v1/performance/cleanup")
    print("   💊 Health Check: http://127.0.0.1:8001/api/v1/performance/health")
    print("   📈 Dashboard: http://127.0.0.1:8001/api/v1/performance/dashboard")
    print()
    print("🌐 Phase 5: Network Optimization & WebSocket Enhancement:")
    print("   📊 Optimization Status: http://127.0.0.1:8001/api/v1/network/optimization/status")
    print("   📈 Network Statistics: http://127.0.0.1:8001/api/v1/network/optimization/statistics")
    print("   ⚙️  Optimization Config: http://127.0.0.1:8001/api/v1/network/optimization/configuration")
    print("   🔧 Update Config: http://127.0.0.1:8001/api/v1/network/optimization/configure")
    print("   🔍 Network Diagnostics: http://127.0.0.1:8001/api/v1/network/diagnostics/run")
    print("   🌊 Connection Pools: http://127.0.0.1:8001/api/v1/network/connection-pools/status")
    print("   ⚖️  Load Balancer: http://127.0.0.1:8001/api/v1/network/load-balancer/status")
    print("   📊 Performance Metrics: http://127.0.0.1:8001/api/v1/network/performance/current")
    print("   📈 Performance History: http://127.0.0.1:8001/api/v1/network/performance/history")
    print("   💬 Message Optimization: http://127.0.0.1:8001/api/v1/network/message-optimization/statistics")
    print("   🛡️  Reliability Sessions: http://127.0.0.1:8001/api/v1/network/reliability/sessions")
    print("   💊 Network Health Check: http://127.0.0.1:8001/api/v1/network/health")
    print("   📋 Dashboard Summary: http://127.0.0.1:8001/api/v1/network/dashboard/summary")
    print("   💡 Recommendations: http://127.0.0.1:8001/api/v1/network/recommendations")
    print()
    print("🏗️ Architecture v2.0 Features:")
    print("   📦 Modular router-based architecture")
    print("   🔧 Dependency injection pattern")
    print("   🧠 Centralized state management")
    print("   🔄 Singleton resource management")
    print("   🛡️  Type-safe configuration system")
    print("   📊 Enhanced error handling and monitoring")
    print("   ⚡ Optimized async/await patterns")
    print("   🎯 SOLID principles compliance")
    print()
    print("🆕 Phase 3 New Features:")
    print("   🎯 Unified error handling middleware")
    print("   📊 Distributed tracing and call chain analysis")  
    print("   🔍 Real-time error monitoring dashboard")
    print("   🌐 Enhanced WebSocket error handling")
    print("   📈 Performance profiling and bottleneck detection")
    print("   🧪 Development/Production environment awareness")
    print("   📝 Structured logging with context correlation")
    print("   🚨 Intelligent error recovery and suggestions")
    print()
    print("🚀 Phase 4 New Features:")
    print("   ⚡ Real-time system performance monitoring")
    print("   💾 Memory usage tracking and leak detection")  
    print("   🖥️  CPU, GPU, disk usage monitoring")
    print("   📊 Request-level performance middleware")
    print("   🐌 Slow request detection and analysis")
    print("   💡 Intelligent batch processing optimization")
    print("   📈 Performance history and trend analysis")
    print("   🔧 Resource optimization recommendations")
    print("   🎯 Automated performance tuning")
    print()
    print("🚀 Phase 5 Network Optimization Features:")
    print("   🌊 WebSocket connection pooling and management")
    print("   🗜️  Message compression (gzip, deflate, brotli)")
    print("   📦 Intelligent message batching and aggregation")
    print("   🔒 Message reliability layer (ACK/NACK, retry)")
    print("   🎯 QoS levels (At-Most-Once, At-Least-Once, Exactly-Once)")  
    print("   🌐 HTTP/2 optimization (multiplexing, server push)")
    print("   ⚖️  Multi-algorithm load balancing")
    print("   🔍 Real-time network diagnostics and monitoring")
    print("   📊 Latency, bandwidth, and connection quality analysis")
    print("   🎪 Geographic and resource-based routing")
    print("   💪 Connection health monitoring and failover")
    print("   📈 Performance optimization recommendations")
    print()
    print("🧠 Smart Processing:")
    print("   ⚡ Direct text processing (TXT/MD files)")
    print("   📄 PDF files → MinerU (specialized PDF engine)")
    print("   📊 Office files → Docling (native Office support)")
    print("   🖼️  Image files → MinerU (OCR capability)")
    print("   📈 Real-time parser usage statistics")
    print("   🎯 Manual processing control")
    print("   💾 Intelligent caching with modification tracking")
    print()
    
    # 启动服务器
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info"
    )


if __name__ == "__main__":
    main()