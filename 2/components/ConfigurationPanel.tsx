"use client";

import React, { useState } from "react";
import { Settings, Save, RotateCcw, Eye, EyeOff, TestTube, CheckCircle, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ConfigSection {
  id: string;
  title: string;
  description: string;
  settings: ConfigSetting[];
}

interface ConfigSetting {
  key: string;
  label: string;
  type: 'text' | 'number' | 'boolean' | 'select' | 'password';
  value: any;
  default: any;
  description?: string;
  options?: { value: string; label: string }[];
  validation?: (value: any) => string | null;
}

const ConfigurationPanel = () => {
  const [activeSection, setActiveSection] = useState("parser");
  const [showPasswords, setShowPasswords] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, boolean>>({});
  const [isTesting, setIsTesting] = useState<Record<string, boolean>>({});

  const [config, setConfig] = useState<Record<string, ConfigSection>>({
    parser: {
      id: "parser",
      title: "文档解析",
      description: "配置文档解析器和处理方法",
      settings: [
        {
          key: "parser",
          label: "解析器",
          type: "select",
          value: "mineru",
          default: "mineru",
          description: "选择文档解析引擎",
          options: [
            { value: "mineru", label: "MinerU (推荐)" },
            { value: "docling", label: "Docling" }
          ]
        },
        {
          key: "parse_method",
          label: "解析方法",
          type: "select",
          value: "auto",
          default: "auto",
          description: "文档解析的具体方法",
          options: [
            { value: "auto", label: "自动选择" },
            { value: "ocr", label: "OCR识别" },
            { value: "txt", label: "文本提取" }
          ]
        },
        {
          key: "max_concurrent_files",
          label: "最大并发文件数",
          type: "number",
          value: 4,
          default: 4,
          description: "同时处理的文件数量上限"
        },
        {
          key: "device",
          label: "计算设备",
          type: "select",
          value: "cuda",
          default: "cuda",
          options: [
            { value: "cuda", label: "GPU (CUDA)" },
            { value: "cpu", label: "CPU" }
          ]
        }
      ]
    },
    multimodal: {
      id: "multimodal",
      title: "多模态处理",
      description: "配置图像、表格、公式等多模态内容的处理选项",
      settings: [
        {
          key: "enable_image_processing",
          label: "启用图像处理",
          type: "boolean",
          value: true,
          default: true,
          description: "处理文档中的图像内容"
        },
        {
          key: "enable_table_processing",
          label: "启用表格处理",
          type: "boolean",
          value: true,
          default: true,
          description: "分析和处理表格数据"
        },
        {
          key: "enable_equation_processing",
          label: "启用公式处理",
          type: "boolean",
          value: true,
          default: true,
          description: "识别和处理数学公式"
        },
        {
          key: "context_window",
          label: "上下文窗口",
          type: "number",
          value: 1,
          default: 1,
          description: "多模态内容的上下文范围"
        },
        {
          key: "max_context_tokens",
          label: "最大上下文令牌数",
          type: "number",
          value: 2000,
          default: 2000,
          description: "上下文内容的最大令牌数量"
        }
      ]
    },
    llm: {
      id: "llm",
      title: "LLM配置",
      description: "配置大语言模型相关参数",
      settings: [
        {
          key: "api_key",
          label: "API密钥",
          type: "password",
          value: "sk-xxxxxxxxxxxxxxxx",
          default: "",
          description: "OpenAI或其他LLM服务的API密钥"
        },
        {
          key: "base_url",
          label: "API基础URL",
          type: "text",
          value: "https://api.openai.com/v1",
          default: "https://api.openai.com/v1",
          description: "LLM服务的API端点"
        },
        {
          key: "model_name",
          label: "模型名称",
          type: "select",
          value: "gpt-4",
          default: "gpt-4",
          options: [
            { value: "gpt-4", label: "GPT-4" },
            { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
            { value: "claude-3", label: "Claude 3" }
          ]
        },
        {
          key: "temperature",
          label: "温度参数",
          type: "number",
          value: 0.7,
          default: 0.7,
          description: "控制模型输出的随机性 (0.0-1.0)"
        },
        {
          key: "max_tokens",
          label: "最大令牌数",
          type: "number",
          value: 4000,
          default: 4000,
          description: "单次响应的最大令牌数"
        }
      ]
    },
    storage: {
      id: "storage",
      title: "存储配置",
      description: "配置数据存储和向量数据库",
      settings: [
        {
          key: "working_dir",
          label: "工作目录",
          type: "text",
          value: "./rag_storage",
          default: "./rag_storage",
          description: "RAG系统的数据存储目录"
        },
        {
          key: "vector_db_type",
          label: "向量数据库类型",
          type: "select",
          value: "chromadb",
          default: "chromadb",
          options: [
            { value: "chromadb", label: "ChromaDB" },
            { value: "faiss", label: "FAISS" },
            { value: "qdrant", label: "Qdrant" }
          ]
        },
        {
          key: "chunk_size",
          label: "文本分块大小",
          type: "number",
          value: 500,
          default: 500,
          description: "文本分块的令牌数量"
        },
        {
          key: "chunk_overlap",
          label: "分块重叠",
          type: "number",
          value: 50,
          default: 50,
          description: "相邻分块的重叠令牌数"
        }
      ]
    }
  });

  const updateSetting = (sectionId: string, key: string, value: any) => {
    setConfig(prev => ({
      ...prev,
      [sectionId]: {
        ...prev[sectionId],
        settings: prev[sectionId].settings.map(setting =>
          setting.key === key ? { ...setting, value } : setting
        )
      }
    }));
  };

  const resetSection = (sectionId: string) => {
    setConfig(prev => ({
      ...prev,
      [sectionId]: {
        ...prev[sectionId],
        settings: prev[sectionId].settings.map(setting => ({
          ...setting,
          value: setting.default
        }))
      }
    }));
  };

  const testConnection = async (sectionId: string) => {
    setIsTesting(prev => ({ ...prev, [sectionId]: true }));
    
    // 模拟测试连接
    setTimeout(() => {
      const isSuccess = Math.random() > 0.3; // 70% 成功率
      setTestResults(prev => ({ ...prev, [sectionId]: isSuccess }));
      setIsTesting(prev => ({ ...prev, [sectionId]: false }));
    }, 2000);
  };

  const saveConfiguration = () => {
    // 这里应该调用API保存配置
    console.log("Saving configuration:", config);
    alert("配置已保存！");
  };

  const renderSetting = (sectionId: string, setting: ConfigSetting) => {
    const commonProps = {
      id: `${sectionId}_${setting.key}`,
      value: setting.value,
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const value = setting.type === 'boolean' ? e.target.checked : 
                     setting.type === 'number' ? Number(e.target.value) : e.target.value;
        updateSetting(sectionId, setting.key, value);
      },
      className: "w-full p-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
    };

    switch (setting.type) {
      case 'boolean':
        return (
          <div className="flex items-center">
            <input
              type="checkbox"
              checked={setting.value}
              onChange={(e) => updateSetting(sectionId, setting.key, e.target.checked)}
              className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
            />
            <span className="ml-2 text-sm text-gray-600 dark:text-gray-300">{setting.description}</span>
          </div>
        );
      
      case 'select':
        return (
          <select {...commonProps}>
            {setting.options?.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        );
      
      case 'password':
        return (
          <div className="relative">
            <input
              type={showPasswords ? 'text' : 'password'}
              {...commonProps}
            />
            <button
              type="button"
              onClick={() => setShowPasswords(!showPasswords)}
              className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              {showPasswords ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        );
      
      default:
        return <input type={setting.type} {...commonProps} />;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">系统配置</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-2">管理RAG系统的各项配置参数</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Navigation */}
        <div className="bg-white dark:bg-neutral-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">配置分类</h3>
          <nav className="space-y-2">
            {Object.values(config).map((section) => (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={cn(
                  "w-full text-left p-3 rounded-lg transition-colors",
                  activeSection === section.id
                    ? "bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-800"
                    : "text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700"
                )}
              >
                <div className="font-medium">{section.title}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {section.description}
                </div>
              </button>
            ))}
          </nav>
        </div>

        {/* Configuration Form */}
        <div className="lg:col-span-3 space-y-6">
          {Object.values(config)
            .filter(section => section.id === activeSection)
            .map(section => (
              <div key={section.id} className="bg-white dark:bg-neutral-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
                      {section.title}
                    </h3>
                    <p className="text-gray-600 dark:text-gray-300 mt-1">
                      {section.description}
                    </p>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    {(section.id === 'llm' || section.id === 'storage') && (
                      <button
                        onClick={() => testConnection(section.id)}
                        disabled={isTesting[section.id]}
                        className={cn(
                          "flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                          isTesting[section.id]
                            ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                            : "bg-blue-50 text-blue-700 hover:bg-blue-100 dark:bg-blue-900/20 dark:text-blue-300"
                        )}
                      >
                        {isTesting[section.id] ? (
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600" />
                        ) : (
                          <TestTube className="h-4 w-4" />
                        )}
                        <span>{isTesting[section.id] ? "测试中..." : "测试连接"}</span>
                      </button>
                    )}
                    
                    {testResults[section.id] !== undefined && (
                      <div className={cn(
                        "flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-medium",
                        testResults[section.id]
                          ? "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-300"
                          : "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-300"
                      )}>
                        {testResults[section.id] ? (
                          <CheckCircle className="h-3 w-3" />
                        ) : (
                          <AlertCircle className="h-3 w-3" />
                        )}
                        <span>{testResults[section.id] ? "连接成功" : "连接失败"}</span>
                      </div>
                    )}
                    
                    <button
                      onClick={() => resetSection(section.id)}
                      className="flex items-center space-x-1 px-3 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-50 rounded-lg transition-colors"
                      title="重置为默认值"
                    >
                      <RotateCcw className="h-4 w-4" />
                      <span className="text-sm">重置</span>
                    </button>
                  </div>
                </div>

                <div className="space-y-6">
                  {section.settings.map((setting) => (
                    <div key={setting.key}>
                      <label
                        htmlFor={`${section.id}_${setting.key}`}
                        className="block text-sm font-medium text-gray-900 dark:text-white mb-2"
                      >
                        {setting.label}
                      </label>
                      
                      {renderSetting(section.id, setting)}
                      
                      {setting.description && setting.type !== 'boolean' && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {setting.description}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}

          {/* Save Button */}
          <div className="bg-white dark:bg-neutral-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-600 dark:text-gray-300">
                配置更改将在保存后生效，部分设置可能需要重启服务
              </p>
              
              <button
                onClick={saveConfiguration}
                className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors"
              >
                <Save className="h-4 w-4" />
                <span>保存配置</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfigurationPanel;