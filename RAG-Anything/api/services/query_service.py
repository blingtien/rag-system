"""
QueryService - 查询服务
实现查询处理和结果优化，支持多种查询模式和结果缓存
"""
import time
import hashlib
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime, timedelta

from pydantic import BaseModel

from core.state_manager import StateManager
from core.rag_manager import RAGManager
from services.exceptions import ServiceException, QueryError


class QueryMode(Enum):
    """查询模式"""
    NAIVE = "naive"
    LOCAL = "local"
    GLOBAL = "global"
    HYBRID = "hybrid"


class QueryRequest(BaseModel):
    """查询请求"""
    query: str
    mode: QueryMode = QueryMode.HYBRID
    vlm_enhanced: bool = False
    multimodal_content: Optional[List[Dict[str, Any]]] = None
    only_need_context: bool = False
    response_type: str = "Multiple Paragraphs"
    
    class Config:
        use_enum_values = True


class QueryResult(BaseModel):
    """查询结果"""
    success: bool
    query: str
    mode: str
    response: str
    response_time_seconds: float
    token_count: Optional[int] = None
    source_documents: Optional[List[Dict[str, Any]]] = None
    cache_hit: bool = False
    timestamp: str


class CachedQuery(BaseModel):
    """缓存的查询"""
    query_hash: str
    query: str
    mode: str
    result: QueryResult
    created_at: str
    last_accessed: str
    access_count: int = 1


class QueryCache:
    """
    查询缓存管理器
    实现智能缓存策略，提高查询性能
    """
    
    def __init__(self, max_size: int = 1000, ttl_hours: int = 24):
        self.max_size = max_size
        self.ttl_hours = ttl_hours
        self._cache: Dict[str, CachedQuery] = {}
        self._access_order: List[str] = []
    
    def _generate_cache_key(self, query: str, mode: str, **kwargs) -> str:
        """生成缓存键"""
        cache_data = {
            "query": query.strip().lower(),
            "mode": mode,
            **kwargs
        }
        cache_str = str(sorted(cache_data.items()))
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def get(self, query: str, mode: str, **kwargs) -> Optional[QueryResult]:
        """获取缓存的查询结果"""
        cache_key = self._generate_cache_key(query, mode, **kwargs)
        
        if cache_key not in self._cache:
            return None
        
        cached_query = self._cache[cache_key]
        
        # 检查TTL
        created_time = datetime.fromisoformat(cached_query.created_at)
        if datetime.now() - created_time > timedelta(hours=self.ttl_hours):
            self._remove_cache_entry(cache_key)
            return None
        
        # 更新访问信息
        cached_query.last_accessed = datetime.now().isoformat()
        cached_query.access_count += 1
        
        # 更新访问顺序
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)
        self._access_order.append(cache_key)
        
        # 标记结果为缓存命中
        result = cached_query.result.copy()
        result.cache_hit = True
        return result
    
    def set(self, query: str, mode: str, result: QueryResult, **kwargs):
        """设置缓存"""
        cache_key = self._generate_cache_key(query, mode, **kwargs)
        
        # 检查缓存大小，必要时清理
        if len(self._cache) >= self.max_size:
            self._evict_least_recently_used()
        
        # 创建缓存条目
        cached_query = CachedQuery(
            query_hash=cache_key,
            query=query,
            mode=mode,
            result=result,
            created_at=datetime.now().isoformat(),
            last_accessed=datetime.now().isoformat()
        )
        
        self._cache[cache_key] = cached_query
        self._access_order.append(cache_key)
    
    def _evict_least_recently_used(self):
        """驱逐最少使用的缓存条目"""
        if self._access_order:
            lru_key = self._access_order.pop(0)
            self._remove_cache_entry(lru_key)
    
    def _remove_cache_entry(self, cache_key: str):
        """移除缓存条目"""
        if cache_key in self._cache:
            del self._cache[cache_key]
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._access_order.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_access = sum(cached.access_count for cached in self._cache.values())
        
        return {
            "cache_size": len(self._cache),
            "max_size": self.max_size,
            "total_access_count": total_access,
            "average_access_per_query": total_access / len(self._cache) if self._cache else 0,
            "oldest_query": min(
                (cached.created_at for cached in self._cache.values()),
                default=None
            ),
            "newest_query": max(
                (cached.created_at for cached in self._cache.values()),
                default=None
            )
        }


class QueryOptimizer:
    """
    查询优化器
    负责查询预处理、后处理和结果优化
    """
    
    @staticmethod
    def optimize_query(query: str) -> str:
        """优化查询文本"""
        # 基本清理
        optimized = query.strip()
        
        # 移除多余空格
        optimized = ' '.join(optimized.split())
        
        # 这里可以添加更多优化逻辑：
        # - 同义词替换
        # - 查询扩展
        # - 语法纠错
        
        return optimized
    
    @staticmethod
    def enhance_response(response: str, query: str, mode: str) -> str:
        """增强响应内容"""
        # 基本后处理
        enhanced = response.strip()
        
        # 根据查询模式进行优化
        if mode == "global":
            # 为全局查询添加上下文说明
            if not enhanced.startswith("从整体知识库的角度来看"):
                enhanced = f"从整体知识库的角度来看，{enhanced}"
        
        elif mode == "local":
            # 为本地查询添加具体性说明
            if "具体来说" not in enhanced and "详细地说" not in enhanced:
                enhanced = f"详细地说，{enhanced}"
        
        return enhanced
    
    @staticmethod
    def extract_source_info(rag_instance, query: str) -> Optional[List[Dict[str, Any]]]:
        """提取源文档信息"""
        try:
            # TODO: 实现从RAG实例中提取源文档信息
            # 这需要LightRAG提供相关API
            return None
        except Exception:
            return None


class QueryService:
    """
    查询服务
    
    负责处理用户查询，应用缓存策略和结果优化
    支持多种查询模式和多模态查询
    """
    
    def __init__(
        self,
        state_manager: StateManager,
        rag_manager: RAGManager,
        enable_cache: bool = True,
        cache_ttl_hours: int = 24
    ):
        self.state_manager = state_manager
        self.rag_manager = rag_manager
        self.enable_cache = enable_cache
        
        # 初始化缓存
        if enable_cache:
            self.cache = QueryCache(ttl_hours=cache_ttl_hours)
        else:
            self.cache = None
        
        # 查询优化器
        self.optimizer = QueryOptimizer()
        
        # 查询统计
        self.query_stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "average_response_time": 0.0,
            "mode_usage": {}
        }
    
    async def query(self, request: QueryRequest) -> QueryResult:
        """
        执行查询
        
        Args:
            request: 查询请求
            
        Returns:
            QueryResult: 查询结果
            
        Raises:
            ServiceException: 服务层异常
            QueryError: 查询处理异常
        """
        start_time = time.time()
        
        try:
            # 优化查询文本
            optimized_query = self.optimizer.optimize_query(request.query)
            
            # 检查缓存
            if self.enable_cache and self.cache:
                cached_result = self.cache.get(
                    optimized_query,
                    request.mode.value,
                    vlm_enhanced=request.vlm_enhanced,
                    only_need_context=request.only_need_context
                )
                
                if cached_result:
                    self._update_query_stats(request.mode.value, True, time.time() - start_time)
                    return cached_result
            
            # 获取RAG实例
            rag_instance = await self.rag_manager.get_rag_instance()
            if not rag_instance:
                raise ServiceException("RAG系统不可用")
            
            # 执行查询
            response = await self._execute_query(rag_instance, request, optimized_query)
            
            # 后处理响应
            enhanced_response = self.optimizer.enhance_response(
                response, optimized_query, request.mode.value
            )
            
            # 计算响应时间
            response_time = time.time() - start_time
            
            # 提取源文档信息
            source_docs = self.optimizer.extract_source_info(rag_instance, optimized_query)
            
            # 创建结果
            result = QueryResult(
                success=True,
                query=optimized_query,
                mode=request.mode.value,
                response=enhanced_response,
                response_time_seconds=response_time,
                source_documents=source_docs,
                cache_hit=False,
                timestamp=datetime.now().isoformat()
            )
            
            # 缓存结果
            if self.enable_cache and self.cache:
                self.cache.set(
                    optimized_query,
                    request.mode.value,
                    result,
                    vlm_enhanced=request.vlm_enhanced,
                    only_need_context=request.only_need_context
                )
            
            # 更新统计
            self._update_query_stats(request.mode.value, False, response_time)
            
            return result
            
        except Exception as e:
            response_time = time.time() - start_time
            
            # 创建失败结果
            error_result = QueryResult(
                success=False,
                query=request.query,
                mode=request.mode.value,
                response=f"查询失败: {str(e)}",
                response_time_seconds=response_time,
                timestamp=datetime.now().isoformat()
            )
            
            self._update_query_stats(request.mode.value, False, response_time)
            
            raise ServiceException(f"查询处理失败: {str(e)}") from e
    
    async def batch_query(self, requests: List[QueryRequest]) -> List[QueryResult]:
        """
        批量查询
        
        Args:
            requests: 查询请求列表
            
        Returns:
            List[QueryResult]: 查询结果列表
        """
        results = []
        
        for request in requests:
            try:
                result = await self.query(request)
                results.append(result)
            except Exception as e:
                # 创建失败结果
                error_result = QueryResult(
                    success=False,
                    query=request.query,
                    mode=request.mode.value,
                    response=f"批量查询项失败: {str(e)}",
                    response_time_seconds=0.0,
                    timestamp=datetime.now().isoformat()
                )
                results.append(error_result)
        
        return results
    
    async def get_query_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
        """
        获取查询建议
        
        Args:
            partial_query: 部分查询文本
            limit: 返回建议数量限制
            
        Returns:
            List[str]: 查询建议列表
        """
        try:
            # 基于缓存历史生成建议
            suggestions = []
            
            if self.cache:
                for cached_query in self.cache._cache.values():
                    if partial_query.lower() in cached_query.query.lower():
                        suggestions.append(cached_query.query)
                    
                    if len(suggestions) >= limit:
                        break
            
            # TODO: 可以集成更智能的建议系统
            # - 基于语义相似性的建议
            # - 基于流行查询的建议
            # - 基于文档内容的建议
            
            return suggestions
            
        except Exception as e:
            raise ServiceException(f"获取查询建议失败: {str(e)}") from e
    
    def get_query_statistics(self) -> Dict[str, Any]:
        """获取查询统计信息"""
        stats = self.query_stats.copy()
        
        # 计算缓存命中率
        total_queries = stats["total_queries"]
        if total_queries > 0:
            stats["cache_hit_rate"] = stats["cache_hits"] / total_queries * 100
        else:
            stats["cache_hit_rate"] = 0.0
        
        # 添加缓存统计
        if self.cache:
            stats["cache_stats"] = self.cache.get_stats()
        
        return stats
    
    def clear_cache(self):
        """清空查询缓存"""
        if self.cache:
            self.cache.clear()
    
    def get_cache_size(self) -> int:
        """获取缓存大小"""
        if self.cache:
            return len(self.cache._cache)
        return 0
    
    async def validate_query(self, query: str) -> Dict[str, Any]:
        """
        验证查询
        
        Args:
            query: 查询文本
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        validation_result = {
            "valid": True,
            "warnings": [],
            "suggestions": []
        }
        
        # 检查查询长度
        if len(query.strip()) < 3:
            validation_result["valid"] = False
            validation_result["warnings"].append("查询文本过短，至少需要3个字符")
        
        if len(query) > 1000:
            validation_result["warnings"].append("查询文本较长，可能影响处理效率")
        
        # 检查特殊字符
        special_chars = ['<', '>', '{', '}', '[', ']']
        if any(char in query for char in special_chars):
            validation_result["warnings"].append("查询包含特殊字符，可能影响解析")
        
        # 提供优化建议
        optimized = self.optimizer.optimize_query(query)
        if optimized != query:
            validation_result["suggestions"].append(f"建议优化为: {optimized}")
        
        return validation_result
    
    # === 私有方法 ===
    
    async def _execute_query(
        self,
        rag_instance,
        request: QueryRequest,
        optimized_query: str
    ) -> str:
        """执行具体的查询"""
        try:
            if request.multimodal_content:
                # 多模态查询
                response = await rag_instance.aquery_with_multimodal(
                    optimized_query,
                    multimodal_content=request.multimodal_content,
                    mode=request.mode.value,
                    only_need_context=request.only_need_context,
                    response_type=request.response_type
                )
            elif request.vlm_enhanced:
                # VLM增强查询
                response = await rag_instance.aquery(
                    optimized_query,
                    mode=request.mode.value,
                    vlm_enhanced=True,
                    only_need_context=request.only_need_context,
                    response_type=request.response_type
                )
            else:
                # 标准查询
                response = await rag_instance.aquery(
                    optimized_query,
                    mode=request.mode.value,
                    only_need_context=request.only_need_context,
                    response_type=request.response_type
                )
            
            return response
            
        except Exception as e:
            raise QueryError(f"RAG查询执行失败: {str(e)}") from e
    
    def _update_query_stats(self, mode: str, cache_hit: bool, response_time: float):
        """更新查询统计"""
        self.query_stats["total_queries"] += 1
        
        if cache_hit:
            self.query_stats["cache_hits"] += 1
        else:
            self.query_stats["cache_misses"] += 1
        
        # 更新平均响应时间
        total = self.query_stats["total_queries"]
        current_avg = self.query_stats["average_response_time"]
        self.query_stats["average_response_time"] = (
            (current_avg * (total - 1) + response_time) / total
        )
        
        # 更新模式使用统计
        if mode not in self.query_stats["mode_usage"]:
            self.query_stats["mode_usage"][mode] = 0
        self.query_stats["mode_usage"][mode] += 1