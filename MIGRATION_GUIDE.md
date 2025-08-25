# 批量处理重构迁移指南

## 概述

本指南说明如何安全地将现有的批量处理代码迁移到新的架构，解决cache_metrics初始化问题和其他架构缺陷。

## 迁移步骤

### 第一步：集成新的批处理协调器（立即可用）

1. **导入新模块**

在 `rag_api_server.py` 中添加导入：

```python
# 在文件顶部的导入部分添加
from batch_processing_refactor import (
    BatchProcessingCoordinator,
    BatchContext,
    CacheMetrics,
    ProcessingState
)
```

2. **创建协调器实例**

在 `initialize_rag()` 函数后添加：

```python
# 全局批处理协调器
batch_coordinator: Optional[BatchProcessingCoordinator] = None

async def initialize_batch_coordinator():
    """初始化批处理协调器"""
    global batch_coordinator, cache_enhanced_processor
    
    if batch_coordinator is not None:
        return batch_coordinator
    
    # 确保RAG和缓存处理器已初始化
    await initialize_rag()
    
    # 创建批处理协调器
    batch_coordinator = BatchProcessingCoordinator(
        documents_store=documents,
        tasks_store=tasks,
        rag_instance=rag_instance,
        cache_processor=cache_enhanced_processor
    )
    
    logger.info("批处理协调器初始化成功")
    return batch_coordinator
```

3. **更新startup事件**

```python
@app.on_event("startup")
async def startup_event():
    """服务启动时初始化"""
    logger.info("=== 服务器启动初始化开始 ===")
    
    # 现有初始化代码...
    
    # 添加批处理协调器初始化
    logger.info("初始化批处理协调器...")
    await initialize_batch_coordinator()
    
    logger.info("=== 服务器启动完成 ===")
```

### 第二步：替换批量处理端点（安全迁移）

创建新的端点，与原有端点并存，便于A/B测试：

```python
@app.post("/api/v2/documents/process/batch")
async def process_documents_batch_v2(request: BatchProcessRequest):
    """
    改进的批量处理端点 - 使用新架构
    解决了cache_metrics初始化问题
    """
    batch_operation_id = str(uuid.uuid4())
    
    # 确保协调器已初始化
    if not batch_coordinator:
        await initialize_batch_coordinator()
    
    logger.info(f"🚀 [V2] 开始批量处理 {len(request.document_ids)} 个文档")
    
    try:
        # 使用新的协调器处理
        result = await batch_coordinator.process_batch(
            batch_id=batch_operation_id,
            document_ids=request.document_ids,
            options={
                "output_dir": OUTPUT_DIR,
                "parse_method": request.parse_method or "auto",
                "max_workers": int(os.getenv("MAX_CONCURRENT_PROCESSING", "3"))
            }
        )
        
        # 构建响应
        return BatchProcessResponse(
            success=result["success"],
            started_count=result["valid_count"],
            failed_count=result["invalid_count"],
            total_requested=result["total_requested"],
            results=result.get("results", {}).get("results", []),
            batch_operation_id=batch_operation_id,
            message=f"批量处理{'成功' if result['success'] else '失败'}",
            cache_performance=result["cache_performance"]  # 保证始终有值
        )
        
    except Exception as e:
        logger.error(f"V2批量处理失败: {str(e)}")
        
        # 即使出错也返回完整的响应，包含初始化的cache_metrics
        return BatchProcessResponse(
            success=False,
            started_count=0,
            failed_count=len(request.document_ids),
            total_requested=len(request.document_ids),
            results=[],
            batch_operation_id=batch_operation_id,
            message=f"批量处理失败: {str(e)}",
            cache_performance=CacheMetrics().to_dict()  # 始终返回有效的metrics
        )
```

### 第三步：逐步迁移（推荐方式）

1. **并行运行新旧版本**
   - 保持原有的 `/api/v1/documents/process/batch` 端点不变
   - 新增 `/api/v2/documents/process/batch` 端点使用新架构
   - 通过前端配置或功能开关控制使用哪个版本

2. **监控和对比**
   ```python
   # 添加监控中间件
   @app.middleware("http")
   async def monitor_batch_processing(request: Request, call_next):
       if "/process/batch" in request.url.path:
           start_time = time.time()
           response = await call_next(request)
           duration = time.time() - start_time
           
           version = "v2" if "/v2/" in request.url.path else "v1"
           logger.info(f"Batch processing {version} took {duration:.2f}s")
           
           # 记录指标用于对比
           if version == "v2":
               # 记录新版本的性能指标
               pass
       else:
           response = await call_next(request)
       
       return response
   ```

3. **渐进式切换**
   ```python
   # 使用功能开关控制流量
   USE_NEW_BATCH_PROCESSOR = os.getenv("USE_NEW_BATCH_PROCESSOR", "false").lower() == "true"
   
   @app.post("/api/v1/documents/process/batch")
   async def process_documents_batch_adaptive(request: BatchProcessRequest):
       """自适应批量处理端点 - 根据配置选择实现"""
       if USE_NEW_BATCH_PROCESSOR:
           # 转发到新实现
           return await process_documents_batch_v2(request)
       else:
           # 使用原有实现
           return await process_documents_batch(request)
   ```

### 第四步：验证和测试

1. **单元测试**

创建测试文件 `test_batch_processing_refactor.py`：

```python
import pytest
from batch_processing_refactor import (
    BatchProcessingCoordinator,
    CacheMetrics,
    BatchContext,
    ProcessingState
)

@pytest.mark.asyncio
async def test_cache_metrics_always_initialized():
    """验证cache_metrics始终被初始化"""
    # 准备
    coordinator = BatchProcessingCoordinator({}, {})
    
    # 执行 - 空文档列表
    result = await coordinator.process_batch(
        batch_id="test-batch",
        document_ids=[]
    )
    
    # 验证
    assert "cache_performance" in result
    assert result["cache_performance"] is not None
    assert isinstance(result["cache_performance"], dict)
    assert "cache_hits" in result["cache_performance"]
    assert "cache_misses" in result["cache_performance"]

@pytest.mark.asyncio
async def test_error_preserves_cache_metrics():
    """验证错误情况下cache_metrics仍然存在"""
    # 准备 - 无效的文档ID
    coordinator = BatchProcessingCoordinator({}, {})
    
    # 执行
    result = await coordinator.process_batch(
        batch_id="test-batch",
        document_ids=["non-existent-doc"]
    )
    
    # 验证
    assert not result["success"]
    assert "cache_performance" in result
    assert result["cache_performance"] is not None
```

2. **集成测试**

```python
# 测试新旧版本的兼容性
async def test_version_compatibility():
    """测试新旧版本API的兼容性"""
    # 准备测试数据
    test_request = {
        "document_ids": ["doc1", "doc2"],
        "parse_method": "auto"
    }
    
    # 测试V1端点
    response_v1 = await client.post("/api/v1/documents/process/batch", json=test_request)
    assert response_v1.status_code == 200
    data_v1 = response_v1.json()
    
    # 测试V2端点
    response_v2 = await client.post("/api/v2/documents/process/batch", json=test_request)
    assert response_v2.status_code == 200
    data_v2 = response_v2.json()
    
    # 验证响应结构一致
    assert "cache_performance" in data_v1
    assert "cache_performance" in data_v2
    assert data_v2["cache_performance"] is not None
```

### 第五步：性能监控

添加性能监控以验证改进效果：

```python
# 在 rag_api_server.py 中添加
class BatchProcessingMetrics:
    """批处理性能指标收集"""
    
    def __init__(self):
        self.v1_metrics = []
        self.v2_metrics = []
    
    def record_v1(self, duration: float, success: bool, cache_metrics: dict):
        self.v1_metrics.append({
            "timestamp": datetime.now().isoformat(),
            "duration": duration,
            "success": success,
            "cache_metrics": cache_metrics
        })
    
    def record_v2(self, duration: float, success: bool, cache_metrics: dict):
        self.v2_metrics.append({
            "timestamp": datetime.now().isoformat(),
            "duration": duration,
            "success": success,
            "cache_metrics": cache_metrics
        })
    
    def get_comparison(self):
        """获取性能对比"""
        return {
            "v1": {
                "avg_duration": sum(m["duration"] for m in self.v1_metrics) / len(self.v1_metrics) if self.v1_metrics else 0,
                "success_rate": sum(1 for m in self.v1_metrics if m["success"]) / len(self.v1_metrics) if self.v1_metrics else 0,
                "total_processed": len(self.v1_metrics)
            },
            "v2": {
                "avg_duration": sum(m["duration"] for m in self.v2_metrics) / len(self.v2_metrics) if self.v2_metrics else 0,
                "success_rate": sum(1 for m in self.v2_metrics if m["success"]) / len(self.v2_metrics) if self.v2_metrics else 0,
                "total_processed": len(self.v2_metrics)
            }
        }

# 创建全局指标收集器
batch_metrics = BatchProcessingMetrics()
```

### 第六步：回滚计划

如果新版本出现问题，可以快速回滚：

1. **环境变量控制**
   ```bash
   # 切换到新版本
   export USE_NEW_BATCH_PROCESSOR=true
   
   # 回滚到旧版本
   export USE_NEW_BATCH_PROCESSOR=false
   ```

2. **热切换支持**
   ```python
   @app.post("/api/admin/batch-processor/switch")
   async def switch_batch_processor(use_new: bool):
       """运行时切换批处理器版本"""
       global USE_NEW_BATCH_PROCESSOR
       USE_NEW_BATCH_PROCESSOR = use_new
       
       return {
           "success": True,
           "message": f"已切换到{'新' if use_new else '旧'}版批处理器",
           "current_version": "v2" if use_new else "v1"
       }
   ```

## 验证检查清单

迁移完成后，请验证以下项目：

- [ ] cache_metrics在所有情况下都被正确初始化
- [ ] 错误处理不会导致UnboundLocalError
- [ ] 批量处理性能与原版本相当或更好
- [ ] 所有现有API响应格式保持兼容
- [ ] 日志记录正常工作
- [ ] WebSocket通知正常发送
- [ ] 缓存统计正确记录和报告
- [ ] 可以在新旧版本间无缝切换

## 问题排查

### 问题1：cache_metrics仍然未定义

**检查点：**
1. 确认使用了新的BatchProcessingCoordinator
2. 验证CacheMetrics类被正确导入
3. 检查是否有其他地方直接访问cache_metrics变量

**解决方案：**
```python
# 始终使用CacheMetrics类
cache_metrics = CacheMetrics()  # 而不是 cache_metrics = {}
```

### 问题2：性能下降

**检查点：**
1. 检查是否正确配置了并发数
2. 验证缓存是否正常工作
3. 查看是否有额外的同步操作

**解决方案：**
调整MAX_CONCURRENT_PROCESSING环境变量

### 问题3：API响应格式不兼容

**检查点：**
1. 对比新旧响应结构
2. 检查前端是否依赖特定字段

**解决方案：**
使用适配器模式转换响应格式

## 总结

通过这个渐进式迁移方案，可以：

1. **立即解决**cache_metrics初始化问题
2. **逐步改善**代码架构质量
3. **保持系统**稳定运行
4. **提供回滚**能力以应对意外情况

建议按照迁移步骤逐步实施，并在每个阶段进行充分测试。