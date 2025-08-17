#!/usr/bin/env python3
"""
API兼容性测试脚本
验证RAG-Anything API与LightRAG WebUI的兼容性
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, List
import aiohttp
import sys
import traceback

class APICompatibilityTester:
    """API兼容性测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.session = None
        self.test_results = []
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有兼容性测试"""
        print("🚀 开始API兼容性测试...")
        print(f"目标服务器: {self.base_url}")
        print("-" * 50)
        
        # 测试用例列表
        test_cases = [
            ("健康检查", self.test_health_check),
            ("文档状态获取", self.test_get_documents),
            ("查询接口", self.test_query_interface),
            ("知识图谱接口", self.test_graph_interface),
            ("错误处理", self.test_error_handling),
            ("响应格式", self.test_response_format),
        ]
        
        results = {
            "total_tests": len(test_cases),
            "passed": 0,
            "failed": 0,
            "test_details": []
        }
        
        for test_name, test_func in test_cases:
            print(f"🧪 测试: {test_name}")
            
            try:
                start_time = time.time()
                result = await test_func()
                duration = time.time() - start_time
                
                if result["passed"]:
                    print(f"✅ {test_name} - 通过 ({duration:.2f}s)")
                    results["passed"] += 1
                else:
                    print(f"❌ {test_name} - 失败: {result['error']}")
                    results["failed"] += 1
                
                result["duration"] = duration
                results["test_details"].append({
                    "name": test_name,
                    "result": result
                })
                
            except Exception as e:
                print(f"💥 {test_name} - 异常: {str(e)}")
                results["failed"] += 1
                results["test_details"].append({
                    "name": test_name,
                    "result": {
                        "passed": False,
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    }
                })
        
        print("-" * 50)
        print(f"📊 测试完成: {results['passed']}/{results['total_tests']} 通过")
        
        return results
    
    async def test_health_check(self) -> Dict[str, Any]:
        """测试健康检查接口"""
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status != 200:
                    return {"passed": False, "error": f"状态码错误: {response.status}"}
                
                data = await response.json()
                
                # 验证必需字段
                required_fields = [
                    "status", "working_directory", "configuration", "pipeline_busy"
                ]
                
                for field in required_fields:
                    if field not in data:
                        return {"passed": False, "error": f"缺少必需字段: {field}"}
                
                # 验证配置字段
                config = data.get("configuration", {})
                config_fields = [
                    "llm_binding", "llm_model", "embedding_binding", "embedding_model"
                ]
                
                for field in config_fields:
                    if field not in config:
                        return {"passed": False, "error": f"配置缺少字段: {field}"}
                
                return {
                    "passed": True,
                    "data": data,
                    "status": data.get("status"),
                    "working_directory": data.get("working_directory")
                }
                
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    async def test_get_documents(self) -> Dict[str, Any]:
        """测试文档状态获取接口"""
        try:
            async with self.session.get(f"{self.base_url}/documents") as response:
                if response.status != 200:
                    return {"passed": False, "error": f"状态码错误: {response.status}"}
                
                data = await response.json()
                
                # 验证响应格式
                if "statuses" not in data:
                    return {"passed": False, "error": "缺少statuses字段"}
                
                statuses = data["statuses"]
                required_status_keys = ["processed", "pending", "processing", "failed"]
                
                for key in required_status_keys:
                    if key not in statuses:
                        return {"passed": False, "error": f"缺少状态类型: {key}"}
                    
                    if not isinstance(statuses[key], list):
                        return {"passed": False, "error": f"状态{key}不是列表格式"}
                
                # 验证文档对象格式（如果有文档的话）
                for status_type, docs in statuses.items():
                    for doc in docs[:1]:  # 只检查第一个文档
                        required_doc_fields = [
                            "id", "content_summary", "status", "created_at", "file_path"
                        ]
                        
                        for field in required_doc_fields:
                            if field not in doc:
                                return {"passed": False, "error": f"文档缺少字段: {field}"}
                
                total_docs = sum(len(docs) for docs in statuses.values())
                
                return {
                    "passed": True,
                    "data": data,
                    "total_documents": total_docs,
                    "status_distribution": {k: len(v) for k, v in statuses.items()}
                }
                
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    async def test_query_interface(self) -> Dict[str, Any]:
        """测试查询接口"""
        try:
            # 测试基本查询
            query_data = {
                "query": "这是一个测试查询",
                "mode": "hybrid"
            }
            
            async with self.session.post(
                f"{self.base_url}/query",
                json=query_data
            ) as response:
                if response.status != 200:
                    return {"passed": False, "error": f"状态码错误: {response.status}"}
                
                data = await response.json()
                
                # 验证响应格式
                if "response" not in data:
                    return {"passed": False, "error": "缺少response字段"}
                
                if not isinstance(data["response"], str):
                    return {"passed": False, "error": "response字段不是字符串"}
                
                # 测试不同查询模式
                modes = ["naive", "local", "global", "hybrid"]
                mode_results = {}
                
                for mode in modes:
                    test_query = {
                        "query": f"测试{mode}模式",
                        "mode": mode
                    }
                    
                    async with self.session.post(
                        f"{self.base_url}/query",
                        json=test_query
                    ) as mode_response:
                        mode_results[mode] = {
                            "status": mode_response.status,
                            "success": mode_response.status == 200
                        }
                
                return {
                    "passed": True,
                    "data": data,
                    "response_length": len(data["response"]),
                    "mode_test_results": mode_results
                }
                
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    async def test_graph_interface(self) -> Dict[str, Any]:
        """测试知识图谱接口"""
        try:
            # 测试图谱获取接口
            async with self.session.get(
                f"{self.base_url}/graphs?label=test&max_depth=3&max_nodes=10"
            ) as response:
                if response.status != 200:
                    return {"passed": False, "error": f"图谱接口状态码错误: {response.status}"}
                
                data = await response.json()
                
                # 验证图谱数据格式
                if "nodes" not in data or "edges" not in data:
                    return {"passed": False, "error": "图谱数据缺少nodes或edges字段"}
                
                if not isinstance(data["nodes"], list) or not isinstance(data["edges"], list):
                    return {"passed": False, "error": "nodes或edges不是列表格式"}
                
                # 验证节点格式
                for node in data["nodes"][:1]:
                    required_node_fields = ["id", "labels", "properties"]
                    for field in required_node_fields:
                        if field not in node:
                            return {"passed": False, "error": f"节点缺少字段: {field}"}
                
                # 验证边格式
                for edge in data["edges"][:1]:
                    required_edge_fields = ["id", "source", "target", "type", "properties"]
                    for field in required_edge_fields:
                        if field not in edge:
                            return {"passed": False, "error": f"边缺少字段: {field}"}
            
            # 测试标签列表接口
            async with self.session.get(f"{self.base_url}/graph/label/list") as response:
                if response.status != 200:
                    return {"passed": False, "error": f"标签接口状态码错误: {response.status}"}
                
                labels = await response.json()
                
                if not isinstance(labels, list):
                    return {"passed": False, "error": "标签列表不是数组格式"}
                
                return {
                    "passed": True,
                    "node_count": len(data["nodes"]),
                    "edge_count": len(data["edges"]),
                    "label_count": len(labels),
                    "available_labels": labels
                }
                
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    async def test_error_handling(self) -> Dict[str, Any]:
        """测试错误处理"""
        try:
            error_tests = []
            
            # 测试空查询
            async with self.session.post(
                f"{self.base_url}/query",
                json={"query": "", "mode": "hybrid"}
            ) as response:
                error_tests.append({
                    "test": "空查询",
                    "status": response.status,
                    "expected": 400,
                    "passed": response.status == 400
                })
            
            # 测试无效模式
            async with self.session.post(
                f"{self.base_url}/query",
                json={"query": "test", "mode": "invalid_mode"}
            ) as response:
                error_tests.append({
                    "test": "无效模式",
                    "status": response.status,
                    "expected": 400,
                    "passed": response.status == 400
                })
            
            # 测试不存在的接口
            async with self.session.get(f"{self.base_url}/nonexistent") as response:
                error_tests.append({
                    "test": "不存在接口",
                    "status": response.status,
                    "expected": 404,
                    "passed": response.status == 404
                })
            
            all_passed = all(test["passed"] for test in error_tests)
            
            return {
                "passed": all_passed,
                "error_tests": error_tests,
                "total_error_tests": len(error_tests),
                "passed_error_tests": sum(1 for test in error_tests if test["passed"])
            }
            
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    async def test_response_format(self) -> Dict[str, Any]:
        """测试响应格式一致性"""
        try:
            format_tests = []
            
            # 检查健康检查响应
            async with self.session.get(f"{self.base_url}/health") as response:
                data = await response.json()
                format_tests.append({
                    "endpoint": "/health",
                    "has_correct_content_type": response.headers.get("content-type", "").startswith("application/json"),
                    "response_structure_valid": isinstance(data, dict) and "status" in data
                })
            
            # 检查文档列表响应
            async with self.session.get(f"{self.base_url}/documents") as response:
                data = await response.json()
                format_tests.append({
                    "endpoint": "/documents",
                    "has_correct_content_type": response.headers.get("content-type", "").startswith("application/json"),
                    "response_structure_valid": isinstance(data, dict) and "statuses" in data
                })
            
            # 检查查询响应
            async with self.session.post(
                f"{self.base_url}/query",
                json={"query": "test", "mode": "hybrid"}
            ) as response:
                data = await response.json()
                format_tests.append({
                    "endpoint": "/query",
                    "has_correct_content_type": response.headers.get("content-type", "").startswith("application/json"),
                    "response_structure_valid": isinstance(data, dict) and "response" in data
                })
            
            all_valid = all(
                test["has_correct_content_type"] and test["response_structure_valid"]
                for test in format_tests
            )
            
            return {
                "passed": all_valid,
                "format_tests": format_tests,
                "total_endpoints_tested": len(format_tests)
            }
            
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    def save_results(self, results: Dict[str, Any], filename: str = None):
        """保存测试结果"""
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"api_compatibility_test_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"📄 测试结果已保存到: {filename}")

async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG-Anything API兼容性测试")
    parser.add_argument("--base-url", default="http://localhost:8001", help="API服务器地址")
    parser.add_argument("--output", help="结果输出文件名")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    async with APICompatibilityTester(args.base_url) as tester:
        results = await tester.run_all_tests()
        
        if args.output:
            tester.save_results(results, args.output)
        
        if args.verbose:
            print("\n📋 详细测试结果:")
            print(json.dumps(results, ensure_ascii=False, indent=2))
        
        # 返回合适的退出码
        success_rate = results["passed"] / results["total_tests"]
        if success_rate >= 0.8:  # 80%通过率认为是成功
            print(f"\n🎉 测试基本通过 (通过率: {success_rate:.1%})")
            sys.exit(0)
        else:
            print(f"\n⚠️ 测试未完全通过 (通过率: {success_rate:.1%})")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())