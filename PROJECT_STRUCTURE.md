# RAG-Anything Web UI 项目结构

## 📁 项目总览

```
ragsystem/
├── RAG-Anything/                    # 原始RAG-Anything核心系统
│   ├── raganything/                 # 核心Python包
│   │   ├── __init__.py
│   │   ├── raganything.py          # 主要orchestrator类
│   │   ├── config.py               # 配置管理
│   │   ├── parser.py               # 文档解析器
│   │   ├── query.py                # 查询功能
│   │   ├── processor.py            # 文档处理
│   │   ├── modalprocessors.py      # 多模态处理器
│   │   └── utils.py                # 工具函数
│   ├── examples/                   # 示例脚本
│   ├── docs/                       # 文档
│   └── requirements.txt            # Python依赖
│
├── web-ui/                         # React前端应用
│   ├── app/                        # Next.js App Router
│   │   ├── page.tsx                # 主页面
│   │   └── globals.css             # 全局样式
│   ├── components/                 # React组件
│   │   ├── ui/                     # 基础UI组件
│   │   │   └── sidebar.tsx         # 侧边栏组件
│   │   ├── RAGDashboard.tsx        # 主仪表盘
│   │   ├── DocumentUpload.tsx      # 文档上传
│   │   ├── QueryInterface.tsx      # 查询界面
│   │   ├── SystemStatus.tsx        # 系统状态
│   │   └── ConfigurationPanel.tsx  # 配置面板
│   ├── lib/                        # 工具库
│   │   └── utils.ts                # 工具函数
│   ├── package.json                # Node.js依赖
│   ├── next.config.js              # Next.js配置
│   ├── tailwind.config.js          # Tailwind配置
│   └── tsconfig.json               # TypeScript配置
│
├── web-api/                        # FastAPI后端服务
│   ├── main.py                     # 主API服务器
│   ├── start_server.py             # 启动脚本
│   ├── requirements.txt            # Python依赖
│   └── api.log                     # 运行日志
│
├── start_webui.sh                  # Web UI启动脚本
├── WEBUI_README.md                 # Web UI文档
├── PROJECT_STRUCTURE.md            # 本文件
└── CLAUDE.md                       # 项目指导文档
```

## 🏗️ 架构说明

### 前端层 (web-ui/)
- **技术栈**：React 18 + Next.js 14 + TypeScript + Tailwind CSS
- **主要功能**：
  - 用户界面展示
  - 文件上传和管理
  - 查询输入和结果展示
  - 系统监控和配置
  - 实时状态更新

### API层 (web-api/)
- **技术栈**：FastAPI + Uvicorn + Pydantic
- **主要功能**：
  - RESTful API接口
  - 文件处理和存储
  - 查询转发和结果返回
  - 系统状态监控
  - 配置管理

### 核心层 (RAG-Anything/)
- **技术栈**：Python + LightRAG + MinerU + 多模态处理器
- **主要功能**：
  - 文档解析和处理
  - 多模态内容分析
  - 向量检索和知识图谱
  - 智能查询和生成

## 🔄 数据流

```
┌─────────────┐    HTTP/WebSocket    ┌─────────────┐    Python调用    ┌─────────────┐
│   前端UI    │ ─────────────────── │  API服务器  │ ─────────────── │ RAG核心系统  │
│             │                      │             │                  │             │
│ React组件   │ ◄─────────────────── │ FastAPI路由 │ ◄─────────────── │ LightRAG    │
│ 状态管理    │    JSON响应          │ 数据处理    │    处理结果       │ 多模态处理   │
└─────────────┘                      └─────────────┘                  └─────────────┘
```

## 📦 组件说明

### 前端组件

#### RAGDashboard.tsx
- 主仪表盘组件
- 集成所有功能模块
- 侧边栏导航
- 状态管理

#### DocumentUpload.tsx
- 文件拖拽上传
- 进度显示
- 格式验证
- 批量处理

#### QueryInterface.tsx
- 查询输入界面
- 多模态内容添加
- 查询历史
- 结果展示

#### SystemStatus.tsx
- 实时系统监控
- 性能指标
- 服务状态
- 日志查看

#### ConfigurationPanel.tsx
- 配置管理界面
- 分类设置
- 连接测试
- 参数验证

### 后端API端点

#### 系统管理
- `GET /health` - 健康检查
- `GET /api/system/status` - 系统状态
- `GET/POST /api/config` - 配置管理

#### 文档处理
- `POST /api/documents/upload` - 文档上传
- `GET /api/documents` - 文档列表
- `DELETE /api/documents/{id}` - 删除文档

#### 查询功能
- `POST /api/query` - 执行查询
- `GET /api/query/history` - 查询历史
- `POST /api/query/multimodal` - 多模态查询

## 🚀 部署架构

### 开发环境
```
localhost:3000 (前端) ──► localhost:8000 (API) ──► RAG核心系统
```

### 生产环境建议
```
Nginx ──► React构建 + FastAPI ──► RAG核心系统
```

## 🔧 扩展点

### 前端扩展
1. **新页面**：在 `web-ui/components/` 添加新组件
2. **新功能**：扩展现有组件或创建新的业务组件
3. **主题**：修改 `tailwind.config.js` 和 CSS变量
4. **国际化**：集成 i18next 支持多语言

### 后端扩展
1. **新API**：在 `main.py` 添加新路由
2. **中间件**：添加认证、限流等中间件
3. **数据库**：集成 SQLAlchemy 或其他ORM
4. **缓存**：添加 Redis 缓存层

### 核心系统扩展
1. **新解析器**：扩展 `parser.py` 支持更多格式
2. **新处理器**：在 `modalprocessors.py` 添加新的内容类型
3. **新存储**：扩展存储后端支持
4. **新模型**：集成更多LLM和嵌入模型

## 📝 开发规范

### 前端规范
- 使用TypeScript类型定义
- 遵循React Hooks模式
- 组件命名使用PascalCase
- 文件名与组件名保持一致
- 使用Tailwind CSS类名

### 后端规范
- 使用Pydantic模型验证
- 异步函数优先
- 错误处理和日志记录
- API文档注释
- 类型提示

### 代码组织
- 单一职责原则
- 模块化设计
- 配置外部化
- 错误处理统一
- 日志格式规范

## 🔄 版本控制

### Git工作流
```
main ──► develop ──► feature/xxx
                  ├── feature/ui-enhancement
                  ├── feature/api-optimization
                  └── feature/new-processor
```

### 发布流程
1. 功能开发在feature分支
2. 合并到develop分支测试
3. 发布时合并到main分支
4. 使用语义化版本号

## 📊 监控和日志

### 日志位置
- **API日志**：`web-api/api.log`
- **RAG日志**：`rag_storage/` 目录
- **前端日志**：浏览器控制台

### 监控指标
- 系统资源使用率
- API响应时间
- 文档处理成功率
- 查询准确性
- 用户活跃度

---

这个项目结构为RAG-Anything系统提供了现代化的Web界面，通过清晰的分层架构实现了良好的可维护性和可扩展性。