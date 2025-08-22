"use client";

import React, { useState, useCallback } from "react";
import { Upload, File, X, CheckCircle, AlertCircle, Loader } from "lucide-react";
import { cn } from "@/lib/utils";

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  status: 'uploading' | 'processing' | 'completed' | 'error';
  progress: number;
  error?: string;
}

const DocumentUpload = () => {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);

  const supportedFormats = [
    { ext: '.pdf', label: 'PDF文档', icon: '📄' },
    { ext: '.docx', label: 'Word文档', icon: '📝' },
    { ext: '.pptx', label: 'PowerPoint演示', icon: '📊' },
    { ext: '.txt', label: '文本文件', icon: '📋' },
    { ext: '.md', label: 'Markdown文件', icon: '📔' },
    { ext: '.jpg', label: '图片文件', icon: '🖼️' },
    { ext: '.png', label: '图片文件', icon: '🖼️' },
  ];

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    
    const droppedFiles = Array.from(e.dataTransfer.files);
    handleFiles(droppedFiles);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    handleFiles(selectedFiles);
  }, []);

  const handleFiles = (fileList: File[]) => {
    const newFiles: UploadedFile[] = fileList.map(file => ({
      id: Math.random().toString(36).substr(2, 9),
      name: file.name,
      size: file.size,
      type: file.type,
      status: 'uploading',
      progress: 0,
    }));

    setFiles(prev => [...prev, ...newFiles]);

    // 真实文件上传到后端API
    newFiles.forEach(file => {
      uploadFileToServer(file, fileList.find(f => f.name === file.name)!);
    });
  };

  const uploadFileToServer = async (uploadedFile: UploadedFile, actualFile: File) => {
    try {
      // 创建FormData用于文件上传
      const formData = new FormData();
      formData.append('file', actualFile);
      formData.append('parser', 'mineru');
      formData.append('parse_method', 'auto');

      // 更新状态为上传中
      setFiles(prev => prev.map(file => 
        file.id === uploadedFile.id 
          ? { ...file, status: 'uploading', progress: 50 }
          : file
      ));

      // 调用后端API
      const response = await fetch('http://localhost:8000/api/documents/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`上传失败: ${response.statusText}`);
      }

      const result = await response.json();
      
      // 上传成功，更新为处理中状态
      setFiles(prev => prev.map(file => 
        file.id === uploadedFile.id 
          ? { ...file, status: 'processing', progress: 100 }
          : file
      ));

      // 模拟后端处理时间（因为后端是异步处理）
      setTimeout(() => {
        setFiles(prev => prev.map(file => 
          file.id === uploadedFile.id 
            ? { ...file, status: 'completed' }
            : file
        ));
      }, 3000 + Math.random() * 2000);

    } catch (error) {
      console.error('文件上传失败:', error);
      // 更新为错误状态
      setFiles(prev => prev.map(file => 
        file.id === uploadedFile.id 
          ? { 
              ...file, 
              status: 'error', 
              progress: 0,
              error: error instanceof Error ? error.message : '上传失败'
            }
          : file
      ));
    }
  };

  const removeFile = (fileId: string) => {
    setFiles(prev => prev.filter(file => file.id !== fileId));
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusIcon = (status: UploadedFile['status']) => {
    switch (status) {
      case 'uploading':
      case 'processing':
        return <Loader className="h-4 w-4 animate-spin text-blue-500" />;
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
    }
  };

  const getStatusText = (status: UploadedFile['status']) => {
    switch (status) {
      case 'uploading':
        return '上传中...';
      case 'processing':
        return '处理中...';
      case 'completed':
        return '已完成';
      case 'error':
        return '错误';
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">文档管理</h1>
        <p className="text-gray-600 dark:text-gray-300 mt-2">上传并处理各种格式的文档</p>
      </div>

      {/* Upload Area */}
      <div
        className={cn(
          "border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200",
          isDragOver
            ? "border-blue-400 bg-blue-50 dark:bg-blue-900/20"
            : "border-gray-300 dark:border-gray-600 hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20"
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <Upload className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          拖拽文件到此处或点击上传
        </h3>
        <p className="text-gray-600 dark:text-gray-300 mb-4">
          支持多种文档格式，包括 PDF、Word、PowerPoint、图片等
        </p>
        <input
          type="file"
          multiple
          onChange={handleFileSelect}
          className="hidden"
          id="file-upload"
          accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.jpg,.jpeg,.png,.gif,.bmp,.tiff,.webp"
        />
        <label
          htmlFor="file-upload"
          className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 cursor-pointer transition-colors"
        >
          <Upload className="h-4 w-4 mr-2" />
          选择文件
        </label>
      </div>

      {/* Supported Formats */}
      <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">支持的文件格式</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
          {supportedFormats.map((format, idx) => (
            <div key={idx} className="text-center p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="text-2xl mb-2">{format.icon}</div>
              <div className="text-xs font-medium text-gray-900 dark:text-white">{format.ext}</div>
              <div className="text-xs text-gray-600 dark:text-gray-300">{format.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            上传队列 ({files.length})
          </h3>
          <div className="space-y-3">
            {files.map((file) => (
              <div key={file.id} className="flex items-center space-x-4 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <File className="h-8 w-8 text-gray-500 flex-shrink-0" />
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {file.name}
                    </p>
                    <div className="flex items-center space-x-2">
                      {getStatusIcon(file.status)}
                      <span className="text-xs text-gray-600 dark:text-gray-300">
                        {getStatusText(file.status)}
                      </span>
                      <button
                        onClick={() => removeFile(file.id)}
                        className="text-gray-400 hover:text-red-500 transition-colors"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between text-xs text-gray-600 dark:text-gray-300">
                    <span>{formatFileSize(file.size)}</span>
                    {file.status === 'uploading' && (
                      <span>{Math.round(file.progress)}%</span>
                    )}
                  </div>
                  
                  {(file.status === 'uploading' || file.status === 'processing') && (
                    <div className="mt-2">
                      <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${file.progress}%` }}
                        />
                      </div>
                    </div>
                  )}
                  
                  {file.error && (
                    <p className="text-xs text-red-600 dark:text-red-400 mt-1">{file.error}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Processing Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
          <div className="text-blue-600 dark:text-blue-400 text-sm font-medium">总文件数</div>
          <div className="text-2xl font-bold text-blue-900 dark:text-blue-100">{files.length}</div>
        </div>
        
        <div className="bg-green-50 dark:bg-green-900/20 p-4 rounded-lg border border-green-200 dark:border-green-800">
          <div className="text-green-600 dark:text-green-400 text-sm font-medium">已完成</div>
          <div className="text-2xl font-bold text-green-900 dark:text-green-100">
            {files.filter(f => f.status === 'completed').length}
          </div>
        </div>
        
        <div className="bg-yellow-50 dark:bg-yellow-900/20 p-4 rounded-lg border border-yellow-200 dark:border-yellow-800">
          <div className="text-yellow-600 dark:text-yellow-400 text-sm font-medium">处理中</div>
          <div className="text-2xl font-bold text-yellow-900 dark:text-yellow-100">
            {files.filter(f => f.status === 'processing' || f.status === 'uploading').length}
          </div>
        </div>
        
        <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-lg border border-red-200 dark:border-red-800">
          <div className="text-red-600 dark:text-red-400 text-sm font-medium">错误</div>
          <div className="text-2xl font-bold text-red-900 dark:text-red-100">
            {files.filter(f => f.status === 'error').length}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocumentUpload;