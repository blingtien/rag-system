#!/usr/bin/env python3
"""
WebSocket log handler to capture LightRAG logs and broadcast them via WebSocket
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import List, Any, Dict

# 导入智能日志处理器
from intelligent_log_processor import intelligent_log_processor, LogLevel


class WebSocketLogHandler(logging.Handler):
    """Custom logging handler that broadcasts log messages to WebSocket clients"""
    
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.websocket_clients: List[Any] = []
        self.loop = None
        
    def add_websocket_client(self, websocket):
        """Add a WebSocket client for broadcasting"""
        self.websocket_clients.append(websocket)
        
    def remove_websocket_client(self, websocket):
        """Remove a WebSocket client"""
        if websocket in self.websocket_clients:
            self.websocket_clients.remove(websocket)
    
    def emit(self, record):
        """Emit a log record by broadcasting to WebSocket clients"""
        try:
            # Format the log message using LightRAG's native format
            message = self.format(record)
            
            # Determine log level for WebSocket
            level_map = {
                logging.DEBUG: "debug",
                logging.INFO: "info", 
                logging.WARNING: "warning",
                logging.ERROR: "error",
                logging.CRITICAL: "error"
            }
            ws_level = level_map.get(record.levelno, "info")
            
            # 使用智能日志处理器处理日志
            processed_log = intelligent_log_processor.process_log_message(
                message, ws_level, record.name
            )
            
            # 如果日志被过滤掉（重复或不重要），则不发送
            if processed_log is None:
                return
            
            # 创建优化的WebSocket消息
            log_data = {
                "type": "log",
                "id": processed_log.id,
                "level": processed_log.level.value,
                "category": processed_log.category.value,
                "title": processed_log.title,
                "message": processed_log.message,
                "details": processed_log.details,
                "progress": processed_log.progress,
                "metadata": processed_log.metadata,
                "is_milestone": processed_log.is_milestone,
                "group_id": processed_log.group_id,
                "timestamp": processed_log.timestamp.isoformat(),
                "logger_name": record.name,
                "source": "lightrag"
            }
            
            # Broadcast to WebSocket clients (async)
            if self.websocket_clients and self.loop:
                # Schedule the async broadcast
                asyncio.run_coroutine_threadsafe(
                    self._broadcast_to_websockets(log_data), 
                    self.loop
                )
                
        except Exception as e:
            # Don't let logging errors break the application
            print(f"WebSocket log handler error: {e}")
    
    async def _broadcast_to_websockets(self, log_data):
        """Broadcast log data to all WebSocket clients"""
        if not self.websocket_clients:
            return
            
        # Remove disconnected clients
        disconnected_clients = []
        for ws in self.websocket_clients:
            try:
                await ws.send_text(json.dumps(log_data))
            except Exception:
                disconnected_clients.append(ws)
        
        # Clean up disconnected clients
        for ws in disconnected_clients:
            self.websocket_clients.remove(ws)
    
    def set_event_loop(self, loop):
        """Set the event loop for async operations"""
        self.loop = loop


# Global WebSocket log handler instance
websocket_log_handler = WebSocketLogHandler()

def setup_websocket_logging():
    """Setup WebSocket logging to capture LightRAG logs"""
    from lightrag.utils import logger
    
    # Set formatter to match native LightRAG log format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    websocket_log_handler.setFormatter(formatter)
    
    # Add handler to LightRAG logger
    logger.addHandler(websocket_log_handler)
    logger.setLevel(logging.INFO)
    
    return websocket_log_handler

def cleanup_websocket_logging():
    """Remove WebSocket logging handler"""
    from lightrag.utils import logger
    logger.removeHandler(websocket_log_handler)


def get_log_summary(mode: str = "summary", include_debug: bool = False) -> Dict:
    """获取日志摘要"""
    return intelligent_log_processor.get_frontend_log_summary(include_debug)


def get_core_progress() -> List[Dict]:
    """获取核心进度信息"""
    return intelligent_log_processor.get_core_progress_only()


def clear_logs():
    """清空日志"""
    intelligent_log_processor.clear_logs()