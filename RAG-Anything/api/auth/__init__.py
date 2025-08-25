"""
RAG-Anything API 认证包
"""

from .simple_auth import (
    SimpleLocalAuth,
    AuthConfig,
    get_auth,
    get_current_user_optional,
    get_current_user_required
)

__all__ = [
    'SimpleLocalAuth',
    'AuthConfig',
    'get_auth',
    'get_current_user_optional',
    'get_current_user_required'
]