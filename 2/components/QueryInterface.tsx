"use client";

import React, { useState } from "react";
import { Send, Image, Table, Calculator, Settings, History, Copy, Download } from "lucide-react";
import { cn } from "@/lib/utils";

interface QueryResult {
  id: string;
  query: string;
  result: string;
  timestamp: Date;
  mode: string;
  multimodal?: boolean;
}

const QueryInterface = () => {
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [queryMode, setQueryMode] = useState("hybrid");
  const [results, setResults] = useState<QueryResult[]>([
    {
      id: "1",
      query: "机器学习的主要应用领域有哪些？",
      result: "根据文档分析，机器学习的主要应用领域包括：\n\n1. **自然语言处理**：文本分类、情感分析、机器翻译等\n2. **计算机视觉**：图像识别、物体检测、医学影像分析\n3. **推荐系统**：个性化推荐、内容过滤\n4. **金融科技**：风险评估、算法交易、反欺诈\n5. **医疗健康**：疾病诊断、药物发现、基因分析\n\n这些应用领域展现了机器学习技术的广泛适用性和实用价值。",
      timestamp: new Date(Date.now() - 3600000),
      mode: "hybrid"
    }
  ]);
  const [multimodalContent, setMultimodalContent] = useState<any[]>([]);

  const queryModes = [
    { value: "local", label: "本地查询", description: "基于局部相似性检索" },
    { value: "global", label: "全局查询", description: "基于全局知识图谱" },
    { value: "hybrid", label: "混合查询", description: "结合多种检索策略" },
    { value: "naive", label: "简单查询", description: "基础相似性匹配" },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;

    setIsLoading(true);
    
    // 模拟API调用
    setTimeout(() => {
      const newResult: QueryResult = {
        id: Date.now().toString(),
        query: query,
        result: generateMockResponse(query),
        timestamp: new Date(),
        mode: queryMode,
        multimodal: multimodalContent.length > 0
      };
      
      setResults(prev => [newResult, ...prev]);
      setQuery("");
      setIsLoading(false);
    }, 2000 + Math.random() * 1000);
  };

  const generateMockResponse = (query: string) => {
    const responses = [
      "基于文档分析，这个问题涉及多个方面...",
      "根据已处理的文档内容，可以得出以下结论...",
      "通过检索相关知识片段，发现以下关键信息...",
      "结合多模态内容分析，相关信息如下..."
    ];
    return responses[Math.floor(Math.random() * responses.length)] + "\n\n这是一个模拟的查询结果，实际使用中将连接到RAG-Anything后端系统。";
  };

  const addMultimodalContent = (type: string) => {
    const newContent = {
      id: Date.now().toString(),
      type: type,
      placeholder: `添加${type === 'image' ? '图片' : type === 'table' ? '表格' : '公式'}内容`
    };
    setMultimodalContent(prev => [...prev, newContent]);
  };

  const removeMultimodalContent = (id: string) => {
    setMultimodalContent(prev => prev.filter(item => item.id !== id));
  };

  return (
    <div className="h-full flex flex-col space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">智能查询</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-2">基于多模态RAG系统的智能问答</p>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Query Input Section */}
        <div className="lg:col-span-2 space-y-4">
          {/* Query Mode Selection */}
          <div className="bg-white dark:bg-neutral-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
            <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3">查询模式</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {queryModes.map((mode) => (
                <button
                  key={mode.value}
                  onClick={() => setQueryMode(mode.value)}
                  className={cn(
                    "p-2 text-sm rounded-lg border transition-all",
                    queryMode === mode.value
                      ? "bg-blue-50 border-blue-300 text-blue-700 dark:bg-blue-900/20 dark:border-blue-600 dark:text-blue-300"
                      : "bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-300"
                  )}
                  title={mode.description}
                >
                  {mode.label}
                </button>
              ))}
            </div>
          </div>

          {/* Multimodal Content */}
          {multimodalContent.length > 0 && (
            <div className="bg-white dark:bg-neutral-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-3">多模态内容</h3>
              <div className="space-y-2">
                {multimodalContent.map((content) => (
                  <div key={content.id} className="flex items-center space-x-3 p-2 bg-gray-50 dark:bg-gray-700 rounded">
                    <span className="text-sm text-gray-600 dark:text-gray-300">{content.placeholder}</span>
                    <button
                      onClick={() => removeMultimodalContent(content.id)}
                      className="text-red-500 hover:text-red-700 text-sm"
                    >
                      删除
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Query Input */}
          <form onSubmit={handleSubmit} className="bg-white dark:bg-neutral-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-900 dark:text-white mb-2">
                  输入您的问题
                </label>
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                  rows={4}
                  placeholder="例如：请分析这个表格中的数据趋势..."
                  disabled={isLoading}
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={() => addMultimodalContent('image')}
                    className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                    title="添加图片"
                  >
                    <Image className="h-5 w-5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => addMultimodalContent('table')}
                    className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                    title="添加表格"
                  >
                    <Table className="h-5 w-5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => addMultimodalContent('equation')}
                    className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                    title="添加公式"
                  >
                    <Calculator className="h-5 w-5" />
                  </button>
                </div>

                <button
                  type="submit"
                  disabled={!query.trim() || isLoading}
                  className={cn(
                    "flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-all",
                    query.trim() && !isLoading
                      ? "bg-blue-600 text-white hover:bg-blue-700"
                      : "bg-gray-300 text-gray-500 cursor-not-allowed"
                  )}
                >
                  {isLoading ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                  <span>{isLoading ? "查询中..." : "发送查询"}</span>
                </button>
              </div>
            </div>
          </form>

          {/* Query Results */}
          <div className="space-y-4">
            {results.map((result) => (
              <div key={result.id} className="bg-white dark:bg-neutral-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h4 className="font-medium text-gray-900 dark:text-white mb-1">
                      {result.query}
                    </h4>
                    <div className="flex items-center space-x-4 text-xs text-gray-500 dark:text-gray-400">
                      <span>{result.timestamp.toLocaleString()}</span>
                      <span className={cn(
                        "px-2 py-1 rounded-full",
                        "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
                      )}>
                        {result.mode}
                      </span>
                      {result.multimodal && (
                        <span className="px-2 py-1 rounded-full bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300">
                          多模态
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <button className="p-1 text-gray-400 hover:text-gray-600 transition-colors" title="复制结果">
                      <Copy className="h-4 w-4" />
                    </button>
                    <button className="p-1 text-gray-400 hover:text-gray-600 transition-colors" title="导出结果">
                      <Download className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                
                <div className="prose dark:prose-invert max-w-none">
                  <div className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                    {result.result}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Query Statistics */}
          <div className="bg-white dark:bg-neutral-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">查询统计</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600 dark:text-gray-300">今日查询</span>
                <span className="font-semibold text-gray-900 dark:text-white">12</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600 dark:text-gray-300">总查询数</span>
                <span className="font-semibold text-gray-900 dark:text-white">156</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600 dark:text-gray-300">平均响应时间</span>
                <span className="font-semibold text-gray-900 dark:text-white">2.3s</span>
              </div>
            </div>
          </div>

          {/* Quick Query Templates */}
          <div className="bg-white dark:bg-neutral-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">快速查询模板</h3>
            <div className="space-y-2">
              {[
                "总结文档的主要内容",
                "分析数据中的关键趋势",
                "比较不同方案的优缺点",
                "提取文档中的关键信息"
              ].map((template, idx) => (
                <button
                  key={idx}
                  onClick={() => setQuery(template)}
                  className="w-full text-left p-2 text-sm bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 rounded transition-colors"
                >
                  {template}
                </button>
              ))}
            </div>
          </div>

          {/* Recent Queries */}
          <div className="bg-white dark:bg-neutral-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="flex items-center space-x-2 mb-4">
              <History className="h-5 w-5 text-gray-500" />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">最近查询</h3>
            </div>
            <div className="space-y-2">
              {results.slice(0, 3).map((result) => (
                <button
                  key={result.id}
                  onClick={() => setQuery(result.query)}
                  className="w-full text-left p-2 text-sm bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 rounded transition-colors"
                >
                  <div className="truncate">{result.query}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {result.timestamp.toLocaleDateString()}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default QueryInterface;