#!/usr/bin/env python
"""
修正后的自定义模型示例 - 遵循RAG-Anything官方模式

基于Context7文档分析，正确的集成方式是：
1. RAG-Anything初始化时传递函数参数，不依赖自定义环境变量
2. 环境变量在函数内部读取，而不是通过RAGAnything配置
3. 遵循官方的lambda函数模式
"""

import asyncio
import os
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from lightrag.utils import EmbeddingFunc
from raganything import RAGAnything, RAGAnythingConfig
from raganything.custom_models import (
    get_qwen_embedding_func,
    deepseek_complete_if_cache,
    validate_custom_models
)

# 加载环境变量
load_dotenv()

async def main():
    """主函数 - 遵循官方RAG-Anything模式"""
    print("🚀 使用修正后的自定义模型配置...")
    
    # 1. 验证依赖
    print("\n📋 验证依赖...")
    validation = validate_custom_models()
    for key, value in validation.items():
        status = "✅" if value else "❌"
        print(f"  {status} {key}")
    
    if not all([validation["torch_available"], validation["transformers_available"]]):
        print("❌ 缺少必要依赖，请先安装 torch 和 transformers")
        return
    
    # 2. 创建embedding函数 (遵循官方lambda模式)
    print("\n🧠 创建embedding函数...")
    qwen_embedding_func = get_qwen_embedding_func()
    
    # 获取embedding维度
    from raganything.custom_models import _qwen_model_instance
    embedding_dim = _qwen_model_instance.embedding_dim if _qwen_model_instance else 768
    
    # 创建兼容LightRAG的embedding函数
    embedding_func = EmbeddingFunc(
        embedding_dim=embedding_dim,
        max_token_size=int(os.getenv("EMBEDDING_MAX_LENGTH", "512")),
        func=qwen_embedding_func
    )
    print(f"✅ Qwen embedding配置完成，维度: {embedding_dim}")
    
    # 3. 创建LLM函数 (遵循官方lambda模式)
    print("\n🤖 创建LLM函数...")
    
    def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
        """LLM函数 - 遵循官方openai_complete_if_cache签名"""
        return deepseek_complete_if_cache(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            temperature=float(os.getenv("TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
            **kwargs
        )
    
    def vision_model_func(prompt, system_prompt=None, history_messages=[], image_data=None, messages=None, **kwargs):
        """视觉模型函数 - 遵循官方模式"""
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
        # 如果有图像数据
        elif image_data:
            # 构造视觉消息格式
            content = [{"type": "text", "text": prompt}]
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
            })
            
            vision_messages = []
            if system_prompt:
                vision_messages.append({"role": "system", "content": system_prompt})
            if history_messages:
                vision_messages.extend(history_messages)
            vision_messages.append({"role": "user", "content": content})
            
            return deepseek_complete_if_cache(
                model=os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl"),
                prompt="",
                system_prompt=None,
                history_messages=[],
                messages=vision_messages,
                **kwargs
            )
        else:
            # 回退到文本模式
            return llm_model_func(prompt, system_prompt, history_messages, **kwargs)
    
    print("✅ DeepSeek LLM函数配置完成")
    
    # 4. 按官方模式初始化RAGAnything
    print("\n⚙️  初始化RAGAnything...")
    
    # 使用官方支持的配置参数
    config = RAGAnythingConfig(
        working_dir=os.getenv("WORKING_DIR", "./rag_storage"),
        parser_output_dir=os.getenv("OUTPUT_DIR", "./output"),
        parser=os.getenv("PARSER", "mineru"),
        parse_method=os.getenv("PARSE_METHOD", "auto"),
        enable_image_processing=os.getenv("ENABLE_IMAGE_PROCESSING", "true").lower() == "true",
        enable_table_processing=os.getenv("ENABLE_TABLE_PROCESSING", "true").lower() == "true",
        enable_equation_processing=os.getenv("ENABLE_EQUATION_PROCESSING", "true").lower() == "true",
    )
    
    # 按照官方文档的方式初始化
    rag = RAGAnything(
        config=config,
        llm_model_func=llm_model_func,
        vision_model_func=vision_model_func,
        embedding_func=embedding_func,
    )
    
    print("✅ RAGAnything初始化成功")
    
    # 5. 测试配置
    print("\n🧪 测试配置...")
    
    # 测试embedding
    try:
        test_embeddings = qwen_embedding_func(["测试embedding"])
        print(f"✅ Embedding测试成功: {len(test_embeddings[0])}维")
    except Exception as e:
        print(f"❌ Embedding测试失败: {e}")
    
    # 测试LLM（需要API key）
    if os.getenv("DEEPSEEK_API_KEY", "").startswith("sk-"):
        try:
            test_response = llm_model_func("简短回复：你好")
            print(f"✅ LLM测试成功: {test_response[:50]}...")
        except Exception as e:
            print(f"⚠️  LLM测试失败: {e}")
    else:
        print("⚠️  DEEPSEEK_API_KEY未设置，跳过LLM测试")
    
    print("\n🎉 配置验证完成！")
    print("\n📖 使用方法:")
    print("   # 处理文档")
    print("   await rag.process_document_complete('document.pdf')")
    print("   # 查询文档")
    print("   result = await rag.aquery('问题', mode='hybrid')")
    
    return rag

if __name__ == "__main__":
    asyncio.run(main())