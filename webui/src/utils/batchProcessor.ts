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
 */
export async function batchProcessDocuments(
  documentIds: string[],
  onProgress?: (completed: number, total: number, results: any[]) => void
): Promise<{
  successCount: number
  failCount: number
  results: BatchProcessResult<any>[]
  errors: string[]
}> {
  const errors: string[] = []
  
  const results = await BatchProcessor.processInParallel(
    documentIds,
    async (documentId) => {
      const response = await axios.post(`/api/v1/documents/${documentId}/process`)
      if (!response.data?.success) {
        throw new Error(response.data?.message || '处理失败')
      }
      return response.data
    },
    {
      maxConcurrent: PERFORMANCE_CONFIG.batch.maxConcurrentProcess,
      chunkSize: PERFORMANCE_CONFIG.batch.processChunkSize,
      onProgress: (completed, total) => {
        onProgress?.(completed, total, results)
      },
      onItemComplete: (result) => {
        if (!result.success && result.error) {
          errors.push(`文档 ${result.item}: ${result.error}`)
        }
      }
    }
  )
  
  const successCount = results.filter(r => r.success).length
  const failCount = results.filter(r => !r.success).length
  
  return {
    successCount,
    failCount,
    results,
    errors
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