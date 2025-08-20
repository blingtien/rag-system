#!/usr/bin/env python3
"""
Progress callback system for real-time WebSocket updates during document processing
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ProgressUpdate:
    """Progress update data structure"""
    stage: str
    message: str
    progress_percent: float
    timestamp: str
    level: str = "info"
    details: Optional[Dict[str, Any]] = None

class ProgressCallback:
    """Progress callback manager for real-time updates"""
    
    def __init__(self):
        self.callbacks: List[Callable[[ProgressUpdate], None]] = []
        self.websocket_clients: List[Any] = []  # WebSocket connections
        
    def add_callback(self, callback: Callable[[ProgressUpdate], None]):
        """Add a progress callback function"""
        self.callbacks.append(callback)
    
    def add_websocket_client(self, websocket):
        """Add a WebSocket client for broadcasting"""
        self.websocket_clients.append(websocket)
    
    def remove_websocket_client(self, websocket):
        """Remove a WebSocket client"""
        if websocket in self.websocket_clients:
            self.websocket_clients.remove(websocket)
    
    async def emit_progress(
        self, 
        stage: str, 
        message: str, 
        progress_percent: float, 
        level: str = "info",
        details: Optional[Dict[str, Any]] = None
    ):
        """Emit a progress update to all registered callbacks and WebSocket clients"""
        update = ProgressUpdate(
            stage=stage,
            message=message,
            progress_percent=progress_percent,
            timestamp=datetime.now().isoformat(),
            level=level,
            details=details or {}
        )
        
        # Call registered callbacks
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(update)
                else:
                    callback(update)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
        
        # Broadcast to WebSocket clients
        await self._broadcast_to_websockets(update)
    
    async def _broadcast_to_websockets(self, update: ProgressUpdate):
        """Broadcast progress update to all WebSocket clients"""
        if not self.websocket_clients:
            return
            
        log_data = {
            "type": "log",
            "level": update.level,
            "message": update.message,
            "timestamp": update.timestamp,
            "stage": update.stage,
            "progress": update.progress_percent,
            "details": update.details
        }
        
        # Remove disconnected clients
        disconnected_clients = []
        for ws in self.websocket_clients:
            try:
                await ws.send_text(json.dumps(log_data))
            except Exception as e:
                logger.debug(f"WebSocket send failed, removing client: {e}")
                disconnected_clients.append(ws)
        
        # Clean up disconnected clients
        for ws in disconnected_clients:
            self.websocket_clients.remove(ws)

# Global progress callback instance
progress_callback = ProgressCallback()

class AsyncProgressReporter:
    """Async context manager for reporting progress during long operations"""
    
    def __init__(self, stage: str, total_steps: int, callback: ProgressCallback):
        self.stage = stage
        self.total_steps = total_steps
        self.current_step = 0
        self.callback = callback
        
    async def __aenter__(self):
        await self.callback.emit_progress(
            self.stage, 
            f"开始{self.stage}", 
            0.0, 
            "info"
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self.callback.emit_progress(
                self.stage, 
                f"{self.stage}完成", 
                100.0, 
                "success"
            )
        else:
            await self.callback.emit_progress(
                self.stage, 
                f"{self.stage}失败: {str(exc_val)}", 
                self.current_step / self.total_steps * 100, 
                "error"
            )
    
    async def update_progress(self, step_message: str, increment: int = 1):
        """Update progress with a specific message"""
        self.current_step += increment
        progress = min(self.current_step / self.total_steps * 100, 100.0)
        
        await self.callback.emit_progress(
            self.stage,
            step_message,
            progress,
            "info"
        )

def create_progress_reporter(stage: str, total_steps: int) -> AsyncProgressReporter:
    """Create a progress reporter for a specific stage"""
    return AsyncProgressReporter(stage, total_steps, progress_callback)