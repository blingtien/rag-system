"""
应用配置管理
统一管理所有环境变量和配置项
"""
import os
from typing import List, Optional
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(dotenv_path="/home/ragsvr/projects/ragsystem/.env", override=False)
load_dotenv(dotenv_path="/home/ragsvr/projects/ragsystem/.env.performance", override=True)


class Settings(BaseSettings):
    """应用设置"""
    
    # 服务器配置
    host: str = "127.0.0.1"
    port: int = 8001
    debug: bool = False
    
    # 路径配置 - 使用环境变量，避免硬编码
    upload_dir: str = os.path.abspath("../../uploads")
    working_dir: str = os.getenv("WORKING_DIR", "/home/ragsvr/projects/ragsystem/rag_storage")
    output_dir: str = os.getenv("OUTPUT_DIR", "/home/ragsvr/projects/ragsystem/output")
    
    # RAG配置
    parser: str = os.getenv("PARSER", "mineru")
    parse_method: str = os.getenv("PARSE_METHOD", "auto")
    enable_image_processing: bool = os.getenv("ENABLE_IMAGE_PROCESSING", "true").lower() == "true"
    enable_table_processing: bool = os.getenv("ENABLE_TABLE_PROCESSING", "true").lower() == "true"
    enable_equation_processing: bool = os.getenv("ENABLE_EQUATION_PROCESSING", "true").lower() == "true"
    
    # API密钥配置
    deepseek_api_key: Optional[str] = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_BINDING_API_KEY")
    llm_binding_host: str = os.getenv("LLM_BINDING_HOST", "https://api.deepseek.com/v1")
    
    # 缓存配置
    enable_parse_cache: bool = os.getenv("ENABLE_PARSE_CACHE", "true").lower() == "true"
    enable_llm_cache: bool = os.getenv("ENABLE_LLM_CACHE", "true").lower() == "true"
    enable_query_cache: bool = os.getenv("ENABLE_QUERY_CACHE", "true").lower() == "true"
    query_cache_ttl_hours: int = int(os.getenv("QUERY_CACHE_TTL_HOURS", "24"))
    
    # 批量处理配置
    max_concurrent_files: int = int(os.getenv("MAX_CONCURRENT_FILES", "4"))
    max_concurrent_processing: int = int(os.getenv("MAX_CONCURRENT_PROCESSING", "3"))
    recursive_folder_processing: bool = os.getenv("RECURSIVE_FOLDER_PROCESSING", "true").lower() == "true"
    
    # CORS配置
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    
    # 上下文配置
    context_window: int = int(os.getenv("CONTEXT_WINDOW", "1"))
    context_mode: str = os.getenv("CONTEXT_MODE", "page")
    max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "2000"))
    include_headers: bool = os.getenv("INCLUDE_HEADERS", "true").lower() == "true"
    include_captions: bool = os.getenv("INCLUDE_CAPTIONS", "true").lower() == "true"
    
    def __init__(self):
        super().__init__()
        
        # 从环境变量添加额外的CORS源
        additional_origins = os.getenv("ADDITIONAL_CORS_ORIGINS")
        if additional_origins:
            self.allowed_origins.extend([origin.strip() for origin in additional_origins.split(",")])
        
        # 确保目录存在
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.working_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
    
    @property
    def torch_available(self) -> bool:
        """检查PyTorch是否可用"""
        try:
            import torch
            return True
        except ImportError:
            return False
    
    @property
    def device_type(self) -> str:
        """获取推荐的设备类型"""
        if self.torch_available:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        return "cpu"
    
    class Config:
        env_file = ".env"


# 创建全局设置实例
settings = Settings()