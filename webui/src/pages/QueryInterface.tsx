import React, { useState } from 'react'
import { Card, Typography, Input, Button, Radio, Space, List, Tag, message } from 'antd'
import * as Icons from '@ant-design/icons'
const { SendOutlined, FileImageOutlined, TableOutlined, EditOutlined } = Icons
import axios from 'axios'

const { Title, Paragraph } = Typography
const { TextArea } = Input

interface QueryResult {
  query: string
  mode: string
  result: string
  timestamp: string
  processing_time: number
}

const QueryInterface: React.FC = () => {
  const [query, setQuery] = useState('')
  const [queryMode, setQueryMode] = useState('hybrid')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<QueryResult[]>([])

  const handleQuery = async () => {
    if (!query.trim()) {
      message.warning('请输入查询内容')
      return
    }

    setLoading(true)
    try {
      const response = await axios.post('/api/v1/query', {
        query: query,
        mode: queryMode
      })

      if (response.data.success) {
        const newResult: QueryResult = {
          query: response.data.query,
          mode: response.data.mode,
          result: response.data.result,
          timestamp: response.data.timestamp,
          processing_time: response.data.processing_time
        }
        setResults([newResult, ...results])
        setQuery('')
        message.success('查询完成')
      }
    } catch (error) {
      console.error('查询失败:', error)
      message.error('查询失败，请检查API连接')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 32 }}>
        <Title level={2}>智能查询</Title>
        <Paragraph type="secondary">基于多模态RAG系统的智能问答</Paragraph>
      </div>

      {/* 查询模式选择 */}
      <Card title="查询模式" style={{ marginBottom: 24 }}>
        <Radio.Group value={queryMode} onChange={(e) => setQueryMode(e.target.value)}>
          <Space wrap>
            <Radio.Button value="local">本地查询</Radio.Button>
            <Radio.Button value="global">全局查询</Radio.Button>
            <Radio.Button value="hybrid">混合查询</Radio.Button>
            <Radio.Button value="naive">简单查询</Radio.Button>
          </Space>
        </Radio.Group>
      </Card>

      {/* 查询输入 */}
      <Card style={{ marginBottom: 24 }}>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', marginBottom: 8, fontWeight: 'bold' }}>
            输入您的问题
          </label>
          <TextArea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="例如：请分析这个表格中的数据趋势..."
            rows={4}
            style={{ marginBottom: 16 }}
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Button icon={<FileImageOutlined />} title="添加图片" />
            <Button icon={<TableOutlined />} title="添加表格" />
            <Button icon={<EditOutlined />} title="添加公式" />
          </Space>

          <Button
            type="primary"
            icon={<SendOutlined />}
            loading={loading}
            onClick={handleQuery}
          >
            发送查询
          </Button>
        </div>
      </Card>

      {/* 查询结果 */}
      {results.length > 0 && (
        <div>
          <Title level={4} style={{ marginBottom: 16 }}>查询结果</Title>
          <List
            dataSource={results}
            renderItem={(item) => (
              <List.Item>
                <Card style={{ width: '100%' }}>
                  <div style={{ marginBottom: 16 }}>
                    <Title level={5} style={{ marginBottom: 8 }}>{item.query}</Title>
                    <Space>
                      <span>{new Date(item.timestamp).toLocaleString()}</span>
                      <Tag color="blue">{item.mode}</Tag>
                      <span>耗时: {(item.processing_time * 1000).toFixed(1)}ms</span>
                    </Space>
                  </div>
                  <Paragraph>{item.result}</Paragraph>
                </Card>
              </List.Item>
            )}
          />
        </div>
      )}
    </div>
  )
}

export default QueryInterface