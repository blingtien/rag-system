#!/usr/bin/env python3
"""
Mock RAG-Anything API Server for Testing
模拟的RAG-Anything API服务器，用于测试前端集成功能
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List
import uvicorn
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock RAG-Anything API", version="1.0.0")

# 启用CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 模拟数据存储
tasks: Dict[str, dict] = {}
documents: Dict[str, dict] = {}
active_websockets: Dict[str, WebSocket] = {}

# 模拟处理阶段
PROCESSING_STAGES = [
    ("parsing", "Parsing Document", 15),
    ("separation", "Separating Content", 5),
    ("text_insert", "Inserting Text", 25),
    ("image_process", "Processing Images", 20),
    ("table_process", "Processing Tables", 15),
    ("equation_process", "Processing Equations", 10),
    ("graph_build", "Building Knowledge Graph", 15),
    ("indexing", "Creating Indexes", 10),
]

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "message": "Mock RAG-Anything API is running",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "raganything": "healthy",
            "tasks": "healthy",
            "documents": "healthy"
        },
        "statistics": {
            "active_tasks": len([t for t in tasks.values() if t["status"] == "running"]),
            "total_tasks": len(tasks)
        },
        "system_checks": {
            "api": True,
            "websocket": True,
            "storage": True
        }
    }

@app.post("/api/v1/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """文档上传端点"""
    task_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    
    # 创建任务记录
    task = {
        "task_id": task_id,
        "status": "pending",
        "stage": "parsing",
        "progress": 0,
        "file_path": f"/uploads/{file.filename}",
        "file_name": file.filename,
        "file_size": file.size or 1024,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "document_id": document_id,
        "total_stages": len(PROCESSING_STAGES),
        "stage_details": {
            stage[0]: {
                "status": "pending",
                "progress": 0
            } for stage in PROCESSING_STAGES
        },
        "multimodal_stats": {
            "images_count": 3,
            "tables_count": 2,
            "equations_count": 1,
            "images_processed": 0,
            "tables_processed": 0,
            "equations_processed": 0,
            "processing_success_rate": 0.0
        }
    }
    
    tasks[task_id] = task
    
    # 创建文档记录
    document = {
        "document_id": document_id,
        "file_name": file.filename,
        "file_path": f"/uploads/{file.filename}",
        "file_size": file.size or 1024,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "task_id": task_id
    }
    
    documents[document_id] = document
    
    # 启动异步处理
    asyncio.create_task(simulate_processing(task_id))
    
    return {
        "success": True,
        "task_id": task_id,
        "message": "Document upload successful, processing started",
        "file_name": file.filename,
        "file_size": file.size or 1024
    }

async def simulate_processing(task_id: str):
    """模拟文档处理过程"""
    if task_id not in tasks:
        return
        
    task = tasks[task_id]
    task["status"] = "running"
    task["started_at"] = datetime.now().isoformat()
    
    # 更新文档状态
    if task["document_id"] in documents:
        documents[task["document_id"]]["status"] = "processing"
    
    total_progress = 0
    
    for i, (stage_name, stage_label, stage_weight) in enumerate(PROCESSING_STAGES):
        # 更新当前阶段
        task["stage"] = stage_name
        task["stage_details"][stage_name]["status"] = "running"
        
        # 模拟阶段处理时间
        for progress in range(0, 101, 20):
            if task_id not in tasks:  # 任务可能被取消
                return
                
            # 更新阶段进度
            task["stage_details"][stage_name]["progress"] = progress
            
            # 计算总体进度
            stage_progress = total_progress + (progress / 100.0) * stage_weight
            task["progress"] = min(100, stage_progress)
            task["updated_at"] = datetime.now().isoformat()
            
            # 模拟多模态处理统计更新
            if stage_name == "image_process":
                task["multimodal_stats"]["images_processed"] = min(3, int(progress / 100 * 3))
            elif stage_name == "table_process":
                task["multimodal_stats"]["tables_processed"] = min(2, int(progress / 100 * 2))
            elif stage_name == "equation_process":
                task["multimodal_stats"]["equations_processed"] = min(1, int(progress / 100 * 1))
            
            # 发送WebSocket更新
            if task_id in active_websockets:
                try:
                    await active_websockets[task_id].send_text(json.dumps(task))
                except:
                    # WebSocket连接已断开
                    active_websockets.pop(task_id, None)
            
            await asyncio.sleep(0.5)  # 模拟处理时间
        
        # 完成当前阶段
        task["stage_details"][stage_name]["status"] = "completed"
        task["stage_details"][stage_name]["progress"] = 100
        total_progress += stage_weight
    
    # 完成处理
    task["status"] = "completed"
    task["progress"] = 100
    task["completed_at"] = datetime.now().isoformat()
    task["multimodal_stats"]["processing_success_rate"] = 100.0
    
    # 更新文档状态
    if task["document_id"] in documents:
        documents[task["document_id"]]["status"] = "completed"
        documents[task["document_id"]]["updated_at"] = datetime.now().isoformat()
        documents[task["document_id"]]["processing_time"] = 10.5  # 模拟处理时间
        documents[task["document_id"]]["content_length"] = 15420
        documents[task["document_id"]]["chunks_count"] = 42
    
    # 发送最终更新
    if task_id in active_websockets:
        try:
            await active_websockets[task_id].send_text(json.dumps(task))
        except:
            pass
        finally:
            active_websockets.pop(task_id, None)

@app.get("/api/v1/tasks")
async def list_tasks():
    """获取任务列表"""
    return {
        "success": True,
        "tasks": list(tasks.values()),
        "total_count": len(tasks),
        "active_tasks": len([t for t in tasks.values() if t["status"] == "running"])
    }

@app.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: str):
    """获取特定任务"""
    if task_id not in tasks:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Task not found"}
        )
    return {
        "success": True,
        "task": tasks[task_id]
    }

@app.post("/api/v1/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任务"""
    if task_id not in tasks:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Task not found"}
        )
    
    task = tasks[task_id]
    if task["status"] == "running":
        task["status"] = "cancelled"
        task["updated_at"] = datetime.now().isoformat()
        
        # 更新文档状态
        if task["document_id"] in documents:
            documents[task["document_id"]]["status"] = "failed"
            documents[task["document_id"]]["error_message"] = "Task cancelled by user"
        
        # 关闭WebSocket连接
        if task_id in active_websockets:
            try:
                await active_websockets[task_id].close()
            except:
                pass
            active_websockets.pop(task_id, None)
    
    return {
        "success": True,
        "message": "Task cancelled successfully"
    }

@app.get("/api/v1/documents")
async def list_documents():
    """获取文档列表"""
    return {
        "success": True,
        "documents": list(documents.values()),
        "total_count": len(documents),
        "status_counts": {
            "pending": len([d for d in documents.values() if d["status"] == "pending"]),
            "processing": len([d for d in documents.values() if d["status"] == "processing"]),
            "completed": len([d for d in documents.values() if d["status"] == "completed"]),
            "failed": len([d for d in documents.values() if d["status"] == "failed"])
        }
    }

@app.delete("/api/v1/documents")
async def delete_documents(request: dict):
    """删除文档"""
    document_ids = request.get("document_ids", [])
    deleted_count = 0
    
    for doc_id in document_ids:
        if doc_id in documents:
            del documents[doc_id]
            deleted_count += 1
    
    return {
        "success": True,
        "message": f"Deleted {deleted_count} documents"
    }

@app.delete("/api/v1/documents/clear")
async def clear_documents():
    """清空所有文档"""
    count = len(documents)
    documents.clear()
    tasks.clear()
    
    # 关闭所有WebSocket连接
    for ws in active_websockets.values():
        try:
            await ws.close()
        except:
            pass
    active_websockets.clear()
    
    return {
        "success": True,
        "message": f"Cleared {count} documents"
    }

@app.get("/api/system/status")
async def get_system_status():
    """系统状态端点 - 为demo.html页面提供"""
    import random
    
    return {
        "success": True,
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "metrics": {
            "cpu_usage": round(45.2 + random.uniform(-5, 5), 1),
            "memory_usage": round(68.1 + random.uniform(-3, 3), 1),
            "gpu_usage": round(78.3 + random.uniform(-10, 10), 1),
            "disk_usage": round(32.4 + random.uniform(-2, 2), 1)
        },
        "processing_stats": {
            "documents_processed": len(documents),
            "queries_handled": 156 + len([t for t in tasks.values() if t.get("type") == "query"]),
            "knowledge_blocks": 1247 + len(documents) * 30  # 模拟知识块数量
        },
        "services": {
            "RAG-Anything Core": {
                "status": "running",
                "uptime": "2天 15小时"
            },
            "Document Parser": {
                "status": "running", 
                "uptime": "2天 15小时"
            },
            "Query Engine": {
                "status": "running",
                "uptime": "2天 15小时"
            },
            "Knowledge Graph": {
                "status": "running",
                "uptime": "2天 15小时"
            }
        }
    }

@app.post("/api/v1/query")
async def query_documents(request: dict):
    """查询文档端点"""
    query = request.get("query", "")
    mode = request.get("mode", "hybrid")
    
    if not query.strip():
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Query cannot be empty"}
        )
    
    # 模拟查询结果
    mock_result = {
        "success": True,
        "query": query,
        "mode": mode,
        "result": f"基于您的查询'{query}'，我在测试文档中找到了相关信息。文档包含了用于处理的文本内容、用于解析的简单结构以及用于知识图谱创建的测试数据。此模拟响应展示了查询功能正常工作。",
        "timestamp": datetime.now().isoformat(),
        "processing_time": 0.234,
        "sources": [
            {
                "document_id": "test-doc-001",
                "document_name": "test_document.txt",
                "relevance_score": 0.85,
                "chunk_content": "这是用于RAG-Anything API测试的测试文档。内容包括：- 用于处理的文本内容",
                "chunk_index": 0
            }
        ],
        "metadata": {
            "total_documents": len(documents),
            "tokens_used": 156,
            "confidence_score": 0.89
        }
    }
    
    return mock_result

@app.websocket("/ws/task/{task_id}")
async def websocket_task_endpoint(websocket: WebSocket, task_id: str):
    """任务进度WebSocket端点"""
    await websocket.accept()
    active_websockets[task_id] = websocket
    
    try:
        # 发送当前任务状态
        if task_id in tasks:
            await websocket.send_text(json.dumps(tasks[task_id]))
        
        # 保持连接
        while True:
            try:
                # 等待客户端消息（心跳检测）
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # 30秒无消息，发送心跳
                await websocket.ping()
            except WebSocketDisconnect:
                break
    except Exception as e:
        print(f"WebSocket error for task {task_id}: {e}")
    finally:
        active_websockets.pop(task_id, None)

if __name__ == "__main__":
    print("🚀 Starting Mock RAG-Anything API Server")
    print("📋 Available endpoints:")
    print("   🔍 Health: http://127.0.0.1:8000/health")
    print("   📤 Upload: http://127.0.0.1:8000/api/v1/documents/upload") 
    print("   📋 Tasks: http://127.0.0.1:8000/api/v1/tasks")
    print("   📄 Docs: http://127.0.0.1:8000/api/v1/documents")
    print("   🔍 Query: http://127.0.0.1:8000/api/v1/query")
    print("   🔌 WebSocket: ws://127.0.0.1:8000/ws/task/{task_id}")
    print()
    
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")