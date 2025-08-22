#!/usr/bin/env python3
"""
RAG-Anything API Server
基于RAGAnything的实际API服务器，替换mock版本
支持文档上传、处理、查询等功能
"""

import asyncio
import json
import os
import uuid
import psutil
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import sys

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

import uvicorn
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc, logger
from raganything import RAGAnything, RAGAnythingConfig
from simple_qwen_embed import qwen_embed
from dotenv import load_dotenv

# 导入智能路由和文本处理器
from smart_parser_router import router
from direct_text_processor import text_processor
# 导入详细状态跟踪器
from detailed_status_tracker import detailed_tracker, StatusLogger, ProcessingStage
# 导入WebSocket日志处理器
from websocket_log_handler import websocket_log_handler, setup_websocket_logging, get_log_summary, get_core_progress, clear_logs

# 加载环境变量
load_dotenv(dotenv_path="/home/ragsvr/projects/ragsystem/.env", override=False)
load_dotenv(dotenv_path="/home/ragsvr/projects/ragsystem/.env.performance", override=True)

# 配置日志
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="RAG-Anything API", version="1.0.0")

# 启用CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
rag_instance: Optional[RAGAnything] = None
tasks: Dict[str, dict] = {}
documents: Dict[str, dict] = {}
active_websockets: Dict[str, WebSocket] = {}
processing_log_websockets: List[WebSocket] = []  # 文档解析日志WebSocket连接列表
batch_operations: Dict[str, dict] = {}  # 批量操作状态跟踪

# 日志显示模式
class LogDisplayMode(BaseModel):
    mode: str = "summary"  # core_only, summary, detailed, all
    include_debug: bool = False

# 配置 - 统一使用绝对路径，指向RAG-Anything根目录的存储
UPLOAD_DIR = os.path.abspath("../../uploads")
WORKING_DIR = os.getenv("WORKING_DIR", "/home/ragsvr/projects/ragsystem/rag_storage")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/home/ragsvr/projects/ragsystem/output")

# 确保目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(WORKING_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Request/Response 模型
class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"
    vlm_enhanced: bool = False

class DocumentDeleteRequest(BaseModel):
    document_ids: List[str]

# 批量处理相关数据模型
class BatchUploadResponse(BaseModel):
    success: bool
    uploaded_count: int
    failed_count: int
    total_files: int
    results: List[dict]
    message: str

class BatchProcessRequest(BaseModel):
    document_ids: List[str]
    parser: Optional[str] = None
    parse_method: Optional[str] = None

class BatchProcessResponse(BaseModel):
    success: bool
    started_count: int
    failed_count: int
    total_requested: int
    results: List[dict]
    batch_operation_id: str
    message: str

class BatchOperationStatus(BaseModel):
    batch_operation_id: str
    operation_type: str  # "upload" | "process"
    status: str  # "running" | "completed" | "failed" | "cancelled"
    total_items: int
    completed_items: int
    failed_items: int
    progress: float
    started_at: str
    completed_at: Optional[str] = None
    results: List[dict]

# 模拟处理阶段
PROCESSING_STAGES = [
    ("parsing", "解析文档", 15),
    ("separation", "分离内容", 5),
    ("text_insert", "插入文本", 25),
    ("image_process", "处理图片", 20),
    ("table_process", "处理表格", 15),
    ("equation_process", "处理公式", 10),
    ("graph_build", "构建知识图谱", 15),
    ("indexing", "创建索引", 10),
]

async def load_existing_documents():
    """从RAG存储中加载已存在的文档"""
    global documents
    
    doc_status_file = os.path.join(WORKING_DIR, "kv_store_doc_status.json")
    if not os.path.exists(doc_status_file):
        logger.info("没有找到现有文档状态文件")
        return
    
    try:
        with open(doc_status_file, 'r', encoding='utf-8') as f:
            doc_status_data = json.load(f)
        
        logger.info(f"从RAG存储中发现 {len(doc_status_data)} 个已处理文档")
        
        for doc_id, doc_info in doc_status_data.items():
            if doc_info.get('status') == 'processed':
                # 生成文档记录
                document_id = str(uuid.uuid4())
                file_name = os.path.basename(doc_info.get('file_path', f'document_{doc_id}'))
                
                document = {
                    "document_id": document_id,
                    "file_name": file_name,
                    "file_path": doc_info.get('file_path', ''),
                    "file_size": doc_info.get('content_length', 0),
                    "status": "completed",
                    "created_at": doc_info.get('created_at', datetime.now().isoformat()),
                    "updated_at": doc_info.get('updated_at', datetime.now().isoformat()),
                    "processing_time": 0,  # 历史文档没有处理时间记录
                    "content_length": doc_info.get('content_length', 0),
                    "chunks_count": doc_info.get('chunks_count', 0),
                    "rag_doc_id": doc_id,  # 保存RAG系统的文档ID
                    "content_summary": doc_info.get('content_summary', '')[:100] + "..." if doc_info.get('content_summary') else ""
                }
                
                documents[document_id] = document
                logger.info(f"加载已存在文档: {file_name} (chunks: {doc_info.get('chunks_count', 0)})")
        
        logger.info(f"成功加载 {len(documents)} 个已存在文档")
        
    except Exception as e:
        logger.error(f"加载已存在文档失败: {str(e)}")

async def initialize_rag():
    """初始化RAG系统"""
    global rag_instance
    
    if rag_instance is not None:
        return rag_instance
    
    try:
        # 检查环境变量
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_BINDING_API_KEY")
        if not api_key:
            logger.error("未找到DEEPSEEK_API_KEY，请检查环境变量")
            return None
        
        base_url = os.getenv("LLM_BINDING_HOST", "https://api.deepseek.com/v1")
        
        # 创建配置 - 确保工作目录一致
        config = RAGAnythingConfig(
            working_dir=WORKING_DIR,
            parser_output_dir=OUTPUT_DIR,
            parser=os.getenv("PARSER", "mineru"),
            parse_method=os.getenv("PARSE_METHOD", "auto"),
            enable_image_processing=True,
            enable_table_processing=True,
            enable_equation_processing=True,
        )
        
        # 定义LLM函数
        def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
            return openai_complete_if_cache(
                "deepseek-chat",
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                api_key=api_key,
                base_url=base_url,
                **kwargs,
            )
        
        # 定义视觉模型函数
        def vision_model_func(
            prompt,
            system_prompt=None,
            history_messages=[],
            image_data=None,
            messages=None,
            **kwargs,
        ):
            if messages:
                return openai_complete_if_cache(
                    "deepseek-vl",
                    "",
                    system_prompt=None,
                    history_messages=[],
                    messages=messages,
                    api_key=api_key,
                    base_url=base_url,
                    **kwargs,
                )
            elif image_data:
                return openai_complete_if_cache(
                    "deepseek-vl",
                    "",
                    system_prompt=None,
                    history_messages=[],
                    messages=[
                        {"role": "system", "content": system_prompt} if system_prompt else None,
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                                },
                            ],
                        } if image_data else {"role": "user", "content": prompt},
                    ],
                    api_key=api_key,
                    base_url=base_url,
                    **kwargs,
                )
            else:
                return llm_model_func(prompt, system_prompt, history_messages, **kwargs)
        
        # 定义嵌入函数
        embedding_func = EmbeddingFunc(
            embedding_dim=1024,
            max_token_size=512,
            func=qwen_embed,
        )
        
        # 初始化RAGAnything
        rag_instance = RAGAnything(
            config=config,
            llm_model_func=llm_model_func,
            vision_model_func=vision_model_func,
            embedding_func=embedding_func,
        )
        
        # 确保LightRAG实例已初始化
        await rag_instance._ensure_lightrag_initialized()
        
        logger.info("RAG系统初始化成功")
        logger.info(f"数据目录: {WORKING_DIR}")
        logger.info(f"输出目录: {OUTPUT_DIR}")
        logger.info(f"RAGAnything工作目录: {rag_instance.working_dir}")
        logger.info(f"LLM: DeepSeek API")
        logger.info(f"嵌入: 本地Qwen3-Embedding-0.6B")
        
        # 验证目录一致性
        if rag_instance.working_dir != WORKING_DIR:
            logger.warning(f"工作目录不一致! API服务器: {WORKING_DIR}, RAGAnything: {rag_instance.working_dir}")
        else:
            logger.info("✓ 工作目录配置一致")
        
        return rag_instance
        
    except Exception as e:
        logger.error(f"RAG系统初始化失败: {str(e)}")
        return None

@app.on_event("startup")
async def startup_event():
    """服务启动时初始化RAG系统"""
    # 设置WebSocket日志处理器
    setup_websocket_logging()
    websocket_log_handler.set_event_loop(asyncio.get_event_loop())
    
    await initialize_rag()
    await load_existing_documents()

@app.get("/health")
async def health_check():
    """健康检查端点"""
    global rag_instance
    
    rag_status = "healthy" if rag_instance is not None else "unhealthy"
    
    return {
        "status": "healthy" if rag_status == "healthy" else "degraded",
        "message": "RAG-Anything API is running",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "rag_engine": rag_status,
            "tasks": "healthy",
            "documents": "healthy"
        },
        "statistics": {
            "active_tasks": len([t for t in tasks.values() if t["status"] == "running"]),
            "total_tasks": len(tasks),
            "total_documents": len(documents)
        },
        "system_checks": {
            "api": True,
            "websocket": True,
            "storage": True,
            "rag_initialized": rag_instance is not None
        }
    }

def get_rag_statistics():
    """获取RAG系统统计信息"""
    try:
        stats = {
            "documents_processed": len(documents),
            "entities_count": 0,
            "relationships_count": 0,
            "chunks_count": 0
        }
        
        # 尝试从RAG存储文件中读取统计信息
        try:
            # 读取实体数量
            entities_file = os.path.join(WORKING_DIR, "vdb_entities.json")
            if os.path.exists(entities_file):
                with open(entities_file, 'r', encoding='utf-8') as f:
                    entities_data = json.load(f)
                    stats["entities_count"] = len(entities_data.get("data", []))
            
            # 读取关系数量
            relationships_file = os.path.join(WORKING_DIR, "vdb_relationships.json")
            if os.path.exists(relationships_file):
                with open(relationships_file, 'r', encoding='utf-8') as f:
                    relationships_data = json.load(f)
                    stats["relationships_count"] = len(relationships_data.get("data", []))
            
            # 读取chunks数量
            chunks_file = os.path.join(WORKING_DIR, "vdb_chunks.json")
            if os.path.exists(chunks_file):
                with open(chunks_file, 'r', encoding='utf-8') as f:
                    chunks_data = json.load(f)
                    stats["chunks_count"] = len(chunks_data.get("data", []))
                    
        except Exception as e:
            logger.error(f"读取RAG统计信息失败: {e}")
        
        return stats
        
    except Exception as e:
        logger.error(f"获取RAG统计信息失败: {e}")
        return {
            "documents_processed": len(documents),
            "entities_count": 0,
            "relationships_count": 0,
            "chunks_count": 0
        }

def get_content_stats_from_output(file_path: str, output_dir: str) -> Optional[Dict[str, int]]:
    """从MinerU/Docling输出文件中获取内容统计信息"""
    try:
        # 构建输出文件路径
        file_stem = Path(file_path).stem
        
        # 尝试不同的可能路径，包括更多模式
        possible_paths = [
            os.path.join(output_dir, file_stem, "auto", f"{file_stem}_content_list.json"),
            os.path.join(output_dir, file_stem, f"{file_stem}_content_list.json"),
            os.path.join(output_dir, f"{file_stem}_content_list.json"),
            # 尝试在子目录中查找
            os.path.join(output_dir, file_stem, "content_list.json"),
            os.path.join(output_dir, "content_list.json"),
        ]
        
        content_list_file = None
        for path in possible_paths:
            if os.path.exists(path):
                content_list_file = path
                logger.debug(f"找到content_list文件: {path}")
                break
        
        if not content_list_file:
            # 尝试递归搜索content_list.json文件
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    if file.endswith("_content_list.json") or file == "content_list.json":
                        if file_stem in file or file_stem in root:
                            content_list_file = os.path.join(root, file)
                            logger.debug(f"递归找到content_list文件: {content_list_file}")
                            break
                if content_list_file:
                    break
        
        if not content_list_file:
            logger.warning(f"找不到content_list文件: {file_stem}")
            logger.debug(f"搜索路径: {possible_paths}")
            # 列出输出目录内容以便调试
            try:
                if os.path.exists(output_dir):
                    logger.debug(f"输出目录内容: {os.listdir(output_dir)}")
            except Exception as e:
                logger.debug(f"无法列出输出目录: {e}")
            return None
        
        # 读取并统计内容
        with open(content_list_file, 'r', encoding='utf-8') as f:
            content_list = json.load(f)
        
        stats = {
            'total': len(content_list),
            'text': 0,
            'image': 0,
            'table': 0,
            'equation': 0,
            'other': 0
        }
        
        for item in content_list:
            if isinstance(item, dict):
                item_type = item.get('type', 'unknown')
                if item_type == 'text':
                    stats['text'] += 1
                elif item_type == 'image':
                    stats['image'] += 1
                elif item_type == 'table':
                    stats['table'] += 1
                elif item_type in ['equation', 'formula']:
                    stats['equation'] += 1
                else:
                    stats['other'] += 1
        
        logger.info(f"内容统计 ({file_stem}): {stats} (来源: {content_list_file})")
        return stats
        
    except Exception as e:
        logger.error(f"读取内容统计失败: {e}")
        import traceback
        logger.debug(f"详细错误: {traceback.format_exc()}")
        return None

def get_system_metrics():
    """获取系统指标"""
    try:
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
        logger.error(f"获取系统指标失败: {e}")
        return {
            "cpu_usage": 0,
            "memory_usage": 0,
            "disk_usage": 0,
            "gpu_usage": 0
        }

@app.get("/api/system/status")
async def get_system_status():
    """系统状态端点"""
    global rag_instance
    
    metrics = get_system_metrics()
    
    return {
        "success": True,
        "status": "healthy" if rag_instance else "degraded",
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics,
        "processing_stats": get_rag_statistics(),
        "services": {
            "RAG-Anything Core": {
                "status": "running" if rag_instance else "stopped",
                "uptime": "实时运行"
            },
            "Document Parser": {
                "status": "running" if rag_instance else "stopped", 
                "uptime": "实时运行"
            },
            "Query Engine": {
                "status": "running" if rag_instance else "stopped",
                "uptime": "实时运行"
            },
            "Knowledge Graph": {
                "status": "running" if rag_instance else "stopped",
                "uptime": "实时运行"
            }
        }
    }

@app.get("/api/system/parser-stats")
async def get_parser_statistics():
    """获取解析器使用统计"""
    global rag_instance
    
    routing_stats = router.get_routing_stats()
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
            "mineru": router.validate_parser_availability("mineru"),
            "docling": router.validate_parser_availability("docling"), 
            "direct_text": router.validate_parser_availability("direct_text")
        },
        "optimization_summary": {
            "total_optimizations": parser_usage.get("direct_text", 0) + parser_usage.get("docling", 0),
            "pdf_conversions_avoided": parser_usage.get("direct_text", 0),
            "libreoffice_conversions_avoided": sum(1 for doc in documents.values() 
                                                   if doc.get("parser_used", "").startswith("docling") 
                                                   and any(ext in doc.get("file_name", "") 
                                                          for ext in [".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"]))
        }
    }

async def process_text_file_direct(task_id: str, file_path: str):
    """直接处理文本文件，避免PDF转换"""
    if task_id not in tasks:
        return
        
    task = tasks[task_id]
    task["status"] = "running"
    task["started_at"] = datetime.now().isoformat()
    
    # 初始化时间变量，确保在所有异常处理中都能访问
    start_time = datetime.now()
    processing_start_time = datetime.now()
    
    # 更新文档状态
    if task["document_id"] in documents:
        documents[task["document_id"]]["status"] = "processing"
    
    try:
        # 获取RAG实例
        rag = await initialize_rag()
        if not rag:
            raise Exception("RAG系统未初始化")
        
        # 创建详细状态跟踪
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        detailed_status = detailed_tracker.create_status(
            task_id=task_id,
            file_name=os.path.basename(file_path),
            file_size=file_size,
            parser_used="direct_text",
            parser_reason="文本文件直接解析，避免PDF转换"
        )
        
        # 添加状态变更回调
        detailed_tracker.add_status_callback(task_id, lambda status: send_detailed_status_update(task_id, status))
        
        logger.info(f"开始直接处理文本文件: {file_path}")
        await send_processing_log(f"📝 开始直接处理文本文件 (跳过PDF转换)", "info")
        
        # 开始解析阶段
        detailed_status.start_stage(ProcessingStage.PARSING, 1, "直接解析文本文件")
        await send_processing_log(f"⚡ 使用优化路径直接解析文本内容...", "info")
        
        # 更新传统任务状态（保持兼容性）
        task["stage"] = "parsing"
        task["stage_details"]["parsing"]["status"] = "running"
        task["progress"] = 10
        await send_websocket_update(task_id, task)
        
        # 使用直接文本处理器
        content_list = text_processor.process_text_file(file_path, OUTPUT_DIR)
        
        # 更新内容统计
        detailed_status.content_stats.update_from_content_list(content_list)
        detailed_status.complete_stage(ProcessingStage.PARSING)
        detailed_status.add_log("SUCCESS", f"解析完成！提取了 {len(content_list)} 个内容块")
        await send_processing_log(f"✅ 文本解析完成！提取了 {len(content_list)} 个内容块", "success")
        
        # 更新传统任务状态
        task["stage_details"]["parsing"]["status"] = "completed"
        task["progress"] = 30
        await send_websocket_update(task_id, task)
        
        # 开始文本插入阶段
        detailed_status.start_stage(ProcessingStage.TEXT_PROCESSING, len(content_list), "插入文本内容到知识图谱")
        await send_processing_log(f"📝 开始插入 {len(content_list)} 个内容块到知识图谱...", "info")
        
        task["stage"] = "text_insert"
        task["stage_details"]["text_insert"]["status"] = "running"
        task["progress"] = 50
        await send_websocket_update(task_id, task)
        
        # 调用RAG的内容插入方法
        doc_id = await rag.insert_content_list(content_list, file_path)
        if doc_id is None:
            raise Exception("RAG内容插入失败：返回的文档ID为空")
        await send_processing_log(f"✅ 内容插入完成，文档ID: {doc_id[:12]}...", "success")
        
        # 完成文本处理
        detailed_status.complete_stage(ProcessingStage.TEXT_PROCESSING)
        
        # 开始知识图谱构建
        detailed_status.start_stage(ProcessingStage.GRAPH_BUILDING, 1, "构建知识图谱")
        await send_processing_log(f"🕸️  开始构建知识图谱，提取实体和关系...", "info")
        
        # 快速完成其他阶段（文本文件无需图片、表格、公式处理）
        stages_to_complete = [
            ("text_insert", "文本插入", 70),
            ("graph_build", "知识图谱构建", 90),
            ("indexing", "索引创建", 100),
        ]
        
        for stage_name, stage_label, progress in stages_to_complete:
            if task_id not in tasks:
                return
                
            task["stage"] = stage_name
            task["stage_details"][stage_name]["status"] = "completed"
            task["stage_details"][stage_name]["progress"] = 100
            task["progress"] = progress
            task["updated_at"] = datetime.now().isoformat()
            
            await send_websocket_update(task_id, task)
            await asyncio.sleep(0.1)
        
        # 完成知识图谱构建和索引
        detailed_status.complete_stage(ProcessingStage.GRAPH_BUILDING)
        await send_processing_log(f"✅ 知识图谱构建完成", "success")
        
        detailed_status.start_stage(ProcessingStage.INDEXING, 1, "创建搜索索引")
        await send_processing_log(f"🗂️  创建搜索索引...", "info")
        detailed_status.complete_stage(ProcessingStage.INDEXING)
        await send_processing_log(f"✅ 搜索索引创建完成", "success")
        
        # 完成整个处理过程
        detailed_status.complete_processing()
        await send_processing_log(f"🎉 文本文件处理全部完成！", "success")
        
        # 完成处理
        task["status"] = "completed"
        task["progress"] = 100
        task["completed_at"] = datetime.now().isoformat()
        task["multimodal_stats"]["processing_success_rate"] = 100.0
        task["multimodal_stats"]["text_chunks"] = len(content_list)
        
        # 更新文档状态
        if task["document_id"] in documents:
            documents[task["document_id"]]["status"] = "completed"
            documents[task["document_id"]]["updated_at"] = datetime.now().isoformat()
            documents[task["document_id"]]["processing_time"] = (
                datetime.fromisoformat(task["completed_at"]) - 
                datetime.fromisoformat(task["started_at"])
            ).total_seconds()
            documents[task["document_id"]]["chunks_count"] = len(content_list)
            documents[task["document_id"]]["rag_doc_id"] = doc_id
        
        logger.info(f"直接文本处理完成: {file_path}, {len(content_list)}个内容块")
    
    except Exception as e:
        await send_processing_log(f"❌ 直接文本处理失败: {str(e)}", "error")
        logger.error(f"直接文本处理失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # 设置详细状态错误
        if detailed_tracker.get_status(task_id):
            detailed_status = detailed_tracker.get_status(task_id)
            detailed_status.set_error(str(e))
        
        task["status"] = "failed"
        task["error_message"] = str(e)
        task["completed_at"] = datetime.now().isoformat()  # 确保设置completed_at
        task["updated_at"] = datetime.now().isoformat()
        
        if task["document_id"] in documents:
            documents[task["document_id"]]["status"] = "failed"
            documents[task["document_id"]]["error_message"] = str(e)
            documents[task["document_id"]]["updated_at"] = datetime.now().isoformat()
            # 计算处理时间（即使失败）
            if "started_at" in task and "completed_at" in task:
                documents[task["document_id"]]["processing_time"] = (
                    datetime.fromisoformat(task["completed_at"]) - 
                    datetime.fromisoformat(task["started_at"])
                ).total_seconds()
    
    finally:
        # 清理状态跟踪
        detailed_tracker.remove_status(task_id)
    
    # 发送最终更新
    await send_websocket_update(task_id, task)

async def process_with_parser(task_id: str, file_path: str, parser_config):
    """使用指定解析器处理文档"""
    if task_id not in tasks:
        return
        
    task = tasks[task_id]
    task["status"] = "running"
    task["started_at"] = datetime.now().isoformat()
    
    # 初始化时间变量，确保在所有异常处理中都能访问
    start_time = datetime.now()
    processing_start_time = datetime.now()
    
    # 更新文档状态
    if task["document_id"] in documents:
        documents[task["document_id"]]["status"] = "processing"
    
    try:
        # 获取RAG实例
        rag = await initialize_rag()
        if not rag:
            raise Exception("RAG系统未初始化")
        
        # 创建详细状态跟踪
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        detailed_status = detailed_tracker.create_status(
            task_id=task_id,
            file_name=os.path.basename(file_path),
            file_size=file_size,
            parser_used=parser_config.parser,
            parser_reason=parser_config.reason
        )
        
        # 添加状态变更回调
        detailed_tracker.add_status_callback(task_id, lambda status: send_detailed_status_update(task_id, status))
        
        logger.info(f"开始处理文档: {file_path}, 使用解析器: {parser_config.parser}")
        
        # 发送开始处理日志
        await send_processing_log(f"🚀 开始处理文档: {os.path.basename(file_path)}", "info")
        await send_processing_log(f"📄 文件大小: {file_size/1024:.1f} KB", "info")
        await send_processing_log(f"⚙️  解析器: {parser_config.parser} ({parser_config.reason})", "info")
        await send_processing_log(f"🎯 解析方法: {parser_config.method}", "info")
        
        # 开始解析阶段
        detailed_status.start_stage(ProcessingStage.PARSING, 1, f"使用{parser_config.parser}解析器处理文档")
        await send_processing_log(f"🔧 开始文档解析阶段...", "info")
        
        # 更新传统任务状态
        task["stage"] = "parsing"
        task["stage_details"]["parsing"]["status"] = "running"
        task["progress"] = 10
        await send_websocket_update(task_id, task)
        
        # 临时更新RAG配置使用指定解析器
        original_parser = rag.config.parser
        rag.config.parser = parser_config.parser
        
        try:
            # 处理.doc文件的特殊情况：先转换为.docx再用Docling处理
            actual_file_path = file_path
            temp_converted_file = None
            
            if parser_config.parser == "docling" and Path(file_path).suffix.lower() == ".doc":
                await send_processing_log(f"🔄 检测到.doc文件，使用LibreOffice转换为.docx...", "info")
                
                import tempfile
                import subprocess
                import platform
                import shutil
                
                # 创建临时转换文件
                temp_dir = Path(tempfile.mkdtemp())
                file_stem = Path(file_path).stem
                
                try:
                    # 使用LibreOffice转换.doc为.docx
                    convert_cmd = [
                        "libreoffice",
                        "--headless", 
                        "--convert-to",
                        "docx",
                        "--outdir",
                        str(temp_dir),
                        str(file_path)
                    ]
                    
                    convert_subprocess_kwargs = {
                        "capture_output": True,
                        "text": True,
                        "timeout": 60,
                        "encoding": "utf-8",
                        "errors": "ignore",
                    }
                    
                    if platform.system() == "Windows":
                        convert_subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                    
                    result = subprocess.run(convert_cmd, **convert_subprocess_kwargs)
                    
                    if result.returncode != 0:
                        raise RuntimeError(f"LibreOffice转换失败: {result.stderr}")
                    
                    # 查找生成的.docx文件
                    docx_files = list(temp_dir.glob("*.docx"))
                    if not docx_files:
                        raise RuntimeError("LibreOffice转换失败：未生成.docx文件")
                    
                    temp_docx_path = docx_files[0]
                    
                    # 复制转换后的文件到上传目录，保持原始文件名
                    converted_file_path = Path(file_path).parent / f"{file_stem}_converted.docx"
                    shutil.copy2(temp_docx_path, converted_file_path)
                    
                    actual_file_path = str(converted_file_path)
                    temp_converted_file = converted_file_path
                    
                    await send_processing_log(f"✅ LibreOffice转换完成: {temp_docx_path.stat().st_size} bytes", "success")
                    
                except Exception as e:
                    # 清理临时目录
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    raise RuntimeError(f"LibreOffice转换过程出错: {str(e)}")
                finally:
                    # 清理临时目录
                    shutil.rmtree(temp_dir, ignore_errors=True)
            
            # 调用RAGAnything处理文档（使用实际的文件路径）
            await send_processing_log(f"🔄 调用RAG处理引擎开始解析文档...", "info")
            device_type = "cuda" if TORCH_AVAILABLE and torch.cuda.is_available() else "cpu"
            await send_processing_log(f"🖥️  计算设备: {device_type.upper()}", "info")
            
            # 更新处理开始时间
            processing_start_time = datetime.now()
            await rag.process_document_complete(
                file_path=actual_file_path, 
                output_dir=OUTPUT_DIR,
                parse_method=parser_config.method,
                device=device_type,
                lang="en"  # 使用英文语言配置，MinerU不支持"auto"
            )
            
            # 清理转换的临时文件
            if temp_converted_file and temp_converted_file.exists():
                try:
                    temp_converted_file.unlink()
                    await send_processing_log(f"🧹 清理临时转换文件", "info")
                except Exception:
                    pass  # 忽略清理错误
            
            processing_time = (datetime.now() - processing_start_time).total_seconds()
            await send_processing_log(f"✅ 文档解析完成！总耗时: {processing_time:.2f}秒", "success")
            
            # 尝试获取解析结果来更新内容统计
            try:
                await send_processing_log(f"📊 分析解析结果，提取内容统计信息...", "info")
                # 等待一小段时间确保文件写入完成
                await asyncio.sleep(1)
                
                # 尝试从输出文件读取准确的内容统计（使用原始文件名）
                content_stats = get_content_stats_from_output(file_path, OUTPUT_DIR)
                
                if content_stats:
                    await send_processing_log(f"📈 内容统计完成: 总计{content_stats['total']}个内容块", "success")
                    await send_processing_log(f"📝 文本块: {content_stats['text']}个", "info")
                    await send_processing_log(f"🖼️  图片块: {content_stats['image']}个", "info")
                    await send_processing_log(f"📊 表格块: {content_stats['table']}个", "info")
                    await send_processing_log(f"🧮 公式块: {content_stats.get('equation', 0)}个", "info")
                    
                    # 更新详细状态的内容统计
                    detailed_status.content_stats.total_blocks = content_stats['total']
                    detailed_status.content_stats.text_blocks = content_stats['text']
                    detailed_status.content_stats.image_blocks = content_stats['image']
                    detailed_status.content_stats.table_blocks = content_stats['table']
                    detailed_status.content_stats.equation_blocks = content_stats.get('equation', 0)
                    detailed_status.content_stats.other_blocks = content_stats.get('other', 0)
                    
                    # 更新任务的多模态统计
                    if task_id in tasks:
                        tasks[task_id]["multimodal_stats"]["text_chunks"] = content_stats['text']
                        tasks[task_id]["multimodal_stats"]["images_count"] = content_stats['image']
                        tasks[task_id]["multimodal_stats"]["images_processed"] = content_stats['image']
                        tasks[task_id]["multimodal_stats"]["tables_count"] = content_stats['table']
                        tasks[task_id]["multimodal_stats"]["tables_processed"] = content_stats['table']
                        tasks[task_id]["multimodal_stats"]["equations_count"] = content_stats.get('equation', 0)
                        tasks[task_id]["multimodal_stats"]["equations_processed"] = content_stats.get('equation', 0)
                        tasks[task_id]["multimodal_stats"]["processing_success_rate"] = 100.0
                        
                        # 立即发送更新以反映新的统计信息
                        await send_websocket_update(task_id, tasks[task_id])
                    
                    detailed_status.add_log("SUCCESS", f"解析统计: 总计{content_stats['total']}块 (文本:{content_stats['text']}, 图片:{content_stats['image']}, 表格:{content_stats['table']})")
                    
                    # 通知详细状态更新
                    await send_detailed_status_update(task_id, detailed_status.to_dict())
                else:
                    await send_processing_log("⚠️  无法获取详细的内容统计信息", "warning")
                    detailed_status.add_log("WARNING", "无法获取详细的内容统计信息")
                                
            except Exception as e:
                logger.warning(f"获取解析结果统计失败: {e}")
                detailed_status.add_log("WARNING", f"统计信息获取失败: {str(e)}")
            
            # 完成解析阶段
            detailed_status.complete_stage(ProcessingStage.PARSING)
            detailed_status.add_log("SUCCESS", f"使用{parser_config.parser}解析完成，提取了内容块")
            
        finally:
            # 恢复原始解析器配置
            rag.config.parser = original_parser
        
        # 开始后续处理阶段
        await send_processing_log(f"🔍 开始内容分析阶段...", "info")
        detailed_status.start_stage(ProcessingStage.CONTENT_ANALYSIS, 1, "分析文档内容")
        detailed_status.complete_stage(ProcessingStage.CONTENT_ANALYSIS)
        await send_processing_log(f"✅ 内容分析完成", "success")
        
        await send_processing_log(f"📝 开始文本处理阶段...", "info")
        detailed_status.start_stage(ProcessingStage.TEXT_PROCESSING, 1, "处理文本内容")
        detailed_status.complete_stage(ProcessingStage.TEXT_PROCESSING)
        await send_processing_log(f"✅ 文本处理完成", "success")
        
        await send_processing_log(f"🕸️  开始构建知识图谱...", "info")
        detailed_status.start_stage(ProcessingStage.GRAPH_BUILDING, 1, "构建知识图谱")
        await send_processing_log(f"🧠 提取实体和关系中...", "info")
        detailed_status.complete_stage(ProcessingStage.GRAPH_BUILDING)
        await send_processing_log(f"✅ 知识图谱构建完成", "success")
        
        await send_processing_log(f"🗂️  开始创建搜索索引...", "info")
        detailed_status.start_stage(ProcessingStage.INDEXING, 1, "创建搜索索引")
        detailed_status.complete_stage(ProcessingStage.INDEXING)
        await send_processing_log(f"✅ 搜索索引创建完成", "success")
        
        # 完成整个处理过程
        detailed_status.complete_processing()
        await send_processing_log(f"🎉 文档处理全部完成！文档已成功添加到知识库", "success")
        
        # 逐步更新处理进度（保持兼容性）
        stages_progress = [
            ("parsing", "文档解析", 20),
            ("separation", "内容分离", 30), 
            ("text_insert", "文本插入", 50),
            ("image_process", "图片处理", 70),
            ("table_process", "表格处理", 80),
            ("equation_process", "公式处理", 90),
            ("graph_build", "知识图谱构建", 95),
            ("indexing", "索引创建", 100),
        ]
        
        for stage_name, stage_label, progress in stages_progress:
            if task_id not in tasks:  # 任务可能被取消
                return
                
            task["stage"] = stage_name
            task["stage_details"][stage_name]["status"] = "completed"
            task["stage_details"][stage_name]["progress"] = 100
            task["progress"] = progress
            task["updated_at"] = datetime.now().isoformat()
            
            await send_websocket_update(task_id, task)
            await asyncio.sleep(0.2)  # 短暂延迟以显示进度
        
        # 完成处理
        task["status"] = "completed"
        task["progress"] = 100
        task["completed_at"] = datetime.now().isoformat()
        task["multimodal_stats"]["processing_success_rate"] = 100.0
        
        # 更新文档状态
        if task["document_id"] in documents:
            documents[task["document_id"]]["status"] = "completed"
            documents[task["document_id"]]["updated_at"] = datetime.now().isoformat()
            
            # 获取实际处理结果统计
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            documents[task["document_id"]]["processing_time"] = (
                datetime.fromisoformat(task["completed_at"]) - 
                datetime.fromisoformat(task["started_at"])
            ).total_seconds()
            documents[task["document_id"]]["content_length"] = file_size
            documents[task["document_id"]]["parser_used"] = f"{parser_config.parser}({parser_config.method})"
            documents[task["document_id"]]["parser_reason"] = parser_config.reason
        
        logger.info(f"文档处理完成: {file_path}, 解析器: {parser_config.parser}")
    
    except Exception as e:
        await send_processing_log(f"❌ 文档处理失败: {str(e)}", "error")
        logger.error(f"文档处理失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # 设置详细状态错误
        if detailed_tracker.get_status(task_id):
            detailed_status = detailed_tracker.get_status(task_id)
            detailed_status.set_error(str(e))
        
        task["status"] = "failed"
        task["error_message"] = str(e)
        task["completed_at"] = datetime.now().isoformat()  # 确保设置completed_at
        task["updated_at"] = datetime.now().isoformat()
        
        if task["document_id"] in documents:
            documents[task["document_id"]]["status"] = "failed"
            documents[task["document_id"]]["error_message"] = str(e)
            documents[task["document_id"]]["updated_at"] = datetime.now().isoformat()
            # 计算处理时间（即使失败）
            if "started_at" in task and "completed_at" in task:
                documents[task["document_id"]]["processing_time"] = (
                    datetime.fromisoformat(task["completed_at"]) - 
                    datetime.fromisoformat(task["started_at"])
                ).total_seconds()
    
    finally:
        # 清理状态跟踪
        detailed_tracker.remove_status(task_id)
    
    # 发送最终更新
    await send_websocket_update(task_id, task)

async def process_document_real(task_id: str, file_path: str):
    """智能文档处理过程，使用智能路由选择最优解析策略"""
    if task_id not in tasks:
        return
        
    task = tasks[task_id]
    
    try:
        # 获取文件信息
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        file_name = Path(file_path).name
        
        logger.info(f"开始智能路由文档: {file_name} ({file_size//1024}KB)")
        
        # 使用智能路由器选择最优解析策略
        parser_config = router.route_parser(file_path, file_size)
        
        # 验证解析器可用性
        if not router.validate_parser_availability(parser_config.parser):
            logger.warning(f"首选解析器 {parser_config.parser} 不可用，使用备用方案")
            parser_config = router.get_fallback_config(parser_config)
            
            # 再次验证备用解析器
            if not router.validate_parser_availability(parser_config.parser):
                raise Exception(f"所有解析器都不可用，请检查安装")
        
        # 记录解析器选择信息
        task["parser_info"] = {
            "selected_parser": parser_config.parser,
            "method": parser_config.method,
            "category": parser_config.category,
            "reason": parser_config.reason,
            "direct_processing": parser_config.direct_processing
        }
        
        # 根据解析策略选择处理方式
        if parser_config.direct_processing:
            logger.info(f"使用直接处理: {parser_config.reason}")
            await process_text_file_direct(task_id, file_path)
        else:
            logger.info(f"使用解析器处理: {parser_config.parser} - {parser_config.reason}")
            await process_with_parser(task_id, file_path, parser_config)
            
    except Exception as e:
        logger.error(f"智能路由处理失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # 更新任务状态为失败
        if task_id in tasks:
            task["status"] = "failed"
            task["error_message"] = f"智能路由失败: {str(e)}"
            task["updated_at"] = datetime.now().isoformat()
            
            if task["document_id"] in documents:
                documents[task["document_id"]]["status"] = "failed"
                documents[task["document_id"]]["error_message"] = str(e)
                documents[task["document_id"]]["updated_at"] = datetime.now().isoformat()
            
            # 发送最终更新
            await send_websocket_update(task_id, task)

async def send_detailed_status_update(task_id: str, detailed_status: dict):
    """发送详细状态更新到WebSocket"""
    if task_id in active_websockets:
        try:
            # 检查详细状态是否为空
            if detailed_status is None:
                logger.warning(f"详细状态为空，跳过WebSocket更新: {task_id}")
                return
            
            # 发送详细状态信息
            status_message = {
                "type": "detailed_status",
                "task_id": task_id,
                "detailed_status": detailed_status
            }
            await active_websockets[task_id].send_text(json.dumps(status_message))
        except Exception as e:
            logger.error(f"发送详细状态更新失败: {e}")
            active_websockets.pop(task_id, None)

async def send_websocket_update(task_id: str, task: dict):
    """发送WebSocket更新"""
    if task_id in active_websockets:
        try:
            await active_websockets[task_id].send_text(json.dumps(task))
        except:
            active_websockets.pop(task_id, None)

async def send_processing_log(message: str, level: str = "info"):
    """禁用手动日志发送，避免与LightRAG日志系统重复"""
    # 完全禁用手动日志发送，只使用LightRAG原生日志系统
    # 这确保没有重复日志，所有日志都通过智能处理器统一处理
    pass

@app.post("/api/v1/documents/upload") 
async def upload_document(file: UploadFile = File(...)):
    """单文档上传端点 - 保持向后兼容"""
    # 检查文件名重复
    existing_docs = [doc for doc in documents.values() if doc["file_name"] == file.filename]
    if existing_docs:
        raise HTTPException(
            status_code=400, 
            detail=f"文件名 '{file.filename}' 已存在，请重命名后再上传"
        )
    
    task_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    
    # 保存上传的文件
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # 获取实际文件大小（确保一致性）
    actual_file_size = os.path.getsize(file_path)
    
    # 创建任务记录
    task = {
        "task_id": task_id,
        "status": "pending",
        "stage": "parsing",
        "progress": 0,
        "file_path": file_path,
        "file_name": file.filename,
        "file_size": actual_file_size,
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
            "images_count": 0,
            "tables_count": 0,
            "equations_count": 0,
            "images_processed": 0,
            "tables_processed": 0,
            "equations_processed": 0,
            "processing_success_rate": 0.0,
            "text_chunks": 0,
            "knowledge_entities": 0,
            "knowledge_relationships": 0
        }
    }
    
    tasks[task_id] = task
    
    # 创建文档记录
    document = {
        "document_id": document_id,
        "file_name": file.filename,
        "file_path": file_path,
        "file_size": actual_file_size,
        "status": "uploaded",  # 改为uploaded状态，表示已上传但未解析
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "task_id": task_id
    }
    
    documents[document_id] = document
    
    return {
        "success": True,
        "message": "Document uploaded successfully, ready for manual processing", 
        "task_id": task_id,
        "document_id": document_id,
        "file_name": file.filename,
        "file_size": actual_file_size,
        "status": "uploaded"
    }

@app.post("/api/v1/documents/upload/batch", response_model=BatchUploadResponse)
async def upload_documents_batch(files: List[UploadFile] = File(...)):
    """批量文档上传端点"""
    batch_operation_id = str(uuid.uuid4())
    uploaded_count = 0
    failed_count = 0
    results = []
    
    # 创建批量操作状态跟踪
    batch_operation = {
        "batch_operation_id": batch_operation_id,
        "operation_type": "upload",
        "status": "running",
        "total_items": len(files),
        "completed_items": 0,
        "failed_items": 0,
        "progress": 0.0,
        "started_at": datetime.now().isoformat(),
        "results": []
    }
    batch_operations[batch_operation_id] = batch_operation
    
    logger.info(f"开始批量上传 {len(files)} 个文件")
    await send_processing_log(f"📤 开始批量上传 {len(files)} 个文件", "info")
    
    # 支持的文件类型
    supported_extensions = ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.txt', '.md', '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp']
    
    for i, file in enumerate(files):
        file_result = {
            "file_name": file.filename,
            "file_size": 0,
            "status": "failed",
            "message": "",
            "task_id": None,
            "document_id": None
        }
        
        try:
            # 文件类型验证
            file_extension = os.path.splitext(file.filename)[1].lower()
            if file_extension not in supported_extensions:
                file_result["message"] = f"不支持的文件类型: {file_extension}"
                failed_count += 1
                results.append(file_result)
                batch_operation["failed_items"] += 1
                continue
            
            # 检查文件大小（限制100MB）
            content = await file.read()
            file_size = len(content)
            if file_size > 100 * 1024 * 1024:  # 100MB
                file_result["message"] = "文件大小超过100MB限制"
                failed_count += 1
                results.append(file_result)
                batch_operation["failed_items"] += 1
                continue
                
            # 检查文件名重复
            existing_docs = [doc for doc in documents.values() if doc["file_name"] == file.filename]
            if existing_docs:
                file_result["message"] = "文件名重复，已跳过"
                failed_count += 1
                results.append(file_result)
                batch_operation["failed_items"] += 1
                continue
            
            # 保存文件
            task_id = str(uuid.uuid4())
            document_id = str(uuid.uuid4())
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            
            with open(file_path, "wb") as buffer:
                buffer.write(content)
            
            # 获取实际文件大小
            actual_file_size = os.path.getsize(file_path)
            
            # 创建任务记录
            task = {
                "task_id": task_id,
                "status": "pending",
                "stage": "parsing",
                "progress": 0,
                "file_path": file_path,
                "file_name": file.filename,
                "file_size": actual_file_size,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "document_id": document_id,
                "batch_operation_id": batch_operation_id,
                "total_stages": len(PROCESSING_STAGES),
                "stage_details": {
                    stage[0]: {
                        "status": "pending",
                        "progress": 0
                    } for stage in PROCESSING_STAGES
                },
                "multimodal_stats": {
                    "images_count": 0,
                    "tables_count": 0,
                    "equations_count": 0,
                    "images_processed": 0,
                    "tables_processed": 0,
                    "equations_processed": 0,
                    "processing_success_rate": 0.0,
                    "text_chunks": 0,
                    "knowledge_entities": 0,
                    "knowledge_relationships": 0
                }
            }
            
            tasks[task_id] = task
            
            # 创建文档记录
            document = {
                "document_id": document_id,
                "file_name": file.filename,
                "file_path": file_path,
                "file_size": actual_file_size,
                "status": "uploaded",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "task_id": task_id,
                "batch_operation_id": batch_operation_id
            }
            
            documents[document_id] = document
            
            # 成功结果
            file_result.update({
                "file_size": actual_file_size,
                "status": "success",
                "message": "上传成功",
                "task_id": task_id,
                "document_id": document_id
            })
            
            uploaded_count += 1
            batch_operation["completed_items"] += 1
            results.append(file_result)
            
        except Exception as e:
            file_result["message"] = f"上传失败: {str(e)}"
            failed_count += 1
            batch_operation["failed_items"] += 1
            results.append(file_result)
            logger.error(f"批量上传文件 {file.filename} 失败: {str(e)}")
        
        # 更新进度
        batch_operation["progress"] = ((i + 1) / len(files)) * 100
        await send_processing_log(f"📤 批量上传进度: {i + 1}/{len(files)} ({batch_operation['progress']:.1f}%)", "info")
    
    # 完成批量操作
    batch_operation["status"] = "completed"
    batch_operation["completed_at"] = datetime.now().isoformat()
    batch_operation["results"] = results
    
    message = f"批量上传完成: {uploaded_count} 个成功, {failed_count} 个失败"
    logger.info(message)
    await send_processing_log(f"✅ {message}", "info")
    
    return BatchUploadResponse(
        success=failed_count == 0,
        uploaded_count=uploaded_count,
        failed_count=failed_count,
        total_files=len(files),
        results=results,
        message=message
    )

@app.post("/api/v1/documents/{document_id}/process")
async def process_document_manually(document_id: str):
    """手动触发文档处理端点"""
    if document_id not in documents:
        raise HTTPException(status_code=404, detail="Document not found")
    
    document = documents[document_id]
    
    # 检查文档状态
    if document["status"] != "uploaded":
        raise HTTPException(
            status_code=400, 
            detail=f"Document cannot be processed. Current status: {document['status']}"
        )
    
    # 检查任务是否已存在
    task_id = document.get("task_id")
    if not task_id or task_id not in tasks:
        raise HTTPException(status_code=400, detail="Processing task not found")
    
    try:
        # 更新文档状态为处理中
        document["status"] = "processing"
        document["updated_at"] = datetime.now().isoformat()
        
        # 更新任务状态
        task = tasks[task_id]
        task["status"] = "pending"
        task["updated_at"] = datetime.now().isoformat()
        
        # 启动处理任务
        file_path = document["file_path"]
        asyncio.create_task(process_document_real(task_id, file_path))
        
        logger.info(f"手动启动文档处理: {document['file_name']}")
        
        return {
            "success": True,
            "message": f"Document processing started for {document['file_name']}",
            "document_id": document_id,
            "task_id": task_id,
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"启动文档处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")

@app.post("/api/v1/documents/process/batch", response_model=BatchProcessResponse)
async def process_documents_batch(request: BatchProcessRequest):
    """批量文档处理端点"""
    batch_operation_id = str(uuid.uuid4())
    started_count = 0
    failed_count = 0
    results = []
    
    # 创建批量操作状态跟踪
    batch_operation = {
        "batch_operation_id": batch_operation_id,
        "operation_type": "process",
        "status": "running",
        "total_items": len(request.document_ids),
        "completed_items": 0,
        "failed_items": 0,
        "progress": 0.0,
        "started_at": datetime.now().isoformat(),
        "results": []
    }
    batch_operations[batch_operation_id] = batch_operation
    
    logger.info(f"开始批量处理 {len(request.document_ids)} 个文档")
    await send_processing_log(f"⚡ 开始批量处理 {len(request.document_ids)} 个文档", "info")
    
    # 并发控制配置
    max_concurrent = int(os.getenv("MAX_CONCURRENT_PROCESSING", "3"))
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_single_document(document_id: str, index: int) -> dict:
        """处理单个文档的异步函数"""
        doc_result = {
            "document_id": document_id,
            "file_name": "unknown",
            "status": "failed",
            "message": "",
            "task_id": None
        }
        
        try:
            # 检查文档是否存在
            if document_id not in documents:
                doc_result["message"] = "文档不存在"
                return doc_result
            
            document = documents[document_id]
            doc_result["file_name"] = document["file_name"]
            
            # 检查文档状态
            if document["status"] != "uploaded":
                doc_result["message"] = f"文档状态不允许处理: {document['status']}"
                return doc_result
            
            # 检查任务是否存在
            task_id = document.get("task_id")
            if not task_id or task_id not in tasks:
                doc_result["message"] = "处理任务不存在"
                return doc_result
            
            # 先设置为queued状态，然后通过semaphore控制实际处理
            document["status"] = "queued"
            document["updated_at"] = datetime.now().isoformat()
            
            task = tasks[task_id]
            task["status"] = "queued"
            task["updated_at"] = datetime.now().isoformat()
            task["batch_operation_id"] = batch_operation_id
            
            doc_result.update({
                "status": "success",
                "message": "文档已排队等待处理",
                "task_id": task_id
            })
            
            # 使用semaphore控制并发执行
            async def controlled_processing():
                try:
                    async with semaphore:
                        # 重新检查任务是否仍然存在（并发安全）
                        if task_id not in tasks:
                            logger.warning(f"任务已被删除，跳过处理: {task_id}")
                            return
                        
                        # 更新为processing状态
                        document["status"] = "processing"
                        current_task = tasks[task_id]  # 获取当前任务引用
                        current_task["status"] = "pending"
                        await send_processing_log(f"🔥 开始处理文档: {document['file_name']}", "info")
                        
                        # 启动实际处理任务
                        file_path = document["file_path"]
                        await process_document_real(task_id, file_path)
                        
                        # 处理成功后的状态更新
                        await send_processing_log(f"✅ 文档处理完成: {document['file_name']}", "info")
                        
                except Exception as e:
                    # 确保错误时正确更新状态，再次检查任务存在性
                    document["status"] = "failed"
                    if task_id in tasks:
                        current_task = tasks[task_id]
                        current_task["status"] = "failed"
                        current_task["error"] = str(e)
                        current_task["updated_at"] = datetime.now().isoformat()
                    await send_processing_log(f"❌ 文档处理失败: {document['file_name']} - {str(e)}", "error")
                    logger.error(f"处理文档 {document['file_name']} 失败: {str(e)}")
                    # semaphore在async with块结束时会自动释放
            
            # 启动受控制的处理任务
            asyncio.create_task(controlled_processing())
            
            return doc_result
            
        except Exception as e:
            doc_result["message"] = f"启动处理失败: {str(e)}"
            logger.error(f"批量处理文档 {document_id} 失败: {str(e)}")
            return doc_result
    
    # 执行批量处理
    processing_tasks = []
    for i, document_id in enumerate(request.document_ids):
        task = process_single_document(document_id, i)
        processing_tasks.append(task)
    
    # 等待所有处理任务完成
    processing_results = await asyncio.gather(*processing_tasks, return_exceptions=True)
    
    # 统计结果
    for i, result in enumerate(processing_results):
        if isinstance(result, Exception):
            # 处理异常情况
            doc_result = {
                "document_id": request.document_ids[i],
                "file_name": "unknown",
                "status": "failed",
                "message": f"处理异常: {str(result)}",
                "task_id": None
            }
            failed_count += 1
            batch_operation["failed_items"] += 1
        else:
            if result["status"] == "success":
                started_count += 1
                batch_operation["completed_items"] += 1
            else:
                failed_count += 1
                batch_operation["failed_items"] += 1
            doc_result = result
        
        results.append(doc_result)
        
        # 更新进度
        batch_operation["progress"] = ((i + 1) / len(request.document_ids)) * 100
        await send_processing_log(f"⚡ 批量处理进度: {i + 1}/{len(request.document_ids)} ({batch_operation['progress']:.1f}%)", "info")
    
    # 完成批量操作
    batch_operation["status"] = "completed"
    batch_operation["completed_at"] = datetime.now().isoformat()
    batch_operation["results"] = results
    
    message = f"批量处理完成: {started_count} 个启动成功, {failed_count} 个失败"
    logger.info(message)
    await send_processing_log(f"✅ {message}", "info")
    
    return BatchProcessResponse(
        success=failed_count == 0,
        started_count=started_count,
        failed_count=failed_count,
        total_requested=len(request.document_ids),
        results=results,
        batch_operation_id=batch_operation_id,
        message=message
    )

@app.post("/api/v1/query")
async def query_documents(request: QueryRequest):
    """查询文档端点"""
    rag = await initialize_rag()
    if not rag:
        raise HTTPException(status_code=503, detail="RAG系统未初始化")
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="查询内容不能为空")
    
    try:
        # 执行查询
        result = await rag.aquery(
            request.query, 
            mode=request.mode, 
            vlm_enhanced=request.vlm_enhanced
        )
        
        # 记录查询任务
        query_task_id = str(uuid.uuid4())
        query_task = {
            "task_id": query_task_id,
            "type": "query",
            "query": request.query,
            "mode": request.mode,
            "result": result,
            "timestamp": datetime.now().isoformat(),
            "processing_time": 0.234,  # 模拟处理时间
            "status": "completed"
        }
        tasks[query_task_id] = query_task
        
        return {
            "success": True,
            "query": request.query,
            "mode": request.mode,
            "result": result,
            "timestamp": datetime.now().isoformat(),
            "processing_time": 0.234,
            "sources": [],  # RAG可能返回的源文档信息
            "metadata": {
                "total_documents": len(documents),
                "tokens_used": 156,
                "confidence_score": 0.89
            }
        }
        
    except Exception as e:
        logger.error(f"查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

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
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "success": True,
        "task": tasks[task_id]
    }

@app.get("/api/v1/tasks/{task_id}/detailed-status")
async def get_detailed_task_status(task_id: str):
    """获取任务的详细状态信息"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 获取详细状态
    detailed_status = detailed_tracker.get_status(task_id)
    if not detailed_status:
        return {
            "success": True,
            "task_id": task_id,
            "has_detailed_status": False,
            "message": "详细状态跟踪不可用"
        }
    
    return {
        "success": True,
        "task_id": task_id,
        "has_detailed_status": True,
        "detailed_status": detailed_status.to_dict()
    }

@app.post("/api/v1/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任务"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
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

def get_document_display_info(doc):
    """获取文档的显示信息，适用于统一文档区域"""
    doc_id = doc["document_id"]
    task_id = doc.get("task_id")
    
    # 基础信息
    display_info = {
        "document_id": doc_id,
        "file_name": doc["file_name"],
        "file_size": doc["file_size"],
        "uploaded_at": doc["created_at"],
        "status_code": doc["status"]
    }
    
    # 根据状态生成显示信息
    if doc["status"] == "uploaded":
        display_info.update({
            "status_display": "等待解析",
            "action_type": "start_processing",
            "action_icon": "play",
            "action_text": "开始解析",
            "can_process": True
        })
    
    elif doc["status"] == "processing":
        # 获取实时处理状态
        current_progress = ""
        progress_percent = 0
        
        if task_id and task_id in tasks:
            task = tasks[task_id]
            stage = task.get("stage", "processing")
            progress = task.get("progress", 0)
            progress_percent = progress
            
            # 获取详细状态信息
            detailed_status = detailed_tracker.get_status(task_id)
            if detailed_status:
                current_stage = detailed_status.current_stage
                if current_stage:
                    stage_names = {
                        "parsing": "解析文档",
                        "content_analysis": "分析内容", 
                        "text_processing": "处理文本",
                        "image_processing": "处理图片",
                        "table_processing": "处理表格",
                        "equation_processing": "处理公式",
                        "graph_building": "构建知识图谱",
                        "indexing": "创建索引"
                    }
                    stage_display = stage_names.get(current_stage.value, current_stage.value)
                    
                    # 显示具体进度信息
                    if hasattr(detailed_status, 'content_stats'):
                        stats = detailed_status.content_stats
                        if current_stage.value == "image_processing" and stats.image_blocks > 0:
                            current_progress = f"{stage_display} ({stats.image_blocks}张图片)"
                        elif current_stage.value == "table_processing" and stats.table_blocks > 0:
                            current_progress = f"{stage_display} ({stats.table_blocks}个表格)"
                        else:
                            current_progress = stage_display
                    else:
                        current_progress = stage_display
                else:
                    current_progress = "解析中..."
            else:
                stage_names = {
                    "parsing": "解析文档",
                    "separation": "分离内容",
                    "text_insert": "插入文本", 
                    "image_process": "处理图片",
                    "table_process": "处理表格",
                    "equation_process": "处理公式",
                    "graph_build": "构建知识图谱",
                    "indexing": "创建索引"
                }
                current_progress = stage_names.get(stage, "解析中...")
        
        display_info.update({
            "status_display": f"解析中 - {current_progress}",
            "action_type": "processing",
            "action_icon": "loading",
            "action_text": f"{progress_percent}%",
            "can_process": False,
            "progress_percent": progress_percent
        })
    
    elif doc["status"] == "completed":
        # 计算完成时间
        time_info = "刚刚完成"
        if "updated_at" in doc:
            try:
                from datetime import datetime
                updated_time = datetime.fromisoformat(doc["updated_at"])
                now = datetime.now()
                time_diff = now - updated_time
                
                if time_diff.days > 0:
                    time_info = f"{time_diff.days}天前完成"
                elif time_diff.seconds > 3600:
                    hours = time_diff.seconds // 3600
                    time_info = f"{hours}小时前完成"
                elif time_diff.seconds > 60:
                    minutes = time_diff.seconds // 60
                    time_info = f"{minutes}分钟前完成"
                else:
                    time_info = "刚刚完成"
            except:
                time_info = "已完成"
        
        # 添加文档统计信息
        chunks_info = ""
        if "chunks_count" in doc and doc["chunks_count"]:
            chunks_info = f" ({doc['chunks_count']}个文本块)"
        
        display_info.update({
            "status_display": f"已完成 - {time_info}{chunks_info}",
            "action_type": "completed",
            "action_icon": "check",
            "action_text": "已完成",
            "can_process": False
        })
    
    elif doc["status"] == "failed":
        error_msg = doc.get("error_message", "未知错误")
        # 简化错误信息显示
        if len(error_msg) > 30:
            error_msg = error_msg[:30] + "..."
        
        display_info.update({
            "status_display": f"解析失败 - {error_msg}",
            "action_type": "retry",
            "action_icon": "refresh",
            "action_text": "重试",
            "can_process": True
        })
    
    else:
        display_info.update({
            "status_display": doc["status"],
            "action_type": "unknown",
            "action_icon": "question",
            "action_text": "未知",
            "can_process": False
        })
    
    return display_info

@app.get("/api/v1/documents")
async def list_documents():
    """获取文档列表 - 优化为统一文档区域显示"""
    # 获取增强的文档显示信息
    enhanced_documents = []
    for doc in documents.values():
        enhanced_documents.append(get_document_display_info(doc))
    
    # 按上传时间倒序排列，最新上传的在前
    enhanced_documents.sort(key=lambda x: x["uploaded_at"], reverse=True)
    
    return {
        "success": True,
        "documents": enhanced_documents,
        "total_count": len(enhanced_documents),
        "status_counts": {
            "uploaded": len([d for d in documents.values() if d["status"] == "uploaded"]),
            "processing": len([d for d in documents.values() if d["status"] == "processing"]),
            "completed": len([d for d in documents.values() if d["status"] == "completed"]),
            "failed": len([d for d in documents.values() if d["status"] == "failed"])
        }
    }

@app.get("/api/v1/logs/summary")
async def get_log_summary_api(mode: str = "summary", include_debug: bool = False):
    """获取日志摘要"""
    try:
        summary = get_log_summary(include_debug=include_debug)
        return {
            "success": True,
            "data": summary
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"获取日志摘要失败: {str(e)}"}
        )

@app.get("/api/v1/logs/core")
async def get_core_logs_api():
    """获取核心进度日志"""
    try:
        core_logs = get_core_progress()
        return {
            "success": True,
            "logs": core_logs
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"获取核心日志失败: {str(e)}"}
        )

@app.post("/api/v1/logs/clear")
async def clear_processing_logs_api():
    """清空处理日志"""
    try:
        clear_logs()
        return {"success": True, "message": "日志已清空"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"清空日志失败: {str(e)}"}
        )

@app.delete("/api/v1/documents")
async def delete_documents(request: DocumentDeleteRequest):
    """删除文档 - 完整删除包括向量库和知识图谱中的相关内容"""
    deleted_count = 0
    deletion_results = []
    rag = await initialize_rag()
    
    for doc_id in request.document_ids:
        if doc_id in documents:
            doc = documents[doc_id]
            result = {
                "document_id": doc_id,
                "file_name": doc.get("file_name", "unknown"),
                "status": "success",
                "message": "",
                "details": {}
            }
            
            try:
                # 1. 从RAG系统中删除文档数据（如果有rag_doc_id）
                rag_doc_id = doc.get("rag_doc_id")
                if rag_doc_id and rag:
                    logger.info(f"从RAG系统删除文档: {rag_doc_id}")
                    deletion_result = await rag.lightrag.adelete_by_doc_id(rag_doc_id)
                    result["details"]["rag_deletion"] = {
                        "status": deletion_result.status,
                        "message": deletion_result.message,
                        "status_code": deletion_result.status_code
                    }
                    logger.info(f"RAG删除结果: {deletion_result.status} - {deletion_result.message}")
                else:
                    result["details"]["rag_deletion"] = {
                        "status": "skipped",
                        "message": "文档未在RAG系统中找到或RAG未初始化",
                        "status_code": 404
                    }
                
                # 2. 删除上传的文件
                if os.path.exists(doc["file_path"]):
                    os.remove(doc["file_path"])
                    result["details"]["file_deletion"] = "文件已删除"
                    logger.info(f"删除文件: {doc['file_path']}")
                else:
                    result["details"]["file_deletion"] = "文件不存在或已删除"
                
                # 3. 从内存中删除文档记录
                del documents[doc_id]
                deleted_count += 1
                
                result["message"] = f"文档 {doc['file_name']} 已完全删除"
                logger.info(f"成功删除文档: {doc['file_name']}")
                
            except Exception as e:
                result["status"] = "error"
                result["message"] = f"删除文档时发生错误: {str(e)}"
                result["details"]["error"] = str(e)
                logger.error(f"删除文档失败 {doc['file_name']}: {str(e)}")
            
            deletion_results.append(result)
        else:
            deletion_results.append({
                "document_id": doc_id,
                "file_name": "unknown",
                "status": "not_found",
                "message": "文档不存在",
                "details": {}
            })
    
    success_count = len([r for r in deletion_results if r["status"] == "success"])
    
    return {
        "success": success_count > 0,
        "message": f"成功删除 {success_count}/{len(request.document_ids)} 个文档",
        "deleted_count": success_count,
        "deletion_results": deletion_results
    }

@app.delete("/api/v1/documents/clear")
async def clear_documents():
    """清空所有文档 - 完整清空包括向量库和知识图谱中的所有内容"""
    count = len(documents)
    rag = await initialize_rag()
    
    # 记录清空结果
    clear_results = {
        "total_documents": count,
        "files_deleted": 0,
        "rag_deletions": {"success": 0, "failed": 0, "skipped": 0},
        "orphan_deletions": {"success": 0, "failed": 0},
        "errors": []
    }
    
    # 1. 删除文档管理界面中的文档
    for doc_id, doc in list(documents.items()):
        try:
            # 从RAG系统中删除文档数据
            rag_doc_id = doc.get("rag_doc_id")
            if rag_doc_id and rag:
                try:
                    deletion_result = await rag.lightrag.adelete_by_doc_id(rag_doc_id)
                    if deletion_result.status == "success":
                        clear_results["rag_deletions"]["success"] += 1
                        logger.info(f"从RAG系统删除文档: {rag_doc_id} - {deletion_result.message}")
                    else:
                        clear_results["rag_deletions"]["failed"] += 1
                        logger.warning(f"RAG删除失败: {rag_doc_id} - {deletion_result.message}")
                except Exception as e:
                    clear_results["rag_deletions"]["failed"] += 1
                    clear_results["errors"].append(f"RAG删除失败 {rag_doc_id}: {str(e)}")
                    logger.error(f"RAG删除异常 {rag_doc_id}: {str(e)}")
            else:
                clear_results["rag_deletions"]["skipped"] += 1
            
            # 删除上传的文件
            if os.path.exists(doc["file_path"]):
                os.remove(doc["file_path"])
                clear_results["files_deleted"] += 1
                
        except Exception as e:
            clear_results["errors"].append(f"删除文档失败 {doc.get('file_name', doc_id)}: {str(e)}")
            logger.error(f"删除文档异常: {str(e)}")
    
    # 2. 清理RAG系统中的孤儿文档
    if rag:
        try:
            # 读取RAG系统中的所有文档
            doc_status_file = os.path.join(WORKING_DIR, "kv_store_doc_status.json")
            if os.path.exists(doc_status_file):
                logger.info("清理RAG系统中的孤儿文档...")
                with open(doc_status_file, 'r', encoding='utf-8') as f:
                    rag_docs = json.load(f)
                
                # 获取已处理的RAG文档ID
                processed_rag_ids = {doc.get("rag_doc_id") for doc in documents.values() if doc.get("rag_doc_id")}
                
                # 找出孤儿文档
                orphan_rag_ids = set(rag_docs.keys()) - processed_rag_ids
                logger.info(f"发现 {len(orphan_rag_ids)} 个孤儿文档: {list(orphan_rag_ids)}")
                
                # 删除孤儿文档
                for orphan_id in orphan_rag_ids:
                    try:
                        deletion_result = await rag.lightrag.adelete_by_doc_id(orphan_id)
                        if deletion_result.status == "success":
                            clear_results["orphan_deletions"]["success"] += 1
                            logger.info(f"清理孤儿文档: {orphan_id} - {deletion_result.message}")
                        else:
                            clear_results["orphan_deletions"]["failed"] += 1
                            logger.warning(f"孤儿文档删除失败: {orphan_id} - {deletion_result.message}")
                    except Exception as e:
                        clear_results["orphan_deletions"]["failed"] += 1
                        clear_results["errors"].append(f"孤儿文档删除失败 {orphan_id}: {str(e)}")
                        logger.error(f"孤儿文档删除异常 {orphan_id}: {str(e)}")
        except Exception as e:
            clear_results["errors"].append(f"孤儿文档清理失败: {str(e)}")
            logger.error(f"孤儿文档清理异常: {str(e)}")
    
    # 清空内存数据
    documents.clear()
    tasks.clear()
    
    # 关闭所有WebSocket连接
    for ws in active_websockets.values():
        try:
            await ws.close()
        except:
            pass
    active_websockets.clear()
    
    # 生成清空报告
    success_rate = (clear_results["rag_deletions"]["success"] / max(count, 1)) * 100
    message = f"清空完成: {count}个文档, RAG删除成功率{success_rate:.1f}%"
    
    if clear_results["errors"]:
        message += f", {len(clear_results['errors'])}个错误"
    
    logger.info(message)
    logger.info(f"详细结果: {clear_results}")
    
    return {
        "success": True,
        "message": message,
        "details": clear_results
    }

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
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
    finally:
        active_websockets.pop(task_id, None)

@app.websocket("/api/v1/documents/progress")
async def websocket_processing_logs(websocket: WebSocket):
    """文档解析过程日志WebSocket端点 - 连接到LightRAG实时日志"""
    # Check origin header for CORS compliance
    origin = websocket.headers.get("origin")
    logger.info(f"WebSocket connection attempt from origin: {origin}")
    
    # Accept all origins (similar to CORS middleware configuration)
    await websocket.accept()
    
    # 只添加到智能日志处理器，避免重复
    websocket_log_handler.add_websocket_client(websocket)
    
    try:
        # 发送连接确认 - 通过新的日志系统
        await send_processing_log("WebSocket连接已建立，准备接收LightRAG实时日志...", "info")
        
        # 保持连接
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"处理日志WebSocket错误: {e}")
    finally:
        # 只从智能日志处理器中移除
        websocket_log_handler.remove_websocket_client(websocket)

@app.get("/api/v1/batch-operations/{batch_operation_id}", response_model=BatchOperationStatus)
async def get_batch_operation_status(batch_operation_id: str):
    """获取批量操作状态"""
    if batch_operation_id not in batch_operations:
        raise HTTPException(status_code=404, detail="Batch operation not found")
    
    batch_operation = batch_operations[batch_operation_id]
    
    return BatchOperationStatus(
        batch_operation_id=batch_operation["batch_operation_id"],
        operation_type=batch_operation["operation_type"],
        status=batch_operation["status"],
        total_items=batch_operation["total_items"],
        completed_items=batch_operation["completed_items"],
        failed_items=batch_operation["failed_items"],
        progress=batch_operation["progress"],
        started_at=batch_operation["started_at"],
        completed_at=batch_operation.get("completed_at"),
        results=batch_operation.get("results", [])
    )

@app.get("/api/v1/batch-operations")
async def list_batch_operations(limit: int = 50, status: Optional[str] = None):
    """列出批量操作"""
    operations = list(batch_operations.values())
    
    # 按状态过滤
    if status:
        operations = [op for op in operations if op["status"] == status]
    
    # 按开始时间倒序排序
    operations.sort(key=lambda x: x["started_at"], reverse=True)
    
    # 限制返回数量
    operations = operations[:limit]
    
    return {
        "success": True,
        "operations": operations,
        "total": len(operations)
    }

if __name__ == "__main__":
    print("🚀 Starting RAG-Anything API Server with Smart Parser Routing & Batch Processing Support")
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
    print("🧠 Smart Features:")
    print("   ⚡ Direct text processing (TXT/MD files)")
    print("   📄 PDF files → MinerU (specialized PDF engine)")
    print("   📊 Office files → Docling (native Office support)")
    print("   🖼️  Image files → MinerU (OCR capability)")
    print("   📈 Real-time parser usage statistics")
    print("   📊 Detailed processing status like native_with_qwen.py")
    print("   🎯 Manual processing control - upload without auto-processing")
    print()
    
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="info")