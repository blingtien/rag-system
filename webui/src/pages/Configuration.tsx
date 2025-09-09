import React, { useState } from 'react'
import { Card, Typography, Button, Space, message, Alert } from 'antd'
import * as Icons from '@ant-design/icons'
const { WifiOutlined, CheckCircleOutlined, CloseCircleOutlined } = Icons

const { Title, Paragraph } = Typography

const Configuration: React.FC = () => {
  const [testing, setTesting] = useState(false)
  const [connectionResult, setConnectionResult] = useState<{
    success: boolean
    message: string
  } | null>(null)

  const testConnection = async () => {
    setTesting(true)
    setConnectionResult(null)

    try {
      const response = await fetch('/health')
      const data = await response.json()

      if (response.ok) {
        setConnectionResult({
          success: true,
          message: '连接成功！API服务器运行正常'
        })
      } else {
        throw new Error('API响应异常')
      }
    } catch (error) {
      setConnectionResult({
        success: false,
        message: `连接失败：${error instanceof Error ? error.message : '未知错误'}`
      })
    } finally {
      setTesting(false)
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 32 }}>
        <Title level={2}>系统配置</Title>
        <Paragraph type="secondary">管理RAG系统的各项配置参数</Paragraph>
      </div>

      {/* 连接测试 */}
      <Card title="连接测试" style={{ marginBottom: 24 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Button
            type="primary"
            icon={<WifiOutlined />}
            loading={testing}
            onClick={testConnection}
          >
            测试API连接
          </Button>

          {connectionResult && (
            <Alert
              message={connectionResult.message}
              type={connectionResult.success ? 'success' : 'error'}
              icon={connectionResult.success ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
              showIcon
            />
          )}
        </Space>
      </Card>

      {/* 其他配置区域可以在这里添加 */}
      <Card title="系统信息">
        <Space direction="vertical">
          <div>
            <strong>前端版本:</strong> React + TypeScript + Ant Design
          </div>
          <div>
            <strong>后端API:</strong> http://localhost:8000
          </div>
          <div>
            <strong>构建工具:</strong> Vite
          </div>
        </Space>
      </Card>
    </div>
  )
}

export default Configuration