#!/bin/bash
# RAG System 一键启动脚本

set -e  # 遇到错误时退出

echo "🚀 启动 RAG System..."
echo "===================="

# 检查必要文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件，正在复制模板..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ 已创建 .env 文件，请编辑配置后重新运行"
        echo "📝 主要需要配置："
        echo "   - DEEPSEEK_API_KEY: DeepSeek API 密钥"
        echo "   - 数据库连接信息（如果不使用默认值）"
        exit 1
    else
        echo "❌ 未找到 .env.example 模板文件"
        exit 1
    fi
fi

echo "📋 检查依赖..."

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 请先安装 Docker"
    exit 1
fi

# 检查 Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ 请先安装 Docker Compose"
    exit 1
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 请先安装 Python 3.9+"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "⚠️  未安装 Node.js，跳过前端启动"
    SKIP_FRONTEND=true
fi

echo "✅ 依赖检查完成"

# 启动数据库
echo "🐘 启动数据库服务..."
docker-compose up -d postgres neo4j redis

# 等待数据库启动
echo "⏳ 等待数据库启动..."
sleep 10

# 检查数据库连接
echo "🔗 检查数据库连接..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if docker-compose exec -T postgres pg_isready -U raganything_user -d raganything > /dev/null 2>&1; then
        echo "✅ PostgreSQL 连接成功"
        break
    fi
    echo "⏳ 等待 PostgreSQL 启动... ($((attempt + 1))/$max_attempts)"
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ PostgreSQL 启动超时"
    exit 1
fi

# 安装 Python 依赖
echo "📦 安装 Python 依赖..."
if [ ! -d "venv" ]; then
    echo "🔧 创建虚拟环境..."
    python3 -m venv venv
fi

echo "🔧 激活虚拟环境并安装依赖..."
source venv/bin/activate
pip install -r RAG-Anything/requirements.txt

# 启动后端 API 服务器
echo "🚀 启动后端服务..."
cd RAG-Anything/api
nohup python rag_api_server.py > ../../api_server.log 2>&1 &
API_PID=$!
cd ../..

echo "✅ 后端服务已启动 (PID: $API_PID)"

# 启动前端（如果可用）
if [ "$SKIP_FRONTEND" != "true" ]; then
    echo "🌐 启动前端服务..."
    cd webui
    
    if [ ! -d "node_modules" ]; then
        echo "📦 安装前端依赖..."
        npm install
    fi
    
    echo "🚀 启动前端开发服务器..."
    nohup npm run dev > ../frontend.log 2>&1 &
    FRONTEND_PID=$!
    cd ..
    
    echo "✅ 前端服务已启动 (PID: $FRONTEND_PID)"
fi

echo ""
echo "🎉 RAG System 启动完成！"
echo "===================="
echo "🔗 访问地址："
echo "   📱 前端界面: http://localhost:3000"
echo "   📋 API 文档: http://localhost:8001/docs"
echo "   🐘 PostgreSQL: localhost:5432"
echo "   🕸️  Neo4j: http://localhost:7474 (neo4j/raganything_neo4j)"
echo ""
echo "📋 进程 ID："
echo "   🔧 API 服务器: $API_PID"
if [ "$SKIP_FRONTEND" != "true" ]; then
    echo "   🌐 前端服务: $FRONTEND_PID"
fi
echo ""
echo "📝 日志文件："
echo "   🔧 API: api_server.log"
if [ "$SKIP_FRONTEND" != "true" ]; then
    echo "   🌐 前端: frontend.log"
fi
echo ""
echo "⏹️  停止服务: ./stop.sh"
echo "📊 查看状态: docker-compose ps"