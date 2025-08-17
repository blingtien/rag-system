"""
增强的错误处理和日志系统
为RAG-Anything Web API提供统一的错误处理和结构化日志
"""

import os
import sys
import traceback
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import uuid
import json

import structlog
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# === 错误响应模型 ===

class ErrorDetail(BaseModel):
    error_code: str
    error_message: str
    user_message: str
    timestamp: str
    request_id: str
    path: Optional[str] = None
    method: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class ValidationErrorDetail(BaseModel):
    field: str
    message: str
    invalid_value: Any

class ValidationErrorResponse(BaseModel):
    error_code: str = "VALIDATION_ERROR"
    error_message: str = "请求数据验证失败"
    user_message: str = "请检查输入数据格式"
    timestamp: str
    request_id: str
    validation_errors: List[ValidationErrorDetail]

# === 自定义异常类 ===

class APIError(Exception):
    """API业务错误基类"""
    
    def __init__(
        self, 
        message: str, 
        user_message: str = None,
        error_code: str = "API_ERROR",
        status_code: int = 500,
        details: Dict[str, Any] = None
    ):
        self.message = message
        self.user_message = user_message or message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class ValidationError(APIError):
    """数据验证错误"""
    
    def __init__(self, message: str, field: str = None, invalid_value: Any = None):
        super().__init__(
            message=message,
            user_message="请检查输入数据格式",
            error_code="VALIDATION_ERROR",
            status_code=400
        )
        self.field = field
        self.invalid_value = invalid_value

class AuthenticationError(APIError):
    """认证错误"""
    
    def __init__(self, message: str = "认证失败"):
        super().__init__(
            message=message,
            user_message="请检查API密钥或重新登录",
            error_code="AUTHENTICATION_ERROR",
            status_code=401
        )

class AuthorizationError(APIError):
    """授权错误"""
    
    def __init__(self, message: str = "权限不足"):
        super().__init__(
            message=message,
            user_message="您没有执行此操作的权限",
            error_code="AUTHORIZATION_ERROR",
            status_code=403
        )

class ResourceNotFoundError(APIError):
    """资源不存在错误"""
    
    def __init__(self, resource: str, resource_id: str = None):
        message = f"{resource}不存在"
        if resource_id:
            message += f" (ID: {resource_id})"
        
        super().__init__(
            message=message,
            user_message=f"请求的{resource}不存在",
            error_code="RESOURCE_NOT_FOUND",
            status_code=404
        )

class ServiceUnavailableError(APIError):
    """服务不可用错误"""
    
    def __init__(self, service: str, reason: str = None):
        message = f"{service}服务不可用"
        if reason:
            message += f": {reason}"
        
        super().__init__(
            message=message,
            user_message=f"{service}服务暂时不可用，请稍后重试",
            error_code="SERVICE_UNAVAILABLE",
            status_code=503
        )

class RateLimitError(APIError):
    """频率限制错误"""
    
    def __init__(self, limit: str = "请求"):
        super().__init__(
            message=f"{limit}频率超限",
            user_message="请求过于频繁，请稍后重试",
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429
        )

# === 结构化日志配置 ===

def configure_logging(log_level: str = "INFO", log_file: str = None):
    """配置结构化日志"""
    
    # 配置structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.dev.ConsoleRenderer() if not log_file else structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level.upper())),
        logger_factory=structlog.WriteLoggerFactory(
            file=open(log_file, "a") if log_file else sys.stderr
        ),
        cache_logger_on_first_use=False,
    )
    
    # 配置标准logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
        stream=sys.stderr if not log_file else None,
        filename=log_file if log_file else None
    )

# === 错误处理器工厂 ===

class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self):
        self.logger = structlog.get_logger(__name__)
    
    def create_error_response(
        self, 
        error: Exception, 
        request: Request = None,
        request_id: str = None
    ) -> JSONResponse:
        """创建统一的错误响应"""
        
        if not request_id:
            request_id = str(uuid.uuid4())
        
        timestamp = datetime.now().isoformat()
        
        # 记录错误日志
        self._log_error(error, request, request_id)
        
        # 根据异常类型创建响应
        if isinstance(error, APIError):
            return self._handle_api_error(error, request, request_id, timestamp)
        elif isinstance(error, HTTPException):
            return self._handle_http_exception(error, request, request_id, timestamp)
        else:
            return self._handle_generic_error(error, request, request_id, timestamp)
    
    def _log_error(self, error: Exception, request: Request = None, request_id: str = None):
        """记录错误日志"""
        
        log_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "request_id": request_id,
        }
        
        if request:
            log_data.update({
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            })
        
        if isinstance(error, APIError):
            self.logger.warning("API业务错误", **log_data, error_code=error.error_code)
        else:
            log_data["traceback"] = traceback.format_exc()
            self.logger.error("系统异常", **log_data)
    
    def _handle_api_error(
        self, 
        error: APIError, 
        request: Request, 
        request_id: str, 
        timestamp: str
    ) -> JSONResponse:
        """处理API业务错误"""
        
        return JSONResponse(
            status_code=error.status_code,
            content=ErrorDetail(
                error_code=error.error_code,
                error_message=error.message,
                user_message=error.user_message,
                timestamp=timestamp,
                request_id=request_id,
                path=request.url.path if request else None,
                method=request.method if request else None,
                details=error.details
            ).dict()
        )
    
    def _handle_http_exception(
        self, 
        error: HTTPException, 
        request: Request, 
        request_id: str, 
        timestamp: str
    ) -> JSONResponse:
        """处理FastAPI HTTP异常"""
        
        return JSONResponse(
            status_code=error.status_code,
            content=ErrorDetail(
                error_code="HTTP_ERROR",
                error_message=str(error.detail),
                user_message=self._get_user_friendly_message(error.status_code),
                timestamp=timestamp,
                request_id=request_id,
                path=request.url.path if request else None,
                method=request.method if request else None
            ).dict()
        )
    
    def _handle_generic_error(
        self, 
        error: Exception, 
        request: Request, 
        request_id: str, 
        timestamp: str
    ) -> JSONResponse:
        """处理通用异常"""
        
        # 生产环境不暴露具体错误信息
        is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
        
        error_message = "内部服务器错误" if is_production else str(error)
        details = None if is_production else {"traceback": traceback.format_exc()}
        
        return JSONResponse(
            status_code=500,
            content=ErrorDetail(
                error_code="INTERNAL_ERROR",
                error_message=error_message,
                user_message="服务器内部错误，请稍后重试",
                timestamp=timestamp,
                request_id=request_id,
                path=request.url.path if request else None,
                method=request.method if request else None,
                details=details
            ).dict()
        )
    
    def _get_user_friendly_message(self, status_code: int) -> str:
        """获取用户友好的错误信息"""
        
        messages = {
            400: "请求参数有误，请检查输入",
            401: "认证失败，请检查API密钥",
            403: "权限不足，无法执行此操作",
            404: "请求的资源不存在",
            405: "不支持的请求方法",
            429: "请求过于频繁，请稍后重试",
            500: "服务器内部错误，请稍后重试",
            502: "网关错误，请稍后重试",
            503: "服务暂时不可用，请稍后重试",
            504: "请求超时，请稍后重试"
        }
        
        return messages.get(status_code, "未知错误，请联系管理员")

# === 异常处理装饰器 ===

def handle_exceptions(func):
    """异常处理装饰器"""
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except APIError:
            raise  # 让FastAPI处理器处理
        except Exception as e:
            logger = structlog.get_logger(__name__)
            logger.error(f"函数 {func.__name__} 执行失败", error=str(e), traceback=traceback.format_exc())
            raise APIError(f"执行 {func.__name__} 失败: {str(e)}")
    
    return wrapper

# === 请求验证器 ===

class RequestValidator:
    """请求验证器"""
    
    @staticmethod
    def validate_file_upload(file, max_size: int = 100 * 1024 * 1024):
        """验证文件上传"""
        
        if not file.filename:
            raise ValidationError("文件名不能为空", "filename", file.filename)
        
        if file.size and file.size > max_size:
            raise ValidationError(
                f"文件大小超过限制 ({max_size // 1024 // 1024}MB)",
                "file_size",
                file.size
            )
        
        # 检查文件扩展名
        allowed_extensions = {'.pdf', '.doc', '.docx', '.txt', '.md', '.jpg', '.png', '.jpeg'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise ValidationError(
                f"不支持的文件类型: {file_ext}",
                "file_extension",
                file_ext
            )
    
    @staticmethod
    def validate_query_request(query: str, mode: str):
        """验证查询请求"""
        
        if not query or not query.strip():
            raise ValidationError("查询内容不能为空", "query", query)
        
        if len(query) > 10000:
            raise ValidationError("查询内容过长 (最大10000字符)", "query", len(query))
        
        valid_modes = {"naive", "local", "global", "hybrid", "mix", "bypass"}
        if mode not in valid_modes:
            raise ValidationError(
                f"无效的查询模式: {mode}",
                "mode",
                mode
            )

# === 全局错误处理器实例 ===
error_handler = ErrorHandler()

# 配置日志
log_level = os.getenv("LOG_LEVEL", "INFO")
log_file = os.getenv("LOG_FILE")
configure_logging(log_level, log_file)