#!/usr/bin/env python3
"""
安全文件处理器 - RAG-Anything API
专为本地单人使用场景设计，提供基础但有效的安全防护
修复文件上传路径遍历漏洞和其他安全问题
"""

import os
import re
import uuid
import aiofiles
from pathlib import Path
from typing import Dict, Any, Tuple
from fastapi import UploadFile, HTTPException

try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    print("Warning: python-magic not available, file type checking will be limited")

class LocalSecureFileHandler:
    """本地环境的安全文件处理器"""
    
    def __init__(self, upload_dir: str = "./uploads"):
        self.upload_dir = Path(upload_dir).resolve()
        self.upload_dir.mkdir(exist_ok=True)
        
        # 本地使用的安全配置
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE_MB", "500")) * 1024 * 1024  # 默认500MB
        self.allowed_extensions = {
            '.pdf', '.docx', '.doc', '.txt', '.md', 
            '.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif', '.webp',
            '.pptx', '.ppt', '.xlsx', '.xls'
        }
        
        # MIME类型映射（用于验证文件内容）
        self.allowed_mime_types = {
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
            'text/markdown',
            'image/png',
            'image/jpeg',
            'image/bmp',
            'image/tiff',
            'image/gif',
            'image/webp',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
    
    def secure_filename(self, filename: str) -> str:
        """
        生成安全的文件名，防止路径遍历攻击
        
        Args:
            filename: 原始文件名
            
        Returns:
            安全的文件名
        """
        if not filename:
            raise ValueError("文件名不能为空")
        
        # 移除危险字符和路径字符
        safe_name = re.sub(r'[^\w\s\-\.]', '', filename)
        safe_name = safe_name.strip()
        
        if not safe_name:
            safe_name = "unnamed_file"
        
        # 分离文件名和扩展名
        name, ext = os.path.splitext(safe_name)
        
        # 限制文件名长度
        if len(name) > 100:
            name = name[:100]
        
        # 添加UUID防止文件名冲突
        unique_name = f"{name}_{uuid.uuid4().hex[:8]}{ext.lower()}"
        
        return unique_name
    
    def validate_file_path(self, file_path: str) -> bool:
        """
        验证文件路径安全性，防止路径遍历
        
        Args:
            file_path: 待验证的文件路径
            
        Returns:
            True if safe, False otherwise
        """
        try:
            safe_path = Path(file_path).resolve()
            return safe_path.is_relative_to(self.upload_dir)
        except (OSError, ValueError):
            return False
    
    def validate_file_extension(self, filename: str) -> bool:
        """
        验证文件扩展名
        
        Args:
            filename: 文件名
            
        Returns:
            True if allowed, False otherwise
        """
        if not filename:
            return False
        
        ext = Path(filename).suffix.lower()
        return ext in self.allowed_extensions
    
    def validate_file_size(self, file_size: int) -> bool:
        """
        验证文件大小
        
        Args:
            file_size: 文件大小（字节）
            
        Returns:
            True if within limits, False otherwise
        """
        return 0 < file_size <= self.max_file_size
    
    async def validate_file_content(self, file_content: bytes, filename: str) -> Tuple[bool, str]:
        """
        验证文件内容（魔术字节）
        
        Args:
            file_content: 文件内容（前1024字节）
            filename: 文件名
            
        Returns:
            (is_valid, error_message)
        """
        if not MAGIC_AVAILABLE:
            # 如果python-magic不可用，只做基础验证
            return True, "Magic not available, skipping content validation"
        
        try:
            # 获取MIME类型
            mime_type = magic.from_buffer(file_content[:1024], mime=True)
            
            # 验证MIME类型是否在允许列表中
            if mime_type in self.allowed_mime_types:
                return True, "Valid file content"
            
            # 特殊处理一些常见的变体
            if mime_type.startswith('text/') and Path(filename).suffix.lower() in ['.txt', '.md']:
                return True, "Valid text file"
            
            return False, f"不支持的文件类型: {mime_type}"
            
        except Exception as e:
            # 如果检查出错，记录警告但允许通过
            print(f"Warning: File content validation failed: {e}")
            return True, f"Content validation skipped due to error: {e}"
    
    async def handle_upload(self, file: UploadFile) -> Dict[str, Any]:
        """
        安全的文件上传处理
        
        Args:
            file: FastAPI UploadFile 对象
            
        Returns:
            文件信息字典
            
        Raises:
            HTTPException: 上传验证失败时
        """
        # 1. 基础验证
        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")
        
        # 2. 文件扩展名验证
        if not self.validate_file_extension(file.filename):
            allowed_exts = ', '.join(sorted(self.allowed_extensions))
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件类型。支持的格式: {allowed_exts}"
            )
        
        # 3. 读取文件内容
        file_content = await file.read()
        await file.seek(0)  # 重置文件指针
        
        # 4. 文件大小验证
        file_size = len(file_content)
        if not self.validate_file_size(file_size):
            max_size_mb = self.max_file_size // (1024 * 1024)
            raise HTTPException(
                status_code=413, 
                detail=f"文件过大。最大允许大小: {max_size_mb}MB"
            )
        
        # 5. 文件内容验证
        content_valid, content_message = await self.validate_file_content(file_content, file.filename)
        if not content_valid:
            raise HTTPException(status_code=400, detail=content_message)
        
        # 6. 生成安全的文件名和路径
        safe_filename = self.secure_filename(file.filename)
        file_path = self.upload_dir / safe_filename
        
        # 7. 路径安全性验证
        if not self.validate_file_path(str(file_path)):
            raise HTTPException(status_code=400, detail="文件路径不安全")
        
        # 8. 保存文件
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")
        
        # 9. 返回文件信息
        return {
            "original_filename": file.filename,
            "secure_filename": safe_filename,
            "file_path": str(file_path),
            "file_size": file_size,
            "content_validation": content_message,
            "upload_time": Path(file_path).stat().st_mtime
        }
    
    def cleanup_temp_files(self, max_age_hours: int = 24):
        """
        清理临时文件（可选功能）
        
        Args:
            max_age_hours: 文件最大保留时间（小时）
        """
        import time
        
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)
        
        cleaned_count = 0
        for file_path in self.upload_dir.rglob('*'):
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    cleaned_count += 1
                except Exception as e:
                    print(f"Warning: Failed to cleanup file {file_path}: {e}")
        
        if cleaned_count > 0:
            print(f"Cleaned up {cleaned_count} temporary files")

# 全局实例（单例模式）
_secure_file_handler = None

def get_secure_file_handler() -> LocalSecureFileHandler:
    """获取安全文件处理器实例（单例）"""
    global _secure_file_handler
    
    if _secure_file_handler is None:
        upload_dir = os.getenv("UPLOAD_DIR", "/home/ragsvr/projects/ragsystem/uploads")
        _secure_file_handler = LocalSecureFileHandler(upload_dir)
    
    return _secure_file_handler

# 导出主要接口
__all__ = ['LocalSecureFileHandler', 'get_secure_file_handler']