#!/usr/bin/env python3
"""
统一文档UI演示
展示优化后的API如何支持前端统一文档区域
"""

import requests
import json

API_BASE = "http://127.0.0.1:8001"

def demo_unified_ui():
    """演示统一文档UI的API使用"""
    print("📋 统一文档区域 API 演示")
    print("=" * 60)
    
    # 获取文档列表
    response = requests.get(f"{API_BASE}/api/v1/documents")
    if response.status_code != 200:
        print("❌ 无法获取文档列表")
        return
    
    data = response.json()
    documents = data["documents"]
    
    print(f"✅ 获取到 {len(documents)} 个文档")
    print(f"📊 状态统计: {data['status_counts']}")
    
    # 前端实现模拟
    print(f"\n🖥️  前端UI渲染效果:")
    print("=" * 90)
    print(f"{'文档名称':<25} {'大小':<8} {'状态':<35} {'操作':<15}")
    print("-" * 90)
    
    for doc in documents[:8]:  # 只显示前8个文档
        # 文件大小格式化
        size = doc['file_size']
        if size > 1024 * 1024:
            size_str = f"{size//1024//1024}MB"
        elif size > 1024:
            size_str = f"{size//1024}KB"
        else:
            size_str = f"{size}B"
        
        # 操作按钮图标映射
        icon_map = {
            "play": "▶️ 开始解析",
            "loading": "⏳ 解析中",
            "check": "✅ 已完成",
            "refresh": "🔄 重试",
            "question": "❓ 未知"
        }
        action_display = icon_map.get(doc['action_icon'], doc['action_text'])
        
        print(f"{doc['file_name']:<25} {size_str:<8} {doc['status_display']:<35} {action_display:<15}")
    
    # API字段说明
    print(f"\n📖 API字段说明:")
    print("=" * 50)
    print("🔑 核心显示字段:")
    print("   • file_name        : 文件名称")
    print("   • file_size        : 文件大小（字节）")
    print("   • status_display   : 状态显示文本（直接用于UI）")
    print("   • uploaded_at      : 上传时间")
    
    print("\n🎯 操作控制字段:")
    print("   • action_type      : 操作类型（start_processing/processing/completed/retry）")
    print("   • action_icon      : 图标类型（play/loading/check/refresh）")
    print("   • action_text      : 按钮文本")
    print("   • can_process      : 是否可以触发操作（布尔值）")
    
    print("\n💻 前端实现示例:")
    print("```javascript")
    print("// 渲染文档列表")
    print("documents.forEach(doc => {")
    print("  const row = createTableRow();")
    print("  row.cells[0].textContent = doc.file_name;")
    print("  row.cells[1].textContent = formatFileSize(doc.file_size);")
    print("  row.cells[2].textContent = doc.status_display;")
    print("  ")
    print("  // 动态操作按钮")
    print("  const actionBtn = createActionButton(doc.action_icon);")
    print("  actionBtn.disabled = !doc.can_process;")
    print("  actionBtn.onclick = () => handleAction(doc);")
    print("  row.cells[3].appendChild(actionBtn);")
    print("});")
    print("")
    print("// 处理操作点击")
    print("function handleAction(doc) {")
    print("  if (doc.action_type === 'start_processing') {")
    print("    // 手动触发解析")
    print("    fetch(`/api/v1/documents/${doc.document_id}/process`, {method: 'POST'})")
    print("      .then(() => refreshDocumentList());")
    print("  }")
    print("}")
    print("```")
    
    # 实时状态更新示例
    print(f"\n🔄 实时状态更新示例:")
    uploaded_docs = [d for d in documents if d['status_code'] == 'uploaded']
    if uploaded_docs:
        doc = uploaded_docs[0]
        print(f"📄 示例文档: {doc['file_name']}")
        print(f"   📊 当前状态: {doc['status_display']}")
        print(f"   🎯 操作类型: {doc['action_type']}")
        print(f"   🔲 可操作: {'是' if doc['can_process'] else '否'}")
        
        print(f"\n💡 触发处理的API调用:")
        print(f"curl -X POST \"{API_BASE}/api/v1/documents/{doc['document_id']}/process\"")
    
    print(f"\n🎉 统一文档UI演示完成!")

if __name__ == "__main__":
    demo_unified_ui()