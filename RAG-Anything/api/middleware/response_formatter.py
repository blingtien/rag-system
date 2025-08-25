#!/usr/bin/env python3
"""
结构化响应格式化器
提供统一的API响应格式，支持多语言和用户友好的错误信息
"""

import os
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from fastapi import Request
from fastapi.responses import JSONResponse


class ResponseType(Enum):
    """响应类型"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ResponseMetadata:
    """响应元数据"""
    request_id: str
    timestamp: str
    execution_time_ms: Optional[float] = None
    api_version: str = "v1"
    server_time: Optional[str] = None
    
    def __post_init__(self):
        if not self.server_time:
            self.server_time = datetime.now().isoformat()


@dataclass
class PaginationInfo:
    """分页信息"""
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


@dataclass
class ErrorDetail:
    """错误详细信息"""
    field: Optional[str] = None
    code: Optional[str] = None
    message: Optional[str] = None
    value: Optional[Any] = None


class MessageTemplates:
    """多语言消息模板"""
    
    MESSAGES = {
        'zh': {
            # 通用错误消息
            'validation_error': '输入数据验证失败',
            'resource_not_found': '请求的资源不存在',
            'permission_denied': '权限不足',
            'rate_limit_exceeded': '请求频率过高，请稍后重试',
            'internal_server_error': '服务器内部错误',
            'service_unavailable': '服务暂时不可用',
            'timeout_error': '请求超时',
            'network_error': '网络连接错误',
            
            # 业务相关错误消息
            'document_upload_failed': '文档上传失败',
            'document_processing_failed': '文档处理失败',
            'query_processing_failed': '查询处理失败',
            'batch_operation_failed': '批量操作失败',
            'cache_operation_failed': '缓存操作失败',
            'database_operation_failed': '数据库操作失败',
            
            # 成功消息
            'document_uploaded_successfully': '文档上传成功',
            'document_processed_successfully': '文档处理完成',
            'query_processed_successfully': '查询处理完成',
            'batch_operation_completed': '批量操作完成',
            
            # 解决建议
            'check_input_format': '请检查输入数据的格式',
            'contact_support': '如问题持续，请联系技术支持',
            'retry_later': '请稍后重试',
            'check_permissions': '请检查您的访问权限',
            'reduce_request_frequency': '请降低请求频率'
        },
        'en': {
            # General error messages
            'validation_error': 'Input validation failed',
            'resource_not_found': 'Requested resource not found',
            'permission_denied': 'Permission denied',
            'rate_limit_exceeded': 'Rate limit exceeded, please retry later',
            'internal_server_error': 'Internal server error',
            'service_unavailable': 'Service temporarily unavailable',
            'timeout_error': 'Request timeout',
            'network_error': 'Network connection error',
            
            # Business related error messages
            'document_upload_failed': 'Document upload failed',
            'document_processing_failed': 'Document processing failed',
            'query_processing_failed': 'Query processing failed',
            'batch_operation_failed': 'Batch operation failed',
            'cache_operation_failed': 'Cache operation failed',
            'database_operation_failed': 'Database operation failed',
            
            # Success messages
            'document_uploaded_successfully': 'Document uploaded successfully',
            'document_processed_successfully': 'Document processed successfully',
            'query_processed_successfully': 'Query processed successfully',
            'batch_operation_completed': 'Batch operation completed',
            
            # Solution suggestions
            'check_input_format': 'Please check your input data format',
            'contact_support': 'Please contact technical support if the problem persists',
            'retry_later': 'Please retry later',
            'check_permissions': 'Please check your access permissions',
            'reduce_request_frequency': 'Please reduce request frequency'
        }
    }
    
    @classmethod
    def get_message(cls, key: str, language: str = 'zh') -> str:
        """获取多语言消息"""
        return cls.MESSAGES.get(language, cls.MESSAGES['zh']).get(key, key)
    
    @classmethod
    def get_error_message(cls, error_code: str, language: str = 'zh') -> str:
        """根据错误代码获取用户友好消息"""
        code_mapping = {
            'VALIDATION_ERROR': 'validation_error',
            'RESOURCE_ERROR': 'resource_not_found',
            'PERMISSION_ERROR': 'permission_denied',
            'RATE_LIMIT_ERROR': 'rate_limit_exceeded',
            'INTERNAL_ERROR': 'internal_server_error',
            'SERVICE_UNAVAILABLE': 'service_unavailable',
            'TIMEOUT_ERROR': 'timeout_error',
            'NETWORK_ERROR': 'network_error',
            'DOCUMENT_UPLOAD_ERROR': 'document_upload_failed',
            'DOCUMENT_PROCESSING_ERROR': 'document_processing_failed',
            'QUERY_ERROR': 'query_processing_failed',
            'BATCH_ERROR': 'batch_operation_failed'
        }
        
        message_key = code_mapping.get(error_code, 'internal_server_error')
        return cls.get_message(message_key, language)
    
    @classmethod
    def get_solution_suggestion(cls, error_code: str, language: str = 'zh') -> str:
        """根据错误代码获取解决建议"""
        suggestion_mapping = {
            'VALIDATION_ERROR': 'check_input_format',
            'RESOURCE_ERROR': 'check_permissions',
            'PERMISSION_ERROR': 'check_permissions',
            'RATE_LIMIT_ERROR': 'reduce_request_frequency',
            'TIMEOUT_ERROR': 'retry_later',
            'NETWORK_ERROR': 'retry_later',
            'SERVICE_UNAVAILABLE': 'retry_later'
        }
        
        suggestion_key = suggestion_mapping.get(error_code, 'contact_support')
        return cls.get_message(suggestion_key, language)


class ResponseFormatter:
    """
    响应格式化器
    
    提供统一的API响应格式，包括：
    1. 成功响应格式化
    2. 错误响应格式化
    3. 多语言支持
    4. 响应元数据
    5. 调试信息控制
    """
    
    def __init__(self, enable_debug: bool = None):
        self.enable_debug = enable_debug if enable_debug is not None else (
            os.getenv("DEBUG", "false").lower() == "true"
        )
        self.api_version = os.getenv("API_VERSION", "v1")
    
    def _extract_language(self, request: Optional[Request]) -> str:
        """从请求中提取语言偏好"""
        if not request:
            return 'zh'
        
        # 1. 检查查询参数
        lang = request.query_params.get('lang', '').lower()
        if lang in ['zh', 'en']:
            return lang
        
        # 2. 检查Accept-Language头
        accept_language = request.headers.get('Accept-Language', '')
        if 'en' in accept_language.lower():
            return 'en'
        
        # 3. 默认中文
        return 'zh'
    
    def _create_metadata(self, request_id: str, execution_time_ms: Optional[float] = None) -> ResponseMetadata:
        """创建响应元数据"""
        return ResponseMetadata(
            request_id=request_id,
            timestamp=datetime.now().isoformat(),
            execution_time_ms=execution_time_ms,
            api_version=self.api_version
        )
    
    def format_success_response(
        self,
        data: Any = None,
        message: Optional[str] = None,
        request_id: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        pagination: Optional[PaginationInfo] = None,
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """格式化成功响应"""
        language = self._extract_language(request)
        metadata = self._create_metadata(request_id or "unknown", execution_time_ms)
        
        response = {
            'success': True,
            'type': ResponseType.SUCCESS.value,
            'message': message or MessageTemplates.get_message('operation_successful', language),
            'data': data,
            'metadata': {
                'request_id': metadata.request_id,
                'timestamp': metadata.timestamp,
                'api_version': metadata.api_version,
                'execution_time_ms': metadata.execution_time_ms
            }
        }
        
        # 添加分页信息
        if pagination:
            response['pagination'] = {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'total_pages': pagination.total_pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        
        return response
    
    def format_error_response(
        self,
        error_code: str,
        message: Optional[str] = None,
        user_message: Optional[str] = None,
        details: Optional[Union[List[ErrorDetail], Dict[str, Any]]] = None,
        request_id: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        is_recoverable: bool = True,
        suggested_solution: Optional[str] = None,
        request: Optional[Request] = None,
        debug_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """格式化错误响应"""
        language = self._extract_language(request)
        metadata = self._create_metadata(request_id or "unknown", execution_time_ms)
        
        # 自动生成用户友好消息
        if not user_message:
            user_message = MessageTemplates.get_error_message(error_code, language)
        
        # 自动生成解决建议
        if not suggested_solution:
            suggested_solution = MessageTemplates.get_solution_suggestion(error_code, language)
        
        response = {
            'success': False,
            'type': ResponseType.ERROR.value,
            'error': {
                'code': error_code,
                'message': user_message,
                'severity': severity.value,
                'is_recoverable': is_recoverable,
                'suggested_solution': suggested_solution
            },
            'metadata': {
                'request_id': metadata.request_id,
                'timestamp': metadata.timestamp,
                'api_version': metadata.api_version,
                'execution_time_ms': metadata.execution_time_ms
            }
        }
        
        # 添加详细信息
        if details:
            if isinstance(details, list):
                response['error']['details'] = [
                    {
                        'field': detail.field,
                        'code': detail.code,
                        'message': detail.message,
                        'value': detail.value
                    } for detail in details
                ]
            else:
                response['error']['details'] = details
        
        # 调试信息（仅在调试模式下显示）
        if self.enable_debug and debug_info:
            response['debug'] = debug_info
            if message and message != user_message:
                response['debug']['technical_message'] = message
        
        return response
    
    def format_validation_error_response(
        self,
        validation_errors: List[Dict[str, Any]],
        request_id: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """格式化验证错误响应"""
        language = self._extract_language(request)
        
        error_details = []
        for error in validation_errors:
            error_details.append(ErrorDetail(
                field=error.get('field'),
                code=error.get('code', 'VALIDATION_ERROR'),
                message=error.get('message'),
                value=error.get('value')
            ))
        
        return self.format_error_response(
            error_code='VALIDATION_ERROR',
            user_message=MessageTemplates.get_message('validation_error', language),
            details=error_details,
            request_id=request_id,
            execution_time_ms=execution_time_ms,
            severity=ErrorSeverity.MEDIUM,
            is_recoverable=False,
            request=request
        )
    
    def format_business_error_response(
        self,
        operation_type: str,
        error_message: str,
        error_code: Optional[str] = None,
        request_id: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        is_recoverable: bool = True,
        context: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """格式化业务错误响应"""
        if not error_code:
            error_code = f"{operation_type.upper()}_ERROR"
        
        debug_info = None
        if context and self.enable_debug:
            debug_info = {
                'operation_type': operation_type,
                'context': context
            }
        
        return self.format_error_response(
            error_code=error_code,
            message=error_message,
            request_id=request_id,
            execution_time_ms=execution_time_ms,
            severity=severity,
            is_recoverable=is_recoverable,
            request=request,
            debug_info=debug_info
        )
    
    def format_warning_response(
        self,
        message: str,
        data: Any = None,
        warnings: Optional[List[str]] = None,
        request_id: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """格式化警告响应"""
        metadata = self._create_metadata(request_id or "unknown", execution_time_ms)
        
        response = {
            'success': True,
            'type': ResponseType.WARNING.value,
            'message': message,
            'data': data,
            'warnings': warnings or [],
            'metadata': {
                'request_id': metadata.request_id,
                'timestamp': metadata.timestamp,
                'api_version': metadata.api_version,
                'execution_time_ms': metadata.execution_time_ms
            }
        }
        
        return response
    
    def create_json_response(
        self,
        content: Dict[str, Any],
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None
    ) -> JSONResponse:
        """创建JSON响应"""
        response_headers = headers or {}
        
        # 添加通用响应头
        response_headers.update({
            'Content-Type': 'application/json; charset=utf-8',
            'X-API-Version': self.api_version,
            'X-Response-Time': datetime.now().isoformat()
        })
        
        # 添加请求ID到响应头
        if 'metadata' in content and 'request_id' in content['metadata']:
            response_headers['X-Request-ID'] = content['metadata']['request_id']
        
        return JSONResponse(
            content=content,
            status_code=status_code,
            headers=response_headers
        )


# 全局响应格式化器实例
response_formatter = ResponseFormatter()


# 便捷函数
def success_response(data: Any = None, message: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """创建成功响应"""
    return response_formatter.format_success_response(data=data, message=message, **kwargs)


def error_response(error_code: str, message: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """创建错误响应"""
    return response_formatter.format_error_response(error_code=error_code, message=message, **kwargs)


def validation_error_response(validation_errors: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
    """创建验证错误响应"""
    return response_formatter.format_validation_error_response(validation_errors, **kwargs)


def business_error_response(operation_type: str, error_message: str, **kwargs) -> Dict[str, Any]:
    """创建业务错误响应"""
    return response_formatter.format_business_error_response(operation_type, error_message, **kwargs)


def warning_response(message: str, data: Any = None, warnings: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
    """创建警告响应"""
    return response_formatter.format_warning_response(message, data, warnings, **kwargs)