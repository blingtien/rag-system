#!/usr/bin/env python
"""
简单的RAGAnything查询工具
支持4种查询模式，使用DeepSeek LLM + 本地Qwen embedding
"""

import os
import asyncio
import logging
from pathlib import Path
import sys

# Add project root directory to Python path
sys.path.append(str(Path(__file__).parent))

from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc, logger
from raganything import RAGAnything, RAGAnythingConfig
from simple_qwen_embed import qwen_embed

from dotenv import load_dotenv

# 加载环境变量
load_dotenv(dotenv_path=".env", override=False)

# 配置日志
logging.basicConfig(level=logging.WARNING)  # 减少冗余日志

class SimpleQueryTool:
    """简单的RAG查询工具"""
    
    def __init__(self):
        self.rag = None
        self.modes = {
            "1": ("naive", "朴素模式 - 简单向量相似度搜索，速度最快"),
            "2": ("local", "局部模式 - 关注局部相关内容，适合具体细节"),
            "3": ("global", "全局模式 - 全局知识图谱推理，适合宏观问题"),
            "4": ("hybrid", "混合模式 - 结合local和global，效果最佳（推荐）")
        }
    
    async def initialize(self):
        """初始化RAG系统"""
        try:
            print("🚀 初始化RAG系统...")
            
            # 检查环境变量
            api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_BINDING_API_KEY")
            if not api_key:
                print("❌ 错误: 未找到DEEPSEEK_API_KEY，请检查.env文件")
                return False
            
            base_url = os.getenv("LLM_BINDING_HOST", "https://api.deepseek.com/v1")
            working_dir = os.getenv("WORKING_DIR", "./rag_storage")
            
            # 检查是否已有处理过的数据
            if not os.path.exists(working_dir):
                print(f"❌ 未找到RAG数据目录: {working_dir}")
                print("请先运行文档处理:")
                print("python native_with_qwen.py your_document.pdf --output ./output")
                return False
            
            # 创建配置
            config = RAGAnythingConfig(
                working_dir=working_dir,
                parser="mineru",
                parse_method="auto",
                enable_image_processing=True,
                enable_table_processing=True,
                enable_equation_processing=True,
            )
            
            # 定义LLM函数
            def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
                return openai_complete_if_cache(
                    "deepseek-chat",
                    prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages,
                    api_key=api_key,
                    base_url=base_url,
                    **kwargs,
                )
            
            # 定义嵌入函数
            embedding_func = EmbeddingFunc(
                embedding_dim=1024,
                max_token_size=512,
                func=qwen_embed,
            )
            
            # 初始化RAGAnything
            self.rag = RAGAnything(
                config=config,
                llm_model_func=llm_model_func,
                embedding_func=embedding_func,
            )
            
            # 确保LightRAG实例已初始化
            await self.rag._ensure_lightrag_initialized()
            
            print("✅ RAG系统初始化成功!")
            print(f"📁 数据目录: {working_dir}")
            print(f"🤖 LLM: DeepSeek API")
            print(f"🧠 嵌入: 本地Qwen3-Embedding-0.6B")
            print("-" * 50)
            return True
            
        except Exception as e:
            print(f"❌ 初始化失败: {str(e)}")
            return False
    
    def show_modes(self):
        """显示查询模式选项"""
        print("\n📋 查询模式选择:")
        for key, (mode, description) in self.modes.items():
            print(f"  {key}. {description}")
        print("  q. 退出程序")
    
    def get_mode_choice(self):
        """获取用户选择的模式"""
        while True:
            choice = input("\n请选择查询模式 (1-4) 或 q 退出: ").strip()
            
            if choice.lower() == 'q':
                return None
            
            if choice in self.modes:
                mode, description = self.modes[choice]
                print(f"✅ 已选择: {description}")
                return mode
            
            print("❌ 无效选择，请输入 1-4 或 q")
    
    async def query(self, question, mode):
        """执行查询"""
        try:
            print(f"\n🔍 正在查询 ({mode}模式)...")
            print(f"❓ 问题: {question}")
            
            # 执行查询，禁用VLM避免API兼容性问题
            result = await self.rag.aquery(
                question, 
                mode=mode, 
                vlm_enhanced=False
            )
            
            print(f"\n💡 回答:")
            print("-" * 30)
            print(result)
            print("-" * 30)
            
            return True
            
        except Exception as e:
            print(f"❌ 查询失败: {str(e)}")
            return False
    
    async def run(self):
        """运行查询工具"""
        print("🌟 RAGAnything 简单查询工具")
        print("=" * 40)
        
        # 初始化
        if not await self.initialize():
            return
        
        print("\n🎯 查询工具已就绪! 您可以开始提问了。")
        
        # 主循环
        while True:
            try:
                # 显示模式选择
                self.show_modes()
                
                # 获取模式选择
                mode = self.get_mode_choice()
                if mode is None:
                    print("👋 再见!")
                    break
                
                # 获取问题
                print("\n💭 请输入您的问题:")
                question = input("❓ ").strip()
                
                if not question:
                    print("❌ 问题不能为空")
                    continue
                
                # 执行查询
                success = await self.query(question, mode)
                
                if success:
                    # 询问是否继续
                    while True:
                        continue_choice = input("\n是否继续查询? (y/n): ").strip().lower()
                        if continue_choice in ['y', 'yes', '是']:
                            break
                        elif continue_choice in ['n', 'no', '否']:
                            print("👋 再见!")
                            return
                        else:
                            print("请输入 y 或 n")
                
            except KeyboardInterrupt:
                print("\n👋 用户中断，再见!")
                break
            except Exception as e:
                print(f"❌ 程序错误: {str(e)}")
                continue

def main():
    """主函数"""
    try:
        tool = SimpleQueryTool()
        asyncio.run(tool.run())
    except KeyboardInterrupt:
        print("\n👋 程序被中断")
    except Exception as e:
        print(f"❌ 程序启动失败: {str(e)}")

if __name__ == "__main__":
    main()