#!/usr/bin/env python3
"""
RAG System 项目结构 ASCII 可视化
在终端中展示项目架构和组件关系
"""

def print_project_structure():
    """打印项目结构树"""
    print("═" * 80)
    print("🚀 RAG System 项目架构可视化")
    print("═" * 80)
    
    structure = """
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
"""
    print(structure)

def print_storage_architecture():
    """打印存储架构图"""
    print("\n" + "═" * 80)
    print("💾 存储架构图")
    print("═" * 80)
    
    storage_diagram = """
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
                    │               │               │
            ┌───────▼────────┐ ┌────▼─────┐ ┌─────▼──────┐
            │ 553个实体节点  │ │ 369个关系 │ │ 484个节点  │
            │ lightrag_*表   │ │ 图谱推理  │ │ 362条边    │
            └────────────────┘ └───────────┘ └────────────┘
"""
    print(storage_diagram)

def print_data_flow():
    """打印数据流程图"""
    print("\n" + "═" * 80)
    print("🔄 数据流程图")
    print("═" * 80)
    
    flow_diagram = """
📄 文档上传 → 🔍 格式识别 → 🧠 智能解析 → 📊 内容提取 → 🏗️ 结构化处理
     │             │             │             │             │
     ▼             ▼             ▼             ▼             ▼
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│  Web UI │   │ Parser  │   │ MinerU  │   │ Extract │   │ Chunks  │
│         │   │ Router  │   │ Docling │   │ Content │   │ Vector  │
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘
                                              │
                            ┌─────────────────┼─────────────────┐
                            │                 │                 │
                       ┌────▼─────┐     ┌────▼──┐       ┌─────▼──────┐
                       │ 🧠 实体识别 │     │ 🔗 关系 │       │ 🗂️ 知识图谱  │
                       │          │     │   抽取  │       │           │
                       └──────────┘     └───────┘       └────────────┘
                            │                 │                 │
                            ▼                 ▼                 ▼
                    ┌───────────────────────────────────────────────────┐
                    │              💾 多层存储系统                        │
                    │  PostgreSQL + Neo4j + GraphML + Redis(可选)      │
                    └───────────────────────────────────────────────────┘

❓ 用户查询 → 🧠 语义理解 → 🔍 多路检索 → 🎯 结果融合 → ✨ 答案生成 → 📤 返回结果
"""
    print(flow_diagram)

def print_component_relationships():
    """打印组件关系图"""
    print("\n" + "═" * 80)
    print("🔗 组件关系图")
    print("═" * 80)
    
    components = """
                          ┌─────────────────┐
                          │   🌐 Web UI     │
                          │   (React)       │
                          └─────────┬───────┘
                                    │ HTTP/WebSocket
                          ┌─────────▼───────┐
                          │  🎯 API Gateway │
                          │   (FastAPI)     │
                          └─────────┬───────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
    ┌───────▼──────┐        ┌──────▼──────┐        ┌──────▼──────┐
    │ 🧠 智能路由    │        │ 📄 文档处理   │        │ 🕸️ 知识图谱  │
    │ Smart Router │        │ Processor    │        │ Graph KG   │
    └───────┬──────┘        └──────┬──────┘        └──────┬──────┘
            │                      │                      │
            └──────────────────────┼──────────────────────┘
                                   │
                          ┌────────▼────────┐
                          │  💾 存储层       │
                          │  Storage Layer  │
                          └─────────────────┘
"""
    print(components)

def print_technology_stack():
    """打印技术栈"""
    print("\n" + "═" * 80)
    print("🛠️ 技术栈")
    print("═" * 80)
    
    tech_stack = """
┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│   前端层     │   API层     │   业务层     │   存储层     │   外部服务   │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ React 18    │ FastAPI     │ LightRAG    │ PostgreSQL  │ DeepSeek    │
│ TypeScript  │ WebSocket   │ Python 3.9+ │ pgvector    │ API         │
│ Ant Design  │ Uvicorn     │ AsyncIO     │ Neo4j       │             │
│ D3.js       │ Pydantic    │ NetworkX    │ GraphML     │ Qwen3-Embed │
│ Vite        │ CORS        │ Cache       │ Redis       │ (本地模型)   │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘

📦 解析引擎:        🎯 模型集成:        🔧 开发工具:
├─ MinerU (PDF)     ├─ DeepSeek LLM     ├─ Docker Compose
├─ Docling          ├─ 本地 Embedding   ├─ Environment Config
└─ 多模态支持       └─ 智能缓存机制     └─ Git 版本控制
"""
    print(tech_stack)

def print_performance_metrics():
    """打印性能指标"""
    print("\n" + "═" * 80)
    print("📊 系统性能指标")
    print("═" * 80)
    
    metrics = """
╔═══════════════╦══════════════════╦══════════════════╗
║   处理能力     ║     存储规模      ║    响应性能       ║
╠═══════════════╬══════════════════╬══════════════════╣
║ 文档解析      ║ 单文档: 100MB    ║ 查询响应: 200-800ms ║
║ 2-5秒/PDF页   ║ 总容量: 无限制   ║ 批量处理: 并发     ║
║               ║                  ║                  ║
║ 并发处理      ║ 知识图谱         ║ 实时通信          ║
║ 可配置线程数  ║ 百万级实体关系   ║ WebSocket推送     ║
╚═══════════════╩══════════════════╩══════════════════╝

🎯 架构优势:
• 混合存储: 充分发挥不同数据库优势
• 智能路由: 自动选择最优解析策略
• 实时反馈: WebSocket 细粒度进度追踪
• 缓存优化: 多层缓存提升性能
"""
    print(metrics)

def main():
    """主函数"""
    print_project_structure()
    print_storage_architecture() 
    print_data_flow()
    print_component_relationships()
    print_technology_stack()
    print_performance_metrics()
    
    print("\n" + "═" * 80)
    print("✅ RAG System 项目结构可视化完成")
    print("📁 详细文档位置: /home/ragsvr/projects/ragsystem/docs/")
    print("═" * 80)

if __name__ == "__main__":
    main()