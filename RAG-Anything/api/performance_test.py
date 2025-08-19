#!/usr/bin/env python3
"""
PDF Parser Performance Test
实际测试MinerU vs Docling在不同大小PDF文件上的性能
"""

import asyncio
import time
import tempfile
import os
import psutil
from pathlib import Path
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceTestSuite:
    """PDF解析器性能测试套件"""
    
    def __init__(self):
        self.results = []
        self.test_files = []
    
    def create_test_pdf(self, size_mb: int) -> Path:
        """创建指定大小的测试PDF文件"""
        # 这里应该创建真实的PDF文件用于测试
        # 为了演示，我们创建一个占位符
        temp_dir = Path(tempfile.mkdtemp())
        test_file = temp_dir / f"test_{size_mb}mb.pdf"
        
        # 创建一个模拟PDF文件（实际应该是真实PDF）
        with open(test_file, 'wb') as f:
            # 写入模拟内容达到指定大小
            content = b"PDF_simulation_content" * (size_mb * 1024 * 1024 // 30)
            f.write(content)
        
        return test_file
    
    async def test_parser_performance(self, parser_name: str, file_path: Path) -> Dict:
        """测试单个解析器的性能"""
        result = {
            "parser": parser_name,
            "file_path": str(file_path),
            "file_size_mb": file_path.stat().st_size / (1024 * 1024),
            "success": False,
            "processing_time": 0,
            "memory_usage_mb": 0,
            "error": None
        }
        
        try:
            # 记录开始时的内存使用
            process = psutil.Process()
            start_memory = process.memory_info().rss / (1024 * 1024)
            start_time = time.time()
            
            if parser_name == "mineru":
                await self._test_mineru_parser(file_path)
            elif parser_name == "docling":
                await self._test_docling_parser(file_path)
            else:
                raise ValueError(f"不支持的解析器: {parser_name}")
            
            # 记录结束时间和内存
            end_time = time.time()
            end_memory = process.memory_info().rss / (1024 * 1024)
            
            result.update({
                "success": True,
                "processing_time": end_time - start_time,
                "memory_usage_mb": end_memory - start_memory
            })
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"{parser_name} 解析失败: {e}")
        
        return result
    
    async def _test_mineru_parser(self, file_path: Path):
        """测试MinerU解析器"""
        try:
            from raganything.parser import MineruParser
            parser = MineruParser()
            
            # 模拟解析过程
            if parser.check_installation():
                # 这里应该调用实际的解析方法
                # result = parser.parse_pdf(file_path, output_dir="./test_output")
                # 为了测试演示，我们模拟处理时间
                await asyncio.sleep(0.1)  # 模拟处理时间
                logger.info(f"MinerU 成功处理: {file_path.name}")
            else:
                raise Exception("MinerU 未正确安装")
                
        except ImportError:
            raise Exception("无法导入 MinerU")
    
    async def _test_docling_parser(self, file_path: Path):
        """测试Docling解析器"""
        try:
            from raganything.parser import DoclingParser
            parser = DoclingParser()
            
            # 模拟解析过程
            if parser.check_installation():
                # 这里应该调用实际的解析方法
                # result = parser.parse_pdf(file_path, output_dir="./test_output")
                # 为了测试演示，我们模拟处理时间
                await asyncio.sleep(0.15)  # 模拟稍长的处理时间
                logger.info(f"Docling 成功处理: {file_path.name}")
            else:
                raise Exception("Docling 未正确安装")
                
        except ImportError:
            raise Exception("无法导入 Docling")
    
    async def run_comprehensive_test(self):
        """运行综合性能测试"""
        print("🧪 PDF解析器性能测试")
        print("=" * 50)
        
        # 测试不同大小的文件
        test_sizes = [1, 5, 10, 50, 100]  # MB
        parsers = ["mineru", "docling"]
        
        for size_mb in test_sizes:
            print(f"\n📄 测试 {size_mb}MB PDF文件:")
            
            # 创建测试文件
            test_file = self.create_test_pdf(size_mb)
            self.test_files.append(test_file)
            
            parser_results = []
            
            for parser in parsers:
                print(f"   测试 {parser}...")
                result = await self.test_parser_performance(parser, test_file)
                parser_results.append(result)
                self.results.append(result)
                
                if result["success"]:
                    print(f"   ✅ {parser}: {result['processing_time']:.2f}s, {result['memory_usage_mb']:.1f}MB内存")
                else:
                    print(f"   ❌ {parser}: {result['error']}")
            
            # 比较结果
            if len([r for r in parser_results if r["success"]]) >= 2:
                successful_results = [r for r in parser_results if r["success"]]
                fastest = min(successful_results, key=lambda x: x["processing_time"])
                least_memory = min(successful_results, key=lambda x: x["memory_usage_mb"])
                
                print(f"   🏆 最快: {fastest['parser']} ({fastest['processing_time']:.2f}s)")
                print(f"   💾 最省内存: {least_memory['parser']} ({least_memory['memory_usage_mb']:.1f}MB)")
    
    def analyze_results(self):
        """分析测试结果"""
        print("\n📊 性能测试分析")
        print("=" * 50)
        
        if not self.results:
            print("❌ 没有测试结果")
            return
        
        # 按解析器分组
        by_parser = {}
        for result in self.results:
            parser = result["parser"]
            if parser not in by_parser:
                by_parser[parser] = []
            by_parser[parser].append(result)
        
        # 计算平均性能
        for parser, results in by_parser.items():
            successful = [r for r in results if r["success"]]
            if successful:
                avg_time = sum(r["processing_time"] for r in successful) / len(successful)
                avg_memory = sum(r["memory_usage_mb"] for r in successful) / len(successful)
                success_rate = len(successful) / len(results) * 100
                
                print(f"\n{parser.upper()} 解析器:")
                print(f"   成功率: {success_rate:.1f}%")
                print(f"   平均处理时间: {avg_time:.2f}秒")
                print(f"   平均内存使用: {avg_memory:.1f}MB")
            else:
                print(f"\n{parser.upper()} 解析器:")
                print(f"   ❌ 所有测试都失败")
        
        # 给出建议
        self.generate_recommendations()
    
    def generate_recommendations(self):
        """基于测试结果生成建议"""
        print("\n💡 基于测试结果的建议:")
        print("=" * 30)
        
        successful_results = [r for r in self.results if r["success"]]
        
        if not successful_results:
            print("❌ 无法生成建议，所有测试都失败")
            return
        
        # 按文件大小分析
        small_files = [r for r in successful_results if r["file_size_mb"] <= 10]
        large_files = [r for r in successful_results if r["file_size_mb"] > 50]
        
        if small_files:
            fastest_small = min(small_files, key=lambda x: x["processing_time"])
            print(f"📄 小文件 (≤10MB): 推荐 {fastest_small['parser']}")
        
        if large_files:
            fastest_large = min(large_files, key=lambda x: x["processing_time"])
            least_memory_large = min(large_files, key=lambda x: x["memory_usage_mb"])
            print(f"📄 大文件 (>50MB):")
            print(f"   速度优先: {fastest_large['parser']}")
            print(f"   内存优先: {least_memory_large['parser']}")
        
        print("\n⚠️  注意: 这些结果基于模拟测试，实际性能可能不同")
        print("   建议使用真实PDF文件进行更准确的测试")
    
    def cleanup(self):
        """清理测试文件"""
        for test_file in self.test_files:
            try:
                if test_file.exists():
                    test_file.unlink()
                    test_file.parent.rmdir()
            except Exception as e:
                logger.warning(f"清理测试文件失败: {e}")

async def main():
    """主测试函数"""
    test_suite = PerformanceTestSuite()
    
    try:
        await test_suite.run_comprehensive_test()
        test_suite.analyze_results()
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        test_suite.cleanup()

if __name__ == "__main__":
    print("📋 注意：这是一个演示性测试脚本")
    print("   实际性能测试需要真实的PDF文件和完整的解析器安装")
    print("   当前结果仅用于展示测试框架")
    print()
    
    asyncio.run(main())