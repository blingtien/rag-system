import React from 'react'
import { Layout, Menu, Typography } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import * as Icons from '@ant-design/icons'

const {
  DashboardOutlined,
  FileTextOutlined,
  MessageOutlined,
  ApartmentOutlined,
  BarChartOutlined,
  SettingOutlined
} = Icons

const { Sider } = Layout
const { Title } = Typography

const Sidebar: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()

  const menuItems = [
    {
      key: '/overview',
      icon: <DashboardOutlined />,
      label: '概览',
    },
    {
      key: '/documents',
      icon: <FileTextOutlined />,
      label: '文档管理',
    },
    {
      key: '/query',
      icon: <MessageOutlined />,
      label: '智能查询',
    },
    {
      key: '/graph',
      icon: <ApartmentOutlined />,
      label: '知识图谱',
    },
    {
      key: '/status',
      icon: <BarChartOutlined />,
      label: '系统状态',
    },
    {
      key: '/config',
      icon: <SettingOutlined />,
      label: '配置',
    },
  ]

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  return (
    <Sider width={240} theme="light" style={{ boxShadow: '2px 0 8px rgba(0,0,0,0.1)' }}>
      <div style={{ padding: '24px 16px', borderBottom: '1px solid #f0f0f0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: 32,
              height: 32,
              background: '#1890ff',
              borderRadius: 8,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontWeight: 'bold',
            }}
          >
            R
          </div>
          <Title level={4} style={{ margin: 0 }}>
            RAG-Anything
          </Title>
        </div>
      </div>
      
      <Menu
        mode="inline"
        selectedKeys={[location.pathname]}
        items={menuItems}
        onClick={handleMenuClick}
        style={{ border: 'none', marginTop: '16px' }}
      />
    </Sider>
  )
}

export default Sidebar