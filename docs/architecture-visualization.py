#!/usr/bin/env python3
"""
RAG System Architecture Visualization Generator
生成项目架构的可视化图表
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ConnectionPatch
import numpy as np

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def create_architecture_diagram():
    """创建系统架构图"""
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 12)
    ax.axis('off')
    
    # 定义颜色方案
    colors = {
        'frontend': '#3498db',      # 蓝色
        'api': '#e74c3c',          # 红色  
        'core': '#f39c12',         # 橙色
        'storage': '#27ae60',      # 绿色
        'external': '#9b59b6',     # 紫色
        'connection': '#34495e',   # 深灰色
    }
    
    # 标题
    ax.text(8, 11.5, 'RAG System 架构图', ha='center', va='center', 
            fontsize=20, fontweight='bold')
    
    # 前端层
    frontend_box = FancyBboxPatch((1, 9), 6, 1.5, 
                                  boxstyle="round,pad=0.1", 
                                  facecolor=colors['frontend'], 
                                  alpha=0.8, edgecolor='black')
    ax.add_patch(frontend_box)
    ax.text(4, 9.75, 'Web UI (React)\n• 文档管理 • 查询界面 • 图谱可视化', 
            ha='center', va='center', fontsize=10, color='white', fontweight='bold')
    
    # API网关层
    api_box = FancyBboxPatch((9, 9), 6, 1.5,
                             boxstyle="round,pad=0.1",
                             facecolor=colors['api'],
                             alpha=0.8, edgecolor='black')
    ax.add_patch(api_box)
    ax.text(12, 9.75, 'API Gateway (FastAPI)\n• RESTful API • WebSocket • 认证授权',
            ha='center', va='center', fontsize=10, color='white', fontweight='bold')
    
    # 核心业务层
    core_boxes = [
        {'pos': (1, 6.5), 'size': (3.5, 1.5), 'text': '智能路由\n• 文档分类\n• 解析器选择\n• 质量控制'},
        {'pos': (5.5, 6.5), 'size': (3.5, 1.5), 'text': '文档处理\n• 多模态解析\n• 内容提取\n• 批量处理'},
        {'pos': (10, 6.5), 'size': (2.5, 1.5), 'text': '知识图谱\n• 实体抽取\n• 关系构建'},
        {'pos': (13.5, 6.5), 'size': (2, 1.5), 'text': '查询引擎\n• 语义检索\n• 图谱推理'},
    ]
    
    for box_info in core_boxes:
        box = FancyBboxPatch(box_info['pos'], box_info['size'][0], box_info['size'][1],
                             boxstyle="round,pad=0.1",
                             facecolor=colors['core'],
                             alpha=0.8, edgecolor='black')
        ax.add_patch(box)
        center_x = box_info['pos'][0] + box_info['size'][0] / 2
        center_y = box_info['pos'][1] + box_info['size'][1] / 2
        ax.text(center_x, center_y, box_info['text'],
                ha='center', va='center', fontsize=9, color='white', fontweight='bold')
    
    # 存储层
    storage_boxes = [
        {'pos': (1, 3.5), 'size': (3, 1.5), 'text': 'PostgreSQL\n• 文档状态\n• KV存储\n• 向量索引'},
        {'pos': (5, 3.5), 'size': (3, 1.5), 'text': 'Neo4j\n• 实体节点\n• 关系图谱\n• 语义查询'},
        {'pos': (9, 3.5), 'size': (3, 1.5), 'text': 'GraphML\n• Chunk关联\n• 本地图存储\n• 快速访问'},
        {'pos': (13, 3.5), 'size': (2.5, 1.5), 'text': 'Redis\n• 缓存层\n• 会话管理'},
    ]
    
    for box_info in storage_boxes:
        box = FancyBboxPatch(box_info['pos'], box_info['size'][0], box_info['size'][1],
                             boxstyle="round,pad=0.1",
                             facecolor=colors['storage'],
                             alpha=0.8, edgecolor='black')
        ax.add_patch(box)
        center_x = box_info['pos'][0] + box_info['size'][0] / 2
        center_y = box_info['pos'][1] + box_info['size'][1] / 2
        ax.text(center_x, center_y, box_info['text'],
                ha='center', va='center', fontsize=9, color='white', fontweight='bold')
    
    # 外部服务
    external_boxes = [
        {'pos': (1, 1), 'size': (3, 1.5), 'text': 'LLM服务\n• DeepSeek API\n• 文本生成\n• 语义理解'},
        {'pos': (5, 1), 'size': (3, 1.5), 'text': '嵌入模型\n• Qwen3-Embedding\n• 本地部署\n• 向量化'},
        {'pos': (9, 1), 'size': (3, 1.5), 'text': '解析引擎\n• MinerU (PDF)\n• Docling\n• 多模态支持'},
        {'pos': (13, 1), 'size': (2.5, 1.5), 'text': '监控日志\n• 性能监控\n• 错误追踪'},
    ]
    
    for box_info in external_boxes:
        box = FancyBboxPatch(box_info['pos'], box_info['size'][0], box_info['size'][1],
                             boxstyle="round,pad=0.1",
                             facecolor=colors['external'],
                             alpha=0.8, edgecolor='black')
        ax.add_patch(box)
        center_x = box_info['pos'][0] + box_info['size'][0] / 2
        center_y = box_info['pos'][1] + box_info['size'][1] / 2
        ax.text(center_x, center_y, box_info['text'],
                ha='center', va='center', fontsize=9, color='white', fontweight='bold')
    
    # 绘制连接线
    connections = [
        # 前端到API
        ((4, 9), (12, 9)),
        # API到核心组件
        ((12, 8.5), (2.75, 8)),
        ((12, 8.5), (7.25, 8)),
        ((12, 8.5), (11.25, 8)),
        ((12, 8.5), (14.5, 8)),
        # 核心组件到存储
        ((2.75, 6.5), (2.5, 5)),
        ((7.25, 6.5), (6.5, 5)),
        ((11.25, 6.5), (10.5, 5)),
        ((14.5, 6.5), (14.25, 5)),
        # 存储到外部服务
        ((2.5, 3.5), (2.5, 2.5)),
        ((6.5, 3.5), (6.5, 2.5)),
        ((10.5, 3.5), (10.5, 2.5)),
        ((14.25, 3.5), (14.25, 2.5)),
    ]
    
    for start, end in connections:
        ax.annotate('', xy=end, xytext=start,
                    arrowprops=dict(arrowstyle='->', lw=1.5, color=colors['connection']))
    
    # 添加图例
    legend_elements = [
        plt.Rectangle((0, 0), 1, 1, facecolor=colors['frontend'], alpha=0.8, label='前端层'),
        plt.Rectangle((0, 0), 1, 1, facecolor=colors['api'], alpha=0.8, label='API层'),
        plt.Rectangle((0, 0), 1, 1, facecolor=colors['core'], alpha=0.8, label='业务层'),
        plt.Rectangle((0, 0), 1, 1, facecolor=colors['storage'], alpha=0.8, label='存储层'),
        plt.Rectangle((0, 0), 1, 1, facecolor=colors['external'], alpha=0.8, label='外部服务'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(0.98, 0.98))
    
    plt.tight_layout()
    return fig

def create_data_flow_diagram():
    """创建数据流程图"""
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # 标题
    ax.text(7, 9.5, 'RAG System 数据流程图', ha='center', va='center', 
            fontsize=18, fontweight='bold')
    
    # 流程步骤
    steps = [
        {'pos': (1, 8), 'text': '文档\n上传', 'color': '#3498db'},
        {'pos': (3.5, 8), 'text': '格式\n识别', 'color': '#e74c3c'},
        {'pos': (6, 8), 'text': '智能\n解析', 'color': '#f39c12'},
        {'pos': (8.5, 8), 'text': '内容\n提取', 'color': '#9b59b6'},
        {'pos': (11, 8), 'text': '结构化\n处理', 'color': '#27ae60'},
        
        {'pos': (1, 6), 'text': '实体\n识别', 'color': '#e67e22'},
        {'pos': (3.5, 6), 'text': '关系\n抽取', 'color': '#2ecc71'},
        {'pos': (6, 6), 'text': '知识\n图谱', 'color': '#8e44ad'},
        {'pos': (8.5, 6), 'text': '向量\n存储', 'color': '#34495e'},
        {'pos': (11, 6), 'text': '索引\n建立', 'color': '#16a085'},
        
        {'pos': (2.25, 4), 'text': '用户\n查询', 'color': '#3498db'},
        {'pos': (5.25, 4), 'text': '语义\n理解', 'color': '#e74c3c'},
        {'pos': (8.25, 4), 'text': '多路\n检索', 'color': '#f39c12'},
        {'pos': (11.25, 4), 'text': '结果\n融合', 'color': '#27ae60'},
        
        {'pos': (4, 2), 'text': '答案\n生成', 'color': '#9b59b6'},
        {'pos': (7, 2), 'text': '质量\n评估', 'color': '#e67e22'},
        {'pos': (10, 2), 'text': '结果\n返回', 'color': '#2ecc71'},
    ]
    
    # 绘制步骤
    for step in steps:
        circle = plt.Circle(step['pos'], 0.6, color=step['color'], alpha=0.8)
        ax.add_patch(circle)
        ax.text(step['pos'][0], step['pos'][1], step['text'], 
                ha='center', va='center', fontsize=9, color='white', fontweight='bold')
    
    # 绘制箭头连接
    flow_connections = [
        # 文档处理流程
        ((1.6, 8), (2.9, 8)),
        ((4.1, 8), (5.4, 8)),
        ((6.6, 8), (7.9, 8)),
        ((9.1, 8), (10.4, 8)),
        ((11, 7.4), (11, 6.6)),
        ((10.4, 6), (9.1, 6)),
        ((7.9, 6), (6.6, 6)),
        ((5.4, 6), (4.1, 6)),
        ((2.9, 6), (1.6, 6)),
        
        # 查询处理流程
        ((2.85, 4), (4.65, 4)),
        ((5.85, 4), (7.65, 4)),
        ((8.85, 4), (10.65, 4)),
        ((10.65, 4), (10, 2.6)),
        ((9.4, 2), (7.6, 2)),
        ((6.4, 2), (4.6, 2)),
        
        # 跨流程连接
        ((1, 6.4), (2.25, 4.6)),  # 实体识别到用户查询
        ((6, 6.4), (8.25, 4.6)),   # 知识图谱到多路检索
    ]
    
    for start, end in flow_connections:
        ax.annotate('', xy=end, xytext=start,
                    arrowprops=dict(arrowstyle='->', lw=2, color='#34495e'))
    
    # 添加流程标签
    ax.text(6, 8.8, '📄 文档处理流程', ha='center', va='center', 
            fontsize=12, fontweight='bold', color='#2c3e50')
    ax.text(6, 6.8, '🧠 知识构建流程', ha='center', va='center', 
            fontsize=12, fontweight='bold', color='#2c3e50')
    ax.text(6.75, 4.8, '🔍 查询处理流程', ha='center', va='center', 
            fontsize=12, fontweight='bold', color='#2c3e50')
    ax.text(7, 2.8, '✨ 结果生成流程', ha='center', va='center', 
            fontsize=12, fontweight='bold', color='#2c3e50')
    
    plt.tight_layout()
    return fig

if __name__ == "__main__":
    print("生成RAG系统架构图...")
    
    # 生成架构图
    arch_fig = create_architecture_diagram()
    arch_fig.savefig('/home/ragsvr/projects/ragsystem/docs/system-architecture.png', 
                     dpi=300, bbox_inches='tight', facecolor='white')
    print("✅ 架构图已保存: docs/system-architecture.png")
    
    # 生成数据流程图
    flow_fig = create_data_flow_diagram()
    flow_fig.savefig('/home/ragsvr/projects/ragsystem/docs/data-flow-diagram.png', 
                     dpi=300, bbox_inches='tight', facecolor='white')
    print("✅ 流程图已保存: docs/data-flow-diagram.png")
    
    print("\n🎉 可视化图表生成完成！")
    print("📁 查看文档目录: /home/ragsvr/projects/ragsystem/docs/")