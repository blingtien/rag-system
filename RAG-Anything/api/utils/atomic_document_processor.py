#!/usr/bin/env python3
"""
原子性文档处理器
提供事务性文档处理，支持失败时的自动回滚
"""

import json
import os
import logging
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from contextlib import contextmanager
import traceback

logger = logging.getLogger(__name__)

class DocumentProcessingTransaction:
    """文档处理事务管理器"""
    
    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir or os.environ.get("WORKING_DIR", "./rag_storage"))
        self.rollback_operations = []
        self.completed_operations = []
        self.transaction_id = str(uuid.uuid4())
        
        # 存储文件路径
        self.api_state_file = self.storage_dir / "api_documents_state.json"
        self.doc_status_file = self.storage_dir / "kv_store_doc_status.json"
        self.full_docs_file = self.storage_dir / "kv_store_full_docs.json"
        self.text_chunks_file = self.storage_dir / "kv_store_text_chunks.json"
        
        # 事务日志文件
        self.transaction_log_dir = self.storage_dir / "transaction_logs"
        self.transaction_log_dir.mkdir(exist_ok=True)
        self.transaction_log_file = self.transaction_log_dir / f"transaction_{self.transaction_id}.json"
        
    def log_operation(self, operation: str, details: Dict[str, Any]):
        """记录事务操作"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'details': details,
            'transaction_id': self.transaction_id
        }
        
        try:
            if self.transaction_log_file.exists():
                with open(self.transaction_log_file, 'r+', encoding='utf-8') as f:
                    logs = json.load(f)
                    logs.append(log_entry)
                    f.seek(0)
                    json.dump(logs, f, ensure_ascii=False, indent=2)
                    f.truncate()
            else:
                with open(self.transaction_log_file, 'w', encoding='utf-8') as f:
                    json.dump([log_entry], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"记录事务操作失败: {e}")
    
    def add_rollback_operation(self, operation: Callable, *args, **kwargs):
        """添加回滚操作"""
        self.rollback_operations.append((operation, args, kwargs))
    
    def create_backup(self, file_path: Path) -> Optional[Path]:
        """创建文件备份"""
        if not file_path.exists():
            return None
            
        backup_path = file_path.parent / f"{file_path.stem}.backup_{self.transaction_id}{file_path.suffix}"
        try:
            shutil.copy2(file_path, backup_path)
            logger.debug(f"创建备份: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"创建备份失败 {file_path}: {e}")
            return None
    
    def restore_backup(self, original_path: Path, backup_path: Path):
        """恢复备份文件"""
        try:
            if backup_path.exists():
                shutil.copy2(backup_path, original_path)
                logger.debug(f"恢复备份: {original_path}")
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
    
    def cleanup_backups(self):
        """清理事务备份文件"""
        try:
            backup_pattern = f"*.backup_{self.transaction_id}*"
            for backup_file in self.storage_dir.glob(backup_pattern):
                backup_file.unlink()
                logger.debug(f"删除备份文件: {backup_file}")
        except Exception as e:
            logger.error(f"清理备份文件失败: {e}")
    
    def rollback(self):
        """执行回滚操作"""
        logger.info(f"开始回滚事务 {self.transaction_id}")
        
        # 执行回滚操作（逆序执行）
        for operation, args, kwargs in reversed(self.rollback_operations):
            try:
                operation(*args, **kwargs)
                logger.debug(f"回滚操作成功: {operation.__name__}")
            except Exception as e:
                logger.error(f"回滚操作失败 {operation.__name__}: {e}")
        
        # 记录回滚完成
        self.log_operation("rollback_completed", {
            'rollback_operations_count': len(self.rollback_operations)
        })
        
        self.rollback_operations.clear()
    
    def commit(self):
        """提交事务"""
        logger.info(f"提交事务 {self.transaction_id}")
        
        # 清理备份文件
        self.cleanup_backups()
        
        # 记录事务完成
        self.log_operation("transaction_committed", {
            'completed_operations_count': len(self.completed_operations)
        })
        
        self.rollback_operations.clear()
        self.completed_operations.clear()


class AtomicDocumentProcessor:
    """原子性文档处理器"""
    
    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir or os.environ.get("WORKING_DIR", "./rag_storage"))
        
    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        transaction = DocumentProcessingTransaction(self.storage_dir)
        try:
            logger.info(f"开始事务 {transaction.transaction_id}")
            transaction.log_operation("transaction_started", {})
            yield transaction
            transaction.commit()
            logger.info(f"事务提交成功 {transaction.transaction_id}")
        except Exception as e:
            logger.error(f"事务执行失败 {transaction.transaction_id}: {e}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            transaction.rollback()
            raise
    
    def safe_json_update(self, transaction: DocumentProcessingTransaction, 
                        file_path: Path, update_func: Callable[[Dict], Dict]) -> bool:
        """安全的JSON文件更新"""
        try:
            # 创建备份
            backup_path = transaction.create_backup(file_path)
            if backup_path:
                transaction.add_rollback_operation(
                    transaction.restore_backup, file_path, backup_path
                )
            
            # 加载现有数据
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}
            
            # 执行更新
            updated_data = update_func(data)
            
            # 保存更新后的数据
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(updated_data, f, ensure_ascii=False, indent=2)
            
            transaction.log_operation("json_file_updated", {
                'file_path': str(file_path),
                'backup_created': backup_path is not None
            })
            
            return True
            
        except Exception as e:
            logger.error(f"JSON文件更新失败 {file_path}: {e}")
            return False
    
    def create_document_atomically(self, document_info: Dict[str, Any], 
                                  content_list: Optional[List[Dict]] = None) -> bool:
        """原子性创建文档"""
        with self.transaction() as transaction:
            doc_id = document_info['id']
            rag_doc_id = document_info.get('rag_doc_id', str(uuid.uuid4()))
            
            transaction.log_operation("create_document_started", {
                'doc_id': doc_id,
                'rag_doc_id': rag_doc_id,
                'filename': document_info.get('filename')
            })
            
            # 步骤1: 更新API文档状态
            def update_api_state(data):
                data[doc_id] = document_info
                return data
            
            if not self.safe_json_update(transaction, transaction.api_state_file, update_api_state):
                raise Exception("Failed to update API document state")
            
            # 步骤2: 更新文档状态
            def update_doc_status(data):
                data[rag_doc_id] = "uploaded"
                return data
            
            if not self.safe_json_update(transaction, transaction.doc_status_file, update_doc_status):
                raise Exception("Failed to update document status")
            
            # 步骤3: 如果有内容，添加到full_docs
            if content_list:
                def update_full_docs(data):
                    data[rag_doc_id] = content_list
                    return data
                
                if not self.safe_json_update(transaction, transaction.full_docs_file, update_full_docs):
                    raise Exception("Failed to update full documents")
                
                # 更新状态为已完成
                def update_status_completed(data):
                    data[rag_doc_id] = "completed"
                    return data
                
                if not self.safe_json_update(transaction, transaction.doc_status_file, update_status_completed):
                    raise Exception("Failed to update document status to completed")
            
            transaction.log_operation("create_document_completed", {
                'doc_id': doc_id,
                'rag_doc_id': rag_doc_id
            })
            
            return True
    
    def update_document_status_atomically(self, doc_id: str, rag_doc_id: str, 
                                        new_status: str, error_message: str = None) -> bool:
        """原子性更新文档状态"""
        with self.transaction() as transaction:
            transaction.log_operation("update_status_started", {
                'doc_id': doc_id,
                'rag_doc_id': rag_doc_id,
                'new_status': new_status,
                'error_message': error_message
            })
            
            # 更新API文档状态
            def update_api_state(data):
                if doc_id in data:
                    data[doc_id]['status'] = new_status
                    data[doc_id]['updated_at'] = datetime.now().isoformat()
                    if error_message:
                        data[doc_id]['error_message'] = error_message
                return data
            
            if not self.safe_json_update(transaction, transaction.api_state_file, update_api_state):
                raise Exception("Failed to update API document status")
            
            # 更新RAG文档状态
            def update_rag_status(data):
                data[rag_doc_id] = new_status
                return data
            
            if not self.safe_json_update(transaction, transaction.doc_status_file, update_rag_status):
                raise Exception("Failed to update RAG document status")
            
            return True
    
    def delete_document_atomically(self, doc_id: str, rag_doc_id: str = None) -> bool:
        """原子性删除文档"""
        with self.transaction() as transaction:
            transaction.log_operation("delete_document_started", {
                'doc_id': doc_id,
                'rag_doc_id': rag_doc_id
            })
            
            # 从API文档中获取rag_doc_id（如果未提供）
            if not rag_doc_id:
                api_state_file = transaction.api_state_file
                if api_state_file.exists():
                    with open(api_state_file, 'r', encoding='utf-8') as f:
                        api_docs = json.load(f)
                        doc_info = api_docs.get(doc_id, {})
                        rag_doc_id = doc_info.get('rag_doc_id')
            
            # 删除API文档条目
            def remove_from_api_state(data):
                if doc_id in data:
                    del data[doc_id]
                return data
            
            if not self.safe_json_update(transaction, transaction.api_state_file, remove_from_api_state):
                raise Exception("Failed to remove from API document state")
            
            # 删除RAG文档相关条目
            if rag_doc_id:
                # 删除文档状态
                def remove_from_doc_status(data):
                    if rag_doc_id in data:
                        del data[rag_doc_id]
                    return data
                
                self.safe_json_update(transaction, transaction.doc_status_file, remove_from_doc_status)
                
                # 删除完整文档
                def remove_from_full_docs(data):
                    if rag_doc_id in data:
                        del data[rag_doc_id]
                    return data
                
                self.safe_json_update(transaction, transaction.full_docs_file, remove_from_full_docs)
                
                # 删除相关的文本块
                def remove_related_chunks(data):
                    chunks_to_remove = []
                    for chunk_id, chunk_info in data.items():
                        if isinstance(chunk_info, dict) and chunk_info.get('full_doc_id') == rag_doc_id:
                            chunks_to_remove.append(chunk_id)
                    
                    for chunk_id in chunks_to_remove:
                        del data[chunk_id]
                    
                    return data
                
                self.safe_json_update(transaction, transaction.text_chunks_file, remove_related_chunks)
            
            transaction.log_operation("delete_document_completed", {
                'doc_id': doc_id,
                'rag_doc_id': rag_doc_id
            })
            
            return True
    
    def batch_process_documents_atomically(self, document_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """原子性批处理文档"""
        with self.transaction() as transaction:
            transaction.log_operation("batch_process_started", {
                'document_count': len(document_updates)
            })
            
            results = {
                'successful': [],
                'failed': [],
                'total_processed': 0
            }
            
            for doc_update in document_updates:
                try:
                    operation = doc_update.get('operation')
                    doc_id = doc_update.get('doc_id')
                    
                    if operation == 'create':
                        self.create_document_atomically(doc_update['document_info'], 
                                                      doc_update.get('content_list'))
                    elif operation == 'update_status':
                        self.update_document_status_atomically(
                            doc_id, doc_update['rag_doc_id'], 
                            doc_update['status'], doc_update.get('error_message')
                        )
                    elif operation == 'delete':
                        self.delete_document_atomically(doc_id, doc_update.get('rag_doc_id'))
                    
                    results['successful'].append(doc_id)
                    results['total_processed'] += 1
                    
                except Exception as e:
                    logger.error(f"批处理文档失败 {doc_id}: {e}")
                    results['failed'].append({
                        'doc_id': doc_id,
                        'error': str(e)
                    })
                    # 不中断批处理，继续处理其他文档
            
            # 如果有任何失败，整个批处理也失败
            if results['failed']:
                raise Exception(f"Batch processing failed for {len(results['failed'])} documents")
            
            transaction.log_operation("batch_process_completed", results)
            return results
    
    def check_duplicate_by_hash(self, file_hash: str) -> Optional[str]:
        """检查是否存在相同哈希的文档"""
        try:
            if self.storage_dir.joinpath("api_documents_state.json").exists():
                with open(self.storage_dir / "api_documents_state.json", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 处理嵌套的documents结构
                    if isinstance(data, dict) and 'documents' in data:
                        documents = data['documents']
                    else:
                        documents = data
                    
                for doc_id, doc_info in documents.items():
                    if doc_info.get('file_hash') == file_hash:
                        return doc_id
            return None
        except Exception as e:
            logger.error(f"检查重复文档失败: {e}")
            return None
    
    def cleanup_failed_documents(self, max_age_hours: int = 24) -> Dict[str, int]:
        """清理长时间处理失败的文档"""
        from datetime import datetime, timedelta
        
        cleanup_stats = {
            'checked': 0,
            'cleaned': 0,
            'errors': 0
        }
        
        try:
            with self.transaction() as transaction:
                transaction.log_operation("cleanup_failed_documents_started", {
                    'max_age_hours': max_age_hours
                })
                
                cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
                
                api_state_file = transaction.api_state_file
                if not api_state_file.exists():
                    return cleanup_stats
                
                with open(api_state_file, 'r', encoding='utf-8') as f:
                    documents = json.load(f)
                
                failed_docs_to_remove = []
                
                for doc_id, doc_info in documents.items():
                    cleanup_stats['checked'] += 1
                    
                    # 检查是否是失败的文档
                    if doc_info.get('status') in ['failed', 'error']:
                        created_at = doc_info.get('created_at', '')
                        if created_at:
                            try:
                                created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                if created_time < cutoff_time:
                                    failed_docs_to_remove.append((doc_id, doc_info.get('rag_doc_id')))
                            except ValueError:
                                logger.warning(f"无法解析创建时间: {created_at}")
                
                # 删除过期的失败文档
                for doc_id, rag_doc_id in failed_docs_to_remove:
                    try:
                        if self.delete_document_atomically(doc_id, rag_doc_id):
                            cleanup_stats['cleaned'] += 1
                    except Exception as e:
                        logger.error(f"清理失败文档错误 {doc_id}: {e}")
                        cleanup_stats['errors'] += 1
                
                transaction.log_operation("cleanup_failed_documents_completed", cleanup_stats)
                
        except Exception as e:
            logger.error(f"清理失败文档过程错误: {e}")
            cleanup_stats['errors'] += 1
        
        return cleanup_stats


def main():
    """测试和演示函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='原子性文档处理器测试')
    parser.add_argument('--storage-dir', default=None, help='存储目录路径')
    parser.add_argument('--action', choices=['test-create', 'test-update', 'test-delete', 'cleanup'],
                       default='test-create', help='测试操作')
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    processor = AtomicDocumentProcessor(args.storage_dir)
    
    if args.action == 'test-create':
        # 测试文档创建
        test_doc = {
            'id': f'test_{uuid.uuid4()}',
            'filename': 'test_document.txt',
            'status': 'uploaded',
            'created_at': datetime.now().isoformat(),
            'file_path': '/tmp/test_document.txt',
            'rag_doc_id': str(uuid.uuid4())
        }
        
        try:
            success = processor.create_document_atomically(test_doc)
            print(f"文档创建测试: {'成功' if success else '失败'}")
        except Exception as e:
            print(f"文档创建测试失败: {e}")
    
    elif args.action == 'cleanup':
        # 清理失败的文档
        stats = processor.cleanup_failed_documents(max_age_hours=1)
        print(f"清理统计: {stats}")


if __name__ == "__main__":
    main()