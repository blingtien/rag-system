
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
    