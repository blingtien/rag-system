#!/usr/bin/env python3
"""
统一错误处理中间件
集成现有的enhanced_error_handler和services异常体系
提供全局异常捕获、错误追踪和结构化响应
"""

import os
import uuid
import time
import json
import logging
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# 导入现有的错误处理组件
from enhanced_error_handler import enhanced_error_handler, ErrorInfo as EnhancedErrorInfo
from services.exceptions import (
    ServiceException, ValidationError, ResourceError, ProcessingError,
    ConfigurationError, QueryError, BatchProcessingError, SystemError
)

# 错误追踪上下文
error_context: ContextVar[str] = ContextVar('error_context', default='')


@dataclass
class ErrorContext:
    """错误上下文信息"""
    request_id: str
    user_id: Optional[str]
    path: str
    method: str
    query_params: Dict[str, Any]
    headers: Dict[str, Any]
    timestamp: datetime
    execution_time_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'request_id': self.request_id,
            'user_id': self.user_id,
            'path': self.path,
            'method': self.method,
            'query_params': self.query_params,
            'headers': dict(self.headers),
            'timestamp': self.timestamp.isoformat(),
            'execution_time_ms': self.execution_time_ms
        }


@dataclass 
class StructuredError:
    """结构化错误响应"""
    error_id: str
    error_code: str
    message: str
    user_message: str
    details: Optional[Dict[str, Any]]
    suggested_solution: Optional[str]
    severity: str
    category: str
    is_recoverable: bool
    timestamp: str
    context: Optional[Dict[str, Any]] = None
    
    def to_response_dict(self, include_debug: bool = False) -> Dict[str, Any]:
        """转换为API响应格式"""
        response = {
            'error': {
                'id': self.error_id,
                'code': self.error_code,
                'message': self.user_message,
                'severity': self.severity,
                'category': self.category,
                'is_recoverable': self.is_recoverable,
                'timestamp': self.timestamp
            }
        }
        
        # 生产环境下不暴露敏感信息
        if include_debug:
            response['error']['technical_message'] = self.message
            response['error']['details'] = self.details
            response['error']['suggested_solution'] = self.suggested_solution
            response['error']['context'] = self.context
        elif self.suggested_solution:
            response['error']['suggestion'] = self.suggested_solution
            
        return response


class UnifiedErrorHandler(BaseHTTPMiddleware):
    """
    统一错误处理中间件
    
    功能:
    1. 全局异常捕获和处理
    2. 错误ID生成和追踪
    3. 结构化错误响应
    4. 集成现有错误处理组件
    5. 开发/生产环境区分
    """
    
    def __init__(self, app, enable_debug: bool = None):
        super().__init__(app)
        self.logger = logging.getLogger(__name__)
        self.enable_debug = enable_debug if enable_debug is not None else (
            os.getenv("DEBUG", "false").lower() == "true"
        )
        self.error_stats: Dict[str, int] = {}
        
    async def dispatch(self, request: Request, call_next):
        """处理请求和异常"""
        # 生成请求ID
        request_id = str(uuid.uuid4())
        error_context.set(request_id)
        
        # 记录请求开始时间
        start_time = time.time()
        
        # 构建错误上下文
        context = ErrorContext(
            request_id=request_id,
            user_id=self._extract_user_id(request),
            path=str(request.url.path),
            method=request.method,
            query_params=dict(request.query_params),
            headers=self._filter_sensitive_headers(request.headers),
            timestamp=datetime.now()
        )
        
        # 添加请求ID到响应头
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            
            # 计算执行时间
            execution_time = (time.time() - start_time) * 1000
            response.headers["X-Execution-Time"] = f"{execution_time:.2f}ms"
            
            return response
            
        except Exception as exc:
            # 计算执行时间
            context.execution_time_ms = (time.time() - start_time) * 1000
            
            # 处理异常并返回结构化响应
            return await self._handle_exception(exc, context)
    
    async def _handle_exception(self, exc: Exception, context: ErrorContext) -> JSONResponse:
        """统一异常处理"""
        try:
            # 1. 首先尝试使用enhanced_error_handler处理
            if hasattr(enhanced_error_handler, 'categorize_error'):
                enhanced_error = enhanced_error_handler.categorize_error(
                    exc, context.to_dict()
                )
                structured_error = self._convert_enhanced_error(enhanced_error, context)
            else:
                # 2. 使用服务层异常体系
                structured_error = self._handle_service_exception(exc, context)
            
            # 3. 记录错误日志
            await self._log_error(structured_error, exc, context)
            
            # 4. 更新错误统计
            self._update_error_stats(structured_error)
            
            # 5. 返回结构化响应
            status_code = self._get_http_status_code(structured_error)
            response_data = structured_error.to_response_dict(self.enable_debug)
            
            return JSONResponse(
                status_code=status_code,
                content=response_data,
                headers={"X-Request-ID": context.request_id}
            )
            
        except Exception as handler_exc:
            # 异常处理器本身出错的兜底处理
            self.logger.error(f"Error handler failed: {handler_exc}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "id": context.request_id,
                        "code": "HANDLER_ERROR",
                        "message": "Internal error handler failure",
                        "severity": "critical",
                        "timestamp": datetime.now().isoformat()
                    }
                },
                headers={"X-Request-ID": context.request_id}
            )
    
    def _convert_enhanced_error(self, enhanced_error: EnhancedErrorInfo, context: ErrorContext) -> StructuredError:
        """将enhanced_error_handler的错误转换为结构化错误"""
        return StructuredError(
            error_id=context.request_id,
            error_code=enhanced_error.category.value.upper(),
            message=str(enhanced_error.original_error),
            user_message=enhanced_error.user_message,
            details=enhanced_error.context,
            suggested_solution=enhanced_error.suggested_solution,
            severity=self._map_enhanced_severity(enhanced_error.category),
            category=enhanced_error.category.value,
            is_recoverable=enhanced_error.is_recoverable,
            timestamp=enhanced_error.occurred_at.isoformat(),
            context=context.to_dict()
        )
    
    def _handle_service_exception(self, exc: Exception, context: ErrorContext) -> StructuredError:
        """处理服务层异常"""
        if isinstance(exc, ServiceException):
            return StructuredError(
                error_id=context.request_id,
                error_code=exc.error_code,
                message=exc.message,
                user_message=self._get_user_friendly_message(exc),
                details=exc.details,
                suggested_solution=self._get_suggested_solution(exc),
                severity=self._get_exception_severity(exc),
                category=self._get_exception_category(exc),
                is_recoverable=self._is_exception_recoverable(exc),
                timestamp=exc.timestamp,
                context=context.to_dict()
            )
        elif isinstance(exc, HTTPException):
            return StructuredError(
                error_id=context.request_id,
                error_code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
                user_message=self._get_http_user_message(exc.status_code),
                details={"status_code": exc.status_code},
                suggested_solution=self._get_http_solution(exc.status_code),
                severity=self._get_http_severity(exc.status_code),
                category="http_error",
                is_recoverable=exc.status_code < 500,
                timestamp=datetime.now().isoformat(),
                context=context.to_dict()
            )
        else:
            # 未知异常的默认处理
            return StructuredError(
                error_id=context.request_id,
                error_code="UNKNOWN_ERROR",
                message=str(exc),
                user_message="系统发生未知错误",
                details={"exception_type": exc.__class__.__name__},
                suggested_solution="请稍后重试，如问题持续请联系技术支持",
                severity="high",
                category="system",
                is_recoverable=False,
                timestamp=datetime.now().isoformat(),
                context=context.to_dict()
            )
    
    def _map_enhanced_severity(self, category) -> str:
        """映射enhanced_error_handler的错误严重程度"""
        severity_map = {
            "permanent": "high",
            "gpu_memory": "medium", 
            "system": "high",
            "network": "medium",
            "timeout": "medium",
            "transient": "low",
            "validation": "medium",
            "unknown": "medium"
        }
        return severity_map.get(category.value, "medium")
    
    def _get_user_friendly_message(self, exc: ServiceException) -> str:
        """获取用户友好的错误消息"""
        messages = {
            "ValidationError": "输入数据验证失败",
            "ResourceError": "请求的资源不存在或无权访问",
            "ProcessingError": "文档处理过程中发生错误",
            "ConfigurationError": "系统配置错误",
            "QueryError": "查询处理失败",
            "BatchProcessingError": "批量处理操作失败",
            "SystemError": "系统服务暂时不可用"
        }
        return messages.get(exc.error_code, exc.message)
    
    def _get_suggested_solution(self, exc: ServiceException) -> Optional[str]:
        """获取建议解决方案"""
        solutions = {
            "ValidationError": "请检查输入数据的格式和内容",
            "ResourceError": "请确认资源ID正确且您有相应权限",
            "ProcessingError": "请检查文档格式，或稍后重试",
            "ConfigurationError": "请联系系统管理员检查配置",
            "QueryError": "请检查查询参数或稍后重试",
            "BatchProcessingError": "请减少批量处理的文档数量后重试",
            "SystemError": "请稍后重试，如问题持续请联系技术支持"
        }
        return solutions.get(exc.error_code)
    
    def _get_exception_severity(self, exc: ServiceException) -> str:
        """获取异常严重程度"""
        severity_map = {
            "ValidationError": "medium",
            "ResourceError": "low", 
            "ProcessingError": "medium",
            "ConfigurationError": "high",
            "QueryError": "medium",
            "BatchProcessingError": "medium",
            "SystemError": "high"
        }
        return severity_map.get(exc.error_code, "medium")
    
    def _get_exception_category(self, exc: ServiceException) -> str:
        """获取异常分类"""
        category_map = {
            "ValidationError": "validation",
            "ResourceError": "resource",
            "ProcessingError": "processing", 
            "ConfigurationError": "system",
            "QueryError": "query",
            "BatchProcessingError": "processing",
            "SystemError": "system"
        }
        return category_map.get(exc.error_code, "unknown")
    
    def _is_exception_recoverable(self, exc: ServiceException) -> bool:
        """判断异常是否可恢复"""
        recoverable = {
            "ValidationError": False,
            "ResourceError": False,
            "ProcessingError": True,
            "ConfigurationError": False, 
            "QueryError": True,
            "BatchProcessingError": True,
            "SystemError": True
        }
        return recoverable.get(exc.error_code, False)
    
    def _get_http_user_message(self, status_code: int) -> str:
        """获取HTTP状态码对应的用户友好消息"""
        messages = {
            400: "请求参数有误",
            401: "未授权访问",
            403: "权限不足",
            404: "请求的资源不存在",
            405: "不支持的请求方法",
            422: "请求数据格式错误",
            429: "请求频率过高",
            500: "服务器内部错误",
            502: "网关错误",
            503: "服务暂时不可用",
            504: "网关超时"
        }
        return messages.get(status_code, f"HTTP错误 {status_code}")
    
    def _get_http_solution(self, status_code: int) -> str:
        """获取HTTP错误的解决建议"""
        solutions = {
            400: "请检查请求参数的格式和内容",
            401: "请先登录或检查认证信息",
            403: "请联系管理员获取相应权限",
            404: "请检查请求的URL是否正确",
            405: "请使用正确的HTTP方法",
            422: "请检查提交的数据格式",
            429: "请降低请求频率后重试",
            500: "请稍后重试，如问题持续请联系技术支持",
            502: "请稍后重试",
            503: "服务正在维护，请稍后重试",
            504: "请求超时，请稍后重试"
        }
        return solutions.get(status_code, "请稍后重试或联系技术支持")
    
    def _get_http_severity(self, status_code: int) -> str:
        """获取HTTP错误严重程度"""
        if status_code < 400:
            return "low"
        elif status_code < 500:
            return "medium"
        else:
            return "high"
    
    def _get_http_status_code(self, error: StructuredError) -> int:
        """根据错误类型获取HTTP状态码"""
        code_map = {
            "validation": 400,
            "resource": 404,
            "processing": 422,
            "query": 422,
            "system": 503,
            "network": 502,
            "unknown": 500
        }
        return code_map.get(error.category, 500)
    
    async def _log_error(self, error: StructuredError, exc: Exception, context: ErrorContext):
        """记录错误日志"""
        log_data = {
            "error_id": error.error_id,
            "error_code": error.error_code,
            "category": error.category,
            "severity": error.severity,
            "message": error.message,
            "context": context.to_dict(),
            "exception_type": exc.__class__.__name__,
            "traceback": traceback.format_exc() if self.enable_debug else None
        }
        
        # 根据严重程度选择日志级别
        if error.severity == "critical":
            self.logger.critical(f"Critical error: {error.message}", extra=log_data)
        elif error.severity == "high":
            self.logger.error(f"High severity error: {error.message}", extra=log_data)
        elif error.severity == "medium":
            self.logger.warning(f"Medium severity error: {error.message}", extra=log_data)
        else:
            self.logger.info(f"Low severity error: {error.message}", extra=log_data)
    
    def _update_error_stats(self, error: StructuredError):
        """更新错误统计"""
        key = f"{error.category}:{error.error_code}"
        self.error_stats[key] = self.error_stats.get(key, 0) + 1
    
    def _extract_user_id(self, request: Request) -> Optional[str]:
        """从请求中提取用户ID"""
        # 尝试从不同来源获取用户ID
        user_id = request.headers.get("X-User-ID")
        if not user_id and hasattr(request.state, 'user_id'):
            user_id = request.state.user_id
        return user_id
    
    def _filter_sensitive_headers(self, headers) -> Dict[str, str]:
        """过滤敏感头信息"""
        sensitive_headers = {'authorization', 'cookie', 'x-api-key', 'x-auth-token'}
        return {
            k: v if k.lower() not in sensitive_headers else '[FILTERED]'
            for k, v in headers.items()
        }
    
    def get_error_stats(self) -> Dict[str, int]:
        """获取错误统计"""
        return self.error_stats.copy()
    
    def clear_error_stats(self):
        """清除错误统计"""
        self.error_stats.clear()


# 工具函数
def get_current_error_context() -> str:
    """获取当前错误上下文ID"""
    return error_context.get('')


def create_error_handler_middleware(enable_debug: bool = None) -> UnifiedErrorHandler:
    """创建错误处理中间件实例"""
    return UnifiedErrorHandler(None, enable_debug)