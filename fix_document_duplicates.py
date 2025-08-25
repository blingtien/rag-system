#!/usr/bin/env python3
"""
文档重复问题一键修复脚本
集成所有修复工具，提供简单的命令行界面
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path

# 添加API路径
sys.path.append(str(Path(__file__).parent / "RAG-Anything" / "api"))

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('document_repair.log')
        ]
    )
    return logging.getLogger(__name__)

def main():
    """主修复流程"""
    logger = setup_logging()
    
    print("=" * 60)
    print("🛠️  RAG文档重复问题修复工具")
    print("=" * 60)
    
    try:
        # 导入修复工具
        from utils.document_deduplicator import DocumentDeduplicator
        from utils.storage_consistency_repair import StorageConsistencyRepairer
        from utils.atomic_document_processor import AtomicDocumentProcessor
        
        storage_dir = "./rag_storage"
        
        print(f"\n📁 工作目录: {storage_dir}")
        print(f"📅 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 步骤1: 分析当前状态
        print("\n🔍 步骤1: 分析当前存储状态...")
        repairer = StorageConsistencyRepairer(storage_dir)
        analysis = repairer.analyze_consistency()
        
        print(f"   API文档数: {analysis['file_counts']['api_documents']}")
        print(f"   状态记录数: {analysis['file_counts']['doc_status']}")
        print(f"   完整文档数: {analysis['file_counts']['full_docs']}")
        
        total_issues = sum(len(issues) for issues in analysis['inconsistencies'].values() if issues)
        print(f"   发现问题数: {total_issues}")
        
        if total_issues == 0:
            print("✅ 未发现存储一致性问题！")
        else:
            print("⚠️  发现存储不一致性问题:")
            for issue_type, issues in analysis['inconsistencies'].items():
                if issues:
                    print(f"     {issue_type}: {len(issues)} 项")
        
        # 步骤2: 检查重复文档
        print("\n🔍 步骤2: 检查重复文档...")
        deduplicator = DocumentDeduplicator(storage_dir)
        
        # 为现有文档添加哈希
        hash_result = deduplicator.add_hash_to_documents(dry_run=False)
        print(f"   处理文档: {hash_result['processed_documents']}")
        print(f"   添加哈希: {hash_result['successful_hashes']}")
        print(f"   已有哈希: {hash_result['already_have_hash']}")
        
        # 查找重复文档
        content_duplicates = deduplicator.find_duplicates_by_content()
        filename_duplicates = deduplicator.find_duplicates_by_filename()
        
        print(f"   内容重复组: {len(content_duplicates)}")
        print(f"   文件名重复组: {len(filename_duplicates)}")
        
        total_duplicate_docs = sum(len(docs) - 1 for docs in content_duplicates.values())
        print(f"   可移除重复文档: {total_duplicate_docs}")
        
        # 询问用户是否继续
        if total_issues > 0 or total_duplicate_docs > 0:
            print(f"\n⚠️  发现问题:")
            print(f"   - 存储不一致性: {total_issues} 项")
            print(f"   - 重复文档: {total_duplicate_docs} 个")
            
            response = input("\n是否继续修复这些问题? (y/N): ").lower().strip()
            if response != 'y':
                print("❌ 用户取消，退出修复")
                return
        
        # 步骤3: 修复存储一致性
        if total_issues > 0:
            print("\n🔧 步骤3: 修复存储一致性...")
            repair_result = repairer.full_consistency_repair(dry_run=False)
            
            steps = repair_result.get('steps', {})
            print(f"   修复rag_doc_id: {steps.get('repair_missing_rag_ids', {}).get('repaired', 0)}")
            print(f"   清理孤立条目: {steps.get('clean_orphaned_entries', {}).get('total_cleaned', 0)}")
            print(f"   同步状态: {steps.get('synchronize_status_docs', {}).get('total_synced', 0)}")
            print(f"   标准化路径: {steps.get('standardize_paths', {}).get('standardized', 0)}")
        
        # 步骤4: 移除重复文档
        if total_duplicate_docs > 0:
            print("\n🗑️  步骤4: 移除重复文档...")
            removal_result = deduplicator.remove_duplicate_documents(content_duplicates, dry_run=False)
            
            print(f"   移除重复文档: {removal_result['total_documents_removed']}")
            print(f"   保留最佳文档: {len(removal_result['kept_documents'])}")
            
            # 显示移除的文档详情
            if removal_result['removed_documents']:
                print("   移除的文档:")
                for doc in removal_result['removed_documents'][:5]:  # 只显示前5个
                    print(f"     - {doc['filename']} ({doc['status']})")
                if len(removal_result['removed_documents']) > 5:
                    print(f"     ... 还有 {len(removal_result['removed_documents']) - 5} 个")
        
        # 步骤5: 生成修复报告
        print("\n📋 步骤5: 生成修复报告...")
        
        final_analysis = repairer.analyze_consistency()
        final_duplicates = deduplicator.find_duplicates_by_content()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'repair_summary': {
                'initial_issues': total_issues,
                'initial_duplicates': total_duplicate_docs,
                'final_issues': sum(len(issues) for issues in final_analysis['inconsistencies'].values() if issues),
                'final_duplicates': sum(len(docs) - 1 for docs in final_duplicates.values()),
                'consistency_repair': repair_result if total_issues > 0 else None,
                'duplicate_removal': removal_result if total_duplicate_docs > 0 else None
            },
            'final_state': {
                'api_documents': final_analysis['file_counts']['api_documents'],
                'doc_status': final_analysis['file_counts']['doc_status'],
                'full_docs': final_analysis['file_counts']['full_docs']
            }
        }
        
        report_file = f"document_repair_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"   修复报告已保存: {report_file}")
        
        # 最终状态
        print("\n✅ 修复完成!")
        print(f"   最终API文档数: {final_analysis['file_counts']['api_documents']}")
        print(f"   最终状态记录数: {final_analysis['file_counts']['doc_status']}")
        print(f"   最终完整文档数: {final_analysis['file_counts']['full_docs']}")
        print(f"   剩余问题数: {sum(len(issues) for issues in final_analysis['inconsistencies'].values() if issues)}")
        print(f"   剩余重复文档: {sum(len(docs) - 1 for docs in final_duplicates.values())}")
        
        if sum(len(issues) for issues in final_analysis['inconsistencies'].values() if issues) == 0:
            print("🎉 所有存储一致性问题已解决!")
        
        if sum(len(docs) - 1 for docs in final_duplicates.values()) == 0:
            print("🎉 所有重复文档已清理!")
        
        print("\n📝 建议:")
        print("   1. 重启API服务器以确保更改生效")
        print("   2. 定期运行此工具检查和修复问题")
        print("   3. 查看修复日志了解详细信息")
        
    except ImportError as e:
        print(f"❌ 导入修复工具失败: {e}")
        print("请确保在RAG-Anything项目目录中运行此脚本")
        sys.exit(1)
    except Exception as e:
        logger.error(f"修复过程中发生错误: {e}")
        print(f"❌ 修复失败: {e}")
        print("请查看 document_repair.log 了解详细错误信息")
        sys.exit(1)

if __name__ == "__main__":
    main()