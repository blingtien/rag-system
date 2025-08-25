"""
批量处理 V2 API
使用新的架构重构的批量处理端点，解决cache_metrics等问题
"""
import os
import sys
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

# 添加路径以便导入自定义模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.batch_models import BatchContext, CacheMetrics, BatchOperation
from services.batch_coordinator import BatchProcessingCoordinator

logger = logging.getLogger(__name__)


class BatchProcessingV2:
    """
    批量处理 V2 实现
    
    使用新的架构解决原有的问题：
    1. 变量未初始化错误
    2. 职责过于集中
    3. 错误处理不统一
    4. 状态管理混乱
    """
    
    def __init__(
        self,
        documents_store: Dict[str, Any],
        tasks_store: Dict[str, Any],
        batch_operations: Dict[str, Any],
        cache_enhanced_processor: Any,
        log_callback: Optional[Any] = None
    ):
        """
        初始化 V2 批量处理器
        
        Args:
            documents_store: 文档存储
            tasks_store: 任务存储  
            batch_operations: 批量操作存储
            cache_enhanced_processor: 缓存增强处理器
            log_callback: 日志回调函数
        """
        self.coordinator = BatchProcessingCoordinator(
            documents_store=documents_store,
            tasks_store=tasks_store,
            batch_operations=batch_operations,
            cache_enhanced_processor=cache_enhanced_processor,
            log_callback=log_callback
        )
        self.batch_operations = batch_operations
    
    async def process_documents_batch_v2(
        self,
        document_ids: List[str],
        parser: str = "mineru",
        parse_method: str = "auto",
        max_workers: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        V2 批量处理端点
        
        主要改进：
        1. 所有变量都有默认初始化
        2. 职责清晰分离
        3. 统一的错误处理
        4. 类型安全的数据结构
        
        Args:
            document_ids: 文档ID列表
            parser: 解析器类型
            parse_method: 解析方法
            max_workers: 最大工作线程数
            
        Returns:
            批量处理响应数据
        """
        if not document_ids:
            return {
                "success": False,
                "started_count": 0,
                "failed_count": 0,
                "total_requested": 0,
                "results": [],
                "batch_operation_id": None,
                "message": "文档ID列表不能为空",
                "cache_performance": CacheMetrics().to_dict()
            }
        
        # 创建批量操作跟踪
        batch_operation_id = str(uuid.uuid4())
        batch_operation = BatchOperation(
            batch_operation_id=batch_operation_id,
            operation_type="process",
            total_items=len(document_ids),
            started_at=datetime.now().isoformat()
        )
        self.batch_operations[batch_operation_id] = batch_operation.to_dict()
        
        try:
            # 使用协调器执行批量处理
            context = await self.coordinator.process_batch(
                document_ids=document_ids,
                parser=parser,
                parse_method=parse_method,
                max_workers=max_workers
            )
            
            # 更新批量操作状态
            batch_op_dict = self.batch_operations[batch_operation_id]
            batch_op_dict.update({
                "status": "completed" if context.counters.failed == 0 else "failed",
                "completed_items": context.counters.completed,
                "failed_items": context.counters.failed,
                "progress": 100.0,
                "completed_at": datetime.now().isoformat(),
                "results": [result.__dict__ for result in context.results]
            })
            
            # 生成响应
            return context.to_response_dict()
            
        except Exception as e:
            logger.error(f"V2批量处理失败: {str(e)}")
            
            # 更新批量操作为失败状态
            batch_op_dict = self.batch_operations[batch_operation_id]
            batch_op_dict.update({
                "status": "failed",
                "failed_items": len(document_ids),
                "progress": 100.0,
                "completed_at": datetime.now().isoformat(),
                "error": f"批量处理失败: {str(e)}"
            })
            
            # 返回错误响应，确保所有字段都存在
            return {
                "success": False,
                "started_count": 0,
                "failed_count": len(document_ids),
                "total_requested": len(document_ids),
                "results": [],
                "batch_operation_id": batch_operation_id,
                "message": f"批量处理失败: {str(e)}",
                "cache_performance": CacheMetrics().to_dict(),  # 始终有默认值
                "error_details": {
                    "error_type": "processing_error",
                    "error_message": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            }
    
    def get_batch_status(self, batch_operation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取批量操作状态
        
        Args:
            batch_operation_id: 批量操作ID
            
        Returns:
            批量操作状态数据
        """
        return self.batch_operations.get(batch_operation_id)
    
    def list_batch_operations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        列出批量操作
        
        Args:
            limit: 返回数量限制
            
        Returns:
            批量操作列表
        """
        operations = list(self.batch_operations.values())
        # 按开始时间倒序排列
        operations.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        return operations[:limit]


# 工厂函数，用于创建V2处理器实例
def create_batch_processor_v2(
    documents_store: Dict[str, Any],
    tasks_store: Dict[str, Any], 
    batch_operations: Dict[str, Any],
    cache_enhanced_processor: Any,
    log_callback: Optional[Any] = None
) -> BatchProcessingV2:
    """
    创建V2批量处理器实例
    
    这个工厂函数可以在现有的API服务器中调用，
    逐步迁移到新的架构
    
    Args:
        documents_store: 文档存储
        tasks_store: 任务存储
        batch_operations: 批量操作存储
        cache_enhanced_processor: 缓存增强处理器
        log_callback: 日志回调函数
        
    Returns:
        BatchProcessingV2: V2处理器实例
    """
    return BatchProcessingV2(
        documents_store=documents_store,
        tasks_store=tasks_store,
        batch_operations=batch_operations,
        cache_enhanced_processor=cache_enhanced_processor,
        log_callback=log_callback
    )