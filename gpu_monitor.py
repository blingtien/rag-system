#!/usr/bin/env python3
"""
GPU Monitor Tool for RAG Document Processing
Real-time GPU monitoring with colored terminal output and CSV logging
"""

import os
import sys
import time
import signal
import csv
import argparse
from datetime import datetime
from collections import defaultdict
import threading

try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False
    
try:
    import GPUtil
    HAS_GPUTIL = True
except ImportError:
    HAS_GPUTIL = False

import psutil
import colorama
from colorama import Fore, Back, Style, init

# Initialize colorama for cross-platform colored output
init(autoreset=True)

class GPUMonitor:
    def __init__(self, save_csv=False, csv_filename=None, update_interval=1.0):
        self.save_csv = save_csv
        self.update_interval = update_interval
        self.running = True
        self.csv_file = None
        self.csv_writer = None
        
        # Initialize NVIDIA ML
        self.nvml_available = False
        if HAS_PYNVML:
            try:
                pynvml.nvmlInit()
                self.device_count = pynvml.nvmlDeviceGetCount()
                self.nvml_available = True
                print(f"{Fore.GREEN}✓ NVIDIA ML initialized successfully")
                print(f"{Fore.GREEN}✓ Found {self.device_count} GPU(s)")
            except Exception as e:
                print(f"{Fore.RED}✗ Failed to initialize NVIDIA ML: {e}")
        
        # Fallback to GPUtil
        self.gputil_available = False
        if not self.nvml_available and HAS_GPUTIL:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    self.gputil_available = True
                    self.device_count = len(gpus)
                    print(f"{Fore.YELLOW}⚠ Using GPUtil as fallback")
                    print(f"{Fore.YELLOW}⚠ Found {self.device_count} GPU(s)")
            except Exception as e:
                print(f"{Fore.RED}✗ GPUtil also failed: {e}")
        
        if not self.nvml_available and not self.gputil_available:
            print(f"{Fore.RED}✗ No GPU monitoring libraries available!")
            sys.exit(1)
        
        # Setup CSV logging if requested
        if self.save_csv:
            if csv_filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                csv_filename = f"gpu_monitor_{timestamp}.csv"
            
            self.csv_filename = csv_filename
            self.csv_file = open(csv_filename, 'w', newline='')
            
            # CSV headers
            headers = ['timestamp', 'gpu_id', 'gpu_name', 'utilization_%', 
                      'memory_used_mb', 'memory_total_mb', 'memory_util_%',
                      'temperature_c', 'power_w', 'python_processes']
            
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=headers)
            self.csv_writer.writeheader()
            self.csv_file.flush()
            
            print(f"{Fore.GREEN}✓ CSV logging enabled: {csv_filename}")
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n{Fore.YELLOW}Received shutdown signal. Cleaning up...")
        self.running = False
        
    def get_gpu_info_pynvml(self):
        """Get GPU information using pynvml"""
        gpu_data = []
        
        for i in range(self.device_count):
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                
                # Basic info
                name_raw = pynvml.nvmlDeviceGetName(handle)
                name = name_raw.decode('utf-8') if isinstance(name_raw, bytes) else str(name_raw)
                
                # Utilization
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_util = util.gpu
                memory_util = util.memory
                
                # Memory info
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                mem_total = mem_info.total // (1024 * 1024)  # MB
                mem_used = mem_info.used // (1024 * 1024)   # MB
                mem_free = mem_info.free // (1024 * 1024)   # MB
                mem_percent = (mem_used / mem_total) * 100
                
                # Temperature
                try:
                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                except:
                    temp = None
                
                # Power
                try:
                    power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert mW to W
                except:
                    power = None
                
                gpu_data.append({
                    'id': i,
                    'name': name,
                    'utilization': gpu_util,
                    'memory_utilization': memory_util,
                    'memory_used': mem_used,
                    'memory_total': mem_total,
                    'memory_free': mem_free,
                    'memory_percent': mem_percent,
                    'temperature': temp,
                    'power': power
                })
                
            except Exception as e:
                print(f"{Fore.RED}Error getting info for GPU {i}: {e}")
                
        return gpu_data
    
    def get_gpu_info_gputil(self):
        """Get GPU information using GPUtil (fallback)"""
        gpu_data = []
        
        try:
            gpus = GPUtil.getGPUs()
            for i, gpu in enumerate(gpus):
                gpu_data.append({
                    'id': i,
                    'name': gpu.name,
                    'utilization': gpu.load * 100,
                    'memory_utilization': gpu.memoryUtil * 100,
                    'memory_used': gpu.memoryUsed,
                    'memory_total': gpu.memoryTotal,
                    'memory_free': gpu.memoryFree,
                    'memory_percent': gpu.memoryUtil * 100,
                    'temperature': gpu.temperature,
                    'power': None  # GPUtil doesn't provide power info
                })
        except Exception as e:
            print(f"{Fore.RED}Error with GPUtil: {e}")
            
        return gpu_data
    
    def get_python_gpu_processes(self):
        """Get Python processes using GPU"""
        gpu_processes = defaultdict(list)
        
        try:
            if self.nvml_available:
                for i in range(self.device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    try:
                        procs = pynvml.nvmlDeviceGetRunningProcesses(handle)
                        for proc_info in procs:
                            try:
                                proc = psutil.Process(proc_info.pid)
                                if 'python' in proc.name().lower():
                                    gpu_processes[i].append({
                                        'pid': proc_info.pid,
                                        'name': proc.name(),
                                        'cmdline': ' '.join(proc.cmdline()),
                                        'memory_mb': proc_info.usedGpuMemory // (1024 * 1024)
                                    })
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                continue
                    except Exception:
                        continue
        except Exception as e:
            print(f"{Fore.RED}Error getting GPU processes: {e}")
            
        return gpu_processes
    
    def get_status_color(self, value, thresholds):
        """Get color based on value and thresholds [low, medium, high]"""
        if value < thresholds[0]:
            return Fore.GREEN
        elif value < thresholds[1]:
            return Fore.YELLOW
        else:
            return Fore.RED
    
    def format_bytes(self, bytes_val):
        """Format bytes to human readable format"""
        if bytes_val is None:
            return "N/A"
        
        for unit in ['MB', 'GB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} TB"
    
    def display_gpu_info(self, gpu_data, python_processes):
        """Display GPU information in colored terminal"""
        # Clear screen
        os.system('clear' if os.name == 'posix' else 'cls')
        
        # Header
        print(f"{Style.BRIGHT}{Fore.CYAN}{'=' * 80}")
        print(f"{Style.BRIGHT}{Fore.CYAN}GPU MONITOR - RAG Document Processing")
        print(f"{Style.BRIGHT}{Fore.CYAN}{'=' * 80}")
        print(f"{Fore.WHITE}Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        for gpu_info in gpu_data:
            gpu_id = gpu_info['id']
            
            # GPU header
            print(f"{Style.BRIGHT}{Fore.MAGENTA}GPU {gpu_id}: {gpu_info['name']}")
            print(f"{Style.BRIGHT}{Fore.MAGENTA}{'-' * 50}")
            
            # Utilization
            util_color = self.get_status_color(gpu_info['utilization'], [20, 70])
            print(f"{util_color}GPU Utilization:    {gpu_info['utilization']:6.1f}%")
            
            # Memory
            mem_color = self.get_status_color(gpu_info['memory_percent'], [50, 85])
            print(f"{mem_color}Memory Usage:      {gpu_info['memory_used']:6.0f} MB / {gpu_info['memory_total']:6.0f} MB ({gpu_info['memory_percent']:5.1f}%)")
            print(f"{Fore.WHITE}Memory Free:       {gpu_info['memory_free']:6.0f} MB")
            
            # Temperature
            if gpu_info['temperature'] is not None:
                temp_color = self.get_status_color(gpu_info['temperature'], [60, 80])
                print(f"{temp_color}Temperature:       {gpu_info['temperature']:6.0f}°C")
            else:
                print(f"{Fore.WHITE}Temperature:       N/A")
            
            # Power
            if gpu_info['power'] is not None:
                power_color = self.get_status_color(gpu_info['power'], [100, 200])
                print(f"{power_color}Power Usage:       {gpu_info['power']:6.1f} W")
            else:
                print(f"{Fore.WHITE}Power Usage:       N/A")
            
            # Python processes
            if gpu_id in python_processes and python_processes[gpu_id]:
                print(f"\n{Fore.CYAN}Python Processes:")
                for proc in python_processes[gpu_id]:
                    print(f"{Fore.WHITE}  PID {proc['pid']}: {proc['name']} ({proc['memory_mb']} MB GPU mem)")
                    # Truncate long command lines
                    cmd = proc['cmdline']
                    if len(cmd) > 60:
                        cmd = cmd[:57] + "..."
                    print(f"{Fore.LIGHTBLACK_EX}    {cmd}")
            else:
                print(f"\n{Fore.LIGHTBLACK_EX}No Python processes using GPU")
            
            print()
        
        # Footer
        print(f"{Fore.LIGHTBLACK_EX}Press Ctrl+C to stop monitoring...")
        if self.save_csv:
            print(f"{Fore.LIGHTBLACK_EX}Logging to: {self.csv_filename}")
    
    def log_to_csv(self, gpu_data, python_processes):
        """Log data to CSV file"""
        if not self.csv_writer:
            return
        
        timestamp = datetime.now().isoformat()
        
        for gpu_info in gpu_data:
            gpu_id = gpu_info['id']
            
            # Format Python processes info
            proc_info = []
            if gpu_id in python_processes:
                for proc in python_processes[gpu_id]:
                    proc_info.append(f"PID{proc['pid']}:{proc['name']}")
            proc_str = ';'.join(proc_info) if proc_info else ''
            
            row = {
                'timestamp': timestamp,
                'gpu_id': gpu_id,
                'gpu_name': gpu_info['name'],
                'utilization_%': gpu_info['utilization'],
                'memory_used_mb': gpu_info['memory_used'],
                'memory_total_mb': gpu_info['memory_total'],
                'memory_util_%': gpu_info['memory_percent'],
                'temperature_c': gpu_info['temperature'] if gpu_info['temperature'] is not None else '',
                'power_w': gpu_info['power'] if gpu_info['power'] is not None else '',
                'python_processes': proc_str
            }
            
            self.csv_writer.writerow(row)
        
        self.csv_file.flush()
    
    def run(self):
        """Main monitoring loop"""
        print(f"{Fore.GREEN}Starting GPU monitoring...")
        print(f"{Fore.GREEN}Update interval: {self.update_interval}s")
        print()
        
        try:
            while self.running:
                # Get GPU data
                if self.nvml_available:
                    gpu_data = self.get_gpu_info_pynvml()
                else:
                    gpu_data = self.get_gpu_info_gputil()
                
                # Get Python processes
                python_processes = self.get_python_gpu_processes()
                
                # Display information
                self.display_gpu_info(gpu_data, python_processes)
                
                # Log to CSV if enabled
                if self.save_csv:
                    self.log_to_csv(gpu_data, python_processes)
                
                # Wait for next update
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Monitoring stopped by user.")
        except Exception as e:
            print(f"\n{Fore.RED}Error in monitoring loop: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        if self.csv_file:
            self.csv_file.close()
            print(f"{Fore.GREEN}CSV file saved: {self.csv_filename}")
        
        if self.nvml_available:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
        
        print(f"{Fore.GREEN}GPU monitor stopped.")

def main():
    parser = argparse.ArgumentParser(description='Real-time GPU Monitor for RAG Document Processing')
    parser.add_argument('--csv', '-c', action='store_true', 
                       help='Save monitoring data to CSV file')
    parser.add_argument('--csv-file', '-f', type=str, 
                       help='CSV filename (default: auto-generated with timestamp)')
    parser.add_argument('--interval', '-i', type=float, default=1.0,
                       help='Update interval in seconds (default: 1.0)')
    
    args = parser.parse_args()
    
    print(f"{Style.BRIGHT}{Fore.CYAN}GPU Monitor for RAG Document Processing")
    print(f"{Style.BRIGHT}{Fore.CYAN}{'=' * 50}")
    
    # Create and run monitor
    monitor = GPUMonitor(
        save_csv=args.csv,
        csv_filename=args.csv_file,
        update_interval=args.interval
    )
    
    monitor.run()

if __name__ == "__main__":
    main()