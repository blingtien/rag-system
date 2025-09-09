/**
 * 性能优化配置
 * 用于控制批量操作的并发行为
 */

export const PERFORMANCE_CONFIG = {
  // 批量处理配置
  batch: {
    // 最大并发处理请求数（建议与后端MAX_CONCURRENT_PROCESSING保持一致）
    maxConcurrentProcess: 5,
    // 批处理分组大小
    processChunkSize: 5,
    // 请求重试次数
    maxRetries: 2,
    // 重试延迟（毫秒）
    retryDelay: 1000,
  },
  
  // 上传配置
  upload: {
    // 最大并发上传数
    maxConcurrent: 5,
    // 单文件最大大小（MB）
    maxFileSize: 500,
    // 上传超时（毫秒）
    timeout: 120000,
  },
  
  // WebSocket配置
  websocket: {
    // 重连延迟（毫秒）
    reconnectDelay: 5000,
    // 最大重连次数
    maxReconnectAttempts: 10,
    // 心跳间隔（毫秒）
    heartbeatInterval: 30000,
  },
  
  // 日志配置
  logs: {
    // 最大日志条目数
    maxEntries: 300,
    // 日志批量清理阈值
    cleanupThreshold: 500,
    // 日志自动滚动
    autoScroll: true,
  },
  
  // UI优化
  ui: {
    // 表格分页大小选项
    pageSizeOptions: [10, 20, 50, 100],
    // 默认分页大小
    defaultPageSize: 20,
    // 最大批量选择数
    maxBatchSelection: 50,
    // 防抖延迟（毫秒）
    debounceDelay: 300,
  },
  
  // 缓存配置
  cache: {
    // 文档列表缓存时间（毫秒）
    documentListTTL: 30000,
    // 任务状态缓存时间（毫秒）
    taskStatusTTL: 5000,
  }
}

// 性能监控工具
export class PerformanceMonitor {
  private static timings: Map<string, number> = new Map()
  
  static startTimer(label: string): void {
    this.timings.set(label, performance.now())
  }
  
  static endTimer(label: string): number {
    const start = this.timings.get(label)
    if (!start) return 0
    
    const duration = performance.now() - start
    this.timings.delete(label)
    console.log(`[Performance] ${label}: ${duration.toFixed(2)}ms`)
    return duration
  }
  
  static async measureAsync<T>(
    label: string, 
    fn: () => Promise<T>
  ): Promise<T> {
    this.startTimer(label)
    try {
      const result = await fn()
      this.endTimer(label)
      return result
    } catch (error) {
      this.endTimer(label)
      throw error
    }
  }
}