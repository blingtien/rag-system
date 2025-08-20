#!/usr/bin/env python3
"""
智能日志处理器
解决日志重复和信息过载问题，提供结构化的前端日志展示
"""

import re
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
from enum import Enum


class LogLevel(Enum):
    """日志级别枚举"""
    CRITICAL = "critical"
    ERROR = "error" 
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


class LogCategory(Enum):
    """日志分类"""
    CORE_PROGRESS = "core_progress"      # 核心进度节点
    STAGE_DETAIL = "stage_detail"        # 阶段详细信息
    SYSTEM_DEBUG = "system_debug"        # 系统调试信息
    ERROR_WARNING = "error_warning"      # 错误和警告
    PERFORMANCE = "performance"          # 性能相关
    CACHE_OPERATION = "cache_operation"  # 缓存操作


@dataclass
class ProcessedLogEntry:
    """处理后的日志条目"""
    id: str
    timestamp: datetime
    level: LogLevel
    category: LogCategory
    title: str                   # 简化的标题
    message: str                 # 原始消息
    details: Optional[str]       # 详细信息
    progress: Optional[float]    # 进度百分比 (0-100)
    metadata: Dict              # 额外元数据
    is_milestone: bool          # 是否为重要里程碑
    group_id: Optional[str]     # 分组ID（用于折叠相似日志）


class IntelligentLogProcessor:
    """智能日志处理器"""
    
    def __init__(self):
        self.processed_logs: List[ProcessedLogEntry] = []
        self.seen_hashes: Set[str] = set()
        self.duplicate_window = timedelta(seconds=5)  # 5秒内的重复检测窗口
        self.recent_logs: List[Tuple[str, datetime]] = []
        
        # 日志分类规则
        self.category_patterns = {
            LogCategory.CORE_PROGRESS: [
                r"🚀 开始处理文档",
                r"Starting complete document processing",
                r"Parsing complete! Extracted (\d+) content blocks",
                r"Document processing pipeline completed",
                r"Text content insertion complete",
                r"Generated descriptions for (\d+)/(\d+) multimodal items",
                r"Writing graph with (\d+) nodes, (\d+) edges",
                r"Completed processing file (\d+)/(\d+)"
            ],
            LogCategory.STAGE_DETAIL: [
                r"Chunk (\d+) of (\d+) extracted (\d+) Ent \+ (\d+) Rel",
                r"Phase (\d+): Processing (\d+) entities",
                r"Extracting stage (\d+)/(\d+)",
                r"Merging stage (\d+)/(\d+)",
                r"Content block types:",
                r"Content separation complete"
            ],
            LogCategory.CACHE_OPERATION: [
                r"== LLM cache == saving:",
                r"Merge [NE]:",
                r"LLM merge [NE]:"
            ],
            LogCategory.ERROR_WARNING: [
                r"ERROR",
                r"WARNING", 
                r"Error generating",
                r"Failed to"
            ],
            LogCategory.PERFORMANCE: [
                r"limit_async: (\d+) new workers initialized",
                r"Using (.+) parser with method: (.+)",
                r"计算设备: (.+)"
            ]
        }
        
        # 里程碑关键字
        self.milestone_patterns = [
            r"🚀 开始处理文档",
            r"Parsing complete! Extracted",
            r"Document processing pipeline completed",
            r"Text content insertion complete",
            r"Generated descriptions for .+ multimodal items",
            r"Writing graph with .+ nodes"
        ]
        
        # 进度提取规则
        self.progress_patterns = [
            (r"Chunk (\d+) of (\d+)", self._extract_chunk_progress),
            (r"Phase (\d+): Processing (\d+) entities", self._extract_phase_progress),
            (r"Extracting stage (\d+)/(\d+)", self._extract_stage_progress),
            (r"Generated descriptions for (\d+)/(\d+)", self._extract_multimodal_progress)
        ]
    
    def process_log_message(self, raw_message: str, level: str = "info", 
                          logger_name: str = "lightrag") -> Optional[ProcessedLogEntry]:
        """处理原始日志消息"""
        
        # 去重检查
        if self._is_duplicate(raw_message):
            return None
        
        # 分类日志
        category = self._categorize_log(raw_message)
        
        # 如果是系统调试信息且不是错误，可以过滤掉
        if category == LogCategory.SYSTEM_DEBUG and level.lower() != "error":
            return None
        
        # 提取结构化信息
        title = self._extract_title(raw_message, category)
        details = self._extract_details(raw_message, category)
        progress = self._extract_progress(raw_message)
        is_milestone = self._is_milestone(raw_message)
        group_id = self._generate_group_id(raw_message, category)
        metadata = self._extract_metadata(raw_message, category)
        
        # 创建处理后的日志条目
        log_entry = ProcessedLogEntry(
            id=self._generate_log_id(raw_message),
            timestamp=datetime.now(),
            level=LogLevel(level.lower()),
            category=category,
            title=title,
            message=raw_message,
            details=details,
            progress=progress,
            metadata=metadata,
            is_milestone=is_milestone,
            group_id=group_id
        )
        
        self.processed_logs.append(log_entry)
        return log_entry
    
    def _is_duplicate(self, message: str) -> bool:
        """检测重复日志"""
        # 生成消息哈希
        message_hash = hashlib.md5(message.encode()).hexdigest()
        current_time = datetime.now()
        
        # 清理过期的记录
        self.recent_logs = [
            (hash_val, timestamp) for hash_val, timestamp in self.recent_logs
            if current_time - timestamp < self.duplicate_window
        ]
        
        # 检查是否重复
        for hash_val, _ in self.recent_logs:
            if hash_val == message_hash:
                return True
        
        # 添加到最近日志
        self.recent_logs.append((message_hash, current_time))
        return False
    
    def _categorize_log(self, message: str) -> LogCategory:
        """分类日志消息"""
        # 检查错误和警告
        if any(pattern in message.upper() for pattern in ["ERROR", "WARNING", "FAILED", "EXCEPTION"]):
            return LogCategory.ERROR_WARNING
        
        # 检查各个分类
        for category, patterns in self.category_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    return category
        
        # 默认为系统调试
        return LogCategory.SYSTEM_DEBUG
    
    def _extract_title(self, message: str, category: LogCategory) -> str:
        """提取简化的标题"""
        # 核心进度节点的简化标题
        core_progress_titles = {
            r"🚀 开始处理文档": "📄 开始处理文档",
            r"Starting complete document processing": "📄 开始文档处理",
            r"Parsing complete! Extracted (\d+) content blocks": "✅ 解析完成",
            r"Document processing pipeline completed": "🎯 文档处理完成",
            r"Text content insertion complete": "📝 文本内容插入完成",
            r"Generated descriptions for (\d+)/(\d+) multimodal items": "🖼️ 多模态内容处理完成",
            r"Writing graph with (\d+) nodes, (\d+) edges": "🕸️ 知识图谱构建完成",
            r"Completed processing file (\d+)/(\d+)": "✅ 文件处理完成"
        }
        
        # 阶段详情的简化标题
        stage_detail_titles = {
            r"Chunk (\d+) of (\d+) extracted": "📊 块提取进度",
            r"Phase (\d+): Processing": "⚙️ 处理阶段",
            r"Extracting stage": "🔍 提取阶段", 
            r"Merging stage": "🔗 合并阶段"
        }
        
        # 根据分类选择标题规则
        title_rules = {}
        if category == LogCategory.CORE_PROGRESS:
            title_rules = core_progress_titles
        elif category == LogCategory.STAGE_DETAIL:
            title_rules = stage_detail_titles
        
        # 尝试匹配简化标题
        for pattern, title in title_rules.items():
            if re.search(pattern, message, re.IGNORECASE):
                return title
        
        # 如果没有匹配到，生成简化标题
        if category == LogCategory.ERROR_WARNING:
            return "⚠️ 错误信息"
        elif category == LogCategory.CACHE_OPERATION:
            return "💾 缓存操作"
        elif category == LogCategory.PERFORMANCE:
            return "⚡ 性能信息"
        
        # 截取消息的前30个字符作为标题
        return message[:30] + "..." if len(message) > 30 else message
    
    def _extract_details(self, message: str, category: LogCategory) -> Optional[str]:
        """提取详细信息"""
        if category == LogCategory.CORE_PROGRESS:
            # 对于核心进度，提取数字信息
            numbers = re.findall(r'\d+', message)
            if numbers:
                return f"详细信息: {', '.join(numbers)}"
        
        elif category == LogCategory.ERROR_WARNING:
            # 对于错误，保留完整信息
            return message
            
        return None
    
    def _extract_progress(self, message: str) -> Optional[float]:
        """提取进度信息"""
        for pattern, extractor in self.progress_patterns:
            match = re.search(pattern, message)
            if match:
                return extractor(match)
        return None
    
    def _extract_chunk_progress(self, match) -> float:
        """提取Chunk进度"""
        current = int(match.group(1))
        total = int(match.group(2))
        return (current / total) * 100
    
    def _extract_phase_progress(self, match) -> float:
        """提取Phase进度 - 简化估算"""
        phase = int(match.group(1))
        # 假设有2个主要阶段
        return min((phase / 2) * 100, 100)
    
    def _extract_stage_progress(self, match) -> float:
        """提取Stage进度"""
        current = int(match.group(1))
        total = int(match.group(2))
        return (current / total) * 100
    
    def _extract_multimodal_progress(self, match) -> float:
        """提取多模态处理进度"""
        processed = int(match.group(1))
        total = int(match.group(2))
        return (processed / total) * 100
    
    def _is_milestone(self, message: str) -> bool:
        """判断是否为重要里程碑"""
        for pattern in self.milestone_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True
        return False
    
    def _generate_group_id(self, message: str, category: LogCategory) -> Optional[str]:
        """生成分组ID"""
        if category == LogCategory.CACHE_OPERATION:
            return "cache_operations"
        elif category == LogCategory.STAGE_DETAIL:
            # 根据阶段类型分组
            if "Chunk" in message:
                return "chunk_extraction"
            elif "Phase" in message:
                return "entity_processing"
            elif "Merge" in message:
                return "entity_merging"
        return None
    
    def _extract_metadata(self, message: str, category: LogCategory) -> Dict:
        """提取元数据"""
        metadata = {}
        
        if category == LogCategory.CORE_PROGRESS:
            # 提取文件大小、块数量等
            size_match = re.search(r'(\d+\.?\d*)\s?(KB|MB|GB)', message)
            if size_match:
                metadata['file_size'] = f"{size_match.group(1)} {size_match.group(2)}"
            
            blocks_match = re.search(r'Extracted (\d+) content blocks', message)
            if blocks_match:
                metadata['content_blocks'] = int(blocks_match.group(1))
                
            nodes_match = re.search(r'(\d+) nodes, (\d+) edges', message)
            if nodes_match:
                metadata['graph_nodes'] = int(nodes_match.group(1))
                metadata['graph_edges'] = int(nodes_match.group(2))
        
        elif category == LogCategory.STAGE_DETAIL:
            # 提取实体和关系数量
            ent_rel_match = re.search(r'(\d+) Ent \+ (\d+) Rel', message)
            if ent_rel_match:
                metadata['entities'] = int(ent_rel_match.group(1))
                metadata['relations'] = int(ent_rel_match.group(2))
        
        return metadata
    
    def _generate_log_id(self, message: str) -> str:
        """生成唯一日志ID"""
        return hashlib.sha256(f"{message}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
    
    def get_frontend_log_summary(self, include_debug: bool = False) -> Dict:
        """获取前端展示的日志摘要"""
        # 按分类分组
        categorized_logs = defaultdict(list)
        for log in self.processed_logs:
            if not include_debug and log.category == LogCategory.SYSTEM_DEBUG:
                continue
            categorized_logs[log.category.value].append(self._log_to_dict(log))
        
        # 统计信息
        stats = {
            "total_logs": len(self.processed_logs),
            "error_count": len([l for l in self.processed_logs if l.level == LogLevel.ERROR]),
            "warning_count": len([l for l in self.processed_logs if l.level == LogLevel.WARNING]),
            "milestone_count": len([l for l in self.processed_logs if l.is_milestone])
        }
        
        # 当前处理状态
        latest_milestone = None
        for log in reversed(self.processed_logs):
            if log.is_milestone:
                latest_milestone = self._log_to_dict(log)
                break
        
        return {
            "summary": {
                "stats": stats,
                "latest_milestone": latest_milestone,
                "processing_active": self._is_processing_active()
            },
            "categories": dict(categorized_logs),
            "timeline": [self._log_to_dict(log) for log in self.processed_logs[-10:]]  # 最近10条
        }
    
    def get_core_progress_only(self) -> List[Dict]:
        """仅获取核心进度信息"""
        core_logs = [
            log for log in self.processed_logs 
            if log.category in [LogCategory.CORE_PROGRESS, LogCategory.ERROR_WARNING]
        ]
        return [self._log_to_dict(log) for log in core_logs]
    
    def get_grouped_logs(self) -> Dict[str, List[Dict]]:
        """获取分组的日志信息"""
        grouped = defaultdict(list)
        for log in self.processed_logs:
            group_key = log.group_id or log.category.value
            grouped[group_key].append(self._log_to_dict(log))
        return dict(grouped)
    
    def _log_to_dict(self, log: ProcessedLogEntry) -> Dict:
        """将日志条目转换为字典"""
        return {
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "level": log.level.value,
            "category": log.category.value,
            "title": log.title,
            "message": log.message,
            "details": log.details,
            "progress": log.progress,
            "metadata": log.metadata,
            "is_milestone": log.is_milestone,
            "group_id": log.group_id
        }
    
    def _is_processing_active(self) -> bool:
        """判断是否正在处理中"""
        # 检查最近5分钟是否有活跃日志
        cutoff_time = datetime.now() - timedelta(minutes=5)
        recent_logs = [l for l in self.processed_logs if l.timestamp > cutoff_time]
        
        # 如果有非缓存操作的最近日志，认为正在处理
        return any(
            log.category != LogCategory.CACHE_OPERATION 
            for log in recent_logs
        )
    
    def clear_logs(self):
        """清空日志"""
        self.processed_logs.clear()
        self.seen_hashes.clear()
        self.recent_logs.clear()


# 全局智能日志处理器实例
intelligent_log_processor = IntelligentLogProcessor()


class SmartLogFilter:
    """智能日志过滤器"""
    
    @staticmethod
    def filter_for_frontend(logs: List[Dict], mode: str = "summary") -> List[Dict]:
        """为前端过滤日志"""
        if mode == "core_only":
            # 仅显示核心进度和错误
            return [
                log for log in logs 
                if log.get("category") in ["core_progress", "error_warning"]
            ]
        
        elif mode == "summary":
            # 显示核心进度 + 重要阶段信息
            return [
                log for log in logs 
                if log.get("category") in ["core_progress", "error_warning"] 
                or log.get("is_milestone", False)
            ]
        
        elif mode == "detailed":
            # 显示除系统调试外的所有信息
            return [
                log for log in logs 
                if log.get("category") != "system_debug"
            ]
        
        elif mode == "all":
            # 显示所有信息
            return logs
        
        return logs
    
    @staticmethod
    def group_similar_logs(logs: List[Dict]) -> Dict[str, List[Dict]]:
        """将相似日志分组"""
        grouped = defaultdict(list)
        
        for log in logs:
            group_key = log.get("group_id", log.get("category", "other"))
            grouped[group_key].append(log)
        
        return dict(grouped)


def create_progress_summary(logs: List[ProcessedLogEntry]) -> Dict:
    """创建处理进度摘要"""
    stages = {
        "document_start": False,
        "parsing_complete": False,
        "text_insertion": False,
        "multimodal_processing": False,
        "graph_building": False,
        "processing_complete": False
    }
    
    overall_progress = 0
    latest_progress = 0
    
    for log in logs:
        if "开始处理文档" in log.message or "Starting complete document processing" in log.message:
            stages["document_start"] = True
            overall_progress = max(overall_progress, 10)
            
        elif "Parsing complete" in log.message:
            stages["parsing_complete"] = True
            overall_progress = max(overall_progress, 30)
            
        elif "Text content insertion complete" in log.message:
            stages["text_insertion"] = True
            overall_progress = max(overall_progress, 60)
            
        elif "Generated descriptions for" in log.message and "multimodal items" in log.message:
            stages["multimodal_processing"] = True
            overall_progress = max(overall_progress, 80)
            
        elif "Writing graph with" in log.message:
            stages["graph_building"] = True
            overall_progress = max(overall_progress, 90)
            
        elif "Document processing pipeline completed" in log.message:
            stages["processing_complete"] = True
            overall_progress = 100
        
        # 使用日志中的具体进度
        if log.progress:
            latest_progress = log.progress
    
    return {
        "stages": stages,
        "overall_progress": overall_progress,
        "latest_progress": latest_progress,
        "current_stage": _get_current_stage(stages)
    }


def _get_current_stage(stages: Dict[str, bool]) -> str:
    """获取当前处理阶段"""
    stage_order = [
        ("document_start", "开始处理"),
        ("parsing_complete", "文档解析"),
        ("text_insertion", "文本处理"),
        ("multimodal_processing", "多模态处理"),
        ("graph_building", "图谱构建"),
        ("processing_complete", "处理完成")
    ]
    
    current_stage = "准备中"
    for stage_key, stage_name in stage_order:
        if stages[stage_key]:
            current_stage = stage_name
        else:
            break
    
    return current_stage