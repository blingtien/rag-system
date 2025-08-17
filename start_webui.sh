#!/bin/bash

# RAG-Anything Web UI 启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_message() {
    echo -e "${2}${1}${NC}"
}

print_message "🚀 RAG-Anything Web UI 启动脚本" "$BLUE"
print_message "=================================" "$BLUE"

# 检查Python环境
print_message "📋 检查Python环境..." "$YELLOW"
if ! command -v python3 &> /dev/null; then
    print_message "❌ 错误: 未找到Python3" "$RED"
    exit 1
fi

python_version=$(python3 --version 2>&1 | awk '{print $2}')
print_message "✅ Python版本: $python_version" "$GREEN"

# 检查Node.js环境
print_message "📋 检查Node.js环境..." "$YELLOW"
if ! command -v node &> /dev/null; then
    print_message "❌ 错误: 未找到Node.js" "$RED"
    exit 1
fi

node_version=$(node --version)
print_message "✅ Node.js版本: $node_version" "$GREEN"

# 检查npm
if ! command -v npm &> /dev/null; then
    print_message "❌ 错误: 未找到npm" "$RED"
    exit 1
fi

npm_version=$(npm --version)
print_message "✅ npm版本: $npm_version" "$GREEN"

# 安装后端依赖
print_message "📦 安装后端依赖..." "$YELLOW"
cd web-api
if [ ! -d "venv" ]; then
    print_message "🔧 创建Python虚拟环境..." "$YELLOW"
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt

print_message "✅ 后端依赖安装完成" "$GREEN"

# 安装前端依赖
print_message "📦 安装前端依赖..." "$YELLOW"
cd ../web-ui

if [ ! -d "node_modules" ]; then
    npm install
    print_message "✅ 前端依赖安装完成" "$GREEN"
else
    print_message "✅ 前端依赖已存在" "$GREEN"
fi

# 启动后端服务器（后台运行）
print_message "🔧 启动后端API服务器..." "$YELLOW"
cd ../web-api
source venv/bin/activate

# 检查端口8000是否被占用
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    print_message "⚠️  警告: 端口8000已被占用，尝试终止现有进程..." "$YELLOW"
    pkill -f "uvicorn.*main:app" || true
    sleep 2
fi

# 启动API服务器
nohup python start_server.py --reload > api.log 2>&1 &
API_PID=$!

print_message "✅ 后端API服务器已启动 (PID: $API_PID)" "$GREEN"
print_message "📍 API地址: http://localhost:8000" "$BLUE"
print_message "📚 API文档: http://localhost:8000/docs" "$BLUE"

# 等待API服务器启动
print_message "⏳ 等待API服务器启动..." "$YELLOW"
sleep 5

# 检查API服务器是否启动成功
if curl -s http://localhost:8000/health > /dev/null; then
    print_message "✅ API服务器健康检查通过" "$GREEN"
else
    print_message "❌ API服务器启动失败，请检查日志: web-api/api.log" "$RED"
    exit 1
fi

# 启动前端开发服务器
print_message "🎨 启动前端开发服务器..." "$YELLOW"
cd ../web-ui

# 检查端口3000是否被占用
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null ; then
    print_message "⚠️  警告: 端口3000已被占用，尝试终止现有进程..." "$YELLOW"
    pkill -f "next dev" || true
    sleep 2
fi

print_message "🎉 启动完成！" "$GREEN"
print_message "=================================" "$BLUE"
print_message "🌐 前端地址: http://localhost:3000" "$BLUE"
print_message "🔗 API地址: http://localhost:8000" "$BLUE"
print_message "📖 API文档: http://localhost:8000/docs" "$BLUE"
print_message "=================================" "$BLUE"
print_message "💡 提示: 使用 Ctrl+C 停止服务" "$YELLOW"

# 启动前端（前台运行）
npm run dev

# 如果前端停止了，也停止后端
print_message "🔄 停止后端服务器..." "$YELLOW"
kill $API_PID 2>/dev/null || true

print_message "👋 Web UI已停止" "$BLUE"