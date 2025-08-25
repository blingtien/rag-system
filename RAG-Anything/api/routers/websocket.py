"""
WebSocket路由
处理实时通信、进度推送等WebSocket相关的API端点
"""
import asyncio
import json
import logging
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from config.dependencies import get_state_manager_singleton
from core.state_manager import StateManager


router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/task/{task_id}")
async def websocket_task_endpoint(
    websocket: WebSocket,
    task_id: str,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """任务进度WebSocket端点"""
    await websocket.accept()
    await state_manager.add_websocket(task_id, websocket)
    
    try:
        # 发送当前任务状态
        task = await state_manager.get_task(task_id)
        if task:
            task_dict = {
                "task_id": task.task_id,
                "status": task.status,
                "stage": task.stage,
                "progress": task.progress,
                "file_name": task.file_name,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "stage_details": task.stage_details,
                "multimodal_stats": task.multimodal_stats
            }
            await websocket.send_text(json.dumps(task_dict))
        
        # 保持连接，监听客户端消息
        while True:
            try:
                # 等待客户端消息（心跳或命令）
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # 处理客户端消息
                try:
                    data = json.loads(message)
                    await _handle_websocket_message(websocket, task_id, data, state_manager)
                except json.JSONDecodeError:
                    # 忽略非JSON消息（可能是心跳）
                    pass
                    
            except asyncio.TimeoutError:
                # 发送心跳检查连接
                await websocket.send_text(json.dumps({"type": "ping", "timestamp": ""}))
                continue
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
    finally:
        await state_manager.remove_websocket(task_id)


@router.websocket("/api/v1/documents/progress")
async def websocket_processing_logs(
    websocket: WebSocket,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """文档解析过程日志WebSocket端点"""
    # Check origin header for CORS compliance
    origin = websocket.headers.get("origin")
    logger.info(f"WebSocket connection attempt from origin: {origin}")
    
    await websocket.accept()
    await state_manager.add_processing_websocket(websocket)
    
    try:
        # 发送连接确认
        welcome_message = {
            "type": "connection",
            "message": "WebSocket连接已建立，准备接收实时日志...",
            "level": "info",
            "timestamp": ""
        }
        await websocket.send_text(json.dumps(welcome_message))
        
        # 保持连接
        while True:
            try:
                # 等待客户端消息或超时
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # 处理客户端消息
                try:
                    data = json.loads(message)
                    await _handle_processing_websocket_message(websocket, data, state_manager)
                except json.JSONDecodeError:
                    pass
                    
            except asyncio.TimeoutError:
                # 发送心跳
                ping_message = {
                    "type": "ping",
                    "timestamp": ""
                }
                await websocket.send_text(json.dumps(ping_message))
                continue
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error(f"处理日志WebSocket错误: {e}")
    finally:
        await state_manager.remove_processing_websocket(websocket)


@router.websocket("/ws/system/status")
async def websocket_system_status(
    websocket: WebSocket,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """系统状态WebSocket端点 - 实时系统监控"""
    await websocket.accept()
    
    try:
        # 发送初始系统状态
        await _send_system_status(websocket, state_manager)
        
        # 定期发送系统状态更新
        while True:
            try:
                # 每30秒发送一次系统状态
                await asyncio.sleep(30)
                await _send_system_status(websocket, state_manager)
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"系统状态WebSocket发送失败: {e}")
                break
                
    except Exception as e:
        logger.error(f"系统状态WebSocket错误: {e}")


@router.websocket("/ws/batch/{batch_id}/progress")
async def websocket_batch_progress(
    websocket: WebSocket,
    batch_id: str,
    state_manager: StateManager = Depends(get_state_manager_singleton)
):
    """批量操作进度WebSocket端点"""
    await websocket.accept()
    
    try:
        # 发送初始批量操作状态
        batch_operation = await state_manager.get_batch_operation(batch_id)
        if batch_operation:
            batch_dict = {
                "type": "batch_status",
                "batch_id": batch_id,
                "status": batch_operation.status,
                "progress": batch_operation.progress,
                "total_items": batch_operation.total_items,
                "completed_items": batch_operation.completed_items,
                "failed_items": batch_operation.failed_items
            }
            await websocket.send_text(json.dumps(batch_dict))
        
        # 监控批量操作进度
        while True:
            try:
                # 检查批量操作状态变化
                await asyncio.sleep(2)  # 每2秒检查一次
                
                current_batch = await state_manager.get_batch_operation(batch_id)
                if current_batch:
                    progress_update = {
                        "type": "progress_update",
                        "batch_id": batch_id,
                        "status": current_batch.status,
                        "progress": current_batch.progress,
                        "completed_items": current_batch.completed_items,
                        "failed_items": current_batch.failed_items
                    }
                    await websocket.send_text(json.dumps(progress_update))
                    
                    # 如果批量操作已完成，发送完成消息并退出
                    if current_batch.status in ["completed", "failed", "cancelled"]:
                        completion_message = {
                            "type": "batch_completed",
                            "batch_id": batch_id,
                            "final_status": current_batch.status,
                            "results": current_batch.results
                        }
                        await websocket.send_text(json.dumps(completion_message))
                        break
                else:
                    # 批量操作不存在，可能已被删除
                    break
                    
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error(f"批量进度WebSocket错误: {e}")


async def _handle_websocket_message(
    websocket: WebSocket,
    task_id: str,
    data: dict,
    state_manager: StateManager
):
    """处理任务WebSocket消息"""
    message_type = data.get("type", "")
    
    if message_type == "get_status":
        # 客户端请求当前状态
        task = await state_manager.get_task(task_id)
        if task:
            task_dict = {
                "type": "task_status",
                "task_id": task.task_id,
                "status": task.status,
                "stage": task.stage,
                "progress": task.progress,
                "stage_details": task.stage_details
            }
            await websocket.send_text(json.dumps(task_dict))
    
    elif message_type == "cancel_task":
        # 客户端请求取消任务
        task = await state_manager.get_task(task_id)
        if task and task.status == "running":
            await state_manager.update_task(task_id, status="cancelled")
            
            response = {
                "type": "task_cancelled",
                "task_id": task_id,
                "message": "任务已取消"
            }
            await websocket.send_text(json.dumps(response))
    
    elif message_type == "ping":
        # 心跳响应
        pong = {
            "type": "pong",
            "timestamp": data.get("timestamp", "")
        }
        await websocket.send_text(json.dumps(pong))


async def _handle_processing_websocket_message(
    websocket: WebSocket,
    data: dict,
    state_manager: StateManager
):
    """处理处理日志WebSocket消息"""
    message_type = data.get("type", "")
    
    if message_type == "set_log_level":
        # 客户端设置日志级别
        log_level = data.get("level", "info")
        response = {
            "type": "log_level_set",
            "level": log_level,
            "message": f"日志级别已设置为: {log_level}"
        }
        await websocket.send_text(json.dumps(response))
    
    elif message_type == "get_recent_logs":
        # 客户端请求最近的日志
        # TODO: 在Phase 3中集成日志系统
        logs = []
        
        response = {
            "type": "recent_logs",
            "logs": logs,
            "count": len(logs)
        }
        await websocket.send_text(json.dumps(response))


async def _send_system_status(websocket: WebSocket, state_manager: StateManager):
    """发送系统状态信息"""
    try:
        # 获取系统统计
        stats = await state_manager.get_statistics()
        
        # 构建系统状态消息
        system_status = {
            "type": "system_status",
            "timestamp": "",
            "statistics": stats,
            "services": {
                "api_server": "running",
                "state_manager": "running",
                "websocket": "running"
            }
        }
        
        await websocket.send_text(json.dumps(system_status))
        
    except Exception as e:
        logger.error(f"发送系统状态失败: {e}")


# WebSocket管理工具函数
async def broadcast_to_processing_websockets(
    message: dict,
    state_manager: StateManager
):
    """向所有处理日志WebSocket广播消息"""
    websockets = await state_manager.get_processing_websockets()
    
    if websockets:
        message_text = json.dumps(message)
        
        # 并发发送消息到所有连接
        tasks = []
        for ws in websockets:
            tasks.append(_safe_send_websocket_message(ws, message_text))
        
        await asyncio.gather(*tasks, return_exceptions=True)


async def send_task_update(
    task_id: str,
    task_data: dict,
    state_manager: StateManager
):
    """发送任务更新到对应的WebSocket连接"""
    websocket = await state_manager.get_websocket(task_id)
    
    if websocket:
        message = {
            "type": "task_update",
            **task_data
        }
        await _safe_send_websocket_message(websocket, json.dumps(message))


async def _safe_send_websocket_message(websocket: WebSocket, message: str):
    """安全地发送WebSocket消息，处理连接断开"""
    try:
        await websocket.send_text(message)
    except Exception as e:
        logger.debug(f"WebSocket发送失败: {e}")
        # 连接已断开，忽略错误