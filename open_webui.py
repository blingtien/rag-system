#!/usr/bin/env python3
"""
RAG-Anything Web UI 快速访问脚本
"""

import webbrowser
import requests
import time
import subprocess
import sys

def check_services():
    """检查服务状态"""
    print("🔍 检查服务状态...")
    
    # 检查API服务器
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        api_status = "🟢 正常" if response.status_code == 200 else "🔴 异常"
    except:
        api_status = "🔴 离线"
    
    # 检查Web服务器
    try:
        response = requests.get("http://localhost:3000/demo.html", timeout=5)
        web_status = "🟢 正常" if response.status_code == 200 else "🔴 异常"
    except:
        web_status = "🔴 离线"
    
    print(f"   📡 API服务器 (端口8000): {api_status}")
    print(f"   🌐 Web服务器 (端口3000): {web_status}")
    
    return "🟢" in api_status and "🟢" in web_status

def show_access_info():
    """显示访问信息"""
    print("\n" + "="*60)
    print("🚀 RAG-Anything Web UI 访问信息")
    print("="*60)
    print("📍 主要地址:")
    print("   🖥️  Web界面: http://localhost:3000/demo.html")
    print("   📚 API文档: http://localhost:8000/docs")
    print("   ⚡ API健康: http://localhost:8000/health")
    print("   📊 系统状态: http://localhost:8000/api/system/status")
    
    print("\n🎯 主要功能:")
    print("   📁 文档管理 - 上传和处理各种格式文档")
    print("   🤖 智能查询 - 多模态RAG查询系统")
    print("   📈 系统监控 - 实时性能和状态监控")
    print("   ⚙️  配置管理 - 系统参数配置和调整")
    
    print("\n💡 使用提示:")
    print("   1. 首次使用建议先查看系统状态页面")
    print("   2. 可以上传PDF、Word、图片等多种格式文档")
    print("   3. 支持自然语言查询和多模态内容分析")
    print("   4. 查询支持本地、全局、混合等多种模式")

def main():
    print("🎉 欢迎使用 RAG-Anything Web UI!")
    
    if check_services():
        print("\n✅ 所有服务运行正常!")
        
        # 显示访问链接（不自动打开浏览器）
        print("🌐 系统已就绪，请手动访问以下地址:")
        
        show_access_info()
        
    else:
        print("\n⚠️ 部分服务未运行，请先启动系统:")
        print("   运行命令: ./start_webui.sh")
        print("   或手动启动:")
        print("   1. 启动API: cd web-api && python start_server.py")
        print("   2. 启动Web: python3 -m http.server 3000")

if __name__ == "__main__":
    main()