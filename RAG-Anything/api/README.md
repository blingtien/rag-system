# RAG-Anything API Server

智能多模态RAG系统API服务器，支持智能解析器路由和多种文档格式处理。

## 🚀 核心特性

### 智能解析器路由
- **自动格式识别**: 根据文件扩展名和大小自动选择最优解析器
- **直接文本处理**: TXT/MD文件无需PDF转换，直接解析
- **智能备用方案**: 解析器不可用时自动降级到备用方案
- **性能优化**: 根据文件大小和类型选择最适合的解析策略

### 支持的文件格式

| 格式类别 | 文件扩展名 | 解析器 | 处理方式 |
|---------|------------|--------|----------|
| **文本文件** | .txt, .md | direct_text | 直接解析，避免PDF转换 |
| **PDF文档** | .pdf | mineru | 专业PDF解析引擎 |
| **Office文档** | .doc, .docx, .ppt, .pptx, .xls, .xlsx | docling | 直接解析，无需LibreOffice |
| **图片文件** | .jpg, .jpeg, .png, .bmp, .tiff, .gif, .webp | mineru | OCR识别和分析 |
| **HTML文件** | .html, .htm, .xhtml | docling | 原生HTML解析 |

### 解析器选择策略

#### 专业分工策略
- **PDF文档**: 统一使用MinerU，专为PDF优化的解析引擎
- **Office文档**: 统一使用Docling，原生Office文档支持
- **文本文件**: 使用DirectTextProcessor，支持UTF-8/GBK等多种编码
- **图片文件**: 使用MinerU的OCR能力
- **HTML文件**: 使用Docling原生HTML解析
- **未知格式**: 降级到MinerU通用解析

## 📋 API端点

### 核心功能
- `POST /api/v1/documents/upload` - 文档上传和处理
- `POST /api/v1/query` - 智能查询
- `GET /api/v1/documents` - 文档列表
- `GET /api/v1/tasks` - 任务状态查询
- `WebSocket /ws/task/{task_id}` - 实时处理进度

### 系统监控
- `GET /health` - 健康检查
- `GET /api/system/status` - 系统状态
- `GET /api/system/parser-stats` - 解析器使用统计

## 🔧 配置

### 环境变量

```bash
# 核心设置
WORKING_DIR=./rag_storage           # RAG数据存储目录
OUTPUT_DIR=./output                 # 解析输出目录
PARSER=mineru                       # 默认解析器 (mineru/docling)
PARSE_METHOD=auto                   # 解析方法 (auto/ocr/txt)

# API配置
DEEPSEEK_API_KEY=your_api_key       # DeepSeek API密钥
LLM_BINDING_HOST=https://api.deepseek.com/v1  # LLM API地址

# 多模态处理
ENABLE_IMAGE_PROCESSING=true        # 启用图片处理
ENABLE_TABLE_PROCESSING=true        # 启用表格处理
ENABLE_EQUATION_PROCESSING=true     # 启用公式处理
```

## 🚀 快速开始

### 启动服务器

```bash
cd /path/to/RAG-Anything/api
python rag_api_server.py
```

### 上传文档

```bash
curl -X POST "http://127.0.0.1:8001/api/v1/documents/upload" \
     -F "file=@example.txt"
```

### 查询文档

```bash
curl -X POST "http://127.0.0.1:8001/api/v1/query" \
     -H "Content-Type: application/json" \
     -d '{"query": "文档内容总结", "mode": "hybrid"}'
```

### 查看解析器统计

```bash
curl "http://127.0.0.1:8001/api/system/parser-stats"
```

## 📊 智能路由示例

### 文本文件路由
```json
{
  "file": "document.txt",
  "size": "2KB", 
  "router_decision": {
    "parser": "direct_text",
    "method": "direct",
    "category": "text",
    "reason": "文本文件直接解析，避免PDF转换"
  }
}
```

### Office文档路由
```json
{
  "file": "presentation.pptx",
  "size": "15MB",
  "router_decision": {
    "parser": "docling", 
    "method": "auto",
    "category": "office",
    "reason": "Office文档(.pptx)统一使用Docling直接解析，无需LibreOffice转换"
  }
}
```

### PDF文档路由
```json
{
  "file": "large_report.pdf",
  "size": "80MB",
  "router_decision": {
    "parser": "mineru",
    "method": "auto", 
    "category": "pdf",
    "reason": "PDF文件统一使用MinerU专业PDF解析引擎"
  }
}
```

## 🧪 测试

运行智能路由测试：

```bash
cd api
python test_smart_routing.py
```

测试覆盖：
- ✅ 智能路由逻辑
- ✅ 解析器可用性检查
- ✅ 备用方案逻辑
- ✅ 直接文本处理
- ✅ 统计信息收集

## 📈 性能优化

### 避免的转换操作
1. **TXT文件**: 避免ReportLab PDF转换
2. **Office文档**: 避免LibreOffice PDF转换  
3. **Markdown文件**: 直接解析，保持结构化信息

### 解析器优势利用
1. **MinerU**: OCR能力强，适合图片和小PDF
2. **Docling**: 大文件处理优秀，Office原生支持
3. **DirectText**: 编码检测，结构化Markdown解析

### 统计指标
- **转换避免率**: 直接处理文本文件的比例
- **解析器使用分布**: 不同解析器的使用情况
- **处理效率**: 平均处理时间和成功率

## 🔍 监控和诊断

### 解析器统计API响应
```json
{
  "success": true,
  "timestamp": "2025-01-17T15:30:00",
  "routing_statistics": {
    "total_files_routed": 150,
    "parser_usage": {
      "direct_text": 45,
      "mineru": 65, 
      "docling": 40
    },
    "category_distribution": {
      "text": 45,
      "pdf": 50,
      "office": 35,
      "image": 20
    },
    "efficiency_metrics": {
      "direct_text_processing": 45,
      "avoided_conversions": 45,
      "conversion_rate": 30.0
    }
  },
  "parser_availability": {
    "mineru": true,
    "docling": true,
    "direct_text": true
  },
  "optimization_summary": {
    "total_optimizations": 85,
    "pdf_conversions_avoided": 45,
    "libreoffice_conversions_avoided": 35
  }
}
```

## 🛠️ 故障排除

### 常见问题

1. **解析器不可用**
   - 检查MinerU/Docling安装
   - 查看`/api/system/parser-stats`确认可用性
   - 自动降级到备用解析器

2. **文本编码问题**
   - 支持UTF-8、GBK、GB2312等编码
   - 自动检测和转换
   - 错误时使用忽略模式

3. **大文件处理**
   - 自动选择适合的解析器
   - Docling处理>50MB文件
   - 监控内存使用情况

### 日志级别
- **INFO**: 路由决策和处理进度
- **WARNING**: 解析器降级和编码问题
- **ERROR**: 处理失败和系统错误

## 📝 更新日志

### v1.0.0 (2025-01-17)
- ✨ 新增智能解析器路由系统
- ✨ 新增直接文本文件处理
- ✨ 新增解析器使用统计
- 🚀 优化Office文档处理（避免LibreOffice）
- 🚀 优化文本文件处理（避免PDF转换）
- 📊 新增实时统计和监控端点
- 🧪 完整的测试覆盖