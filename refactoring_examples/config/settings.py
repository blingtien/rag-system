"""
Application Configuration Management
Centralized settings with environment variable support
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Server Configuration
    host: str = Field(default="127.0.0.1", env="API_HOST")
    port: int = Field(default=8001, env="API_PORT")
    log_level: str = Field(default="info", env="LOG_LEVEL")
    
    # Storage Directories
    working_dir: str = Field(
        default="/home/ragsvr/projects/ragsystem/rag_storage",
        env="WORKING_DIR"
    )
    output_dir: str = Field(
        default="/home/ragsvr/projects/ragsystem/output",
        env="OUTPUT_DIR"
    )
    upload_dir: str = Field(
        default="../../uploads",
        env="UPLOAD_DIR"
    )
    
    # RAG Configuration
    parser: str = Field(default="mineru", env="PARSER")
    parse_method: str = Field(default="auto", env="PARSE_METHOD")
    enable_image_processing: bool = Field(default=True, env="ENABLE_IMAGE_PROCESSING")
    enable_table_processing: bool = Field(default=True, env="ENABLE_TABLE_PROCESSING")
    enable_equation_processing: bool = Field(default=True, env="ENABLE_EQUATION_PROCESSING")
    
    # API Keys
    deepseek_api_key: Optional[str] = Field(default=None, env="DEEPSEEK_API_KEY")
    llm_binding_api_key: Optional[str] = Field(default=None, env="LLM_BINDING_API_KEY")
    llm_binding_host: str = Field(
        default="https://api.deepseek.com/v1",
        env="LLM_BINDING_HOST"
    )
    
    # Cache Settings
    enable_llm_cache: bool = Field(default=True, env="ENABLE_LLM_CACHE")
    enable_parse_cache: bool = Field(default=True, env="ENABLE_PARSE_CACHE")
    
    # Processing Limits
    max_concurrent_processing: int = Field(default=3, env="MAX_CONCURRENT_PROCESSING")
    max_file_size_mb: int = Field(default=100, env="MAX_FILE_SIZE_MB")
    
    # Security
    auth_enabled: bool = Field(default=False, env="AUTH_ENABLED")
    auth_token: Optional[str] = Field(default=None, env="AUTH_TOKEN")
    localhost_bypass: bool = Field(default=True, env="LOCALHOST_BYPASS")
    
    # CORS Origins
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        env="CORS_ORIGINS"
    )
    
    @property
    def api_key(self) -> Optional[str]:
        """Get the primary API key"""
        return self.deepseek_api_key or self.llm_binding_api_key
    
    @property
    def working_dir_path(self) -> Path:
        """Get working directory as Path object"""
        return Path(self.working_dir).resolve()
    
    @property
    def output_dir_path(self) -> Path:
        """Get output directory as Path object"""
        return Path(self.output_dir).resolve()
    
    @property
    def upload_dir_path(self) -> Path:
        """Get upload directory as Path object"""
        return Path(self.upload_dir).resolve()
    
    def ensure_directories(self) -> None:
        """Ensure all required directories exist"""
        for dir_path in [self.working_dir_path, self.output_dir_path, self.upload_dir_path]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    class Config:
        env_file = "/home/ragsvr/projects/ragsystem/.env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings"""
    settings = Settings()
    settings.ensure_directories()
    return settings