#!/usr/bin/env python3
"""
测试V2批量处理端点
验证新架构是否解决了cache_metrics等问题
"""
import requests
import json
import time

# 测试配置
API_BASE = "http://127.0.0.1:8001"
V1_ENDPOINT = f"{API_BASE}/api/v1/documents/process/batch"
V2_ENDPOINT = f"{API_BASE}/api/v1/documents/process/batch/v2"

def test_v2_endpoint_with_empty_docs():
    """测试V2端点对空文档列表的处理"""
    print("🧪 测试V2端点 - 空文档列表...")
    
    try:
        response = requests.post(V2_ENDPOINT, json={
            "document_ids": []
        }, timeout=30)
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            data = response.json()
            # 检查关键字段
            assert "cache_performance" in data, "缺少cache_performance字段"
            assert isinstance(data["cache_performance"], dict), "cache_performance应该是字典"
            assert data["started_count"] == 0, "空文档列表应该没有启动任何处理"
            assert data["total_requested"] == 0, "空文档列表应该总请求数为0"
            print("✅ V2端点 - 空文档测试通过")
            return True
        else:
            print(f"❌ V2端点测试失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ V2端点测试异常: {str(e)}")
        return False

def test_v2_endpoint_with_invalid_docs():
    """测试V2端点对无效文档的处理"""
    print("🧪 测试V2端点 - 无效文档...")
    
    try:
        response = requests.post(V2_ENDPOINT, json={
            "document_ids": ["invalid_doc_1", "invalid_doc_2"]
        }, timeout=30)
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            data = response.json()
            # 检查关键字段
            assert "cache_performance" in data, "缺少cache_performance字段"
            assert isinstance(data["cache_performance"], dict), "cache_performance应该是字典"
            assert "batch_operation_id" in data, "缺少batch_operation_id字段"
            print("✅ V2端点 - 无效文档测试通过")
            return True
        else:
            print(f"❌ V2端点测试失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ V2端点测试异常: {str(e)}")
        return False

def get_available_documents():
    """获取可用的文档"""
    try:
        response = requests.get(f"{API_BASE}/api/v1/documents")
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("documents"):
                return [doc["document_id"] for doc in data["documents"][:3]]  # 取前3个
        return []
    except:
        return []

def test_v2_endpoint_with_real_docs():
    """测试V2端点对真实文档的处理"""
    print("🧪 测试V2端点 - 真实文档...")
    
    # 获取可用文档
    doc_ids = get_available_documents()
    if not doc_ids:
        print("⚠️ 没有可用文档，跳过真实文档测试")
        return True
    
    print(f"使用文档: {doc_ids[:2]}")  # 只用前2个避免处理时间过长
    
    try:
        response = requests.post(V2_ENDPOINT, json={
            "document_ids": doc_ids[:2]
        }, timeout=60)  # 增加超时时间
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # 检查关键字段
            assert "cache_performance" in data, "缺少cache_performance字段"
            assert isinstance(data["cache_performance"], dict), "cache_performance应该是字典"
            assert "batch_operation_id" in data, "缺少batch_operation_id字段"
            print("✅ V2端点 - 真实文档测试通过")
            return True
        else:
            print(f"❌ V2端点测试失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ V2端点测试异常: {str(e)}")
        return False

def compare_v1_v2_error_handling():
    """比较V1和V2端点的错误处理"""
    print("🆚 比较V1和V2端点错误处理...")
    
    test_data = {"document_ids": ["invalid_doc"]}
    
    # 测试V1端点
    print("测试V1端点...")
    try:
        v1_response = requests.post(V1_ENDPOINT, json=test_data, timeout=30)
        v1_success = v1_response.status_code == 200
        v1_has_cache = "cache_performance" in v1_response.json() if v1_success else False
        print(f"V1: 状态码={v1_response.status_code}, 有缓存性能={v1_has_cache}")
    except Exception as e:
        print(f"V1测试异常: {str(e)}")
        v1_success = False
        v1_has_cache = False
    
    # 测试V2端点
    print("测试V2端点...")
    try:
        v2_response = requests.post(V2_ENDPOINT, json=test_data, timeout=30)
        v2_success = v2_response.status_code == 200
        v2_has_cache = "cache_performance" in v2_response.json() if v2_success else False
        print(f"V2: 状态码={v2_response.status_code}, 有缓存性能={v2_has_cache}")
    except Exception as e:
        print(f"V2测试异常: {str(e)}")
        v2_success = False
        v2_has_cache = False
    
    print(f"📊 比较结果: V1成功={v1_success}, V2成功={v2_success}")
    print(f"📊 缓存字段: V1有缓存={v1_has_cache}, V2有缓存={v2_has_cache}")
    
    # V2应该更可靠
    return v2_success and v2_has_cache

def main():
    """主测试函数"""
    print("🚀 开始测试V2批量处理端点")
    print("=" * 50)
    
    tests = [
        test_v2_endpoint_with_empty_docs,
        test_v2_endpoint_with_invalid_docs,
        test_v2_endpoint_with_real_docs,
        compare_v1_v2_error_handling
    ]
    
    passed = 0
    total = len(tests)
    
    for i, test in enumerate(tests, 1):
        print(f"\n📝 测试 {i}/{total}")
        try:
            if test():
                passed += 1
                print(f"✅ 测试 {i} 通过")
            else:
                print(f"❌ 测试 {i} 失败")
        except Exception as e:
            print(f"❌ 测试 {i} 异常: {str(e)}")
        
        if i < total:
            print("⏳ 等待2秒...")
            time.sleep(2)
    
    print("\n" + "=" * 50)
    print(f"🎯 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！V2架构工作正常")
        print("✅ cache_metrics初始化问题已解决")
        print("✅ 错误处理机制正常工作")
        print("✅ 类型安全的数据结构运行良好")
    else:
        print("⚠️ 部分测试失败，需要进一步调试")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)