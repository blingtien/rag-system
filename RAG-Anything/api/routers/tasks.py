"""
任务管理路由
处理任务查询、状态获取、取消等相关的API端点
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends

from config.dependencies import get_state_manager_singleton
from core.state_manager import StateManager, Task


router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.get("/")
async def list_tasks(
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取任务列表"""
    tasks = await state_manager.get_all_tasks()
    active_tasks = await state_manager.get_active_tasks()
    
    # 转换为字典格式，保持向后兼容
    task_list = []
    for task in tasks:
        task_dict = {
            "task_id": task.task_id,
            "status": task.status,
            "stage": task.stage,
            "progress": task.progress,
            "file_path": task.file_path,
            "file_name": task.file_name,
            "file_size": task.file_size,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "document_id": task.document_id,
            "total_stages": task.total_stages,
            "stage_details": task.stage_details,
            "multimodal_stats": task.multimodal_stats,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "error_message": task.error_message,
            "batch_operation_id": task.batch_operation_id,
            "parser_info": task.parser_info
        }
        task_list.append(task_dict)
    
    return {
        "success": True,
        "tasks": task_list,
        "total_count": len(task_list),
        "active_tasks": len(active_tasks)
    }


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取特定任务"""
    task = await state_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 转换为字典格式
    task_dict = {
        "task_id": task.task_id,
        "status": task.status,
        "stage": task.stage,
        "progress": task.progress,
        "file_path": task.file_path,
        "file_name": task.file_name,
        "file_size": task.file_size,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "document_id": task.document_id,
        "total_stages": task.total_stages,
        "stage_details": task.stage_details,
        "multimodal_stats": task.multimodal_stats,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
        "error_message": task.error_message,
        "batch_operation_id": task.batch_operation_id,
        "parser_info": task.parser_info
    }
    
    return {
        "success": True,
        "task": task_dict
    }


@router.get("/{task_id}/detailed-status")
async def get_detailed_task_status(
    task_id: str,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取任务的详细状态信息"""
    task = await state_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # TODO: 在Phase 2中实现详细状态跟踪
    # 目前返回基本信息，后续可以集成detailed_status_tracker
    try:
        # 尝试导入详细状态跟踪器
        from detailed_status_tracker import detailed_tracker
        detailed_status = detailed_tracker.get_status(task_id)
        
        if detailed_status:
            return {
                "success": True,
                "task_id": task_id,
                "has_detailed_status": True,
                "detailed_status": detailed_status.to_dict()
            }
    except ImportError:
        pass
    
    # 如果没有详细状态跟踪器，返回基本任务信息
    return {
        "success": True,
        "task_id": task_id,
        "has_detailed_status": False,
        "message": "详细状态跟踪不可用",
        "basic_task_info": {
            "status": task.status,
            "stage": task.stage,
            "progress": task.progress,
            "stage_details": task.stage_details,
            "multimodal_stats": task.multimodal_stats
        }
    }


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """取消任务"""
    task = await state_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status == "running":
        # 更新任务状态为取消
        await state_manager.update_task(
            task_id,
            status="cancelled",
            updated_at=datetime.now().isoformat()
        )
        
        # 更新关联的文档状态
        if task.document_id:
            await state_manager.update_document_status(
                task.document_id,
                "failed",
                error_message="Task cancelled by user",
                updated_at=datetime.now().isoformat()
            )
        
        # TODO: 在Phase 5中实现WebSocket连接关闭
        # websocket = await state_manager.get_websocket(task_id)
        # if websocket:
        #     try:
        #         await websocket.close()
        #     except:
        #         pass
        #     await state_manager.remove_websocket(task_id)
    
    return {
        "success": True,
        "message": "Task cancelled successfully"
    }


@router.get("/{task_id}/progress")
async def get_task_progress(
    task_id: str,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取任务进度信息"""
    task = await state_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 计算总体进度信息
    progress_info = {
        "task_id": task_id,
        "status": task.status,
        "overall_progress": task.progress,
        "current_stage": task.stage,
        "stage_details": task.stage_details,
        "multimodal_stats": task.multimodal_stats,
        "timestamps": {
            "created_at": task.created_at,
            "started_at": task.started_at,
            "updated_at": task.updated_at,
            "completed_at": task.completed_at
        }
    }
    
    # 计算处理时间
    if task.started_at and task.completed_at:
        try:
            start_time = datetime.fromisoformat(task.started_at)
            end_time = datetime.fromisoformat(task.completed_at)
            progress_info["processing_duration"] = (end_time - start_time).total_seconds()
        except:
            progress_info["processing_duration"] = None
    elif task.started_at:
        try:
            start_time = datetime.fromisoformat(task.started_at)
            current_time = datetime.now()
            progress_info["current_duration"] = (current_time - start_time).total_seconds()
        except:
            progress_info["current_duration"] = None
    
    # 估算剩余时间（基于当前进度）
    if task.status == "running" and task.progress > 0:
        try:
            if "current_duration" in progress_info:
                elapsed = progress_info["current_duration"]
                estimated_total = elapsed / (task.progress / 100)
                progress_info["estimated_remaining"] = estimated_total - elapsed
        except:
            pass
    
    return {
        "success": True,
        "progress": progress_info
    }


@router.get("/status/{status}")
async def get_tasks_by_status(
    status: str,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """根据状态筛选任务"""
    all_tasks = await state_manager.get_all_tasks()
    filtered_tasks = [task for task in all_tasks if task.status == status]
    
    # 转换为字典格式
    task_list = []
    for task in filtered_tasks:
        task_dict = {
            "task_id": task.task_id,
            "status": task.status,
            "stage": task.stage,
            "progress": task.progress,
            "file_name": task.file_name,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "document_id": task.document_id
        }
        task_list.append(task_dict)
    
    return {
        "success": True,
        "status_filter": status,
        "tasks": task_list,
        "count": len(task_list)
    }


@router.delete("/cleanup")
async def cleanup_old_tasks(
    keep_days: int = 7,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """清理旧任务（保留最近N天的任务）"""
    all_tasks = await state_manager.get_all_tasks()
    
    # 计算截止日期
    from datetime import timedelta
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    
    cleaned_count = 0
    for task in all_tasks:
        try:
            task_date = datetime.fromisoformat(task.created_at)
            # 只清理已完成或失败的旧任务
            if (task_date < cutoff_date and 
                task.status in ["completed", "failed", "cancelled"]):
                await state_manager.remove_task(task.task_id)
                cleaned_count += 1
        except:
            continue
    
    return {
        "success": True,
        "message": f"Cleaned up {cleaned_count} old tasks",
        "cleaned_count": cleaned_count,
        "keep_days": keep_days
    }


@router.get("/statistics/summary")
async def get_task_statistics(
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """获取任务统计摘要"""
    all_tasks = await state_manager.get_all_tasks()
    
    # 按状态统计
    status_counts = {}
    stage_counts = {}
    total_processing_time = 0
    successful_tasks = 0
    
    for task in all_tasks:
        # 状态统计
        status_counts[task.status] = status_counts.get(task.status, 0) + 1
        
        # 阶段统计（仅限正在运行的任务）
        if task.status == "running":
            stage_counts[task.stage] = stage_counts.get(task.stage, 0) + 1
        
        # 处理时间统计（已完成的任务）
        if task.status == "completed" and task.started_at and task.completed_at:
            try:
                start_time = datetime.fromisoformat(task.started_at)
                end_time = datetime.fromisoformat(task.completed_at)
                duration = (end_time - start_time).total_seconds()
                total_processing_time += duration
                successful_tasks += 1
            except:
                pass
    
    # 计算平均处理时间
    avg_processing_time = total_processing_time / successful_tasks if successful_tasks > 0 else 0
    
    return {
        "success": True,
        "statistics": {
            "total_tasks": len(all_tasks),
            "status_distribution": status_counts,
            "current_stage_distribution": stage_counts,
            "performance_metrics": {
                "total_processing_time_seconds": total_processing_time,
                "successful_tasks": successful_tasks,
                "average_processing_time_seconds": avg_processing_time,
                "success_rate": (successful_tasks / len(all_tasks) * 100) if all_tasks else 0
            }
        },
        "timestamp": datetime.now().isoformat()
    }