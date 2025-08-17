-- PostgreSQL初始化脚本
-- 创建vector扩展用于向量存储
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建AGE扩展用于图数据库功能 (可选)
-- CREATE EXTENSION IF NOT EXISTS age;

-- 创建LightRAG专用数据库
-- CREATE DATABASE lightrag OWNER raguser;

-- 设置搜索路径
-- \c lightrag
-- SET search_path = public;

-- 创建基础表结构会由LightRAG自动创建
-- 这里只做扩展安装