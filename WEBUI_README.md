# RAG-Anything Web UI

RAG-Anything系统的现代化Web用户界面，提供直观易用的文档处理和智能查询体验。

## 🌟 功能特性

### 📁 文档管理
- **拖拽上传**：支持拖拽多个文件批量上传
- **格式支持**：PDF、Word、PowerPoint、图片、文本等多种格式
- **实时处理**：文档上传后自动解析和处理
- **状态监控**：实时显示文档处理进度和状态
- **批量操作**：支持同时处理多个文档

### 🤖 智能查询
- **多模态查询**：支持文本、图片、表格、公式等多种内容类型
- **查询模式**：本地、全局、混合、简单等多种检索策略
- **实时响应**：快速返回查询结果
- **历史记录**：保存和回顾查询历史
- **模板功能**：预设常用查询模板

### 📊 系统监控
- **实时状态**：CPU、内存、磁盘、GPU使用率监控
- **服务状态**：各个系统组件的运行状态
- **处理统计**：文档处理和查询统计数据
- **日志查看**：系统运行日志实时查看
- **性能图表**：系统性能趋势可视化

### ⚙️ 配置管理
- **解析器配置**：选择和配置文档解析引擎
- **多模态设置**：控制图像、表格、公式等处理选项
- **LLM配置**：API密钥、模型选择、参数调整
- **存储配置**：数据存储和向量数据库设置
- **连接测试**：验证各项配置的连通性

## 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React前端     │    │   FastAPI后端   │    │  RAG-Anything   │
│                 │    │                 │    │     核心        │
│  - 用户界面     │◄──►│  - REST API     │◄──►│  - 文档解析     │
│  - 状态管理     │    │  - 文件处理     │    │  - 向量检索     │
│  - 实时更新     │    │  - 查询转发     │    │  - 多模态处理   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 前端技术栈
- **React 18** + **TypeScript**：现代化React开发
- **Next.js 14**：全栈React框架
- **Tailwind CSS**：原子化CSS框架
- **Framer Motion**：动画和交互效果
- **Lucide React**：美观的图标库

### 后端技术栈
- **FastAPI**：现代Python Web框架
- **Uvicorn**：高性能ASGI服务器
- **Pydantic**：数据验证和序列化
- **Asyncio**：异步编程支持

## 🚀 快速开始

### 环境要求
- **Python 3.10+**
- **Node.js 18+**
- **npm或yarn**

### 一键启动
```bash
# 使用启动脚本（推荐）
chmod +x start_webui.sh
./start_webui.sh
```

### 手动启动

#### 1. 启动后端API服务器
```bash
cd web-api
python3 -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate
pip install -r requirements.txt
python start_server.py --reload
```

#### 2. 启动前端开发服务器
```bash
cd web-ui
npm install
npm run dev
```

### 访问地址
- **Web界面**：http://localhost:3000
- **API文档**：http://localhost:8000/docs
- **API健康检查**：http://localhost:8000/health

## 📖 使用指南

### 1. 首次配置
1. 访问 http://localhost:3000
2. 点击侧边栏的"配置"
3. 配置LLM API密钥和相关参数
4. 测试连接确保配置正确

### 2. 上传文档
1. 进入"文档管理"页面
2. 拖拽文件到上传区域或点击选择文件
3. 等待文档处理完成
4. 在文档库中查看处理结果

### 3. 智能查询
1. 进入"智能查询"页面
2. 选择合适的查询模式
3. 输入问题或使用快速模板
4. 可选择添加多模态内容（图片、表格等）
5. 点击发送查询获取结果

### 4. 系统监控
1. 访问"系统状态"页面
2. 查看实时性能指标
3. 监控服务运行状态
4. 浏览系统日志

## 🔧 API接口

### 核心端点
- `GET /api/system/status` - 获取系统状态
- `POST /api/documents/upload` - 上传文档
- `GET /api/documents` - 获取文档列表
- `POST /api/query` - 执行RAG查询
- `GET /api/query/history` - 查询历史
- `GET/POST /api/config` - 配置管理

### 示例请求
```python
import requests

# 上传文档
files = {'file': open('document.pdf', 'rb')}
response = requests.post('http://localhost:8000/api/documents/upload', files=files)

# 执行查询
query_data = {
    "query": "文档的主要内容是什么？",
    "mode": "hybrid"
}
response = requests.post('http://localhost:8000/api/query', json=query_data)
```

## 🎨 界面预览

### 主仪表盘
- 系统概览和统计信息
- 快速操作入口
- 最近活动展示

### 文档管理
- 直观的拖拽上传界面
- 实时处理进度显示
- 支持格式一览

### 智能查询
- 清晰的查询输入区域
- 多模态内容添加
- 结构化结果展示

### 系统监控
- 实时性能图表
- 服务状态总览
- 详细日志查看

## 🔧 自定义配置

### 环境变量
创建 `.env` 文件：
```bash
# API配置
API_HOST=0.0.0.0
API_PORT=8000

# RAG系统配置
WORKING_DIR=./rag_storage
PARSER=mineru
PARSE_METHOD=auto

# LLM配置
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1

# 多模态处理
ENABLE_IMAGE_PROCESSING=true
ENABLE_TABLE_PROCESSING=true
ENABLE_EQUATION_PROCESSING=true
```

### 前端配置
修改 `web-ui/next.config.js`：
```javascript
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://your-api-server:8000/api/:path*',
      },
    ];
  },
}
```

## 🛠️ 开发指南

### 添加新组件
1. 在 `web-ui/components/` 创建新组件
2. 使用TypeScript和Tailwind CSS
3. 遵循现有的命名和结构规范

### 添加新API端点
1. 在 `web-api/main.py` 添加路由
2. 定义对应的Pydantic模型
3. 更新API文档

### 自定义样式
1. 修改 `web-ui/tailwind.config.js`
2. 在 `web-ui/app/globals.css` 添加全局样式
3. 使用CSS变量支持主题切换

## 🔍 故障排除

### 常见问题

**Q: 端口被占用怎么办？**
A: 修改启动脚本中的端口号，或终止占用端口的进程。

**Q: API连接失败？**
A: 检查后端服务是否正常启动，确认防火墙设置。

**Q: 文档处理失败？**
A: 检查文档格式是否支持，查看API日志获取详细错误信息。

**Q: 查询无结果？**
A: 确认文档已成功处理，检查LLM配置是否正确。

### 日志位置
- **API日志**：`web-api/api.log`
- **前端日志**：浏览器开发者工具控制台
- **RAG系统日志**：`rag_storage/` 目录下

## 🤝 贡献指南

1. Fork本项目
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'Add some amazing feature'`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看[LICENSE](LICENSE)文件了解详情。

## 🆘 支持

如遇问题，请：
1. 查看本文档的故障排除部分
2. 检查GitHub Issues
3. 提交新的Issue描述问题

---

**享受使用RAG-Anything Web UI！** 🎉