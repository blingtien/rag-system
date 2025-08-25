"""
MonitoringService - 系统监控服务
实现系统监控和健康检查，提供性能指标和告警功能
"""
import os
import psutil
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from pydantic import BaseModel

from core.state_manager import StateManager
from core.rag_manager import RAGManager
from services.exceptions import ServiceException


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"


class ComponentHealth(BaseModel):
    """组件健康状态"""
    name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    last_check: str
    response_time_ms: Optional[float] = None


class SystemMetrics(BaseModel):
    """系统指标"""
    cpu_usage: float
    memory_usage: float
    memory_total: int
    memory_used: int
    disk_usage: float
    disk_total: int
    disk_used: int
    process_count: int
    uptime_seconds: float
    load_average: Optional[List[float]] = None


class ServiceMetrics(BaseModel):
    """服务指标"""
    total_documents: int
    processing_documents: int
    completed_documents: int
    failed_documents: int
    active_batch_operations: int
    total_queries: int
    cache_hit_rate: float
    average_response_time: float


class PerformanceMetrics(BaseModel):
    """性能指标"""
    system: SystemMetrics
    service: ServiceMetrics
    timestamp: str


class HealthCheck(BaseModel):
    """健康检查结果"""
    overall_status: HealthStatus
    components: List[ComponentHealth]
    metrics: PerformanceMetrics
    alerts: List[Dict[str, Any]]
    timestamp: str


class AlertRule(BaseModel):
    """告警规则"""
    name: str
    condition: str  # Python表达式
    severity: str  # info, warning, critical
    message: str
    enabled: bool = True


class MonitoringService:
    """
    系统监控服务
    
    负责系统健康检查、性能监控和告警管理
    提供全面的系统状态可观测性
    """
    
    def __init__(
        self,
        state_manager: StateManager,
        rag_manager: RAGManager
    ):
        self.state_manager = state_manager
        self.rag_manager = rag_manager
        
        # 系统启动时间
        self.start_time = datetime.now()
        
        # 默认告警规则
        self.alert_rules = [
            AlertRule(
                name="high_cpu_usage",
                condition="metrics.system.cpu_usage > 80",
                severity="warning",
                message="CPU使用率过高: {cpu_usage}%"
            ),
            AlertRule(
                name="high_memory_usage",
                condition="metrics.system.memory_usage > 85",
                severity="warning",
                message="内存使用率过高: {memory_usage}%"
            ),
            AlertRule(
                name="low_disk_space",
                condition="metrics.system.disk_usage > 90",
                severity="critical",
                message="磁盘空间不足: {disk_usage}%"
            ),
            AlertRule(
                name="rag_system_down",
                condition="not rag_healthy",
                severity="critical",
                message="RAG系统不可用"
            ),
            AlertRule(
                name="high_processing_failure_rate",
                condition="failed_rate > 50 and total_documents > 10",
                severity="warning",
                message="文档处理失败率过高: {failed_rate}%"
            )
        ]
        
        # 历史指标存储（简单的内存存储）
        self.metrics_history: List[PerformanceMetrics] = []
        self.max_history_size = 1000
    
    async def health_check(self) -> HealthCheck:
        """
        执行完整的健康检查
        
        Returns:
            HealthCheck: 健康检查结果
        """
        timestamp = datetime.now().isoformat()
        
        # 检查各个组件
        components = []
        
        # 检查RAG系统
        rag_component = await self._check_rag_system()
        components.append(rag_component)
        
        # 检查状态管理器
        state_component = await self._check_state_manager()
        components.append(state_component)
        
        # 检查文件系统
        filesystem_component = await self._check_filesystem()
        components.append(filesystem_component)
        
        # 检查数据库连接（如果适用）
        database_component = await self._check_database()
        components.append(database_component)
        
        # 获取系统指标
        metrics = await self.get_performance_metrics()
        
        # 存储历史指标
        self._store_metrics_history(metrics)
        
        # 计算总体健康状态
        overall_status = self._calculate_overall_status(components)
        
        # 生成告警
        alerts = await self._generate_alerts(metrics, components)
        
        return HealthCheck(
            overall_status=overall_status,
            components=components,
            metrics=metrics,
            alerts=alerts,
            timestamp=timestamp
        )
    
    async def get_performance_metrics(self) -> PerformanceMetrics:
        """获取性能指标"""
        # 获取系统指标
        system_metrics = await self._get_system_metrics()
        
        # 获取服务指标
        service_metrics = await self._get_service_metrics()
        
        return PerformanceMetrics(
            system=system_metrics,
            service=service_metrics,
            timestamp=datetime.now().isoformat()
        )
    
    async def get_metrics_history(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[PerformanceMetrics]:
        """
        获取历史指标
        
        Args:
            hours: 获取最近几小时的数据
            limit: 最大返回数量
            
        Returns:
            List[PerformanceMetrics]: 历史指标列表
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # 过滤时间范围内的指标
        filtered_metrics = []
        for metric in self.metrics_history:
            metric_time = datetime.fromisoformat(metric.timestamp)
            if metric_time >= cutoff_time:
                filtered_metrics.append(metric)
        
        # 按时间倒序排序并限制数量
        filtered_metrics.sort(key=lambda m: m.timestamp, reverse=True)
        return filtered_metrics[:limit]
    
    async def get_system_status_summary(self) -> Dict[str, Any]:
        """获取系统状态摘要"""
        health_check = await self.health_check()
        
        # 统计组件状态
        component_status_counts = {}
        for component in health_check.components:
            status = component.status.value
            component_status_counts[status] = component_status_counts.get(status, 0) + 1
        
        # 获取关键指标
        metrics = health_check.metrics
        
        return {
            "overall_status": health_check.overall_status.value,
            "total_components": len(health_check.components),
            "healthy_components": component_status_counts.get("healthy", 0),
            "warning_components": component_status_counts.get("warning", 0),
            "critical_components": component_status_counts.get("critical", 0),
            "down_components": component_status_counts.get("down", 0),
            "active_alerts": len(health_check.alerts),
            "critical_alerts": len([a for a in health_check.alerts if a["severity"] == "critical"]),
            "system_metrics": {
                "cpu_usage": metrics.system.cpu_usage,
                "memory_usage": metrics.system.memory_usage,
                "disk_usage": metrics.system.disk_usage
            },
            "service_metrics": {
                "total_documents": metrics.service.total_documents,
                "processing_documents": metrics.service.processing_documents,
                "cache_hit_rate": metrics.service.cache_hit_rate
            },
            "uptime_hours": (datetime.now() - self.start_time).total_seconds() / 3600,
            "timestamp": health_check.timestamp
        }
    
    async def get_resource_usage_trends(self, hours: int = 24) -> Dict[str, Any]:
        """获取资源使用趋势"""
        history = await self.get_metrics_history(hours)
        
        if not history:
            return {
                "cpu_trend": [],
                "memory_trend": [],
                "disk_trend": [],
                "service_trend": []
            }
        
        # 提取趋势数据
        cpu_trend = [(h.timestamp, h.system.cpu_usage) for h in history]
        memory_trend = [(h.timestamp, h.system.memory_usage) for h in history]
        disk_trend = [(h.timestamp, h.system.disk_usage) for h in history]
        service_trend = [(h.timestamp, h.service.total_documents) for h in history]
        
        return {
            "cpu_trend": cpu_trend,
            "memory_trend": memory_trend,
            "disk_trend": disk_trend,
            "service_trend": service_trend,
            "data_points": len(history),
            "time_range_hours": hours
        }
    
    def add_alert_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.alert_rules.append(rule)
    
    def remove_alert_rule(self, rule_name: str) -> bool:
        """移除告警规则"""
        for i, rule in enumerate(self.alert_rules):
            if rule.name == rule_name:
                del self.alert_rules[i]
                return True
        return False
    
    def get_alert_rules(self) -> List[AlertRule]:
        """获取所有告警规则"""
        return self.alert_rules.copy()
    
    # === 私有方法 ===
    
    async def _check_rag_system(self) -> ComponentHealth:
        """检查RAG系统健康状态"""
        start_time = datetime.now()
        
        try:
            health_info = await self.rag_manager.health_check()
            
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            if health_info.get("rag_ready", False):
                return ComponentHealth(
                    name="RAG System",
                    status=HealthStatus.HEALTHY,
                    message="RAG系统运行正常",
                    details=health_info,
                    last_check=datetime.now().isoformat(),
                    response_time_ms=response_time
                )
            else:
                return ComponentHealth(
                    name="RAG System",
                    status=HealthStatus.CRITICAL,
                    message="RAG系统不可用",
                    details=health_info,
                    last_check=datetime.now().isoformat(),
                    response_time_ms=response_time
                )
                
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return ComponentHealth(
                name="RAG System",
                status=HealthStatus.DOWN,
                message=f"RAG系统检查失败: {str(e)}",
                details={"error": str(e)},
                last_check=datetime.now().isoformat(),
                response_time_ms=response_time
            )
    
    async def _check_state_manager(self) -> ComponentHealth:
        """检查状态管理器健康状态"""
        start_time = datetime.now()
        
        try:
            # 测试状态管理器的基本操作
            stats = await self.state_manager.get_statistics()
            
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return ComponentHealth(
                name="State Manager",
                status=HealthStatus.HEALTHY,
                message="状态管理器运行正常",
                details=stats,
                last_check=datetime.now().isoformat(),
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return ComponentHealth(
                name="State Manager",
                status=HealthStatus.DOWN,
                message=f"状态管理器检查失败: {str(e)}",
                details={"error": str(e)},
                last_check=datetime.now().isoformat(),
                response_time_ms=response_time
            )
    
    async def _check_filesystem(self) -> ComponentHealth:
        """检查文件系统健康状态"""
        try:
            # 检查工作目录
            from config.settings import settings
            
            working_dir = settings.working_dir
            output_dir = settings.output_dir
            
            issues = []
            
            # 检查目录存在性和权限
            for dir_path, dir_name in [(working_dir, "工作目录"), (output_dir, "输出目录")]:
                if not os.path.exists(dir_path):
                    issues.append(f"{dir_name}不存在: {dir_path}")
                elif not os.access(dir_path, os.W_OK):
                    issues.append(f"{dir_name}无写入权限: {dir_path}")
            
            # 检查磁盘空间
            disk_usage = psutil.disk_usage('/')
            disk_usage_percent = (disk_usage.used / disk_usage.total) * 100
            
            if disk_usage_percent > 95:
                issues.append(f"磁盘空间严重不足: {disk_usage_percent:.1f}%")
            elif disk_usage_percent > 90:
                issues.append(f"磁盘空间不足: {disk_usage_percent:.1f}%")
            
            status = HealthStatus.HEALTHY
            message = "文件系统正常"
            
            if issues:
                status = HealthStatus.WARNING if disk_usage_percent <= 95 else HealthStatus.CRITICAL
                message = f"文件系统存在问题: {'; '.join(issues)}"
            
            return ComponentHealth(
                name="File System",
                status=status,
                message=message,
                details={
                    "working_dir": working_dir,
                    "output_dir": output_dir,
                    "disk_usage_percent": disk_usage_percent,
                    "issues": issues
                },
                last_check=datetime.now().isoformat()
            )
            
        except Exception as e:
            return ComponentHealth(
                name="File System",
                status=HealthStatus.DOWN,
                message=f"文件系统检查失败: {str(e)}",
                details={"error": str(e)},
                last_check=datetime.now().isoformat()
            )
    
    async def _check_database(self) -> ComponentHealth:
        """检查数据库连接健康状态"""
        # 目前系统使用内存状态管理，这里可以扩展为检查持久化数据库
        return ComponentHealth(
            name="Database",
            status=HealthStatus.HEALTHY,
            message="使用内存数据库，状态正常",
            details={"type": "in-memory"},
            last_check=datetime.now().isoformat()
        )
    
    async def _get_system_metrics(self) -> SystemMetrics:
        """获取系统指标"""
        # CPU使用率
        cpu_usage = psutil.cpu_percent(interval=1)
        
        # 内存使用
        memory = psutil.virtual_memory()
        
        # 磁盘使用
        disk = psutil.disk_usage('/')
        
        # 进程数
        process_count = len(psutil.pids())
        
        # 系统运行时间
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        # 负载平均（Linux/Unix系统）
        load_average = None
        try:
            load_average = list(os.getloadavg())
        except (OSError, AttributeError):
            pass  # Windows系统不支持getloadavg
        
        return SystemMetrics(
            cpu_usage=cpu_usage,
            memory_usage=memory.percent,
            memory_total=memory.total,
            memory_used=memory.used,
            disk_usage=(disk.used / disk.total) * 100,
            disk_total=disk.total,
            disk_used=disk.used,
            process_count=process_count,
            uptime_seconds=uptime,
            load_average=load_average
        )
    
    async def _get_service_metrics(self) -> ServiceMetrics:
        """获取服务指标"""
        try:
            # 获取文档统计
            documents = await self.state_manager.get_all_documents()
            
            total_documents = len(documents)
            processing_documents = len([d for d in documents if d.status == "processing"])
            completed_documents = len([d for d in documents if d.status == "completed"])
            failed_documents = len([d for d in documents if d.status == "failed"])
            
            # 获取批量操作统计
            batch_operations = await self.state_manager.get_all_batch_operations()
            active_batch_operations = len([b for b in batch_operations if b.status == "running"])
            
            # TODO: 获取查询统计和缓存命中率
            # 这些需要从QueryService中获取
            total_queries = 0
            cache_hit_rate = 0.0
            average_response_time = 0.0
            
            return ServiceMetrics(
                total_documents=total_documents,
                processing_documents=processing_documents,
                completed_documents=completed_documents,
                failed_documents=failed_documents,
                active_batch_operations=active_batch_operations,
                total_queries=total_queries,
                cache_hit_rate=cache_hit_rate,
                average_response_time=average_response_time
            )
            
        except Exception as e:
            # 返回默认值
            return ServiceMetrics(
                total_documents=0,
                processing_documents=0,
                completed_documents=0,
                failed_documents=0,
                active_batch_operations=0,
                total_queries=0,
                cache_hit_rate=0.0,
                average_response_time=0.0
            )
    
    def _calculate_overall_status(self, components: List[ComponentHealth]) -> HealthStatus:
        """计算总体健康状态"""
        if not components:
            return HealthStatus.DOWN
        
        # 如果有任何组件DOWN，则整体DOWN
        if any(c.status == HealthStatus.DOWN for c in components):
            return HealthStatus.DOWN
        
        # 如果有任何组件CRITICAL，则整体CRITICAL
        if any(c.status == HealthStatus.CRITICAL for c in components):
            return HealthStatus.CRITICAL
        
        # 如果有任何组件WARNING，则整体WARNING
        if any(c.status == HealthStatus.WARNING for c in components):
            return HealthStatus.WARNING
        
        # 否则健康
        return HealthStatus.HEALTHY
    
    async def _generate_alerts(
        self,
        metrics: PerformanceMetrics,
        components: List[ComponentHealth]
    ) -> List[Dict[str, Any]]:
        """生成告警"""
        alerts = []
        
        # 准备上下文变量
        context = {
            "metrics": metrics,
            "cpu_usage": metrics.system.cpu_usage,
            "memory_usage": metrics.system.memory_usage,
            "disk_usage": metrics.system.disk_usage,
            "rag_healthy": any(c.name == "RAG System" and c.status == HealthStatus.HEALTHY for c in components),
            "failed_rate": (metrics.service.failed_documents / metrics.service.total_documents * 100) 
                          if metrics.service.total_documents > 0 else 0,
            "total_documents": metrics.service.total_documents
        }
        
        # 检查每个告警规则
        for rule in self.alert_rules:
            if not rule.enabled:
                continue
            
            try:
                # 评估告警条件
                if eval(rule.condition, {"__builtins__": {}}, context):
                    alert = {
                        "rule_name": rule.name,
                        "severity": rule.severity,
                        "message": rule.message.format(**context),
                        "timestamp": datetime.now().isoformat(),
                        "context": {k: v for k, v in context.items() if isinstance(v, (int, float, str, bool))}
                    }
                    alerts.append(alert)
                    
            except Exception as e:
                # 告警规则评估失败，记录错误但不中断流程
                pass
        
        return alerts
    
    def _store_metrics_history(self, metrics: PerformanceMetrics):
        """存储历史指标"""
        self.metrics_history.append(metrics)
        
        # 限制历史记录大小
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history = self.metrics_history[-self.max_history_size:]