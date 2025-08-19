import React, { useEffect, useState } from 'react'
import { Card, Row, Col, Typography, Button, List, Statistic } from 'antd'
import * as Icons from '@ant-design/icons'

const { 
  FileTextOutlined, 
  NodeIndexOutlined, 
  ApartmentOutlined, 
  BlockOutlined,
  UploadOutlined,
  SearchOutlined
} = Icons
import { useNavigate } from 'react-router-dom'

const { Title, Paragraph } = Typography

interface SystemStats {
  documents_processed: number
  entities_count: number
  relationships_count: number
  chunks_count: number
}

const Overview: React.FC = () => {
  const navigate = useNavigate()
  const [stats, setStats] = useState<SystemStats>({
    documents_processed: 0,
    entities_count: 0,
    relationships_count: 0,
    chunks_count: 0
  })

  useEffect(() => {
    // 模拟获取系统状态
    fetch('/api/system/status')
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setStats({
            documents_processed: data.processing_stats.documents_processed,
            entities_count: data.processing_stats.entities_count,
            relationships_count: data.processing_stats.relationships_count,
            chunks_count: data.processing_stats.chunks_count
          })
        }
      })
      .catch(err => console.log('获取系统状态失败:', err))
  }, [])

  const recentActivities = [
    { icon: '🟢', text: '文档 "research_paper.pdf" 处理完成' },
    { icon: '🔵', text: '执行了查询: "机器学习的应用场景"' },
    { icon: '🟣', text: '更新了系统配置' },
  ]

  return (
    <div>
      <div style={{ marginBottom: 32 }}>
        <Title level={2}>RAG-Anything 仪表盘</Title>
        <Paragraph type="secondary">多模态检索增强生成系统控制中心</Paragraph>
      </div>

      {/* 统计卡片 */}
      <Row gutter={[24, 24]} style={{ marginBottom: 32 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="已处理文档"
              value={stats.documents_processed}
              prefix={<FileTextOutlined style={{ color: '#1890ff' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="知识实体"
              value={stats.entities_count}
              prefix={<NodeIndexOutlined style={{ color: '#52c41a' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="实体关系"
              value={stats.relationships_count}
              prefix={<ApartmentOutlined style={{ color: '#722ed1' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="文本块"
              value={stats.chunks_count}
              prefix={<BlockOutlined style={{ color: '#fa8c16' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* 快速操作和最近活动 */}
      <Row gutter={[24, 24]}>
        <Col xs={24} lg={12}>
          <Card title="快速操作">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <Button
                type="primary"
                icon={<UploadOutlined />}
                size="large"
                onClick={() => navigate('/documents')}
                block
              >
                上传新文档
              </Button>
              <Button
                icon={<SearchOutlined />}
                size="large"
                onClick={() => navigate('/query')}
                block
              >
                开始查询
              </Button>
            </div>
          </Card>
        </Col>
        
        <Col xs={24} lg={12}>
          <Card title="最近活动">
            <List
              dataSource={recentActivities}
              renderItem={(item) => (
                <List.Item>
                  <span style={{ marginRight: 8 }}>{item.icon}</span>
                  {item.text}
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default Overview