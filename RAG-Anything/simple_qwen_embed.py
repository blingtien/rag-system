#!/usr/bin/env python
"""
简单的Qwen嵌入函数，用于替换OpenAI embedding
保持与原生代码的兼容性
"""

import torch
from transformers import AutoTokenizer, AutoModel
import numpy as np
from typing import List
import logging

logger = logging.getLogger(__name__)

# 全局模型实例，避免重复加载
_qwen_tokenizer = None
_qwen_model = None

def load_qwen_model():
    """加载Qwen嵌入模型"""
    global _qwen_tokenizer, _qwen_model
    
    if _qwen_tokenizer is None or _qwen_model is None:
        # 从环境变量读取配置
        import os
        model_name = os.getenv("QWEN_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B")
        device = os.getenv("EMBEDDING_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
        cache_dir = os.getenv("MODEL_CACHE_DIR", "./models")
        
        logger.info(f"Loading Qwen embedding model: {model_name}")
        logger.info(f"Using device: {device}")
        logger.info(f"Cache directory: {cache_dir}")
        
        _qwen_tokenizer = AutoTokenizer.from_pretrained(
            model_name, 
            trust_remote_code=True,
            cache_dir=cache_dir
        )
        
        _qwen_model = AutoModel.from_pretrained(
            model_name,
            trust_remote_code=True,
            cache_dir=cache_dir,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32
        ).to(device)
        
        _qwen_model.eval()
        logger.info("Qwen embedding model loaded successfully")
    
    return _qwen_tokenizer, _qwen_model

async def qwen_embed(texts: List[str], **kwargs) -> List[List[float]]:
    """
    Qwen嵌入函数，兼容OpenAI embed接口（异步版本）
    
    Args:
        texts: 要嵌入的文本列表
        **kwargs: 其他参数（忽略，保持兼容性）
        
    Returns:
        嵌入向量列表
    """
    try:
        tokenizer, model = load_qwen_model()
        device = next(model.parameters()).device
        
        # 批处理编码
        import os
        batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))
        max_length = int(os.getenv("EMBEDDING_MAX_LENGTH", "512"))
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            # 编码文本
            inputs = tokenizer(
                batch_texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=max_length
            ).to(device)
            
            # 获取嵌入
            with torch.no_grad():
                outputs = model(**inputs)
                # 使用平均池化
                embeddings = outputs.last_hidden_state.mean(dim=1)
                # 归一化
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                
            all_embeddings.extend(embeddings.cpu().numpy().tolist())
        
        return all_embeddings
        
    except Exception as e:
        logger.error(f"Error in qwen_embed: {e}")
        # 返回零向量作为备用
        return [[0.0] * 1024 for _ in texts]