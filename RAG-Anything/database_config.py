"""
数据库配置模块
为RAG-Anything配置PostgreSQL和Neo4j数据库集成
基于Issue #6的设计方案
"""

import os
from typing import Dict, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DatabaseConfig:
    """数据库集成配置"""
    
    # PostgreSQL配置 - 与API服务器保持一致
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "raganything"
    postgres_user: str = "ragsvr"  # 使用实际存在的用户
    postgres_password: str = ""    # 空密码用于peer认证
    postgres_schema: str = "public"
    
    # Neo4j配置
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "raganything_neo4j"
    neo4j_database: str = "neo4j"
    
    # Redis配置 (缓存)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    
    # 集成模式配置
    storage_mode: str = "hybrid"  # "hybrid", "postgres_only", "neo4j_only"
    enable_caching: bool = True
    
    def get_postgres_url(self) -> str:
        """获取PostgreSQL连接URL"""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    def get_neo4j_config(self) -> Dict[str, Any]:
        """获取Neo4j连接配置"""
        return {
            "uri": self.neo4j_uri,
            "auth": (self.neo4j_user, self.neo4j_password),
            "database": self.neo4j_database
        }
    
    def get_redis_config(self) -> Dict[str, Any]:
        """获取Redis连接配置"""
        config = {
            "host": self.redis_host,
            "port": self.redis_port,
            "db": self.redis_db
        }
        if self.redis_password:
            config["password"] = self.redis_password
        return config


def create_lightrag_kwargs(db_config: DatabaseConfig) -> Dict[str, Any]:
    """
    基于数据库配置创建LightRAG初始化参数
    根据Issue #6的设计方案配置存储后端
    使用LightRAG 1.4.6的正确存储类名和环境变量配置
    """
    lightrag_kwargs = {}
    
    # 基础性能优化配置
    lightrag_kwargs.update({
        "max_parallel_insert": 4,
        "embedding_batch_num": 16,
        "embedding_func_max_async": 8,
        "llm_model_max_async": 4,
    })
    
    if db_config.storage_mode in ["hybrid", "postgres_only"]:
        # PostgreSQL配置 - LightRAG将从环境变量中读取连接信息
        lightrag_kwargs.update({
            # KV存储使用PostgreSQL
            "kv_storage": "PGKVStorage", 
            # 向量存储使用PostgreSQL + pgvector
            "vector_storage": "PGVectorStorage",
            # 文档状态存储使用PostgreSQL
            "doc_status_storage": "PGDocStatusStorage",
        })
        print(f"✅ 配置PostgreSQL存储: {db_config.postgres_host}:{db_config.postgres_port}/{db_config.postgres_db}")
        print(f"   LightRAG将从环境变量POSTGRES_*读取连接信息")
    
    if db_config.storage_mode in ["hybrid", "neo4j_only"]:
        # Neo4j配置 - LightRAG将从环境变量中读取连接信息
        lightrag_kwargs.update({
            # 使用Neo4j作为图存储（正确类名）
            "graph_storage": "Neo4JStorage",
        })
        print(f"✅ 配置Neo4j存储: {db_config.neo4j_uri}")
        print(f"   LightRAG将从环境变量NEO4J_*读取连接信息")
    
    # 在hybrid模式下，如果只配置了Neo4j，需要为KV和向量存储设置默认值
    if db_config.storage_mode == "hybrid" and "kv_storage" not in lightrag_kwargs:
        lightrag_kwargs.update({
            "vector_storage": "NanoVectorDBStorage",
            "kv_storage": "JsonKVStorage", 
            "doc_status_storage": "JsonDocStatusStorage",
        })
        print(f"⚠️  Hybrid模式：Neo4j用于图存储，KV和向量存储使用文件系统")
    
    # 如果启用缓存
    if db_config.enable_caching:
        lightrag_kwargs.update({
            "enable_llm_cache": True,
        })
    
    return lightrag_kwargs


def load_database_config() -> DatabaseConfig:
    """
    从环境变量加载数据库配置
    支持.env文件配置
    """
    return DatabaseConfig(
        # PostgreSQL配置
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=os.getenv("POSTGRES_DB", "raganything"),
        postgres_user=os.getenv("POSTGRES_USER", "raganything_user"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", "raganything_pass"),
        postgres_schema=os.getenv("POSTGRES_SCHEMA", "public"),
        
        # Neo4j配置
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "raganything_neo4j"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        
        # Redis配置
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_db=int(os.getenv("REDIS_DB", "0")),
        redis_password=os.getenv("REDIS_PASSWORD", ""),
        
        # 集成模式
        storage_mode=os.getenv("STORAGE_MODE", "hybrid"),
        enable_caching=os.getenv("ENABLE_CACHING", "true").lower() == "true"
    )


# 示例用法
if __name__ == "__main__":
    # 加载配置
    db_config = load_database_config()
    print(f"数据库配置: {db_config}")
    
    # 生成LightRAG参数
    lightrag_kwargs = create_lightrag_kwargs(db_config)
    print(f"LightRAG配置: {lightrag_kwargs}")