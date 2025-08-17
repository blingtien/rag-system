# RAG System - 多模态智能问答系统

基于RAG-Anything的完整前后端知识库系统，支持多模态文档处理和智能检索。

## 🎯 项目概述

这是一个综合性的RAG（检索增强生成）系统，整合了：
- **RAG-Anything v1.2.7**: 多模态RAG核心引擎
- **Web API**: FastAPI后端服务
- **React WebUI**: 现代化前端界面
- **开发文档**: 完整的项目分析和开发计划

## 📁 项目结构

```
ragsystem/
├── docses/                              # 📊 项目分析和开发计划文档
│   ├── project-analysis-and-development-plan.md
│   ├── frontend-development-plan.md
│   └── backend-development-plan.md
├── web-api/                             # 🔧 FastAPI后端服务
│   ├── main.py                          # API主服务文件
│   ├── requirements.txt                 # Python依赖
│   └── start_server.py                  # 服务启动脚本
├── web-ui/                              # 🎨 React前端界面
│   ├── app/                             # Next.js应用
│   ├── components/                      # React组件
│   ├── package.json                     # Node.js依赖
│   └── next.config.js                   # Next.js配置
├── CLAUDE.md                            # 🤖 Claude开发指南
├── PROJECT_STRUCTURE.md                 # 📋 项目结构说明
├── install.sh                          # 🚀 一键安装脚本
├── start_webui.sh                       # 🌐 WebUI启动脚本
└── .gitignore                           # 🚫 Git忽略规则
```

## 🚀 快速开始

### 前置要求
- Python 3.10+
- Node.js 18+
- 至少8GB RAM
- LibreOffice（用于Office文档支持）

### 1. 克隆项目
```bash
git clone <repository-url>
cd ragsystem
```

### 2. 环境配置
```bash
# 复制环境变量模板
cp .env.example .env
# 编辑 .env 文件，配置API密钥等
```

### 3. 安装依赖
```bash
# 执行一键安装脚本
chmod +x install.sh
./install.sh
```

### 4. 启动服务
```bash
# 启动后端API服务
cd web-api
python start_server.py

# 启动前端界面（新终端）
cd web-ui
npm run dev
```

## 🔧 核心功能

### 文档处理
- **多格式支持**: PDF、DOC、DOCX、PPT、PPTX、XLS、XLSX
- **多模态内容**: 文本、图像、表格、公式
- **智能解析**: MinerU 2.0文档解析引擎

### 知识检索
- **4种查询模式**: naive、local、global、hybrid
- **向量检索**: Qwen3-Embedding-0.6B本地嵌入
- **知识图谱**: 实体关系可视化

### 用户界面
- **现代化设计**: React 19 + TypeScript + Tailwind CSS
- **实时交互**: WebSocket状态推送
- **响应式布局**: 支持多设备访问

## 🛠️ 技术架构

### 后端技术栈
- **API框架**: FastAPI 0.104+
- **文档解析**: MinerU 2.0
- **向量存储**: 本地JSON存储
- **嵌入模型**: Qwen3-Embedding-0.6B
- **LLM**: DeepSeek API

### 前端技术栈
- **框架**: React 19 + TypeScript
- **构建工具**: Vite 6.1.1
- **样式**: Tailwind CSS 4.0.8 + Radix UI
- **状态管理**: Zustand
- **图表可视化**: Sigma.js + React-Sigma

## 📚 开发文档

项目包含完整的开发计划文档：

1. **[项目分析与开发计划](./docses/project-analysis-and-development-plan.md)**
   - 技术架构现状分析
   - 核心问题识别
   - 完整开发时间线

2. **[前端开发计划](./docses/frontend-development-plan.md)**
   - API适配与基础集成
   - 用户体验优化
   - 高级功能实现

3. **[后端开发计划](./docses/backend-development-plan.md)**
   - API标准化与兼容性
   - 错误处理与稳定性
   - 性能优化与扩展性

## 🔐 安全配置

项目已配置完善的安全措施：
- 环境变量隔离（.env文件不会被提交）
- API密钥保护
- 输入验证和清理
- 文件上传安全检查

## 📈 项目状态

- ✅ **核心功能**: RAG-Anything完全就绪
- ✅ **API适配**: 核心功能已验证
- 🔄 **前端集成**: 组件完整，需要API对接
- 🔄 **用户体验**: 基础框架就绪，需要交互优化

## 🤝 开发指南

详细的开发指南请参考：
- [CLAUDE.md](./CLAUDE.md) - Claude Code开发指南
- [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) - 项目结构详解

## 📄 许可证

MIT License

## 🙋‍♂️ 支持

如有问题或建议，请创建Issue或联系项目维护者。

---

**注意**: 
- 本项目需要配置API密钥才能正常使用
- 首次运行前请仔细阅读环境配置要求
- 生产部署前请确保完成安全配置检查