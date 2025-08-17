#!/usr/bin/env python3
"""
RAG-Anything Web API Server - LightRAG WebUI Compatible Version
修复版本：完全兼容LightRAG WebUI的API接口格式和错误处理
"""

import os
import sys
import asyncio
import logging
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional
import tempfile
import json
from datetime import datetime
import hashlib
import uuid

# 加载环境变量
from dotenv import load_dotenv
load_dotenv("/home/ragsvr/projects/ragsystem/RAG-Anything/.env")
load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import structlog

# 配置结构化日志
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = structlog.get_logger(__name__)

# 接入实际RAG-Anything生产系统
project_root = Path(__file__).parent.parent / "RAG-Anything"
sys.path.insert(0, str(project_root))

try:
    from raganything import RAGAnything, RAGAnythingConfig
    from lightrag.llm.openai import openai_complete_if_cache, openai_embed
    from lightrag.utils import EmbeddingFunc
    RAG_AVAILABLE = True
    logger.info("✅ RAG-Anything核心系统已导入")
except ImportError as e:
    RAG_AVAILABLE = False
    logger.warning(f"⚠️ RAG-Anything核心系统导入失败: {e}")
    logger.warning("🔄 将使用模拟模式运行")

# === 完全兼容LightRAG WebUI的数据模型 ===

class LightragNode(BaseModel):
    id: str
    labels: List[str]
    properties: Dict[str, Any]

class LightragEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    properties: Dict[str, Any]

class LightragGraph(BaseModel):
    nodes: List[LightragNode]
    edges: List[LightragEdge]

class LightragStatus(BaseModel):
    status: str = "healthy"
    working_directory: str
    input_directory: str = ""
    configuration: Dict[str, Any]
    pipeline_busy: bool = False
    core_version: Optional[str] = "1.2.7"
    api_version: Optional[str] = "1.0.0"
    auth_mode: Optional[str] = "disabled"
    webui_title: Optional[str] = "RAG-Anything WebUI"
    webui_description: Optional[str] = "多模态RAG系统Web界面"

class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"  # naive, local, global, hybrid, mix, bypass
    only_need_context: Optional[bool] = False
    only_need_prompt: Optional[bool] = False
    response_type: Optional[str] = "Multiple Paragraphs"
    stream: Optional[bool] = False
    top_k: Optional[int] = 10
    chunk_top_k: Optional[int] = 5
    max_entity_tokens: Optional[int] = 2000
    max_relation_tokens: Optional[int] = 2000
    max_total_tokens: Optional[int] = 8000
    conversation_history: Optional[List[Dict[str, str]]] = None
    history_turns: Optional[int] = 3
    user_prompt: Optional[str] = None
    enable_rerank: Optional[bool] = True

class QueryResponse(BaseModel):
    response: str

class DocActionResponse(BaseModel):
    status: str  # success, partial_success, failure, duplicated
    message: str
    track_id: Optional[str] = None

class DocStatusResponse(BaseModel):
    id: str
    content_summary: str
    content_length: int
    status: str  # pending, processing, processed, failed
    created_at: str
    updated_at: str
    track_id: Optional[str] = None
    chunks_count: Optional[int] = 0
    error_msg: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    file_path: str

class DocsStatusesResponse(BaseModel):
    statuses: Dict[str, List[DocStatusResponse]]

class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: str
    request_id: str

# === FastAPI应用配置 ===

app = FastAPI(
    title="RAG-Anything Web API - LightRAG Compatible",
    description="完全兼容LightRAG WebUI的多模态RAG系统Web接口",
    version="1.2.7"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局RAG实例
rag_instance: Optional[RAGAnything] = None

# === 增强的错误处理 ===

class APIError(Exception):
    def __init__(self, message: str, status_code: int = 500, detail: str = ""):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)

@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    """自定义API错误处理器"""
    request_id = str(uuid.uuid4())
    
    logger.error(
        "API错误",
        error=exc.message,
        detail=exc.detail,
        status_code=exc.status_code,
        request_id=request_id,
        path=request.url.path,
        method=request.method
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.message,
            detail=exc.detail,
            timestamp=datetime.now().isoformat(),
            request_id=request_id
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理器"""
    request_id = str(uuid.uuid4())
    
    logger.error(
        "未处理的异常",
        error=str(exc),
        traceback=traceback.format_exc(),
        request_id=request_id,
        path=request.url.path,
        method=request.method
    )
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Server Error",
            detail=str(exc),
            timestamp=datetime.now().isoformat(),
            request_id=request_id
        ).dict()
    )

# === RAG实例管理 ===

async def get_rag_instance() -> RAGAnything:
    """获取RAG实例，带完整错误处理"""
    global rag_instance
    
    if not RAG_AVAILABLE:
        raise APIError("RAG核心系统不可用", 503, "RAG-Anything导入失败")
    
    if rag_instance is None:
        try:
            logger.info("正在初始化RAG实例...")
            
            # 初始化RAG配置
            config = RAGAnythingConfig(
                working_dir="/home/ragsvr/projects/ragsystem/RAG-Anything/rag_storage",
                parser="mineru",
                parse_method="auto",
                enable_image_processing=True,
                enable_table_processing=True,
                enable_equation_processing=True,
            )
            
            # 检查DeepSeek API配置
            deepseek_api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_BINDING_API_KEY")
            deepseek_base_url = os.getenv("LLM_BINDING_HOST", "https://api.deepseek.com/v1")
            
            if not deepseek_api_key:
                raise APIError("未配置LLM API密钥", 500, "请设置DEEPSEEK_API_KEY环境变量")
            
            logger.info("🚀 使用DeepSeek API作为LLM后端")
            
            # 配置DeepSeek API
            os.environ["OPENAI_API_KEY"] = deepseek_api_key
            os.environ["OPENAI_BASE_URL"] = deepseek_base_url
            
            # LLM函数
            def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
                return openai_complete_if_cache(
                    "deepseek-chat",
                    prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages,
                    api_key=deepseek_api_key,
                    base_url=deepseek_base_url,
                    **kwargs,
                )

            # Vision模型函数
            def vision_model_func(prompt, system_prompt=None, history_messages=[], image_data=None, messages=None, **kwargs):
                if messages:
                    return openai_complete_if_cache(
                        "deepseek-vl", "", None, [], messages=messages,
                        api_key=deepseek_api_key, base_url=deepseek_base_url, **kwargs
                    )
                elif image_data:
                    return openai_complete_if_cache(
                        "deepseek-vl", "", None, [],
                        messages=[
                            {"role": "system", "content": system_prompt} if system_prompt else None,
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                                ],
                            }
                        ],
                        api_key=deepseek_api_key, base_url=deepseek_base_url, **kwargs
                    )
                else:
                    return llm_model_func(prompt, system_prompt, history_messages, **kwargs)

            # 嵌入函数
            try:
                sys.path.append("/home/ragsvr/projects/ragsystem/RAG-Anything")
                from simple_qwen_embed import qwen_embed
                embedding_func = EmbeddingFunc(
                    embedding_dim=1024,
                    max_token_size=512,
                    func=qwen_embed,
                )
                logger.info("✅ 使用本地Qwen3嵌入模型")
            except ImportError:
                logger.warning("⚠️ qwen_embed不可用，使用OpenAI嵌入")
                embedding_func = EmbeddingFunc(
                    embedding_dim=1536,
                    max_token_size=8192,
                    func=openai_embed,
                )
            
            # 创建RAG实例
            rag_instance = RAGAnything(
                config=config,
                llm_model_func=llm_model_func,
                vision_model_func=vision_model_func,
                embedding_func=embedding_func
            )
            
            # 确保RAG已初始化
            await rag_instance._ensure_lightrag_initialized()
            
            logger.info("✅ RAG实例初始化完成")
            
        except Exception as e:
            logger.error(f"❌ RAG实例初始化失败: {e}")
            raise APIError(f"RAG实例初始化失败: {str(e)}", 500, traceback.format_exc())
    
    return rag_instance

# === 完全兼容LightRAG WebUI的API接口 ===

@app.get("/health", response_model=LightragStatus)
async def health_check():
    """健康检查端点 - 完全兼容LightRAG WebUI"""
    try:
        rag = await get_rag_instance()
        
        working_dir = "/home/ragsvr/projects/ragsystem/RAG-Anything/rag_storage"
        if hasattr(rag, 'config') and hasattr(rag.config, 'working_dir'):
            working_dir = rag.config.working_dir
        
        configuration = {
            "llm_binding": "deepseek",
            "llm_binding_host": os.getenv("LLM_BINDING_HOST", "https://api.deepseek.com/v1"),
            "llm_model": "deepseek-chat",
            "embedding_binding": "qwen_local",
            "embedding_binding_host": "local",
            "embedding_model": "Qwen3-Embedding-0.6B",
            "max_tokens": 4000,
            "kv_storage": "json",
            "doc_status_storage": "json", 
            "graph_storage": "json",
            "vector_storage": "json",
            "workspace": working_dir,
            "summary_language": "zh_CN",
            "force_llm_summary_on_merge": True,
            "max_parallel_insert": 4,
            "max_async": 16,
            "embedding_func_max_async": 16,
            "embedding_batch_num": 32,
            "cosine_threshold": 0.2,
            "min_rerank_score": 0.0,
            "related_chunk_number": 10
        }
        
        return LightragStatus(
            status="healthy",
            working_directory=working_dir,
            input_directory=working_dir,
            configuration=configuration,
            pipeline_busy=False,
            core_version="1.2.7",
            api_version="1.0.0", 
            auth_mode="disabled",
            webui_title="RAG-Anything WebUI",
            webui_description="多模态RAG系统Web界面"
        )
    except APIError:
        raise
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise APIError("健康检查失败", 503, str(e))

@app.get("/documents", response_model=DocsStatusesResponse)
async def get_documents():
    """获取文档状态 - 完全兼容LightRAG WebUI格式"""
    try:
        rag_storage_path = "/home/ragsvr/projects/ragsystem/RAG-Anything/rag_storage"
        doc_status_file = os.path.join(rag_storage_path, "kv_store_doc_status.json")
        
        processed_docs = []
        pending_docs = []
        processing_docs = []
        failed_docs = []
        
        if os.path.exists(doc_status_file):
            try:
                with open(doc_status_file, 'r', encoding='utf-8') as f:
                    doc_statuses = json.load(f)
                
                for doc_id, doc_info in doc_statuses.items():
                    doc_data = DocStatusResponse(
                        id=doc_id,
                        content_summary=doc_info.get("content_summary", "")[:200] + "..." if len(doc_info.get("content_summary", "")) > 200 else doc_info.get("content_summary", ""),
                        content_length=doc_info.get("content_length", 0),
                        status=doc_info.get("status", "unknown"),
                        created_at=doc_info.get("created_at", ""),
                        updated_at=doc_info.get("updated_at", ""),
                        track_id=doc_info.get("track_id", ""),
                        chunks_count=doc_info.get("chunks_count", 0),
                        file_path=doc_info.get("file_path", ""),
                        metadata=doc_info.get("metadata", {})
                    )
                    
                    status = doc_info.get("status", "unknown")
                    if status == "processed":
                        processed_docs.append(doc_data)
                    elif status == "pending":
                        pending_docs.append(doc_data)
                    elif status == "processing":
                        processing_docs.append(doc_data)
                    elif status == "failed":
                        failed_docs.append(doc_data)
                
                logger.info(f"从数据库加载文档: processed={len(processed_docs)}, pending={len(pending_docs)}, processing={len(processing_docs)}, failed={len(failed_docs)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析文档状态文件失败: {e}")
                raise APIError("文档状态数据损坏", 500, str(e))
        else:
            logger.warning(f"文档状态文件不存在: {doc_status_file}")
        
        return DocsStatusesResponse(
            statuses={
                "processed": processed_docs,
                "pending": pending_docs,
                "processing": processing_docs,
                "failed": failed_docs
            }
        )
    except APIError:
        raise
    except Exception as e:
        logger.error(f"获取文档失败: {e}")
        raise APIError("获取文档列表失败", 500, str(e))

@app.post("/documents/upload", response_model=DocActionResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """文档上传 - 完全兼容LightRAG WebUI格式"""
    try:
        # 验证文件
        if not file.filename:
            raise APIError("文件名不能为空", 400)
        
        if file.size and file.size > 100 * 1024 * 1024:  # 100MB限制
            raise APIError("文件大小超过100MB限制", 400)
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        track_id = f"upload_{int(datetime.now().timestamp())}_{hashlib.md5(file.filename.encode()).hexdigest()[:8]}"
        
        # 添加后台处理任务
        background_tasks.add_task(
            process_document_background,
            tmp_file_path,
            file.filename,
            track_id
        )
        
        logger.info(f"文件上传成功: {file.filename}, track_id: {track_id}")
        
        return DocActionResponse(
            status="success",
            message=f"文件 {file.filename} 上传成功，正在处理中...",
            track_id=track_id
        )
    except APIError:
        raise
    except Exception as e:
        logger.error(f"文档上传失败: {e}")
        raise APIError("文档上传失败", 500, str(e))

async def process_document_background(file_path: str, filename: str, track_id: str):
    """后台处理文档 - 增强错误处理"""
    try:
        logger.info(f"开始处理文档: {filename}")
        
        rag = await get_rag_instance()
        
        # 处理文档
        output_dir = "/home/ragsvr/projects/ragsystem/web-api/output"
        os.makedirs(output_dir, exist_ok=True)
        
        await rag.process_document_complete(
            file_path=file_path,
            output_dir=output_dir, 
            parse_method="auto"
        )
        
        logger.info(f"文档处理完成: {filename}")
        
    except Exception as e:
        logger.error(f"文档处理失败: {filename}, 错误: {e}")
        
        # 更新文档状态为失败
        try:
            rag_storage_path = "/home/ragsvr/projects/ragsystem/RAG-Anything/rag_storage"
            doc_status_file = os.path.join(rag_storage_path, "kv_store_doc_status.json")
            
            doc_statuses = {}
            if os.path.exists(doc_status_file):
                with open(doc_status_file, 'r', encoding='utf-8') as f:
                    doc_statuses = json.load(f)
            
            doc_statuses[track_id] = {
                "status": "failed",
                "error_msg": str(e),
                "file_path": filename,
                "updated_at": datetime.now().isoformat()
            }
            
            with open(doc_status_file, 'w', encoding='utf-8') as f:
                json.dump(doc_statuses, f, ensure_ascii=False, indent=2)
                
        except Exception as status_error:
            logger.error(f"更新文档状态失败: {status_error}")
    
    finally:
        # 清理临时文件
        try:
            os.unlink(file_path)
        except:
            pass

@app.post("/query", response_model=QueryResponse)
async def query_rag(query_request: QueryRequest):
    """RAG查询接口 - 完全兼容LightRAG WebUI"""
    try:
        if not query_request.query.strip():
            raise APIError("查询内容不能为空", 400)
        
        rag = await get_rag_instance()
        
        logger.info(f"执行查询: {query_request.query[:50]}..., 模式: {query_request.mode}")
        
        # 执行查询
        result = await rag.aquery(
            query_request.query,
            mode=query_request.mode,
            vlm_enhanced=False
        )
        
        logger.info("查询执行成功")
        
        return QueryResponse(response=result)
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"RAG查询失败: {e}")
        raise APIError("查询执行失败", 500, str(e))

@app.post("/query/stream")
async def query_stream(query_request: QueryRequest):
    """流式查询接口 - 兼容LightRAG WebUI"""
    try:
        if not query_request.query.strip():
            raise APIError("查询内容不能为空", 400)
        
        async def generate():
            try:
                rag = await get_rag_instance()
                
                # 为流式响应模拟分块输出
                result = await rag.aquery(
                    query_request.query,
                    mode=query_request.mode,
                    vlm_enhanced=False
                )
                
                # 将结果分成小块流式输出
                words = result.split()
                chunk_size = 5  # 每次输出5个词
                
                for i in range(0, len(words), chunk_size):
                    chunk = " ".join(words[i:i+chunk_size])
                    if i + chunk_size < len(words):
                        chunk += " "
                    
                    yield f'{{"response": "{chunk}"}}\n'
                    await asyncio.sleep(0.1)  # 模拟流式延迟
                
            except Exception as e:
                logger.error(f"流式查询失败: {e}")
                yield f'{{"error": "{str(e)}"}}\n'
        
        return StreamingResponse(
            generate(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache"}
        )
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"流式查询失败: {e}")
        raise APIError("流式查询失败", 500, str(e))

@app.get("/graphs")
async def get_graphs(label: str = "", max_depth: int = 3, max_nodes: int = 100):
    """获取知识图谱 - 兼容LightRAG WebUI"""
    try:
        # 模拟图谱数据，实际应该从RAG系统获取
        nodes = [
            LightragNode(
                id=f"node_{i}",
                labels=["Entity"],
                properties={"name": f"实体{i}", "type": "concept"}
            ) for i in range(min(max_nodes, 10))
        ]
        
        edges = [
            LightragEdge(
                id=f"edge_{i}",
                source=f"node_{i}",
                target=f"node_{i+1}",
                type="RELATED_TO",
                properties={"weight": 0.8}
            ) for i in range(min(len(nodes)-1, 9))
        ]
        
        return LightragGraph(nodes=nodes, edges=edges)
        
    except Exception as e:
        logger.error(f"获取图谱失败: {e}")
        raise APIError("获取知识图谱失败", 500, str(e))

@app.get("/graph/label/list")
async def get_graph_labels():
    """获取图谱标签列表 - 兼容LightRAG WebUI"""
    try:
        # 模拟标签数据
        return ["Entity", "Concept", "Person", "Organization", "Event"]
    except Exception as e:
        logger.error(f"获取图谱标签失败: {e}")
        raise APIError("获取图谱标签失败", 500, str(e))

@app.get("/")
async def root():
    """API根路径"""
    return {
        "message": "RAG-Anything Web API - LightRAG Compatible",
        "version": "1.2.7",
        "docs": "/docs",
        "health": "/health",
        "compatibility": "LightRAG WebUI Compatible"
    }

if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 启动RAG-Anything Web API服务器 (LightRAG兼容版)")
    
    uvicorn.run(
        "main_fixed:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )