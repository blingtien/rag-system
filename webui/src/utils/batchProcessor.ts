/**
 * 批量处理工具类
 * 提供并行批处理能力，优化批量操作性能
 */

import axios, { AxiosError } from 'axios'
import { PERFORMANCE_CONFIG } from '../config/performance.config'

export interface BatchProcessResult<T> {
  success: boolean
  data?: T
  error?: string
  index: number
  item: any
}

export interface BatchProcessOptions {
  maxConcurrent?: number
  chunkSize?: number
  onProgress?: (completed: number, total: number) => void
  onItemComplete?: (result: BatchProcessResult<any>) => void
  retryOnError?: boolean
  maxRetries?: number
  retryDelay?: number
}

/**
 * 批量并行处理器
 */
export class BatchProcessor {
  /**
   * 并行处理批量任务
   * @param items 要处理的项目数组
   * @param processor 处理函数
   * @param options 处理选项
   */
  static async processInParallel<T, R>(
    items: T[],
    processor: (item: T, index: number) => Promise<R>,
    options: BatchProcessOptions = {}
  ): Promise<BatchProcessResult<R>[]> {
    const {
      maxConcurrent = PERFORMANCE_CONFIG.batch.maxConcurrentProcess,
      chunkSize = PERFORMANCE_CONFIG.batch.processChunkSize,
      onProgress,
      onItemComplete,
      retryOnError = true,
      maxRetries = PERFORMANCE_CONFIG.batch.maxRetries,
      retryDelay = PERFORMANCE_CONFIG.batch.retryDelay,
    } = options

    const results: BatchProcessResult<R>[] = []
    let completedCount = 0

    // 处理单个项目（带重试）
    const processItem = async (
      item: T, 
      index: number, 
      retryCount = 0
    ): Promise<BatchProcessResult<R>> => {
      try {
        const data = await processor(item, index)
        const result: BatchProcessResult<R> = {
          success: true,
          data,
          index,
          item
        }
        
        completedCount++
        onProgress?.(completedCount, items.length)
        onItemComplete?.(result)
        
        return result
      } catch (error) {
        // 重试逻辑
        if (retryOnError && retryCount < maxRetries) {
          console.warn(`Retrying item ${index} (attempt ${retryCount + 1}/${maxRetries})`)
          await new Promise(resolve => setTimeout(resolve, retryDelay))
          return processItem(item, index, retryCount + 1)
        }
        
        const errorMessage = error instanceof Error ? error.message : String(error)
        const result: BatchProcessResult<R> = {
          success: false,
          error: errorMessage,
          index,
          item
        }
        
        completedCount++
        onProgress?.(completedCount, items.length)
        onItemComplete?.(result)
        
        return result
      }
    }

    // 分批处理
    for (let i = 0; i < items.length; i += chunkSize) {
      const chunk = items.slice(i, Math.min(i + chunkSize, items.length))
      const chunkPromises = chunk.map((item, chunkIndex) => 
        processItem(item, i + chunkIndex)
      )
      
      // 等待当前批次完成
      const chunkResults = await Promise.all(chunkPromises)
      results.push(...chunkResults)
    }

    return results
  }

  /**
   * 使用信号量控制并发
   */
  static async processWithSemaphore<T, R>(
    items: T[],
    processor: (item: T, index: number) => Promise<R>,
    maxConcurrent: number = PERFORMANCE_CONFIG.batch.maxConcurrentProcess
  ): Promise<BatchProcessResult<R>[]> {
    const results: BatchProcessResult<R>[] = []
    const executing: Promise<void>[] = []
    
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      const promise = (async () => {
        try {
          const data = await processor(item, i)
          results[i] = {
            success: true,
            data,
            index: i,
            item
          }
        } catch (error) {
          results[i] = {
            success: false,
            error: error instanceof Error ? error.message : String(error),
            index: i,
            item
          }
        }
      })()
      
      executing.push(promise)
      
      // 控制并发数
      if (executing.length >= maxConcurrent) {
        await Promise.race(executing)
        // 清理已完成的任务
        executing.splice(0, executing.findIndex(p => 
          p === promise || Promise.race([p, Promise.resolve()]) === Promise.resolve()
        ) + 1)
      }
    }
    
    // 等待所有剩余任务完成
    await Promise.all(executing)
    
    return results
  }
}

/**
 * 批量文档处理专用函数
 * 使用后端专用的批量处理API，而不是并行调用个别文档端点
 * 
 * 重要变更：
 * - 现在调用 POST /api/v1/documents/process/batch 而不是多个 POST /api/v1/documents/{id}/process
 * - 这避免了 N 个并行请求，改为 1 个批量请求
 * - 后端会在内部处理并发控制和资源管理
 * - 返回批量操作ID用于可能的状态跟踪
 */
export async function batchProcessDocuments(
  documentIds: string[],
  onProgress?: (completed: number, total: number, results: any[]) => void,
  parser?: string,
  parseMethod?: string
): Promise<{
  successCount: number
  failCount: number
  results: BatchProcessResult<any>[]
  errors: string[]
  batchOperationId?: string
}> {
  const errors: string[] = []
  
  try {
    // 调用后端专用的批量处理端点
    const response = await axios.post('/api/v1/documents/process/batch', {
      document_ids: documentIds,
      parser: parser,
      parse_method: parseMethod
    })
    
    if (!response.data?.success) {
      throw new Error(response.data?.message || '批量处理请求失败')
    }
    
    const batchResult = response.data
    const results: BatchProcessResult<any>[] = []
    
    // 转换后端批量响应为前端期望的格式
    batchResult.results.forEach((backendResult: any, index: number) => {
      const success = backendResult.status === 'started' || backendResult.status === 'success'
      const result: BatchProcessResult<any> = {
        success,
        data: success ? backendResult : undefined,
        error: success ? undefined : (backendResult.message || '处理启动失败'),
        index,
        item: backendResult.document_id
      }
      
      results.push(result)
      
      if (!success && backendResult.message) {
        errors.push(`文档 ${backendResult.file_name || backendResult.document_id}: ${backendResult.message}`)
      }
    })
    
    // 立即报告完成状态给进度回调
    const successCount = batchResult.started_count
    const failCount = batchResult.failed_count
    const totalCount = batchResult.total_requested
    
    // 调用进度回调表示批量启动完成
    onProgress?.(totalCount, totalCount, results)
    
    return {
      successCount,
      failCount,
      results,
      errors,
      batchOperationId: batchResult.batch_operation_id
    }
    
  } catch (error) {
    // 网络或请求错误处理
    const errorMessage = axios.isAxiosError(error)
      ? error.response?.data?.message || error.message
      : '批量处理请求失败'
    
    // 为所有文档创建失败结果
    const results: BatchProcessResult<any>[] = documentIds.map((documentId, index) => ({
      success: false,
      error: errorMessage,
      index,
      item: documentId
    }))
    
    errors.push(`批量处理失败: ${errorMessage}`)
    
    return {
      successCount: 0,
      failCount: documentIds.length,
      results,
      errors
    }
  }
}

/**
 * 批量上传文档
 */
export async function batchUploadFiles(
  files: File[],
  onProgress?: (file: File, progress: number) => void
): Promise<{
  successCount: number
  failCount: number
  results: BatchProcessResult<any>[]
}> {
  const results = await BatchProcessor.processInParallel(
    files,
    async (file) => {
      const formData = new FormData()
      formData.append('file', file)
      
      const response = await axios.post('/api/v1/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            onProgress?.(file, progress)
          }
        }
      })
      
      if (!response.data?.success) {
        throw new Error(response.data?.message || '上传失败')
      }
      
      return response.data
    },
    {
      maxConcurrent: PERFORMANCE_CONFIG.upload.maxConcurrent,
      chunkSize: PERFORMANCE_CONFIG.upload.maxConcurrent
    }
  )
  
  return {
    successCount: results.filter(r => r.success).length,
    failCount: results.filter(r => !r.success).length,
    results
  }
}