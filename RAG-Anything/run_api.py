#!/usr/bin/env python3
"""
RAG-Anything API启动脚本

用于启动和测试RAG-Anything API服务的脚本。
"""

import os
import sys
import asyncio
import uvicorn
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """启动RAG-Anything API服务器"""
    print("=" * 60)
    print("🚀 启动 RAG-Anything API 服务器")
    print("=" * 60)
    
    # 设置环境变量
    os.environ.setdefault("WORKING_DIR", "./rag_storage")
    os.environ.setdefault("OUTPUT_DIR", "./output")
    os.environ.setdefault("PARSER", "mineru")
    os.environ.setdefault("PARSE_METHOD", "auto")
    os.environ.setdefault("API_HOST", "127.0.0.1")
    os.environ.setdefault("API_PORT", "8000")
    os.environ.setdefault("MAX_CONCURRENT_TASKS", "3")
    
    print("🔧 环境配置:")
    print(f"   工作目录: {os.environ.get('WORKING_DIR')}")
    print(f"   输出目录: {os.environ.get('OUTPUT_DIR')}")
    print(f"   解析器: {os.environ.get('PARSER')}")
    print(f"   主机地址: {os.environ.get('API_HOST')}:{os.environ.get('API_PORT')}")
    print()
    
    # 创建必要的目录
    Path(os.environ.get("WORKING_DIR", "./rag_storage")).mkdir(parents=True, exist_ok=True)
    Path(os.environ.get("OUTPUT_DIR", "./output")).mkdir(parents=True, exist_ok=True)
    Path("./temp_uploads").mkdir(parents=True, exist_ok=True)
    Path("./storage").mkdir(parents=True, exist_ok=True)
    
    print("📁 创建目录结构完成")
    print()
    
    print("🌐 API 端点:")
    host = os.environ.get("API_HOST", "127.0.0.1")
    port = int(os.environ.get("API_PORT", "8000"))
    print(f"   📖 API文档: http://{host}:{port}/docs")
    print(f"   🔍 健康检查: http://{host}:{port}/health")
    print(f"   📤 文档上传: http://{host}:{port}/api/v1/documents/upload")
    print(f"   📋 任务列表: http://{host}:{port}/api/v1/tasks")
    print()
    
    try:
        # 启动FastAPI服务器
        uvicorn.run(
            "api.main:app",
            host=host,
            port=port,
            reload=True,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n🛑 服务器已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()