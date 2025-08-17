#!/usr/bin/env python
"""
简单的自定义模型示例 - Qwen本地embedding + DeepSeek API

这个示例展示如何：
1. 使用本地Qwen embedding模型
2. 使用DeepSeek API作为LLM
3. 正确配置RAGAnything
"""

import asyncio
import os
from pathlib import Path

# 确保能导入模块
import sys
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from lightrag.utils import EmbeddingFunc

# 导入自定义模型函数
from raganything.custom_models import (
    get_qwen_embedding_func,
    deepseek_complete_if_cache,
    deepseek_vision_complete,
    validate_custom_models
)
from raganything import RAGAnything, RAGAnythingConfig

# 加载环境变量
load_dotenv()

def create_custom_llm_func():
    """创建DeepSeek LLM函数"""
    def llm_func(prompt, system_prompt=None, history_messages=[], **kwargs):
        return deepseek_complete_if_cache(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            temperature=float(os.getenv("TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
            **kwargs
        )
    return llm_func

def create_custom_vision_func():
    """创建DeepSeek视觉模型函数"""
    def vision_func(prompt, system_prompt=None, history_messages=[], image_data=None, messages=None, **kwargs):
        # 如果有预格式化的messages，直接使用
        if messages:
            return deepseek_complete_if_cache(
                model=os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl"),
                prompt="",
                system_prompt=None,
                history_messages=[],
                messages=messages,
                **kwargs
            )
        # 如果有图像数据，使用视觉完成
        elif image_data:
            return deepseek_vision_complete(
                model=os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl"),
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                image_data=image_data,
                **kwargs
            )
        # 否则使用普通文本完成
        else:
            return deepseek_complete_if_cache(
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                **kwargs
            )
    return vision_func

async def main():
    """主函数"""
    print("🚀 开始自定义模型配置...")
    
    # 1. 验证配置
    print("\n📋 验证依赖和配置...")
    validation = validate_custom_models()
    for key, value in validation.items():
        status = "✅" if value else "❌"
        print(f"  {status} {key}: {value}")
    
    if not validation["torch_available"]:
        print("❌ PyTorch未安装，请先安装: pip install torch")
        return
    
    if not validation["transformers_available"]:
        print("❌ Transformers未安装，请先安装: pip install transformers")
        return
    
    # 2. 创建嵌入函数
    print("\n🧠 初始化Qwen embedding模型...")
    try:
        embedding_func = get_qwen_embedding_func()
        print("✅ Qwen embedding模型初始化成功")
        
        # 测试embedding
        test_embeddings = embedding_func(["测试文本"])
        print(f"✅ Embedding测试成功，维度: {len(test_embeddings[0])}")
        
    except Exception as e:
        print(f"❌ Qwen embedding模型初始化失败: {e}")
        return
    
    # 3. 创建LLM函数
    print("\n🤖 配置DeepSeek LLM...")
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("⚠️  DEEPSEEK_API_KEY未设置，请在.env中配置")
        print("   示例: DEEPSEEK_API_KEY=your_api_key_here")
        return
    
    llm_func = create_custom_llm_func()
    vision_func = create_custom_vision_func()
    print("✅ DeepSeek API配置完成")
    
    # 4. 配置RAGAnything
    print("\n⚙️  初始化RAGAnything...")
    config = RAGAnythingConfig(
        working_dir=os.getenv("WORKING_DIR", "./rag_storage"),
        enable_image_processing=True,
        enable_table_processing=True,
        enable_equation_processing=True,
    )
    
    # 创建EmbeddingFunc对象
    from raganything.custom_models import _qwen_model_instance
    embedding_dim = _qwen_model_instance.embedding_dim if _qwen_model_instance else 768
    
    embedding_func_obj = EmbeddingFunc(
        embedding_dim=embedding_dim,
        max_token_size=int(os.getenv("EMBEDDING_MAX_LENGTH", "512")),
        func=embedding_func
    )
    
    # 初始化RAGAnything
    rag = RAGAnything(
        config=config,
        llm_model_func=llm_func,
        vision_model_func=vision_func,
        embedding_func=embedding_func_obj
    )
    
    print("✅ RAGAnything初始化成功")
    
    # 5. 测试功能
    print("\n🧪 测试配置...")
    
    # 测试LLM（如果有API key）
    try:
        test_response = llm_func("你好，请简短回复")
        print(f"✅ LLM测试成功: {test_response[:50]}...")
    except Exception as e:
        print(f"⚠️  LLM测试失败（可能是API key问题）: {e}")
    
    print("\n🎉 配置完成！现在可以使用自定义模型处理文档了。")
    print("\n📖 使用示例:")
    print("   # 处理文档")
    print("   await rag.process_document_complete('document.pdf')")
    print("   # 查询")
    print("   result = await rag.aquery('你的问题', mode='hybrid')")

if __name__ == "__main__":
    asyncio.run(main())