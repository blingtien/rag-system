# RAG-Anything WebUI

现代化的RAG-Anything前端界面，基于React + TypeScript + Ant Design构建。

## 技术栈

- **React 18** - 前端框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具  
- **Ant Design** - UI组件库
- **React Router** - 路由管理
- **Axios** - HTTP客户端

## 文件结构

```
webui/
├── legacy/              # 原版HTML页面备份
├── src/
│   ├── components/      # 可复用组件
│   ├── pages/          # 页面组件
│   ├── services/       # API服务
│   ├── types/          # TypeScript类型定义
│   ├── utils/          # 工具函数
│   ├── App.tsx         # 主应用组件
│   ├── main.tsx        # 应用入口
│   └── index.css       # 全局样式
├── public/             # 静态资源
├── package.json        # 依赖配置
├── vite.config.ts      # Vite配置
└── tsconfig.json       # TypeScript配置
```

## 开发命令

```bash
# 安装依赖
npm install

# 启动开发服务器 (http://localhost:3000)
npm run dev

# 构建生产版本
npm run build

# 预览构建结果
npm run preview

# 代码检查
npm run lint
```

## API代理配置

Vite已配置API代理，前端请求会自动转发到后端：
- 前端: http://localhost:3000
- 后端: http://localhost:8001
- API代理: /api/* → http://localhost:8001/api/*

## 从原版升级

原版HTML页面已移动到 `legacy/` 文件夹作为备份。新版本提供：

✅ 组件化架构
✅ TypeScript类型安全  
✅ 现代化UI组件
✅ 路由管理
✅ 开发热更新
✅ 生产优化构建