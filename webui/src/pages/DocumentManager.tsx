import React, { useEffect, useState, useRef } from 'react'
import { Card, Typography, Upload, Row, Col, Tag, Table, Button, Progress, Space, message, Modal, Divider, Tooltip, Layout } from 'antd'
import * as Icons from '@ant-design/icons'
const { InboxOutlined, PlayCircleOutlined, DeleteOutlined, ReloadOutlined, ExclamationCircleOutlined, PauseCircleOutlined, ClearOutlined } = Icons
import axios from 'axios'

const { Title, Paragraph } = Typography
const { Dragger } = Upload
const { confirm } = Modal

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

const DocumentManager: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [processingLogs, setProcessingLogs] = useState<string[]>([])
  const [ws, setWs] = useState<WebSocket | null>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)

  const supportedFormats = [
    { emoji: '📄', format: '.pdf', description: 'PDF文档' },
    { emoji: '📝', format: '.docx', description: 'Word文档' },
    { emoji: '📊', format: '.pptx', description: 'PowerPoint演示' },
    { emoji: '📋', format: '.txt', description: '文本文件' },
    { emoji: '📔', format: '.md', description: 'Markdown文件' },
    { emoji: '🖼️', format: '.jpg', description: '图片文件' },
    { emoji: '🖼️', format: '.png', description: '图片文件' },
  ]

  // 获取文档列表
  const fetchDocuments = async () => {
    try {
      const response = await axios.get('/api/v1/documents')
      if (response.data.success) {
        setDocuments(response.data.documents)
      }
    } catch (error) {
      console.error('获取文档列表失败:', error)
    }
  }

  // 获取任务列表
  const fetchTasks = async () => {
    try {
      const response = await axios.get('/api/v1/tasks')
      if (response.data.success) {
        setTasks(response.data.tasks)
      }
    } catch (error) {
      console.error('获取任务列表失败:', error)
    }
  }

  // 刷新数据
  const refreshData = async () => {
    setRefreshing(true)
    await Promise.all([fetchDocuments(), fetchTasks()])
    setRefreshing(false)
  }

  // 启动文档解析
  const startProcessing = async (documentId: string, fileName: string) => {
    try {
      message.loading(`正在启动解析：${fileName}`, 0)
      const response = await axios.post(`/api/v1/documents/${documentId}/process`)
      
      message.destroy() // 清除loading消息
      
      if (response.data.success) {
        message.success(`开始解析：${fileName}`)
        refreshData() // 刷新状态
      } else {
        message.error('启动解析失败')
      }
    } catch (error) {
      message.destroy()
      message.error('启动解析失败')
      console.error('Processing error:', error)
    }
  }

  // 删除文档
  const deleteDocument = (documentId: string, fileName: string) => {
    confirm({
      title: '确认删除',
      icon: <ExclamationCircleOutlined />,
      content: `确定要删除文档"${fileName}"吗？`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      async onOk() {
        try {
          const response = await axios.delete('/api/v1/documents', {
            data: { document_ids: [documentId] }
          })
          if (response.data.success) {
            message.success('文档删除成功')
            refreshData()
          }
        } catch (error) {
          message.error('删除失败')
        }
      }
    })
  }

  // 清空所有文档
  const clearAllDocuments = () => {
    confirm({
      title: '确认清空',
      icon: <ExclamationCircleOutlined />,
      content: '确定要清空所有文档吗？此操作不可恢复！',
      okText: '清空',
      okType: 'danger',
      cancelText: '取消',
      async onOk() {
        try {
          const response = await axios.delete('/api/v1/documents/clear')
          if (response.data.success) {
            message.success('所有文档已清空')
            refreshData()
          }
        } catch (error) {
          message.error('清空失败')
        }
      }
    })
  }

  // 格式化文件大小
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  // 获取状态显示内容（包含进度信息）
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

  // WebSocket连接管理
  const connectWebSocket = () => {
    // 如果已有连接，先关闭
    if (ws && ws.readyState !== WebSocket.CLOSED) {
      ws.close()
    }
    
    const wsUrl = `ws://${window.location.host}/api/v1/documents/progress`
    const websocket = new WebSocket(wsUrl)
    
    websocket.onopen = () => {
      console.log('WebSocket连接已建立')
      setWs(websocket)
    }
    
    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'log') {
        setProcessingLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${data.message}`])
        // 自动滚动到底部
        setTimeout(() => {
          logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
        }, 100)
      }
    }
    
    websocket.onclose = (event) => {
      console.log('WebSocket连接已关闭', event.code, event.reason)
      setWs(null)
      // 只有在非正常关闭时才自动重连
      if (event.code !== 1000 && event.code !== 1001) {
        setTimeout(connectWebSocket, 5000)
      }
    }
    
    websocket.onerror = (error) => {
      console.error('WebSocket错误:', error)
    }
  }

  // 清空日志
  const clearLogs = () => {
    setProcessingLogs([])
  }

  // 组件挂载时加载数据
  useEffect(() => {
    refreshData()
    connectWebSocket()
    // 设置定时刷新
    const interval = setInterval(refreshData, 10000) // 每10秒刷新一次
    
    return () => {
      clearInterval(interval)
      if (ws && ws.readyState !== WebSocket.CLOSED) {
        ws.close(1000, 'Component unmounting') // 正常关闭
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 处理文件拖拽和选择（去重）
  const handleFilesChange = (files: File[]) => {
    setPendingFiles(prev => {
      const newFiles = files.filter(newFile => 
        !prev.some(existingFile => 
          existingFile.name === newFile.name && 
          existingFile.size === newFile.size &&
          existingFile.lastModified === newFile.lastModified
        )
      )
      return [...prev, ...newFiles]
    })
  }

  // 移除待上传文件
  const removePendingFile = (index: number) => {
    setPendingFiles(prev => prev.filter((_, i) => i !== index))
  }

  // 确认上传文件（逐个上传）
  const confirmUpload = async () => {
    if (pendingFiles.length === 0) return
    
    setUploading(true)
    let successCount = 0
    let failCount = 0

    try {
      for (const file of pendingFiles) {
        const formData = new FormData()
        formData.append('file', file)

        try {
          const response = await axios.post('/api/v1/documents/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
          })
          
          if (response.data.success) {
            successCount++
          } else {
            failCount++
          }
        } catch (error) {
          failCount++
          console.error(`Upload error for ${file.name}:`, error)
        }
      }

      if (successCount > 0) {
        message.success(`${successCount} 个文件上传成功${failCount > 0 ? `，${failCount} 个失败` : ''}`)
      }
      if (failCount > 0 && successCount === 0) {
        message.error(`${failCount} 个文件上传失败`)
      }
      
      setPendingFiles([])
      refreshData()
    } catch (error) {
      message.error('上传过程中发生错误')
      console.error('Upload process error:', error)
    } finally {
      setUploading(false)
    }
  }

  const uploadProps = {
    name: 'file',
    multiple: true,
    beforeUpload: (file: File) => {
      handleFilesChange([file])
      return false // 阻止自动上传
    },
    onDrop(e: any) {
      const files = Array.from(e.dataTransfer.files) as File[]
      handleFilesChange(files)
    },
    showUploadList: false,
  }

  // 文档表格列定义
  const documentColumns = [
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

  // 筛选正在运行的任务（用于统计显示）
  const runningTasks = tasks.filter(task => task.status === 'running')

  return (
    <div>
      {/* 页面标题 */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={2}>文档管理</Title>
            <Paragraph type="secondary">上传并处理各种格式的文档，实时查看解析过程</Paragraph>
          </div>
          <Space>
            <Button 
              icon={<ReloadOutlined />} 
              loading={refreshing}
              onClick={refreshData}
            >
              刷新
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

      {/* 上半部分：左侧上传区域 + 右侧解析日志 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {/* 左上角：文件上传区域 */}
        <Col xs={24} lg={12}>
          <Card 
            title="文件上传" 
            style={{ height: '400px' }}
            bodyStyle={{ height: 'calc(100% - 56px)', display: 'flex', flexDirection: 'column' }}
          >
            {/* 待上传文件列表 */}
            {pendingFiles.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  marginBottom: 8
                }}>
                  <span style={{ fontWeight: 'bold' }}>待上传文件 ({pendingFiles.length})</span>
                  <Space>
                    <Button 
                      size="small" 
                      onClick={() => setPendingFiles([])}
                    >
                      清空
                    </Button>
                    <Button 
                      type="primary" 
                      size="small"
                      loading={uploading}
                      onClick={confirmUpload}
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
                  {pendingFiles.map((file, index) => (
                    <div key={index} style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      padding: '4px 0',
                      borderBottom: index < pendingFiles.length - 1 ? '1px solid #f5f5f5' : 'none'
                    }}>
                      <Space size={4}>
                        <span style={{ fontSize: '12px' }}>{file.name}</span>
                        <Tag size="small" color="blue">{formatFileSize(file.size)}</Tag>
                      </Space>
                      <Button 
                        size="small" 
                        type="text" 
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => removePendingFile(index)}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 文件拖拽上传区域 */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <Dragger 
                {...uploadProps} 
                style={{ 
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <div style={{ textAlign: 'center' }}>
                  <p className="ant-upload-drag-icon">
                    <InboxOutlined style={{ fontSize: 32, color: '#1890ff' }} />
                  </p>
                  <p className="ant-upload-text" style={{ fontSize: 14, marginBottom: 8 }}>
                    拖拽文件到此处或点击选择
                  </p>
                  <p className="ant-upload-hint" style={{ color: '#666', fontSize: 12 }}>
                    支持 PDF, Word, PPT, 图片等格式
                  </p>
                </div>
              </Dragger>
            </div>
          </Card>
        </Col>

        {/* 右上角：实时解析日志 */}
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

      {/* 处理统计信息 */}
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

      {/* 已处理文档列表 */}
      <Card 
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>已处理文档 ({documents.length})</span>
            <Space>
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
            emptyText: '暂无文档数据'
          }}
        />
      </Card>

      <Divider style={{ margin: '24px 0' }} />

      {/* 支持的文件格式 */}
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