#!/usr/bin/env python3
"""
文档去重集成补丁
为现有的RAG API服务器集成去重功能
"""

import os
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class APIServerPatcher:
    """API服务器补丁器"""
    
    def __init__(self, api_server_file: str = None):
        self.api_server_file = Path(api_server_file or "rag_api_server.py")
        self.backup_file = self.api_server_file.with_suffix(".backup")
    
    def create_backup(self):
        """创建备份文件"""
        if self.api_server_file.exists():
            import shutil
            shutil.copy2(self.api_server_file, self.backup_file)
            logger.info(f"已创建备份: {self.backup_file}")
    
    def apply_patches(self):
        """应用补丁"""
        logger.info("开始应用去重集成补丁...")
        
        if not self.api_server_file.exists():
            logger.error(f"API服务器文件不存在: {self.api_server_file}")
            return False
        
        # 创建备份
        self.create_backup()
        
        try:
            # 读取原文件
            with open(self.api_server_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 应用各个补丁
            content = self._patch_imports(content)
            content = self._patch_upload_endpoints(content)
            content = self._patch_health_endpoints(content)
            content = self._patch_cleanup_endpoints(content)
            
            # 写入修改后的文件
            with open(self.api_server_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info("补丁应用完成")
            return True
            
        except Exception as e:
            logger.error(f"应用补丁失败: {e}")
            # 恢复备份
            if self.backup_file.exists():
                import shutil
                shutil.copy2(self.backup_file, self.api_server_file)
                logger.info("已恢复原文件")
            return False
    
    def _patch_imports(self, content: str) -> str:
        """添加新的导入语句"""
        logger.info("应用导入补丁...")
        
        # 找到导入安全文件处理器的行
        secure_handler_import = "from utils.secure_file_handler import get_secure_file_handler"
        
        if secure_handler_import in content:
            # 在其后添加新的导入
            new_imports = """from utils.secure_file_handler import get_secure_file_handler
# 导入增强的上传处理器（集成去重功能）
from utils.enhanced_upload_handler import get_enhanced_upload_handler
from utils.document_deduplicator import DocumentDeduplicator
from utils.atomic_document_processor import AtomicDocumentProcessor
from utils.storage_consistency_repair import StorageConsistencyRepairer"""
            
            content = content.replace(secure_handler_import, new_imports)
            logger.info("导入补丁已应用")
        else:
            logger.warning("未找到安全文件处理器导入，手动添加导入")
            # 在现有导入后添加
            import_section = content.find("# 导入简化认证机制")
            if import_section != -1:
                insert_point = content.find("\n", import_section) + 1
                new_imports = """
# 导入增强的上传处理器（集成去重功能）
from utils.enhanced_upload_handler import get_enhanced_upload_handler
from utils.document_deduplicator import DocumentDeduplicator
from utils.atomic_document_processor import AtomicDocumentProcessor
from utils.storage_consistency_repair import StorageConsistencyRepairer
"""
                content = content[:insert_point] + new_imports + content[insert_point:]
        
        return content
    
    def _patch_upload_endpoints(self, content: str) -> str:
        """修补上传端点以使用增强处理器"""
        logger.info("应用上传端点补丁...")
        
        # 替换单文档上传端点
        single_upload_pattern = r'(@app\.post\("/api/v1/documents/upload"\)\s+async def upload_document\([^)]+\):[^}]+?return JSONResponse[^}]+?})'
        
        new_single_upload = '''@app.post("/api/v1/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    auto_process: bool = True,
    current_user: str = Depends(get_current_user_optional)
):
    """单文档上传端点 - 使用增强处理器，支持去重"""
    try:
        # 获取增强上传处理器
        enhanced_handler = get_enhanced_upload_handler()
        
        # 处理文件上传（包含去重检查）
        result = await enhanced_handler.process_single_upload(file, auto_process)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": result.get('message', '文件上传成功'),
                "data": {
                    "document_id": result['document_id'],
                    "rag_doc_id": result.get('rag_doc_id'),
                    "filename": result.get('filename', file.filename),
                    "file_size": result.get('file_size'),
                    "file_hash": result.get('file_hash'),
                    "is_duplicate": result['status'] == 'duplicate_found',
                    "auto_process": auto_process
                }
            }
        )
        
    except HTTPException as e:
        logger.error(f"HTTP异常 - 上传文档: {e.detail}")
        raise e
    except Exception as e:
        error_msg = f"上传文档时发生错误: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)'''
        
        if re.search(single_upload_pattern, content, re.DOTALL):
            content = re.sub(single_upload_pattern, new_single_upload, content, flags=re.DOTALL)
            logger.info("单文档上传端点补丁已应用")
        else:
            logger.warning("未找到单文档上传端点模式")
        
        # 替换批量上传端点
        batch_upload_pattern = r'(@app\.post\("/api/v1/documents/upload/batch"[^}]+?return JSONResponse[^}]+?})'
        
        new_batch_upload = '''@app.post("/api/v1/documents/upload/batch", response_model=BatchUploadResponse)
async def upload_documents_batch(
    files: List[UploadFile] = File(...),
    auto_process: bool = True,
    current_user: str = Depends(get_current_user_optional)
):
    """批量文档上传端点 - 使用增强处理器，支持去重和原子性"""
    try:
        # 获取增强上传处理器
        enhanced_handler = get_enhanced_upload_handler()
        
        # 处理批量上传（包含去重检查和事务处理）
        result = await enhanced_handler.process_batch_upload(files, auto_process)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": f"批量上传完成 - 成功: {result['summary']['success_count']}, "
                          f"失败: {result['summary']['failure_count']}, "
                          f"重复: {result['summary']['duplicate_count']}",
                "data": {
                    "batch_id": result['batch_id'],
                    "summary": result['summary'],
                    "successful_uploads": result['successful_uploads'],
                    "failed_uploads": result['failed_uploads'],
                    "duplicate_files": result['duplicate_files']
                }
            }
        )
        
    except HTTPException as e:
        logger.error(f"HTTP异常 - 批量上传: {e.detail}")
        raise e
    except Exception as e:
        error_msg = f"批量上传文档时发生错误: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)'''
        
        if re.search(batch_upload_pattern, content, re.DOTALL):
            content = re.sub(batch_upload_pattern, new_batch_upload, content, flags=re.DOTALL)
            logger.info("批量上传端点补丁已应用")
        else:
            logger.warning("未找到批量上传端点模式")
        
        return content
    
    def _patch_health_endpoints(self, content: str) -> str:
        """添加存储健康检查端点"""
        logger.info("添加存储健康端点...")
        
        # 在现有健康检查端点后添加新端点
        health_endpoint_pattern = r'(@app\.get\("/health"\)[^}]+?return [^}]+?})'
        
        new_endpoints = '''@app.get("/health")
async def health_check():
    """系统健康检查"""
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "message": "RAG-Anything API is running"
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@app.get("/api/v1/system/storage-health")
async def get_storage_health(current_user: str = Depends(get_current_user_optional)):
    """获取存储系统健康状态"""
    try:
        enhanced_handler = get_enhanced_upload_handler()
        health_status = enhanced_handler.check_storage_health()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": health_status
            }
        )
    except Exception as e:
        logger.error(f"检查存储健康状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查存储健康状态失败: {str(e)}")

@app.post("/api/v1/system/repair-storage")
async def repair_storage_consistency(
    dry_run: bool = True,
    current_user: str = Depends(get_current_user_required)
):
    """修复存储一致性问题"""
    try:
        enhanced_handler = get_enhanced_upload_handler()
        repair_result = await enhanced_handler.repair_storage_issues(dry_run)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": repair_result
            }
        )
    except Exception as e:
        logger.error(f"修复存储一致性失败: {e}")
        raise HTTPException(status_code=500, detail=f"修复存储失败: {str(e)}")'''
        
        if re.search(health_endpoint_pattern, content, re.DOTALL):
            content = re.sub(health_endpoint_pattern, new_endpoints, content, flags=re.DOTALL)
            logger.info("存储健康端点补丁已应用")
        else:
            # 如果没找到，在文件末尾添加
            content += "\n\n" + new_endpoints
            logger.info("存储健康端点已添加到文件末尾")
        
        return content
    
    def _patch_cleanup_endpoints(self, content: str) -> str:
        """添加清理端点"""
        logger.info("添加清理端点...")
        
        cleanup_endpoints = '''
@app.post("/api/v1/system/cleanup-duplicates")
async def cleanup_duplicate_documents(
    dry_run: bool = True,
    current_user: str = Depends(get_current_user_required)
):
    """清理重复文档"""
    try:
        deduplicator = DocumentDeduplicator()
        
        # 查找内容重复的文档
        content_duplicates = deduplicator.find_duplicates_by_content()
        
        if not content_duplicates:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": "未发现重复文档",
                    "data": {"duplicates_found": 0}
                }
            )
        
        # 移除重复文档
        removal_result = deduplicator.remove_duplicate_documents(content_duplicates, dry_run)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": f"重复文档清理完成 - {'预览' if dry_run else '实际'}移除 {removal_result['total_documents_removed']} 个文档",
                "data": removal_result
            }
        )
        
    except Exception as e:
        logger.error(f"清理重复文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理重复文档失败: {str(e)}")

@app.post("/api/v1/system/cleanup-files")
async def cleanup_old_files(
    max_age_days: int = 30,
    current_user: str = Depends(get_current_user_required)
):
    """清理旧文件和失败的文档记录"""
    try:
        enhanced_handler = get_enhanced_upload_handler()
        cleanup_result = await enhanced_handler.cleanup_old_files(max_age_days)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": f"清理完成 - 文件: {cleanup_result['files_cleaned']}, 文档: {cleanup_result['documents_cleaned']}",
                "data": cleanup_result
            }
        )
        
    except Exception as e:
        logger.error(f"清理旧文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理旧文件失败: {str(e)}")

@app.get("/api/v1/system/deduplication-report")
async def get_deduplication_report(current_user: str = Depends(get_current_user_optional)):
    """获取去重分析报告"""
    try:
        deduplicator = DocumentDeduplicator()
        report = deduplicator.generate_deduplication_report()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": report
            }
        )
        
    except Exception as e:
        logger.error(f"生成去重报告失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成去重报告失败: {str(e)}")
'''
        
        # 在文件末尾添加清理端点
        content += cleanup_endpoints
        logger.info("清理端点已添加")
        
        return content
    
    def generate_usage_guide(self):
        """生成使用指南"""
        guide = """
# 文档去重功能使用指南

## 新增功能

### 1. 自动去重上传
- **端点**: `POST /api/v1/documents/upload`
- **功能**: 上传文件时自动检测重复，基于文件内容哈希
- **参数**: 
  - `file`: 上传的文件
  - `auto_process`: 是否自动处理（默认true）

### 2. 批量上传去重
- **端点**: `POST /api/v1/documents/upload/batch`  
- **功能**: 批量上传时自动去重，支持原子性事务
- **参数**:
  - `files`: 文件列表
  - `auto_process`: 是否自动处理（默认true）

### 3. 存储健康检查
- **端点**: `GET /api/v1/system/storage-health`
- **功能**: 检查存储系统一致性和健康状态
- **返回**: 详细的健康报告和修复建议

### 4. 存储一致性修复
- **端点**: `POST /api/v1/system/repair-storage`
- **功能**: 修复存储不一致性问题
- **参数**: 
  - `dry_run`: 是否预览模式（默认true）

### 5. 重复文档清理
- **端点**: `POST /api/v1/system/cleanup-duplicates`
- **功能**: 清理基于内容的重复文档
- **参数**: 
  - `dry_run`: 是否预览模式（默认true）

### 6. 旧文件清理
- **端点**: `POST /api/v1/system/cleanup-files`
- **功能**: 清理旧的上传文件和失败的文档记录
- **参数**: 
  - `max_age_days`: 最大保留天数（默认30）

### 7. 去重分析报告
- **端点**: `GET /api/v1/system/deduplication-report`
- **功能**: 获取详细的重复文档分析报告

## 使用建议

1. **定期健康检查**: 每天运行存储健康检查
2. **定期清理**: 每周清理重复文档和旧文件
3. **谨慎执行**: 修复和清理操作先用dry_run=true预览
4. **监控日志**: 关注事务日志和错误信息

## 命令行工具

### 文档去重工具
```bash
python -m utils.document_deduplicator --action report
python -m utils.document_deduplicator --action remove-duplicates --execute
```

### 存储一致性修复
```bash
python -m utils.storage_consistency_repair --action analyze
python -m utils.storage_consistency_repair --action full-repair --execute
```

### 原子性处理器测试
```bash
python -m utils.atomic_document_processor --action cleanup
```
"""
        
        guide_file = Path("deduplication_usage_guide.md")
        with open(guide_file, 'w', encoding='utf-8') as f:
            f.write(guide)
        
        logger.info(f"使用指南已生成: {guide_file}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='RAG API服务器去重集成补丁')
    parser.add_argument('--api-server', default='rag_api_server.py', help='API服务器文件路径')
    parser.add_argument('--apply', action='store_true', help='应用补丁')
    parser.add_argument('--generate-guide', action='store_true', help='生成使用指南')
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    patcher = APIServerPatcher(args.api_server)
    
    if args.apply:
        success = patcher.apply_patches()
        if success:
            print("✅ 补丁应用成功!")
            print("⚠️  请重启API服务器以使更改生效")
        else:
            print("❌ 补丁应用失败，请检查日志")
    
    if args.generate_guide:
        patcher.generate_usage_guide()
        print("📋 使用指南已生成")
    
    if not args.apply and not args.generate_guide:
        print("使用 --apply 应用补丁，或 --generate-guide 生成使用指南")


if __name__ == "__main__":
    main()