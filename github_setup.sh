#!/bin/bash

# GitHub仓库设置脚本
# 请先在GitHub网站创建仓库，然后运行此脚本

echo "=== GitHub仓库推送脚本 ==="
echo "请确保你已经在GitHub上创建了名为 'rag-system' 的仓库"
echo "仓库地址应该是: https://github.com/livenowtian/rag-system"
echo ""

# 检查是否已有远程仓库
if git remote | grep -q origin; then
    echo "检测到已有远程仓库，删除并重新配置..."
    git remote remove origin
fi

# 添加远程仓库
echo "添加远程仓库..."
git remote add origin https://github.com/livenowtian/rag-system.git

# 确保在main分支
echo "确保在main分支..."
git branch -M main

# 推送到GitHub
echo "推送到GitHub..."
echo "注意：首次推送可能需要输入GitHub用户名和Personal Access Token"
echo "如果需要认证，请访问 https://github.com/settings/tokens 创建Personal Access Token"
echo ""

# 推送代码
git push -u origin main

echo ""
echo "=== 推送完成 ==="
echo "仓库地址: https://github.com/livenowtian/rag-system"
echo ""
echo "下一步操作："
echo "1. 访问 https://github.com/livenowtian/rag-system 查看仓库"
echo "2. 在Settings -> Secrets中添加环境变量（如API密钥）"
echo "3. 可以选择添加GitHub Actions进行CI/CD"