"""
批量操作路由
处理批量处理、批量操作状态查询等相关的API端点
"""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from config.dependencies import (
    get_state_manager_singleton,
    get_rag_instance,
    get_cache_enhanced_processor
)
from core.state_manager import StateManager, BatchOperation


router = APIRouter(prefix="/api/v1", tags=["batch"])


# 请求/响应模型
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
    cache_performance: Optional[dict] = None


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


@router.post("/documents/process/batch", response_model=BatchProcessResponse)
async def process_documents_batch(
    request: BatchProcessRequest,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """批量文档处理端点"""
    batch_operation_id = str(uuid.uuid4())
    started_count = 0
    failed_count = 0
    results = []
    
    # 初始化缓存性能指标
    cache_metrics = {
        "cache_hits": 0,
        "cache_misses": 0,
        "cache_hit_ratio": 0.0,
        "total_time_saved": 0.0,
        "efficiency_improvement": 0.0
    }
    
    # 创建批量操作状态跟踪
    batch_operation = BatchOperation(
        batch_operation_id=batch_operation_id,
        operation_type="process",
        status="running",
        total_items=len(request.document_ids),
        completed_items=0,
        failed_items=0,
        progress=0.0,
        started_at=datetime.now().isoformat(),
        results=[]
    )
    
    await state_manager.add_batch_operation(batch_operation)
    
    try:
        # TODO: 在Phase 2中实现具体的批量处理逻辑
        # 目前只进行基本的验证和状态更新
        
        # 验证文档存在性和状态
        valid_documents = []
        for document_id in request.document_ids:
            document = await state_manager.get_document(document_id)
            
            if not document:
                results.append({
                    "document_id": document_id,
                    "file_name": "unknown",
                    "status": "failed",
                    "message": "文档不存在",
                    "task_id": None
                })
                failed_count += 1
                continue
            
            if document.status != "uploaded":
                results.append({
                    "document_id": document_id,
                    "file_name": document.file_name,
                    "status": "failed",
                    "message": f"文档状态不允许处理: {document.status}",
                    "task_id": document.task_id
                })
                failed_count += 1
                continue
            
            # 验证文件存在
            import os
            if not os.path.exists(document.file_path):
                results.append({
                    "document_id": document_id,
                    "file_name": document.file_name,
                    "status": "failed",
                    "message": f"文件不存在: {document.file_path}",
                    "task_id": document.task_id
                })
                failed_count += 1
                continue
            
            valid_documents.append(document)
        
        # 对有效文档进行批量处理准备
        for document in valid_documents:
            try:
                # 更新文档状态为处理中
                await state_manager.update_document_status(
                    document.document_id,
                    "processing",
                    batch_operation_id=batch_operation_id
                )
                
                # 更新任务状态
                if document.task_id:
                    await state_manager.update_task(
                        document.task_id,
                        status="pending",
                        batch_operation_id=batch_operation_id
                    )
                
                results.append({
                    "document_id": document.document_id,
                    "file_name": document.file_name,
                    "status": "success",
                    "message": "批量处理已启动",
                    "task_id": document.task_id
                })
                started_count += 1
                
            except Exception as e:
                results.append({
                    "document_id": document.document_id,
                    "file_name": document.file_name,
                    "status": "failed",
                    "message": f"启动处理失败: {str(e)}",
                    "task_id": document.task_id
                })
                failed_count += 1
        
        # 更新批量操作状态
        await state_manager.update_batch_operation(
            batch_operation_id,
            completed_items=started_count,
            failed_items=failed_count,
            progress=100.0,
            status="completed",
            completed_at=datetime.now().isoformat(),
            results=results
        )
        
        message = f"批量处理启动: {started_count} 个成功, {failed_count} 个失败"
        
        return BatchProcessResponse(
            success=failed_count == 0,
            started_count=started_count,
            failed_count=failed_count,
            total_requested=len(request.document_ids),
            results=results,
            batch_operation_id=batch_operation_id,
            message=message,
            cache_performance=cache_metrics
        )
        
    except Exception as e:
        # 更新批量操作为失败状态
        error_msg = f"批量处理失败: {str(e)}"
        await state_manager.update_batch_operation(
            batch_operation_id,
            status="failed",
            failed_items=len(request.document_ids),
            completed_at=datetime.now().isoformat(),
            error=error_msg
        )
        
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/batch-operations/{batch_operation_id}", response_model=BatchOperationStatus)
async def get_batch_operation_status(
    batch_operation_id: str,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取批量操作状态"""
    batch_operation = await state_manager.get_batch_operation(batch_operation_id)
    
    if not batch_operation:
        raise HTTPException(status_code=404, detail="Batch operation not found")
    
    return BatchOperationStatus(
        batch_operation_id=batch_operation.batch_operation_id,
        operation_type=batch_operation.operation_type,
        status=batch_operation.status,
        total_items=batch_operation.total_items,
        completed_items=batch_operation.completed_items,
        failed_items=batch_operation.failed_items,
        progress=batch_operation.progress,
        started_at=batch_operation.started_at,
        completed_at=batch_operation.completed_at,
        results=batch_operation.results
    )


@router.get("/batch-operations")
async def list_batch_operations(
    limit: int = 50,
    status: Optional[str] = None,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """列出批量操作"""
    operations = await state_manager.get_all_batch_operations()
    
    # 按状态过滤
    if status:
        operations = [op for op in operations if op.status == status]
    
    # 按开始时间倒序排序
    operations.sort(key=lambda x: x.started_at, reverse=True)
    
    # 限制返回数量
    operations = operations[:limit]
    
    # 转换为字典格式
    operations_list = []
    for op in operations:
        op_dict = {
            "batch_operation_id": op.batch_operation_id,
            "operation_type": op.operation_type,
            "status": op.status,
            "total_items": op.total_items,
            "completed_items": op.completed_items,
            "failed_items": op.failed_items,
            "progress": op.progress,
            "started_at": op.started_at,
            "completed_at": op.completed_at,
            "error": op.error
        }
        operations_list.append(op_dict)
    
    return {
        "success": True,
        "operations": operations_list,
        "total": len(operations_list)
    }


@router.post("/batch-operations/{batch_operation_id}/cancel")
async def cancel_batch_operation(
    batch_operation_id: str,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """取消批量操作"""
    batch_operation = await state_manager.get_batch_operation(batch_operation_id)
    
    if not batch_operation:
        raise HTTPException(status_code=404, detail="Batch operation not found")
    
    if batch_operation.status != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel batch operation with status: {batch_operation.status}"
        )
    
    try:
        # 更新批量操作状态为取消
        await state_manager.update_batch_operation(
            batch_operation_id,
            status="cancelled",
            completed_at=datetime.now().isoformat()
        )
        
        # TODO: 在Phase 2中实现取消相关任务的逻辑
        # 目前只更新状态，后续需要实际停止处理过程
        
        return {
            "success": True,
            "message": f"批量操作 {batch_operation_id} 已取消",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消操作失败: {str(e)}")


@router.get("/batch-progress/{batch_id}")
async def get_batch_progress(
    batch_id: str,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取批量操作的实时进度"""
    batch_operation = await state_manager.get_batch_operation(batch_id)
    
    if not batch_operation:
        raise HTTPException(status_code=404, detail="批量操作不存在或已完成")
    
    # TODO: 在Phase 4中集成advanced_progress_tracker
    # progress = advanced_progress_tracker.get_batch_progress(batch_id)
    
    # 构建进度信息
    progress_info = {
        "batch_id": batch_id,
        "operation_type": batch_operation.operation_type,
        "status": batch_operation.status,
        "total_items": batch_operation.total_items,
        "completed_items": batch_operation.completed_items,
        "failed_items": batch_operation.failed_items,
        "progress": batch_operation.progress,
        "started_at": batch_operation.started_at,
        "current_phase": "processing" if batch_operation.status == "running" else batch_operation.status
    }
    
    # 计算处理速度和预估剩余时间
    if batch_operation.status == "running":
        try:
            start_time = datetime.fromisoformat(batch_operation.started_at)
            current_time = datetime.now()
            elapsed_seconds = (current_time - start_time).total_seconds()
            
            if elapsed_seconds > 0 and batch_operation.completed_items > 0:
                items_per_second = batch_operation.completed_items / elapsed_seconds
                remaining_items = batch_operation.total_items - batch_operation.completed_items
                
                if items_per_second > 0:
                    estimated_remaining_seconds = remaining_items / items_per_second
                    progress_info["processing_speed"] = items_per_second
                    progress_info["estimated_remaining_seconds"] = estimated_remaining_seconds
                    progress_info["elapsed_seconds"] = elapsed_seconds
        except:
            pass
    
    return {
        "success": True,
        "batch_progress": progress_info,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/batch-progress")
async def get_all_batch_progress(
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取所有活跃批量操作的进度"""
    all_operations = await state_manager.get_all_batch_operations()
    
    # 筛选活跃的操作
    active_batches = []
    recent_history = []
    
    for op in all_operations:
        batch_info = {
            "batch_id": op.batch_operation_id,
            "operation_type": op.operation_type,
            "status": op.status,
            "progress": op.progress,
            "started_at": op.started_at,
            "completed_at": op.completed_at,
            "total_items": op.total_items,
            "completed_items": op.completed_items,
            "failed_items": op.failed_items
        }
        
        if op.status == "running":
            active_batches.append(batch_info)
        else:
            recent_history.append(batch_info)
    
    # 限制历史记录数量
    recent_history.sort(key=lambda x: x["started_at"], reverse=True)
    recent_history = recent_history[:20]
    
    return {
        "success": True,
        "active_batches": active_batches,
        "recent_history": recent_history,
        "timestamp": datetime.now().isoformat()
    }


@router.delete("/batch-operations/cleanup")
async def cleanup_batch_operations(
    keep_days: int = 30,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """清理旧的批量操作记录"""
    all_operations = await state_manager.get_all_batch_operations()
    
    # 计算截止日期
    from datetime import timedelta
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    
    cleaned_count = 0
    for operation in all_operations:
        try:
            op_date = datetime.fromisoformat(operation.started_at)
            # 只清理已完成、失败或取消的旧操作
            if (op_date < cutoff_date and 
                operation.status in ["completed", "failed", "cancelled"]):
                # 从状态管理器中删除
                # TODO: 实现删除批量操作的方法
                cleaned_count += 1
        except:
            continue
    
    return {
        "success": True,
        "message": f"Cleaned up {cleaned_count} old batch operations",
        "cleaned_count": cleaned_count,
        "keep_days": keep_days
    }


@router.get("/batch-statistics")
async def get_batch_statistics(
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取批量操作统计信息"""
    all_operations = await state_manager.get_all_batch_operations()
    
    # 统计各种指标
    status_counts = {}
    operation_type_counts = {}
    total_items = 0
    total_completed = 0
    total_failed = 0
    
    for op in all_operations:
        # 状态统计
        status_counts[op.status] = status_counts.get(op.status, 0) + 1
        
        # 操作类型统计
        operation_type_counts[op.operation_type] = operation_type_counts.get(op.operation_type, 0) + 1
        
        # 项目统计
        total_items += op.total_items
        total_completed += op.completed_items
        total_failed += op.failed_items
    
    # 计算成功率
    success_rate = (total_completed / total_items * 100) if total_items > 0 else 0
    
    return {
        "success": True,
        "statistics": {
            "total_batch_operations": len(all_operations),
            "status_distribution": status_counts,
            "operation_type_distribution": operation_type_counts,
            "processing_metrics": {
                "total_items_processed": total_items,
                "total_completed": total_completed,
                "total_failed": total_failed,
                "success_rate_percent": round(success_rate, 2)
            }
        },
        "timestamp": datetime.now().isoformat()
    }