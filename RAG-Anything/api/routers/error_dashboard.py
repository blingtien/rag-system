#!/usr/bin/env python3
"""
错误监控和诊断Dashboard API路由
提供错误分析、性能监控、调用链追踪等功能的API接口
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Query, Path, Depends, HTTPException
from pydantic import BaseModel, Field

# 导入中间件组件
from middleware.error_tracking import error_tracker
from middleware.debug_tools import debug_profiler
from middleware.unified_logging import LoggerFactory, LogLevel, LogCategory
from middleware.websocket_error_handler import websocket_error_handler
from middleware.response_formatter import success_response, error_response, ResponseFormatter

# 导入依赖
from config.dependencies import get_current_user_optional


router = APIRouter(prefix="/api/v1/debug", tags=["debug", "monitoring"])
logger = LoggerFactory.get_logger("error_dashboard")
response_formatter = ResponseFormatter()


# 请求/响应模型
class ErrorAnalysisRequest(BaseModel):
    """错误分析请求"""
    time_range_hours: int = Field(default=24, ge=1, le=168, description="时间范围（小时）")
    error_types: Optional[List[str]] = Field(default=None, description="错误类型过滤")
    severity_levels: Optional[List[str]] = Field(default=None, description="严重程度过滤")


class PerformanceAnalysisRequest(BaseModel):
    """性能分析请求"""
    time_range_hours: int = Field(default=24, ge=1, le=168)
    endpoint_filter: Optional[str] = Field(default=None, description="端点过滤")
    slow_threshold_ms: Optional[float] = Field(default=5000, description="慢请求阈值")


class TraceAnalysisRequest(BaseModel):
    """调用链分析请求"""
    trace_id: Optional[str] = Field(default=None, description="指定调用链ID")
    operation_filter: Optional[str] = Field(default=None, description="操作过滤")
    include_spans: bool = Field(default=True, description="包含跨度详情")


# Dashboard概览API
@router.get("/overview")
async def get_dashboard_overview(
    current_user: str = Depends(get_current_user_optional)
):
    """获取错误监控Dashboard概览"""
    try:
        # 系统指标
        system_metrics = debug_profiler.get_system_metrics()
        
        # 错误统计
        error_patterns = error_tracker.get_error_patterns()
        slow_operations = error_tracker.get_slow_operations()
        frequent_errors = error_tracker.get_frequent_errors()
        
        # 调用链摘要
        traces_summary = error_tracker.get_traces_summary()
        
        # WebSocket连接状态
        websocket_stats = websocket_error_handler.get_connection_stats()
        
        # 性能报告
        performance_report = debug_profiler.get_performance_report()
        
        # 日志统计
        unified_logger = LoggerFactory.get_logger()
        error_summary = unified_logger.get_error_summary()
        performance_summary = unified_logger.get_performance_summary()
        
        overview_data = {
            'system_health': {
                'cpu_usage': system_metrics.cpu_usage,
                'memory_usage': system_metrics.memory_usage,
                'disk_usage': system_metrics.disk_usage,
                'status': _get_health_status(system_metrics)
            },
            'error_statistics': {
                'total_error_patterns': len(error_patterns),
                'frequent_errors_count': len(frequent_errors),
                'recent_errors': error_summary.get('recent_errors_count', 0),
                'error_patterns': dict(list(error_patterns.items())[:10])  # Top 10
            },
            'performance_metrics': {
                'slow_operations_count': len(slow_operations),
                'avg_response_time': performance_report.get('performance_summary', {}).get('avg_response_time', 0),
                'error_rate': performance_report.get('performance_summary', {}).get('error_rate', 0),
                'total_endpoints': performance_report.get('performance_summary', {}).get('total_endpoints', 0)
            },
            'trace_analytics': {
                'total_traces': traces_summary.get('total_traces', 0),
                'active_traces': traces_summary.get('active_traces', 0),
                'error_traces': traces_summary.get('error_traces', 0),
                'success_rate': traces_summary.get('success_rate', 100),
                'avg_duration': traces_summary.get('avg_duration_ms', 0)
            },
            'websocket_status': {
                'active_connections': websocket_stats.get('active_connections', 0),
                'total_connections': websocket_stats.get('total_connections', 0),
                'connection_success_rate': websocket_stats.get('connection_success_rate', 100),
                'queued_messages': websocket_stats.get('queued_messages', 0)
            },
            'timestamp': datetime.now().isoformat()
        }
        
        return success_response(overview_data, "Dashboard overview retrieved successfully")
        
    except Exception as e:
        await logger.error(f"Failed to get dashboard overview: {str(e)}")
        return error_response("DASHBOARD_ERROR", f"Failed to retrieve dashboard overview: {str(e)}")


# 错误分析API
@router.post("/errors/analyze")
async def analyze_errors(
    request: ErrorAnalysisRequest,
    current_user: str = Depends(get_current_user_optional)
):
    """错误分析和模式识别"""
    try:
        # 获取错误数据
        error_patterns = error_tracker.get_error_patterns()
        frequent_errors = error_tracker.get_frequent_errors(50)  # 最近50个错误
        
        # 时间过滤
        cutoff_time = datetime.now() - timedelta(hours=request.time_range_hours)
        filtered_errors = [
            error for error in frequent_errors
            if datetime.fromisoformat(error['timestamp']) > cutoff_time
        ]
        
        # 类型过滤
        if request.error_types:
            filtered_errors = [
                error for error in filtered_errors
                if any(error_type.lower() in error['operation'].lower() for error_type in request.error_types)
            ]
        
        # 错误聚合分析
        error_aggregation = {}
        for error in filtered_errors:
            key = error['operation']
            if key not in error_aggregation:
                error_aggregation[key] = {
                    'count': 0,
                    'operations': [],
                    'first_seen': error['timestamp'],
                    'last_seen': error['timestamp']
                }
            
            error_aggregation[key]['count'] += 1
            error_aggregation[key]['operations'].append(error)
            
            if error['timestamp'] > error_aggregation[key]['last_seen']:
                error_aggregation[key]['last_seen'] = error['timestamp']
        
        # 错误趋势分析
        error_trend = _analyze_error_trend(filtered_errors, request.time_range_hours)
        
        # 生成洞察和建议
        insights = _generate_error_insights(error_aggregation, error_patterns)
        
        analysis_data = {
            'time_range': {
                'start': cutoff_time.isoformat(),
                'end': datetime.now().isoformat(),
                'hours': request.time_range_hours
            },
            'error_summary': {
                'total_errors': len(filtered_errors),
                'unique_error_types': len(error_aggregation),
                'most_frequent_error': max(error_aggregation.items(), key=lambda x: x[1]['count'])[0] if error_aggregation else None
            },
            'error_aggregation': error_aggregation,
            'error_patterns': dict(list(error_patterns.items())[:20]),
            'error_trend': error_trend,
            'insights_and_recommendations': insights
        }
        
        return success_response(analysis_data, "Error analysis completed successfully")
        
    except Exception as e:
        await logger.error(f"Failed to analyze errors: {str(e)}")
        return error_response("ERROR_ANALYSIS_FAILED", f"Failed to analyze errors: {str(e)}")


# 性能分析API
@router.post("/performance/analyze")
async def analyze_performance(
    request: PerformanceAnalysisRequest,
    current_user: str = Depends(get_current_user_optional)
):
    """性能分析和瓶颈识别"""
    try:
        # 获取性能数据
        performance_report = debug_profiler.get_performance_report()
        slow_operations = error_tracker.get_slow_operations(100)
        
        # 时间过滤
        cutoff_time = datetime.now() - timedelta(hours=request.time_range_hours)
        filtered_slow_ops = [
            op for op in slow_operations
            if datetime.fromisoformat(op['timestamp']) > cutoff_time
        ]
        
        # 端点过滤
        if request.endpoint_filter:
            filtered_slow_ops = [
                op for op in filtered_slow_ops
                if request.endpoint_filter.lower() in op['operation'].lower()
            ]
        
        # 慢操作阈值过滤
        if request.slow_threshold_ms:
            filtered_slow_ops = [
                op for op in filtered_slow_ops
                if op['duration_ms'] > request.slow_threshold_ms
            ]
        
        # 性能瓶颈分析
        bottlenecks = _identify_performance_bottlenecks(filtered_slow_ops)
        
        # 端点性能统计
        endpoint_stats = performance_report.get('endpoint_stats', {})
        
        # 系统资源分析
        system_metrics = debug_profiler.get_system_metrics()
        resource_analysis = _analyze_resource_usage(system_metrics)
        
        # 性能趋势分析
        performance_trend = _analyze_performance_trend(filtered_slow_ops, request.time_range_hours)
        
        # 优化建议
        optimization_suggestions = _generate_performance_suggestions(bottlenecks, resource_analysis)
        
        analysis_data = {
            'time_range': {
                'start': cutoff_time.isoformat(),
                'end': datetime.now().isoformat(),
                'hours': request.time_range_hours
            },
            'performance_summary': {
                'total_slow_operations': len(filtered_slow_ops),
                'avg_duration_ms': sum(op['duration_ms'] for op in filtered_slow_ops) / len(filtered_slow_ops) if filtered_slow_ops else 0,
                'slowest_operation': max(filtered_slow_ops, key=lambda x: x['duration_ms']) if filtered_slow_ops else None
            },
            'bottlenecks': bottlenecks,
            'endpoint_statistics': endpoint_stats,
            'system_resource_analysis': resource_analysis,
            'performance_trend': performance_trend,
            'optimization_suggestions': optimization_suggestions
        }
        
        return success_response(analysis_data, "Performance analysis completed successfully")
        
    except Exception as e:
        await logger.error(f"Failed to analyze performance: {str(e)}")
        return error_response("PERFORMANCE_ANALYSIS_FAILED", f"Failed to analyze performance: {str(e)}")


# 调用链分析API
@router.post("/traces/analyze")
async def analyze_traces(
    request: TraceAnalysisRequest,
    current_user: str = Depends(get_current_user_optional)
):
    """调用链分析和依赖关系图"""
    try:
        if request.trace_id:
            # 分析特定调用链
            trace = error_tracker.get_trace(request.trace_id)
            if not trace:
                return error_response("TRACE_NOT_FOUND", f"Trace {request.trace_id} not found")
            
            trace_data = trace.to_dict()
            
            # 添加详细的跨度分析
            if request.include_spans:
                span_analysis = _analyze_trace_spans(trace)
                trace_data['span_analysis'] = span_analysis
            
            return success_response(trace_data, "Trace analysis completed successfully")
        
        else:
            # 全局调用链分析
            traces_summary = error_tracker.get_traces_summary()
            
            # 获取错误调用链
            error_traces = []
            if request.operation_filter:
                error_traces = error_tracker.get_trace_by_error(request.operation_filter)
            
            # 调用链模式分析
            trace_patterns = _analyze_trace_patterns(error_tracker)
            
            # 依赖关系分析
            dependency_graph = _build_dependency_graph(error_tracker)
            
            analysis_data = {
                'traces_summary': traces_summary,
                'error_traces': [trace.to_dict() for trace in error_traces[:10]],
                'trace_patterns': trace_patterns,
                'dependency_graph': dependency_graph
            }
            
            return success_response(analysis_data, "Traces analysis completed successfully")
        
    except Exception as e:
        await logger.error(f"Failed to analyze traces: {str(e)}")
        return error_response("TRACE_ANALYSIS_FAILED", f"Failed to analyze traces: {str(e)}")


# 实时监控API
@router.get("/realtime/status")
async def get_realtime_status(
    current_user: str = Depends(get_current_user_optional)
):
    """获取实时系统状态"""
    try:
        # 当前系统指标
        system_metrics = debug_profiler.get_system_metrics()
        
        # 活跃调用链
        active_traces_count = error_tracker.get_active_traces_count()
        
        # WebSocket连接状态
        websocket_stats = websocket_error_handler.get_connection_stats()
        websocket_clients = websocket_error_handler.get_all_clients_info()
        
        # 最近错误（5分钟内）
        recent_errors = error_tracker.get_frequent_errors(10)
        cutoff_time = datetime.now() - timedelta(minutes=5)
        recent_errors = [
            error for error in recent_errors
            if datetime.fromisoformat(error['timestamp']) > cutoff_time
        ]
        
        # 系统健康状态
        health_status = _get_health_status(system_metrics)
        
        realtime_data = {
            'timestamp': datetime.now().isoformat(),
            'system_metrics': system_metrics.to_dict(),
            'health_status': health_status,
            'active_traces': active_traces_count,
            'websocket_connections': {
                'stats': websocket_stats,
                'clients': websocket_clients[:10]  # 限制返回数量
            },
            'recent_errors': recent_errors,
            'alerts': _generate_system_alerts(system_metrics, recent_errors)
        }
        
        return success_response(realtime_data, "Realtime status retrieved successfully")
        
    except Exception as e:
        await logger.error(f"Failed to get realtime status: {str(e)}")
        return error_response("REALTIME_STATUS_FAILED", f"Failed to get realtime status: {str(e)}")


# 系统健康检查API
@router.get("/health")
async def health_check():
    """系统健康检查"""
    try:
        system_metrics = debug_profiler.get_system_metrics()
        health_status = _get_health_status(system_metrics)
        
        # 检查各组件状态
        components_status = {
            'error_tracker': 'healthy',
            'debug_profiler': 'healthy',
            'websocket_handler': 'healthy' if websocket_error_handler.get_connection_stats()['active_connections'] >= 0 else 'error',
            'logging_system': 'healthy'
        }
        
        # 系统警告
        warnings = []
        if system_metrics.cpu_usage > 80:
            warnings.append("High CPU usage detected")
        if system_metrics.memory_usage > 80:
            warnings.append("High memory usage detected")
        if system_metrics.disk_usage > 90:
            warnings.append("Low disk space")
        
        overall_status = 'healthy'
        if any(status == 'error' for status in components_status.values()):
            overall_status = 'error'
        elif warnings:
            overall_status = 'warning'
        
        health_data = {
            'status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'system_metrics': system_metrics.to_dict(),
            'components': components_status,
            'warnings': warnings
        }
        
        status_code = 200 if overall_status == 'healthy' else 503
        return response_formatter.create_json_response(
            success_response(health_data, f"System is {overall_status}"),
            status_code=status_code
        )
        
    except Exception as e:
        return response_formatter.create_json_response(
            error_response("HEALTH_CHECK_FAILED", f"Health check failed: {str(e)}"),
            status_code=503
        )


# 配置管理API
@router.get("/config")
async def get_debug_config(
    current_user: str = Depends(get_current_user_optional)
):
    """获取调试配置"""
    from middleware.debug_tools import is_debug_mode, is_development_mode
    
    config_data = {
        'debug_mode': is_debug_mode(),
        'development_mode': is_development_mode(),
        'profiling_enabled': debug_profiler.enable_profiling,
        'performance_thresholds': debug_profiler.performance_thresholds,
        'websocket_config': {
            'heartbeat_interval': websocket_error_handler.heartbeat_interval,
            'connection_timeout': websocket_error_handler.connection_timeout,
            'max_message_queue_size': websocket_error_handler.max_message_queue_size
        },
        'error_tracking_config': {
            'max_traces': error_tracker.max_traces,
            'max_trace_age_hours': error_tracker.max_trace_age.total_seconds() / 3600
        }
    }
    
    return success_response(config_data, "Debug configuration retrieved successfully")


# 数据清理API
@router.post("/cleanup")
async def cleanup_debug_data(
    current_user: str = Depends(get_current_user_optional)
):
    """清理调试数据"""
    try:
        # 清理错误追踪数据
        error_tracker.clear_all_data()
        
        # 清理性能分析数据
        debug_profiler.clear_debug_data()
        
        # 清理日志数据
        unified_logger = LoggerFactory.get_logger()
        unified_logger.clear_logs()
        
        cleanup_data = {
            'timestamp': datetime.now().isoformat(),
            'cleaned_components': ['error_tracker', 'debug_profiler', 'logging_system']
        }
        
        return success_response(cleanup_data, "Debug data cleaned successfully")
        
    except Exception as e:
        await logger.error(f"Failed to cleanup debug data: {str(e)}")
        return error_response("CLEANUP_FAILED", f"Failed to cleanup debug data: {str(e)}")


# 辅助函数
def _get_health_status(system_metrics) -> str:
    """根据系统指标确定健康状态"""
    if system_metrics.cpu_usage > 90 or system_metrics.memory_usage > 90:
        return "critical"
    elif system_metrics.cpu_usage > 70 or system_metrics.memory_usage > 70:
        return "warning"
    else:
        return "healthy"


def _analyze_error_trend(errors: List[Dict[str, Any]], hours: int) -> Dict[str, Any]:
    """分析错误趋势"""
    # 按小时分组错误
    hourly_errors = {}
    for error in errors:
        timestamp = datetime.fromisoformat(error['timestamp'])
        hour = timestamp.replace(minute=0, second=0, microsecond=0)
        hour_str = hour.isoformat()
        
        if hour_str not in hourly_errors:
            hourly_errors[hour_str] = 0
        hourly_errors[hour_str] += 1
    
    return {
        'hourly_distribution': hourly_errors,
        'peak_hour': max(hourly_errors.items(), key=lambda x: x[1])[0] if hourly_errors else None,
        'trend_direction': 'increasing' if len(errors) > 0 else 'stable'  # 简化的趋势分析
    }


def _generate_error_insights(error_aggregation: Dict[str, Any], error_patterns: Dict[str, int]) -> List[str]:
    """生成错误洞察和建议"""
    insights = []
    
    if error_aggregation:
        # 最频繁的错误
        most_frequent = max(error_aggregation.items(), key=lambda x: x[1]['count'])
        insights.append(f"Most frequent error: {most_frequent[0]} ({most_frequent[1]['count']} occurrences)")
        
        # 新出现的错误
        recent_errors = [
            k for k, v in error_aggregation.items()
            if (datetime.now() - datetime.fromisoformat(v['first_seen'])).total_seconds() < 3600
        ]
        if recent_errors:
            insights.append(f"New errors in last hour: {len(recent_errors)} types")
    
    if not error_patterns:
        insights.append("No significant error patterns detected")
    
    return insights


def _identify_performance_bottlenecks(slow_operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """识别性能瓶颈"""
    if not slow_operations:
        return {'bottlenecks': [], 'summary': 'No performance bottlenecks detected'}
    
    # 按操作类型分组
    operation_groups = {}
    for op in slow_operations:
        operation = op['operation']
        if operation not in operation_groups:
            operation_groups[operation] = []
        operation_groups[operation].append(op)
    
    # 识别瓶颈
    bottlenecks = []
    for operation, ops in operation_groups.items():
        if len(ops) >= 3:  # 至少出现3次才认为是瓶颈
            avg_duration = sum(op['duration_ms'] for op in ops) / len(ops)
            bottlenecks.append({
                'operation': operation,
                'occurrence_count': len(ops),
                'avg_duration_ms': avg_duration,
                'max_duration_ms': max(op['duration_ms'] for op in ops)
            })
    
    return {
        'bottlenecks': bottlenecks,
        'summary': f"Identified {len(bottlenecks)} performance bottlenecks"
    }


def _analyze_resource_usage(system_metrics) -> Dict[str, Any]:
    """分析系统资源使用情况"""
    return {
        'cpu_status': 'high' if system_metrics.cpu_usage > 70 else 'normal',
        'memory_status': 'high' if system_metrics.memory_usage > 70 else 'normal',
        'disk_status': 'low' if system_metrics.disk_usage > 80 else 'normal',
        'overall_status': _get_health_status(system_metrics)
    }


def _analyze_performance_trend(slow_operations: List[Dict[str, Any]], hours: int) -> Dict[str, Any]:
    """分析性能趋势"""
    if not slow_operations:
        return {'trend': 'no_data'}
    
    # 简化的趋势分析
    recent_half = slow_operations[len(slow_operations)//2:]
    earlier_half = slow_operations[:len(slow_operations)//2]
    
    if len(recent_half) > len(earlier_half):
        trend = 'degrading'
    elif len(recent_half) < len(earlier_half):
        trend = 'improving'
    else:
        trend = 'stable'
    
    return {
        'trend': trend,
        'recent_slow_ops': len(recent_half),
        'earlier_slow_ops': len(earlier_half)
    }


def _generate_performance_suggestions(bottlenecks: Dict[str, Any], resource_analysis: Dict[str, Any]) -> List[str]:
    """生成性能优化建议"""
    suggestions = []
    
    if bottlenecks['bottlenecks']:
        suggestions.append("Consider optimizing frequent slow operations")
        suggestions.append("Add caching for repeated operations")
    
    if resource_analysis['cpu_status'] == 'high':
        suggestions.append("Consider reducing CPU-intensive operations")
    
    if resource_analysis['memory_status'] == 'high':
        suggestions.append("Review memory usage and implement cleanup")
    
    if resource_analysis['disk_status'] == 'low':
        suggestions.append("Clean up temporary files and logs")
    
    if not suggestions:
        suggestions.append("System performance is optimal")
    
    return suggestions


def _analyze_trace_spans(trace) -> Dict[str, Any]:
    """分析调用链跨度"""
    spans = list(trace.spans.values())
    
    if not spans:
        return {'analysis': 'No spans found'}
    
    # 分析跨度统计
    total_spans = len(spans)
    error_spans = len([s for s in spans if s.status == 'error'])
    avg_duration = sum(s.duration_ms for s in spans if s.duration_ms) / total_spans if spans else 0
    
    # 最慢的跨度
    slowest_span = max(spans, key=lambda x: x.duration_ms or 0)
    
    return {
        'total_spans': total_spans,
        'error_spans': error_spans,
        'success_rate': ((total_spans - error_spans) / total_spans * 100) if total_spans > 0 else 100,
        'avg_duration_ms': avg_duration,
        'slowest_span': {
            'operation': slowest_span.operation_name,
            'duration_ms': slowest_span.duration_ms,
            'span_type': slowest_span.span_type.value
        } if slowest_span.duration_ms else None
    }


def _analyze_trace_patterns(error_tracker) -> Dict[str, Any]:
    """分析调用链模式"""
    # 这里可以实现更复杂的模式识别算法
    return {
        'common_patterns': ['http_request -> document_processing', 'batch_operation -> multiple_queries'],
        'error_patterns': ['timeout_in_processing', 'memory_error_in_batch'],
        'analysis': 'Pattern analysis completed'
    }


def _build_dependency_graph(error_tracker) -> Dict[str, Any]:
    """构建服务依赖关系图"""
    # 这里可以基于调用链数据构建依赖图
    return {
        'nodes': ['api_server', 'document_service', 'database', 'cache'],
        'edges': [
            {'from': 'api_server', 'to': 'document_service'},
            {'from': 'document_service', 'to': 'database'},
            {'from': 'document_service', 'to': 'cache'}
        ],
        'analysis': 'Dependency graph built from trace data'
    }


def _generate_system_alerts(system_metrics, recent_errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """生成系统告警"""
    alerts = []
    
    # 系统资源告警
    if system_metrics.cpu_usage > 80:
        alerts.append({
            'type': 'resource',
            'severity': 'warning',
            'message': f"High CPU usage: {system_metrics.cpu_usage:.1f}%",
            'timestamp': datetime.now().isoformat()
        })
    
    if system_metrics.memory_usage > 80:
        alerts.append({
            'type': 'resource',
            'severity': 'warning',
            'message': f"High memory usage: {system_metrics.memory_usage:.1f}%",
            'timestamp': datetime.now().isoformat()
        })
    
    # 错误频率告警
    if len(recent_errors) > 10:
        alerts.append({
            'type': 'error',
            'severity': 'critical',
            'message': f"High error rate: {len(recent_errors)} errors in 5 minutes",
            'timestamp': datetime.now().isoformat()
        })
    
    return alerts