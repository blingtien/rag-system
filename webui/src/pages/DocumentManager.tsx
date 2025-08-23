import React, { useEffect, useState, useRef, useCallback } from 'react'
import { Card, Typography, Upload, Row, Col, Tag, Table, Button, Progress, Space, message, Modal, Divider, Tooltip, Layout, Checkbox, Alert, Dropdown } from 'antd'
import * as Icons from '@ant-design/icons'
const { InboxOutlined, PlayCircleOutlined, DeleteOutlined, ReloadOutlined, ExclamationCircleOutlined, PauseCircleOutlined, ClearOutlined, FolderOpenOutlined, CheckSquareOutlined, MinusSquareOutlined, DownOutlined, PlaySquareOutlined } = Icons
import axios, { AxiosError } from 'axios'
import { batchProcessDocuments } from '../utils/batchProcessor'
import { PERFORMANCE_CONFIG, PerformanceMonitor } from '../config/performance.config'

const { Title, Paragraph } = Typography
const { Dragger } = Upload
const { confirm } = Modal

// Types and Interfaces
interface Document {
  document_id: string
  file_name: string
  file_size: number
  uploaded_at: string
  status_code: 'pending' | 'uploaded' | 'processing' | 'completed' | 'failed'
  status_display: string
  action_type: string
  action_icon: string
  action_text: string
  can_process: boolean
  task_id?: string
  processing_time?: number
  content_length?: number
  chunks_count?: number
  error_message?: string
}

interface Task {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  stage: string
  file_name: string
  multimodal_stats: {
    images_count: number
    tables_count: number
    equations_count: number
    images_processed: number
    tables_processed: number
    equations_processed: number
    processing_success_rate: number
  }
}

interface PendingFile {
  file: File
  id: string
  status: 'pending' | 'uploading' | 'uploaded' | 'error'
  progress: number
  error?: string
  relativePath?: string // For folder uploads
}

interface UploadResponse {
  success: boolean
  message?: string
  document_id?: string
  task_id?: string
}

// Constants
const MAX_CONCURRENT_UPLOADS = 5
const MAX_BATCH_SELECTION = 50
const MAX_LOG_ENTRIES = 300
const WEBSOCKET_RECONNECT_DELAY = 5000
const SUPPORTED_FILE_TYPES = ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.txt', '.md', '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp']

// Utility function to check if file type is supported
const isFileTypeSupported = (fileName: string): boolean => {
  const extension = fileName.toLowerCase().substring(fileName.lastIndexOf('.'))
  return SUPPORTED_FILE_TYPES.includes(extension)
}

// Generate unique file ID for deduplication
const generateFileId = (file: File): string => {
  return `${file.name}_${file.size}_${file.lastModified}`
}

const DocumentManager: React.FC = () => {
  // State management
  const [documents, setDocuments] = useState<Document[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [processingLogs, setProcessingLogs] = useState<string[]>([])
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>([])
  const [dragOver, setDragOver] = useState(false)
  const isDragEventRef = useRef(false)
  
  // Refs for cleanup and state management
  const wsRef = useRef<WebSocket | null>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const logIdsRef = useRef<Set<string>>(new Set())
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const isComponentMountedRef = useRef(true)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const lastRequestIdRef = useRef<number>(0)
  
  // File deduplication cache for performance
  const fileHashCacheRef = useRef<Map<string, string>>(new Map())

  const supportedFormats = [
    { emoji: '📄', format: '.pdf', description: 'PDF文档' },
    { emoji: '📝', format: '.docx', description: 'Word文档' },
    { emoji: '📊', format: '.pptx', description: 'PowerPoint演示' },
    { emoji: '📋', format: '.txt', description: '文本文件' },
    { emoji: '📔', format: '.md', description: 'Markdown文件' },
    { emoji: '🖼️', format: '.jpg', description: '图片文件' },
    { emoji: '🖼️', format: '.png', description: '图片文件' },
  ]

  // Super simplified data refresh function
  const refreshData = useCallback(async () => {
    console.log('🔄 Starting refreshData...')
    
    setRefreshing(true)
    
    try {
      console.log('📡 Fetching documents from API...')
      const response = await axios.get('/api/v1/documents')
      
      console.log('📥 Raw API response:', response.data)
      
      if (response.data && response.data.success && Array.isArray(response.data.documents)) {
        console.log(`✅ Successfully got ${response.data.documents.length} documents`)
        setDocuments(response.data.documents)
      } else {
        console.log('❌ Invalid API response structure')
        setDocuments([])
      }
    } catch (error) {
      console.error('❌ API call failed:', error)
      message.error('获取文档列表失败')
      setDocuments([])
    }
    
    // Get tasks (non-critical)
    try {
      const tasksResponse = await axios.get('/api/v1/tasks')
      if (tasksResponse.data?.success && Array.isArray(tasksResponse.data.tasks)) {
        setTasks(tasksResponse.data.tasks)
      } else {
        setTasks([])
      }
    } catch (error) {
      console.log('Tasks API failed (non-critical):', error)
      setTasks([])
    }
    
    setRefreshing(false)
  }, [])

  // Enhanced document processing with better error handling
  const startProcessing = async (documentId: string, fileName: string) => {
    if (!documentId || !fileName) {
      message.error('文档信息不完整，无法启动解析')
      return
    }
    
    const loadingKey = `processing-${documentId}`
    
    try {
      message.loading({ content: `正在启动解析：${fileName}`, key: loadingKey, duration: 0 })
      
      const response = await axios.post(`/api/v1/documents/${documentId}/process`)
      
      message.destroy(loadingKey)
      
      if (response.data?.success) {
        message.success(`开始解析：${fileName}`)
        await refreshData()
      } else {
        const errorMsg = response.data?.message || '启动解析失败'
        message.error(errorMsg)
      }
    } catch (error) {
      message.destroy(loadingKey)
      
      const errorMessage = axios.isAxiosError(error)
        ? error.response?.data?.message || error.message
        : '启动解析失败'
      
      message.error(errorMessage)
      console.error('Processing error:', error)
    }
  }
  
  // Batch processing with parallel execution
  const handleBatchProcessDocuments = async (documentIds: string[]) => {
    if (documentIds.length === 0) {
      message.warning('请先选择要解析的文档')
      return
    }

    if (documentIds.length > MAX_BATCH_SELECTION) {
      message.error(`最多只能同时选择 ${MAX_BATCH_SELECTION} 个文档进行批量操作`)
      return
    }

    const selectedDocs = documents.filter(doc => 
      documentIds.includes(doc.document_id) && doc.can_process
    )

    if (selectedDocs.length === 0) {
      message.warning('选中的文档中没有可解析的文档')
      return
    }

    Modal.confirm({
      title: '批量解析确认',
      icon: <ExclamationCircleOutlined />,
      content: (
        <div>
          <p>确定要解析选中的 {selectedDocs.length} 个文档吗？</p>
          <p style={{ fontSize: '12px', color: '#666', marginTop: 8 }}>
            将使用并行处理，最多同时处理 {PERFORMANCE_CONFIG.batch.maxConcurrentProcess} 个文档
          </p>
        </div>
      ),
      okText: '开始解析',
      cancelText: '取消',
      onOk: async () => {
        const loadingKey = 'batch-processing'
        message.loading({ content: '正在启动批量解析...', key: loadingKey, duration: 0 })

        // 记录性能
        PerformanceMonitor.startTimer('batch-process')

        // 使用后端专用的批量处理API
        const validDocIds = selectedDocs.map(doc => doc.document_id)
        const { successCount, failCount, errors, batchOperationId } = await batchProcessDocuments(
          validDocIds,
          (completed, total) => {
            // 更新进度 - 现在表示批量启动的进度
            const progress = Math.round((completed / total) * 100)
            message.loading({ 
              content: `正在启动批量解析... (${completed}/${total}) ${progress}%`, 
              key: loadingKey, 
              duration: 0 
            })
          },
          undefined, // parser: 使用默认解析器
          undefined  // parseMethod: 使用默认方法
        )

        // 记录性能结果
        const duration = PerformanceMonitor.endTimer('batch-process')
        console.log(`批量处理 ${selectedDocs.length} 个文档耗时: ${(duration / 1000).toFixed(2)}秒`)
        
        // 记录批量操作ID用于可能的后续跟踪
        if (batchOperationId) {
          console.log(`批量操作ID: ${batchOperationId}`)
        }

        message.destroy(loadingKey)

        if (successCount > 0) {
          message.success(`成功启动 ${successCount} 个文档的解析${failCount > 0 ? `，${failCount} 个失败` : ''}`)
        }
        
        if (failCount > 0 && errors.length > 0) {
          Modal.error({
            title: '部分文档解析启动失败',
            content: (
              <div>
                <p>失败的文档：</p>
                <ul style={{ maxHeight: '200px', overflow: 'auto' }}>
                  {errors.map((error, index) => (
                    <li key={index} style={{ fontSize: '12px', color: '#ff4d4f' }}>
                      {error}
                    </li>
                  ))}
                </ul>
              </div>
            ),
            width: 600
          })
        }

        setSelectedDocuments([])
        await refreshData()
      }
    })
  }
  
  // Batch delete with enhanced error handling
  const batchDeleteDocuments = async (documentIds: string[]) => {
    if (documentIds.length === 0) {
      message.warning('请先选择要删除的文档')
      return
    }

    if (documentIds.length > MAX_BATCH_SELECTION) {
      message.error(`最多只能同时选择 ${MAX_BATCH_SELECTION} 个文档进行批量操作`)
      return
    }

    const selectedDocs = documents.filter(doc => documentIds.includes(doc.document_id))

    Modal.confirm({
      title: '批量删除确认',
      icon: <ExclamationCircleOutlined />,
      content: `确定要删除选中的 ${selectedDocs.length} 个文档吗？此操作不可恢复！`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          const response = await axios.delete('/api/v1/documents', {
            data: { document_ids: documentIds }
          })
          
          if (response.data?.success) {
            message.success(`成功删除 ${selectedDocs.length} 个文档`)
            setSelectedDocuments([])
            await refreshData()
          } else {
            message.error(response.data?.message || '批量删除失败')
          }
        } catch (error) {
          const errorMessage = axios.isAxiosError(error)
            ? error.response?.data?.message || error.message
            : '批量删除失败'
          message.error(errorMessage)
        }
      }
    })
  }

  // Delete document with enhanced error handling
  const deleteDocument = (documentId: string, fileName: string) => {
    if (!documentId || !fileName) {
      message.error('文档信息不完整，无法删除')
      return
    }

    Modal.confirm({
      title: '确认删除',
      icon: <ExclamationCircleOutlined />,
      content: `确定要删除文档"${fileName}"吗？`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          const response = await axios.delete('/api/v1/documents', {
            data: { document_ids: [documentId] }
          })
          if (response.data?.success) {
            message.success('文档删除成功')
            await refreshData()
          } else {
            message.error(response.data?.message || '删除失败')
          }
        } catch (error) {
          const errorMessage = axios.isAxiosError(error)
            ? error.response?.data?.message || error.message
            : '删除失败'
          message.error(errorMessage)
        }
      }
    })
  }

  // Clear all documents with confirmation
  const clearAllDocuments = () => {
    Modal.confirm({
      title: '确认清空',
      icon: <ExclamationCircleOutlined />,
      content: '确定要清空所有文档吗？此操作不可恢复！',
      okText: '清空',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          const response = await axios.delete('/api/v1/documents/clear')
          if (response.data?.success) {
            message.success('所有文档已清空')
            setSelectedDocuments([])
            await refreshData()
          } else {
            message.error(response.data?.message || '清空失败')
          }
        } catch (error) {
          const errorMessage = axios.isAxiosError(error)
            ? error.response?.data?.message || error.message
            : '清空失败'
          message.error(errorMessage)
        }
      }
    })
  }

  // Format file size
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  // Get status display with enhanced task information
  const getStatusDisplay = (document: Document) => {
    const task = tasks.find(t => t.task_id === document.task_id)
    
    switch (document.status_code) {
      case 'completed':
        return (
          <div>
            <Tag color="success">已完成</Tag>
            {document.chunks_count && (
              <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                共 {document.chunks_count} 个片段
              </div>
            )}
          </div>
        )
      case 'processing':
        return (
          <div>
            <Tag color="processing">解析中</Tag>
            {task && (
              <div style={{ marginTop: 8 }}>
                <Progress 
                  percent={task.progress} 
                  size="small" 
                  status="active"
                  showInfo={false}
                />
                <div style={{ fontSize: 11, color: '#666', marginTop: 2 }}>
                  {task.stage}
                </div>
                <div style={{ fontSize: 10, color: '#999', marginTop: 2 }}>
                  📷 {task.multimodal_stats.images_processed}/{task.multimodal_stats.images_count} | 
                  📊 {task.multimodal_stats.tables_processed}/{task.multimodal_stats.tables_count} | 
                  🧮 {task.multimodal_stats.equations_processed}/{task.multimodal_stats.equations_count}
                </div>
              </div>
            )}
          </div>
        )
      case 'queued':
        return (
          <div>
            <Tag color="orange">排队等待</Tag>
            <div style={{ fontSize: 12, color: '#ff7a00', marginTop: 4 }}>
              正在等待处理资源释放
            </div>
          </div>
        )
      case 'pending':
      case 'uploaded':
        return <Tag color="default">{document.status_display}</Tag>
      case 'failed':
        return (
          <div>
            <Tag color="error">解析失败</Tag>
            {document.error_message && (
              <Tooltip title={document.error_message}>
                <div style={{ fontSize: 12, color: '#ff4d4f', marginTop: 4, cursor: 'help' }}>
                  点击查看错误详情
                </div>
              </Tooltip>
            )}
          </div>
        )
      default:
        return <Tag>{document.status_display}</Tag>
    }
  }

  // Efficient log deduplication hash function
  const generateLogHash = useCallback((message: string, timestamp: number): string => {
    let hash = 0
    const str = `${timestamp}_${message}`
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i)
      hash = ((hash << 5) - hash) + char
      hash = hash & hash
    }
    return hash.toString(36)
  }, [])

  // Memory cleanup function with enhanced management
  const cleanupMemory = useCallback(() => {
    // Clean log deduplication set, keep only recent 300
    if (logIdsRef.current.size > 800) {
      const ids = Array.from(logIdsRef.current)
      const toKeep = ids.slice(-300)
      logIdsRef.current.clear()
      toKeep.forEach(id => logIdsRef.current.add(id))
    }
    
    // Clean file hash cache periodically
    if (fileHashCacheRef.current.size > 500) {
      fileHashCacheRef.current.clear()
    }
  }, [])

  // Enhanced WebSocket connection management
  const connectWebSocket = useCallback(() => {
    if (!isComponentMountedRef.current) return
    
    // Clean up existing connections and reconnect timers
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.close(1000, 'Creating new connection')
    }
    
    const wsUrl = `ws://${window.location.host}/api/v1/documents/progress`
    const websocket = new WebSocket(wsUrl)
    
    wsRef.current = websocket
    
    websocket.onopen = () => {
      console.log('WebSocket连接已建立')
    }
    
    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'log' && isComponentMountedRef.current) {
          const timestamp = data.timestamp || Date.now()
          const logHash = generateLogHash(data.message, timestamp)
          
          if (!logIdsRef.current.has(logHash)) {
            const logEntry = `[${new Date(timestamp).toLocaleTimeString()}] ${data.message}`
            
            logIdsRef.current.add(logHash)
            
            setProcessingLogs(prev => {
              const newLogs = [...prev, logEntry]
              return newLogs.length > MAX_LOG_ENTRIES ? newLogs.slice(-MAX_LOG_ENTRIES) : newLogs
            })
            
            // Use requestAnimationFrame for smooth scrolling
            requestAnimationFrame(() => {
              if (logsEndRef.current && isComponentMountedRef.current) {
                logsEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' })
              }
            })
            
            // Periodic memory cleanup
            if (logIdsRef.current.size % 100 === 0) {
              cleanupMemory()
            }
          }
        }
      } catch (error) {
        console.error('解析WebSocket消息失败:', error)
      }
    }
    
    websocket.onclose = (event) => {
      console.log('WebSocket连接已关闭', event.code, event.reason)
      
      if (wsRef.current === websocket) {
        wsRef.current = null
      }
      
      // Smart reconnection: only reconnect on abnormal closure
      const shouldReconnect = (
        event.code !== 1000 &&
        event.code !== 1001 &&
        event.code !== 1005 &&
        isComponentMountedRef.current
      )
      
      if (shouldReconnect) {
        console.log(`WebSocket异常关闭，${WEBSOCKET_RECONNECT_DELAY/1000}秒后尝试重连...`)
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isComponentMountedRef.current) {
            connectWebSocket()
          }
        }, WEBSOCKET_RECONNECT_DELAY)
      }
    }
    
    websocket.onerror = (error) => {
      console.error('WebSocket错误:', error)
    }
    
    return websocket
  }, [generateLogHash, cleanupMemory])

  // Clear logs and memory
  const clearLogs = useCallback(() => {
    setProcessingLogs([])
    logIdsRef.current.clear()
    // Suggest garbage collection if available
    if (window.gc) {
      window.gc()
    }
  }, [])

  // Enhanced file deduplication check - now includes server-side documents
  const isDuplicateFile = useCallback((newFile: File, existingFiles: PendingFile[]): boolean => {
    const fileKey = `${newFile.name}_${newFile.size}_${newFile.lastModified}`
    
    // Check cache first
    if (fileHashCacheRef.current.has(fileKey)) {
      return true
    }
    
    // Check against pending files (local queue)
    const isPendingDuplicate = existingFiles.some(existing => 
      existing.file.name === newFile.name && 
      existing.file.size === newFile.size &&
      existing.file.lastModified === newFile.lastModified
    )
    
    // Check against server-side documents (by file name)
    const isServerDuplicate = documents.some(doc => 
      doc.file_name === newFile.name
    )
    
    const isDuplicate = isPendingDuplicate || isServerDuplicate
    
    if (isDuplicate) {
      fileHashCacheRef.current.set(fileKey, 'duplicate')
    }
    
    return isDuplicate
  }, [documents])

  // Enhanced file handling with folder support
  const handleFilesChange = useCallback((files: File[]) => {
    const newPendingFiles: PendingFile[] = []
    let duplicateCount = 0
    let unsupportedCount = 0

    files.forEach(file => {
      // Check file type support
      if (!isFileTypeSupported(file.name)) {
        unsupportedCount++
        return
      }

      // Check for duplicates
      if (!isDuplicateFile(file, pendingFiles) && !isDuplicateFile(file, newPendingFiles)) {
        newPendingFiles.push({
          file,
          id: generateFileId(file),
          status: 'pending',
          progress: 0,
          relativePath: (file as any).webkitRelativePath || file.name
        })
      } else {
        duplicateCount++
      }
    })

    // Show feedback messages
    if (unsupportedCount > 0) {
      message.warning(`已过滤 ${unsupportedCount} 个不支持的文件格式`)
    }

    if (duplicateCount > 0) {
      message.warning(`已过滤 ${duplicateCount} 个重复文件（包括服务器已存在的文件）`)
    }

    if (newPendingFiles.length > 0) {
      setPendingFiles(prev => [...prev, ...newPendingFiles])
      message.success(`添加了 ${newPendingFiles.length} 个文件到上传队列`)
    } else if (files.length > 0) {
      message.warning('没有找到可以添加的新文件')
    }
  }, [pendingFiles, isDuplicateFile])

  // Handle folder selection
  const handleFolderSelect = useCallback(() => {
    if (folderInputRef.current) {
      folderInputRef.current.click()
    }
  }, [])

  // Handle folder input change
  const handleFolderInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length > 0) {
      message.info(`从文件夹中选择了 ${files.length} 个文件`)
      handleFilesChange(files)
    }
    // Reset input value to allow selecting the same folder again
    if (folderInputRef.current) {
      folderInputRef.current.value = ''
    }
  }, [handleFilesChange])

  // Remove pending file
  const removePendingFile = useCallback((id: string) => {
    setPendingFiles(prev => prev.filter(file => file.id !== id))
  }, [])

  // Enhanced upload with concurrent processing
  const confirmUpload = async () => {
    if (pendingFiles.length === 0) {
      message.warning('没有待上传的文件')
      return
    }
    
    const filesToUpload = pendingFiles.filter(f => f.status === 'pending')
    
    if (filesToUpload.length === 0) {
      message.warning('没有可上传的文件')
      setUploading(false)
      return
    }

    setUploading(true)
    let successCount = 0
    let failCount = 0
    const uploadErrors: string[] = []

    try {
      // Process files in batches for better performance
      for (let i = 0; i < filesToUpload.length; i += MAX_CONCURRENT_UPLOADS) {
        const batch = filesToUpload.slice(i, i + MAX_CONCURRENT_UPLOADS)
        
        const batchPromises = batch.map(async (pendingFile) => {
          try {
            // Update file status to uploading
            setPendingFiles(prev => prev.map(f => 
              f.id === pendingFile.id ? { ...f, status: 'uploading' as const } : f
            ))

            const formData = new FormData()
            formData.append('file', pendingFile.file)

            const response = await axios.post('/api/v1/documents/upload', formData, {
              headers: { 'Content-Type': 'multipart/form-data' },
              onUploadProgress: (progressEvent) => {
                if (progressEvent.total) {
                  const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
                  setPendingFiles(prev => prev.map(f => 
                    f.id === pendingFile.id ? { ...f, progress } : f
                  ))
                }
              }
            })
            
            if (response.data?.success) {
              successCount++
              setPendingFiles(prev => prev.map(f => 
                f.id === pendingFile.id ? { ...f, status: 'uploaded' as const, progress: 100 } : f
              ))
            } else {
              failCount++
              const errorMsg = response.data?.message || '上传失败'
              setPendingFiles(prev => prev.map(f => 
                f.id === pendingFile.id ? { 
                  ...f, 
                  status: 'error' as const, 
                  error: errorMsg 
                } : f
              ))
              uploadErrors.push(`${pendingFile.file.name}: ${errorMsg}`)
            }
          } catch (error) {
            failCount++
            let errorMessage = '上传失败'
            
            if (axios.isAxiosError(error)) {
              if (error.response?.status === 400 && error.response?.data?.detail?.includes('已存在')) {
                errorMessage = '文件名已存在'
              } else {
                errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message
              }
            }
            
            setPendingFiles(prev => prev.map(f => 
              f.id === pendingFile.id ? { 
                ...f, 
                status: 'error' as const, 
                error: errorMessage 
              } : f
            ))
            
            uploadErrors.push(`${pendingFile.file.name}: ${errorMessage}`)
            console.error(`Upload error for ${pendingFile.file.name}:`, error)
          }
        })

        // Wait for current batch to complete before processing next batch
        await Promise.all(batchPromises)
      }

      // Show results
      if (successCount > 0) {
        message.success(`${successCount} 个文件上传成功${failCount > 0 ? `，${failCount} 个失败` : ''}`)
      }
      
      if (failCount > 0) {
        if (successCount === 0) {
          message.error(`${failCount} 个文件上传失败`)
        }
        
        // Show detailed errors in modal
        if (uploadErrors.length > 0) {
          Modal.error({
            title: '部分文件上传失败',
            content: (
              <div>
                <p>失败的文件：</p>
                <ul style={{ maxHeight: '200px', overflow: 'auto' }}>
                  {uploadErrors.map((error, index) => (
                    <li key={index} style={{ fontSize: '12px', color: '#ff4d4f' }}>
                      {error}
                    </li>
                  ))}
                </ul>
              </div>
            ),
            width: 600
          })
        }
      }
      
      // Remove successfully uploaded files after a delay
      setTimeout(() => {
        setPendingFiles(prev => prev.filter(f => f.status !== 'uploaded'))
      }, 2000)
      
      await refreshData()
      
    } catch (error) {
      message.error('上传过程中发生错误')
      console.error('Upload process error:', error)
    } finally {
      setUploading(false)
    }
  }

  // Batch selection related methods
  const handleSelectAll = useCallback((checked: boolean) => {
    if (checked) {
      const selectableIds = documents
        .filter(doc => doc.status_code !== 'processing')
        .slice(0, MAX_BATCH_SELECTION)
        .map(doc => doc.document_id)
      setSelectedDocuments(selectableIds)
      
      if (documents.length > MAX_BATCH_SELECTION) {
        message.info(`只选择了前 ${MAX_BATCH_SELECTION} 个文档`)
      }
    } else {
      setSelectedDocuments([])
    }
  }, [documents])

  const handleSelectDocument = useCallback((documentId: string, checked: boolean) => {
    setSelectedDocuments(prev => {
      if (checked) {
        if (prev.length >= MAX_BATCH_SELECTION) {
          message.warning(`最多只能选择 ${MAX_BATCH_SELECTION} 个文档`)
          return prev
        }
        return [...prev, documentId]
      } else {
        return prev.filter(id => id !== documentId)
      }
    })
  }, [])

  // Drag and drop handlers
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
    isDragEventRef.current = true
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    
    const files = Array.from(e.dataTransfer.files) as File[]
    handleFilesChange(files)
    
    // Reset drag event flag after a longer delay to ensure upload component doesn't interfere
    setTimeout(() => {
      isDragEventRef.current = false
    }, 500)
  }, [handleFilesChange])

  // Enhanced upload props with better error handling
  const uploadProps = {
    name: 'file',
    multiple: true,
    directory: true, // Enable folder upload
    beforeUpload: (file: File) => {
      // Skip processing if this is from a drag event to avoid duplication
      if (isDragEventRef.current) {
        return false
      }
      
      // Handle file selection (click/browse events only)
      handleFilesChange([file])
      return false // Prevent automatic upload
    },
    showUploadList: false,
    accept: SUPPORTED_FILE_TYPES.join(',')
    // onDrop is handled by the container div to avoid duplication
  }

  // Check selection states
  const selectableDocuments = documents.filter(doc => doc.status_code !== 'processing')
  const isAllSelected = selectableDocuments.length > 0 && selectedDocuments.length === Math.min(selectableDocuments.length, MAX_BATCH_SELECTION)
  const isIndeterminate = selectedDocuments.length > 0 && selectedDocuments.length < Math.min(selectableDocuments.length, MAX_BATCH_SELECTION)

  // Enhanced document table columns with batch selection
  const documentColumns = [
    {
      title: (
        <Checkbox
          indeterminate={isIndeterminate}
          onChange={(e) => handleSelectAll(e.target.checked)}
          checked={isAllSelected}
        >
          全选
        </Checkbox>
      ),
      dataIndex: 'selection',
      key: 'selection',
      width: 80,
      render: (_: any, record: Document) => (
        <Checkbox
          checked={selectedDocuments.includes(record.document_id)}
          onChange={(e) => handleSelectDocument(record.document_id, e.target.checked)}
          disabled={record.status_code === 'processing'}
        />
      ),
    },
    {
      title: '文件名',
      dataIndex: 'file_name',
      key: 'file_name',
      ellipsis: true,
    },
    {
      title: '文件大小',
      dataIndex: 'file_size',
      key: 'file_size',
      render: (size: number) => formatFileSize(size),
      width: 120,
    },
    {
      title: '状态',
      key: 'status_display',
      render: (record: Document) => getStatusDisplay(record),
      width: 200,
    },
    {
      title: '上传时间',
      dataIndex: 'uploaded_at',
      key: 'uploaded_at',
      render: (time: string) => new Date(time).toLocaleString(),
      width: 180,
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: Document) => (
        <Space>
          {record.can_process ? (
            <Tooltip title={record.action_text}>
              <Button 
                type="primary"
                shape="circle"
                icon={record.action_icon === 'play' ? <PlayCircleOutlined /> : <PauseCircleOutlined />} 
                size="small"
                onClick={() => startProcessing(record.document_id, record.file_name)}
              />
            </Tooltip>
          ) : record.status_code === 'processing' ? (
            <Tooltip title="解析进行中">
              <Button 
                type="default"
                shape="circle"
                icon={<PauseCircleOutlined />} 
                size="small"
                disabled
              />
            </Tooltip>
          ) : (
            <Tooltip title={record.status_display}>
              <Button 
                type="default"
                shape="circle"
                icon={<PlayCircleOutlined />} 
                size="small"
                disabled
                style={{ opacity: 0.5 }}
              />
            </Tooltip>
          )}
          <Tooltip title="删除文档">
            <Button 
              danger
              shape="circle"
              icon={<DeleteOutlined />} 
              size="small"
              onClick={() => deleteDocument(record.document_id, record.file_name)}
            />
          </Tooltip>
        </Space>
      ),
      width: 120,
    },
  ]

  // Batch operation menu items
  const batchOperationMenuItems = [
    {
      key: 'batch-process',
      label: '批量解析',
      icon: <PlaySquareOutlined />,
      disabled: selectedDocuments.length === 0
    },
    {
      key: 'batch-delete',
      label: '批量删除',
      icon: <DeleteOutlined />,
      disabled: selectedDocuments.length === 0
    }
  ]

  const handleBatchMenuClick = ({ key }: { key: string }) => {
    switch (key) {
      case 'batch-process':
        handleBatchProcessDocuments(selectedDocuments)
        break
      case 'batch-delete':
        batchDeleteDocuments(selectedDocuments)
        break
    }
  }

  // Filter running tasks for statistics
  const runningTasks = tasks.filter(task => task.status === 'running')

  // Simplified component mount effect
  useEffect(() => {
    console.log('🚀 DocumentManager component mounting')
    isComponentMountedRef.current = true
    
    // Initial data load
    refreshData()
    connectWebSocket()
    
    return () => {
      console.log('🔄 DocumentManager component unmounting')
      isComponentMountedRef.current = false
      
      // Clean up timers
      if (pollIntervalRef.current) {
        clearTimeout(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
      
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      
      // Clean up WebSocket
      if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
        wsRef.current.close(1000, 'Component unmounting')
      }
      wsRef.current = null
      
      // Clean up memory
      logIdsRef.current.clear()
      fileHashCacheRef.current.clear()
    }
  }, []) // Empty dependency array to run only once on mount

  // Debug effect to track documents state changes
  useEffect(() => {
    console.log('📊 Documents state changed:', {
      count: documents.length,
      documents: documents.map(d => ({ id: d.document_id, name: d.file_name, status: d.status_code }))
    })
  }, [documents])

  // Debug effect to track loading state changes  
  useEffect(() => {
    console.log('⏳ Loading states:', { loading, refreshing })
  }, [loading, refreshing])

  return (
    <div>
      {/* Hidden folder input */}
      <input
        ref={folderInputRef}
        type="file"
        webkitdirectory="true"
        multiple
        style={{ display: 'none' }}
        onChange={handleFolderInputChange}
        accept={SUPPORTED_FILE_TYPES.join(',')}
      />

      {/* Page title */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={2}>文档管理</Title>
            <Paragraph type="secondary">上传并处理各种格式的文档，支持批量操作和文件夹上传，实时查看解析过程</Paragraph>
          </div>
          <Space>
            <Button 
              icon={<ReloadOutlined />} 
              loading={refreshing}
              onClick={refreshData}
            >
              刷新 (调试: {documents.length} 文档)
            </Button>
            <Button 
              danger 
              onClick={clearAllDocuments}
              disabled={documents.length === 0}
            >
              清空所有
            </Button>
          </Space>
        </div>
      </div>

      {/* Upper section: Upload area + Processing logs */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {/* Left: File upload area */}
        <Col xs={24} lg={12}>
          <Card 
            title={
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>文件上传</span>
                <Button
                  icon={<FolderOpenOutlined />}
                  size="small"
                  onClick={handleFolderSelect}
                >
                  选择文件夹
                </Button>
              </div>
            }
            style={{ height: '400px' }}
            bodyStyle={{ height: 'calc(100% - 56px)', display: 'flex', flexDirection: 'column' }}
          >
            {/* Pending files list */}
            {pendingFiles.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  marginBottom: 8
                }}>
                  <span style={{ fontWeight: 'bold' }}>
                    待上传文件 ({pendingFiles.length})
                    {pendingFiles.length > MAX_CONCURRENT_UPLOADS && (
                      <Tag size="small" color="orange" style={{ marginLeft: 8 }}>
                        将分批上传
                      </Tag>
                    )}
                  </span>
                  <Space>
                    <Button 
                      size="small" 
                      onClick={() => setPendingFiles([])}
                      disabled={uploading}
                    >
                      清空
                    </Button>
                    <Button 
                      type="primary" 
                      size="small"
                      loading={uploading}
                      onClick={confirmUpload}
                      disabled={pendingFiles.filter(f => f.status === 'pending').length === 0}
                    >
                      确认上传
                    </Button>
                  </Space>
                </div>
                <div style={{ 
                  maxHeight: '120px', 
                  overflowY: 'auto',
                  border: '1px solid #f0f0f0',
                  borderRadius: '6px',
                  padding: '8px'
                }}>
                  {pendingFiles.map((pendingFile) => (
                    <div key={pendingFile.id} style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      padding: '4px 0',
                      borderBottom: '1px solid #f5f5f5'
                    }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 2 }}>
                          <span style={{ 
                            fontSize: '12px', 
                            flex: 1, 
                            overflow: 'hidden', 
                            textOverflow: 'ellipsis', 
                            whiteSpace: 'nowrap',
                            marginRight: 8
                          }}>
                            {pendingFile.relativePath || pendingFile.file.name}
                          </span>
                          <Tag size="small" color="blue">{formatFileSize(pendingFile.file.size)}</Tag>
                        </div>
                        {pendingFile.status === 'uploading' && (
                          <Progress 
                            percent={pendingFile.progress} 
                            size="small" 
                            showInfo={false}
                            status="active"
                          />
                        )}
                        {pendingFile.status === 'uploaded' && (
                          <Tag color="success" size="small">上传成功</Tag>
                        )}
                        {pendingFile.status === 'error' && (
                          <Tooltip title={pendingFile.error}>
                            <Tag color="error" size="small">上传失败</Tag>
                          </Tooltip>
                        )}
                      </div>
                      <Button 
                        size="small" 
                        type="text" 
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => removePendingFile(pendingFile.id)}
                        disabled={pendingFile.status === 'uploading'}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* File drag upload area */}
            <div 
              style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
            >
              <Dragger 
                {...uploadProps} 
                style={{ 
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: dragOver ? '2px dashed #1890ff' : '2px dashed #d9d9d9',
                  backgroundColor: dragOver ? '#f0f8ff' : undefined,
                  transition: 'all 0.3s'
                }}
              >
                <div style={{ textAlign: 'center' }}>
                  <p className="ant-upload-drag-icon">
                    <InboxOutlined style={{ 
                      fontSize: 32, 
                      color: dragOver ? '#1890ff' : '#1890ff' 
                    }} />
                  </p>
                  <p className="ant-upload-text" style={{ fontSize: 14, marginBottom: 8 }}>
                    拖拽文件或文件夹到此处，或点击选择
                  </p>
                  <p className="ant-upload-hint" style={{ color: '#666', fontSize: 12 }}>
                    支持 PDF, Word, PPT, 图片等格式，支持批量和文件夹上传
                  </p>
                  {dragOver && (
                    <p style={{ color: '#1890ff', fontSize: 12, marginTop: 8 }}>
                      松开鼠标开始上传
                    </p>
                  )}
                </div>
              </Dragger>
            </div>
          </Card>
        </Col>

        {/* Right: Real-time processing logs */}
        <Col xs={24} lg={12}>
          <Card 
            title={
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>解析过程日志</span>
                <Space>
                  <span style={{ fontSize: '12px', color: '#666' }}>
                    {processingLogs.length} 条日志
                  </span>
                  <Button 
                    size="small" 
                    icon={<ClearOutlined />}
                    onClick={clearLogs}
                    disabled={processingLogs.length === 0}
                  >
                    清空
                  </Button>
                </Space>
              </div>
            }
            style={{ height: '400px' }}
            bodyStyle={{ 
              height: 'calc(100% - 56px)', 
              padding: 0,
              display: 'flex',
              flexDirection: 'column'
            }}
          >
            <div style={{
              flex: 1,
              overflowY: 'auto',
              backgroundColor: '#000',
              color: '#00ff00',
              fontFamily: 'Monaco, Consolas, "Courier New", monospace',
              fontSize: '11px',
              lineHeight: '1.4',
              padding: '8px 12px'
            }}>
              {processingLogs.length === 0 ? (
                <div style={{ color: '#666', textAlign: 'center', paddingTop: '20px' }}>
                  暂无解析日志，上传文档后开始解析即可查看详细过程
                </div>
              ) : (
                <div>
                  {processingLogs.map((log, index) => (
                    <div key={index} style={{ marginBottom: '2px', wordBreak: 'break-all' }}>
                      {log}
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              )}
            </div>
          </Card>
        </Col>
      </Row>

      {/* Processing statistics */}
      {runningTasks.length > 0 && (
        <Card 
          size="small" 
          style={{ marginBottom: 24, backgroundColor: '#f6ffed', borderColor: '#b7eb8f' }}
        >
          <Space>
            <Tag color="processing">正在处理 {runningTasks.length} 个文档</Tag>
            <span style={{ color: '#666' }}>
              详细过程可在上方日志区域查看，进度会在下方表格中实时更新
            </span>
          </Space>
        </Card>
      )}

      {/* Batch operation alert */}
      {selectedDocuments.length > 0 && (
        <Alert
          message={`已选择 ${selectedDocuments.length} 个文档`}
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          action={
            <Space>
              <Button
                size="small"
                type="primary"
                icon={<PlaySquareOutlined />}
                onClick={() => handleBatchProcessDocuments(selectedDocuments)}
              >
                批量解析
              </Button>
              <Button
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={() => batchDeleteDocuments(selectedDocuments)}
              >
                批量删除
              </Button>
              <Button
                size="small"
                onClick={() => setSelectedDocuments([])}
              >
                取消选择
              </Button>
            </Space>
          }
        />
      )}

      {/* Document list */}
      <Card 
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>已处理文档 ({documents.length})</span>
            <Space>
              {selectedDocuments.length > 0 && (
                <Dropdown
                  menu={{ 
                    items: batchOperationMenuItems,
                    onClick: handleBatchMenuClick
                  }}
                  trigger={['click']}
                >
                  <Button icon={<DownOutlined />}>
                    批量操作
                  </Button>
                </Dropdown>
              )}
              <span style={{ fontSize: 14, fontWeight: 'normal', color: '#666' }}>
                共 {documents.length} 个文档
              </span>
            </Space>
          </div>
        }
        style={{ marginBottom: 24 }}
      >
        <Table
          dataSource={documents}
          columns={documentColumns}
          rowKey="document_id"
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
          }}
          locale={{
            emptyText: `暂无文档数据 (调试: documents数组长度=${documents.length}, refreshing=${refreshing})`
          }}
          scroll={{ x: true }}
          loading={refreshing}
        />
      </Card>

      <Divider style={{ margin: '24px 0' }} />

      {/* Supported file formats */}
      <Card title="支持的文件格式" size="small">
        <Row gutter={[12, 12]}>
          {supportedFormats.map((format, index) => (
            <Col xs={12} sm={8} md={6} lg={4} xl={3} key={index}>
              <div
                style={{ 
                  textAlign: 'center', 
                  backgroundColor: '#fafafa',
                  padding: '12px',
                  borderRadius: '6px',
                  border: '1px solid #f0f0f0'
                }}
              >
                <div style={{ fontSize: 20, marginBottom: 6 }}>{format.emoji}</div>
                <div style={{ fontWeight: 'bold', marginBottom: 4 }}>
                  <Tag size="small" color="blue">{format.format}</Tag>
                </div>
                <div style={{ fontSize: 11, color: '#666' }}>{format.description}</div>
              </div>
            </Col>
          ))}
        </Row>
      </Card>
    </div>
  )
}

export default DocumentManager