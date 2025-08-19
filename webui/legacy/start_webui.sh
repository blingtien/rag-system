#!/bin/bash
"""
RAG-Anything WebUI 前端服务器启动脚本
"""

echo "🚀 启动 RAG-Anything WebUI 前端服务器"
echo "端口: 3000"
echo "目录: $(pwd)"
echo ""

# 检查Python是否可用
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未找到，请先安装Python3"
    exit 1
fi

# 启动静态文件服务器
python3 server.py