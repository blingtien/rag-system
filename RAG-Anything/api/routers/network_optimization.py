#!/usr/bin/env python3
"""
网络优化API路由

提供网络优化相关的API端点:
1. 优化配置管理
2. 性能监控数据
3. 网络诊断
4. 连接池状态
5. 负载均衡状态
6. 实时统计信息
"""

import asyncio
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse

from middleware.network_optimization_suite import (
    network_optimization_suite,
    NetworkOptimizationConfig,
    OptimizationLevel,
    get_network_optimization_suite
)
from middleware.network_performance_monitor import DiagnosticLevel
from middleware.websocket_load_balancer import LoadBalancingAlgorithm
from middleware.websocket_reliability_layer import QoSLevel
from middleware.websocket_message_optimizer import MessagePriority

router = APIRouter(prefix="/api/v1/network", tags=["network-optimization"])


@router.get("/optimization/status")
async def get_optimization_status():
    """获取网络优化状态"""
    try:
        suite = get_network_optimization_suite()
        health_status = suite.get_health_status()
        
        return {
            "status": "success",
            "data": health_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get optimization status: {str(e)}")


@router.get("/optimization/statistics")
async def get_optimization_statistics():
    """获取详细的优化统计信息"""
    try:
        suite = get_network_optimization_suite()
        stats = await suite.get_optimization_statistics()
        
        return {
            "status": "success",
            "data": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get optimization statistics: {str(e)}")


@router.get("/optimization/configuration")
async def get_optimization_configuration():
    """获取当前优化配置"""
    try:
        suite = get_network_optimization_suite()
        config_dict = suite.config.to_dict()
        
        return {
            "status": "success",
            "data": {
                "current_configuration": config_dict,
                "available_options": {
                    "optimization_levels": [level.value for level in OptimizationLevel],
                    "qos_levels": [qos.value for qos in QoSLevel],
                    "message_priorities": [priority.value for priority in MessagePriority],
                    "load_balancing_algorithms": [alg.value for alg in LoadBalancingAlgorithm],
                    "diagnostic_levels": [level.value for level in DiagnosticLevel]
                }
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {str(e)}")


@router.post("/optimization/configure")
async def update_optimization_configuration(config_updates: Dict[str, Any] = Body(...)):
    """更新优化配置"""
    try:
        suite = get_network_optimization_suite()
        
        # 验证配置参数
        valid_updates = {}
        
        if "optimization_level" in config_updates:
            level = config_updates["optimization_level"]
            if level in [l.value for l in OptimizationLevel]:
                valid_updates["optimization_level"] = OptimizationLevel(level)
        
        if "connection_pooling" in config_updates:
            pool_config = config_updates["connection_pooling"]
            if isinstance(pool_config, dict):
                valid_updates.update(pool_config)
        
        if "message_optimization" in config_updates:
            msg_config = config_updates["message_optimization"]
            if isinstance(msg_config, dict):
                valid_updates["message_optimization"] = msg_config
        
        if "reliability" in config_updates:
            rel_config = config_updates["reliability"]
            if isinstance(rel_config, dict):
                valid_updates.update(rel_config)
        
        if "http2" in config_updates:
            http2_config = config_updates["http2"]
            if isinstance(http2_config, dict):
                valid_updates["http2"] = http2_config
        
        if "monitoring" in config_updates:
            mon_config = config_updates["monitoring"]
            if isinstance(mon_config, dict):
                valid_updates.update(mon_config)
        
        if "load_balancing" in config_updates:
            lb_config = config_updates["load_balancing"]
            if isinstance(lb_config, dict):
                valid_updates["load_balancing"] = lb_config
        
        # 应用配置更新
        if valid_updates:
            await suite.configure(**valid_updates)
        
        return {
            "status": "success",
            "message": "Configuration updated successfully",
            "updated_fields": list(valid_updates.keys()),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update configuration: {str(e)}")


@router.post("/diagnostics/run")
async def run_network_diagnostics(
    level: str = Query(default="standard", description="Diagnostic level: basic, standard, advanced, deep")
):
    """运行网络诊断"""
    try:
        # 验证诊断级别
        if level not in [l.value for l in DiagnosticLevel]:
            raise HTTPException(status_code=400, detail=f"Invalid diagnostic level: {level}")
        
        diagnostic_level = DiagnosticLevel(level.upper())
        
        suite = get_network_optimization_suite()
        results = await suite.run_network_diagnostics(diagnostic_level)
        
        return {
            "status": "success",
            "data": results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run diagnostics: {str(e)}")


@router.get("/connection-pools/status")
async def get_connection_pools_status():
    """获取连接池状态"""
    try:
        suite = get_network_optimization_suite()
        
        if not suite.connection_pool_manager:
            return {
                "status": "success",
                "data": {
                    "enabled": False,
                    "message": "Connection pooling is not enabled"
                },
                "timestamp": datetime.now().isoformat()
            }
        
        stats = await suite.connection_pool_manager.get_all_statistics()
        
        return {
            "status": "success",
            "data": {
                "enabled": True,
                "statistics": stats
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get connection pools status: {str(e)}")


@router.post("/connection-pools/create")
async def create_connection_pool(
    pool_id: str = Body(..., description="Pool identifier"),
    min_connections: int = Body(default=2, description="Minimum connections"),
    max_connections: int = Body(default=100, description="Maximum connections"),
    strategy: str = Body(default="least_connections", description="Load balancing strategy")
):
    """创建新的连接池"""
    try:
        suite = get_network_optimization_suite()
        
        if not suite.connection_pool_manager:
            raise HTTPException(status_code=400, detail="Connection pooling is not enabled")
        
        # 验证策略
        from middleware.websocket_connection_pool import PoolStrategy
        if strategy not in [s.value for s in PoolStrategy]:
            raise HTTPException(status_code=400, detail=f"Invalid strategy: {strategy}")
        
        pool_strategy = PoolStrategy(strategy)
        
        pool = await suite.connection_pool_manager.create_pool(
            pool_id=pool_id,
            min_connections=min_connections,
            max_connections=max_connections,
            strategy=pool_strategy
        )
        
        return {
            "status": "success",
            "message": f"Connection pool '{pool_id}' created successfully",
            "data": {
                "pool_id": pool_id,
                "min_connections": min_connections,
                "max_connections": max_connections,
                "strategy": strategy
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create connection pool: {str(e)}")


@router.delete("/connection-pools/{pool_id}")
async def remove_connection_pool(pool_id: str):
    """移除连接池"""
    try:
        suite = get_network_optimization_suite()
        
        if not suite.connection_pool_manager:
            raise HTTPException(status_code=400, detail="Connection pooling is not enabled")
        
        await suite.connection_pool_manager.remove_pool(pool_id)
        
        return {
            "status": "success",
            "message": f"Connection pool '{pool_id}' removed successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove connection pool: {str(e)}")


@router.get("/load-balancer/status")
async def get_load_balancer_status():
    """获取负载均衡器状态"""
    try:
        suite = get_network_optimization_suite()
        
        if not suite.load_balancer:
            return {
                "status": "success",
                "data": {
                    "enabled": False,
                    "message": "Load balancing is not enabled"
                },
                "timestamp": datetime.now().isoformat()
            }
        
        stats = await suite.load_balancer.get_load_balancer_statistics()
        
        return {
            "status": "success",
            "data": {
                "enabled": True,
                "statistics": stats
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get load balancer status: {str(e)}")


@router.post("/load-balancer/add-node")
async def add_load_balancer_node(
    host: str = Body(..., description="Server host"),
    port: int = Body(..., description="Server port"),
    weight: float = Body(default=1.0, description="Server weight"),
    max_connections: int = Body(default=1000, description="Maximum connections"),
    region: Optional[str] = Body(default=None, description="Server region")
):
    """添加负载均衡节点"""
    try:
        suite = get_network_optimization_suite()
        
        if not suite.load_balancer:
            raise HTTPException(status_code=400, detail="Load balancing is not enabled")
        
        node_id = await suite.load_balancer.add_server_node(
            host=host,
            port=port,
            weight=weight,
            max_connections=max_connections,
            region=region
        )
        
        return {
            "status": "success",
            "message": f"Load balancer node '{node_id}' added successfully",
            "data": {
                "node_id": node_id,
                "host": host,
                "port": port,
                "weight": weight,
                "max_connections": max_connections,
                "region": region
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add load balancer node: {str(e)}")


@router.delete("/load-balancer/nodes/{node_id}")
async def remove_load_balancer_node(node_id: str):
    """移除负载均衡节点"""
    try:
        suite = get_network_optimization_suite()
        
        if not suite.load_balancer:
            raise HTTPException(status_code=400, detail="Load balancing is not enabled")
        
        await suite.load_balancer.remove_server_node(node_id)
        
        return {
            "status": "success",
            "message": f"Load balancer node '{node_id}' removed successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove load balancer node: {str(e)}")


@router.get("/performance/current")
async def get_current_performance_metrics():
    """获取当前性能指标"""
    try:
        suite = get_network_optimization_suite()
        
        if not suite.performance_monitor:
            return {
                "status": "success",
                "data": {
                    "enabled": False,
                    "message": "Performance monitoring is not enabled"
                },
                "timestamp": datetime.now().isoformat()
            }
        
        current_metrics = suite.performance_monitor.get_current_metrics()
        
        return {
            "status": "success",
            "data": {
                "enabled": True,
                "current_metrics": current_metrics.to_dict() if current_metrics else None
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")


@router.get("/performance/history")
async def get_performance_history(
    hours: int = Query(default=24, description="Number of hours of history to retrieve")
):
    """获取性能历史数据"""
    try:
        suite = get_network_optimization_suite()
        
        if not suite.performance_monitor:
            raise HTTPException(status_code=400, detail="Performance monitoring is not enabled")
        
        history = suite.performance_monitor.get_metrics_history(hours)
        
        return {
            "status": "success",
            "data": {
                "hours_requested": hours,
                "data_points": len(history),
                "metrics": [metric.to_dict() for metric in history]
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance history: {str(e)}")


@router.get("/message-optimization/statistics")
async def get_message_optimization_statistics():
    """获取消息优化统计"""
    try:
        suite = get_network_optimization_suite()
        
        if not suite.message_optimizer:
            return {
                "status": "success",
                "data": {
                    "enabled": False,
                    "message": "Message optimization is not enabled"
                },
                "timestamp": datetime.now().isoformat()
            }
        
        stats = suite.message_optimizer.get_optimization_statistics()
        
        return {
            "status": "success",
            "data": {
                "enabled": True,
                "statistics": stats
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get message optimization statistics: {str(e)}")


@router.get("/reliability/sessions")
async def get_reliability_sessions():
    """获取可靠性会话信息"""
    try:
        suite = get_network_optimization_suite()
        
        if not suite.reliability_manager:
            return {
                "status": "success",
                "data": {
                    "enabled": False,
                    "message": "Reliability layer is not enabled"
                },
                "timestamp": datetime.now().isoformat()
            }
        
        stats = await suite.reliability_manager.get_all_statistics()
        
        return {
            "status": "success",
            "data": {
                "enabled": True,
                "statistics": stats
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get reliability sessions: {str(e)}")


@router.post("/optimization/restart")
async def restart_optimization_suite():
    """重启优化套件"""
    try:
        suite = get_network_optimization_suite()
        
        # 停止当前实例
        await suite.stop()
        
        # 重新启动
        await suite.start()
        
        return {
            "status": "success",
            "message": "Network optimization suite restarted successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart optimization suite: {str(e)}")


@router.get("/health")
async def health_check():
    """健康检查端点"""
    try:
        suite = get_network_optimization_suite()
        health = suite.get_health_status()
        
        status_code = 200 if health['status'] == 'healthy' else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "success",
                "data": health,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
        )


@router.get("/dashboard/summary")
async def get_dashboard_summary():
    """获取仪表板摘要信息"""
    try:
        suite = get_network_optimization_suite()
        
        # 收集各组件的关键指标
        summary = {
            "optimization_level": suite.config.optimization_level.value,
            "suite_status": suite.get_health_status(),
            "key_metrics": {}
        }
        
        # 连接池指标
        if suite.connection_pool_manager:
            pool_stats = await suite.connection_pool_manager.get_all_statistics()
            summary["key_metrics"]["connection_pools"] = {
                "total_pools": pool_stats.get("pool_count", 0),
                "total_connections": sum(
                    pool.get("size", {}).get("current", 0) 
                    for pool in pool_stats.get("pools", {}).values()
                )
            }
        
        # 消息优化指标
        if suite.message_optimizer:
            msg_stats = suite.message_optimizer.get_optimization_statistics()
            summary["key_metrics"]["message_optimization"] = {
                "compression_ratio": msg_stats.get("compression", {}).get("overall_compression_ratio", 0),
                "messages_processed": msg_stats.get("optimizer", {}).get("total_messages_processed", 0)
            }
        
        # 性能监控指标
        if suite.performance_monitor:
            current_metrics = suite.performance_monitor.get_current_metrics()
            if current_metrics:
                summary["key_metrics"]["performance"] = {
                    "latency_ms": current_metrics.latency_ms,
                    "packet_loss_percent": current_metrics.packet_loss_percent,
                    "active_connections": current_metrics.active_connections
                }
        
        # 负载均衡指标
        if suite.load_balancer:
            lb_stats = await suite.load_balancer.get_load_balancer_statistics()
            summary["key_metrics"]["load_balancing"] = {
                "total_nodes": lb_stats.get("nodes", {}).get("total_nodes", 0),
                "healthy_nodes": lb_stats.get("nodes", {}).get("healthy_nodes", 0),
                "success_rate": lb_stats.get("requests", {}).get("success_rate", 0)
            }
        
        return {
            "status": "success",
            "data": summary,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard summary: {str(e)}")


@router.get("/recommendations")
async def get_optimization_recommendations():
    """获取优化建议"""
    try:
        suite = get_network_optimization_suite()
        recommendations = []
        
        # 基于当前配置和性能数据生成建议
        if not suite.config.enable_message_compression:
            recommendations.append({
                "type": "configuration",
                "priority": "medium",
                "title": "启用消息压缩",
                "description": "启用消息压缩可以减少网络带宽使用",
                "action": "enable_message_compression"
            })
        
        if not suite.config.enable_performance_monitoring:
            recommendations.append({
                "type": "monitoring",
                "priority": "high", 
                "title": "启用性能监控",
                "description": "性能监控有助于识别网络问题",
                "action": "enable_performance_monitoring"
            })
        
        # 基于性能数据的建议
        if suite.performance_monitor:
            current_metrics = suite.performance_monitor.get_current_metrics()
            if current_metrics:
                if current_metrics.latency_ms > 100:
                    recommendations.append({
                        "type": "performance",
                        "priority": "high",
                        "title": "高延迟检测",
                        "description": f"当前延迟 {current_metrics.latency_ms:.1f}ms 较高，建议检查网络连接",
                        "action": "investigate_latency"
                    })
                
                if current_metrics.packet_loss_percent > 1:
                    recommendations.append({
                        "type": "performance",
                        "priority": "critical",
                        "title": "包丢失检测",
                        "description": f"检测到 {current_metrics.packet_loss_percent:.1f}% 的包丢失",
                        "action": "investigate_packet_loss"
                    })
        
        return {
            "status": "success",
            "data": {
                "recommendations": recommendations,
                "count": len(recommendations)
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")