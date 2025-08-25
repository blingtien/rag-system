"""
DocumentService - 文档管理服务
提供文档生命周期管理的业务逻辑抽象，包括上传、删除、状态管理等操作
"""
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel

from core.state_manager import StateManager, Document
from core.rag_manager import RAGManager
from utils.secure_file_handler import SecureFileHandler
from services.exceptions import ServiceException, ValidationError, ResourceError


class DocumentUploadResult(BaseModel):
    """文档上传结果"""
    success: bool
    document_id: str
    task_id: str
    file_name: str
    file_size: int
    message: str
    status: str


class DocumentDeletionResult(BaseModel):
    """文档删除结果"""
    document_id: str
    file_name: str
    status: str
    message: str
    details: Dict[str, Any]


class BatchUploadResult(BaseModel):
    """批量上传结果"""
    success: bool
    uploaded_count: int
    failed_count: int
    total_files: int
    results: List[Dict[str, Any]]
    message: str


class DocumentDisplayInfo(BaseModel):
    """文档显示信息"""
    document_id: str
    file_name: str
    file_size: int
    uploaded_at: str
    status_code: str
    status_display: str
    action_type: str
    action_icon: str
    action_text: str
    can_process: bool


class DocumentService:
    """
    文档服务 - 负责文档的完整生命周期管理
    
    应用设计模式：
    - Repository Pattern: 通过 StateManager 抽象数据访问
    - Strategy Pattern: 支持不同的文件处理策略
    - Factory Pattern: 创建文档实例和结果对象
    """
    
    def __init__(
        self,
        state_manager: StateManager,
        rag_manager: RAGManager,
        secure_file_handler: SecureFileHandler
    ):
        self.state_manager = state_manager
        self.rag_manager = rag_manager
        self.secure_file_handler = secure_file_handler
    
    async def upload_single_document(
        self,
        file: UploadFile,
        user_id: Optional[str] = None
    ) -> DocumentUploadResult:
        """
        上传单个文档
        
        Args:
            file: 上传的文件
            user_id: 可选的用户ID
            
        Returns:
            DocumentUploadResult: 上传结果
            
        Raises:
            ValidationError: 文件验证失败
            ResourceError: 资源处理失败
            ServiceException: 服务层异常
        """
        try:
            # 安全文件处理
            upload_result = await self.secure_file_handler.handle_upload(file)
            
            # 检查文件名重复
            await self._check_filename_duplicate(upload_result["original_filename"])
            
            # 创建文档记录
            document = await self._create_document_record(
                upload_result["original_filename"],
                upload_result["file_path"],
                upload_result["file_size"]
            )
            
            # 保存到状态管理器
            await self.state_manager.add_document(document)
            
            return DocumentUploadResult(
                success=True,
                document_id=document.document_id,
                task_id=document.task_id,
                file_name=document.file_name,
                file_size=document.file_size,
                message="文档上传成功，准备手动处理",
                status=document.status
            )
            
        except HTTPException:
            # 安全处理器的HTTP异常直接传播
            raise
        except Exception as e:
            # 包装为服务异常
            raise ServiceException(f"文档上传失败: {str(e)}") from e
    
    async def upload_batch_documents(
        self,
        files: List[UploadFile],
        user_id: Optional[str] = None
    ) -> BatchUploadResult:
        """
        批量上传文档
        
        Args:
            files: 上传的文件列表
            user_id: 可选的用户ID
            
        Returns:
            BatchUploadResult: 批量上传结果
        """
        uploaded_count = 0
        failed_count = 0
        results = []
        
        # 获取已存在的文件名集合
        existing_names = await self._get_existing_filenames()
        
        for i, file in enumerate(files):
            file_result = {
                "file_name": file.filename if file.filename else f"unknown_file_{i}",
                "file_size": 0,
                "status": "failed",
                "message": "",
                "task_id": None,
                "document_id": None
            }
            
            try:
                # 单个文件处理
                upload_result = await self.secure_file_handler.handle_upload(file)
                
                # 检查重复
                if upload_result["original_filename"] in existing_names:
                    # 清理已上传的文件
                    await self._cleanup_uploaded_file(upload_result["file_path"])
                    file_result["message"] = "文件名重复，已跳过"
                    failed_count += 1
                    results.append(file_result)
                    continue
                
                # 创建文档记录
                document = await self._create_document_record(
                    upload_result["original_filename"],
                    upload_result["file_path"],
                    upload_result["file_size"]
                )
                
                # 保存文档
                await self.state_manager.add_document(document)
                existing_names.add(upload_result["original_filename"])
                
                # 更新结果
                file_result.update({
                    "file_size": upload_result["file_size"],
                    "status": "success",
                    "message": "上传成功",
                    "task_id": document.task_id,
                    "document_id": document.document_id
                })
                
                uploaded_count += 1
                
            except HTTPException as e:
                file_result["message"] = e.detail
                failed_count += 1
            except Exception as e:
                file_result["message"] = f"上传失败: {str(e)}"
                failed_count += 1
            
            results.append(file_result)
        
        message = f"批量上传完成: {uploaded_count} 个成功, {failed_count} 个失败"
        
        return BatchUploadResult(
            success=failed_count == 0,
            uploaded_count=uploaded_count,
            failed_count=failed_count,
            total_files=len(files),
            results=results,
            message=message
        )
    
    async def delete_documents(
        self,
        document_ids: List[str]
    ) -> Tuple[int, List[DocumentDeletionResult]]:
        """
        删除多个文档
        
        Args:
            document_ids: 要删除的文档ID列表
            
        Returns:
            Tuple[int, List[DocumentDeletionResult]]: 成功删除的数量和删除结果列表
        """
        deletion_results = []
        successful_deletions = 0
        
        # 获取RAG实例（如果可用）
        rag_instance = None
        try:
            rag_instance = await self.rag_manager.get_rag_instance()
        except:
            pass  # RAG不可用时继续执行删除操作
        
        for doc_id in document_ids:
            result = await self._delete_single_document(doc_id, rag_instance)
            deletion_results.append(result)
            
            if result.status == "success":
                successful_deletions += 1
        
        return successful_deletions, deletion_results
    
    async def clear_all_documents(self) -> Dict[str, Any]:
        """
        清空所有文档
        
        Returns:
            Dict[str, Any]: 清空操作的详细结果
        """
        documents = await self.state_manager.get_all_documents()
        count = len(documents)
        
        # 获取RAG实例
        rag_instance = None
        try:
            rag_instance = await self.rag_manager.get_rag_instance()
        except:
            pass
        
        # 清空结果统计
        clear_results = {
            "total_documents": count,
            "files_deleted": 0,
            "rag_deletions": {"success": 0, "failed": 0, "skipped": 0},
            "errors": []
        }
        
        # 删除所有文档
        for document in documents:
            try:
                # RAG系统删除（如果可用）
                if document.rag_doc_id and rag_instance:
                    try:
                        # TODO: 实现RAG删除逻辑
                        # deletion_result = await rag_instance.lightrag.adelete_by_doc_id(document.rag_doc_id)
                        clear_results["rag_deletions"]["skipped"] += 1
                    except Exception as e:
                        clear_results["rag_deletions"]["failed"] += 1
                        clear_results["errors"].append(f"RAG删除失败 {document.file_name}: {str(e)}")
                
                # 删除物理文件
                if os.path.exists(document.file_path):
                    os.remove(document.file_path)
                    clear_results["files_deleted"] += 1
                    
            except Exception as e:
                clear_results["errors"].append(f"删除文档失败 {document.file_name}: {str(e)}")
        
        # 清空状态管理器
        await self.state_manager.clear_documents()
        
        message = f"清空完成: {count}个文档"
        if clear_results["errors"]:
            message += f", {len(clear_results['errors'])}个错误"
        
        return {
            "success": True,
            "message": message,
            "details": clear_results
        }
    
    async def get_document_list(self) -> Dict[str, Any]:
        """
        获取文档列表，包含显示信息和统计数据
        
        Returns:
            Dict[str, Any]: 包含文档列表和统计信息
        """
        documents = await self.state_manager.get_all_documents()
        
        # 转换为显示格式
        enhanced_documents = []
        for doc in documents:
            display_info = self._get_document_display_info(doc)
            enhanced_documents.append(display_info.dict())
        
        # 按上传时间倒序排序
        enhanced_documents.sort(key=lambda x: x["uploaded_at"], reverse=True)
        
        # 统计各状态的文档数量
        status_counts = {
            "uploaded": len([d for d in documents if d.status == "uploaded"]),
            "processing": len([d for d in documents if d.status == "processing"]),
            "completed": len([d for d in documents if d.status == "completed"]),
            "failed": len([d for d in documents if d.status == "failed"])
        }
        
        return {
            "success": True,
            "documents": enhanced_documents,
            "total_count": len(enhanced_documents),
            "status_counts": status_counts
        }
    
    async def trigger_document_processing(self, document_id: str) -> Dict[str, Any]:
        """
        触发文档处理
        
        Args:
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 处理触发结果
            
        Raises:
            ValidationError: 文档状态不允许处理
            ResourceError: 文档不存在或文件缺失
        """
        document = await self.state_manager.get_document(document_id)
        if not document:
            raise ResourceError("文档不存在")
        
        # 检查文档状态
        if document.status != "uploaded":
            raise ValidationError(f"文档无法处理，当前状态: {document.status}")
        
        # 检查任务ID
        if not document.task_id:
            raise ValidationError("处理任务不存在")
        
        # 检查文件存在性
        if not os.path.exists(document.file_path):
            raise ResourceError(f"文件不存在: {document.file_path}")
        
        try:
            # 更新文档状态
            await self.state_manager.update_document_status(document_id, "processing")
            
            # TODO: 在ProcessingService中实现具体处理逻辑
            # 这里只是准备处理，实际处理将由ProcessingService异步执行
            
            return {
                "success": True,
                "message": f"文档处理已启动: {document.file_name}",
                "document_id": document_id,
                "task_id": document.task_id,
                "status": "processing"
            }
            
        except Exception as e:
            raise ServiceException(f"启动处理失败: {str(e)}") from e
    
    # === 私有方法 ===
    
    async def _check_filename_duplicate(self, filename: str) -> None:
        """检查文件名是否重复"""
        existing_docs = await self.state_manager.get_all_documents()
        for doc in existing_docs:
            if doc.file_name == filename:
                raise ValidationError(f"文件名 '{filename}' 已存在，请重命名后再上传")
    
    async def _get_existing_filenames(self) -> set:
        """获取现有文件名集合"""
        documents = await self.state_manager.get_all_documents()
        return {doc.file_name for doc in documents}
    
    async def _create_document_record(
        self,
        filename: str,
        filepath: str,
        filesize: int
    ) -> Document:
        """创建文档记录"""
        task_id = str(uuid.uuid4())
        document_id = str(uuid.uuid4())
        
        return Document(
            document_id=document_id,
            file_name=filename,
            file_path=filepath,
            file_size=filesize,
            status="uploaded",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            task_id=task_id
        )
    
    async def _cleanup_uploaded_file(self, file_path: str) -> None:
        """清理已上传的文件"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception:
            pass  # 忽略清理失败，不影响主流程
    
    async def _delete_single_document(
        self,
        document_id: str,
        rag_instance: Optional[Any]
    ) -> DocumentDeletionResult:
        """删除单个文档"""
        document = await self.state_manager.get_document(document_id)
        
        if not document:
            return DocumentDeletionResult(
                document_id=document_id,
                file_name="unknown",
                status="not_found",
                message="文档不存在",
                details={}
            )
        
        result = DocumentDeletionResult(
            document_id=document_id,
            file_name=document.file_name,
            status="success",
            message="",
            details={}
        )
        
        try:
            # TODO: RAG系统删除（待ProcessingService实现）
            # if document.rag_doc_id and rag_instance:
            #     deletion_result = await rag_instance.lightrag.adelete_by_doc_id(document.rag_doc_id)
            #     result.details["rag_deletion"] = {
            #         "status": deletion_result.status,
            #         "message": deletion_result.message
            #     }
            
            # 删除物理文件
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
                result.details["file_deletion"] = "文件已删除"
            else:
                result.details["file_deletion"] = "文件不存在或已删除"
            
            # 从状态管理器中删除
            await self.state_manager.remove_document(document_id)
            result.message = f"文档 {document.file_name} 已完全删除"
            
        except Exception as e:
            result.status = "error"
            result.message = f"删除文档时发生错误: {str(e)}"
            result.details["error"] = str(e)
        
        return result
    
    def _get_document_display_info(self, doc: Document) -> DocumentDisplayInfo:
        """获取文档显示信息"""
        base_info = DocumentDisplayInfo(
            document_id=doc.document_id,
            file_name=doc.file_name,
            file_size=doc.file_size,
            uploaded_at=doc.created_at,
            status_code=doc.status,
            status_display="",
            action_type="",
            action_icon="",
            action_text="",
            can_process=False
        )
        
        # 根据状态设置显示信息
        if doc.status == "uploaded":
            base_info.status_display = "等待解析"
            base_info.action_type = "start_processing"
            base_info.action_icon = "play"
            base_info.action_text = "开始解析"
            base_info.can_process = True
            
        elif doc.status == "processing":
            base_info.status_display = "解析中..."
            base_info.action_type = "processing"
            base_info.action_icon = "loading"
            base_info.action_text = "处理中"
            base_info.can_process = False
            
        elif doc.status == "completed":
            # 计算完成时间
            time_info = self._calculate_completion_time(doc.updated_at)
            chunks_info = f" ({doc.chunks_count}个文本块)" if doc.chunks_count else ""
            
            base_info.status_display = f"已完成 - {time_info}{chunks_info}"
            base_info.action_type = "completed"
            base_info.action_icon = "check"
            base_info.action_text = "已完成"
            base_info.can_process = False
            
        elif doc.status == "failed":
            error_msg = doc.error_message or "未知错误"
            if len(error_msg) > 30:
                error_msg = error_msg[:30] + "..."
            
            base_info.status_display = f"解析失败 - {error_msg}"
            base_info.action_type = "retry"
            base_info.action_icon = "refresh"
            base_info.action_text = "重试"
            base_info.can_process = True
            
        else:
            base_info.status_display = doc.status
            base_info.action_type = "unknown"
            base_info.action_icon = "question"
            base_info.action_text = "未知"
            base_info.can_process = False
        
        return base_info
    
    def _calculate_completion_time(self, updated_at: Optional[str]) -> str:
        """计算完成时间显示"""
        if not updated_at:
            return "已完成"
        
        try:
            updated_time = datetime.fromisoformat(updated_at)
            now = datetime.now()
            time_diff = now - updated_time
            
            if time_diff.days > 0:
                return f"{time_diff.days}天前完成"
            elif time_diff.seconds > 3600:
                hours = time_diff.seconds // 3600
                return f"{hours}小时前完成"
            elif time_diff.seconds > 60:
                minutes = time_diff.seconds // 60
                return f"{minutes}分钟前完成"
            else:
                return "刚刚完成"
        except:
            return "已完成"
    
    async def scan_uploads_folder(self) -> Dict[str, Any]:
        """扫描uploads文件夹，发现未处理的文件"""
        try:
            upload_dir = os.getenv("UPLOAD_DIR", "/home/ragsvr/projects/ragsystem/uploads")
            
            # 支持的文件扩展名
            supported_extensions = {
                '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
                '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp',
                '.txt', '.md'
            }
            
            # 扫描uploads文件夹
            found_files = []
            if os.path.exists(upload_dir):
                for root, dirs, files in os.walk(upload_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        file_ext = os.path.splitext(file.lower())[1]
                        
                        if file_ext in supported_extensions:
                            file_size = os.path.getsize(file_path)
                            file_stat = os.stat(file_path)
                            modified_time = datetime.fromtimestamp(file_stat.st_mtime)
                            
                            found_files.append({
                                'file_name': file,
                                'file_path': file_path,
                                'file_size': file_size,
                                'modified_time': modified_time.isoformat(),
                                'extension': file_ext
                            })
            
            # 获取已知文档列表
            existing_documents = await self.state_manager.get_all_documents()
            existing_filenames = {doc.file_name for doc in existing_documents}
            
            # 找出未处理的文件
            unprocessed_files = []
            for file_info in found_files:
                if file_info['file_name'] not in existing_filenames:
                    unprocessed_files.append({
                        'file_name': file_info['file_name'],
                        'file_path': file_info['file_path'],
                        'file_size': file_info['file_size'],
                        'file_size_display': self._format_file_size(file_info['file_size']),
                        'modified_time': file_info['modified_time'],
                        'extension': file_info['extension']
                    })
            
            return {
                'success': True,
                'scanned_files': len(found_files),
                'unprocessed_files': len(unprocessed_files),
                'unprocessed_file_list': unprocessed_files,
                'message': f'扫描完成：发现 {len(found_files)} 个文件，其中 {len(unprocessed_files)} 个未处理'
            }
            
        except Exception as e:
            return {
                'success': False,
                'scanned_files': 0,
                'unprocessed_files': 0,
                'unprocessed_file_list': [],
                'message': f'扫描失败: {str(e)}'
            }
    
    async def process_unprocessed_files(self, parser: str = "mineru", parse_method: str = "auto") -> Dict[str, Any]:
        """批量处理uploads文件夹中未处理的文件"""
        try:
            # 先扫描获取未处理文件
            scan_result = await self.scan_uploads_folder()
            
            if not scan_result['success'] or scan_result['unprocessed_files'] == 0:
                return {
                    'success': True,
                    'added_count': 0,
                    'message': '没有发现未处理的文件'
                }
            
            unprocessed_files = scan_result['unprocessed_file_list']
            added_documents = []
            failed_files = []
            
            # 为每个未处理文件创建文档记录
            for file_info in unprocessed_files:
                try:
                    # 创建文档记录
                    document = await self._create_document_record(
                        filename=file_info['file_name'],
                        filepath=file_info['file_path'],
                        filesize=file_info['file_size']
                    )
                    
                    # 添加到状态管理器
                    await self.state_manager.add_document(document)
                    added_documents.append({
                        'document_id': document.document_id,
                        'file_name': document.file_name,
                        'file_size': document.file_size,
                        'task_id': document.task_id
                    })
                    
                except Exception as e:
                    failed_files.append({
                        'file_name': file_info['file_name'],
                        'error': str(e)
                    })
            
            # TODO: 这里可以集成批量处理服务来自动开始处理
            # 现在只是添加到系统中，用户可以在前端看到这些文件并选择处理
            
            return {
                'success': True,
                'added_count': len(added_documents),
                'failed_count': len(failed_files),
                'total_files': len(unprocessed_files),
                'added_documents': added_documents,
                'failed_files': failed_files,
                'message': f'成功添加 {len(added_documents)} 个文件到处理队列'
            }
            
        except Exception as e:
            return {
                'success': False,
                'added_count': 0,
                'failed_count': 0,
                'total_files': 0,
                'message': f'批量处理失败: {str(e)}'
            }
    
    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小显示"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"