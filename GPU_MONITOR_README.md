# GPU Monitor Tool

专为RAG文档解析过程设计的实时GPU监控工具。

## 功能特性

✅ **实时监控指标**
- GPU使用率（百分比）
- 显存使用量/总量/占用率
- GPU温度（摄氏度）
- GPU功耗（瓦特）
- Python进程GPU使用情况

✅ **彩色终端输出**
- 绿色：低使用率（正常）
- 黄色：中等使用率（注意）
- 红色：高使用率（警告）

✅ **CSV数据记录**
- 可选的历史数据记录
- 自动时间戳文件命名
- 完整监控数据导出

✅ **智能进程监控**
- 自动识别Python进程
- 显示进程ID、名称和GPU内存使用
- 显示进程命令行（截断长命令）

## 系统要求

- Linux系统（已在WSL2上测试）
- NVIDIA GPU + CUDA驱动
- Python 3.10+
- 已安装必要依赖：`pynvml`, `colorama`, `GPUtil`, `psutil`

## 安装依赖

依赖已自动安装完成：
```bash
pip install pynvml colorama GPUtil psutil
```

## 使用方法

### 基本监控（推荐）
```bash
python gpu_monitor.py
```

### 带CSV记录的监控
```bash
# 自动生成CSV文件名
python gpu_monitor.py --csv

# 指定CSV文件名
python gpu_monitor.py --csv --csv-file my_monitoring.csv
```

### 自定义更新间隔
```bash
# 每0.5秒更新一次（更频繁）
python gpu_monitor.py --interval 0.5

# 每2秒更新一次（较缓慢）
python gpu_monitor.py --interval 2
```

### 组合参数
```bash
# CSV记录 + 0.5秒间隔
python gpu_monitor.py --csv --interval 0.5 --csv-file rag_parsing_monitor.csv
```

## 输出说明

### 终端显示
```
================================================================================
GPU MONITOR - RAG Document Processing
================================================================================
Time: 2025-08-23 10:14:58

GPU 0: NVIDIA GeForce RTX 2060 SUPER
--------------------------------------------------
GPU Utilization:       9.0%      ← GPU计算使用率
Memory Usage:        1473 MB /   8192 MB ( 18.0%)  ← 显存使用情况
Memory Free:         6718 MB     ← 可用显存
Temperature:           45°C       ← GPU温度
Power Usage:         13.1 W      ← 功耗

Python Processes:                 ← 相关Python进程
  PID 12345: python (256 MB GPU mem)
    python rag_parser.py document.pdf
```

### CSV记录格式
| 字段 | 说明 |
|------|------|
| timestamp | ISO格式时间戳 |
| gpu_id | GPU设备ID |
| gpu_name | GPU型号名称 |
| utilization_% | GPU使用率百分比 |
| memory_used_mb | 已用显存（MB） |
| memory_total_mb | 总显存（MB） |
| memory_util_% | 显存使用率百分比 |
| temperature_c | GPU温度（摄氏度） |
| power_w | 功耗（瓦特） |
| python_processes | Python进程列表 |

## 颜色含义

| 颜色 | GPU使用率 | 显存使用率 | 温度 | 功耗 | 含义 |
|------|-----------|-----------|------|------|------|
| 🟢 绿色 | < 20% | < 50% | < 60°C | < 100W | 正常 |
| 🟡 黄色 | 20-70% | 50-85% | 60-80°C | 100-200W | 注意 |
| 🔴 红色 | > 70% | > 85% | > 80°C | > 200W | 警告 |

## 使用场景

### 1. RAG文档解析监控
```bash
# 在一个终端启动监控
python gpu_monitor.py --csv --csv-file rag_parsing.csv

# 在另一个终端运行文档解析
python -m raganything.process_document document.pdf
```

### 2. 批量处理监控
```bash
# 启动监控
python gpu_monitor.py --csv --interval 0.5

# 运行批量处理
python -m raganything.batch_parser /path/to/documents/ --workers 4
```

### 3. 性能调优
```bash
# 高频监控用于性能分析
python gpu_monitor.py --csv --interval 0.2 --csv-file performance_analysis.csv
```

## 故障排除

### 1. 权限问题
如果出现权限错误：
```bash
sudo usermod -a -G video $USER
# 重新登录后生效
```

### 2. 库依赖问题
重新安装依赖：
```bash
pip install --force-reinstall pynvml colorama GPUtil psutil
```

### 3. GPU驱动问题
检查NVIDIA驱动：
```bash
nvidia-smi
```

### 4. WSL2特殊问题
确保WSL2支持NVIDIA GPU：
```bash
# 检查CUDA是否可用
python -c "import torch; print(torch.cuda.is_available())"
```

## 停止监控

- 按 `Ctrl+C` 优雅停止
- 自动保存CSV文件（如果启用）
- 清理资源并退出

## 性能影响

- 监控工具本身占用极少GPU资源（< 1%）
- 建议在不同终端窗口运行监控和处理任务
- CSV记录对性能影响可忽略不计

## 技术架构

- **主要库**：pynvml（NVIDIA官方库）
- **备用库**：GPUtil（兼容性备选）
- **进程监控**：psutil
- **彩色输出**：colorama
- **数据记录**：Python CSV模块

监控工具已完成并可立即使用！🚀