#!/usr/bin/env python3
"""
RAG-Anything Web API 启动脚本
"""

import os
import sys
import argparse
import uvicorn
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="启动RAG-Anything Web API服务器")
    parser.add_argument("--host", default="0.0.0.0", help="服务器主机地址")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口")
    parser.add_argument("--reload", action="store_true", help="启用热重载（开发模式）")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"], help="日志级别")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数")
    
    args = parser.parse_args()
    
    # 设置环境变量
    os.environ.setdefault("PYTHONPATH", str(Path(__file__).parent.parent))
    
    print(f"🚀 启动RAG-Anything Web API服务器")
    print(f"📍 地址: http://{args.host}:{args.port}")
    print(f"📚 API文档: http://{args.host}:{args.port}/docs")
    print(f"🔧 重载模式: {'开启' if args.reload else '关闭'}")
    print(f"📊 日志级别: {args.log_level}")
    print("=" * 50)
    
    # 启动服务器
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
        workers=args.workers if not args.reload else 1,  # 重载模式下只能用单进程
        access_log=True
    )

if __name__ == "__main__":
    main()