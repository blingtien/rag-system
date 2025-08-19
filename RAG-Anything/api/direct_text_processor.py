#!/usr/bin/env python3
"""
Direct Text File Processor for RAG-Anything API
直接文本文件处理器，避免PDF转换的高效文本解析
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Any
import hashlib

logger = logging.getLogger(__name__)

class DirectTextProcessor:
    """直接文本文件处理器"""
    
    def __init__(self):
        """初始化处理器"""
        self.supported_encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1', 'cp1252']
        self.processing_stats = {
            "files_processed": 0,
            "total_lines": 0,
            "total_chars": 0,
            "encoding_usage": {}
        }
    
    def process_text_file(self, file_path: str, output_dir: str = None) -> List[Dict[str, Any]]:
        """
        直接处理文本文件，生成content_list
        
        Args:
            file_path: 文本文件路径
            output_dir: 输出目录（可选）
            
        Returns:
            List[Dict[str, Any]]: content_list格式的内容块
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 检查文件格式
            if file_path.suffix.lower() not in {'.txt', '.md'}:
                raise ValueError(f"不支持的文件格式: {file_path.suffix}")
            
            # 读取文件内容
            content, encoding_used = self._read_file_with_encoding(file_path)
            
            # 更新统计
            self.processing_stats["files_processed"] += 1
            self.processing_stats["total_chars"] += len(content)
            self.processing_stats["encoding_usage"][encoding_used] = self.processing_stats["encoding_usage"].get(encoding_used, 0) + 1
            
            # 根据文件类型处理
            if file_path.suffix.lower() == '.md':
                content_list = self._process_markdown_content(content)
            else:
                content_list = self._process_plain_text_content(content)
            
            # 添加文件元信息
            for item in content_list:
                item['source_file'] = str(file_path)
                item['encoding'] = encoding_used
                item['file_type'] = file_path.suffix.lower()
            
            logger.info(f"直接文本处理完成: {file_path.name}, {len(content_list)}个内容块, 编码: {encoding_used}")
            
            return content_list
            
        except Exception as e:
            logger.error(f"直接文本处理失败 {file_path}: {str(e)}")
            raise
    
    def _read_file_with_encoding(self, file_path: Path) -> tuple[str, str]:
        """
        尝试多种编码读取文件
        
        Returns:
            tuple[str, str]: (文件内容, 使用的编码)
        """
        for encoding in self.supported_encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                logger.debug(f"成功使用 {encoding} 编码读取文件: {file_path.name}")
                return content, encoding
            except UnicodeDecodeError:
                continue
        
        # 如果所有编码都失败，尝试使用错误忽略模式
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            logger.warning(f"使用UTF-8忽略错误模式读取文件: {file_path.name}")
            return content, 'utf-8-ignore'
        except Exception as e:
            raise RuntimeError(f"无法读取文件 {file_path.name}: {str(e)}")
    
    def _process_plain_text_content(self, content: str) -> List[Dict[str, Any]]:
        """
        处理纯文本内容
        
        Args:
            content: 文本内容
            
        Returns:
            List[Dict[str, Any]]: content_list格式
        """
        content_list = []
        
        # 按段落分割（双换行符）
        paragraphs = content.split('\n\n')
        
        for i, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # 进一步处理长段落（按单换行符分割）
            lines = paragraph.split('\n')
            if len(lines) == 1:
                # 单行段落
                content_list.append({
                    "type": "text",
                    "text": paragraph,
                    "page_idx": 0,
                    "paragraph_idx": i,
                    "char_count": len(paragraph)
                })
            else:
                # 多行段落，保持为一个文本块但标记换行
                combined_text = '\n'.join(line.strip() for line in lines if line.strip())
                if combined_text:
                    content_list.append({
                        "type": "text", 
                        "text": combined_text,
                        "page_idx": 0,
                        "paragraph_idx": i,
                        "line_count": len(lines),
                        "char_count": len(combined_text)
                    })
        
        # 如果没有找到段落，按行处理
        if not content_list:
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            for i, line in enumerate(lines):
                content_list.append({
                    "type": "text",
                    "text": line,
                    "page_idx": 0,
                    "line_idx": i,
                    "char_count": len(line)
                })
        
        self.processing_stats["total_lines"] += len(content_list)
        
        return content_list
    
    def _process_markdown_content(self, content: str) -> List[Dict[str, Any]]:
        """
        处理Markdown内容，识别结构化元素
        
        Args:
            content: Markdown内容
            
        Returns:
            List[Dict[str, Any]]: content_list格式
        """
        content_list = []
        lines = content.split('\n')
        current_paragraph = []
        in_code_block = False
        code_block_content = []
        table_content = []
        in_table = False
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # 代码块处理
            if line_stripped.startswith('```'):
                if in_code_block:
                    # 结束代码块
                    if code_block_content:
                        content_list.append({
                            "type": "code",
                            "text": '\n'.join(code_block_content),
                            "page_idx": 0,
                            "line_start": i - len(code_block_content),
                            "line_end": i,
                            "language": code_block_content[0].replace('```', '').strip() if code_block_content else ""
                        })
                    code_block_content = []
                    in_code_block = False
                else:
                    # 开始代码块
                    if current_paragraph:
                        content_list.append({
                            "type": "text",
                            "text": '\n'.join(current_paragraph),
                            "page_idx": 0,
                            "char_count": sum(len(p) for p in current_paragraph)
                        })
                        current_paragraph = []
                    in_code_block = True
                continue
            
            if in_code_block:
                code_block_content.append(line)
                continue
            
            # 表格处理
            if self._is_table_line(line_stripped):
                if not in_table:
                    # 开始表格
                    if current_paragraph:
                        content_list.append({
                            "type": "text",
                            "text": '\n'.join(current_paragraph),
                            "page_idx": 0,
                            "char_count": sum(len(p) for p in current_paragraph)
                        })
                        current_paragraph = []
                    in_table = True
                table_content.append(line_stripped)
                continue
            else:
                if in_table:
                    # 结束表格
                    if table_content:
                        content_list.append({
                            "type": "table",
                            "table_body": '\n'.join(table_content),
                            "page_idx": 0,
                            "row_count": len([r for r in table_content if '|' in r and not r.startswith('|---')])
                        })
                    table_content = []
                    in_table = False
            
            # 标题处理
            if line_stripped.startswith('#'):
                if current_paragraph:
                    content_list.append({
                        "type": "text",
                        "text": '\n'.join(current_paragraph),
                        "page_idx": 0,
                        "char_count": sum(len(p) for p in current_paragraph)
                    })
                    current_paragraph = []
                
                level = len(line_stripped) - len(line_stripped.lstrip('#'))
                title_text = line_stripped.lstrip('#').strip()
                content_list.append({
                    "type": "heading",
                    "text": title_text,
                    "level": level,
                    "page_idx": 0,
                    "line_idx": i
                })
                continue
            
            # 列表项处理
            if re.match(r'^[\s]*[-*+]\s+', line_stripped) or re.match(r'^[\s]*\d+\.\s+', line_stripped):
                if current_paragraph:
                    content_list.append({
                        "type": "text",
                        "text": '\n'.join(current_paragraph),
                        "page_idx": 0,
                        "char_count": sum(len(p) for p in current_paragraph)
                    })
                    current_paragraph = []
                
                content_list.append({
                    "type": "list_item",
                    "text": line_stripped,
                    "page_idx": 0,
                    "line_idx": i,
                    "list_type": "ordered" if re.match(r'^[\s]*\d+\.', line_stripped) else "unordered"
                })
                continue
            
            # 空行处理
            if not line_stripped:
                if current_paragraph:
                    content_list.append({
                        "type": "text",
                        "text": '\n'.join(current_paragraph),
                        "page_idx": 0,
                        "char_count": sum(len(p) for p in current_paragraph)
                    })
                    current_paragraph = []
                continue
            
            # 普通文本行
            current_paragraph.append(line_stripped)
        
        # 处理最后的内容
        if current_paragraph:
            content_list.append({
                "type": "text",
                "text": '\n'.join(current_paragraph),
                "page_idx": 0,
                "char_count": sum(len(p) for p in current_paragraph)
            })
        
        if in_table and table_content:
            content_list.append({
                "type": "table",
                "table_body": '\n'.join(table_content),
                "page_idx": 0,
                "row_count": len([r for r in table_content if '|' in r and not r.startswith('|---')])
            })
        
        if in_code_block and code_block_content:
            content_list.append({
                "type": "code",
                "text": '\n'.join(code_block_content),
                "page_idx": 0,
                "language": "unknown"
            })
        
        self.processing_stats["total_lines"] += len(content_list)
        
        return content_list
    
    def _is_table_line(self, line: str) -> bool:
        """判断是否为表格行"""
        if not line:
            return False
        
        # 表格行应该包含 | 符号
        if '|' not in line:
            return False
        
        # 表格分隔符行（如 |---|---|）
        if re.match(r'^[\s]*\|[\s]*:?-+:?[\s]*(\|[\s]*:?-+:?[\s]*)*\|?[\s]*$', line):
            return True
        
        # 普通表格数据行
        if line.count('|') >= 1:
            return True
        
        return False
    
    def get_processing_stats(self) -> Dict:
        """获取处理统计信息"""
        return self.processing_stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self.processing_stats = {
            "files_processed": 0,
            "total_lines": 0,
            "total_chars": 0,
            "encoding_usage": {}
        }

# 全局文本处理器实例
text_processor = DirectTextProcessor()