# 前端日志系统集成指南

## 问题解决方案

✅ **重复日志问题已解决**：移除了双重发送机制，现在只通过智能日志处理器发送  
✅ **日志过滤已实现**：智能分类和去重系统  
✅ **新增API端点**：提供多种日志展示模式

## 新增API端点

### 1. 日志摘要API
```
GET /api/v1/logs/summary?mode=summary&include_debug=false
```

**返回结构**：
```json
{
  "success": true,
  "data": {
    "summary": {
      "stats": {
        "total_logs": 6,
        "error_count": 0,
        "warning_count": 1,
        "milestone_count": 0
      },
      "latest_milestone": null,
      "processing_active": true
    },
    "categories": {
      "core_progress": [...],
      "stage_detail": [...],
      "error_warning": [...],
      "performance": [...]
    },
    "timeline": [...]
  }
}
```

### 2. 核心日志API
```
GET /api/v1/logs/core
```
只返回核心进度和错误信息，适合简洁显示。

### 3. 清空日志API
```
POST /api/v1/logs/clear
```

## 前端集成建议

### 1. 分层显示模式
```javascript
// 日志显示模式
const LOG_MODES = {
  CORE_ONLY: 'core_only',      // 仅核心进度和错误
  SUMMARY: 'summary',           // 核心 + 重要阶段信息
  DETAILED: 'detailed',         // 除调试外的所有信息
  ALL: 'all'                    // 完整信息
};

// 使用示例
const fetchLogs = async (mode = LOG_MODES.SUMMARY) => {
  const response = await fetch(`/api/v1/logs/summary?mode=${mode}`);
  return response.json();
};
```

### 2. 日志分类展示
```javascript
// 日志分类颜色方案
const LOG_CATEGORY_STYLES = {
  core_progress: { color: '#22c55e', icon: '🎯' },
  stage_detail: { color: '#3b82f6', icon: '📊' },
  error_warning: { color: '#ef4444', icon: '⚠️' },
  performance: { color: '#8b5cf6', icon: '⚡' },
  cache_operation: { color: '#6b7280', icon: '💾' }
};
```

### 3. 折叠分组显示
```javascript
// 分组展示组件
const LogGroupComponent = ({ groupId, logs, collapsed = true }) => {
  const [isCollapsed, setIsCollapsed] = useState(collapsed);
  
  return (
    <div className="log-group">
      <div 
        className="group-header"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <span>{groupId}</span>
        <span className="log-count">({logs.length})</span>
        <span className="collapse-icon">
          {isCollapsed ? '▶️' : '▼️'}
        </span>
      </div>
      {!isCollapsed && (
        <div className="group-content">
          {logs.map(log => <LogItem key={log.id} log={log} />)}
        </div>
      )}
    </div>
  );
};
```

### 4. 进度可视化
```javascript
// 进度显示组件
const ProgressLogItem = ({ log }) => {
  return (
    <div className="log-item">
      <div className="log-header">
        <span className="log-title">{log.title}</span>
        {log.progress && (
          <div className="progress-bar">
            <div 
              className="progress-fill"
              style={{ width: `${log.progress}%` }}
            />
            <span className="progress-text">{log.progress.toFixed(1)}%</span>
          </div>
        )}
      </div>
      {log.details && (
        <div className="log-details">{log.details}</div>
      )}
    </div>
  );
};
```

### 5. 里程碑高亮
```javascript
// 里程碑日志特殊显示
const MilestoneLogItem = ({ log }) => {
  return (
    <div className={`log-item ${log.is_milestone ? 'milestone' : ''}`}>
      <div className="milestone-badge">🏆</div>
      <div className="milestone-content">
        <div className="milestone-title">{log.title}</div>
        <div className="milestone-time">
          {new Date(log.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
};
```

### 6. 实时日志更新
```javascript
// WebSocket + API混合模式
const useLogManager = () => {
  const [logs, setLogs] = useState([]);
  const [displayMode, setDisplayMode] = useState(LOG_MODES.SUMMARY);
  
  // WebSocket实时接收
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8001/api/v1/documents/progress');
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'log') {
        // 实时日志已经过滤，直接添加
        setLogs(prev => [...prev, data]);
      }
    };
    
    return () => ws.close();
  }, []);
  
  // 定期获取摘要（防止丢失）
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const summary = await fetchLogs(displayMode);
        // 合并或替换日志
        setLogs(summary.data.timeline);
      } catch (error) {
        console.error('获取日志摘要失败:', error);
      }
    }, 10000); // 每10秒获取一次摘要
    
    return () => clearInterval(interval);
  }, [displayMode]);
};
```

## 推荐的UI布局

### 简洁模式（默认）
```
┌─────────────────────────────────────┐
│ 📄 正在处理: test_log.txt            │
│ ✅ 解析完成 (164 blocks)            │
│ 🔍 提取阶段 ████████████ 100%      │
│ 🕸️ 知识图谱构建中...               │
└─────────────────────────────────────┘
```

### 详细模式（可展开）
```
┌─────────────────────────────────────┐
│ 📊 阶段详情 (5 logs) ▼              │
│   ├─ Chunk 1/7 extracted 19 Ent    │
│   ├─ Chunk 2/7 extracted 23 Ent    │
│   └─ ...                           │
│                                     │
│ ⚡ 性能信息 (2 logs) ▶              │
│ 💾 缓存操作 (15 logs) ▶            │
└─────────────────────────────────────┘
```

## 使用示例

### 获取不同级别的日志
```bash
# 仅核心信息
curl http://localhost:8001/api/v1/logs/core

# 摘要信息（推荐用于前端默认显示）
curl "http://localhost:8001/api/v1/logs/summary?mode=summary"

# 详细信息（用于调试模式）
curl "http://localhost:8001/api/v1/logs/summary?mode=detailed"

# 完整信息（用于开发调试）
curl "http://localhost:8001/api/v1/logs/summary?mode=all&include_debug=true"
```

## 优化效果

✅ **去重效果**：相同日志在5秒窗口内自动去重  
✅ **分类效果**：按核心进度、阶段详情、性能、错误分类  
✅ **过滤效果**：缓存操作等细节信息被归类，不干扰主流程  
✅ **进度提取**：自动提取Chunk进度、Stage进度等关键指标  
✅ **里程碑标记**：重要节点自动标记为里程碑  

## 下一步建议

1. **前端实现**：根据本指南更新前端日志显示组件
2. **用户偏好**：添加用户可选的日志详细级别设置
3. **历史记录**：考虑添加日志历史查询功能
4. **导出功能**：为调试提供日志导出功能