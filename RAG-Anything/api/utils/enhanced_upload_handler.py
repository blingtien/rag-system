#!/usr/bin/env python3
"""
增强的上传处理器
集成文档去重、原子性处理和路径标准化功能
"""

import hashlib
import json
import os
import uuid
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from fastapi import UploadFile, HTTPException

from .document_deduplicator import DocumentDeduplicator
from .atomic_document_processor import AtomicDocumentProcessor
from .storage_consistency_repair import StorageConsistencyRepairer

logger = logging.getLogger(__name__)

class EnhancedUploadHandler:
    """增强的文档上传处理器"""
    
    def __init__(self, storage_dir: str = None, upload_dir: str = None):
        self.storage_dir = Path(storage_dir or os.environ.get("WORKING_DIR", "./rag_storage"))
        self.upload_dir = Path(upload_dir or "./uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化组件
        self.deduplicator = DocumentDeduplicator(self.storage_dir)
        self.atomic_processor = AtomicDocumentProcessor(self.storage_dir)
        self.consistency_repairer = StorageConsistencyRepairer(self.storage_dir)
        
        # 配置参数
        self.max_file_size = int(os.environ.get("MAX_FILE_SIZE", 100 * 1024 * 1024))  # 100MB
        self.allowed_extensions = {
            '.pdf', '.docx', '.doc', '.txt', '.md', '.png', '.jpg', '.jpeg', 
            '.bmp', '.tiff', '.gif', '.webp', '.pptx', '.ppt', '.xlsx', '.xls'
        }
    
    def calculate_file_hash(self, file_content: bytes) -> str:
        """计算文件内容的SHA-256哈希"""
        return hashlib.sha256(file_content).hexdigest()
    
    def validate_file(self, file: UploadFile) -> Tuple[bool, str]:
        """验证文件"""
        # 检查文件名
        if not file.filename:
            return False, "文件名为空"
        
        # 检查文件扩展名
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in self.allowed_extensions:
            return False, f"不支持的文件类型: {file_ext}"
        
        return True, ""
    
    def normalize_file_path(self, relative_path: str) -> str:
        """标准化文件路径为绝对路径"""
        if os.path.isabs(relative_path):
            return relative_path
        
        base_path = "/home/ragsvr/projects/ragsystem"
        return os.path.join(base_path, relative_path.lstrip('./'))
    
    async def save_uploaded_file(self, file: UploadFile, file_hash: str) -> Tuple[str, str]:
        """保存上传的文件"""
        try:
            # 读取文件内容
            file_content = await file.read()
            file.file.seek(0)  # 重置文件指针
            
            # 验证文件大小
            if len(file_content) > self.max_file_size:
                raise HTTPException(
                    status_code=413, 
                    detail=f"文件过大，最大允许 {self.max_file_size / (1024*1024):.1f}MB"
                )
            
            # 生成安全的文件名（使用哈希值避免重复）
            file_ext = Path(file.filename).suffix.lower()
            safe_filename = f"{file_hash[:16]}_{file.filename}"
            
            # 保存文件
            file_path = self.upload_dir / safe_filename
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            logger.info(f"文件已保存: {file_path}")
            return str(file_path), safe_filename
            
        except Exception as e:
            logger.error(f"保存文件失败: {e}")
            raise HTTPException(status_code=500, detail=f"保存文件失败: {str(e)}")
    
    async def process_single_upload(self, file: UploadFile, 
                                  auto_process: bool = True) -> Dict[str, Any]:
        """处理单个文件上传"""
        logger.info(f"开始处理上传文件: {file.filename}")
        
        try:
            # 验证文件
            is_valid, error_msg = self.validate_file(file)
            if not is_valid:
                raise HTTPException(status_code=400, detail=error_msg)
            
            # 读取文件内容并计算哈希
            file_content = await file.read()
            file_hash = self.calculate_file_hash(file_content)
            file.file.seek(0)  # 重置文件指针
            
            # 检查是否已存在相同内容的文档
            existing_doc_id = self.atomic_processor.check_duplicate_by_hash(file_hash)
            if existing_doc_id:
                logger.info(f"发现重复文档，返回现有文档ID: {existing_doc_id}")
                return {
                    'status': 'duplicate_found',
                    'document_id': existing_doc_id,
                    'message': f'文件已存在，返回现有文档ID',
                    'file_hash': file_hash,
                    'original_filename': file.filename
                }
            
            # 保存文件
            file_path, safe_filename = await self.save_uploaded_file(file, file_hash)
            
            # 创建文档信息
            doc_id = str(uuid.uuid4())
            rag_doc_id = str(uuid.uuid4())
            
            document_info = {
                'id': doc_id,
                'rag_doc_id': rag_doc_id,
                'filename': file.filename,
                'safe_filename': safe_filename,
                'file_path': self.normalize_file_path(file_path),
                'file_size': len(file_content),
                'file_hash': file_hash,
                'content_type': file.content_type,
                'status': 'uploaded',
                'auto_process': auto_process,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'upload_source': 'api'
            }
            
            # 原子性创建文档记录
            success = self.atomic_processor.create_document_atomically(document_info)
            
            if not success:
                # 如果创建失败，清理已保存的文件
                try:
                    os.remove(file_path)
                except:
                    pass
                raise HTTPException(status_code=500, detail="创建文档记录失败")
            
            logger.info(f"文档上传成功: {doc_id}")
            
            result = {
                'status': 'success',
                'document_id': doc_id,
                'rag_doc_id': rag_doc_id,
                'filename': file.filename,
                'file_size': len(file_content),
                'file_hash': file_hash,
                'auto_process': auto_process,
                'message': '文件上传成功'
            }
            
            if not auto_process:
                result['message'] += '，等待手动处理'
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"处理上传文件失败 {file.filename}: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"处理文件上传失败: {str(e)}"
            )
    
    async def process_batch_upload(self, files: List[UploadFile], 
                                 auto_process: bool = True) -> Dict[str, Any]:
        """处理批量文件上传"""
        logger.info(f"开始批量上传处理，文件数量: {len(files)}")
        
        batch_id = str(uuid.uuid4())
        results = {
            'batch_id': batch_id,
            'total_files': len(files),
            'successful_uploads': [],
            'failed_uploads': [],
            'duplicate_files': [],
            'summary': {
                'success_count': 0,
                'failure_count': 0,
                'duplicate_count': 0
            }
        }
        
        # 使用事务处理批量上传
        try:
            with self.atomic_processor.transaction() as transaction:
                transaction.log_operation("batch_upload_started", {
                    'batch_id': batch_id,
                    'file_count': len(files),
                    'auto_process': auto_process
                })
                
                for file in files:
                    try:
                        # 处理单个文件
                        upload_result = await self.process_single_upload(file, auto_process)
                        
                        if upload_result['status'] == 'duplicate_found':
                            results['duplicate_files'].append({
                                'filename': file.filename,
                                'existing_document_id': upload_result['document_id'],
                                'file_hash': upload_result['file_hash']
                            })
                            results['summary']['duplicate_count'] += 1
                        else:
                            results['successful_uploads'].append({
                                'filename': file.filename,
                                'document_id': upload_result['document_id'],
                                'rag_doc_id': upload_result['rag_doc_id'],
                                'file_size': upload_result['file_size']
                            })
                            results['summary']['success_count'] += 1
                        
                    except Exception as e:
                        logger.error(f"批量上传中处理文件失败 {file.filename}: {e}")
                        results['failed_uploads'].append({
                            'filename': file.filename,
                            'error': str(e)
                        })
                        results['summary']['failure_count'] += 1
                
                transaction.log_operation("batch_upload_completed", results['summary'])
                
        except Exception as e:
            logger.error(f"批量上传事务失败: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"批量上传失败: {str(e)}"
            )
        
        logger.info(f"批量上传完成 - 成功: {results['summary']['success_count']}, "
                   f"失败: {results['summary']['failure_count']}, "
                   f"重复: {results['summary']['duplicate_count']}")
        
        return results
    
    def check_storage_health(self) -> Dict[str, Any]:
        """检查存储系统健康状态"""
        try:
            analysis = self.consistency_repairer.analyze_consistency()
            
            health_status = {
                'timestamp': datetime.now().isoformat(),
                'storage_health': 'healthy',
                'issues_found': 0,
                'recommendations': [],
                'file_counts': analysis['file_counts'],
                'inconsistencies': {}
            }
            
            # 计算总问题数
            total_issues = 0
            for issue_type, issues in analysis['inconsistencies'].items():
                if issues:
                    health_status['inconsistencies'][issue_type] = len(issues)
                    total_issues += len(issues)
            
            health_status['issues_found'] = total_issues
            health_status['recommendations'] = analysis['repair_recommendations']
            
            if total_issues > 0:
                if total_issues < 5:
                    health_status['storage_health'] = 'minor_issues'
                elif total_issues < 20:
                    health_status['storage_health'] = 'moderate_issues'
                else:
                    health_status['storage_health'] = 'major_issues'
            
            return health_status
            
        except Exception as e:
            logger.error(f"检查存储健康状态失败: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'storage_health': 'error',
                'error': str(e)
            }
    
    async def repair_storage_issues(self, dry_run: bool = True) -> Dict[str, Any]:
        """修复存储问题"""
        try:
            logger.info(f"开始修复存储问题 (dry_run={dry_run})")
            
            repair_result = self.consistency_repairer.full_consistency_repair(dry_run)
            
            return {
                'status': 'success',
                'dry_run': dry_run,
                'repair_summary': repair_result,
                'message': '存储修复完成' if not dry_run else '存储修复预览完成'
            }
            
        except Exception as e:
            logger.error(f"修复存储问题失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'message': '存储修复失败'
            }
    
    async def cleanup_old_files(self, max_age_days: int = 30) -> Dict[str, Any]:
        """清理旧的上传文件和失败的文档记录"""
        try:
            from datetime import timedelta
            
            cleanup_stats = {
                'files_cleaned': 0,
                'documents_cleaned': 0,
                'space_freed': 0,
                'errors': 0
            }
            
            # 清理失败的文档记录
            doc_cleanup = self.atomic_processor.cleanup_failed_documents(max_age_days * 24)
            cleanup_stats['documents_cleaned'] = doc_cleanup.get('cleaned', 0)
            cleanup_stats['errors'] += doc_cleanup.get('errors', 0)
            
            # 清理孤立的上传文件
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            
            for file_path in self.upload_dir.glob("*"):
                if file_path.is_file():
                    try:
                        file_stat = file_path.stat()
                        file_time = datetime.fromtimestamp(file_stat.st_mtime)
                        
                        if file_time < cutoff_time:
                            file_size = file_stat.st_size
                            file_path.unlink()
                            cleanup_stats['files_cleaned'] += 1
                            cleanup_stats['space_freed'] += file_size
                            
                    except Exception as e:
                        logger.error(f"清理文件失败 {file_path}: {e}")
                        cleanup_stats['errors'] += 1
            
            logger.info(f"清理完成 - 文件: {cleanup_stats['files_cleaned']}, "
                       f"文档: {cleanup_stats['documents_cleaned']}, "
                       f"释放空间: {cleanup_stats['space_freed'] / 1024 / 1024:.1f}MB")
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"清理旧文件失败: {e}")
            return {
                'error': str(e),
                'files_cleaned': 0,
                'documents_cleaned': 0,
                'space_freed': 0,
                'errors': 1
            }


# 全局实例
_enhanced_upload_handler: Optional[EnhancedUploadHandler] = None

def get_enhanced_upload_handler() -> EnhancedUploadHandler:
    """获取增强上传处理器实例（单例模式）"""
    global _enhanced_upload_handler
    
    if _enhanced_upload_handler is None:
        storage_dir = os.environ.get("WORKING_DIR", "./rag_storage")
        upload_dir = os.environ.get("UPLOAD_DIR", "./uploads")
        _enhanced_upload_handler = EnhancedUploadHandler(storage_dir, upload_dir)
        logger.info("增强上传处理器已初始化")
    
    return _enhanced_upload_handler


def main():
    """测试函数"""
    import asyncio
    from unittest.mock import Mock
    
    async def test_upload_handler():
        handler = get_enhanced_upload_handler()
        
        # 检查存储健康状态
        health = handler.check_storage_health()
        print("存储健康状态:")
        print(json.dumps(health, ensure_ascii=False, indent=2))
        
        # 修复存储问题（dry run）
        repair_result = await handler.repair_storage_issues(dry_run=True)
        print("\n存储修复预览:")
        print(json.dumps(repair_result, ensure_ascii=False, indent=2))
    
    # 配置日志
    logging.basicConfig(level=logging.INFO)
    
    # 运行测试
    asyncio.run(test_upload_handler())


if __name__ == "__main__":
    main()