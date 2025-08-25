#!/usr/bin/env python3
"""
Query Optimization Layer for Mixed Content Scenarios
Filters corrupted content and optimizes query performance in RAG systems
"""

import json
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ContentQualityMetrics:
    """Content quality assessment metrics"""
    corruption_score: float  # 0-1, higher = more corrupted
    readability_score: float  # 0-1, higher = more readable
    information_density: float  # 0-1, higher = more informative
    confidence_score: float  # 0-1, overall quality confidence
    corruption_patterns: List[str]


class ContentQualityAnalyzer:
    """Analyzes content quality to filter corrupted results"""
    
    def __init__(self):
        self.corruption_patterns = {
            'repeated_chars': r'(.)\1{10,}',
            'chinese_corruption': r'[规锟烫鎻]{10,}',
            'unicode_errors': r'[\ufffd]{3,}',
            'punctuation_spam': r'[《》、。，]{10,}',
            'whitespace_excess': r'\s{20,}',
            'control_chars': r'[\x00-\x1f]{5,}'
        }
        
        self.quality_indicators = {
            'sentence_structure': r'[.!?][\s\n]+[A-Z\u4e00-\u9fa5]',
            'word_boundaries': r'\b\w+\b',
            'coherent_phrases': r'[a-zA-Z\u4e00-\u9fa5]{3,}',
            'punctuation_balance': r'[,.!?;:]'
        }
        
    def analyze_content_quality(self, content: str) -> ContentQualityMetrics:
        """Analyze content quality and return metrics"""
        if not content or len(content.strip()) == 0:
            return ContentQualityMetrics(
                corruption_score=1.0,
                readability_score=0.0,
                information_density=0.0,
                confidence_score=0.0,
                corruption_patterns=['empty_content']
            )
        
        # Check for corruption patterns
        corruption_score = 0.0
        detected_patterns = []
        
        for pattern_name, pattern in self.corruption_patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                detected_patterns.append(pattern_name)
                # Weight corruption score based on pattern severity
                if pattern_name in ['repeated_chars', 'chinese_corruption']:
                    corruption_score += 0.4
                elif pattern_name in ['unicode_errors', 'control_chars']:
                    corruption_score += 0.3
                else:
                    corruption_score += 0.1
        
        corruption_score = min(corruption_score, 1.0)
        
        # Assess readability
        readability_score = self._calculate_readability(content)
        
        # Calculate information density
        information_density = self._calculate_information_density(content)
        
        # Overall confidence (inverse of corruption, weighted by readability)
        confidence_score = (1.0 - corruption_score) * 0.6 + readability_score * 0.4
        
        return ContentQualityMetrics(
            corruption_score=corruption_score,
            readability_score=readability_score,
            information_density=information_density,
            confidence_score=confidence_score,
            corruption_patterns=detected_patterns
        )
    
    def _calculate_readability(self, content: str) -> float:
        """Calculate readability score based on text structure"""
        if not content:
            return 0.0
        
        score = 0.0
        total_checks = 0
        
        # Check for sentence structure
        sentences = re.findall(self.quality_indicators['sentence_structure'], content)
        total_checks += 1
        if len(sentences) > 0:
            score += min(len(sentences) / (len(content) / 100), 1.0) * 0.3
        
        # Check word boundaries
        words = re.findall(self.quality_indicators['word_boundaries'], content)
        total_checks += 1
        if len(words) > 0:
            score += min(len(words) / max(len(content) / 10, 1), 1.0) * 0.4
        
        # Check coherent phrases
        phrases = re.findall(self.quality_indicators['coherent_phrases'], content)
        total_checks += 1
        if len(phrases) > 0:
            score += min(len(phrases) / max(len(content) / 20, 1), 1.0) * 0.3
        
        return min(score, 1.0)
    
    def _calculate_information_density(self, content: str) -> float:
        """Calculate information density of the content"""
        if not content:
            return 0.0
        
        # Simple heuristic: ratio of unique characters to total length
        unique_chars = len(set(content))
        total_chars = len(content)
        
        # Normalize by expected character diversity
        if total_chars == 0:
            return 0.0
        
        density = unique_chars / min(total_chars, 1000)  # Cap at reasonable length
        return min(density * 2, 1.0)  # Scale and cap at 1.0


class QueryResultFilter:
    """Filters query results based on content quality"""
    
    def __init__(self, min_confidence_threshold: float = 0.3):
        self.min_confidence_threshold = min_confidence_threshold
        self.quality_analyzer = ContentQualityAnalyzer()
    
    def filter_results(self, results: List[Dict[str, Any]], 
                      max_results: int = 10) -> List[Dict[str, Any]]:
        """Filter and rank results by quality"""
        if not results:
            return results
        
        # Analyze quality for each result
        scored_results = []
        for result in results:
            content = result.get('content', '') or result.get('text', '') or str(result)
            quality_metrics = self.quality_analyzer.analyze_content_quality(content)
            
            # Only include results above confidence threshold
            if quality_metrics.confidence_score >= self.min_confidence_threshold:
                scored_results.append({
                    **result,
                    '_quality_score': quality_metrics.confidence_score,
                    '_corruption_score': quality_metrics.corruption_score,
                    '_quality_metrics': quality_metrics
                })
        
        # Sort by quality score (descending)
        scored_results.sort(key=lambda x: x['_quality_score'], reverse=True)
        
        # Return top results
        return scored_results[:max_results]
    
    def is_content_corrupted(self, content: str) -> bool:
        """Quick check if content is corrupted"""
        quality_metrics = self.quality_analyzer.analyze_content_quality(content)
        return quality_metrics.corruption_score > 0.5 or quality_metrics.confidence_score < 0.2


class SmartQueryOptimizer:
    """Optimizes query performance with corruption awareness"""
    
    def __init__(self, rag_storage_path: str = "/home/ragsvr/projects/ragsystem/rag_storage"):
        self.storage_path = Path(rag_storage_path)
        self.result_filter = QueryResultFilter()
        self.query_cache = {}  # Simple query result cache
        self.performance_stats = {
            'queries_processed': 0,
            'corrupted_results_filtered': 0,
            'cache_hits': 0,
            'avg_result_quality': 0.0
        }
    
    def optimize_query(self, query: str, raw_results: List[Dict[str, Any]], 
                      query_mode: str = "hybrid") -> Dict[str, Any]:
        """Optimize query results by filtering corruption and ranking by quality"""
        self.performance_stats['queries_processed'] += 1
        
        # Check cache first
        cache_key = f"{hash(query)}_{query_mode}_{len(raw_results)}"
        if cache_key in self.query_cache:
            self.performance_stats['cache_hits'] += 1
            return self.query_cache[cache_key]
        
        # Filter corrupted results
        initial_count = len(raw_results)
        filtered_results = self.result_filter.filter_results(raw_results)
        corrupted_filtered = initial_count - len(filtered_results)
        
        self.performance_stats['corrupted_results_filtered'] += corrupted_filtered
        
        # Calculate average quality
        if filtered_results:
            avg_quality = sum(r.get('_quality_score', 0) for r in filtered_results) / len(filtered_results)
            self.performance_stats['avg_result_quality'] = (
                self.performance_stats['avg_result_quality'] * 0.9 + avg_quality * 0.1
            )
        
        # Enhance results with quality metadata
        enhanced_results = self._enhance_results_metadata(filtered_results)
        
        optimized_response = {
            'query': query,
            'mode': query_mode,
            'results': enhanced_results,
            'quality_stats': {
                'total_candidates': initial_count,
                'quality_filtered': len(filtered_results),
                'corrupted_filtered': corrupted_filtered,
                'avg_quality_score': avg_quality if filtered_results else 0.0
            },
            'optimization_applied': True
        }
        
        # Cache the result
        self.query_cache[cache_key] = optimized_response
        
        # Limit cache size
        if len(self.query_cache) > 1000:
            # Remove oldest entries (simple FIFO)
            oldest_keys = list(self.query_cache.keys())[:100]
            for key in oldest_keys:
                del self.query_cache[key]
        
        return optimized_response
    
    def _enhance_results_metadata(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add quality and relevance metadata to results"""
        enhanced = []
        
        for result in results:
            quality_metrics = result.get('_quality_metrics')
            if quality_metrics:
                enhanced_result = {
                    **result,
                    'quality_indicators': {
                        'confidence_score': quality_metrics.confidence_score,
                        'corruption_detected': quality_metrics.corruption_score > 0.3,
                        'readability_score': quality_metrics.readability_score,
                        'information_density': quality_metrics.information_density
                    }
                }
                
                # Remove internal quality metrics from final result
                enhanced_result.pop('_quality_metrics', None)
                enhanced_result.pop('_quality_score', None)
                enhanced_result.pop('_corruption_score', None)
                
                enhanced.append(enhanced_result)
            else:
                enhanced.append(result)
        
        return enhanced
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return self.performance_stats.copy()
    
    def clear_cache(self):
        """Clear query cache"""
        self.query_cache.clear()
        logger.info("Query cache cleared")


class RAGQueryWrapper:
    """Wrapper class that adds optimization layer to RAG queries"""
    
    def __init__(self, lightrag_instance, enable_optimization: bool = True):
        self.lightrag = lightrag_instance
        self.enable_optimization = enable_optimization
        self.optimizer = SmartQueryOptimizer() if enable_optimization else None
    
    async def optimized_query(self, query: str, mode: str = "hybrid", 
                            response_type: str = "multiple", 
                            **kwargs) -> str:
        """Execute optimized query with corruption filtering"""
        if not self.enable_optimization:
            # Fall back to standard query
            return await self.lightrag.aquery(query, mode=mode, response_type=response_type, **kwargs)
        
        # Execute standard query first
        try:
            raw_response = await self.lightrag.aquery(query, mode=mode, response_type=response_type, **kwargs)
            
            # For string responses, we need to parse or work with the response differently
            # This is a simplified approach - in practice, you'd need to integrate deeper
            # with LightRAG's internal result processing
            
            if isinstance(raw_response, str):
                # Basic corruption check on the final response
                if self.optimizer.result_filter.is_content_corrupted(raw_response):
                    logger.warning("Query response appears corrupted, attempting alternative mode")
                    
                    # Try alternative query mode
                    alternative_mode = "local" if mode != "local" else "global"
                    raw_response = await self.lightrag.aquery(query, mode=alternative_mode, 
                                                            response_type=response_type, **kwargs)
            
            return raw_response
            
        except Exception as e:
            logger.error(f"Optimized query failed: {e}")
            # Fall back to standard query
            return await self.lightrag.aquery(query, mode=mode, response_type=response_type, **kwargs)
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization performance statistics"""
        if self.optimizer:
            return self.optimizer.get_performance_stats()
        return {'optimization_disabled': True}


# Usage example and testing
def test_query_optimization():
    """Test query optimization functionality"""
    analyzer = ContentQualityAnalyzer()
    
    # Test content samples
    good_content = "This is a well-formed document with proper structure and readable content."
    corrupted_content = "规规规规规规规规规规规规规规规规规规规规规规规规规规规规"
    mixed_content = "This document starts well but then becomes 国国国国国国国国国国国国国"
    
    print("=== Content Quality Analysis ===")
    for label, content in [("Good", good_content), ("Corrupted", corrupted_content), ("Mixed", mixed_content)]:
        metrics = analyzer.analyze_content_quality(content)
        print(f"\n{label} Content:")
        print(f"  Corruption Score: {metrics.corruption_score:.3f}")
        print(f"  Readability Score: {metrics.readability_score:.3f}")
        print(f"  Information Density: {metrics.information_density:.3f}")
        print(f"  Confidence Score: {metrics.confidence_score:.3f}")
        print(f"  Detected Patterns: {metrics.corruption_patterns}")
    
    # Test result filtering
    filter = QueryResultFilter(min_confidence_threshold=0.3)
    sample_results = [
        {'content': good_content, 'source': 'doc1'},
        {'content': corrupted_content, 'source': 'doc2'},
        {'content': mixed_content, 'source': 'doc3'}
    ]
    
    filtered = filter.filter_results(sample_results)
    print(f"\n=== Result Filtering ===")
    print(f"Original results: {len(sample_results)}")
    print(f"Filtered results: {len(filtered)}")
    for result in filtered:
        print(f"  Source: {result['source']}, Quality: {result['_quality_score']:.3f}")


if __name__ == "__main__":
    test_query_optimization()