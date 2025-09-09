#!/bin/bash
# RAG System 停止脚本

echo "🛑 停止 RAG System..."
echo "===================="

# 停止 Python 后端进程
echo "🔧 停止后端服务..."
pkill -f "python rag_api_server.py" || true

# 停止前端进程
echo "🌐 停止前端服务..."
pkill -f "npm run dev" || true
pkill -f "vite" || true

# 停止数据库容器
echo "🗄️ 停止数据库服务..."
docker-compose down

# 清理日志文件（可选）
if [ "$1" = "--clean" ]; then
    echo "🧹 清理日志文件..."
    rm -f api_server.log frontend.log
    echo "✅ 日志文件已清理"
fi

echo ""
echo "✅ RAG System 已停止"
echo ""
echo "💡 提示："
echo "   🔄 重新启动: ./start.sh"
echo "   📋 查看状态: docker-compose ps"
echo "   🧹 停止并清理日志: ./stop.sh --clean"