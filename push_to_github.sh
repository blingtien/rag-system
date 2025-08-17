#!/bin/bash

echo "=== 推送RAG系统到GitHub ==="
echo "确保你已经在GitHub创建了 'rag-system' 仓库"
echo "仓库地址: https://github.com/livenowtian/rag-system"
echo ""

# 推送到GitHub
echo "正在推送代码到GitHub..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 成功推送到GitHub!"
    echo "仓库地址: https://github.com/livenowtian/rag-system"
    echo ""
    echo "🔒 安全提醒:"
    echo "- .env文件已被正确排除，不会上传密钥"
    echo "- 大型模型文件已被排除"
    echo "- 子仓库将作为独立项目管理"
    echo ""
    echo "📁 仓库包含:"
    echo "- 完整的项目结构和代码"
    echo "- 详细的开发计划文档"
    echo "- 安全的配置模板"
    echo "- 完善的README文档"
else
    echo ""
    echo "❌ 推送失败，可能需要认证"
    echo "请确保："
    echo "1. 已在GitHub创建仓库"
    echo "2. 有推送权限"
    echo "3. 网络连接正常"
fi