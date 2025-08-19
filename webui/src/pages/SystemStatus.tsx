import React, { useEffect, useState } from 'react'
import { Card, Typography, Row, Col, Statistic, List, Tag } from 'antd'
import * as Icons from '@ant-design/icons'
const { 
  DesktopOutlined, 
  CloudOutlined, 
  DatabaseOutlined, 
  ThunderboltOutlined 
} = Icons

const { Title, Paragraph } = Typography

interface SystemMetrics {
  cpu_usage: number
  memory_usage: number
  disk_usage: number
  gpu_usage: number
}

interface ServiceInfo {
  status: string
  uptime: string
}

interface SystemStatusData {
  metrics: SystemMetrics
  services: Record<string, ServiceInfo>
}

const SystemStatus: React.FC = () => {
  const [statusData, setStatusData] = useState<SystemStatusData>({
    metrics: {
      cpu_usage: 0,
      memory_usage: 0,
      disk_usage: 0,
      gpu_usage: 0
    },
    services: {}
  })

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch('/api/system/status')
        const data = await response.json()
        if (data.success) {
          setStatusData({
            metrics: data.metrics,
            services: data.services
          })
        }
      } catch (error) {
        console.error('获取系统状态失败:', error)
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 30000) // 每30秒更新一次

    return () => clearInterval(interval)
  }, [])

  const getStatusColor = (usage: number) => {
    if (usage < 50) return '#52c41a'
    if (usage < 80) return '#faad14'
    return '#ff4d4f'
  }

  const getStatusTag = (usage: number) => {
    if (usage < 50) return <Tag color="success">正常</Tag>
    if (usage < 80) return <Tag color="warning">警告</Tag>
    return <Tag color="error">危险</Tag>
  }

  return (
    <div>
      <div style={{ marginBottom: 32 }}>
        <Title level={2}>系统状态</Title>
        <Paragraph type="secondary">监控RAG系统的运行状态和性能指标</Paragraph>
      </div>

      {/* 系统指标 */}
      <Row gutter={[24, 24]} style={{ marginBottom: 32 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <DesktopOutlined style={{ color: '#1890ff' }} />
                <span style={{ fontSize: 14, fontWeight: 500 }}>CPU使用率</span>
              </div>
              {getStatusTag(statusData.metrics.cpu_usage)}
            </div>
            <Statistic
              value={statusData.metrics.cpu_usage}
              suffix="%"
              valueStyle={{ color: getStatusColor(statusData.metrics.cpu_usage) }}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <CloudOutlined style={{ color: '#52c41a' }} />
                <span style={{ fontSize: 14, fontWeight: 500 }}>内存使用率</span>
              </div>
              {getStatusTag(statusData.metrics.memory_usage)}
            </div>
            <Statistic
              value={statusData.metrics.memory_usage}
              suffix="%"
              valueStyle={{ color: getStatusColor(statusData.metrics.memory_usage) }}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <DatabaseOutlined style={{ color: '#722ed1' }} />
                <span style={{ fontSize: 14, fontWeight: 500 }}>磁盘使用率</span>
              </div>
              {getStatusTag(statusData.metrics.disk_usage)}
            </div>
            <Statistic
              value={statusData.metrics.disk_usage}
              suffix="%"
              valueStyle={{ color: getStatusColor(statusData.metrics.disk_usage) }}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <ThunderboltOutlined style={{ color: '#fa8c16' }} />
                <span style={{ fontSize: 14, fontWeight: 500 }}>GPU使用率</span>
              </div>
              {getStatusTag(statusData.metrics.gpu_usage)}
            </div>
            <Statistic
              value={statusData.metrics.gpu_usage}
              suffix="%"
              valueStyle={{ color: getStatusColor(statusData.metrics.gpu_usage) }}
            />
          </Card>
        </Col>
      </Row>

      {/* 服务状态 */}
      <Card title="服务状态">
        <List
          dataSource={Object.entries(statusData.services)}
          renderItem={([serviceName, serviceInfo]) => (
            <List.Item>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div
                    style={{
                      width: 12,
                      height: 12,
                      borderRadius: '50%',
                      backgroundColor: serviceInfo.status === 'running' ? '#52c41a' : '#ff4d4f'
                    }}
                  />
                  <span style={{ fontWeight: 500 }}>{serviceName}</span>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div>
                    <Tag color={serviceInfo.status === 'running' ? 'success' : 'error'}>
                      {serviceInfo.status === 'running' ? '运行中' : '已停止'}
                    </Tag>
                  </div>
                  <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                    运行时间: {serviceInfo.uptime}
                  </div>
                </div>
              </div>
            </List.Item>
          )}
        />
      </Card>
    </div>
  )
}

export default SystemStatus