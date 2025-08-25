#!/usr/bin/env python3
"""
简化认证机制 - RAG-Anything API
专为本地单人使用场景设计的轻量级认证
提供基础安全保护而不增加使用复杂度
"""

import os
import logging
from typing import Optional
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

class SimpleLocalAuth:
    """
    本地使用的简化认证机制
    
    特性：
    1. 支持简单的API令牌认证
    2. localhost访问可选认证（开发友好）
    3. 环境变量配置
    4. 无需复杂的用户管理
    """
    
    def __init__(self):
        # 从环境变量读取配置
        self.api_token = os.getenv("RAG_API_TOKEN")
        self.require_auth = os.getenv("RAG_REQUIRE_AUTH", "false").lower() == "true"
        self.localhost_bypass = os.getenv("RAG_LOCALHOST_BYPASS", "true").lower() == "true"
        
        # 如果没有设置令牌且要求认证，生成一个默认令牌
        if self.require_auth and not self.api_token:
            self.api_token = "rag-local-default-token-2024"
            logger.warning("未设置RAG_API_TOKEN环境变量，使用默认令牌。生产环境请设置自定义令牌！")
        
        # 安全配置
        self.security = HTTPBearer(auto_error=False)
        
        # 记录配置状态
        if self.require_auth:
            logger.info("认证已启用，需要有效的API令牌")
        else:
            logger.info("认证已禁用，API开放访问")
            
        if self.localhost_bypass:
            logger.info("localhost访问绕过认证已启用")
    
    def _is_localhost_request(self, request: Request) -> bool:
        """检查是否是本地请求"""
        if not hasattr(request, 'client'):
            return False
            
        client_host = getattr(request.client, 'host', None)
        if not client_host:
            return False
            
        localhost_ips = ["127.0.0.1", "::1", "localhost"]
        return client_host in localhost_ips
    
    async def verify_token_optional(self, 
                                  request: Request,
                                  credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))) -> str:
        """
        可选的令牌验证（主要用于开发和测试）
        
        Returns:
            用户标识字符串
        """
        # 如果完全不需要认证
        if not self.require_auth:
            return "anonymous_user"
        
        # 如果允许localhost绕过认证
        if self.localhost_bypass and self._is_localhost_request(request):
            logger.debug("localhost请求，绕过认证")
            return "localhost_user"
        
        # 检查令牌
        if not credentials:
            raise HTTPException(
                status_code=401, 
                detail="需要API令牌访问。请在请求头中包含 'Authorization: Bearer <token>'"
            )
        
        if credentials.credentials != self.api_token:
            raise HTTPException(
                status_code=401, 
                detail="无效的API令牌"
            )
        
        return "authenticated_user"
    
    async def verify_token_required(self, 
                                  request: Request,
                                  credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> str:
        """
        强制令牌验证（用于敏感操作）
        
        Returns:
            用户标识字符串
        """
        # 如果允许localhost绕过认证（但仍然记录）
        if self.localhost_bypass and self._is_localhost_request(request):
            logger.info("敏感操作的localhost访问，允许但记录")
            return "localhost_user"
        
        # 强制检查令牌
        if not self.api_token:
            raise HTTPException(
                status_code=500,
                detail="服务器认证配置错误"
            )
        
        if credentials.credentials != self.api_token:
            raise HTTPException(
                status_code=401, 
                detail="无效的API令牌"
            )
        
        return "authenticated_user"
    
    def get_auth_info(self) -> dict:
        """获取认证配置信息（用于调试）"""
        return {
            "auth_enabled": self.require_auth,
            "localhost_bypass": self.localhost_bypass,
            "token_configured": bool(self.api_token),
            "auth_status": "enabled" if self.require_auth else "disabled"
        }

class AuthConfig:
    """认证配置帮助类"""
    
    @staticmethod
    def setup_for_development():
        """为开发环境设置认证"""
        os.environ.setdefault("RAG_REQUIRE_AUTH", "false")
        os.environ.setdefault("RAG_LOCALHOST_BYPASS", "true")
        logger.info("开发环境认证配置已设置")
    
    @staticmethod
    def setup_for_production():
        """为生产环境设置认证"""
        os.environ.setdefault("RAG_REQUIRE_AUTH", "true")
        os.environ.setdefault("RAG_LOCALHOST_BYPASS", "false")
        
        if not os.getenv("RAG_API_TOKEN"):
            logger.error("生产环境必须设置RAG_API_TOKEN环境变量！")
            raise ValueError("生产环境缺少API令牌配置")
        
        logger.info("生产环境认证配置已设置")
    
    @staticmethod
    def generate_sample_env_config():
        """生成示例环境配置"""
        import uuid
        sample_token = f"rag-api-{uuid.uuid4().hex[:16]}"
        
        return f"""# RAG-Anything API 认证配置
# 是否启用认证（true/false）
RAG_REQUIRE_AUTH=true

# API访问令牌
RAG_API_TOKEN={sample_token}

# 是否允许localhost绕过认证（开发用）
RAG_LOCALHOST_BYPASS=true

# 使用方法：
# 1. 将此配置添加到 .env 文件
# 2. 重启API服务器
# 3. 使用令牌访问API：
#    curl -H "Authorization: Bearer {sample_token}" http://localhost:8001/api/v1/documents
"""

# 全局认证实例
_auth_instance = None

def get_auth() -> SimpleLocalAuth:
    """获取认证实例（单例）"""
    global _auth_instance
    
    if _auth_instance is None:
        _auth_instance = SimpleLocalAuth()
    
    return _auth_instance

def get_current_user_optional(request: Request, auth: SimpleLocalAuth = Depends(get_auth)):
    """获取当前用户（可选认证）- 依赖注入函数"""
    return auth.verify_token_optional(request)

def get_current_user_required(request: Request, auth: SimpleLocalAuth = Depends(get_auth)):
    """获取当前用户（必需认证）- 依赖注入函数"""
    return auth.verify_token_required(request)

# 导出主要接口
__all__ = [
    'SimpleLocalAuth', 
    'AuthConfig', 
    'get_auth', 
    'get_current_user_optional', 
    'get_current_user_required'
]