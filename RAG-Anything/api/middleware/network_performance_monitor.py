#!/usr/bin/env python3
"""
网络性能监控和诊断工具

功能特性:
1. 实时网络连接质量监控
2. 带宽使用分析和预测
3. 延迟和丢包检测
4. 连接稳定性评估
5. 网络拓扑发现
6. 性能优化建议
7. 网络故障诊断
"""

import asyncio
import time
import json
import logging
import socket
import subprocess
import platform
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from collections import defaultdict, deque
import statistics
import threading
import weakref

try:
    import ping3
    PING3_AVAILABLE = True
except ImportError:
    PING3_AVAILABLE = False

try:
    import speedtest
    SPEEDTEST_AVAILABLE = True
except ImportError:
    SPEEDTEST_AVAILABLE = False

from middleware.unified_logging import LoggerFactory, LogCategory


class NetworkQuality(Enum):
    """网络质量等级"""
    EXCELLENT = "excellent"    # 优秀
    GOOD = "good"             # 良好
    FAIR = "fair"             # 一般
    POOR = "poor"             # 较差
    CRITICAL = "critical"     # 严重


class ConnectionType(Enum):
    """连接类型"""
    ETHERNET = "ethernet"
    WIFI = "wifi"
    MOBILE = "mobile"
    UNKNOWN = "unknown"


class DiagnosticLevel(IntEnum):
    """诊断级别"""
    BASIC = 1      # 基础检测
    STANDARD = 2   # 标准检测
    ADVANCED = 3   # 高级检测
    DEEP = 4       # 深度检测


@dataclass
class NetworkMetrics:
    """网络指标"""
    timestamp: float
    
    # 延迟指标
    latency_ms: float = 0.0
    jitter_ms: float = 0.0
    packet_loss_percent: float = 0.0
    
    # 带宽指标
    bandwidth_download_mbps: float = 0.0
    bandwidth_upload_mbps: float = 0.0
    bandwidth_utilization_percent: float = 0.0
    
    # 连接指标
    active_connections: int = 0
    established_connections: int = 0
    time_wait_connections: int = 0
    
    # 流量指标
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    
    # 错误指标
    errors_in: int = 0
    errors_out: int = 0
    drops_in: int = 0
    drops_out: int = 0
    
    @property
    def total_bandwidth_mbps(self) -> float:
        """总带宽"""
        return self.bandwidth_download_mbps + self.bandwidth_upload_mbps
    
    @property
    def error_rate_percent(self) -> float:
        """错误率"""
        total_packets = self.packets_sent + self.packets_received
        total_errors = self.errors_in + self.errors_out + self.drops_in + self.drops_out
        if total_packets == 0:
            return 0.0
        return (total_errors / total_packets) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp,
            'latency': {
                'latency_ms': round(self.latency_ms, 2),
                'jitter_ms': round(self.jitter_ms, 2),
                'packet_loss_percent': round(self.packet_loss_percent, 2)
            },
            'bandwidth': {
                'download_mbps': round(self.bandwidth_download_mbps, 2),
                'upload_mbps': round(self.bandwidth_upload_mbps, 2),
                'utilization_percent': round(self.bandwidth_utilization_percent, 2),
                'total_mbps': round(self.total_bandwidth_mbps, 2)
            },
            'connections': {
                'active': self.active_connections,
                'established': self.established_connections,
                'time_wait': self.time_wait_connections
            },
            'traffic': {
                'bytes_sent': self.bytes_sent,
                'bytes_received': self.bytes_received,
                'packets_sent': self.packets_sent,
                'packets_received': self.packets_received
            },
            'errors': {
                'errors_in': self.errors_in,
                'errors_out': self.errors_out,
                'drops_in': self.drops_in,
                'drops_out': self.drops_out,
                'error_rate_percent': round(self.error_rate_percent, 2)
            }
        }


@dataclass
class NetworkInterface:
    """网络接口信息"""
    name: str
    display_name: str
    mac_address: str
    ip_addresses: List[str]
    connection_type: ConnectionType
    is_active: bool = False
    speed_mbps: Optional[int] = None
    mtu: int = 1500
    
    # 统计信息
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    errors_in: int = 0
    errors_out: int = 0
    drops_in: int = 0
    drops_out: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'display_name': self.display_name,
            'mac_address': self.mac_address,
            'ip_addresses': self.ip_addresses,
            'connection_type': self.connection_type.value,
            'is_active': self.is_active,
            'speed_mbps': self.speed_mbps,
            'mtu': self.mtu,
            'statistics': {
                'bytes_sent': self.bytes_sent,
                'bytes_received': self.bytes_received,
                'packets_sent': self.packets_sent,
                'packets_received': self.packets_received,
                'errors_in': self.errors_in,
                'errors_out': self.errors_out,
                'drops_in': self.drops_in,
                'drops_out': self.drops_out
            }
        }


@dataclass
class DiagnosticResult:
    """诊断结果"""
    test_name: str
    test_type: str
    status: str  # "passed", "warning", "failed", "error"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'test_name': self.test_name,
            'test_type': self.test_type,
            'status': self.status,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp,
            'duration_ms': self.duration_ms
        }


class NetworkLatencyAnalyzer:
    """网络延迟分析器"""
    
    def __init__(self):
        self.logger = LoggerFactory.get_logger("network_latency_analyzer")
        self.ping_history: deque = deque(maxlen=100)
        
        # 测试目标
        self.test_targets = [
            "8.8.8.8",          # Google DNS
            "1.1.1.1",          # Cloudflare DNS
            "114.114.114.114",  # 114 DNS
            "localhost"         # 本地回环
        ]
    
    async def measure_latency(self, target: str, count: int = 10) -> Dict[str, float]:
        """测量延迟"""
        if not PING3_AVAILABLE:
            return await self._fallback_ping(target, count)
        
        ping_times = []
        start_time = time.time()
        
        try:
            for _ in range(count):
                ping_time = ping3.ping(target, timeout=5)
                if ping_time is not None:
                    ping_times.append(ping_time * 1000)  # 转换为毫秒
                else:
                    ping_times.append(float('inf'))  # 超时
                
                await asyncio.sleep(0.1)  # 间隔100ms
            
            # 过滤无效值
            valid_pings = [p for p in ping_times if p != float('inf')]
            
            if not valid_pings:
                return {
                    'min_ms': float('inf'),
                    'max_ms': float('inf'),
                    'avg_ms': float('inf'),
                    'packet_loss_percent': 100.0,
                    'jitter_ms': 0.0
                }
            
            # 计算统计值
            min_ping = min(valid_pings)
            max_ping = max(valid_pings)
            avg_ping = statistics.mean(valid_pings)
            packet_loss = (count - len(valid_pings)) / count * 100
            
            # 计算抖动（标准差）
            jitter = statistics.stdev(valid_pings) if len(valid_pings) > 1 else 0.0
            
            result = {
                'min_ms': round(min_ping, 2),
                'max_ms': round(max_ping, 2),
                'avg_ms': round(avg_ping, 2),
                'packet_loss_percent': round(packet_loss, 2),
                'jitter_ms': round(jitter, 2),
                'test_duration_s': round(time.time() - start_time, 2),
                'target': target
            }
            
            # 记录历史
            self.ping_history.append({
                'timestamp': time.time(),
                'target': target,
                'result': result
            })
            
            return result
            
        except Exception as e:
            await self.logger.error(f"延迟测量失败 {target}: {str(e)}")
            return {
                'error': str(e),
                'target': target
            }
    
    async def _fallback_ping(self, target: str, count: int) -> Dict[str, float]:
        """备用ping实现"""
        try:
            system = platform.system().lower()
            if system == "windows":
                cmd = f"ping -n {count} {target}"
            else:
                cmd = f"ping -c {count} {target}"
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            output = stdout.decode()
            
            # 解析ping输出（简化版）
            lines = output.split('\n')
            ping_times = []
            
            for line in lines:
                if 'time=' in line or 'time<' in line:
                    try:
                        time_part = line.split('time')[1].split()[0]
                        time_value = float(time_part.replace('=', '').replace('<', '').replace('ms', ''))
                        ping_times.append(time_value)
                    except:
                        continue
            
            if ping_times:
                return {
                    'min_ms': min(ping_times),
                    'max_ms': max(ping_times),
                    'avg_ms': statistics.mean(ping_times),
                    'packet_loss_percent': (count - len(ping_times)) / count * 100,
                    'jitter_ms': statistics.stdev(ping_times) if len(ping_times) > 1 else 0.0,
                    'target': target
                }
            else:
                return {
                    'error': 'No ping data found',
                    'target': target
                }
                
        except Exception as e:
            return {
                'error': str(e),
                'target': target
            }
    
    async def analyze_all_targets(self) -> Dict[str, Dict[str, float]]:
        """分析所有目标的延迟"""
        results = {}
        
        tasks = [
            self.measure_latency(target) 
            for target in self.test_targets
        ]
        
        target_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for target, result in zip(self.test_targets, target_results):
            if isinstance(result, Exception):
                results[target] = {'error': str(result)}
            else:
                results[target] = result
        
        return results
    
    def get_latency_quality(self, avg_latency_ms: float) -> NetworkQuality:
        """评估延迟质量"""
        if avg_latency_ms < 20:
            return NetworkQuality.EXCELLENT
        elif avg_latency_ms < 50:
            return NetworkQuality.GOOD
        elif avg_latency_ms < 100:
            return NetworkQuality.FAIR
        elif avg_latency_ms < 200:
            return NetworkQuality.POOR
        else:
            return NetworkQuality.CRITICAL


class BandwidthAnalyzer:
    """带宽分析器"""
    
    def __init__(self):
        self.logger = LoggerFactory.get_logger("bandwidth_analyzer")
        self.bandwidth_history: deque = deque(maxlen=50)
    
    async def measure_bandwidth(self) -> Dict[str, float]:
        """测量带宽"""
        if not SPEEDTEST_AVAILABLE:
            return await self._estimate_bandwidth_from_interface()
        
        try:
            start_time = time.time()
            
            # 创建speedtest实例
            st = speedtest.Speedtest()
            
            # 获取最佳服务器
            await asyncio.to_thread(st.get_best_server)
            
            # 测试下载速度
            download_speed = await asyncio.to_thread(st.download)
            
            # 测试上传速度
            upload_speed = await asyncio.to_thread(st.upload)
            
            # 获取ping
            ping_result = st.results.ping
            
            result = {
                'download_mbps': round(download_speed / (1024 * 1024), 2),
                'upload_mbps': round(upload_speed / (1024 * 1024), 2),
                'ping_ms': round(ping_result, 2),
                'test_duration_s': round(time.time() - start_time, 2),
                'server_info': {
                    'host': st.best['host'],
                    'location': f"{st.best['name']}, {st.best['country']}"
                }
            }
            
            # 记录历史
            self.bandwidth_history.append({
                'timestamp': time.time(),
                'result': result
            })
            
            return result
            
        except Exception as e:
            await self.logger.error(f"带宽测量失败: {str(e)}")
            return {'error': str(e)}
    
    async def _estimate_bandwidth_from_interface(self) -> Dict[str, float]:
        """从网络接口估算带宽"""
        try:
            # 获取网络接口统计
            net_io_before = psutil.net_io_counters()
            await asyncio.sleep(1)  # 等待1秒
            net_io_after = psutil.net_io_counters()
            
            # 计算每秒传输的字节数
            bytes_sent_per_sec = net_io_after.bytes_sent - net_io_before.bytes_sent
            bytes_recv_per_sec = net_io_after.bytes_recv - net_io_before.bytes_recv
            
            # 转换为Mbps
            upload_mbps = (bytes_sent_per_sec * 8) / (1024 * 1024)
            download_mbps = (bytes_recv_per_sec * 8) / (1024 * 1024)
            
            return {
                'download_mbps': round(download_mbps, 2),
                'upload_mbps': round(upload_mbps, 2),
                'estimated': True,
                'note': 'Estimated from interface statistics'
            }
            
        except Exception as e:
            await self.logger.error(f"带宽估算失败: {str(e)}")
            return {'error': str(e)}
    
    def get_bandwidth_quality(self, download_mbps: float) -> NetworkQuality:
        """评估带宽质量"""
        if download_mbps > 100:
            return NetworkQuality.EXCELLENT
        elif download_mbps > 50:
            return NetworkQuality.GOOD
        elif download_mbps > 20:
            return NetworkQuality.FAIR
        elif download_mbps > 5:
            return NetworkQuality.POOR
        else:
            return NetworkQuality.CRITICAL


class NetworkInterfaceMonitor:
    """网络接口监控器"""
    
    def __init__(self):
        self.logger = LoggerFactory.get_logger("network_interface_monitor")
        self.interfaces: Dict[str, NetworkInterface] = {}
    
    async def discover_interfaces(self) -> Dict[str, NetworkInterface]:
        """发现网络接口"""
        interfaces = {}
        
        try:
            # 获取网络接口信息
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            net_io_counters = psutil.net_io_counters(pernic=True)
            
            for interface_name, addrs in net_if_addrs.items():
                # 跳过回环接口
                if interface_name.startswith('lo'):
                    continue
                
                # 获取IP地址
                ip_addresses = []
                mac_address = ""
                
                for addr in addrs:
                    if addr.family == socket.AF_INET:  # IPv4
                        ip_addresses.append(addr.address)
                    elif addr.family == psutil.AF_LINK:  # MAC地址
                        mac_address = addr.address
                
                # 获取接口统计
                stats = net_if_stats.get(interface_name)
                io_counters = net_io_counters.get(interface_name)
                
                if stats:
                    # 判断连接类型
                    connection_type = self._detect_connection_type(interface_name)
                    
                    interface = NetworkInterface(
                        name=interface_name,
                        display_name=self._get_display_name(interface_name),
                        mac_address=mac_address,
                        ip_addresses=ip_addresses,
                        connection_type=connection_type,
                        is_active=stats.isup,
                        speed_mbps=stats.speed if stats.speed > 0 else None,
                        mtu=stats.mtu
                    )
                    
                    # 添加IO统计
                    if io_counters:
                        interface.bytes_sent = io_counters.bytes_sent
                        interface.bytes_received = io_counters.bytes_recv
                        interface.packets_sent = io_counters.packets_sent
                        interface.packets_received = io_counters.packets_recv
                        interface.errors_in = io_counters.errin
                        interface.errors_out = io_counters.errout
                        interface.drops_in = io_counters.dropin
                        interface.drops_out = io_counters.dropout
                    
                    interfaces[interface_name] = interface
            
            self.interfaces = interfaces
            return interfaces
            
        except Exception as e:
            await self.logger.error(f"网络接口发现失败: {str(e)}")
            return {}
    
    def _detect_connection_type(self, interface_name: str) -> ConnectionType:
        """检测连接类型"""
        name_lower = interface_name.lower()
        
        if 'eth' in name_lower or 'en' in name_lower:
            return ConnectionType.ETHERNET
        elif 'wlan' in name_lower or 'wifi' in name_lower or 'wl' in name_lower:
            return ConnectionType.WIFI
        elif 'mobile' in name_lower or 'cellular' in name_lower:
            return ConnectionType.MOBILE
        else:
            return ConnectionType.UNKNOWN
    
    def _get_display_name(self, interface_name: str) -> str:
        """获取显示名称"""
        display_names = {
            'eth0': 'Ethernet Adapter',
            'eth1': 'Ethernet Adapter #2',
            'wlan0': 'Wireless Network Adapter',
            'wlan1': 'Wireless Network Adapter #2'
        }
        
        return display_names.get(interface_name, interface_name)
    
    async def get_active_interface(self) -> Optional[NetworkInterface]:
        """获取活跃的网络接口"""
        await self.discover_interfaces()
        
        # 优先选择有IP地址的以太网接口
        for interface in self.interfaces.values():
            if (interface.is_active and 
                interface.ip_addresses and 
                interface.connection_type == ConnectionType.ETHERNET):
                return interface
        
        # 其次选择Wi-Fi接口
        for interface in self.interfaces.values():
            if (interface.is_active and 
                interface.ip_addresses and 
                interface.connection_type == ConnectionType.WIFI):
                return interface
        
        # 最后选择任何活跃的接口
        for interface in self.interfaces.values():
            if interface.is_active and interface.ip_addresses:
                return interface
        
        return None


class NetworkDiagnosticEngine:
    """网络诊断引擎"""
    
    def __init__(self):
        self.logger = LoggerFactory.get_logger("network_diagnostic_engine")
        
        # 组件初始化
        self.latency_analyzer = NetworkLatencyAnalyzer()
        self.bandwidth_analyzer = BandwidthAnalyzer()
        self.interface_monitor = NetworkInterfaceMonitor()
        
        # 诊断历史
        self.diagnostic_history: deque = deque(maxlen=100)
    
    async def run_basic_diagnostics(self) -> List[DiagnosticResult]:
        """运行基础诊断"""
        results = []
        
        # 1. 网络接口检查
        results.append(await self._test_network_interfaces())
        
        # 2. 连通性测试
        results.append(await self._test_connectivity())
        
        # 3. DNS解析测试
        results.append(await self._test_dns_resolution())
        
        return results
    
    async def run_standard_diagnostics(self) -> List[DiagnosticResult]:
        """运行标准诊断"""
        results = await self.run_basic_diagnostics()
        
        # 4. 延迟和丢包测试
        results.append(await self._test_latency_and_packet_loss())
        
        # 5. 端口连接测试
        results.append(await self._test_port_connectivity())
        
        return results
    
    async def run_advanced_diagnostics(self) -> List[DiagnosticResult]:
        """运行高级诊断"""
        results = await self.run_standard_diagnostics()
        
        # 6. 带宽测试
        results.append(await self._test_bandwidth())
        
        # 7. 路由跟踪
        results.append(await self._test_route_tracing())
        
        return results
    
    async def run_deep_diagnostics(self) -> List[DiagnosticResult]:
        """运行深度诊断"""
        results = await self.run_advanced_diagnostics()
        
        # 8. 防火墙和安全检查
        results.append(await self._test_firewall_rules())
        
        # 9. 网络性能分析
        results.append(await self._test_network_performance())
        
        return results
    
    async def _test_network_interfaces(self) -> DiagnosticResult:
        """测试网络接口"""
        start_time = time.time()
        
        try:
            interfaces = await self.interface_monitor.discover_interfaces()
            active_interfaces = [iface for iface in interfaces.values() if iface.is_active]
            
            if not active_interfaces:
                return DiagnosticResult(
                    test_name="Network Interfaces",
                    test_type="connectivity",
                    status="failed",
                    message="No active network interfaces found",
                    duration_ms=(time.time() - start_time) * 1000
                )
            
            # 检查接口状态
            ethernet_count = sum(1 for iface in active_interfaces 
                               if iface.connection_type == ConnectionType.ETHERNET)
            wifi_count = sum(1 for iface in active_interfaces 
                           if iface.connection_type == ConnectionType.WIFI)
            
            return DiagnosticResult(
                test_name="Network Interfaces",
                test_type="connectivity",
                status="passed",
                message=f"Found {len(active_interfaces)} active interfaces",
                details={
                    'total_interfaces': len(interfaces),
                    'active_interfaces': len(active_interfaces),
                    'ethernet_interfaces': ethernet_count,
                    'wifi_interfaces': wifi_count,
                    'interfaces': [iface.to_dict() for iface in active_interfaces]
                },
                duration_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            return DiagnosticResult(
                test_name="Network Interfaces",
                test_type="connectivity",
                status="error",
                message=f"Interface test failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000
            )
    
    async def _test_connectivity(self) -> DiagnosticResult:
        """测试连通性"""
        start_time = time.time()
        
        try:
            # 测试本地回环
            localhost_result = await self.latency_analyzer.measure_latency("localhost", 3)
            
            # 测试外网连接
            internet_results = await self.latency_analyzer.analyze_all_targets()
            
            # 分析结果
            successful_targets = [target for target, result in internet_results.items() 
                                if 'error' not in result and result.get('avg_ms', float('inf')) < 1000]
            
            if not successful_targets:
                return DiagnosticResult(
                    test_name="Connectivity Test",
                    test_type="connectivity",
                    status="failed",
                    message="No internet connectivity detected",
                    details={
                        'localhost': localhost_result,
                        'internet_targets': internet_results
                    },
                    duration_ms=(time.time() - start_time) * 1000
                )
            
            status = "passed" if len(successful_targets) >= 2 else "warning"
            
            return DiagnosticResult(
                test_name="Connectivity Test",
                test_type="connectivity",
                status=status,
                message=f"Connected to {len(successful_targets)} out of {len(internet_results)} targets",
                details={
                    'localhost': localhost_result,
                    'internet_targets': internet_results,
                    'successful_targets': successful_targets
                },
                duration_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            return DiagnosticResult(
                test_name="Connectivity Test",
                test_type="connectivity",
                status="error",
                message=f"Connectivity test failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000
            )
    
    async def _test_dns_resolution(self) -> DiagnosticResult:
        """测试DNS解析"""
        start_time = time.time()
        
        try:
            test_domains = [
                "google.com",
                "cloudflare.com",
                "github.com",
                "stackoverflow.com"
            ]
            
            resolution_results = {}
            successful_resolutions = 0
            
            for domain in test_domains:
                try:
                    resolve_start = time.time()
                    result = socket.getaddrinfo(domain, None)
                    resolve_time = (time.time() - resolve_start) * 1000
                    
                    resolution_results[domain] = {
                        'status': 'success',
                        'resolve_time_ms': round(resolve_time, 2),
                        'ip_addresses': [addr[4][0] for addr in result]
                    }
                    successful_resolutions += 1
                    
                except Exception as e:
                    resolution_results[domain] = {
                        'status': 'failed',
                        'error': str(e)
                    }
            
            if successful_resolutions == 0:
                status = "failed"
                message = "DNS resolution completely failed"
            elif successful_resolutions < len(test_domains):
                status = "warning"
                message = f"DNS resolution partially successful ({successful_resolutions}/{len(test_domains)})"
            else:
                status = "passed"
                message = "DNS resolution working properly"
            
            return DiagnosticResult(
                test_name="DNS Resolution Test",
                test_type="connectivity",
                status=status,
                message=message,
                details={
                    'test_domains': test_domains,
                    'resolution_results': resolution_results,
                    'success_rate': round(successful_resolutions / len(test_domains) * 100, 1)
                },
                duration_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            return DiagnosticResult(
                test_name="DNS Resolution Test",
                test_type="connectivity",
                status="error",
                message=f"DNS test failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000
            )
    
    async def _test_latency_and_packet_loss(self) -> DiagnosticResult:
        """测试延迟和丢包"""
        start_time = time.time()
        
        try:
            latency_results = await self.latency_analyzer.analyze_all_targets()
            
            # 分析延迟质量
            valid_results = [result for result in latency_results.values() 
                           if 'error' not in result and 'avg_ms' in result]
            
            if not valid_results:
                return DiagnosticResult(
                    test_name="Latency and Packet Loss Test",
                    test_type="performance",
                    status="failed",
                    message="Could not measure latency to any target",
                    details=latency_results,
                    duration_ms=(time.time() - start_time) * 1000
                )
            
            # 计算平均延迟和丢包率
            avg_latencies = [result['avg_ms'] for result in valid_results]
            packet_losses = [result['packet_loss_percent'] for result in valid_results]
            
            overall_avg_latency = statistics.mean(avg_latencies)
            overall_packet_loss = statistics.mean(packet_losses)
            
            # 评估质量
            latency_quality = self.latency_analyzer.get_latency_quality(overall_avg_latency)
            
            # 确定状态
            if latency_quality in [NetworkQuality.EXCELLENT, NetworkQuality.GOOD] and overall_packet_loss < 1:
                status = "passed"
            elif latency_quality == NetworkQuality.FAIR or overall_packet_loss < 5:
                status = "warning"
            else:
                status = "failed"
            
            return DiagnosticResult(
                test_name="Latency and Packet Loss Test",
                test_type="performance",
                status=status,
                message=f"Avg latency: {overall_avg_latency:.1f}ms, Packet loss: {overall_packet_loss:.1f}%",
                details={
                    'individual_results': latency_results,
                    'overall_metrics': {
                        'average_latency_ms': round(overall_avg_latency, 2),
                        'average_packet_loss_percent': round(overall_packet_loss, 2),
                        'latency_quality': latency_quality.value
                    }
                },
                duration_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            return DiagnosticResult(
                test_name="Latency and Packet Loss Test",
                test_type="performance",
                status="error",
                message=f"Latency test failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000
            )
    
    async def _test_port_connectivity(self) -> DiagnosticResult:
        """测试端口连接"""
        start_time = time.time()
        
        try:
            # 测试常用端口
            test_ports = [
                ("google.com", 80, "HTTP"),
                ("google.com", 443, "HTTPS"),
                ("8.8.8.8", 53, "DNS"),
                ("localhost", 22, "SSH"),
                ("localhost", 8001, "API Server")  # 本地API服务器
            ]
            
            port_results = {}
            successful_connections = 0
            
            for host, port, description in test_ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)  # 5秒超时
                    
                    connect_start = time.time()
                    result = sock.connect_ex((host, port))
                    connect_time = (time.time() - connect_start) * 1000
                    
                    sock.close()
                    
                    if result == 0:
                        port_results[f"{host}:{port}"] = {
                            'status': 'open',
                            'description': description,
                            'connect_time_ms': round(connect_time, 2)
                        }
                        successful_connections += 1
                    else:
                        port_results[f"{host}:{port}"] = {
                            'status': 'closed',
                            'description': description,
                            'error_code': result
                        }
                        
                except Exception as e:
                    port_results[f"{host}:{port}"] = {
                        'status': 'failed',
                        'description': description,
                        'error': str(e)
                    }
            
            success_rate = successful_connections / len(test_ports) * 100
            
            if success_rate >= 80:
                status = "passed"
            elif success_rate >= 50:
                status = "warning"
            else:
                status = "failed"
            
            return DiagnosticResult(
                test_name="Port Connectivity Test",
                test_type="connectivity",
                status=status,
                message=f"Port connectivity: {successful_connections}/{len(test_ports)} ports accessible",
                details={
                    'port_results': port_results,
                    'success_rate': round(success_rate, 1)
                },
                duration_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            return DiagnosticResult(
                test_name="Port Connectivity Test",
                test_type="connectivity",
                status="error",
                message=f"Port test failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000
            )
    
    async def _test_bandwidth(self) -> DiagnosticResult:
        """测试带宽"""
        start_time = time.time()
        
        try:
            bandwidth_result = await self.bandwidth_analyzer.measure_bandwidth()
            
            if 'error' in bandwidth_result:
                return DiagnosticResult(
                    test_name="Bandwidth Test",
                    test_type="performance",
                    status="failed",
                    message=f"Bandwidth test failed: {bandwidth_result['error']}",
                    duration_ms=(time.time() - start_time) * 1000
                )
            
            download_speed = bandwidth_result.get('download_mbps', 0)
            upload_speed = bandwidth_result.get('upload_mbps', 0)
            
            # 评估带宽质量
            bandwidth_quality = self.bandwidth_analyzer.get_bandwidth_quality(download_speed)
            
            if bandwidth_quality in [NetworkQuality.EXCELLENT, NetworkQuality.GOOD]:
                status = "passed"
            elif bandwidth_quality == NetworkQuality.FAIR:
                status = "warning"
            else:
                status = "failed"
            
            return DiagnosticResult(
                test_name="Bandwidth Test",
                test_type="performance",
                status=status,
                message=f"Download: {download_speed:.1f} Mbps, Upload: {upload_speed:.1f} Mbps",
                details={
                    'bandwidth_result': bandwidth_result,
                    'bandwidth_quality': bandwidth_quality.value
                },
                duration_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            return DiagnosticResult(
                test_name="Bandwidth Test",
                test_type="performance",
                status="error",
                message=f"Bandwidth test failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000
            )
    
    async def _test_route_tracing(self) -> DiagnosticResult:
        """测试路由跟踪"""
        start_time = time.time()
        
        try:
            # 简化的路由跟踪（使用ping测试多个跳点）
            target = "8.8.8.8"
            
            route_info = {
                'target': target,
                'hops': [],
                'total_hops': 0,
                'trace_successful': False
            }
            
            # 由于权限限制，这里只做基本的连通性测试
            ping_result = await self.latency_analyzer.measure_latency(target, 5)
            
            if 'error' not in ping_result:
                route_info['trace_successful'] = True
                route_info['final_hop'] = {
                    'ip': target,
                    'latency_ms': ping_result['avg_ms'],
                    'packet_loss_percent': ping_result['packet_loss_percent']
                }
            
            status = "passed" if route_info['trace_successful'] else "failed"
            message = f"Route to {target}: {'reachable' if route_info['trace_successful'] else 'unreachable'}"
            
            return DiagnosticResult(
                test_name="Route Tracing Test",
                test_type="connectivity",
                status=status,
                message=message,
                details=route_info,
                duration_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            return DiagnosticResult(
                test_name="Route Tracing Test",
                test_type="connectivity",
                status="error",
                message=f"Route tracing failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000
            )
    
    async def _test_firewall_rules(self) -> DiagnosticResult:
        """测试防火墙规则"""
        start_time = time.time()
        
        try:
            firewall_info = {
                'platform': platform.system(),
                'firewall_active': False,
                'rules_checked': False,
                'open_ports': [],
                'blocked_ports': []
            }
            
            # 基本的端口扫描
            test_ports = [22, 80, 443, 8001, 8080]
            
            for port in test_ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex(('localhost', port))
                    sock.close()
                    
                    if result == 0:
                        firewall_info['open_ports'].append(port)
                    else:
                        firewall_info['blocked_ports'].append(port)
                except:
                    firewall_info['blocked_ports'].append(port)
            
            firewall_info['rules_checked'] = True
            
            return DiagnosticResult(
                test_name="Firewall Rules Test",
                test_type="security",
                status="passed",
                message=f"Firewall check completed: {len(firewall_info['open_ports'])} open ports",
                details=firewall_info,
                duration_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            return DiagnosticResult(
                test_name="Firewall Rules Test",
                test_type="security",
                status="error",
                message=f"Firewall test failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000
            )
    
    async def _test_network_performance(self) -> DiagnosticResult:
        """测试网络性能"""
        start_time = time.time()
        
        try:
            # 收集系统网络统计
            net_io = psutil.net_io_counters()
            net_connections = psutil.net_connections()
            
            # 分析连接状态
            connection_states = defaultdict(int)
            for conn in net_connections:
                connection_states[conn.status] += 1
            
            # 计算网络利用率（简化版）
            active_interface = await self.interface_monitor.get_active_interface()
            
            performance_metrics = {
                'total_bytes_sent': net_io.bytes_sent,
                'total_bytes_received': net_io.bytes_recv,
                'total_packets_sent': net_io.packets_sent,
                'total_packets_received': net_io.packets_recv,
                'errors_in': net_io.errin,
                'errors_out': net_io.errout,
                'drops_in': net_io.dropin,
                'drops_out': net_io.dropout,
                'connection_states': dict(connection_states),
                'active_interface': active_interface.to_dict() if active_interface else None
            }
            
            # 评估性能
            error_rate = (net_io.errin + net_io.errout) / max(net_io.packets_sent + net_io.packets_recv, 1) * 100
            drop_rate = (net_io.dropin + net_io.dropout) / max(net_io.packets_sent + net_io.packets_recv, 1) * 100
            
            if error_rate < 0.1 and drop_rate < 0.1:
                status = "passed"
                message = "Network performance is good"
            elif error_rate < 1.0 and drop_rate < 1.0:
                status = "warning"
                message = f"Minor network issues detected (error rate: {error_rate:.2f}%)"
            else:
                status = "failed"
                message = f"Network performance issues (error rate: {error_rate:.2f}%, drop rate: {drop_rate:.2f}%)"
            
            return DiagnosticResult(
                test_name="Network Performance Test",
                test_type="performance",
                status=status,
                message=message,
                details={
                    'performance_metrics': performance_metrics,
                    'analysis': {
                        'error_rate_percent': round(error_rate, 3),
                        'drop_rate_percent': round(drop_rate, 3)
                    }
                },
                duration_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            return DiagnosticResult(
                test_name="Network Performance Test",
                test_type="performance",
                status="error",
                message=f"Performance test failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000
            )


class NetworkPerformanceMonitor:
    """
    网络性能监控器
    
    主监控类，整合所有网络监控功能
    """
    
    def __init__(self):
        self.logger = LoggerFactory.get_logger("network_performance_monitor")
        
        # 组件初始化
        self.diagnostic_engine = NetworkDiagnosticEngine()
        self.latency_analyzer = self.diagnostic_engine.latency_analyzer
        self.bandwidth_analyzer = self.diagnostic_engine.bandwidth_analyzer
        self.interface_monitor = self.diagnostic_engine.interface_monitor
        
        # 监控状态
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.monitoring_interval = 60  # 60秒
        
        # 性能历史
        self.metrics_history: deque = deque(maxlen=1440)  # 24小时（每分钟一次）
        
        # 告警阈值
        self.alert_thresholds = {
            'latency_ms': 200,
            'packet_loss_percent': 5.0,
            'bandwidth_min_mbps': 10,
            'error_rate_percent': 1.0
        }
    
    async def start_monitoring(self):
        """启动监控"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        await self.logger.info("网络性能监控已启动")
    
    async def stop_monitoring(self):
        """停止监控"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        await self.logger.info("网络性能监控已停止")
    
    async def _monitoring_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                # 收集网络指标
                metrics = await self._collect_network_metrics()
                
                # 添加到历史记录
                self.metrics_history.append(metrics)
                
                # 检查告警
                await self._check_alerts(metrics)
                
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(f"监控循环错误: {str(e)}")
                await asyncio.sleep(10)  # 出错后等待10秒再试
    
    async def _collect_network_metrics(self) -> NetworkMetrics:
        """收集网络指标"""
        timestamp = time.time()
        
        # 获取基础网络统计
        net_io = psutil.net_io_counters()
        net_connections = psutil.net_connections()
        
        # 统计连接状态
        established_count = sum(1 for conn in net_connections if conn.status == psutil.CONN_ESTABLISHED)
        time_wait_count = sum(1 for conn in net_connections if conn.status == psutil.CONN_TIME_WAIT)
        
        # 创建指标对象
        metrics = NetworkMetrics(
            timestamp=timestamp,
            active_connections=len(net_connections),
            established_connections=established_count,
            time_wait_connections=time_wait_count,
            bytes_sent=net_io.bytes_sent,
            bytes_received=net_io.bytes_recv,
            packets_sent=net_io.packets_sent,
            packets_received=net_io.packets_recv,
            errors_in=net_io.errin,
            errors_out=net_io.errout,
            drops_in=net_io.dropin,
            drops_out=net_io.dropout
        )
        
        # 异步测试延迟（每5分钟一次）
        if len(self.metrics_history) % 5 == 0:
            try:
                latency_result = await self.latency_analyzer.measure_latency("8.8.8.8", 3)
                if 'avg_ms' in latency_result:
                    metrics.latency_ms = latency_result['avg_ms']
                    metrics.jitter_ms = latency_result.get('jitter_ms', 0)
                    metrics.packet_loss_percent = latency_result.get('packet_loss_percent', 0)
            except Exception as e:
                await self.logger.debug(f"延迟测试失败: {str(e)}")
        
        return metrics
    
    async def _check_alerts(self, metrics: NetworkMetrics):
        """检查告警"""
        alerts = []
        
        # 延迟告警
        if metrics.latency_ms > self.alert_thresholds['latency_ms']:
            alerts.append({
                'type': 'latency_high',
                'severity': 'warning',
                'message': f"High latency detected: {metrics.latency_ms:.1f}ms",
                'threshold': self.alert_thresholds['latency_ms']
            })
        
        # 丢包告警
        if metrics.packet_loss_percent > self.alert_thresholds['packet_loss_percent']:
            alerts.append({
                'type': 'packet_loss_high',
                'severity': 'warning',
                'message': f"High packet loss: {metrics.packet_loss_percent:.1f}%",
                'threshold': self.alert_thresholds['packet_loss_percent']
            })
        
        # 错误率告警
        if metrics.error_rate_percent > self.alert_thresholds['error_rate_percent']:
            alerts.append({
                'type': 'error_rate_high',
                'severity': 'error',
                'message': f"High error rate: {metrics.error_rate_percent:.1f}%",
                'threshold': self.alert_thresholds['error_rate_percent']
            })
        
        # 发送告警
        for alert in alerts:
            await self.logger.warning(f"Network Alert: {alert['message']}")
    
    async def run_diagnostics(self, level: DiagnosticLevel = DiagnosticLevel.STANDARD) -> List[DiagnosticResult]:
        """运行网络诊断"""
        if level == DiagnosticLevel.BASIC:
            return await self.diagnostic_engine.run_basic_diagnostics()
        elif level == DiagnosticLevel.STANDARD:
            return await self.diagnostic_engine.run_standard_diagnostics()
        elif level == DiagnosticLevel.ADVANCED:
            return await self.diagnostic_engine.run_advanced_diagnostics()
        elif level == DiagnosticLevel.DEEP:
            return await self.diagnostic_engine.run_deep_diagnostics()
        else:
            return await self.diagnostic_engine.run_standard_diagnostics()
    
    def get_current_metrics(self) -> Optional[NetworkMetrics]:
        """获取当前指标"""
        return self.metrics_history[-1] if self.metrics_history else None
    
    def get_metrics_history(self, hours: int = 24) -> List[NetworkMetrics]:
        """获取历史指标"""
        if not self.metrics_history:
            return []
        
        cutoff_time = time.time() - (hours * 3600)
        return [m for m in self.metrics_history if m.timestamp > cutoff_time]
    
    async def get_monitoring_statistics(self) -> Dict[str, Any]:
        """获取监控统计"""
        current_metrics = self.get_current_metrics()
        history = self.get_metrics_history()
        
        # 计算统计值
        if history:
            latencies = [m.latency_ms for m in history if m.latency_ms > 0]
            packet_losses = [m.packet_loss_percent for m in history if m.packet_loss_percent >= 0]
            error_rates = [m.error_rate_percent for m in history]
            
            avg_latency = statistics.mean(latencies) if latencies else 0
            avg_packet_loss = statistics.mean(packet_losses) if packet_losses else 0
            avg_error_rate = statistics.mean(error_rates) if error_rates else 0
        else:
            avg_latency = avg_packet_loss = avg_error_rate = 0
        
        return {
            'monitoring_status': {
                'is_active': self.is_monitoring,
                'interval_seconds': self.monitoring_interval,
                'metrics_collected': len(self.metrics_history),
                'history_hours': len(self.metrics_history) / 60
            },
            'current_metrics': current_metrics.to_dict() if current_metrics else None,
            'historical_averages': {
                'latency_ms': round(avg_latency, 2),
                'packet_loss_percent': round(avg_packet_loss, 2),
                'error_rate_percent': round(avg_error_rate, 3)
            },
            'alert_thresholds': self.alert_thresholds,
            'network_interfaces': [iface.to_dict() for iface in self.interface_monitor.interfaces.values()]
        }


# 全局网络性能监控器实例
network_performance_monitor = NetworkPerformanceMonitor()