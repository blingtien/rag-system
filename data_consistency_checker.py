#!/usr/bin/env python3
# RAG系统数据一致性检查和修复工具

import os
import json
import asyncio
import sys
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# 添加项目路径
sys.path.append('/home/ragsvr/projects/ragsystem/RAG-Anything')

class RAGDataConsistencyChecker:
    def __init__(self, rag_storage_dir: str, output_dir: str):
        """
        初始化数据一致性检查器
        
        Args:
            rag_storage_dir: LightRAG存储目录
            output_dir: 解析输出目录
        """
        self.rag_storage_dir = rag_storage_dir
        self.output_dir = output_dir
        
        # 关键文件路径
        self.doc_status_path = os.path.join(rag_storage_dir, "kv_store_doc_status.json")
        self.full_docs_path = os.path.join(rag_storage_dir, "kv_store_full_docs.json")
        self.vdb_chunks_path = os.path.join(rag_storage_dir, "vdb_chunks.json")
        
        # 配置日志
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
        self.logger = logging.getLogger(__name__)
        
    def load_json(self, filepath: str) -> Dict:
        """安全加载JSON文件"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                self.logger.warning(f"文件不存在: {filepath}")
                return {}
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.error(f"加载 {filepath} 失败: {e}")
            return {}
    
    def get_doc_id_from_filename(self, filename: str) -> Optional[str]:
        """根据文件名查找对应的doc_id"""
        doc_status = self.load_json(self.doc_status_path)
        
        # 直接查找完全匹配的文件名
        for doc_id, status_info in doc_status.items():
            if isinstance(status_info, dict) and status_info.get('file_name') == filename:
                return doc_id
                
        # 如果没有找到，尝试模糊匹配
        for doc_id, status_info in doc_status.items():
            if isinstance(status_info, dict):
                stored_filename = status_info.get('file_name', '')
                if filename in stored_filename or stored_filename in filename:
                    return doc_id
        
        return None
    
    def check_document_consistency(self, doc_id: str) -> Dict:
        """检查特定文档的数据一致性"""
        doc_status = self.load_json(self.doc_status_path)
        full_docs = self.load_json(self.full_docs_path)
        vdb_chunks = self.load_json(self.vdb_chunks_path)
        
        status_info = doc_status.get(doc_id, {})
        full_doc = full_docs.get(doc_id, None)
        
        # 统计chunks
        chunk_count = 0
        if isinstance(vdb_chunks, dict) and 'data' in vdb_chunks:
            # LightRAG的vdb_chunks格式是 {"embedding_dim": ..., "data": [...]}
            chunks_data = vdb_chunks.get('data', [])
            if isinstance(chunks_data, list):
                chunk_count = len([chunk for chunk in chunks_data if chunk.get('full_doc_id') == doc_id])
        elif isinstance(vdb_chunks, list):
            # 兼容其他格式
            chunk_count = len([chunk for chunk in vdb_chunks if chunk.get('metadata', {}).get('doc_id') == doc_id or chunk.get('full_doc_id') == doc_id])
        elif isinstance(vdb_chunks, dict):
            # 兼容字典格式
            chunk_count = len([chunk for chunk in vdb_chunks.values() if isinstance(chunk, dict) and (chunk.get('metadata', {}).get('doc_id') == doc_id or chunk.get('full_doc_id') == doc_id)])
        
        return {
            "doc_id": doc_id,
            "status": status_info.get('status', 'unknown'),
            "file_name": status_info.get('file_path', status_info.get('file_name', 'unknown')),
            "has_full_doc": full_doc is not None,
            "chunk_count": chunk_count,
            "has_parsing_output": self._check_parsing_output(status_info.get('file_path', status_info.get('file_name', '')))
        }
    
    def _check_parsing_output(self, filename: str) -> bool:
        """检查是否存在解析输出"""
        if not filename:
            return False
        
        # 查找content_list.json文件 - 支持多种路径结构
        base_name = filename.replace('.pdf', '')
        folder_paths = [
            os.path.join(self.output_dir, base_name),
            os.path.join(self.output_dir, base_name, 'auto'),
            os.path.join(self.output_dir, base_name, base_name, 'auto'),
        ]
        
        content_list_files = [
            'content_list.json',
            f'{base_name}_content_list.json'
        ]
        
        for folder_path in folder_paths:
            for filename_pattern in content_list_files:
                potential_path = os.path.join(folder_path, filename_pattern)
                if os.path.exists(potential_path):
                    return True
            
        return False
    
    def find_inconsistent_documents(self) -> Tuple[List[Dict], List[Dict]]:
        """
        查找所有数据不一致的文档
        
        Returns:
            (failed_docs, recoverable_docs)
        """
        doc_status = self.load_json(self.doc_status_path)
        
        failed_docs = []
        recoverable_docs = []
        
        for doc_id, status_info in doc_status.items():
            if isinstance(status_info, dict):
                consistency = self.check_document_consistency(doc_id)
                
                if consistency['status'] == 'failed' or not consistency['has_full_doc']:
                    doc_info = {
                        'doc_id': doc_id,
                        'file_name': status_info.get('file_path', status_info.get('file_name', 'unknown')),
                        'status': consistency['status'],
                        'has_parsing_output': consistency['has_parsing_output'],
                        'chunk_count': consistency['chunk_count']
                    }
                    
                    if consistency['has_parsing_output']:
                        # 可恢复 - 有解析输出可以重新导入
                        file_name = status_info.get('file_path', status_info.get('file_name', ''))
                        content_summary = self._get_content_summary(file_name)
                        doc_info['content_summary'] = content_summary
                        doc_info['error'] = f"Document content not found in full_docs for doc_id: {doc_id}"
                        recoverable_docs.append(doc_info)
                    else:
                        # 不可恢复 - 需要重新解析
                        doc_info['error'] = "No parsing output found - requires re-parsing"
                        failed_docs.append(doc_info)
        
        return failed_docs, recoverable_docs
    
    def _get_content_summary(self, filename: str) -> str:
        """获取文档内容摘要（从解析输出）"""
        if not filename:
            return "无法获取内容摘要"
            
        # 查找content_list.json文件 - 支持多种路径结构
        base_name = filename.replace('.pdf', '')
        folder_paths = [
            os.path.join(self.output_dir, base_name),
            os.path.join(self.output_dir, base_name, 'auto'),
            os.path.join(self.output_dir, base_name, base_name, 'auto'),
        ]
        
        content_list_files = [
            'content_list.json',
            f'{base_name}_content_list.json'
        ]
        
        content_list_path = None
        for folder_path in folder_paths:
            for filename_pattern in content_list_files:
                potential_path = os.path.join(folder_path, filename_pattern)
                if os.path.exists(potential_path):
                    content_list_path = potential_path
                    break
            if content_list_path:
                break
        
        if content_list_path and os.path.exists(content_list_path):
            try:
                with open(content_list_path, 'r', encoding='utf-8') as f:
                    content_list = json.load(f)
                
                # 提取前几段文本作为摘要
                text_parts = []
                for item in content_list[:5]:  # 只取前5项
                    if item.get('type') == 'text' and item.get('text'):
                        text = item['text'].strip()
                        if text and len(text) > 10:  # 忽略太短的文本
                            text_parts.append(text[:200])  # 限制长度
                
                return '\n\n'.join(text_parts[:3])  # 只返回前3段
                
            except Exception as e:
                self.logger.error(f"读取content_list失败 {content_list_path}: {e}")
                return "内容摘要获取失败"
        
        return "未找到解析输出文件"
    
    async def repair_document(self, doc_id: str, rag) -> bool:
        """修复特定文档的数据一致性问题"""
        try:
            doc_status = self.load_json(self.doc_status_path)
            status_info = doc_status.get(doc_id, {})
            filename = status_info.get('file_path', status_info.get('file_name', ''))
            
            if not filename:
                self.logger.error(f"无法找到doc_id {doc_id}对应的文件名")
                return False
            
            # 查找content_list.json文件 - 支持多种路径结构
            base_name = filename.replace('.pdf', '')
            folder_paths = [
                os.path.join(self.output_dir, base_name),
                os.path.join(self.output_dir, base_name, 'auto'),
                os.path.join(self.output_dir, base_name, base_name, 'auto'),
            ]
            
            content_list_files = [
                'content_list.json',
                f'{base_name}_content_list.json'
            ]
            
            content_list_path = None
            for folder_path in folder_paths:
                for filename_pattern in content_list_files:
                    potential_path = os.path.join(folder_path, filename_pattern)
                    if os.path.exists(potential_path):
                        content_list_path = potential_path
                        break
                if content_list_path:
                    break
            
            if not content_list_path or not os.path.exists(content_list_path):
                self.logger.error(f"未找到解析输出: 已查找路径 {folder_paths}")
                return False
            
            # 加载content_list
            with open(content_list_path, 'r', encoding='utf-8') as f:
                content_list = json.load(f)
            
            self.logger.info(f"开始修复文档: {filename}, 内容块数量: {len(content_list)}")
            
            # 先清理旧的doc_id记录，然后重新插入
            # 删除旧的doc_id记录
            if hasattr(rag.lightrag, 'doc_status') and doc_id in rag.lightrag.doc_status:
                del rag.lightrag.doc_status[doc_id]
            
            # 重新使用insert_content_list，它会生成新的doc_id
            await rag.insert_content_list(content_list, filename)
            
            self.logger.info(f"成功修复文档: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"修复文档 {doc_id} 失败: {e}")
            return False
    
    def generate_report(self) -> Dict:
        """生成完整的数据一致性报告"""
        failed_docs, recoverable_docs = self.find_inconsistent_documents()
        
        doc_status = self.load_json(self.doc_status_path)
        total_docs = len(doc_status)
        successful_docs = total_docs - len(failed_docs) - len(recoverable_docs)
        
        report = {
            "summary": {
                "total_documents": total_docs,
                "successful_documents": successful_docs,
                "failed_documents": len(failed_docs),
                "recoverable_documents": len(recoverable_docs)
            },
            "failed_docs": failed_docs,
            "recoverable_docs": recoverable_docs
        }
        
        return report


def main():
    """主函数 - 生成数据一致性报告"""
    if len(sys.argv) < 3:
        print("用法: python data_consistency_checker.py <rag_storage_dir> <output_dir>")
        sys.exit(1)
    
    rag_storage_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    checker = RAGDataConsistencyChecker(rag_storage_dir, output_dir)
    report = checker.generate_report()
    
    print("=== RAG数据一致性检查报告 ===")
    print(f"总文档数: {report['summary']['total_documents']}")
    print(f"正常文档: {report['summary']['successful_documents']}")
    print(f"失败文档: {report['summary']['failed_documents']}")
    print(f"可恢复文档: {report['summary']['recoverable_documents']}")
    
    if report['recoverable_docs']:
        print("\n可恢复的文档:")
        for doc in report['recoverable_docs']:
            print(f"  - {doc['file_name']} (doc_id: {doc['doc_id']})")
    
    if report['failed_docs']:
        print("\n需要重新解析的文档:")
        for doc in report['failed_docs']:
            print(f"  - {doc['file_name']} (doc_id: {doc['doc_id']})")
    
    # 保存详细报告
    with open('data_consistency_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print("\n详细报告已保存到: data_consistency_report.json")


if __name__ == "__main__":
    main()