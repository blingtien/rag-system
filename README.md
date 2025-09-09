# 🚀 RAG System - 智能文档问答系统

基于 LightRAG 和多数据库存储的企业级 RAG（检索增强生成）系统，支持多模态文档解析、知识图谱构建和智能问答。

## 📊 项目架构可视化

```
ragsystem/
├── 🚀 RAG-Anything/           # 核心RAG系统
│   ├── 🌐 api/                # API服务层
│   │   ├── rag_api_server.py         # 主API服务器
│   │   ├── smart_parser_router.py    # 智能解析路由
│   │   ├── cache_enhanced_processor.py # 缓存增强处理
│   │   └── websocket_log_handler.py  # WebSocket日志
│   │
│   └── 🧠 raganything/        # 核心业务层
│       ├── raganything.py            # 主业务逻辑
│       ├── processor.py              # 文档处理器
│       ├── parser.py                 # 解析器框架
│       └── batch.py                  # 批量处理
│
├── 🌐 webui/                  # React前端界面
│   └── src/
│       ├── pages/                    # 页面组件
│       └── components/               # 通用组件
│
├── 📚 LightRAG/               # 上游LightRAG库
├── 🔧 docs/                   # 项目文档
├── 💾 rag_storage/            # RAG数据存储
│   └── graph_chunk_entity_relation.graphml
└── ⚙️  配置文件
    ├── database_config.py
    └── .env
```

## 💾 存储架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RAG System 存储层                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
            ┌───────▼────────┐ ┌────▼─────┐ ┌─────▼──────┐
            │  🐘 PostgreSQL │ │ 🕸️ Neo4j  │ │ 📄 GraphML │
            │                │ │           │ │   文件      │
            │ • 文档状态      │ │ • 实体图谱 │ │ • Chunk关联 │
            │ • KV存储       │ │ • 语义关系 │ │ • 本地图存储 │
            │ • 向量索引     │ │ • 图查询   │ │ • 快速访问  │
            └────────────────┘ └───────────┘ └────────────┘
```

## 🛠️ 技术栈

| 前端层 | API层 | 业务层 | 存储层 | 外部服务 |
|--------|-------|--------|--------|----------|
| React 18 | FastAPI | LightRAG | PostgreSQL | DeepSeek API |
| TypeScript | WebSocket | Python 3.9+ | pgvector | |
| Ant Design | Uvicorn | AsyncIO | Neo4j | Qwen3-Embed |
| D3.js | Pydantic | NetworkX | GraphML | (本地模型) |
| Vite | CORS | Cache | Redis | |

## ✨ 核心特性

### 🎯 智能文档解析
- **多格式支持**: PDF, Word, Excel, PowerPoint, 图片, 视频
- **解析器路由**: 自动选择最优解析引擎 (MinerU, Docling)
- **质量保证**: 多阶段验证和错误恢复机制

### 🧠 知识图谱构建
- **实体抽取**: 基于NLP的智能实体识别
- **关系推理**: 语义关系自动发现和构建
- **混合存储**: Neo4j + GraphML 双存储架构

### 🔍 增强检索系统
- **多路检索**: 向量检索 + 关键词检索 + 图谱检索
- **语义理解**: 基于大模型的深度语义匹配
- **上下文融合**: 多文档信息整合和推理

### ⚡ 性能优化
- **多层缓存**: 解析缓存 + LLM缓存 + 查询缓存
- **批量处理**: 支持并发文档处理
- **实时反馈**: WebSocket 细粒度进度追踪

## 🚀 快速开始

### 环境要求
- Python 3.9+
- Node.js 16+
- PostgreSQL 13+ (with pgvector)
- Neo4j 5.0+
- Docker & Docker Compose

### 安装部署

1. **克隆项目**
```bash
git clone https://github.com/blingtien/ragsystem.git
cd ragsystem
```

2. **环境配置**
```bash
# 复制环境配置
cp .env.example .env
# 编辑配置文件，设置API密钥和数据库连接
nano .env
```

3. **启动数据库**
```bash
# 启动 PostgreSQL 和 Neo4j
docker-compose up -d postgres neo4j
```

4. **安装依赖**
```bash
# Python 后端
cd RAG-Anything
pip install -r requirements.txt

# React 前端
cd ../webui
npm install
```

5. **启动服务**
```bash
# 启动 API 服务器
cd RAG-Anything/api
python rag_api_server.py

# 启动前端 (新终端)
cd webui
npm run dev
```

6. **访问应用**
- 前端界面: http://localhost:3000
- API 文档: http://localhost:8001/docs

## 📊 性能指标

| 处理能力 | 存储规模 | 响应性能 |
|----------|----------|----------|
| 文档解析: 2-5秒/PDF页 | 单文档: 100MB | 查询响应: 200-800ms |
| 并发处理: 可配置线程数 | 知识图谱: 百万级实体关系 | 实时通信: WebSocket推送 |

## 📚 详细文档

- [项目架构概览](docs/project-architecture-overview.md)
- [存储架构分析](docs/lightrag-storage-architecture-analysis.md)
- [API 接口文档](RAG-Anything/api/README.md)
- [部署指南](docs/deployment-guide.md)

## 🔧 配置说明

### 数据库配置
系统采用混合存储架构，各数据库分工明确：

- **PostgreSQL**: 文档状态、KV存储、向量索引
- **Neo4j**: 实体图谱、语义关系、图查询
- **GraphML**: Chunk-实体关联、本地图存储
- **Redis**: 缓存层、会话管理（可选）

### LLM 配置
支持多种大语言模型：

```bash
# DeepSeek API (推荐)
OPENAI_API_KEY=your_deepseek_key
OPENAI_BASE_URL=https://api.deepseek.com/v1

# 本地嵌入模型
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
EMBEDDING_MODEL_TYPE=local
```

## 🤝 贡献指南

1. Fork 本项目
2. 创建特性分支: `git checkout -b feature/your-feature`
3. 提交更改: `git commit -am 'Add some feature'`
4. 推送分支: `git push origin feature/your-feature`
5. 提交 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

- [LightRAG](https://github.com/HKUDS/LightRAG) - 核心RAG框架
- [MinerU](https://github.com/opendatalab/MinerU) - PDF解析引擎
- [Neo4j](https://neo4j.com/) - 图数据库支持
- [PostgreSQL](https://postgresql.org/) - 关系数据库支持

---

⭐ 如果这个项目对你有帮助，请给一个 Star！

📧 问题反馈：[Issues](https://github.com/blingtien/ragsystem/issues)