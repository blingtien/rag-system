"use client";

import React, { useState, useEffect } from "react";
import { Server, Database, Cpu, Memory, HardDrive, Activity, AlertTriangle, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface SystemMetric {
  name: string;
  value: number;
  unit: string;
  status: 'good' | 'warning' | 'error';
  trend: 'up' | 'down' | 'stable';
}

const SystemStatus = () => {
  const [metrics, setMetrics] = useState<SystemMetric[]>([
    { name: 'CPU使用率', value: 45, unit: '%', status: 'good', trend: 'stable' },
    { name: '内存使用率', value: 68, unit: '%', status: 'warning', trend: 'up' },
    { name: '磁盘使用率', value: 32, unit: '%', status: 'good', trend: 'down' },
    { name: 'GPU使用率', value: 78, unit: '%', status: 'good', trend: 'up' },
  ]);

  const [processingStats, setProcessingStats] = useState({
    documentsProcessed: 24,
    queriesHandled: 156,
    errorRate: 2.1,
    avgResponseTime: 2.3
  });

  const [logs, setLogs] = useState([
    { id: 1, timestamp: new Date(), level: 'info', message: 'Document "research_paper.pdf" processed successfully' },
    { id: 2, timestamp: new Date(Date.now() - 60000), level: 'info', message: 'Query completed in 1.8s' },
    { id: 3, timestamp: new Date(Date.now() - 120000), level: 'warning', message: 'High memory usage detected' },
    { id: 4, timestamp: new Date(Date.now() - 180000), level: 'error', message: 'Failed to process document: timeout' },
    { id: 5, timestamp: new Date(Date.now() - 240000), level: 'info', message: 'System health check completed' },
  ]);

  // 模拟实时数据更新
  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics(prev => prev.map(metric => ({
        ...metric,
        value: Math.max(0, Math.min(100, metric.value + (Math.random() - 0.5) * 10)),
        status: metric.value > 80 ? 'error' : metric.value > 60 ? 'warning' : 'good'
      })));
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: 'good' | 'warning' | 'error') => {
    switch (status) {
      case 'good': return 'text-green-600 bg-green-100 dark:bg-green-900/20';
      case 'warning': return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/20';
      case 'error': return 'text-red-600 bg-red-100 dark:bg-red-900/20';
    }
  };

  const getStatusIcon = (status: 'good' | 'warning' | 'error') => {
    switch (status) {
      case 'good': return <CheckCircle className="h-4 w-4" />;
      case 'warning': case 'error': return <AlertTriangle className="h-4 w-4" />;
    }
  };

  const getTrendIndicator = (trend: 'up' | 'down' | 'stable') => {
    switch (trend) {
      case 'up': return '↗️';
      case 'down': return '↘️';
      case 'stable': return '➡️';
    }
  };

  const getLogLevelColor = (level: string) => {
    switch (level) {
      case 'error': return 'text-red-600 bg-red-50 dark:bg-red-900/20';
      case 'warning': return 'text-yellow-600 bg-yellow-50 dark:bg-yellow-900/20';
      case 'info': return 'text-blue-600 bg-blue-50 dark:bg-blue-900/20';
      default: return 'text-gray-600 bg-gray-50 dark:bg-gray-700';
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">系统状态</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-2">监控RAG系统的运行状态和性能指标</p>
      </div>

      {/* System Health Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {metrics.map((metric, idx) => (
          <div key={idx} className="bg-white dark:bg-neutral-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2">
                {idx === 0 && <Cpu className="h-5 w-5 text-blue-600" />}
                {idx === 1 && <Memory className="h-5 w-5 text-green-600" />}
                {idx === 2 && <HardDrive className="h-5 w-5 text-purple-600" />}
                {idx === 3 && <Server className="h-5 w-5 text-orange-600" />}
                <span className="text-sm font-medium text-gray-900 dark:text-white">{metric.name}</span>
              </div>
              <div className={cn("px-2 py-1 rounded-full text-xs font-medium flex items-center space-x-1", getStatusColor(metric.status))}>
                {getStatusIcon(metric.status)}
                <span>{metric.status === 'good' ? '正常' : metric.status === 'warning' ? '警告' : '错误'}</span>
              </div>
            </div>
            
            <div className="flex items-end justify-between">
              <div>
                <div className="text-2xl font-bold text-gray-900 dark:text-white">
                  {metric.value.toFixed(1)}{metric.unit}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {getTrendIndicator(metric.trend)} 趋势
                </div>
              </div>
              
              {/* Simple progress bar */}
              <div className="w-16 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div 
                  className={cn(
                    "h-full rounded-full transition-all duration-300",
                    metric.status === 'good' ? 'bg-green-500' : 
                    metric.status === 'warning' ? 'bg-yellow-500' : 'bg-red-500'
                  )}
                  style={{ width: `${metric.value}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Processing Statistics */}
      <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center">
          <Activity className="h-5 w-5 mr-2 text-blue-600" />
          处理统计
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">{processingStats.documentsProcessed}</div>
            <div className="text-sm text-gray-600 dark:text-gray-300">已处理文档</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">{processingStats.queriesHandled}</div>
            <div className="text-sm text-gray-600 dark:text-gray-300">查询次数</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600">{processingStats.errorRate}%</div>
            <div className="text-sm text-gray-600 dark:text-gray-300">错误率</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">{processingStats.avgResponseTime}s</div>
            <div className="text-sm text-gray-600 dark:text-gray-300">平均响应时间</div>
          </div>
        </div>
      </div>

      {/* Service Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">服务状态</h3>
          
          <div className="space-y-4">
            {[
              { name: 'LightRAG核心服务', status: 'running', uptime: '2天 14小时' },
              { name: 'MinerU解析器', status: 'running', uptime: '2天 14小时' },
              { name: '向量数据库', status: 'running', uptime: '2天 14小时' },
              { name: '多模态处理器', status: 'warning', uptime: '1天 8小时' },
              { name: 'Web API服务', status: 'running', uptime: '2天 14小时' },
            ].map((service, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <div className="flex items-center space-x-3">
                  <div className={cn(
                    "w-3 h-3 rounded-full",
                    service.status === 'running' ? 'bg-green-500' : 
                    service.status === 'warning' ? 'bg-yellow-500' : 'bg-red-500'
                  )} />
                  <span className="font-medium text-gray-900 dark:text-white">{service.name}</span>
                </div>
                <div className="text-right">
                  <div className={cn(
                    "text-xs px-2 py-1 rounded-full font-medium",
                    service.status === 'running' ? 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-300' :
                    service.status === 'warning' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-300' :
                    'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-300'
                  )}>
                    {service.status === 'running' ? '运行中' : service.status === 'warning' ? '警告' : '已停止'}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    运行时间: {service.uptime}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* System Logs */}
        <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">系统日志</h3>
          
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {logs.map((log) => (
              <div key={log.id} className="flex items-start space-x-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <div className={cn(
                  "px-2 py-1 rounded text-xs font-medium flex-shrink-0",
                  getLogLevelColor(log.level)
                )}>
                  {log.level.toUpperCase()}
                </div>
                
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-900 dark:text-white">{log.message}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {log.timestamp.toLocaleString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
          
          <div className="mt-4 text-center">
            <button className="text-sm text-blue-600 hover:text-blue-800 font-medium">
              查看完整日志
            </button>
          </div>
        </div>
      </div>

      {/* Performance Charts Placeholder */}
      <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">性能趋势</h3>
        <div className="h-64 bg-gray-50 dark:bg-gray-700 rounded-lg flex items-center justify-center">
          <p className="text-gray-500 dark:text-gray-400">性能图表 (可集成Chart.js或其他图表库)</p>
        </div>
      </div>
    </div>
  );
};

export default SystemStatus;