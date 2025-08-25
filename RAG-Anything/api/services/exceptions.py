"""
服务层异常定义和错误处理
提供统一的异常处理模式和错误边界
"""
import traceback
import logging
from typing import Dict, Any, Optional, Type
from datetime import datetime

from fastapi import HTTPException, status


# 配置日志
logger = logging.getLogger(__name__)


class ServiceException(Exception):
    """服务层基础异常"""
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: Optional[str] = None
    ):
        self.message = message
        self.details = details or {}
        self.http_status = http_status
        self.error_code = error_code or self.__class__.__name__
        self.timestamp = datetime.now().isoformat()
        super().__init__(message)


class ValidationError(ServiceException):
    """验证错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details, status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR")


class ResourceError(ServiceException):
    """资源相关错误（不存在、无权限等）"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details, status.HTTP_404_NOT_FOUND, "RESOURCE_ERROR")


class ProcessingError(ServiceException):
    """文档处理错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details, status.HTTP_422_UNPROCESSABLE_ENTITY, "PROCESSING_ERROR")


class ConfigurationError(ServiceException):
    """配置错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details, status.HTTP_500_INTERNAL_SERVER_ERROR, "CONFIGURATION_ERROR")


class QueryError(ServiceException):
    """查询处理错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details, status.HTTP_422_UNPROCESSABLE_ENTITY, "QUERY_ERROR")


class BatchProcessingError(ServiceException):
    """批量处理错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details, status.HTTP_500_INTERNAL_SERVER_ERROR, "BATCH_PROCESSING_ERROR")


class SystemError(ServiceException):
    """系统错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details, status.HTTP_503_SERVICE_UNAVAILABLE, "SYSTEM_ERROR")


class ErrorHandler:
    """
    统一错误处理器
    
    提供集中的异常处理和日志记录
    """
    
    @staticmethod
    def handle_service_exception(exc: ServiceException) -> HTTPException:
        """
        处理服务层异常
        
        Args:
            exc: 服务层异常
            
        Returns:
            HTTPException: FastAPI HTTP异常
        """
        # 记录错误日志
        logger.error(
            f"Service Exception: {exc.error_code}: {exc.message}",
            extra={
                "error_code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
                "timestamp": exc.timestamp,
                "traceback": traceback.format_exc()
            }
        )
        
        # 构建响应详情
        detail = {
            "error_code": exc.error_code,
            "message": exc.message,
            "timestamp": exc.timestamp
        }
        
        # 在调试模式下添加详细信息
        import os
        if os.getenv("DEBUG", "false").lower() == "true":
            detail["details"] = exc.details
        
        return HTTPException(status_code=exc.http_status, detail=detail)
    
    @staticmethod
    def handle_generic_exception(exc: Exception) -> HTTPException:
        """
        处理通用异常
        
        Args:
            exc: 通用异常
            
        Returns:
            HTTPException: FastAPI HTTP异常
        """
        timestamp = datetime.now().isoformat()
        
        # 记录错误日志
        logger.error(
            f"Unexpected Exception: {exc.__class__.__name__}: {str(exc)}",
            extra={
                "exception_type": exc.__class__.__name__,
                "message": str(exc),
                "timestamp": timestamp,
                "traceback": traceback.format_exc()
            }
        )
        
        # 构建响应详情
        detail = {
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "内部服务器错误",
            "timestamp": timestamp
        }
        
        # 在调试模式下添加详细信息
        import os
        if os.getenv("DEBUG", "false").lower() == "true":
            detail["debug_message"] = str(exc)
            detail["exception_type"] = exc.__class__.__name__
        
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


def error_boundary(func):
    """
    错误边界装饰器 - 用于包装服务层方法
    
    使用方式:
    @error_boundary
    async def some_service_method(self, ...):
        ...
    """
    import functools
    import asyncio
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except ServiceException as e:
            raise ErrorHandler.handle_service_exception(e)
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            raise ErrorHandler.handle_generic_exception(e)
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ServiceException as e:
            raise ErrorHandler.handle_service_exception(e)
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            raise ErrorHandler.handle_generic_exception(e)
    
    # 根据函数类型返回对应的包装器
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


class ServiceResult:
    """
    服务结果包装器
    
    提供一致的服务层返回类型
    """
    
    def __init__(self, success: bool, data: Any = None, error: Optional[str] = None):
        self.success = success
        self.data = data
        self.error = error
        self.timestamp = datetime.now().isoformat()
    
    @classmethod
    def success_result(cls, data: Any = None) -> "ServiceResult":
        """创建成功结果"""
        return cls(success=True, data=data)
    
    @classmethod
    def error_result(cls, error: str) -> "ServiceResult":
        """创建错误结果"""
        return cls(success=False, error=error)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "success": self.success,
            "timestamp": self.timestamp
        }
        
        if self.success:
            result["data"] = self.data
        else:
            result["error"] = self.error
        
        return result
    
    def raise_if_error(self):
        """如果是错误结果则抛出异常"""
        if not self.success:
            raise ServiceException(self.error or "Unknown error")


# 类型注解
ErrorHandlerType = Type[ErrorHandler]
ServiceExceptionType = Type[ServiceException]