"""
API路由模块
包含所有拆分后的路由模块
"""
from . import documents
from . import tasks
from . import batch
from . import query
from . import system
from . import websocket
from . import cache

__all__ = [
    "documents",
    "tasks", 
    "batch",
    "query",
    "system",
    "websocket",
    "cache"
]