"use client";

import React, { useState } from "react";
import { Sidebar, SidebarBody, SidebarLink } from "@/components/ui/sidebar";
import { 
  LayoutDashboard, 
  Upload, 
  MessageSquare, 
  Settings, 
  FileText,
  BarChart3,
  Database
} from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

// Import individual page components
import DocumentUpload from "./DocumentUpload";
import QueryInterface from "./QueryInterface";
import SystemStatus from "./SystemStatus";
import ConfigurationPanel from "./ConfigurationPanel";

const RAGDashboard = () => {
  const [activeSection, setActiveSection] = useState("overview");
  
  const links = [
    {
      label: "概览",
      href: "#overview",
      icon: (
        <LayoutDashboard className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />
      ),
      id: "overview"
    },
    {
      label: "文档管理",
      href: "#documents",
      icon: (
        <Upload className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />
      ),
      id: "documents"
    },
    {
      label: "智能查询",
      href: "#query",
      icon: (
        <MessageSquare className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />
      ),
      id: "query"
    },
    {
      label: "知识库",
      href: "#knowledge",
      icon: (
        <Database className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />
      ),
      id: "knowledge"
    },
    {
      label: "系统状态",
      href: "#status",
      icon: (
        <BarChart3 className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />
      ),
      id: "status"
    },
    {
      label: "配置",
      href: "#settings",
      icon: (
        <Settings className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />
      ),
      id: "settings"
    },
  ];

  const [open, setOpen] = useState(false);

  const handleSectionChange = (sectionId: string) => {
    setActiveSection(sectionId);
  };

  const renderMainContent = () => {
    switch (activeSection) {
      case "overview":
        return <OverviewDashboard />;
      case "documents":
        return <DocumentUpload />;
      case "query":
        return <QueryInterface />;
      case "knowledge":
        return <KnowledgeBase />;
      case "status":
        return <SystemStatus />;
      case "settings":
        return <ConfigurationPanel />;
      default:
        return <OverviewDashboard />;
    }
  };

  return (
    <div className={cn(
      "rounded-md flex flex-col md:flex-row bg-gray-100 dark:bg-neutral-800 w-full flex-1 h-screen border border-neutral-200 dark:border-neutral-700 overflow-hidden"
    )}>
      <Sidebar open={open} setOpen={setOpen}>
        <SidebarBody className="justify-between gap-10">
          <div className="flex flex-col flex-1 overflow-y-auto overflow-x-hidden">
            {open ? <Logo /> : <LogoIcon />}
            <div className="mt-8 flex flex-col gap-2">
              {links.map((link, idx) => (
                <div key={idx} onClick={() => handleSectionChange(link.id)}>
                  <SidebarLink 
                    link={{
                      ...link,
                      href: "#"
                    }} 
                    className={cn(
                      "cursor-pointer",
                      activeSection === link.id && "bg-blue-50 text-blue-700 dark:bg-blue-900/20"
                    )}
                  />
                </div>
              ))}
            </div>
          </div>
          <div>
            <SidebarLink
              link={{
                label: "RAG系统",
                href: "#",
                icon: (
                  <div className="h-7 w-7 bg-blue-600 rounded-full flex items-center justify-center">
                    <span className="text-white text-xs font-bold">R</span>
                  </div>
                ),
              }}
            />
          </div>
        </SidebarBody>
      </Sidebar>
      
      {/* Main Content Area */}
      <div className="flex flex-1">
        <div className="p-2 md:p-6 rounded-tl-2xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 flex flex-col gap-2 flex-1 w-full h-full overflow-auto">
          {renderMainContent()}
        </div>
      </div>
    </div>
  );
};

// Logo Components
export const Logo = () => {
  return (
    <Link
      href="#"
      className="font-normal flex space-x-2 items-center text-sm text-black py-1 relative z-20"
    >
      <div className="h-5 w-6 bg-blue-600 dark:bg-blue-500 rounded-br-lg rounded-tr-sm rounded-tl-lg rounded-bl-sm flex-shrink-0" />
      <motion.span
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="font-medium text-black dark:text-white whitespace-pre"
      >
        RAG-Anything
      </motion.span>
    </Link>
  );
};

export const LogoIcon = () => {
  return (
    <Link
      href="#"
      className="font-normal flex space-x-2 items-center text-sm text-black py-1 relative z-20"
    >
      <div className="h-5 w-6 bg-blue-600 dark:bg-blue-500 rounded-br-lg rounded-tr-sm rounded-tl-lg rounded-bl-sm flex-shrink-0" />
    </Link>
  );
};

// Overview Dashboard Component
const OverviewDashboard = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">RAG-Anything 仪表盘</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-2">多模态检索增强生成系统控制中心</p>
      </div>
      
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-blue-50 dark:bg-blue-900/20 p-6 rounded-lg border border-blue-200 dark:border-blue-800">
          <div className="flex items-center">
            <FileText className="h-8 w-8 text-blue-600" />
            <div className="ml-4">
              <p className="text-blue-600 dark:text-blue-400 text-sm font-medium">已处理文档</p>
              <p className="text-2xl font-bold text-blue-900 dark:text-blue-100">24</p>
            </div>
          </div>
        </div>
        
        <div className="bg-green-50 dark:bg-green-900/20 p-6 rounded-lg border border-green-200 dark:border-green-800">
          <div className="flex items-center">
            <MessageSquare className="h-8 w-8 text-green-600" />
            <div className="ml-4">
              <p className="text-green-600 dark:text-green-400 text-sm font-medium">查询次数</p>
              <p className="text-2xl font-bold text-green-900 dark:text-green-100">156</p>
            </div>
          </div>
        </div>
        
        <div className="bg-purple-50 dark:bg-purple-900/20 p-6 rounded-lg border border-purple-200 dark:border-purple-800">
          <div className="flex items-center">
            <Database className="h-8 w-8 text-purple-600" />
            <div className="ml-4">
              <p className="text-purple-600 dark:text-purple-400 text-sm font-medium">知识块</p>
              <p className="text-2xl font-bold text-purple-900 dark:text-purple-100">1,247</p>
            </div>
          </div>
        </div>
        
        <div className="bg-orange-50 dark:bg-orange-900/20 p-6 rounded-lg border border-orange-200 dark:border-orange-800">
          <div className="flex items-center">
            <BarChart3 className="h-8 w-8 text-orange-600" />
            <div className="ml-4">
              <p className="text-orange-600 dark:text-orange-400 text-sm font-medium">系统状态</p>
              <p className="text-lg font-bold text-orange-900 dark:text-orange-100">正常</p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">快速操作</h3>
          <div className="space-y-3">
            <button className="w-full text-left p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors">
              <div className="flex items-center">
                <Upload className="h-5 w-5 text-blue-600 mr-3" />
                <span className="text-blue-900 dark:text-blue-100">上传新文档</span>
              </div>
            </button>
            <button className="w-full text-left p-3 bg-green-50 dark:bg-green-900/20 rounded-lg hover:bg-green-100 dark:hover:bg-green-900/30 transition-colors">
              <div className="flex items-center">
                <MessageSquare className="h-5 w-5 text-green-600 mr-3" />
                <span className="text-green-900 dark:text-green-100">开始查询</span>
              </div>
            </button>
          </div>
        </div>
        
        <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">最近活动</h3>
          <div className="space-y-3 text-sm">
            <div className="flex items-center text-gray-600 dark:text-gray-300">
              <div className="w-2 h-2 bg-green-500 rounded-full mr-3"></div>
              <span>文档 "research_paper.pdf" 处理完成</span>
            </div>
            <div className="flex items-center text-gray-600 dark:text-gray-300">
              <div className="w-2 h-2 bg-blue-500 rounded-full mr-3"></div>
              <span>执行了查询: "机器学习的应用场景"</span>
            </div>
            <div className="flex items-center text-gray-600 dark:text-gray-300">
              <div className="w-2 h-2 bg-purple-500 rounded-full mr-3"></div>
              <span>更新了系统配置</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Knowledge Base Component
const KnowledgeBase = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">知识库管理</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-2">浏览和管理已处理的文档知识</p>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
        {/* Document List */}
        <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">文档库</h3>
          <div className="space-y-3">
            {[
              { name: "research_paper.pdf", status: "已完成", chunks: 45 },
              { name: "product_manual.docx", status: "已完成", chunks: 32 },
              { name: "presentation.pptx", status: "处理中", chunks: 0 },
            ].map((doc, idx) => (
              <div key={idx} className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-900 dark:text-white">{doc.name}</span>
                  <span className={cn(
                    "text-xs px-2 py-1 rounded-full",
                    doc.status === "已完成" 
                      ? "bg-green-100 text-green-800" 
                      : "bg-yellow-100 text-yellow-800"
                  )}>
                    {doc.status}
                  </span>
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                  {doc.chunks > 0 ? `${doc.chunks} 个知识块` : "等待处理"}
                </p>
              </div>
            ))}
          </div>
        </div>
        
        {/* Knowledge Graph */}
        <div className="lg:col-span-2 bg-white dark:bg-neutral-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">知识图谱</h3>
          <div className="h-96 bg-gray-50 dark:bg-gray-700 rounded-lg flex items-center justify-center">
            <p className="text-gray-500 dark:text-gray-400">知识图谱可视化 (开发中)</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RAGDashboard;