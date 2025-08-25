#!/usr/bin/env python3
"""
存储一致性修复工具
修复API状态、KV存储、向量数据库之间的不一致性问题
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import shutil

logger = logging.getLogger(__name__)

class StorageConsistencyRepairer:
    """存储一致性修复器"""
    
    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir or os.environ.get("WORKING_DIR", "./rag_storage"))
        self.api_state_file = self.storage_dir / "api_documents_state.json"
        self.doc_status_file = self.storage_dir / "kv_store_doc_status.json"
        self.full_docs_file = self.storage_dir / "kv_store_full_docs.json"
        self.text_chunks_file = self.storage_dir / "kv_store_text_chunks.json"
        self.entities_file = self.storage_dir / "kv_store_full_entities.json"
        self.relations_file = self.storage_dir / "kv_store_full_relations.json"
        self.vdb_chunks_file = self.storage_dir / "vdb_chunks.json"
        self.vdb_entities_file = self.storage_dir / "vdb_entities.json"
        self.vdb_relationships_file = self.storage_dir / "vdb_relationships.json"
        
    def load_json_file(self, file_path: Path) -> Dict:
        """安全加载JSON文件"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载文件失败 {file_path}: {e}")
            return {}
    
    def save_json_file(self, data: Dict, file_path: Path, create_backup: bool = True):
        """安全保存JSON文件"""
        try:
            if create_backup and file_path.exists():
                backup_path = file_path.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
                shutil.copy2(file_path, backup_path)
                logger.info(f"已创建备份: {backup_path}")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"文件已保存: {file_path}")
        except Exception as e:
            logger.error(f"保存文件失败 {file_path}: {e}")
    
    def analyze_consistency(self) -> Dict:
        """分析存储系统之间的一致性"""
        logger.info("开始分析存储一致性...")
        
        # 加载所有存储文件
        api_docs_raw = self.load_json_file(self.api_state_file)
        # 处理嵌套的documents结构
        if isinstance(api_docs_raw, dict) and 'documents' in api_docs_raw:
            api_docs = api_docs_raw['documents']
        else:
            api_docs = api_docs_raw
        
        doc_status = self.load_json_file(self.doc_status_file)
        full_docs = self.load_json_file(self.full_docs_file)
        text_chunks = self.load_json_file(self.text_chunks_file)
        entities = self.load_json_file(self.entities_file)
        relations = self.load_json_file(self.relations_file)
        vdb_chunks = self.load_json_file(self.vdb_chunks_file)
        vdb_entities = self.load_json_file(self.vdb_entities_file)
        vdb_relationships = self.load_json_file(self.vdb_relationships_file)
        
        # 提取所有文档ID集合
        api_doc_ids = set(api_docs.keys())
        rag_doc_ids_from_status = set(doc_status.keys())
        rag_doc_ids_from_full_docs = set(full_docs.keys())
        
        # 从API文档中提取rag_doc_id
        rag_doc_ids_from_api = set()
        api_to_rag_mapping = {}
        for api_id, doc_info in api_docs.items():
            rag_id = doc_info.get('rag_doc_id')
            if rag_id:
                rag_doc_ids_from_api.add(rag_id)
                api_to_rag_mapping[api_id] = rag_id
        
        # 分析一致性问题
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'file_counts': {
                'api_documents': len(api_docs),
                'doc_status': len(doc_status),
                'full_docs': len(full_docs),
                'text_chunks': len(text_chunks),
                'entities': len(entities),
                'relations': len(relations),
                'vdb_chunks': len(vdb_chunks),
                'vdb_entities': len(vdb_entities),
                'vdb_relationships': len(vdb_relationships)
            },
            'inconsistencies': {
                'orphaned_api_documents': [],  # API中存在但RAG中不存在
                'orphaned_rag_status': [],     # status中存在但API中不存在
                'orphaned_rag_docs': [],       # full_docs中存在但API中不存在
                'missing_rag_doc_id': [],      # API文档缺少rag_doc_id
                'status_docs_mismatch': [],    # status和full_docs不一致
                'orphaned_chunks': [],         # chunks中存在但文档不存在
                'orphaned_entities': [],       # entities中存在但无对应chunks
                'orphaned_relations': []       # relations中存在但无对应entities
            },
            'repair_recommendations': []
        }
        
        # 检查孤立的API文档
        for api_id in api_doc_ids:
            rag_id = api_to_rag_mapping.get(api_id)
            if not rag_id:
                analysis['inconsistencies']['missing_rag_doc_id'].append(api_id)
            elif rag_id not in rag_doc_ids_from_status and rag_id not in rag_doc_ids_from_full_docs:
                analysis['inconsistencies']['orphaned_api_documents'].append(api_id)
        
        # 检查孤立的RAG status
        for rag_id in rag_doc_ids_from_status:
            if rag_id not in rag_doc_ids_from_api:
                analysis['inconsistencies']['orphaned_rag_status'].append(rag_id)
        
        # 检查孤立的RAG full_docs
        for rag_id in rag_doc_ids_from_full_docs:
            if rag_id not in rag_doc_ids_from_api:
                analysis['inconsistencies']['orphaned_rag_docs'].append(rag_id)
        
        # 检查status和full_docs不一致
        status_vs_docs = rag_doc_ids_from_status.symmetric_difference(rag_doc_ids_from_full_docs)
        analysis['inconsistencies']['status_docs_mismatch'] = list(status_vs_docs)
        
        # 检查孤立的chunks
        valid_rag_ids = rag_doc_ids_from_full_docs
        orphaned_chunks = []
        for chunk_id, chunk_info in text_chunks.items():
            if isinstance(chunk_info, dict):
                chunk_doc_id = chunk_info.get('full_doc_id', '')
                if chunk_doc_id and chunk_doc_id not in valid_rag_ids:
                    orphaned_chunks.append(chunk_id)
        analysis['inconsistencies']['orphaned_chunks'] = orphaned_chunks
        
        # 生成修复建议
        if analysis['inconsistencies']['missing_rag_doc_id']:
            analysis['repair_recommendations'].append(
                "为缺少rag_doc_id的API文档生成新的RAG文档ID"
            )
        
        if analysis['inconsistencies']['orphaned_api_documents']:
            analysis['repair_recommendations'].append(
                "移除孤立的API文档或为其创建对应的RAG条目"
            )
        
        if analysis['inconsistencies']['orphaned_rag_status'] or analysis['inconsistencies']['orphaned_rag_docs']:
            analysis['repair_recommendations'].append(
                "清理孤立的RAG存储条目"
            )
        
        if analysis['inconsistencies']['status_docs_mismatch']:
            analysis['repair_recommendations'].append(
                "同步doc_status和full_docs之间的不一致"
            )
        
        if analysis['inconsistencies']['orphaned_chunks']:
            analysis['repair_recommendations'].append(
                "清理孤立的文本块和相关的向量数据"
            )
        
        return analysis
    
    def repair_missing_rag_doc_ids(self, dry_run: bool = True) -> Dict:
        """修复缺少rag_doc_id的API文档"""
        logger.info(f"修复缺少rag_doc_id的API文档 (dry_run={dry_run})...")
        
        api_docs_raw = self.load_json_file(self.api_state_file)
        # 处理嵌套的documents结构
        if isinstance(api_docs_raw, dict) and 'documents' in api_docs_raw:
            api_docs = api_docs_raw['documents']
        else:
            api_docs = api_docs_raw
            
        repair_report = {
            'processed': 0,
            'repaired': 0,
            'failed': 0,
            'details': []
        }
        
        import uuid
        
        for api_id, doc_info in api_docs.items():
            repair_report['processed'] += 1
            
            if not doc_info.get('rag_doc_id'):
                # 生成新的rag_doc_id
                new_rag_id = str(uuid.uuid4())
                
                if not dry_run:
                    api_docs[api_id]['rag_doc_id'] = new_rag_id
                
                repair_report['repaired'] += 1
                repair_report['details'].append({
                    'api_id': api_id,
                    'filename': doc_info.get('filename', ''),
                    'new_rag_id': new_rag_id
                })
                logger.info(f"为文档 {doc_info.get('filename', api_id)} 生成RAG ID: {new_rag_id}")
        
        if not dry_run and repair_report['repaired'] > 0:
            # 保持原有的嵌套结构
            data_to_save = {"documents": api_docs}
            self.save_json_file(data_to_save, self.api_state_file)
        
        return repair_report
    
    def clean_orphaned_rag_entries(self, dry_run: bool = True) -> Dict:
        """清理孤立的RAG条目"""
        logger.info(f"清理孤立的RAG条目 (dry_run={dry_run})...")
        
        api_docs_raw = self.load_json_file(self.api_state_file)
        # 处理嵌套的documents结构
        if isinstance(api_docs_raw, dict) and 'documents' in api_docs_raw:
            api_docs = api_docs_raw['documents']
        else:
            api_docs = api_docs_raw
            
        doc_status = self.load_json_file(self.doc_status_file)
        full_docs = self.load_json_file(self.full_docs_file)
        text_chunks = self.load_json_file(self.text_chunks_file)
        
        # 获取有效的rag_doc_id集合
        valid_rag_ids = set()
        for doc_info in api_docs.values():
            rag_id = doc_info.get('rag_doc_id')
            if rag_id:
                valid_rag_ids.add(rag_id)
        
        cleanup_report = {
            'orphaned_status': [],
            'orphaned_full_docs': [],
            'orphaned_chunks': [],
            'total_cleaned': 0
        }
        
        # 清理孤立的doc_status条目
        orphaned_status_ids = []
        for rag_id in doc_status.keys():
            if rag_id not in valid_rag_ids:
                orphaned_status_ids.append(rag_id)
        
        for rag_id in orphaned_status_ids:
            cleanup_report['orphaned_status'].append(rag_id)
            if not dry_run:
                del doc_status[rag_id]
        
        # 清理孤立的full_docs条目
        orphaned_full_doc_ids = []
        for rag_id in full_docs.keys():
            if rag_id not in valid_rag_ids:
                orphaned_full_doc_ids.append(rag_id)
        
        for rag_id in orphaned_full_doc_ids:
            cleanup_report['orphaned_full_docs'].append(rag_id)
            if not dry_run:
                del full_docs[rag_id]
        
        # 清理孤立的text_chunks条目
        orphaned_chunk_ids = []
        for chunk_id, chunk_info in text_chunks.items():
            if isinstance(chunk_info, dict):
                chunk_doc_id = chunk_info.get('full_doc_id', '')
                if chunk_doc_id and chunk_doc_id not in valid_rag_ids:
                    orphaned_chunk_ids.append(chunk_id)
        
        for chunk_id in orphaned_chunk_ids:
            cleanup_report['orphaned_chunks'].append(chunk_id)
            if not dry_run:
                del text_chunks[chunk_id]
        
        cleanup_report['total_cleaned'] = (
            len(cleanup_report['orphaned_status']) +
            len(cleanup_report['orphaned_full_docs']) +
            len(cleanup_report['orphaned_chunks'])
        )
        
        if not dry_run and cleanup_report['total_cleaned'] > 0:
            self.save_json_file(doc_status, self.doc_status_file)
            self.save_json_file(full_docs, self.full_docs_file)
            self.save_json_file(text_chunks, self.text_chunks_file)
        
        logger.info(f"清理报告: 状态条目={len(cleanup_report['orphaned_status'])}, "
                   f"文档条目={len(cleanup_report['orphaned_full_docs'])}, "
                   f"文本块={len(cleanup_report['orphaned_chunks'])}")
        
        return cleanup_report
    
    def synchronize_status_and_docs(self, dry_run: bool = True) -> Dict:
        """同步doc_status和full_docs"""
        logger.info(f"同步doc_status和full_docs (dry_run={dry_run})...")
        
        doc_status = self.load_json_file(self.doc_status_file)
        full_docs = self.load_json_file(self.full_docs_file)
        
        sync_report = {
            'added_to_status': [],
            'added_to_full_docs': [],
            'total_synced': 0
        }
        
        # 将full_docs中存在但doc_status中不存在的条目添加到doc_status
        for rag_id in full_docs.keys():
            if rag_id not in doc_status:
                sync_report['added_to_status'].append(rag_id)
                if not dry_run:
                    doc_status[rag_id] = "completed"  # 假设存在于full_docs中的都是已完成的
        
        # 将doc_status中存在但full_docs中不存在的条目从doc_status中移除
        # (这些通常是处理失败的文档)
        orphaned_status = []
        for rag_id in list(doc_status.keys()):
            if rag_id not in full_docs:
                # 只有当状态不是"completed"时才移除，已完成的可能是数据丢失
                if doc_status[rag_id] != "completed":
                    orphaned_status.append(rag_id)
                    if not dry_run:
                        del doc_status[rag_id]
        
        sync_report['total_synced'] = len(sync_report['added_to_status']) + len(orphaned_status)
        
        if not dry_run and sync_report['total_synced'] > 0:
            self.save_json_file(doc_status, self.doc_status_file)
        
        logger.info(f"同步报告: 添加到状态={len(sync_report['added_to_status'])}, "
                   f"移除孤立状态={len(orphaned_status)}")
        
        return sync_report
    
    def standardize_file_paths(self, dry_run: bool = True) -> Dict:
        """标准化文件路径"""
        logger.info(f"标准化文件路径 (dry_run={dry_run})...")
        
        api_docs_raw = self.load_json_file(self.api_state_file)
        # 处理嵌套的documents结构
        if isinstance(api_docs_raw, dict) and 'documents' in api_docs_raw:
            api_docs = api_docs_raw['documents']
        else:
            api_docs = api_docs_raw
            
        base_path = "/home/ragsvr/projects/ragsystem"
        
        standardize_report = {
            'processed': 0,
            'standardized': 0,
            'already_absolute': 0,
            'details': []
        }
        
        for api_id, doc_info in api_docs.items():
            standardize_report['processed'] += 1
            file_path = doc_info.get('file_path', '')
            
            if file_path:
                if os.path.isabs(file_path):
                    standardize_report['already_absolute'] += 1
                else:
                    # 转换相对路径为绝对路径
                    normalized_path = os.path.join(base_path, file_path.lstrip('./'))
                    
                    if not dry_run:
                        api_docs[api_id]['file_path'] = normalized_path
                    
                    standardize_report['standardized'] += 1
                    standardize_report['details'].append({
                        'api_id': api_id,
                        'filename': doc_info.get('filename', ''),
                        'old_path': file_path,
                        'new_path': normalized_path
                    })
                    logger.info(f"标准化路径: {file_path} -> {normalized_path}")
        
        if not dry_run and standardize_report['standardized'] > 0:
            # 保持原有的嵌套结构
            data_to_save = {"documents": api_docs}
            self.save_json_file(data_to_save, self.api_state_file)
        
        return standardize_report
    
    def full_consistency_repair(self, dry_run: bool = True) -> Dict:
        """执行完整的一致性修复"""
        logger.info(f"开始完整一致性修复 (dry_run={dry_run})...")
        
        full_report = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': dry_run,
            'steps': {}
        }
        
        try:
            # 步骤1: 修复缺少的rag_doc_id
            full_report['steps']['repair_missing_rag_ids'] = self.repair_missing_rag_doc_ids(dry_run)
            
            # 步骤2: 清理孤立的RAG条目
            full_report['steps']['clean_orphaned_entries'] = self.clean_orphaned_rag_entries(dry_run)
            
            # 步骤3: 同步状态和文档
            full_report['steps']['synchronize_status_docs'] = self.synchronize_status_and_docs(dry_run)
            
            # 步骤4: 标准化文件路径
            full_report['steps']['standardize_paths'] = self.standardize_file_paths(dry_run)
            
            # 步骤5: 生成修复后的分析报告
            full_report['final_analysis'] = self.analyze_consistency()
            
        except Exception as e:
            logger.error(f"修复过程中发生错误: {e}")
            full_report['error'] = str(e)
        
        return full_report


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='RAG存储一致性修复工具')
    parser.add_argument('--storage-dir', default=None, help='存储目录路径')
    parser.add_argument('--action', choices=['analyze', 'repair-ids', 'clean-orphaned', 
                                           'sync-status', 'standardize-paths', 'full-repair'],
                       default='analyze', help='执行的操作')
    parser.add_argument('--dry-run', action='store_true', default=True, help='模拟运行')
    parser.add_argument('--execute', action='store_true', help='实际执行修改')
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    repairer = StorageConsistencyRepairer(args.storage_dir)
    dry_run = not args.execute
    
    if args.action == 'analyze':
        analysis = repairer.analyze_consistency()
        print("\n" + "="*60)
        print("🔍 RAG存储一致性分析报告")
        print("="*60)
        print(f"API文档: {analysis['file_counts']['api_documents']}")
        print(f"状态记录: {analysis['file_counts']['doc_status']}")
        print(f"完整文档: {analysis['file_counts']['full_docs']}")
        print(f"文本块: {analysis['file_counts']['text_chunks']}")
        print("\n🚨 发现的不一致性:")
        for issue, items in analysis['inconsistencies'].items():
            if items:
                print(f"  {issue}: {len(items)} 项")
        
        print(f"\n💡 修复建议:")
        for i, recommendation in enumerate(analysis['repair_recommendations'], 1):
            print(f"  {i}. {recommendation}")
        
        # 保存分析报告
        report_file = repairer.storage_dir / f"consistency_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        print(f"\n📋 详细报告已保存: {report_file}")
    
    elif args.action == 'full-repair':
        result = repairer.full_consistency_repair(dry_run)
        print("\n" + "="*60)
        print("🔧 完整一致性修复报告")
        print("="*60)
        
        for step, report in result.get('steps', {}).items():
            print(f"\n📋 {step}:")
            if isinstance(report, dict):
                for key, value in report.items():
                    if isinstance(value, (int, str)):
                        print(f"  {key}: {value}")
        
        if dry_run:
            print("\n⚠️  这是模拟运行。使用 --execute 执行实际修复。")
    
    else:
        # 执行单个操作
        if args.action == 'repair-ids':
            result = repairer.repair_missing_rag_doc_ids(dry_run)
        elif args.action == 'clean-orphaned':
            result = repairer.clean_orphaned_rag_entries(dry_run)
        elif args.action == 'sync-status':
            result = repairer.synchronize_status_and_docs(dry_run)
        elif args.action == 'standardize-paths':
            result = repairer.standardize_file_paths(dry_run)
        
        print(f"\n✅ {args.action} 完成:")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()