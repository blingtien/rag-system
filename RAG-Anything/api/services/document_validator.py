"""
文档验证服务
职责：验证文档状态、文件存在性、任务有效性
"""
import os
import logging
from typing import List, Tuple, Dict, Any
from models.batch_models import DocumentInfo, DocumentStatus, BatchResult

logger = logging.getLogger(__name__)


class DocumentValidationError(Exception):
    """文档验证错误"""
    pass


class DocumentValidator:
    """文档验证器
    
    单一职责：验证批量处理前的文档状态和可用性
    """
    
    def __init__(self, documents_store: Dict[str, Any], tasks_store: Dict[str, Any]):
        """
        初始化验证器
        
        Args:
            documents_store: 文档存储字典
            tasks_store: 任务存储字典
        """
        self.documents = documents_store
        self.tasks = tasks_store
    
    def validate_batch_documents(self, document_ids: List[str]) -> Tuple[List[DocumentInfo], List[BatchResult]]:
        """
        验证批量文档
        
        Args:
            document_ids: 要验证的文档ID列表
            
        Returns:
            Tuple[valid_documents, failed_results]
            - valid_documents: 验证通过的文档信息列表
            - failed_results: 验证失败的结果列表
        """
        if not document_ids:
            raise DocumentValidationError("文档ID列表不能为空")
        
        valid_documents = []
        failed_results = []
        
        logger.info(f"开始验证 {len(document_ids)} 个文档")
        
        for document_id in document_ids:
            try:
                # 验证单个文档
                doc_info, error_result = self._validate_single_document(document_id)
                
                if doc_info:
                    valid_documents.append(doc_info)
                    logger.debug(f"文档验证成功: {document_id} - {doc_info.file_name}")
                else:
                    failed_results.append(error_result)
                    logger.warning(f"文档验证失败: {document_id} - {error_result.message}")
                    
            except Exception as e:
                logger.error(f"验证文档 {document_id} 时发生异常: {str(e)}")
                failed_results.append(BatchResult(
                    document_id=document_id,
                    file_name="unknown",
                    status="failed", 
                    message=f"验证过程中发生错误: {str(e)}",
                    task_id=None
                ))
        
        logger.info(f"文档验证完成: {len(valid_documents)} 个有效, {len(failed_results)} 个无效")
        return valid_documents, failed_results
    
    def _validate_single_document(self, document_id: str) -> Tuple[DocumentInfo, BatchResult]:
        """
        验证单个文档
        
        Args:
            document_id: 文档ID
            
        Returns:
            Tuple[DocumentInfo or None, BatchResult or None]
            成功时返回(DocumentInfo, None)，失败时返回(None, BatchResult)
        """
        # 1. 检查文档是否存在
        if document_id not in self.documents:
            return None, BatchResult(
                document_id=document_id,
                file_name="unknown",
                status="failed",
                message="文档不存在",
                task_id=None
            )
        
        document_data = self.documents[document_id]
        file_name = document_data.get("file_name", "unknown")
        
        # 2. 检查文档状态
        current_status = document_data.get("status", "unknown")
        if current_status != "uploaded":
            return None, BatchResult(
                document_id=document_id,
                file_name=file_name,
                status="failed", 
                message=f"文档状态不允许处理: {current_status}",
                task_id=document_data.get("task_id")
            )
        
        # 3. 检查任务是否存在
        task_id = document_data.get("task_id")
        if not task_id or task_id not in self.tasks:
            return None, BatchResult(
                document_id=document_id,
                file_name=file_name,
                status="failed",
                message="处理任务不存在",
                task_id=task_id
            )
        
        # 4. 验证文件路径存在
        file_path = document_data.get("file_path", "")
        if not file_path or not os.path.exists(file_path):
            return None, BatchResult(
                document_id=document_id,
                file_name=file_name, 
                status="failed",
                message=f"文件不存在: {file_path}",
                task_id=task_id
            )
        
        # 5. 检查文件大小
        try:
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return None, BatchResult(
                    document_id=document_id,
                    file_name=file_name,
                    status="failed",
                    message="文件为空",
                    task_id=task_id
                )
        except OSError as e:
            return None, BatchResult(
                document_id=document_id,
                file_name=file_name,
                status="failed", 
                message=f"无法读取文件: {str(e)}",
                task_id=task_id
            )
        
        # 6. 创建验证通过的文档信息
        doc_info = DocumentInfo(
            document_id=document_id,
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            status=DocumentStatus.UPLOADED,
            task_id=task_id
        )
        
        return doc_info, None
    
    def get_validation_summary(self, valid_docs: List[DocumentInfo], failed_results: List[BatchResult]) -> str:
        """
        获取验证结果摘要
        
        Args:
            valid_docs: 有效文档列表
            failed_results: 失败结果列表
            
        Returns:
            验证结果摘要字符串
        """
        total = len(valid_docs) + len(failed_results)
        if total == 0:
            return "没有文档需要验证"
        
        success_rate = (len(valid_docs) / total) * 100
        
        summary = f"文档验证结果: {len(valid_docs)}/{total} 通过 ({success_rate:.1f}%)"
        
        if failed_results:
            # 统计失败原因
            failure_reasons = {}
            for result in failed_results:
                reason = result.message.split(':')[0]  # 提取主要错误类型
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            
            summary += "\n失败原因分布: " + ", ".join([f"{reason}({count}个)" for reason, count in failure_reasons.items()])
        
        return summary