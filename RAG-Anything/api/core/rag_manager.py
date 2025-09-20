"""
RAG管理器
单例模式管理RAG实例，确保线程安全和资源复用
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional
from threading import RLock

# 添加项目根路径到sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))

from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc, logger
from raganything import RAGAnything, RAGAnythingConfig
from simple_qwen_embed import qwen_embed

from config.settings import settings
from cache_enhanced_processor import CacheEnhancedProcessor
from cache_statistics import initialize_cache_tracking


class RAGManager:
    """
    RAG管理器 - 单例模式管理RAG实例
    提供线程安全的RAG实例访问和生命周期管理
    """
    
    _instance = None
    _instance_lock = RLock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super(RAGManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._rag_instance: Optional[RAGAnything] = None
        self._cache_enhanced_processor: Optional[CacheEnhancedProcessor] = None
        self._initialization_lock = RLock()
        self._is_initializing = False
        self._initialized = True
    
    async def get_rag_instance(self) -> Optional[RAGAnything]:
        """
        获取RAG实例，如果未初始化则自动初始化
        线程安全的懒加载模式
        """
        if self._rag_instance is not None:
            return self._rag_instance
            
        with self._initialization_lock:
            if self._is_initializing:
                # 如果正在初始化，等待完成
                while self._is_initializing:
                    await asyncio.sleep(0.1)
                return self._rag_instance
            
            if self._rag_instance is None:
                await self._initialize()
            
        return self._rag_instance
    
    async def _initialize(self) -> None:
        """初始化RAG系统"""
        self._is_initializing = True
        
        try:
            logger.info("开始初始化RAG系统...")
            
            # 检查API密钥
            if not settings.deepseek_api_key:
                logger.error("未找到DEEPSEEK_API_KEY，请检查环境变量")
                return
            
            # 创建RAGAnything配置
            config = RAGAnythingConfig(
                working_dir=settings.working_dir,
                parser_output_dir=settings.output_dir,
                parser=settings.parser,
                parse_method=settings.parse_method,
                enable_image_processing=settings.enable_image_processing,
                enable_table_processing=settings.enable_table_processing,
                enable_equation_processing=settings.enable_equation_processing,
            )
            
            # 定义LLM函数
            def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
                return openai_complete_if_cache(
                    "deepseek-chat",
                    prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages,
                    api_key=settings.deepseek_api_key,
                    base_url=settings.llm_binding_host,
                    **kwargs,
                )
            
            # 定义视觉模型函数
            def vision_model_func(
                prompt,
                system_prompt=None,
                history_messages=[],
                image_data=None,
                messages=None,
                **kwargs,
            ):
                if messages:
                    return openai_complete_if_cache(
                        "deepseek-vl",
                        "",
                        system_prompt=None,
                        history_messages=[],
                        messages=messages,
                        api_key=settings.deepseek_api_key,
                        base_url=settings.llm_binding_host,
                        **kwargs,
                    )
                elif image_data:
                    return openai_complete_if_cache(
                        "deepseek-vl",
                        "",
                        system_prompt=None,
                        history_messages=[],
                        messages=[
                            {"role": "system", "content": system_prompt} if system_prompt else None,
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                                    },
                                ],
                            } if image_data else {"role": "user", "content": prompt},
                        ],
                        api_key=settings.deepseek_api_key,
                        base_url=settings.llm_binding_host,
                        **kwargs,
                    )
                else:
                    return llm_model_func(prompt, system_prompt, history_messages, **kwargs)
            
            # 定义嵌入函数
            embedding_func = EmbeddingFunc(
                embedding_dim=1024,
                max_token_size=512,
                func=qwen_embed,
            )
            
            # 配置LightRAG缓存设置
            lightrag_kwargs = {
                "enable_llm_cache": settings.enable_llm_cache,
            }
            
            # 初始化RAGAnything
            self._rag_instance = RAGAnything(
                config=config,
                llm_model_func=llm_model_func,
                vision_model_func=vision_model_func,
                embedding_func=embedding_func,
                lightrag_kwargs=lightrag_kwargs,
            )
            
            # 确保LightRAG实例已初始化
            await self._rag_instance._ensure_lightrag_initialized()
            
            # 初始化缓存统计跟踪
            initialize_cache_tracking(settings.working_dir)
            
            # 创建缓存增强处理器
            self._cache_enhanced_processor = CacheEnhancedProcessor(
                rag_instance=self._rag_instance,
                storage_dir=settings.working_dir
            )
            
            # 记录初始化信息
            logger.info("🎯 RAG系统初始化成功")
            logger.info("📋 系统配置信息:")
            logger.info(f"   📁 数据目录: {settings.working_dir}")
            logger.info(f"   📤 输出目录: {settings.output_dir}")
            logger.info(f"   🏠 RAGAnything工作目录: {self._rag_instance.working_dir}")
            logger.info(f"   🤖 LLM模型: DeepSeek API ({settings.llm_binding_host})")
            logger.info(f"   🔤 嵌入模型: 本地Qwen3-Embedding-0.6B")
            logger.info(f"   💾 缓存配置: Parse Cache={settings.enable_parse_cache}, LLM Cache={settings.enable_llm_cache}")
            
            # 验证目录一致性
            if self._rag_instance.working_dir != settings.working_dir:
                logger.warning(f"⚠️ 工作目录不一致! API服务器: {settings.working_dir}, RAGAnything: {self._rag_instance.working_dir}")
            else:
                logger.info("✅ 工作目录配置一致")
                
            # 显示存储后端信息
            storage_mode = getattr(settings, 'storage_mode', 'hybrid')
            logger.info(f"🗄️ 存储模式: {storage_mode}")
            if storage_mode in ['hybrid', 'postgres_only']:
                postgres_host = os.getenv('POSTGRES_HOST', 'localhost')
                postgres_db = os.getenv('POSTGRES_DB', 'raganything')
                logger.info(f"   📊 PostgreSQL: {postgres_host}/{postgres_db}")
            if storage_mode in ['hybrid', 'neo4j_only']:
                neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
                logger.info(f"   🕸️ Neo4j: {neo4j_uri}")
                
        except Exception as e:
            logger.error(f"RAG系统初始化失败: {str(e)}")
            self._rag_instance = None
            self._cache_enhanced_processor = None
            
        finally:
            self._is_initializing = False
    
    async def get_cache_enhanced_processor(self) -> Optional[CacheEnhancedProcessor]:
        """获取缓存增强处理器"""
        # 确保RAG实例已初始化
        await self.get_rag_instance()
        return self._cache_enhanced_processor
    
    def is_ready(self) -> bool:
        """检查RAG是否就绪"""
        return self._rag_instance is not None and not self._is_initializing
    
    async def shutdown(self) -> None:
        """关闭RAG系统，清理资源"""
        with self._initialization_lock:
            if self._rag_instance:
                try:
                    # 这里可以添加RAG实例的清理逻辑
                    logger.info("关闭RAG系统")
                    self._rag_instance = None
                    self._cache_enhanced_processor = None
                except Exception as e:
                    logger.error(f"关闭RAG系统时出错: {str(e)}")
    
    async def health_check(self) -> dict:
        """健康检查"""
        is_ready = self.is_ready()
        rag_instance = await self.get_rag_instance()
        
        health_info = {
            "rag_ready": is_ready,
            "rag_instance_available": rag_instance is not None,
            "cache_processor_available": self._cache_enhanced_processor is not None,
            "working_directory": settings.working_dir,
            "output_directory": settings.output_dir,
            "device_type": settings.device_type,
            "torch_available": settings.torch_available
        }
        
        if rag_instance:
            try:
                # 可以添加更多的健康检查逻辑
                health_info["lightrag_initialized"] = hasattr(rag_instance, 'lightrag') and rag_instance.lightrag is not None
            except Exception as e:
                health_info["health_check_error"] = str(e)
        
        return health_info
    
    async def reload(self) -> bool:
        """重新加载RAG实例"""
        try:
            logger.info("重新加载RAG系统")
            await self.shutdown()
            await self._initialize()
            return self.is_ready()
        except Exception as e:
            logger.error(f"重新加载RAG系统失败: {str(e)}")
            return False


# 创建全局RAG管理器实例
_rag_manager_instance = None

def get_rag_manager() -> RAGManager:
    """获取RAG管理器实例（单例模式）"""
    global _rag_manager_instance
    if _rag_manager_instance is None:
        _rag_manager_instance = RAGManager()
    return _rag_manager_instance