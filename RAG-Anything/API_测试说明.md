# RAG-Anything API 测试说明

## 📋 项目概述

本文档介绍如何测试RAG-Anything独立API层的基本功能。我们已经成功创建了一个基于DDD架构的API封装层，它通过组合模式包装RAG-Anything核心功能，提供REST API接口。

## 🏗️ 架构特点

- **DDD架构**: 领域驱动设计，清晰的层次分离
- **组合模式**: 不修改RAG-Anything核心代码，通过适配器模式包装
- **实时进度**: 支持WebSocket实时进度监控（即将实现）
- **多模态处理**: 支持图像、表格、公式等多种内容类型

## 📁 项目结构

```
RAG-Anything/
├── api/                          # 独立API层
│   ├── config/                   # 配置管理
│   │   ├── settings.py          # API设置
│   │   └── dependencies.py      # 依赖注入
│   ├── domain/                   # 领域层
│   │   ├── models/              # 领域模型
│   │   │   ├── task.py         # 任务模型
│   │   │   ├── document.py     # 文档模型
│   │   │   ├── query.py        # 查询模型
│   │   │   └── system.py       # 系统模型
│   │   └── services/            # 领域服务
│   │       ├── task_service.py # 任务管理服务
│   │       └── document_service.py # 文档管理服务
│   ├── infrastructure/          # 基础设施层
│   │   ├── adapters/           # 适配器
│   │   │   └── raganything_adapter.py # RAG-Anything适配器
│   │   └── storage/            # 存储组件
│   │       └── task_storage.py # 任务存储
│   ├── interfaces/             # 接口层
│   │   └── routes/             # REST路由
│   │       ├── documents.py   # 文档API
│   │       └── tasks.py       # 任务API
│   └── main.py                 # FastAPI应用入口
├── lightrag_webui/             # WebUI前端（已拷贝）
├── run_api.py                  # API启动脚本
└── test_api.py                 # API测试脚本
```

## 🚀 启动API服务器

### 1. 安装依赖

确保已安装RAG-Anything及其依赖：

```bash
cd RAG-Anything
pip install -e '.[all]'
pip install fastapi uvicorn
```

### 2. 启动API服务器

```bash
python run_api.py
```

启动后你会看到：

```
🚀 启动 RAG-Anything API 服务器
🔧 环境配置:
   工作目录: ./rag_storage
   输出目录: ./output
   解析器: mineru
   主机地址: 127.0.0.1:8000

🌐 API 端点:
   📖 API文档: http://127.0.0.1:8000/docs
   🔍 健康检查: http://127.0.0.1:8000/health
   📤 文档上传: http://127.0.0.1:8000/api/v1/documents/upload
   📋 任务列表: http://127.0.0.1:8000/api/v1/tasks
```

## 🧪 运行测试

### 1. 自动化测试

在另一个终端运行：

```bash
python test_api.py
```

测试包括：
- ✅ 健康检查
- ✅ 系统能力查询
- ✅ 文档列表
- ✅ 任务列表
- ✅ 任务统计
- ✅ 文档上传
- ✅ 任务进度查询

### 2. 手动测试

#### 健康检查
```bash
curl http://127.0.0.1:8000/health
```

#### 查看API文档
访问：http://127.0.0.1:8000/docs

#### 上传文档
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/documents/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_document.pdf" \
  -F "parser=mineru" \
  -F "parse_method=auto"
```

#### 查看任务状态
```bash
curl http://127.0.0.1:8000/api/v1/tasks/{task_id}
```

#### 查看任务进度
```bash
curl http://127.0.0.1:8000/api/v1/tasks/{task_id}/progress
```

## 📊 API端点总览

### 系统端点
- `GET /health` - 系统健康检查
- `GET /capabilities` - 系统能力查询

### 文档管理
- `POST /api/v1/documents/upload` - 上传文档
- `GET /api/v1/documents` - 文档列表
- `GET /api/v1/documents/{doc_id}` - 获取文档详情
- `DELETE /api/v1/documents/{doc_id}` - 删除文档
- `POST /api/v1/documents/batch` - 批量处理
- `GET /api/v1/documents/batch/{batch_id}/status` - 批量状态

### 任务管理
- `GET /api/v1/tasks` - 任务列表
- `GET /api/v1/tasks/{task_id}` - 任务详情
- `GET /api/v1/tasks/{task_id}/progress` - 任务进度
- `POST /api/v1/tasks/{task_id}/cancel` - 取消任务
- `GET /api/v1/tasks/statistics/overview` - 任务统计

## 🎯 测试重点

### 1. 基础功能测试
- [x] API服务器正常启动
- [x] 健康检查响应正常
- [x] 文档上传功能正常
- [x] 任务创建和状态管理正常

### 2. 错误处理测试
- [x] 无效文件类型上传
- [x] 文件大小超限
- [x] 不存在的任务ID查询

### 3. 进度监控测试
- [x] 任务进度查询
- [x] 8阶段进度反馈
- [ ] WebSocket实时进度（待实现）

## 🔧 配置说明

### 环境变量

可以通过环境变量配置API行为：

```bash
export WORKING_DIR="./rag_storage"      # RAG工作目录
export OUTPUT_DIR="./output"            # 输出目录
export PARSER="mineru"                  # 默认解析器
export PARSE_METHOD="auto"              # 默认解析方法
export API_HOST="127.0.0.1"            # API主机
export API_PORT="8000"                  # API端口
export MAX_CONCURRENT_TASKS="3"         # 最大并发任务数
export MAX_FILE_SIZE="104857600"        # 最大文件大小(100MB)
```

### 支持的文件类型

- **文档**: PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX
- **文本**: TXT, MD
- **图像**: JPG, PNG, BMP, TIFF, GIF, WebP

## 📝 已知限制

1. **WebSocket功能**: 目前实时进度监控通过REST API实现，WebSocket组件待开发
2. **查询功能**: 查询相关API（query_service）待实现
3. **用户认证**: 目前无认证机制，可通过API_KEY环境变量启用
4. **数据持久化**: 使用简单的JSON文件存储，生产环境建议使用数据库

## 🔄 下一步计划

1. **WebSocket组件**: 实现实时进度广播
2. **查询API**: 实现文档查询和检索功能
3. **WebUI集成**: 修改前端代码以使用新的API后端
4. **性能优化**: 添加缓存和并发控制
5. **部署配置**: Docker容器化和生产部署配置

## 🤝 总结

当前API层已经实现了基础的文档管理和任务监控功能，成功将RAG-Anything包装成了独立的API服务。通过DDD架构设计，保持了良好的代码组织和可维护性，为后续功能扩展奠定了坚实基础。

测试结果表明API各项基础功能运行正常，可以进行下一步的WebSocket和查询功能开发。