#!/usr/bin/env python3
"""
文档去重工具
实现基于内容哈希的文档重复检测和清理功能
"""

import hashlib
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
import shutil

logger = logging.getLogger(__name__)

class DocumentDeduplicator:
    """文档去重器 - 检测和处理重复文档"""
    
    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir or os.environ.get("WORKING_DIR", "./rag_storage"))
        self.api_state_file = self.storage_dir / "api_documents_state.json"
        self.doc_status_file = self.storage_dir / "kv_store_doc_status.json"
        self.full_docs_file = self.storage_dir / "kv_store_full_docs.json"
        
    def calculate_file_hash(self, file_path: str) -> Optional[str]:
        """计算文件的SHA-256哈希值"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logger.warning(f"文件不存在: {file_path}")
                return None
                
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希失败 {file_path}: {e}")
            return None
    
    def load_api_documents(self) -> Dict:
        """加载API文档状态"""
        try:
            if self.api_state_file.exists():
                with open(self.api_state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 处理嵌套的documents结构
                    if isinstance(data, dict) and 'documents' in data:
                        return data['documents']
                    return data
            return {}
        except Exception as e:
            logger.error(f"加载API文档状态失败: {e}")
            return {}
    
    def save_api_documents(self, documents: Dict):
        """保存API文档状态"""
        try:
            # 保持原有的嵌套结构
            data_to_save = {"documents": documents}
            with open(self.api_state_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            logger.info("API文档状态已保存")
        except Exception as e:
            logger.error(f"保存API文档状态失败: {e}")
    
    def load_kv_store(self, store_file: Path) -> Dict:
        """加载KV存储文件"""
        try:
            if store_file.exists():
                with open(store_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载KV存储失败 {store_file}: {e}")
            return {}
    
    def save_kv_store(self, data: Dict, store_file: Path):
        """保存KV存储文件"""
        try:
            with open(store_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"KV存储已保存: {store_file.name}")
        except Exception as e:
            logger.error(f"保存KV存储失败 {store_file}: {e}")
    
    def find_duplicates_by_content(self) -> Dict[str, List[str]]:
        """基于文件内容查找重复文档"""
        logger.info("开始基于内容查找重复文档...")
        
        documents = self.load_api_documents()
        hash_to_docs = {}
        content_duplicates = {}
        
        for doc_id, doc_info in documents.items():
            # 兼容不同的字段名
            file_path = doc_info.get('file_path', '') or doc_info.get('filepath', '')
            
            # 规范化路径
            if file_path and not os.path.isabs(file_path):
                file_path = os.path.join('/home/ragsvr/projects/ragsystem', file_path.lstrip('./'))
            
            if file_path:
                file_hash = self.calculate_file_hash(file_path)
                if file_hash:
                    if file_hash not in hash_to_docs:
                        hash_to_docs[file_hash] = []
                    hash_to_docs[file_hash].append(doc_id)
        
        # 找出有多个文档的哈希值（重复内容）
        for file_hash, doc_ids in hash_to_docs.items():
            if len(doc_ids) > 1:
                content_duplicates[file_hash] = doc_ids
                logger.info(f"发现重复内容: {len(doc_ids)} 个文档，哈希: {file_hash[:8]}...")
        
        return content_duplicates
    
    def find_duplicates_by_filename(self) -> Dict[str, List[str]]:
        """基于文件名查找重复文档"""
        logger.info("开始基于文件名查找重复文档...")
        
        documents = self.load_api_documents()
        filename_to_docs = {}
        filename_duplicates = {}
        
        for doc_id, doc_info in documents.items():
            # 兼容不同的字段名
            filename = doc_info.get('filename', '') or doc_info.get('file_name', '')
            if filename:
                if filename not in filename_to_docs:
                    filename_to_docs[filename] = []
                filename_to_docs[filename].append(doc_id)
        
        # 找出有多个文档的文件名
        for filename, doc_ids in filename_to_docs.items():
            if len(doc_ids) > 1:
                filename_duplicates[filename] = doc_ids
                logger.info(f"发现重复文件名: {len(doc_ids)} 个文档，文件名: {filename}")
        
        return filename_duplicates
    
    def select_best_document(self, doc_ids: List[str], documents: Dict) -> str:
        """从重复文档中选择最佳文档（优先级：已处理完成 > 最新创建时间 > 绝对路径）"""
        best_doc_id = doc_ids[0]
        best_doc = documents[best_doc_id]
        
        for doc_id in doc_ids[1:]:
            current_doc = documents[doc_id]
            
            # 优先级1: 处理状态（已完成 > 其他状态）
            current_status = current_doc.get('status', '')
            best_status = best_doc.get('status', '')
            
            if current_status == 'completed' and best_status != 'completed':
                best_doc_id = doc_id
                best_doc = current_doc
                continue
            elif best_status == 'completed' and current_status != 'completed':
                continue
            
            # 优先级2: 创建时间（更新的更好）
            current_time = current_doc.get('created_at', '')
            best_time = best_doc.get('created_at', '')
            
            if current_time > best_time:
                best_doc_id = doc_id
                best_doc = current_doc
                continue
            elif best_time > current_time:
                continue
            
            # 优先级3: 路径类型（绝对路径 > 相对路径）
            current_path = current_doc.get('file_path', '')
            best_path = best_doc.get('file_path', '')
            
            if os.path.isabs(current_path) and not os.path.isabs(best_path):
                best_doc_id = doc_id
                best_doc = current_doc
        
        return best_doc_id
    
    def remove_duplicate_documents(self, duplicates: Dict[str, List[str]], dry_run: bool = True) -> Dict:
        """移除重复文档"""
        logger.info(f"开始移除重复文档 (dry_run={dry_run})...")
        
        documents = self.load_api_documents()
        doc_status = self.load_kv_store(self.doc_status_file)
        full_docs = self.load_kv_store(self.full_docs_file)
        
        removal_report = {
            'removed_documents': [],
            'kept_documents': [],
            'total_duplicates_found': len(duplicates),
            'total_documents_removed': 0
        }
        
        for identifier, doc_ids in duplicates.items():
            # 选择最佳文档
            best_doc_id = self.select_best_document(doc_ids, documents)
            docs_to_remove = [doc_id for doc_id in doc_ids if doc_id != best_doc_id]
            
            removal_report['kept_documents'].append({
                'doc_id': best_doc_id,
                'filename': documents[best_doc_id].get('filename', ''),
                'status': documents[best_doc_id].get('status', ''),
                'identifier': identifier[:8] if len(identifier) > 8 else identifier
            })
            
            for doc_id in docs_to_remove:
                doc_info = documents.get(doc_id, {})
                removal_report['removed_documents'].append({
                    'doc_id': doc_id,
                    'filename': doc_info.get('filename', ''),
                    'status': doc_info.get('status', ''),
                    'file_path': doc_info.get('file_path', ''),
                    'identifier': identifier[:8] if len(identifier) > 8 else identifier
                })
                
                if not dry_run:
                    # 从API状态中移除
                    if doc_id in documents:
                        del documents[doc_id]
                    
                    # 从KV存储中移除
                    rag_doc_id = doc_info.get('rag_doc_id')
                    if rag_doc_id:
                        if rag_doc_id in doc_status:
                            del doc_status[rag_doc_id]
                        if rag_doc_id in full_docs:
                            del full_docs[rag_doc_id]
        
        removal_report['total_documents_removed'] = len(removal_report['removed_documents'])
        
        if not dry_run:
            # 保存清理后的数据
            self.save_api_documents(documents)
            self.save_kv_store(doc_status, self.doc_status_file)
            self.save_kv_store(full_docs, self.full_docs_file)
            logger.info(f"实际移除了 {removal_report['total_documents_removed']} 个重复文档")
        else:
            logger.info(f"模拟运行：将移除 {removal_report['total_documents_removed']} 个重复文档")
        
        return removal_report
    
    def check_document_by_hash(self, file_hash: str) -> Optional[str]:
        """根据文件哈希检查是否已存在文档"""
        documents = self.load_api_documents()
        
        for doc_id, doc_info in documents.items():
            stored_hash = doc_info.get('file_hash')
            if stored_hash == file_hash:
                return doc_id
        
        return None
    
    def add_hash_to_documents(self, dry_run: bool = True) -> Dict:
        """为现有文档添加哈希值"""
        logger.info(f"开始为文档添加哈希值 (dry_run={dry_run})...")
        
        documents = self.load_api_documents()
        hash_report = {
            'processed_documents': 0,
            'successful_hashes': 0,
            'failed_hashes': 0,
            'already_have_hash': 0
        }
        
        for doc_id, doc_info in documents.items():
            hash_report['processed_documents'] += 1
            
            # 检查是否已有哈希值
            if doc_info.get('file_hash'):
                hash_report['already_have_hash'] += 1
                continue
            
            file_path = doc_info.get('file_path', '')
            if file_path and not os.path.isabs(file_path):
                file_path = os.path.join('/home/ragsvr/projects/ragsystem', file_path.lstrip('./'))
            
            if file_path:
                file_hash = self.calculate_file_hash(file_path)
                if file_hash:
                    if not dry_run:
                        documents[doc_id]['file_hash'] = file_hash
                    hash_report['successful_hashes'] += 1
                else:
                    hash_report['failed_hashes'] += 1
        
        if not dry_run:
            self.save_api_documents(documents)
            logger.info("文档哈希值已更新")
        
        return hash_report
    
    def generate_deduplication_report(self) -> Dict:
        """生成去重分析报告"""
        logger.info("生成去重分析报告...")
        
        content_duplicates = self.find_duplicates_by_content()
        filename_duplicates = self.find_duplicates_by_filename()
        
        documents = self.load_api_documents()
        doc_status = self.load_kv_store(self.doc_status_file)
        full_docs = self.load_kv_store(self.full_docs_file)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_api_documents': len(documents),
                'total_kv_doc_status': len(doc_status),
                'total_kv_full_docs': len(full_docs),
                'content_duplicate_groups': len(content_duplicates),
                'filename_duplicate_groups': len(filename_duplicates),
                'total_duplicate_documents': sum(len(docs) - 1 for docs in content_duplicates.values()),
                'potential_savings': sum(len(docs) - 1 for docs in content_duplicates.values())
            },
            'content_duplicates': content_duplicates,
            'filename_duplicates': filename_duplicates,
            'storage_inconsistency': {
                'api_vs_doc_status': len(documents) - len(doc_status),
                'api_vs_full_docs': len(documents) - len(full_docs)
            }
        }
        
        return report


def main():
    """主函数 - 命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='RAG文档去重工具')
    parser.add_argument('--storage-dir', default=None, help='存储目录路径')
    parser.add_argument('--action', choices=['report', 'add-hash', 'remove-duplicates'], 
                       default='report', help='执行的操作')
    parser.add_argument('--dry-run', action='store_true', default=True, help='模拟运行（不实际修改）')
    parser.add_argument('--execute', action='store_true', help='实际执行修改')
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    deduplicator = DocumentDeduplicator(args.storage_dir)
    dry_run = not args.execute
    
    if args.action == 'report':
        report = deduplicator.generate_deduplication_report()
        print("\n" + "="*50)
        print("📊 RAG文档去重分析报告")
        print("="*50)
        print(f"📄 总文档数: {report['summary']['total_api_documents']}")
        print(f"🔄 内容重复组: {report['summary']['content_duplicate_groups']}")
        print(f"📝 文件名重复组: {report['summary']['filename_duplicate_groups']}")
        print(f"🗑️  可移除重复文档: {report['summary']['total_duplicate_documents']}")
        print(f"💾 存储一致性问题: API({len(deduplicator.load_api_documents())}) vs KV({len(deduplicator.load_kv_store(deduplicator.doc_status_file))})")
        
        # 保存详细报告
        report_file = deduplicator.storage_dir / f"deduplication_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"📋 详细报告已保存: {report_file}")
    
    elif args.action == 'add-hash':
        result = deduplicator.add_hash_to_documents(dry_run)
        print(f"\n📊 哈希添加结果:")
        print(f"处理文档: {result['processed_documents']}")
        print(f"成功添加: {result['successful_hashes']}")
        print(f"添加失败: {result['failed_hashes']}")
        print(f"已有哈希: {result['already_have_hash']}")
    
    elif args.action == 'remove-duplicates':
        content_duplicates = deduplicator.find_duplicates_by_content()
        if content_duplicates:
            result = deduplicator.remove_duplicate_documents(content_duplicates, dry_run)
            print(f"\n🗑️  重复文档移除结果:")
            print(f"重复组数: {result['total_duplicates_found']}")
            print(f"移除文档: {result['total_documents_removed']}")
            print(f"保留文档: {len(result['kept_documents'])}")
            
            if dry_run:
                print("\n⚠️  这是模拟运行。使用 --execute 执行实际移除。")
        else:
            print("✅ 未发现基于内容的重复文档")


if __name__ == "__main__":
    main()