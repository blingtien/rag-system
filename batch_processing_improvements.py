#!/usr/bin/env python3
"""
批量处理改进方案
增强批量处理的错误检测和数据一致性验证
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class EnhancedBatchProcessor:
    """增强的批量处理器，包含数据一致性验证"""
    
    def __init__(self, rag_storage_dir: str):
        self.rag_storage_dir = Path(rag_storage_dir)
        
    async def verify_document_consistency(self, doc_id: str, file_path: str) -> Dict:
        """验证单个文档的数据一致性"""
        verification_result = {
            "doc_id": doc_id,
            "file_path": file_path,
            "is_consistent": True,
            "missing_components": [],
            "errors": [],
            "verification_timestamp": datetime.now().isoformat()
        }
        
        try:
            # 检查doc_status
            doc_status_file = self.rag_storage_dir / "kv_store_doc_status.json"
            if doc_status_file.exists():
                with open(doc_status_file, 'r', encoding='utf-8') as f:
                    doc_status = json.load(f)
                
                if doc_id not in doc_status:
                    verification_result["missing_components"].append("doc_status")
                    verification_result["is_consistent"] = False
                elif doc_status[doc_id].get("status") != "processed":
                    verification_result["errors"].append(
                        f"Document status is '{doc_status[doc_id].get('status')}', expected 'processed'"
                    )
                    verification_result["is_consistent"] = False
            
            # 检查full_docs
            full_docs_file = self.rag_storage_dir / "kv_store_full_docs.json"
            if full_docs_file.exists():
                with open(full_docs_file, 'r', encoding='utf-8') as f:
                    full_docs = json.load(f)
                
                if doc_id not in full_docs:
                    verification_result["missing_components"].append("full_docs")
                    verification_result["is_consistent"] = False
            
            # 检查chunks
            chunks_file = self.rag_storage_dir / "vdb_chunks.json"
            if chunks_file.exists():
                with open(chunks_file, 'r', encoding='utf-8') as f:
                    chunks_data = json.load(f)
                
                doc_chunks = [c for c in chunks_data.get("data", []) if c.get("full_doc_id") == doc_id]
                if not doc_chunks:
                    verification_result["missing_components"].append("chunks")
                    verification_result["is_consistent"] = False
                    
        except Exception as e:
            verification_result["errors"].append(f"Verification error: {str(e)}")
            verification_result["is_consistent"] = False
            
        return verification_result
    
    async def enhanced_batch_process_with_verification(
        self, 
        file_paths: List[str],
        rag_instance,
        progress_callback=None,
        **kwargs
    ) -> Dict:
        """增强的批量处理，包含一致性验证"""
        
        logger.info(f"开始增强批量处理: {len(file_paths)} 个文件")
        
        results = {
            "total_files": len(file_paths),
            "successful": 0,
            "failed": 0,
            "verified_consistent": 0,
            "verified_inconsistent": 0,
            "processing_results": [],
            "verification_results": [],
            "inconsistent_documents": [],
            "processing_timestamp": datetime.now().isoformat()
        }
        
        # 第一阶段：常规批量处理
        batch_result = await rag_instance.process_folder_complete(
            folder_path=str(Path(file_paths[0]).parent),
            **kwargs
        )
        
        # 第二阶段：验证每个文档的一致性
        logger.info("开始数据一致性验证阶段...")
        
        for i, file_path in enumerate(file_paths):
            try:
                # 生成文档ID (模拟RAG系统的ID生成逻辑)
                import hashlib
                doc_id = f"doc-{hashlib.md5(file_path.encode()).hexdigest()}"
                
                # 验证文档一致性
                verification = await self.verify_document_consistency(doc_id, file_path)
                results["verification_results"].append(verification)
                
                if verification["is_consistent"]:
                    results["verified_consistent"] += 1
                    results["successful"] += 1
                else:
                    results["verified_inconsistent"] += 1
                    results["failed"] += 1
                    results["inconsistent_documents"].append({
                        "file_path": file_path,
                        "doc_id": doc_id,
                        "missing_components": verification["missing_components"],
                        "errors": verification["errors"]
                    })
                    
                    logger.warning(f"数据不一致检测: {Path(file_path).name}")
                    for error in verification["errors"]:
                        logger.warning(f"  - {error}")
                
                # 进度回调
                if progress_callback:
                    await progress_callback({
                        "stage": "verification",
                        "current": i + 1,
                        "total": len(file_paths),
                        "progress": (i + 1) / len(file_paths) * 100,
                        "current_file": Path(file_path).name,
                        "is_consistent": verification["is_consistent"]
                    })
                    
            except Exception as e:
                logger.error(f"验证文档失败 {file_path}: {str(e)}")
                results["failed"] += 1
                results["inconsistent_documents"].append({
                    "file_path": file_path,
                    "doc_id": "unknown",
                    "errors": [f"Verification failed: {str(e)}"]
                })
        
        logger.info(f"批量处理完成: {results['successful']} 成功, {results['failed']} 失败")
        logger.info(f"一致性验证: {results['verified_consistent']} 一致, {results['verified_inconsistent']} 不一致")
        
        return results

def create_improved_batch_endpoint_patch():
    """创建改进的批量处理端点补丁"""
    
    patch_code = '''
# 在 /api/v1/documents/process/batch 端点中的改进

async def process_documents_batch_enhanced(request: BatchProcessRequest):
    """增强的批量文档处理端点 - 包含数据一致性验证"""
    
    # ... 现有的初始化代码 ...
    
    try:
        # 使用增强的批量处理器
        enhanced_processor = EnhancedBatchProcessor(WORKING_DIR)
        
        # 执行增强的批量处理
        enhanced_result = await enhanced_processor.enhanced_batch_process_with_verification(
            file_paths=file_paths,
            rag_instance=rag,
            progress_callback=websocket_progress_callback,
            output_dir=OUTPUT_DIR,
            parse_method=parse_method,
            max_workers=max_workers,
            recursive=False,
            show_progress=True,
            lang="en",
            device=device_type
        )
        
        # 处理结果，重点关注不一致的文档
        for file_path in file_paths:
            doc_info = path_to_doc[file_path]
            document_id = doc_info["document_id"]
            document = doc_info["document"]
            task_id = doc_info["task_id"]
            
            # 检查该文件的一致性验证结果
            file_verification = next(
                (v for v in enhanced_result["verification_results"] if v["file_path"] == file_path),
                None
            )
            
            if file_verification and file_verification["is_consistent"]:
                # 一致性验证通过
                document["status"] = "completed"
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["completed_at"] = datetime.now().isoformat()
                
                results.append({
                    "document_id": document_id,
                    "file_name": document["file_name"],
                    "status": "success",
                    "message": "文档批量处理成功并通过一致性验证",
                    "task_id": task_id,
                    "verification_passed": True
                })
                started_count += 1
            else:
                # 一致性验证失败
                error_details = []
                if file_verification:
                    error_details = file_verification.get("errors", [])
                    missing_components = file_verification.get("missing_components", [])
                    if missing_components:
                        error_details.append(f"缺失组件: {', '.join(missing_components)}")
                
                error_msg = f"数据一致性验证失败: {'; '.join(error_details)}"
                
                document["status"] = "failed"
                document["error_category"] = "data_inconsistency"
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = error_msg
                tasks[task_id]["updated_at"] = datetime.now().isoformat()
                
                results.append({
                    "document_id": document_id,
                    "file_name": document["file_name"],
                    "status": "failed",
                    "message": error_msg,
                    "task_id": task_id,
                    "verification_passed": False,
                    "missing_components": file_verification.get("missing_components", []) if file_verification else []
                })
                failed_count += 1
        
        # 生成详细报告
        response_data = {
            "success": failed_count == 0,
            "started_count": started_count,
            "failed_count": failed_count,
            "total_requested": len(request.document_ids),
            "results": results,
            "batch_operation_id": batch_operation_id,
            "message": f"增强批量处理完成: {started_count} 个成功, {failed_count} 个失败",
            "verification_summary": {
                "verified_consistent": enhanced_result["verified_consistent"],
                "verified_inconsistent": enhanced_result["verified_inconsistent"],
                "inconsistent_documents": len(enhanced_result["inconsistent_documents"])
            }
        }
        
        # 如果有不一致的文档，记录详细信息
        if enhanced_result["inconsistent_documents"]:
            await send_processing_log(
                f"⚠️  发现 {len(enhanced_result['inconsistent_documents'])} 个数据不一致的文档", 
                "warning"
            )
            
            # 自动生成修复建议
            await send_processing_log(
                f"💡 建议运行数据一致性检查器进行修复: python data_consistency_checker.py", 
                "info"
            )
        
        return BatchProcessResponse(**response_data)
        
    except Exception as e:
        # 现有的错误处理逻辑...
        pass
    '''
    
    return patch_code

if __name__ == "__main__":
    # 生成改进方案的示例代码
    patch_code = create_improved_batch_endpoint_patch()
    
    with open("batch_processing_endpoint_improvements.py", "w", encoding="utf-8") as f:
        f.write(patch_code)
    
    print("✅ 批量处理改进方案已生成")
    print("📁 文件: batch_processing_endpoint_improvements.py")
    print("🔧 可以参考此代码来改进API端点的批量处理逻辑")