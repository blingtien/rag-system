#!/usr/bin/env python3
"""
连接状态检测器
增强API服务启动时的远程存储连接状态检测和日志输出
"""

import asyncio
import asyncpg
import os
import socket
import time
import logging
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ConnectionStatus(Enum):
    """连接状态枚举"""
    CONNECTED = "✅ 已连接"
    FAILED = "❌ 连接失败" 
    TIMEOUT = "⏰ 连接超时"
    NOT_CONFIGURED = "⚠️ 未配置"
    SKIP = "⏸️ 跳过检测"

@dataclass
class ConnectionResult:
    """连接检测结果"""
    service: str
    status: ConnectionStatus
    message: str
    response_time_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None

class RemoteConnectionChecker:
    """远程存储连接检测器"""
    
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.results = {}
        
    async def check_all_connections(self) -> Dict[str, ConnectionResult]:
        """检查所有远程存储连接"""
        logger.info("🔍 开始检测远程存储连接状态...")
        
        # 并行检测所有连接
        tasks = [
            self._check_postgresql(),
            self._check_neo4j(), 
            self._check_redis(),
            self._check_nfs_storage(),
            self._check_network_latency()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 整理结果
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"连接检测异常: {result}")
            elif isinstance(result, ConnectionResult):
                self.results[result.service] = result
        
        # 输出汇总报告
        self._print_connection_summary()
        return self.results
    
    async def _check_postgresql(self) -> ConnectionResult:
        """检测PostgreSQL连接"""
        service = "PostgreSQL"
        start_time = time.time()
        
        try:
            # 从环境变量获取连接信息
            host = os.getenv('POSTGRES_HOST', '192.168.7.130')
            port = int(os.getenv('POSTGRES_PORT', '5432'))
            database = os.getenv('POSTGRES_DATABASE', os.getenv('POSTGRES_DB', 'raganything'))
            user = os.getenv('POSTGRES_USER', 'ragsvr')
            password = os.getenv('POSTGRES_PASSWORD', 'ragpass2024')
            
            if not all([host, port, database, user]):
                return ConnectionResult(
                    service=service,
                    status=ConnectionStatus.NOT_CONFIGURED,
                    message="缺少必要的连接参数"
                )
            
            # 构建连接字符串
            if host.startswith('/'):  # Unix socket
                dsn = f"postgresql://{user}@/{database}?host={host}"
            else:
                dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"
            
            # 尝试连接
            conn = await asyncio.wait_for(
                asyncpg.connect(dsn),
                timeout=self.timeout
            )
            
            # 执行简单查询测试
            version = await conn.fetchval("SELECT version()")
            await conn.close()
            
            response_time = (time.time() - start_time) * 1000
            
            return ConnectionResult(
                service=service,
                status=ConnectionStatus.CONNECTED,
                message=f"连接成功 ({host}:{port}/{database})",
                response_time_ms=response_time,
                details={
                    "host": host,
                    "port": port, 
                    "database": database,
                    "user": user,
                    "version": version[:100] if version else "未知版本"
                }
            )
            
        except asyncio.TimeoutError:
            return ConnectionResult(
                service=service,
                status=ConnectionStatus.TIMEOUT,
                message=f"连接超时 ({self.timeout}s)"
            )
        except Exception as e:
            return ConnectionResult(
                service=service,
                status=ConnectionStatus.FAILED,
                message=f"连接失败: {str(e)}"
            )
    
    async def _check_neo4j(self) -> ConnectionResult:
        """检测Neo4j连接"""
        service = "Neo4j"
        start_time = time.time()
        
        try:
            # 从环境变量获取连接信息
            uri = os.getenv('NEO4J_URI', 'bolt://192.168.7.130:7687')
            username = os.getenv('NEO4J_USER', os.getenv('NEO4J_USERNAME', 'neo4j'))
            password = os.getenv('NEO4J_PASSWORD', 'password123')
            database = os.getenv('NEO4J_DATABASE', 'neo4j')
            
            if not all([uri, username, password]):
                return ConnectionResult(
                    service=service,
                    status=ConnectionStatus.NOT_CONFIGURED,
                    message="缺少必要的连接参数"
                )
            
            # 尝试导入neo4j驱动
            try:
                from neo4j import GraphDatabase
            except ImportError:
                return ConnectionResult(
                    service=service,
                    status=ConnectionStatus.FAILED,
                    message="Neo4j驱动未安装 (pip install neo4j)"
                )
            
            # 创建连接
            driver = GraphDatabase.driver(uri, auth=(username, password))
            
            # 测试连接
            def test_connection():
                with driver.session(database=database) as session:
                    result = session.run("RETURN 1 as test")
                    return result.single()
            
            result = await asyncio.wait_for(
                asyncio.to_thread(test_connection),
                timeout=self.timeout
            )
            
            driver.close()
            response_time = (time.time() - start_time) * 1000
            
            return ConnectionResult(
                service=service,
                status=ConnectionStatus.CONNECTED,
                message=f"连接成功 ({uri})",
                response_time_ms=response_time,
                details={
                    "uri": uri,
                    "database": database,
                    "username": username
                }
            )
            
        except asyncio.TimeoutError:
            return ConnectionResult(
                service=service,
                status=ConnectionStatus.TIMEOUT,
                message=f"连接超时 ({self.timeout}s)"
            )
        except Exception as e:
            return ConnectionResult(
                service=service,
                status=ConnectionStatus.FAILED,
                message=f"连接失败: {str(e)}"
            )
    
    async def _check_redis(self) -> ConnectionResult:
        """检测Redis连接"""
        service = "Redis"
        start_time = time.time()
        
        try:
            # 从环境变量获取连接信息
            host = os.getenv('REDIS_HOST', '192.168.7.130')
            port = int(os.getenv('REDIS_PORT', '6379'))
            db = int(os.getenv('REDIS_DB', '0'))
            password = os.getenv('REDIS_PASSWORD', '')
            
            # 尝试导入redis客户端
            try:
                import aioredis
            except ImportError:
                return ConnectionResult(
                    service=service,
                    status=ConnectionStatus.FAILED,
                    message="Redis客户端未安装 (pip install aioredis)"
                )
            
            # 创建连接
            if password:
                redis_url = f"redis://:{password}@{host}:{port}/{db}"
            else:
                redis_url = f"redis://{host}:{port}/{db}"
            
            redis = aioredis.from_url(redis_url)
            
            # 测试连接
            pong = await asyncio.wait_for(
                redis.ping(),
                timeout=self.timeout
            )
            
            # 获取Redis信息
            info = await redis.info("server")
            await redis.close()
            
            response_time = (time.time() - start_time) * 1000
            
            return ConnectionResult(
                service=service,
                status=ConnectionStatus.CONNECTED,
                message=f"连接成功 ({host}:{port})",
                response_time_ms=response_time,
                details={
                    "host": host,
                    "port": port,
                    "database": db,
                    "version": info.get("redis_version", "未知版本")
                }
            )
            
        except asyncio.TimeoutError:
            return ConnectionResult(
                service=service,
                status=ConnectionStatus.TIMEOUT,
                message=f"连接超时 ({self.timeout}s)"
            )
        except Exception as e:
            return ConnectionResult(
                service=service,
                status=ConnectionStatus.FAILED,
                message=f"连接失败: {str(e)}"
            )
    
    async def _check_nfs_storage(self) -> ConnectionResult:
        """检测NFS存储挂载状态"""
        service = "NFS存储"
        start_time = time.time()
        
        try:
            # 检查关键存储目录
            working_dir = os.getenv('WORKING_DIR', '/mnt/ragsystem/rag_storage')
            parse_cache_dir = os.getenv('PARSE_CACHE_DIR', '/mnt/ragsystem/parse_cache')
            upload_dir = os.getenv('UPLOAD_DIR', '/mnt/ragsystem/uploads')
            
            storage_paths = [
                working_dir,
                parse_cache_dir, 
                upload_dir,
                '/mnt/ragsystem'
            ]
            
            # 检查路径是否存在且可写
            accessible_paths = []
            readonly_paths = []
            inaccessible_paths = []
            
            for path in storage_paths:
                if os.path.exists(path):
                    try:
                        # 测试写权限
                        test_file = os.path.join(path, '.connection_test')
                        with open(test_file, 'w') as f:
                            f.write('test')
                        os.remove(test_file)
                        accessible_paths.append(path)
                    except (PermissionError, OSError):
                        readonly_paths.append(f"{path} (只读)")
                else:
                    inaccessible_paths.append(f"{path} (不存在)")
            
            response_time = (time.time() - start_time) * 1000
            
            total_paths = len(storage_paths)
            writable_count = len(accessible_paths)
            readonly_count = len(readonly_paths)
            missing_count = len(inaccessible_paths)
            
            if writable_count == total_paths:
                status = ConnectionStatus.CONNECTED
                message = f"所有存储目录可写 ({writable_count}/{total_paths})"
            elif writable_count > 0 or readonly_count > 0:
                if readonly_count > 0:
                    status = ConnectionStatus.CONNECTED  # 只读也算连接成功
                    message = f"NFS已挂载 - 可写:{writable_count}, 只读:{readonly_count}, 缺失:{missing_count}"
                else:
                    status = ConnectionStatus.FAILED
                    message = f"部分存储目录问题 - 可写:{writable_count}, 只读:{readonly_count}, 缺失:{missing_count}"
            else:
                status = ConnectionStatus.FAILED
                message = "所有存储目录都不可访问"
            
            return ConnectionResult(
                service=service,
                status=status,
                message=message,
                response_time_ms=response_time,
                details={
                    "writable": accessible_paths,
                    "readonly": readonly_paths,
                    "missing": inaccessible_paths,
                    "working_dir": working_dir
                }
            )
            
        except Exception as e:
            return ConnectionResult(
                service=service,
                status=ConnectionStatus.FAILED,
                message=f"检测失败: {str(e)}"
            )
    
    async def _check_network_latency(self) -> ConnectionResult:
        """检测网络延迟"""
        service = "网络延迟"
        
        try:
            # 测试到数据库服务器的网络延迟
            db_host = os.getenv('POSTGRES_HOST', '192.168.7.130')
            if db_host.startswith('/'):
                # Unix socket，跳过网络延迟检测
                return ConnectionResult(
                    service=service,
                    status=ConnectionStatus.SKIP,
                    message="使用Unix socket，跳过网络延迟检测"
                )
            
            # 简单的TCP连接测试
            start_time = time.time()
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            try:
                result = sock.connect_ex((db_host, 5432))  # PostgreSQL端口
                response_time = (time.time() - start_time) * 1000
                
                if result == 0:
                    status = ConnectionStatus.CONNECTED
                    if response_time < 10:
                        message = f"网络延迟优秀 ({response_time:.1f}ms)"
                    elif response_time < 50:
                        message = f"网络延迟良好 ({response_time:.1f}ms)"
                    elif response_time < 100:
                        message = f"网络延迟一般 ({response_time:.1f}ms)"
                    else:
                        message = f"网络延迟较高 ({response_time:.1f}ms)"
                else:
                    status = ConnectionStatus.FAILED
                    message = f"网络不通 (错误代码: {result})"
                    response_time = None
            finally:
                sock.close()
            
            return ConnectionResult(
                service=service,
                status=status,
                message=message,
                response_time_ms=response_time,
                details={"target_host": db_host}
            )
            
        except Exception as e:
            return ConnectionResult(
                service=service,
                status=ConnectionStatus.FAILED,
                message=f"网络检测失败: {str(e)}"
            )
    
    def _print_connection_summary(self):
        """打印连接状态汇总"""
        logger.info("=" * 80)
        logger.info("🔗 远程存储连接状态检测报告")
        logger.info("=" * 80)
        
        # 按状态分类统计
        connected = []
        failed = []
        other = []
        
        for service, result in self.results.items():
            if result.status == ConnectionStatus.CONNECTED:
                connected.append(result)
            elif result.status in [ConnectionStatus.FAILED, ConnectionStatus.TIMEOUT]:
                failed.append(result)
            else:
                other.append(result)
        
        # 输出详细信息
        all_results = connected + failed + other
        for result in all_results:
            status_line = f"{result.status.value} {result.service}: {result.message}"
            
            if result.response_time_ms:
                status_line += f" ({result.response_time_ms:.1f}ms)"
            
            if result.status == ConnectionStatus.CONNECTED:
                logger.info(status_line)
                
                # 输出详细信息
                if result.details:
                    for key, value in result.details.items():
                        if key not in ['version']:  # 跳过版本信息以节省空间
                            logger.info(f"   {key}: {value}")
            else:
                logger.warning(status_line)
        
        # 输出汇总统计
        logger.info("-" * 80)
        total_services = len(self.results)
        connected_count = len(connected)
        failed_count = len(failed)
        
        if connected_count == total_services:
            logger.info(f"🎉 所有远程服务连接正常 ({connected_count}/{total_services})")
        elif connected_count > 0:
            logger.warning(f"⚠️ 部分服务连接异常: 正常 {connected_count}, 异常 {failed_count}")
        else:
            logger.error(f"🚨 所有远程服务连接失败 ({failed_count} 个服务)")
        
        logger.info("=" * 80)


# 快速连接检测函数
async def quick_connection_check() -> Dict[str, ConnectionResult]:
    """快速连接检测（供其他模块调用）"""
    checker = RemoteConnectionChecker(timeout=3.0)
    return await checker.check_all_connections()


# 命令行测试
if __name__ == "__main__":
    import sys
    import logging
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    async def main():
        checker = RemoteConnectionChecker()
        results = await checker.check_all_connections()
        
        # 返回退出代码
        failed_count = sum(1 for r in results.values() 
                          if r.status in [ConnectionStatus.FAILED, ConnectionStatus.TIMEOUT])
        sys.exit(failed_count)
    
    asyncio.run(main())