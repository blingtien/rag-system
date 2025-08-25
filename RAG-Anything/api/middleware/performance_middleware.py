"""
性能监控中间件
自动收集API请求的性能指标和资源使用情况
"""
import time
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List
import json
import uuid

from fastapi import Request, Response
try:
    from fastapi.middleware.base import BaseHTTPMiddleware
except ImportError:
    from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import psutil

logger = logging.getLogger(__name__)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """性能监控中间件"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.request_metrics: List[Dict[str, Any]] = []
        self.max_metrics = 10000  # 最多保存10000条请求记录
        self.slow_request_threshold = 2.0  # 慢请求阈值（秒）
        self.memory_threshold_mb = 1000  # 内存使用告警阈值（MB）
    
    async def dispatch(self, request: Request, call_next):
        """处理请求并收集性能指标"""
        # 生成请求ID
        request_id = str(uuid.uuid4())[:8]
        
        # 记录请求开始时间和系统状态
        start_time = time.time()
        start_datetime = datetime.now()
        
        # 获取请求开始时的系统指标
        process = psutil.Process()
        start_memory = process.memory_info().rss / (1024 * 1024)  # MB
        start_cpu_times = process.cpu_times()
        
        # 收集请求信息
        request_info = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_host": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown")
        }
        
        # 添加请求ID到请求状态中，便于日志追踪
        request.state.request_id = request_id
        request.state.start_time = start_time
        
        response = None
        error = None
        
        try:
            # 处理请求
            response = await call_next(request)
            
        except Exception as e:
            error = e
            logger.error(f"请求处理异常 [请求ID: {request_id}]: {str(e)}")
            raise
            
        finally:
            # 记录请求结束时间和系统状态
            end_time = time.time()
            processing_time = end_time - start_time
            
            # 获取请求结束时的系统指标
            end_memory = process.memory_info().rss / (1024 * 1024)  # MB
            end_cpu_times = process.cpu_times()
            
            # 计算CPU使用情况
            cpu_time_used = (end_cpu_times.user - start_cpu_times.user) + (end_cpu_times.system - start_cpu_times.system)
            memory_delta = end_memory - start_memory
            
            # 构建性能指标
            performance_metrics = {
                **request_info,
                "timestamp": start_datetime.isoformat(),
                "processing_time": round(processing_time, 4),
                "status_code": response.status_code if response else 500,
                "response_size": len(response.body) if response and hasattr(response, 'body') else 0,
                "memory_usage": {
                    "start_mb": round(start_memory, 2),
                    "end_mb": round(end_memory, 2),
                    "delta_mb": round(memory_delta, 2)
                },
                "cpu_time_used": round(cpu_time_used, 4),
                "error": str(error) if error else None,
                "is_slow_request": processing_time > self.slow_request_threshold,
                "is_memory_intensive": abs(memory_delta) > 50,  # 内存变化超过50MB
                "performance_category": self._categorize_performance(processing_time, memory_delta)
            }
            
            # 添加响应头
            if response:
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Processing-Time"] = str(round(processing_time, 4))
                response.headers["X-Memory-Delta"] = str(round(memory_delta, 2))
            
            # 记录性能指标
            await self._record_metrics(performance_metrics)
            
            # 检查是否需要性能告警
            await self._check_performance_alerts(performance_metrics)
        
        return response
    
    def _categorize_performance(self, processing_time: float, memory_delta: float) -> str:
        """对性能进行分类"""
        if processing_time > 10.0:
            return "very_slow"
        elif processing_time > 5.0:
            return "slow"
        elif processing_time > 2.0:
            return "moderate"
        elif processing_time > 1.0:
            return "normal"
        else:
            return "fast"
    
    async def _record_metrics(self, metrics: Dict[str, Any]):
        """记录性能指标"""
        try:
            # 添加到内存记录中
            self.request_metrics.append(metrics)
            
            # 限制内存中的记录数量
            if len(self.request_metrics) > self.max_metrics:
                self.request_metrics = self.request_metrics[-self.max_metrics:]
            
            # 记录到日志中
            if metrics["is_slow_request"]:
                logger.warning(
                    f"慢请求检测 [请求ID: {metrics['request_id']}]: "
                    f"{metrics['method']} {metrics['path']} - "
                    f"耗时: {metrics['processing_time']}s, "
                    f"内存变化: {metrics['memory_usage']['delta_mb']}MB"
                )
            
            # 记录到性能文件中（可选）
            await self._write_to_performance_log(metrics)
            
        except Exception as e:
            logger.error(f"记录性能指标时出错: {e}")
    
    async def _write_to_performance_log(self, metrics: Dict[str, Any]):
        """将性能指标写入日志文件"""
        try:
            # 只记录关键性能指标到文件
            if metrics["is_slow_request"] or metrics["is_memory_intensive"]:
                performance_log = {
                    "timestamp": metrics["timestamp"],
                    "request_id": metrics["request_id"],
                    "method": metrics["method"],
                    "path": metrics["path"],
                    "processing_time": metrics["processing_time"],
                    "status_code": metrics["status_code"],
                    "memory_delta": metrics["memory_usage"]["delta_mb"],
                    "performance_category": metrics["performance_category"]
                }
                
                # 可以写入到专门的性能日志文件
                # 这里使用标准日志记录
                logger.info(f"PERFORMANCE_METRIC: {json.dumps(performance_log)}")
                
        except Exception as e:
            logger.debug(f"写入性能日志时出错: {e}")
    
    async def _check_performance_alerts(self, metrics: Dict[str, Any]):
        """检查是否需要发出性能告警"""
        try:
            alerts = []
            
            # 慢请求告警
            if metrics["processing_time"] > 10.0:
                alerts.append({
                    "type": "slow_request_critical",
                    "message": f"极慢请求: {metrics['processing_time']:.2f}s",
                    "severity": "critical"
                })
            elif metrics["processing_time"] > 5.0:
                alerts.append({
                    "type": "slow_request_warning",
                    "message": f"慢请求: {metrics['processing_time']:.2f}s",
                    "severity": "warning"
                })
            
            # 内存使用告警
            memory_delta = metrics["memory_usage"]["delta_mb"]
            if abs(memory_delta) > 200:
                alerts.append({
                    "type": "high_memory_usage",
                    "message": f"高内存使用: {memory_delta:+.1f}MB",
                    "severity": "warning"
                })
            
            # 错误告警
            if metrics["error"]:
                alerts.append({
                    "type": "request_error",
                    "message": f"请求错误: {metrics['error']}",
                    "severity": "error"
                })
            
            # 发送告警
            for alert in alerts:
                await self._send_performance_alert(metrics["request_id"], alert)
                
        except Exception as e:
            logger.error(f"检查性能告警时出错: {e}")
    
    async def _send_performance_alert(self, request_id: str, alert: Dict[str, Any]):
        """发送性能告警"""
        try:
            alert_message = (
                f"性能告警 [请求ID: {request_id}] - "
                f"类型: {alert['type']}, "
                f"消息: {alert['message']}, "
                f"严重级别: {alert['severity']}"
            )
            
            if alert["severity"] == "critical":
                logger.critical(alert_message)
            elif alert["severity"] == "error":
                logger.error(alert_message)
            else:
                logger.warning(alert_message)
            
            # 这里可以集成其他告警系统，如发送邮件、短信等
            
        except Exception as e:
            logger.error(f"发送性能告警时出错: {e}")
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """获取性能摘要"""
        try:
            # 过滤指定时间段的记录
            cutoff_time = datetime.now().timestamp() - (hours * 3600)
            recent_metrics = [
                m for m in self.request_metrics 
                if datetime.fromisoformat(m["timestamp"]).timestamp() > cutoff_time
            ]
            
            if not recent_metrics:
                return {
                    "period_hours": hours,
                    "total_requests": 0,
                    "message": "无性能数据"
                }
            
            # 计算统计指标
            total_requests = len(recent_metrics)
            processing_times = [m["processing_time"] for m in recent_metrics]
            memory_deltas = [m["memory_usage"]["delta_mb"] for m in recent_metrics]
            
            avg_processing_time = sum(processing_times) / len(processing_times)
            max_processing_time = max(processing_times)
            min_processing_time = min(processing_times)
            
            # 按路径统计
            path_stats = {}
            for metric in recent_metrics:
                path = metric["path"]
                if path not in path_stats:
                    path_stats[path] = {
                        "count": 0,
                        "total_time": 0,
                        "max_time": 0,
                        "errors": 0
                    }
                
                path_stats[path]["count"] += 1
                path_stats[path]["total_time"] += metric["processing_time"]
                path_stats[path]["max_time"] = max(path_stats[path]["max_time"], metric["processing_time"])
                if metric["error"]:
                    path_stats[path]["errors"] += 1
            
            # 计算平均时间
            for path in path_stats:
                path_stats[path]["avg_time"] = path_stats[path]["total_time"] / path_stats[path]["count"]
            
            # 性能分类统计
            performance_categories = {}
            for metric in recent_metrics:
                category = metric["performance_category"]
                performance_categories[category] = performance_categories.get(category, 0) + 1
            
            # 慢请求统计
            slow_requests = [m for m in recent_metrics if m["is_slow_request"]]
            memory_intensive_requests = [m for m in recent_metrics if m["is_memory_intensive"]]
            
            return {
                "period_hours": hours,
                "total_requests": total_requests,
                "performance_metrics": {
                    "avg_processing_time": round(avg_processing_time, 4),
                    "max_processing_time": round(max_processing_time, 4),
                    "min_processing_time": round(min_processing_time, 4),
                    "avg_memory_delta": round(sum(memory_deltas) / len(memory_deltas), 2),
                    "max_memory_delta": round(max(memory_deltas), 2),
                    "min_memory_delta": round(min(memory_deltas), 2)
                },
                "request_categories": performance_categories,
                "slow_requests": {
                    "count": len(slow_requests),
                    "percentage": round(len(slow_requests) / total_requests * 100, 2)
                },
                "memory_intensive_requests": {
                    "count": len(memory_intensive_requests),
                    "percentage": round(len(memory_intensive_requests) / total_requests * 100, 2)
                },
                "top_paths": sorted(
                    [(path, stats) for path, stats in path_stats.items()],
                    key=lambda x: x[1]["avg_time"],
                    reverse=True
                )[:10],
                "error_rate": round(len([m for m in recent_metrics if m["error"]]) / total_requests * 100, 2)
            }
            
        except Exception as e:
            logger.error(f"获取性能摘要时出错: {e}")
            return {
                "error": str(e),
                "period_hours": hours
            }
    
    def get_slow_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最慢的请求记录"""
        try:
            slow_requests = [m for m in self.request_metrics if m["is_slow_request"]]
            slow_requests.sort(key=lambda x: x["processing_time"], reverse=True)
            return slow_requests[:limit]
        except Exception as e:
            logger.error(f"获取慢请求记录时出错: {e}")
            return []
    
    def get_memory_intensive_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取内存密集型请求记录"""
        try:
            memory_requests = [m for m in self.request_metrics if m["is_memory_intensive"]]
            memory_requests.sort(key=lambda x: abs(x["memory_usage"]["delta_mb"]), reverse=True)
            return memory_requests[:limit]
        except Exception as e:
            logger.error(f"获取内存密集型请求记录时出错: {e}")
            return []
    
    def clear_old_metrics(self, hours: int = 72):
        """清理旧的性能指标数据"""
        try:
            cutoff_time = datetime.now().timestamp() - (hours * 3600)
            original_count = len(self.request_metrics)
            
            self.request_metrics = [
                m for m in self.request_metrics 
                if datetime.fromisoformat(m["timestamp"]).timestamp() > cutoff_time
            ]
            
            cleared_count = original_count - len(self.request_metrics)
            logger.info(f"清理了 {cleared_count} 条旧的性能指标记录")
            
            return cleared_count
            
        except Exception as e:
            logger.error(f"清理旧性能指标时出错: {e}")
            return 0


# 全局中间件实例（用于访问性能数据）
_performance_middleware_instance = None

def get_performance_middleware() -> PerformanceMiddleware:
    """获取性能监控中间件实例"""
    global _performance_middleware_instance
    return _performance_middleware_instance

def set_performance_middleware(instance: PerformanceMiddleware):
    """设置性能监控中间件实例"""
    global _performance_middleware_instance
    _performance_middleware_instance = instance