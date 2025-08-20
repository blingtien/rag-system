#!/usr/bin/env python3
"""
Smart Parser Router for RAG-Anything API
智能解析器路由器，根据文件格式和特征选择最优解析策略
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ParserConfig:
    """解析器配置"""
    parser: str
    method: str
    category: str
    reason: str
    direct_processing: bool = False
    
class SmartParserRouter:
    """智能解析器路由器"""
    
    # 文件格式分类
    OFFICE_FORMATS = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
    IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".webp"}
    TEXT_FORMATS = {".txt", ".md"}
    HTML_FORMATS = {".html", ".htm", ".xhtml"}
    PDF_FORMATS = {".pdf"}
    
    # 文件大小阈值（字节）
    LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB
    SMALL_FILE_THRESHOLD = 1 * 1024 * 1024   # 1MB
    
    def __init__(self):
        """初始化路由器"""
        self.routing_stats = {
            "total_routed": 0,
            "parser_usage": {"mineru": 0, "docling": 0, "direct_text": 0},
            "category_distribution": {}
        }
    
    def route_parser(self, file_path: str, file_size: int) -> ParserConfig:
        """
        根据文件格式和特征路由到最优解析器
        
        Args:
            file_path: 文件路径
            file_size: 文件大小（字节）
            
        Returns:
            ParserConfig: 解析器配置
        """
        file_ext = Path(file_path).suffix.lower()
        file_name = Path(file_path).name
        
        # 更新统计
        self.routing_stats["total_routed"] += 1
        
        # 路由逻辑
        if file_ext in self.TEXT_FORMATS:
            config = self._route_text_file(file_path, file_size)
        elif file_ext in self.OFFICE_FORMATS:
            config = self._route_office_file(file_path, file_size)
        elif file_ext in self.IMAGE_FORMATS:
            config = self._route_image_file(file_path, file_size)
        elif file_ext in self.PDF_FORMATS:
            config = self._route_pdf_file(file_path, file_size)
        elif file_ext in self.HTML_FORMATS:
            config = self._route_html_file(file_path, file_size)
        else:
            config = self._route_unknown_file(file_path, file_size)
        
        # 更新统计
        self.routing_stats["parser_usage"][config.parser] = self.routing_stats["parser_usage"].get(config.parser, 0) + 1
        self.routing_stats["category_distribution"][config.category] = self.routing_stats["category_distribution"].get(config.category, 0) + 1
        
        logger.info(f"文件路由: {file_name} -> {config.parser} ({config.category}) - {config.reason}")
        
        return config
    
    def _route_text_file(self, file_path: str, file_size: int) -> ParserConfig:
        """路由文本文件"""
        # 对于文本文件，使用直接处理避免PDF转换
        return ParserConfig(
            parser="direct_text",
            method="direct",
            category="text",
            reason="文本文件直接解析，避免PDF转换",
            direct_processing=True
        )
    
    def _route_office_file(self, file_path: str, file_size: int) -> ParserConfig:
        """路由Office文件 - 根据格式选择解析器"""
        file_ext = Path(file_path).suffix.lower()
        
        # .doc格式先用LibreOffice转换为.docx，然后用Docling解析
        if file_ext == ".doc":
            return ParserConfig(
                parser="docling",
                method="auto",
                category="office", 
                reason="DOC文档先用LibreOffice转换为DOCX，然后用Docling解析"
            )
        
        # 其他Office文档(.docx, .pptx, .xlsx)直接用Docling解析
        return ParserConfig(
            parser="docling",
            method="auto", 
            category="office",
            reason=f"Office文档({file_ext})使用Docling直接解析"
        )
    
    def _route_image_file(self, file_path: str, file_size: int) -> ParserConfig:
        """路由图片文件"""
        file_ext = Path(file_path).suffix.lower()
        
        # MinerU在图片OCR方面有优势
        return ParserConfig(
            parser="mineru",
            method="ocr",
            category="image",
            reason=f"图片文件({file_ext})，MinerU OCR能力强"
        )
    
    def _route_pdf_file(self, file_path: str, file_size: int) -> ParserConfig:
        """路由PDF文件 - 一律使用MinerU"""
        return ParserConfig(
            parser="mineru",
            method="auto",
            category="pdf",
            reason="PDF文件统一使用MinerU专业PDF解析引擎"
        )
    
    def _route_html_file(self, file_path: str, file_size: int) -> ParserConfig:
        """路由HTML文件"""
        # Docling支持HTML直接解析
        return ParserConfig(
            parser="docling",
            method="auto",
            category="html",
            reason="HTML文件，Docling原生支持"
        )
    
    def _route_unknown_file(self, file_path: str, file_size: int) -> ParserConfig:
        """路由未知格式文件"""
        file_ext = Path(file_path).suffix.lower()
        
        # 对于未知格式，尝试作为PDF处理
        return ParserConfig(
            parser="mineru",
            method="auto",
            category="unknown",
            reason=f"未知格式({file_ext})，尝试MinerU通用解析"
        )
    
    def get_routing_stats(self) -> Dict:
        """获取路由统计信息"""
        return self.routing_stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self.routing_stats = {
            "total_routed": 0,
            "parser_usage": {"mineru": 0, "docling": 0, "direct_text": 0},
            "category_distribution": {}
        }
    
    def validate_parser_availability(self, parser: str) -> bool:
        """验证解析器是否可用"""
        if parser == "mineru":
            try:
                from raganything.parser import MineruParser
                return MineruParser().check_installation()
            except Exception as e:
                logger.warning(f"MinerU解析器不可用: {e}")
                return False
        
        elif parser == "docling":
            try:
                from raganything.parser import DoclingParser
                return DoclingParser().check_installation()
            except Exception as e:
                logger.warning(f"Docling解析器不可用: {e}")
                return False
        
        elif parser == "direct_text":
            # 直接文本处理不需要外部依赖
            return True
        
        return False
    
    def get_fallback_config(self, original_config: ParserConfig) -> ParserConfig:
        """获取备用解析器配置"""
        if original_config.parser == "docling":
            return ParserConfig(
                parser="mineru",
                method="auto",
                category=original_config.category,
                reason=f"Docling不可用，降级到MinerU"
            )
        elif original_config.parser == "mineru":
            return ParserConfig(
                parser="docling", 
                method="auto",
                category=original_config.category,
                reason=f"MinerU不可用，降级到Docling"
            )
        elif original_config.parser == "direct_text":
            # 文本处理失败则转换为PDF后解析
            return ParserConfig(
                parser="mineru",
                method="auto",
                category="text_fallback",
                reason="直接文本处理失败，转换为PDF解析"
            )
        else:
            return ParserConfig(
                parser="mineru",
                method="auto", 
                category="fallback",
                reason="所有解析器失败，使用MinerU最后尝试"
            )

# 全局路由器实例
router = SmartParserRouter()