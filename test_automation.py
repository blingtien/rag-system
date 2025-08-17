#!/usr/bin/env python3
"""
RAG-Anything Web UI 自动化测试脚本
"""

import requests
import json
import time
import sys
from typing import Dict, Any
import tempfile
import os

class RAGWebUITester:
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, message: str = "", data: Any = None):
        """记录测试结果"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "data": data
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if data and not success:
            print(f"   Data: {data}")
    
    def test_health_check(self):
        """测试健康检查接口"""
        try:
            response = requests.get(f"{self.api_base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log_test("健康检查", True, f"API服务器运行正常，状态: {data.get('status')}", data)
                return True
            else:
                self.log_test("健康检查", False, f"HTTP状态码: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("健康检查", False, f"连接失败: {str(e)}")
            return False
    
    def test_system_status(self):
        """测试系统状态接口"""
        try:
            response = requests.get(f"{self.api_base_url}/api/system/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                services_count = len(data.get('services', {}))
                metrics_count = len(data.get('metrics', {}))
                self.log_test("系统状态", True, 
                            f"获取到 {services_count} 个服务状态，{metrics_count} 个性能指标", 
                            data)
                return True
            else:
                self.log_test("系统状态", False, f"HTTP状态码: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("系统状态", False, f"请求失败: {str(e)}")
            return False
    
    def test_query_api(self):
        """测试查询接口"""
        test_queries = [
            {"query": "什么是RAG系统？", "mode": "hybrid"},
            {"query": "机器学习的应用场景", "mode": "local"},
            {"query": "人工智能的发展历史", "mode": "global"},
        ]
        
        for i, query_data in enumerate(test_queries):
            try:
                response = requests.post(
                    f"{self.api_base_url}/api/query",
                    json=query_data,
                    headers={"Content-Type": "application/json"},
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result_length = len(data.get('result', ''))
                    processing_time = data.get('processing_time', 0)
                    self.log_test(f"查询测试 {i+1}", True, 
                                f"查询成功，返回 {result_length} 字符，耗时 {processing_time:.3f}s",
                                {"query": query_data["query"], "mode": query_data["mode"]})
                else:
                    self.log_test(f"查询测试 {i+1}", False, f"HTTP状态码: {response.status_code}")
            except Exception as e:
                self.log_test(f"查询测试 {i+1}", False, f"请求失败: {str(e)}")
    
    def test_multimodal_query(self):
        """测试多模态查询"""
        multimodal_data = {
            "query": "分析这个表格数据",
            "mode": "hybrid",
            "multimodal_content": [
                {
                    "type": "table",
                    "table_data": "姓名,年龄,职业\n张三,25,工程师\n李四,30,设计师",
                    "table_caption": "员工信息表"
                }
            ]
        }
        
        try:
            response = requests.post(
                f"{self.api_base_url}/api/query",
                json=multimodal_data,
                headers={"Content-Type": "application/json"},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('result', '')
                has_multimodal_info = "多模态内容" in result
                self.log_test("多模态查询", True, 
                            f"查询成功，{'包含' if has_multimodal_info else '不包含'}多模态信息",
                            {"result_preview": result[:100] + "..."})
            else:
                self.log_test("多模态查询", False, f"HTTP状态码: {response.status_code}")
        except Exception as e:
            self.log_test("多模态查询", False, f"请求失败: {str(e)}")
    
    def test_file_upload_simulation(self):
        """测试文件上传接口（模拟）"""
        # 创建一个临时文本文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("这是一个测试文档，用于验证文件上传功能。\n包含一些示例文本内容。")
            temp_file_path = f.name
        
        try:
            with open(temp_file_path, 'rb') as f:
                files = {'file': ('test_document.txt', f, 'text/plain')}
                data = {'parser': 'mineru', 'parse_method': 'auto'}
                
                response = requests.post(
                    f"{self.api_base_url}/api/documents/upload",
                    files=files,
                    data=data,
                    timeout=10
                )
            
            if response.status_code == 200:
                result = response.json()
                file_id = result.get('file_id')
                status = result.get('status')
                self.log_test("文件上传", True, 
                            f"文件上传成功，ID: {file_id}，状态: {status}",
                            result)
            else:
                self.log_test("文件上传", False, f"HTTP状态码: {response.status_code}")
                
        except Exception as e:
            self.log_test("文件上传", False, f"请求失败: {str(e)}")
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file_path)
            except:
                pass
    
    def test_documents_list(self):
        """测试文档列表接口"""
        try:
            response = requests.get(f"{self.api_base_url}/api/documents", timeout=10)
            if response.status_code == 200:
                data = response.json()
                documents_count = len(data.get('documents', []))
                total = data.get('total', 0)
                self.log_test("文档列表", True, 
                            f"获取到 {documents_count} 个文档，总计 {total} 个",
                            {"sample_docs": data.get('documents', [])[:2]})
            else:
                self.log_test("文档列表", False, f"HTTP状态码: {response.status_code}")
        except Exception as e:
            self.log_test("文档列表", False, f"请求失败: {str(e)}")
    
    def test_query_history(self):
        """测试查询历史接口"""
        try:
            response = requests.get(f"{self.api_base_url}/api/query/history?limit=5", timeout=10)
            if response.status_code == 200:
                data = response.json()
                history_count = len(data.get('history', []))
                total = data.get('total', 0)
                self.log_test("查询历史", True, 
                            f"获取到 {history_count} 条历史记录，总计 {total} 条",
                            {"sample_history": data.get('history', [])[:1]})
            else:
                self.log_test("查询历史", False, f"HTTP状态码: {response.status_code}")
        except Exception as e:
            self.log_test("查询历史", False, f"请求失败: {str(e)}")
    
    def test_configuration(self):
        """测试配置接口"""
        try:
            # 获取配置
            response = requests.get(f"{self.api_base_url}/api/config", timeout=10)
            if response.status_code == 200:
                data = response.json()
                config_sections = len(data)
                self.log_test("获取配置", True, f"获取到 {config_sections} 个配置项", 
                            {"config_keys": list(data.keys())})
                
                # 测试更新配置
                test_config = {
                    "section": "parser",
                    "settings": {
                        "max_concurrent_files": 8
                    }
                }
                
                response = requests.post(
                    f"{self.api_base_url}/api/config",
                    json=test_config,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                if response.status_code == 200:
                    self.log_test("更新配置", True, "配置更新成功")
                else:
                    self.log_test("更新配置", False, f"HTTP状态码: {response.status_code}")
            else:
                self.log_test("获取配置", False, f"HTTP状态码: {response.status_code}")
        except Exception as e:
            self.log_test("配置管理", False, f"请求失败: {str(e)}")
    
    def run_load_test(self, concurrent_requests: int = 5):
        """运行负载测试"""
        import threading
        import time
        
        print(f"\n🔄 开始负载测试，并发请求数: {concurrent_requests}")
        
        results = []
        start_time = time.time()
        
        def make_request(thread_id):
            try:
                response = requests.post(
                    f"{self.api_base_url}/api/query",
                    json={"query": f"负载测试查询 {thread_id}", "mode": "hybrid"},
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                end_time = time.time()
                results.append({
                    "thread_id": thread_id,
                    "success": response.status_code == 200,
                    "response_time": end_time - start_time,
                    "status_code": response.status_code
                })
            except Exception as e:
                results.append({
                    "thread_id": thread_id,
                    "success": False,
                    "error": str(e)
                })
        
        # 启动并发请求
        threads = []
        for i in range(concurrent_requests):
            thread = threading.Thread(target=make_request, args=(i,))
            thread.start()
            threads.append(thread)
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        success_count = sum(1 for r in results if r.get('success', False))
        avg_response_time = sum(r.get('response_time', 0) for r in results) / len(results)
        
        self.log_test("负载测试", success_count > 0, 
                    f"{success_count}/{concurrent_requests} 请求成功，平均响应时间: {avg_response_time:.2f}s，总耗时: {total_time:.2f}s",
                    {"details": results})
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始RAG-Anything Web UI自动化测试")
        print("=" * 60)
        
        # 基础连接测试
        if not self.test_health_check():
            print("❌ 基础连接失败，终止测试")
            return
        
        # 系统功能测试
        self.test_system_status()
        self.test_query_api()
        self.test_multimodal_query()
        self.test_file_upload_simulation()
        self.test_documents_list()
        self.test_query_history()
        self.test_configuration()
        
        # 负载测试
        self.run_load_test(3)
        
        # 生成测试报告
        self.generate_report()
    
    def generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 60)
        print("📊 测试报告")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for t in self.test_results if t['success'])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests}")
        print(f"失败: {failed_tests}")
        print(f"成功率: {success_rate:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ 失败的测试:")
            for test in self.test_results:
                if not test['success']:
                    print(f"  - {test['test']}: {test['message']}")
        else:
            print("\n🎉 所有测试都通过了！")
        
        # 保存详细报告
        report_file = f"test_report_{int(time.time())}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)
        print(f"\n📄 详细报告已保存到: {report_file}")

if __name__ == "__main__":
    tester = RAGWebUITester()
    tester.run_all_tests()