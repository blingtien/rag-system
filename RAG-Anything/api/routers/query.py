"""
查询服务路由
处理文档查询、检索等相关的API端点
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from config.dependencies import get_rag_instance, get_state_manager_singleton
from core.state_manager import StateManager
from raganything import RAGAnything


router = APIRouter(prefix="/api/v1", tags=["query"])


# 请求/响应模型
class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"
    vlm_enhanced: bool = False


class QueryResponse(BaseModel):
    success: bool
    query: str
    mode: str
    result: str
    timestamp: str
    processing_time: float
    sources: list = []
    metadata: dict = {}


@router.post("/query")
async def query_documents(
    request: QueryRequest,
    rag_instance: RAGAnything = Depends(get_rag_instance),
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """查询文档端点"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="查询内容不能为空")
    
    start_time = datetime.now()
    
    try:
        # 执行查询
        result = await rag_instance.aquery(
            request.query, 
            mode=request.mode, 
            vlm_enhanced=request.vlm_enhanced
        )
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # 记录查询任务到状态管理器
        query_task_id = str(uuid.uuid4())
        query_task_data = {
            "task_id": query_task_id,
            "type": "query",
            "query": request.query,
            "mode": request.mode,
            "result": result,
            "timestamp": end_time.isoformat(),
            "processing_time": processing_time,
            "status": "completed"
        }
        
        # TODO: 在Phase 2中实现专门的查询任务存储
        # await state_manager.add_query_task(query_task_data)
        
        # 获取文档统计信息
        documents = await state_manager.get_all_documents()
        completed_docs = [doc for doc in documents if doc.status == "completed"]
        
        return QueryResponse(
            success=True,
            query=request.query,
            mode=request.mode,
            result=result,
            timestamp=end_time.isoformat(),
            processing_time=processing_time,
            sources=[],  # RAG可能返回的源文档信息
            metadata={
                "total_documents": len(documents),
                "searchable_documents": len(completed_docs),
                "tokens_used": 156,  # 模拟数据，实际可以从RAG系统获取
                "confidence_score": 0.89  # 模拟数据
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/query/multimodal")
async def query_with_multimodal(
    query: str,
    multimodal_content: Optional[list] = None,
    mode: str = "hybrid",
    rag_instance: RAGAnything = Depends(get_rag_instance),
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """多模态查询端点"""
    if not query.strip():
        raise HTTPException(status_code=400, detail="查询内容不能为空")
    
    start_time = datetime.now()
    
    try:
        # TODO: 在Phase 2中实现多模态查询逻辑
        # 目前使用基本查询作为占位符
        result = await rag_instance.aquery(query, mode=mode)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # 记录多模态查询
        query_task_id = str(uuid.uuid4())
        
        return {
            "success": True,
            "query": query,
            "mode": mode,
            "multimodal_content_provided": multimodal_content is not None,
            "result": result,
            "timestamp": end_time.isoformat(),
            "processing_time": processing_time,
            "query_id": query_task_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"多模态查询失败: {str(e)}")


@router.get("/query/history")
async def get_query_history(
    limit: int = 50,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取查询历史"""
    # TODO: 在Phase 2中实现查询历史存储和检索
    # 目前返回模拟数据
    
    mock_history = [
        {
            "query_id": str(uuid.uuid4()),
            "query": "什么是机器学习?",
            "mode": "hybrid",
            "timestamp": datetime.now().isoformat(),
            "processing_time": 1.234,
            "status": "completed"
        }
    ]
    
    return {
        "success": True,
        "queries": mock_history[:limit],
        "total_count": len(mock_history),
        "limit": limit
    }


@router.get("/query/statistics")
async def get_query_statistics(
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取查询统计信息"""
    # TODO: 在Phase 2中实现真实的查询统计
    # 目前返回基本信息
    
    documents = await state_manager.get_all_documents()
    completed_docs = [doc for doc in documents if doc.status == "completed"]
    
    return {
        "success": True,
        "statistics": {
            "searchable_documents": len(completed_docs),
            "total_documents": len(documents),
            "total_queries_today": 0,  # TODO: 实现查询计数
            "average_response_time": 0.0,  # TODO: 实现平均响应时间
            "query_modes_usage": {
                "hybrid": 0,
                "local": 0,
                "global": 0,
                "naive": 0
            }
        },
        "timestamp": datetime.now().isoformat()
    }


@router.post("/query/suggest")
async def suggest_queries(
    partial_query: str,
    max_suggestions: int = 5,
    rag_instance: RAGAnything = Depends(get_rag_instance)
):
    """查询建议端点"""
    if not partial_query.strip():
        return {
            "success": True,
            "suggestions": [],
            "partial_query": partial_query
        }
    
    try:
        # TODO: 在Phase 2中实现基于文档内容的智能查询建议
        # 目前返回简单的模拟建议
        
        mock_suggestions = [
            f"{partial_query}的定义是什么？",
            f"{partial_query}的应用场景有哪些？",
            f"如何理解{partial_query}？",
            f"{partial_query}的优缺点是什么？",
            f"{partial_query}与相关概念的区别？"
        ]
        
        # 根据请求限制返回数量
        suggestions = mock_suggestions[:max_suggestions]
        
        return {
            "success": True,
            "suggestions": suggestions,
            "partial_query": partial_query,
            "max_suggestions": max_suggestions
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"生成查询建议失败: {str(e)}",
            "suggestions": [],
            "partial_query": partial_query
        }


@router.get("/query/modes")
async def get_available_query_modes():
    """获取可用的查询模式"""
    modes = [
        {
            "mode": "hybrid",
            "name": "混合模式",
            "description": "结合本地和全局信息，提供最佳的查询结果",
            "recommended": True
        },
        {
            "mode": "local",
            "name": "本地模式", 
            "description": "基于本地模式匹配，适合具体问题查询",
            "recommended": False
        },
        {
            "mode": "global",
            "name": "全局模式",
            "description": "基于全局知识图谱，适合概览性查询",
            "recommended": False
        },
        {
            "mode": "naive",
            "name": "简单模式",
            "description": "基于简单相似度匹配，快速查询",
            "recommended": False
        }
    ]
    
    return {
        "success": True,
        "available_modes": modes,
        "default_mode": "hybrid"
    }


@router.post("/query/explain")
async def explain_query_result(
    query: str,
    result: str,
    mode: str = "hybrid",
    rag_instance: RAGAnything = Depends(get_rag_instance)
):
    """解释查询结果端点"""
    try:
        # TODO: 在Phase 2中实现结果解释逻辑
        # 可以分析结果的来源、置信度、相关性等
        
        explanation = {
            "query_analysis": {
                "query_type": "factual",  # 查询类型：factual, procedural, conceptual
                "key_concepts": query.split(),  # 简化的概念提取
                "complexity": "medium"
            },
            "result_analysis": {
                "source_documents": [],  # 来源文档
                "confidence_score": 0.85,
                "reasoning_path": "基于混合检索模式，结合了本地和全局信息",
                "key_evidence": []
            },
            "suggestions": [
                "可以尝试更具体的查询词汇",
                "考虑使用不同的查询模式",
                "添加更多上下文信息"
            ]
        }
        
        return {
            "success": True,
            "query": query,
            "mode": mode,
            "explanation": explanation,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"结果解释失败: {str(e)}")


@router.post("/query/feedback")
async def submit_query_feedback(
    query: str,
    result: str,
    rating: int,  # 1-5评分
    feedback_text: Optional[str] = None,
    helpful: bool = True
):
    """提交查询反馈端点"""
    if not 1 <= rating <= 5:
        raise HTTPException(status_code=400, detail="评分必须在1-5之间")
    
    feedback_id = str(uuid.uuid4())
    
    # TODO: 在Phase 2中实现反馈存储和分析
    feedback_data = {
        "feedback_id": feedback_id,
        "query": query,
        "result": result,
        "rating": rating,
        "feedback_text": feedback_text,
        "helpful": helpful,
        "timestamp": datetime.now().isoformat()
    }
    
    return {
        "success": True,
        "message": "反馈已提交，谢谢您的宝贵意见！",
        "feedback_id": feedback_id,
        "timestamp": datetime.now().isoformat()
    }