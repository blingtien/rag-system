"""
ProcessingService - 文档处理服务
实现文档解析处理的策略模式和异步处理，支持不同解析器和处理方法
"""
import asyncio
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Protocol
from enum import Enum
from datetime import datetime

from pydantic import BaseModel

from core.state_manager import StateManager, Document
from core.rag_manager import RAGManager
from services.exceptions import ServiceException, ProcessingError, ConfigurationError


class ParserType(Enum):
    """支持的解析器类型"""
    MINERU = "mineru"
    DOCLING = "docling"


class ParseMethod(Enum):
    """解析方法"""
    AUTO = "auto"
    OCR = "ocr"
    TXT = "txt"


class ProcessingConfig(BaseModel):
    """处理配置"""
    parser: ParserType = ParserType.MINERU
    parse_method: ParseMethod = ParseMethod.AUTO
    device: Optional[str] = None
    lang: str = "en"
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    enable_formula: bool = True
    enable_table: bool = True
    backend: str = "pipeline"
    
    class Config:
        use_enum_values = True


class ProcessingResult(BaseModel):
    """处理结果"""
    success: bool
    document_id: str
    task_id: str
    file_name: str
    message: str
    processing_time_seconds: Optional[float] = None
    chunks_count: Optional[int] = None
    error_details: Optional[Dict[str, Any]] = None


class ProcessingStrategy(ABC):
    """
    处理策略抽象基类
    应用Strategy Pattern实现不同解析器的处理逻辑
    """
    
    @abstractmethod
    async def process(
        self,
        document: Document,
        config: ProcessingConfig,
        rag_instance: Any
    ) -> ProcessingResult:
        """执行文档处理"""
        pass
    
    @abstractmethod
    def supports_parser(self, parser: ParserType) -> bool:
        """检查是否支持指定解析器"""
        pass


class MineruProcessingStrategy(ProcessingStrategy):
    """MinerU处理策略"""
    
    async def process(
        self,
        document: Document,
        config: ProcessingConfig,
        rag_instance: Any
    ) -> ProcessingResult:
        """使用MinerU处理文档"""
        start_time = datetime.now()
        
        try:
            # 验证文件存在
            if not os.path.exists(document.file_path):
                raise ProcessingError(f"文件不存在: {document.file_path}")
            
            # 构建处理参数
            process_kwargs = {
                "parser": config.parser.value,
                "parse_method": config.parse_method.value,
                "lang": config.lang,
                "formula": config.enable_formula,
                "table": config.enable_table,
                "backend": config.backend
            }
            
            # 添加可选参数
            if config.device:
                process_kwargs["device"] = config.device
            if config.start_page is not None:
                process_kwargs["start_page"] = config.start_page
            if config.end_page is not None:
                process_kwargs["end_page"] = config.end_page
            
            # 执行处理
            await rag_instance.process_document_complete(
                document.file_path,
                **process_kwargs
            )
            
            # 计算处理时间
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # TODO: 获取实际的chunks数量
            # chunks_count = await self._get_chunks_count(rag_instance, document)
            chunks_count = None
            
            return ProcessingResult(
                success=True,
                document_id=document.document_id,
                task_id=document.task_id,
                file_name=document.file_name,
                message="MinerU处理完成",
                processing_time_seconds=processing_time,
                chunks_count=chunks_count
            )
            
        except Exception as e:
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            return ProcessingResult(
                success=False,
                document_id=document.document_id,
                task_id=document.task_id,
                file_name=document.file_name,
                message=f"MinerU处理失败: {str(e)}",
                processing_time_seconds=processing_time,
                error_details={"error": str(e), "strategy": "mineru"}
            )
    
    def supports_parser(self, parser: ParserType) -> bool:
        """检查是否支持MinerU解析器"""
        return parser == ParserType.MINERU


class DoclingProcessingStrategy(ProcessingStrategy):
    """Docling处理策略"""
    
    async def process(
        self,
        document: Document,
        config: ProcessingConfig,
        rag_instance: Any
    ) -> ProcessingResult:
        """使用Docling处理文档"""
        start_time = datetime.now()
        
        try:
            # 验证文件存在
            if not os.path.exists(document.file_path):
                raise ProcessingError(f"文件不存在: {document.file_path}")
            
            # 构建处理参数
            process_kwargs = {
                "parser": config.parser.value,
                "parse_method": config.parse_method.value
            }
            
            # 执行处理
            await rag_instance.process_document_complete(
                document.file_path,
                **process_kwargs
            )
            
            # 计算处理时间
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            return ProcessingResult(
                success=True,
                document_id=document.document_id,
                task_id=document.task_id,
                file_name=document.file_name,
                message="Docling处理完成",
                processing_time_seconds=processing_time
            )
            
        except Exception as e:
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            return ProcessingResult(
                success=False,
                document_id=document.document_id,
                task_id=document.task_id,
                file_name=document.file_name,
                message=f"Docling处理失败: {str(e)}",
                processing_time_seconds=processing_time,
                error_details={"error": str(e), "strategy": "docling"}
            )
    
    def supports_parser(self, parser: ParserType) -> bool:
        """检查是否支持Docling解析器"""
        return parser == ParserType.DOCLING


class ProcessingStrategyFactory:
    """
    处理策略工厂
    应用Factory Pattern创建不同的处理策略
    """
    
    _strategies: Dict[ParserType, ProcessingStrategy] = {
        ParserType.MINERU: MineruProcessingStrategy(),
        ParserType.DOCLING: DoclingProcessingStrategy()
    }
    
    @classmethod
    def get_strategy(cls, parser: ParserType) -> ProcessingStrategy:
        """获取处理策略"""
        if parser not in cls._strategies:
            raise ConfigurationError(f"不支持的解析器: {parser.value}")
        
        return cls._strategies[parser]
    
    @classmethod
    def register_strategy(cls, parser: ParserType, strategy: ProcessingStrategy):
        """注册新的处理策略"""
        cls._strategies[parser] = strategy


class ProcessingService:
    """
    文档处理服务
    
    负责协调文档处理流程，应用策略模式支持不同解析器
    提供异步处理能力和进度跟踪
    """
    
    def __init__(
        self,
        state_manager: StateManager,
        rag_manager: RAGManager
    ):
        self.state_manager = state_manager
        self.rag_manager = rag_manager
        self._active_tasks: Dict[str, asyncio.Task] = {}
    
    async def process_document(
        self,
        document_id: str,
        config: Optional[ProcessingConfig] = None
    ) -> ProcessingResult:
        """
        处理文档
        
        Args:
            document_id: 文档ID
            config: 处理配置，如果为None则使用默认配置
            
        Returns:
            ProcessingResult: 处理结果
            
        Raises:
            ServiceException: 服务层异常
            ProcessingError: 处理过程异常
        """
        # 使用默认配置
        if config is None:
            config = ProcessingConfig()
        
        # 获取文档
        document = await self.state_manager.get_document(document_id)
        if not document:
            raise ServiceException(f"文档不存在: {document_id}")
        
        # 检查文档状态
        if document.status not in ["uploaded", "failed"]:
            raise ServiceException(f"文档状态不允许处理: {document.status}")
        
        # 获取RAG实例
        rag_instance = await self.rag_manager.get_rag_instance()
        if not rag_instance:
            raise ServiceException("RAG系统不可用")
        
        try:
            # 更新文档状态为处理中
            await self.state_manager.update_document_status(
                document_id,
                "processing",
                processing_start_time=datetime.now().isoformat()
            )
            
            # 获取处理策略
            strategy = ProcessingStrategyFactory.get_strategy(config.parser)
            
            # 执行处理
            result = await strategy.process(document, config, rag_instance)
            
            # 更新文档状态
            if result.success:
                await self.state_manager.update_document_status(
                    document_id,
                    "completed",
                    processing_end_time=datetime.now().isoformat(),
                    chunks_count=result.chunks_count,
                    processing_time_seconds=result.processing_time_seconds
                )
            else:
                await self.state_manager.update_document_status(
                    document_id,
                    "failed",
                    processing_end_time=datetime.now().isoformat(),
                    error_message=result.message,
                    processing_time_seconds=result.processing_time_seconds
                )
            
            return result
            
        except Exception as e:
            # 更新文档状态为失败
            await self.state_manager.update_document_status(
                document_id,
                "failed",
                processing_end_time=datetime.now().isoformat(),
                error_message=str(e)
            )
            
            raise ServiceException(f"文档处理失败: {str(e)}") from e
    
    async def process_document_async(
        self,
        document_id: str,
        config: Optional[ProcessingConfig] = None
    ) -> str:
        """
        异步处理文档（后台任务）
        
        Args:
            document_id: 文档ID
            config: 处理配置
            
        Returns:
            str: 任务ID
        """
        # 创建后台任务
        task = asyncio.create_task(
            self._process_document_background(document_id, config)
        )
        
        # 存储任务引用
        task_id = f"process_{document_id}_{datetime.now().timestamp()}"
        self._active_tasks[task_id] = task
        
        # 清理完成的任务
        task.add_done_callback(lambda t: self._cleanup_task(task_id))
        
        return task_id
    
    async def get_processing_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取处理任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务状态信息
        """
        if task_id not in self._active_tasks:
            return {
                "task_id": task_id,
                "status": "not_found",
                "message": "任务不存在或已完成"
            }
        
        task = self._active_tasks[task_id]
        
        if task.done():
            try:
                result = task.result()
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "result": result.dict()
                }
            except Exception as e:
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e)
                }
        else:
            return {
                "task_id": task_id,
                "status": "running",
                "message": "处理中..."
            }
    
    async def cancel_processing(self, task_id: str) -> bool:
        """
        取消处理任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        if task_id not in self._active_tasks:
            return False
        
        task = self._active_tasks[task_id]
        if not task.done():
            task.cancel()
            return True
        
        return False
    
    def get_supported_parsers(self) -> List[str]:
        """获取支持的解析器列表"""
        return [parser.value for parser in ParserType]
    
    def get_supported_methods(self) -> List[str]:
        """获取支持的解析方法列表"""
        return [method.value for method in ParseMethod]
    
    async def validate_processing_config(self, config: ProcessingConfig) -> Dict[str, Any]:
        """
        验证处理配置
        
        Args:
            config: 处理配置
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        validation_result = {
            "valid": True,
            "warnings": [],
            "errors": []
        }
        
        # 检查解析器支持
        try:
            ProcessingStrategyFactory.get_strategy(config.parser)
        except ConfigurationError as e:
            validation_result["valid"] = False
            validation_result["errors"].append(str(e))
        
        # 检查设备配置
        if config.device and not config.device.startswith(("cpu", "cuda", "mps")):
            validation_result["warnings"].append(f"未知设备类型: {config.device}")
        
        # 检查页码范围
        if (config.start_page is not None and config.end_page is not None and
            config.start_page > config.end_page):
            validation_result["valid"] = False
            validation_result["errors"].append("起始页码不能大于结束页码")
        
        return validation_result
    
    # === 私有方法 ===
    
    async def _process_document_background(
        self,
        document_id: str,
        config: Optional[ProcessingConfig]
    ) -> ProcessingResult:
        """后台处理文档"""
        try:
            return await self.process_document(document_id, config)
        except Exception as e:
            # 记录错误日志
            return ProcessingResult(
                success=False,
                document_id=document_id,
                task_id="",
                file_name="unknown",
                message=f"后台处理失败: {str(e)}",
                error_details={"background_error": str(e)}
            )
    
    def _cleanup_task(self, task_id: str):
        """清理完成的任务"""
        if task_id in self._active_tasks:
            del self._active_tasks[task_id]
    
    async def _get_chunks_count(self, rag_instance: Any, document: Document) -> Optional[int]:
        """获取处理后的文本块数量"""
        try:
            # TODO: 实现获取chunks数量的逻辑
            # 这需要从LightRAG实例中查询相关文档的chunks数量
            return None
        except Exception:
            return None