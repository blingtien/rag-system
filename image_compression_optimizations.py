#!/usr/bin/env python3
"""
Performance Optimizations for Image Compression Implementation

This module provides optimized versions of the image compression utilities
with caching, async processing, memory pooling, and other performance improvements.
"""

import os
import sys
import asyncio
import base64
import io
import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache, wraps
from dataclasses import dataclass
import threading
import queue
import logging
from PIL import Image
import numpy as np

# Add RAG-Anything to path
sys.path.insert(0, '/home/ragsvr/projects/ragsystem/RAG-Anything')

logger = logging.getLogger(__name__)


@dataclass
class CompressionCache:
    """LRU cache for compressed images"""
    max_size: int = 100
    ttl_seconds: int = 3600
    
    def __post_init__(self):
        self.cache: Dict[str, Tuple[str, float]] = {}
        self.access_times: Dict[str, float] = {}
        self.lock = threading.Lock()
    
    def get_cache_key(self, image_path: str, max_size_kb: int, max_dimension: int) -> str:
        """Generate cache key for image compression parameters"""
        # Include file modification time for cache invalidation
        mtime = os.path.getmtime(image_path) if os.path.exists(image_path) else 0
        key_parts = [image_path, str(max_size_kb), str(max_dimension), str(mtime)]
        return hashlib.md5('|'.join(key_parts).encode()).hexdigest()
    
    def get(self, key: str) -> Optional[str]:
        """Get cached compression result"""
        with self.lock:
            if key in self.cache:
                result, timestamp = self.cache[key]
                # Check TTL
                if time.time() - timestamp < self.ttl_seconds:
                    self.access_times[key] = time.time()
                    logger.debug(f"Cache hit for key: {key}")
                    return result
                else:
                    # Expired
                    del self.cache[key]
                    del self.access_times[key]
                    logger.debug(f"Cache expired for key: {key}")
            return None
    
    def set(self, key: str, value: str):
        """Set cached compression result"""
        with self.lock:
            # Implement LRU eviction if cache is full
            if len(self.cache) >= self.max_size:
                # Find least recently used
                lru_key = min(self.access_times, key=self.access_times.get)
                del self.cache[lru_key]
                del self.access_times[lru_key]
                logger.debug(f"Evicted LRU cache entry: {lru_key}")
            
            self.cache[key] = (value, time.time())
            self.access_times[key] = time.time()
            logger.debug(f"Cache set for key: {key}")
    
    def clear(self):
        """Clear the cache"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'ttl_seconds': self.ttl_seconds,
                'oldest_entry_age': min(
                    [time.time() - t for _, t in self.cache.values()],
                    default=0
                )
            }


class ImageMemoryPool:
    """Memory pool for reusing PIL Image objects and buffers"""
    
    def __init__(self, pool_size: int = 10):
        self.pool_size = pool_size
        self.image_pool = queue.Queue(maxsize=pool_size)
        self.buffer_pool = queue.Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        
        # Pre-allocate buffers
        for _ in range(pool_size // 2):
            self.buffer_pool.put(io.BytesIO())
    
    def get_buffer(self) -> io.BytesIO:
        """Get a buffer from the pool or create a new one"""
        try:
            buffer = self.buffer_pool.get_nowait()
            buffer.seek(0)
            buffer.truncate(0)
            return buffer
        except queue.Empty:
            return io.BytesIO()
    
    def return_buffer(self, buffer: io.BytesIO):
        """Return a buffer to the pool"""
        try:
            buffer.seek(0)
            buffer.truncate(0)
            self.buffer_pool.put_nowait(buffer)
        except queue.Full:
            # Pool is full, let it be garbage collected
            pass


class AsyncImageCompressor:
    """Async image compression with optimizations"""
    
    def __init__(
        self,
        max_workers: int = 4,
        cache_size: int = 100,
        use_memory_pool: bool = True
    ):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.cache = CompressionCache(max_size=cache_size)
        self.memory_pool = ImageMemoryPool() if use_memory_pool else None
        self.stats = {
            'compressions': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_time': 0,
            'total_bytes_saved': 0
        }
        self.stats_lock = threading.Lock()
    
    async def compress_image_async(
        self,
        image_path: str,
        max_size_kb: int = 200,
        max_dimension: int = 1024,
        force_compression: bool = True
    ) -> Optional[str]:
        """Async wrapper for image compression with caching"""
        # Check cache first
        cache_key = self.cache.get_cache_key(image_path, max_size_kb, max_dimension)
        cached_result = self.cache.get(cache_key)
        
        if cached_result:
            with self.stats_lock:
                self.stats['cache_hits'] += 1
            return cached_result
        
        with self.stats_lock:
            self.stats['cache_misses'] += 1
        
        # Perform compression in thread pool
        start_time = time.time()
        result = await asyncio.get_event_loop().run_in_executor(
            self.executor,
            self._compress_image_optimized,
            image_path,
            max_size_kb,
            max_dimension,
            force_compression
        )
        
        compression_time = time.time() - start_time
        
        # Update stats
        with self.stats_lock:
            self.stats['compressions'] += 1
            self.stats['total_time'] += compression_time
        
        # Cache the result
        if result:
            self.cache.set(cache_key, result)
            
            # Calculate bytes saved
            original_size = os.path.getsize(image_path)
            compressed_size = len(result)
            bytes_saved = max(0, original_size - compressed_size)
            
            with self.stats_lock:
                self.stats['total_bytes_saved'] += bytes_saved
        
        return result
    
    def _compress_image_optimized(
        self,
        image_path: str,
        max_size_kb: int,
        max_dimension: int,
        force_compression: bool
    ) -> Optional[str]:
        """Optimized compression implementation"""
        try:
            if not os.path.exists(image_path):
                logger.error(f"Image file not found: {image_path}")
                return None
            
            # Use memory-mapped file for large images
            file_size = os.path.getsize(image_path)
            use_mmap = file_size > 10 * 1024 * 1024  # 10MB threshold
            
            # Open image with optimization hints
            with Image.open(image_path) as img:
                # Quick size check
                if not force_compression and self._estimate_base64_size(img) <= max_size_kb:
                    # Read and encode directly
                    with open(image_path, 'rb') as f:
                        return base64.b64encode(f.read()).decode('utf-8')
                
                # Convert color mode efficiently
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = self._convert_image_mode_optimized(img)
                elif img.mode not in ['RGB', 'L']:
                    img = img.convert('RGB')
                
                # Resize if needed
                if img.width > max_dimension or img.height > max_dimension:
                    img = self._resize_image_optimized(img, max_dimension)
                
                # Progressive compression with early exit
                return self._progressive_compress_optimized(img, max_size_kb)
                
        except Exception as e:
            logger.error(f"Optimized compression failed for {image_path}: {e}")
            return None
    
    def _estimate_base64_size(self, img: Image.Image) -> float:
        """Quick estimation of base64 encoded size"""
        # Rough estimation based on image dimensions and mode
        bytes_per_pixel = {'L': 1, 'RGB': 3, 'RGBA': 4}.get(img.mode, 3)
        estimated_bytes = img.width * img.height * bytes_per_pixel
        # JPEG compression typically achieves 10:1 to 20:1 ratio
        estimated_compressed = estimated_bytes / 15
        # Base64 adds ~33% overhead
        estimated_base64 = estimated_compressed * 1.33
        return estimated_base64 / 1024  # Return in KB
    
    def _convert_image_mode_optimized(self, img: Image.Image) -> Image.Image:
        """Optimized color mode conversion"""
        # Use faster conversion methods
        if img.mode == 'RGBA':
            # Create white background more efficiently
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
            return background
        elif img.mode == 'P':
            # Convert palette images
            return img.convert('RGB')
        elif img.mode == 'LA':
            # Convert grayscale with alpha
            return img.convert('RGB')
        return img
    
    def _resize_image_optimized(self, img: Image.Image, max_dimension: int) -> Image.Image:
        """Optimized image resizing"""
        ratio = min(max_dimension / img.width, max_dimension / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        
        # Use appropriate resampling based on size reduction
        if ratio < 0.5:
            # For significant downscaling, use faster algorithm
            return img.resize(new_size, Image.Resampling.BILINEAR)
        else:
            # For moderate scaling, use high quality
            return img.resize(new_size, Image.Resampling.LANCZOS)
    
    def _progressive_compress_optimized(self, img: Image.Image, max_size_kb: int) -> Optional[str]:
        """Optimized progressive compression with early exit"""
        # Use binary search for faster quality finding
        min_quality = 20
        max_quality = 95
        best_result = None
        best_size = float('inf')
        
        # Get buffer from pool if available
        buffer = self.memory_pool.get_buffer() if self.memory_pool else io.BytesIO()
        
        try:
            # Binary search for optimal quality
            while min_quality <= max_quality:
                quality = (min_quality + max_quality) // 2
                
                buffer.seek(0)
                buffer.truncate(0)
                
                # Save with current quality
                save_kwargs = {
                    'format': 'JPEG',
                    'quality': quality,
                    'optimize': quality > 60,  # Only optimize for higher qualities
                    'progressive': quality < 50  # Progressive for lower qualities
                }
                
                img.save(buffer, **save_kwargs)
                
                # Check size
                compressed_data = buffer.getvalue()
                encoded_string = base64.b64encode(compressed_data).decode('utf-8')
                size_kb = len(encoded_string) / 1024
                
                if size_kb <= max_size_kb:
                    # Found valid compression
                    best_result = encoded_string
                    best_size = size_kb
                    # Try higher quality
                    min_quality = quality + 1
                else:
                    # Too large, reduce quality
                    max_quality = quality - 1
            
            return best_result
            
        finally:
            # Return buffer to pool
            if self.memory_pool:
                self.memory_pool.return_buffer(buffer)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics"""
        with self.stats_lock:
            stats = self.stats.copy()
            stats['cache_stats'] = self.cache.get_stats()
            stats['avg_compression_time'] = (
                stats['total_time'] / stats['compressions']
                if stats['compressions'] > 0 else 0
            )
            stats['cache_hit_rate'] = (
                stats['cache_hits'] / (stats['cache_hits'] + stats['cache_misses'])
                if (stats['cache_hits'] + stats['cache_misses']) > 0 else 0
            )
            stats['total_mb_saved'] = stats['total_bytes_saved'] / (1024 * 1024)
            return stats
    
    async def close(self):
        """Clean up resources"""
        self.executor.shutdown(wait=True)
        self.cache.clear()
        logger.info("AsyncImageCompressor closed")


class BatchImageProcessor:
    """Batch processing for multiple images with optimizations"""
    
    def __init__(self, compressor: AsyncImageCompressor = None):
        self.compressor = compressor or AsyncImageCompressor()
    
    async def process_batch(
        self,
        image_paths: List[str],
        max_size_kb: int = 200,
        max_dimension: int = 1024,
        batch_size: int = 10
    ) -> List[Optional[str]]:
        """Process multiple images in optimized batches"""
        results = []
        
        # Process in batches to avoid overwhelming the system
        for i in range(0, len(image_paths), batch_size):
            batch = image_paths[i:i + batch_size]
            
            # Create compression tasks
            tasks = [
                self.compressor.compress_image_async(
                    path, max_size_kb, max_dimension
                )
                for path in batch
            ]
            
            # Process batch concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle results
            for path, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Batch processing error for {path}: {result}")
                    results.append(None)
                else:
                    results.append(result)
            
            # Small delay between batches to prevent resource exhaustion
            if i + batch_size < len(image_paths):
                await asyncio.sleep(0.1)
        
        return results
    
    async def process_directory(
        self,
        directory: str,
        patterns: List[str] = None,
        recursive: bool = True,
        **compression_kwargs
    ) -> Dict[str, Optional[str]]:
        """Process all images in a directory"""
        directory = Path(directory)
        patterns = patterns or ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff']
        
        # Find all image files
        image_files = []
        for pattern in patterns:
            if recursive:
                image_files.extend(directory.rglob(pattern))
            else:
                image_files.extend(directory.glob(pattern))
        
        # Convert to strings
        image_paths = [str(f) for f in image_files]
        logger.info(f"Found {len(image_paths)} images to process")
        
        # Process all images
        results = await self.process_batch(image_paths, **compression_kwargs)
        
        # Create result dictionary
        return {path: result for path, result in zip(image_paths, results)}


# Optimized synchronous wrapper for compatibility
class OptimizedImageCompressor:
    """Synchronous wrapper for the async compressor"""
    
    def __init__(self, **kwargs):
        self.async_compressor = AsyncImageCompressor(**kwargs)
        self._loop = None
    
    def compress_image(self, image_path: str, **kwargs) -> Optional[str]:
        """Synchronous compression method"""
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run async compression
        return loop.run_until_complete(
            self.async_compressor.compress_image_async(image_path, **kwargs)
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics"""
        return self.async_compressor.get_stats()


# Decorator for automatic image compression
def auto_compress_images(max_size_kb: int = 200, max_dimension: int = 1024):
    """Decorator to automatically compress images in function arguments"""
    compressor = OptimizedImageCompressor()
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Find and compress image paths in arguments
            compressed_args = []
            for arg in args:
                if isinstance(arg, str) and os.path.isfile(arg):
                    # Check if it's an image file
                    if any(arg.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']):
                        compressed = compressor.compress_image(
                            arg, max_size_kb=max_size_kb, max_dimension=max_dimension
                        )
                        compressed_args.append(compressed if compressed else arg)
                    else:
                        compressed_args.append(arg)
                else:
                    compressed_args.append(arg)
            
            # Call original function with compressed images
            return func(*compressed_args, **kwargs)
        
        return wrapper
    return decorator


# Example usage and testing
async def example_usage():
    """Example of using the optimized compression"""
    # Create compressor with caching
    compressor = AsyncImageCompressor(max_workers=4, cache_size=100)
    
    # Single image compression
    image_path = "/path/to/image.jpg"
    if os.path.exists(image_path):
        result = await compressor.compress_image_async(image_path)
        print(f"Compressed size: {len(result)/1024:.1f}KB" if result else "Compression failed")
    
    # Batch processing
    batch_processor = BatchImageProcessor(compressor)
    image_paths = ["/path/to/image1.jpg", "/path/to/image2.png"]
    results = await batch_processor.process_batch(image_paths)
    
    # Get statistics
    stats = compressor.get_stats()
    print(f"Compression stats: {json.dumps(stats, indent=2)}")
    
    # Clean up
    await compressor.close()


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())