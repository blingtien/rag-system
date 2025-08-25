"""
图像处理工具模块
解决deepseek-vl API调用时JSON载荷过大的问题
通过智能压缩确保图像base64编码后小于指定大小
"""

import os
import base64
import io
import json
from PIL import Image, ImageEnhance
from pathlib import Path
from typing import Optional, Tuple
import hashlib
import logging

logger = logging.getLogger(__name__)

class ImageCompressionSettings:
    """图像压缩配置"""
    MAX_PAYLOAD_SIZE_KB = 200  # 最大载荷大小 (KB)
    MAX_DIMENSION = 1024       # 最大图像尺寸
    MIN_QUALITY = 20          # 最低JPEG质量
    QUALITY_STEP = 15         # 质量递减步长
    
    # 不同文件类型的初始质量设置
    INITIAL_QUALITY = {
        'JPEG': 85,
        'JPG': 85, 
        'PNG': 90,
        'BMP': 80,
        'TIFF': 85,
        'default': 85
    }

def calculate_estimated_base64_size(image_path: str) -> float:
    """
    估算图像base64编码后的大小(KB)
    base64编码会增加约33%的大小
    """
    try:
        file_size_bytes = os.path.getsize(image_path)
        # base64编码后大小约为原文件的1.33倍
        estimated_size_kb = (file_size_bytes * 1.33) / 1024
        return estimated_size_kb
    except Exception as e:
        logger.error(f"Failed to estimate file size for {image_path}: {e}")
        return 0

def validate_and_compress_image(
    image_path: str, 
    max_size_kb: int = ImageCompressionSettings.MAX_PAYLOAD_SIZE_KB,
    max_dimension: int = ImageCompressionSettings.MAX_DIMENSION,
    force_compression: bool = True
) -> Optional[str]:
    """
    验证图像大小并在需要时进行压缩
    
    Args:
        image_path: 图像文件路径
        max_size_kb: 最大编码后大小(KB)
        max_dimension: 最大图像尺寸(像素)
        force_compression: 是否强制压缩优化
    
    Returns:
        Base64编码后的图像字符串，如果处理失败返回None
    """
    try:
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return None
        
        # 检查原始文件大小
        original_size_kb = os.path.getsize(image_path) / 1024
        estimated_b64_size = calculate_estimated_base64_size(image_path)
        
        logger.info(f"Processing image: {image_path}")
        logger.info(f"Original size: {original_size_kb:.1f}KB, Estimated base64 size: {estimated_b64_size:.1f}KB")
        
        # 如果预估大小就超出限制，需要压缩
        needs_compression = estimated_b64_size > max_size_kb or force_compression
        
        # 打开并处理图像
        with Image.open(image_path) as img:
            # 获取原始格式和尺寸
            original_format = img.format or 'JPEG'
            original_size = img.size
            logger.info(f"Original format: {original_format}, Size: {original_size}")
            
            # 转换颜色模式以确保兼容性
            if img.mode in ('RGBA', 'P', 'LA'):
                # 对于带透明度的图像，创建白色背景
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ['RGBA', 'LA'] else None)
                img = background
            elif img.mode not in ['RGB', 'L']:
                img = img.convert('RGB')
            
            # 调整图像尺寸如果超过限制
            if img.width > max_dimension or img.height > max_dimension:
                # 计算新尺寸，保持宽高比
                ratio = min(max_dimension / img.width, max_dimension / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"Resized to: {new_size}")
            
            # 如果不需要压缩且尺寸未改变，直接编码
            if not needs_compression and img.size == original_size:
                with open(image_path, 'rb') as f:
                    encoded_string = base64.b64encode(f.read()).decode('utf-8')
                    final_size_kb = len(encoded_string) / 1024
                    logger.info(f"No compression needed. Final size: {final_size_kb:.1f}KB")
                    return encoded_string
            
            # 压缩优化
            return _compress_to_target_size(img, max_size_kb, original_format)
            
    except Exception as e:
        logger.error(f"Failed to process image {image_path}: {e}")
        return None

def _compress_to_target_size(img: Image.Image, max_size_kb: int, original_format: str) -> Optional[str]:
    """
    压缩图像到目标大小
    """
    try:
        # 获取初始质量设置
        initial_quality = ImageCompressionSettings.INITIAL_QUALITY.get(
            original_format, 
            ImageCompressionSettings.INITIAL_QUALITY['default']
        )
        
        quality = initial_quality
        best_result = None
        best_size = float('inf')
        
        # 尝试不同的压缩质量
        while quality >= ImageCompressionSettings.MIN_QUALITY:
            buffer = io.BytesIO()
            
            try:
                # 保存为JPEG格式进行压缩
                save_kwargs = {
                    'format': 'JPEG',
                    'quality': quality,
                    'optimize': True,
                }
                
                # 对于低质量，使用更激进的优化
                if quality < 50:
                    save_kwargs['progressive'] = True
                
                img.save(buffer, **save_kwargs)
                
                # 检查压缩后大小
                compressed_data = buffer.getvalue()
                buffer.seek(0)
                
                # 编码为base64
                encoded_string = base64.b64encode(compressed_data).decode('utf-8')
                final_size_kb = len(encoded_string) / 1024
                
                logger.debug(f"Quality {quality}%: {final_size_kb:.1f}KB")
                
                # 如果满足大小要求，返回结果
                if final_size_kb <= max_size_kb:
                    logger.info(f"Compression successful! Quality: {quality}%, Final size: {final_size_kb:.1f}KB")
                    return encoded_string
                
                # 记录最好的结果（即使超过限制）
                if final_size_kb < best_size:
                    best_result = encoded_string
                    best_size = final_size_kb
                
            except Exception as e:
                logger.debug(f"Compression failed at quality {quality}%: {e}")
            
            # 降低质量重试
            quality -= ImageCompressionSettings.QUALITY_STEP
        
        # 如果无法达到目标大小，返回最好的结果（如果不是太大的话）
        if best_result and best_size <= max_size_kb * 2:  # 允许2倍的容差
            logger.warning(f"Using best available result: {best_size:.1f}KB (exceeds target of {max_size_kb}KB)")
            return best_result
        
        logger.error(f"Unable to compress image to target size {max_size_kb}KB. Best result: {best_size:.1f}KB")
        return None
        
    except Exception as e:
        logger.error(f"Compression process failed: {e}")
        return None

def validate_payload_size(data: dict, max_size_kb: int = 500) -> Tuple[bool, float]:
    """
    验证数据载荷的JSON序列化后大小
    
    Args:
        data: 要验证的数据
        max_size_kb: 最大允许大小(KB)
    
    Returns:
        (是否通过验证, 实际大小KB)
    """
    try:
        json_str = json.dumps(data, ensure_ascii=False)
        size_kb = len(json_str.encode('utf-8')) / 1024
        
        is_valid = size_kb <= max_size_kb
        
        if not is_valid:
            logger.warning(f"Payload size validation failed: {size_kb:.1f}KB exceeds limit of {max_size_kb}KB")
        else:
            logger.debug(f"Payload size validation passed: {size_kb:.1f}KB")
        
        return is_valid, size_kb
        
    except Exception as e:
        logger.error(f"Failed to validate payload size: {e}")
        return False, 0.0

def create_image_processing_report(image_path: str, result: Optional[str]) -> dict:
    """
    创建图像处理报告
    """
    report = {
        'image_path': image_path,
        'processing_timestamp': str(os.times()),
        'original_exists': os.path.exists(image_path),
        'processing_successful': result is not None
    }
    
    try:
        if os.path.exists(image_path):
            report.update({
                'original_size_kb': os.path.getsize(image_path) / 1024,
                'estimated_b64_size_kb': calculate_estimated_base64_size(image_path)
            })
        
        if result:
            report.update({
                'final_b64_size_kb': len(result) / 1024,
                'compression_ratio': report.get('original_size_kb', 0) / (len(result) / 1024) if result else 0
            })
    except Exception as e:
        report['report_error'] = str(e)
    
    return report

# 配置日志
if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    # 测试图像压缩功能
    test_image = "/path/to/test/image.jpg"
    if os.path.exists(test_image):
        result = validate_and_compress_image(test_image)
        if result:
            print(f"Success! Compressed size: {len(result)/1024:.1f}KB")
        else:
            print("Failed to compress image")