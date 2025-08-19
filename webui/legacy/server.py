#!/usr/bin/env python3
"""
静态文件服务器 - 用于提供RAG-Anything WebUI前端页面
端口: 3000
"""

import os
import sys
import http.server
import socketserver
from pathlib import Path

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)
    
    def end_headers(self):
        # 添加CORS头部以允许跨域请求
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        # 处理预检请求
        self.send_response(200)
        self.end_headers()
    
    def log_message(self, format, *args):
        # 自定义日志格式
        print(f"[{self.log_date_time_string()}] {format % args}")

def main():
    PORT = 3000  # 生产环境固定端口
    HOST = '0.0.0.0'
    
    print("🌐 RAG-Anything WebUI 前端服务器")
    print("=" * 50)
    print(f"📱 访问地址: http://localhost:{PORT}")
    print(f"📱 访问地址: http://127.0.0.1:{PORT}")
    print(f"🔧 服务目录: {Path(__file__).parent}")
    print(f"🚀 后端API: http://localhost:8000")
    print("=" * 50)
    print("按 Ctrl+C 停止服务器")
    print()
    
    try:
        with socketserver.TCPServer((HOST, PORT), MyHTTPRequestHandler) as httpd:
            print(f"✅ 服务器启动成功，监听 {HOST}:{PORT}")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 服务器已停止")
    except OSError as e:
        if e.errno == 98:
            print(f"❌ 端口 {PORT} 已被占用，请检查是否有其他服务运行")
        else:
            print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()