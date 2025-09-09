import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Card, Spin, Alert, Button, Space, Select, InputNumber, Slider } from 'antd';
import { ReloadOutlined, FullscreenOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons';
import ForceGraph2D from 'react-force-graph-2d';
import axios from 'axios';

interface GraphNode {
  id: string;
  name: string;
  type: string;
  properties?: any;
  color?: string;
  size?: number;
}

interface GraphEdge {
  source: string;
  target: string;
  name?: string;
  type: string;
  properties?: any;
  color?: string;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphEdge[];
}

const GraphVisualization: React.FC = () => {
  const forceRef = useRef<any>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [nodeLimit, setNodeLimit] = useState(10);
  const [linkDistance, setLinkDistance] = useState(200);
  const [nodeSize, setNodeSize] = useState(8);

  // 节点颜色映射
  const getNodeColor = (type: string) => {
    const colors: { [key: string]: string } = {
      'concept': '#5B8FF9',
      'entity': '#5AD8A6', 
      'person': '#5D7092',
      'location': '#F6BD16',
      'organization': '#E86452',
      'default': '#9270CA'
    };
    return colors[type] || colors.default;
  };

  // Fetch graph data from API
  const fetchGraphData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      console.log('Fetching graph data...');
      
      // Fetch nodes and relationships separately
      const [nodesResponse, edgesResponse] = await Promise.all([
        axios.get(`/api/v1/graph/nodes?limit=${nodeLimit}`),
        axios.get(`/api/v1/graph/relationships?limit=${nodeLimit}`)
      ]);
      
      console.log('Nodes response:', nodesResponse.data);
      console.log('Edges response:', edgesResponse.data);
      
      const nodesData = nodesResponse.data;
      const edgesData = edgesResponse.data;
      
      // Transform API data to react-force-graph format
      const nodes = nodesData.nodes?.map((node: any) => ({
        id: node.id,
        name: node.label || node.id,
        type: node.type || 'entity',
        properties: node.properties,
        color: getNodeColor(node.type || 'entity'),
        size: nodeSize,
      })) || [];
      
      const links = edgesData.edges?.map((edge: any) => ({
        source: edge.source,
        target: edge.target,
        name: edge.label || edge.type,
        type: edge.type || 'relationship',
        properties: edge.properties,
        color: '#e2e2e2',
      })) || [];

      console.log('Processed nodes:', nodes);
      console.log('Processed links:', links);

      setGraphData({ nodes, links });
      
    } catch (err: any) {
      console.error('Error fetching graph data:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to load graph data');
    } finally {
      setLoading(false);
    }
  };

  // Load data on component mount
  useEffect(() => {
    fetchGraphData();
  }, [nodeLimit]);

  // Node click handler
  const handleNodeClick = useCallback((node: GraphNode) => {
    console.log('Node clicked:', node);
    // Focus on clicked node
    if (forceRef.current) {
      forceRef.current.centerAt(node.x, node.y, 1000);
      forceRef.current.zoom(2, 1000);
    }
  }, []);

  // Link click handler
  const handleLinkClick = useCallback((link: GraphEdge) => {
    console.log('Link clicked:', link);
  }, []);

  // Control handlers
  const handleZoomToFit = () => {
    if (forceRef.current) {
      forceRef.current.zoomToFit(400);
    }
  };

  const handleCenterGraph = () => {
    if (forceRef.current) {
      forceRef.current.centerAt(0, 0, 1000);
    }
  };

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title="Knowledge Graph Visualization"
        extra={
          <Space>
            <InputNumber
              addonBefore="Nodes"
              value={nodeLimit}
              onChange={(value) => setNodeLimit(value || 10)}
              min={5}
              max={100}
              style={{ width: 130 }}
            />
            <Button 
              icon={<ReloadOutlined />} 
              onClick={fetchGraphData}
              loading={loading}
            >
              Refresh
            </Button>
          </Space>
        }
      >
        {error && (
          <Alert
            message="Error loading graph data"
            description={error}
            type="error"
            style={{ marginBottom: 16 }}
            showIcon
          />
        )}
        
        <div style={{ marginBottom: 16 }}>
          <Space wrap>
            <Button icon={<FullscreenOutlined />} onClick={handleZoomToFit}>
              Zoom to Fit
            </Button>
            <Button onClick={handleCenterGraph}>
              Center
            </Button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '12px', minWidth: '80px' }}>Link Distance:</span>
              <Slider
                style={{ width: 100 }}
                min={50}
                max={500}
                value={linkDistance}
                onChange={setLinkDistance}
              />
              <span style={{ fontSize: '12px' }}>{linkDistance}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '12px', minWidth: '70px' }}>Node Size:</span>
              <Slider
                style={{ width: 80 }}
                min={4}
                max={20}
                value={nodeSize}
                onChange={setNodeSize}
              />
              <span style={{ fontSize: '12px' }}>{nodeSize}</span>
            </div>
          </Space>
        </div>

        <div style={{ position: 'relative' }}>
          {loading && (
            <div style={{ 
              position: 'absolute', 
              top: '50%', 
              left: '50%', 
              transform: 'translate(-50%, -50%)',
              zIndex: 10,
              background: 'rgba(255, 255, 255, 0.95)',
              padding: '24px',
              borderRadius: '8px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.15)'
            }}>
              <Spin size="large" tip="Loading graph data..." />
            </div>
          )}
          
          <div 
            style={{ 
              width: '100%', 
              height: '600px', 
              border: '1px solid #d9d9d9',
              borderRadius: '6px',
              backgroundColor: '#fafafa',
              overflow: 'hidden'
            }} 
          >
            {graphData.nodes.length > 0 && (
              <ForceGraph2D
                ref={forceRef}
                graphData={graphData}
                nodeId="id"
                nodeLabel="name"
                nodeColor="color"
                nodeVal={(node: any) => nodeSize}
                linkSource="source"
                linkTarget="target"
                linkLabel="name"
                linkColor="color"
                linkDirectionalArrowLength={6}
                linkDirectionalArrowRelPos={1}
                linkDirectionalParticles={2}
                linkDirectionalParticleSpeed={0.005}
                d3ForceLink={(d3: any) => d3.distance(linkDistance).strength(0.1)}
                d3ForceManyBody={(d3: any) => d3.strength(-300)}
                d3ForceCenter={(d3: any) => d3.strength(0.05)}
                onNodeClick={handleNodeClick}
                onLinkClick={handleLinkClick}
                enablePanInteraction={true}
                enableZoomInteraction={true}
                enableNodeDrag={true}
                nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
                  // Draw node
                  ctx.beginPath();
                  ctx.arc(node.x, node.y, nodeSize, 0, 2 * Math.PI, false);
                  ctx.fillStyle = node.color;
                  ctx.fill();
                  ctx.strokeStyle = '#fff';
                  ctx.lineWidth = 2;
                  ctx.stroke();
                  
                  // Draw label
                  const label = node.name;
                  const fontSize = Math.max(12/globalScale, 3);
                  ctx.font = `${fontSize}px Arial`;
                  ctx.fillStyle = '#333';
                  ctx.textAlign = 'center';
                  ctx.textBaseline = 'middle';
                  ctx.fillText(label, node.x, node.y + nodeSize + fontSize);
                }}
              />
            )}
          </div>
        </div>
        
        <div style={{ marginTop: 16, fontSize: '12px', color: '#666' }}>
          <Space split="|">
            <span>Nodes: {graphData.nodes.length}</span>
            <span>Links: {graphData.links.length}</span>
            <span>Interactive: Drag nodes, scroll to zoom</span>
          </Space>
        </div>
      </Card>
    </div>
  );
};

export default GraphVisualization;