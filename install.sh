#!/usr/bin/env bash

# ==============================================================================
# Claude Code 自动安装配置脚本 - 增强版
# 支持更多系统，包括 Windows WSL
# ==============================================================================

# 脚本常量
readonly CLAUDE_COMMAND="claude"
readonly NPM_PACKAGE="@anthropic-ai/claude-code"
readonly CLAUDE_CONFIG_FILE="$HOME/.claude.json"
readonly CLAUDE_DIR="$HOME/.claude"

# API 配置 - 默认值
API_KEY=""
API_BASE_URL="https://api5.ai"

# ANSI 颜色代码
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly WHITE='\033[1;37m'
readonly NC='\033[0m' # No Color

# 显示彩色消息
print_info() {
    echo -e "${WHITE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检测操作系统和环境
detect_environment() {
    local os_type=""
    local is_wsl=false
    
    # 检测 WSL
    if grep -qEi "(Microsoft|WSL)" /proc/version 2>/dev/null; then
        is_wsl=true
        os_type="wsl"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        os_type="macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        os_type="linux"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        os_type="windows_bash"
        # 在Windows环境下，提供PowerShell脚本选项
        print_warning "检测到 Windows Git Bash/MSYS 环境"
        print_info "推荐使用 Windows PowerShell 版本以获得更好的体验"
        echo
        read -p "是否下载并运行 PowerShell 版本? (Y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # 下载PowerShell脚本
            print_info "正在下载 PowerShell 安装脚本..."
            local ps_script="install-claude-code.ps1"
            if command -v curl &> /dev/null; then
                curl -sSL "https://1.api5.ai/install-claude-code.ps1" -o "$ps_script"
            elif command -v wget &> /dev/null; then
                wget -q "https://1.api5.ai/install-claude-code.ps1" -O "$ps_script"
            else
                print_error "需要 curl 或 wget 来下载脚本"
                return 1
            fi
            
            print_success "PowerShell 脚本已下载: $ps_script"
            print_info "请在 PowerShell 中运行以下命令："
            echo
            echo "  powershell.exe -ExecutionPolicy Bypass -File $ps_script"
            echo
            print_info "或者在 Windows 资源管理器中右键点击脚本选择'使用 PowerShell 运行'"
            exit 0
        fi
    else
        os_type="unknown"
    fi
    
    echo "$os_type"
}

# 检测 Linux 发行版
detect_linux_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    elif [ -f /etc/redhat-release ]; then
        echo "rhel"
    elif [ -f /etc/debian_version ]; then
        echo "debian"
    else
        echo "unknown"
    fi
}

# 检查是否有 sudo 权限
check_sudo() {
    if command -v sudo &> /dev/null; then
        if sudo -n true 2>/dev/null; then
            return 0
        else
            print_warning "需要 sudo 权限来安装依赖包"
            sudo -v
            return $?
        fi
    else
        # 没有 sudo，检查是否是 root
        if [ "$EUID" -eq 0 ]; then
            return 0
        else
            print_error "需要 root 权限或 sudo 来安装依赖包"
            return 1
        fi
    fi
}

# 安装 Node.js (通用方法)
install_nodejs_universal() {
    print_info "使用 NodeSource 安装 Node.js..."
    
    # 检测架构
    local arch=$(uname -m)
    local node_version="20"  # LTS 版本
    
    # NodeSource 安装脚本
    if command -v curl &> /dev/null; then
        curl -fsSL https://deb.nodesource.com/setup_${node_version}.x | sudo -E bash -
    elif command -v wget &> /dev/null; then
        wget -qO- https://deb.nodesource.com/setup_${node_version}.x | sudo -E bash -
    else
        print_error "需要 curl 或 wget 来下载 Node.js"
        return 1
    fi
}

# WSL 特定的安装函数
install_wsl_packages() {
    print_info "检测到 Windows WSL 环境"
    
    # WSL 可能需要更新包列表
    if command -v apt-get &> /dev/null; then
        print_info "更新包管理器..."
        sudo apt-get update -qq
    fi
    
    # 安装基础工具
    local packages=("curl" "wget" "jq" "python3" "python3-pip")
    
    for pkg in "${packages[@]}"; do
        if ! command -v "$pkg" &> /dev/null; then
            print_info "安装 $pkg..."
            sudo apt-get install -y "$pkg" || print_warning "无法安装 $pkg"
        fi
    done
    
    # 安装 Node.js
    if ! command -v node &> /dev/null; then
        install_nodejs_universal
        sudo apt-get install -y nodejs
    fi
}

# 安装 Homebrew (macOS)
install_homebrew() {
    if ! command -v brew &> /dev/null; then
        print_info "安装 Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # 添加 Homebrew 到 PATH
        if [[ -f "/opt/homebrew/bin/brew" ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [[ -f "/usr/local/bin/brew" ]]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
        
        print_success "Homebrew 安装完成"
    fi
}

# macOS 安装函数
install_macos_packages() {
    install_homebrew
    
    local packages=("node" "jq" "python3")
    
    for pkg in "${packages[@]}"; do
        if ! command -v "$pkg" &> /dev/null; then
            print_info "安装 $pkg..."
            brew install "$pkg"
        fi
    done
}

# Linux 通用安装函数
install_linux_packages() {
    local distro=$(detect_linux_distro)
    print_info "检测到 Linux 发行版: $distro"
    
    case "$distro" in
        ubuntu|debian|linuxmint|pop)
            sudo apt-get update -qq
            local packages=("nodejs" "npm" "jq" "python3" "python3-pip" "curl" "wget")
            
            # 先安装 Node.js 仓库
            if ! command -v node &> /dev/null; then
                install_nodejs_universal
            fi
            
            for pkg in "${packages[@]}"; do
                if ! command -v "${pkg%%[0-9]*}" &> /dev/null; then
                    sudo apt-get install -y "$pkg"
                fi
            done
            ;;
            
        fedora|rhel|centos|rocky|almalinux)
            sudo yum install -y epel-release 2>/dev/null || true
            local packages=("nodejs" "npm" "jq" "python3" "python3-pip" "curl" "wget")
            
            for pkg in "${packages[@]}"; do
                if ! command -v "${pkg%%[0-9]*}" &> /dev/null; then
                    sudo yum install -y "$pkg"
                fi
            done
            ;;
            
        arch|manjaro)
            sudo pacman -Sy --noconfirm
            local packages=("nodejs" "npm" "jq" "python" "python-pip" "curl" "wget")
            
            for pkg in "${packages[@]}"; do
                if ! command -v "${pkg%%[0-9]*}" &> /dev/null; then
                    sudo pacman -S --noconfirm "$pkg"
                fi
            done
            ;;
            
        opensuse*)
            sudo zypper refresh
            local packages=("nodejs" "npm" "jq" "python3" "python3-pip" "curl" "wget")
            
            for pkg in "${packages[@]}"; do
                if ! command -v "${pkg%%[0-9]*}" &> /dev/null; then
                    sudo zypper install -y "$pkg"
                fi
            done
            ;;
            
        *)
            print_warning "未知的 Linux 发行版: $distro"
            print_info "尝试通用安装方法..."
            
            # 尝试使用可用的包管理器
            if command -v apt-get &> /dev/null; then
                sudo apt-get update && sudo apt-get install -y nodejs npm jq python3
            elif command -v yum &> /dev/null; then
                sudo yum install -y nodejs npm jq python3
            elif command -v pacman &> /dev/null; then
                sudo pacman -S --noconfirm nodejs npm jq python
            else
                print_error "无法自动安装依赖，请手动安装: nodejs, npm, jq, python3"
                return 1
            fi
            ;;
    esac
}

# ========================================
# Claude CLI 检测和修复功能
# ========================================

# 检测 Claude CLI 安装情况
detect_claude_installation() {
    # 检查是否安装了 Claude CLI
    if ! command -v claude &> /dev/null; then
        return 1  # 未安装
    fi
    
    # 获取 Claude CLI 的实际路径
    CLAUDE_PATH=$(which claude 2>/dev/null)
    
    if [ -z "$CLAUDE_PATH" ]; then
        return 1
    fi
    
    print_info "当前 Claude CLI 路径: $CLAUDE_PATH"
    
    # 获取 Claude CLI 版本信息
    # 使用 timeout 防止命令卡住
    if command -v timeout &> /dev/null; then
        CLAUDE_VERSION=$(timeout 5 claude --version 2>/dev/null || echo "未知版本")
    else
        # macOS 可能没有 timeout，使用其他方法
        CLAUDE_VERSION=$(claude --version 2>/dev/null || echo "未知版本") &
        VERSION_PID=$!
        sleep 5
        if kill -0 $VERSION_PID 2>/dev/null; then
            kill $VERSION_PID 2>/dev/null
            CLAUDE_VERSION="未知版本"
        else
            wait $VERSION_PID
        fi
    fi
    print_info "Claude CLI 版本: $CLAUDE_VERSION"
    
    # 检查安装方式
    if [[ "$CLAUDE_PATH" == *"/.nvm/versions/node/"* ]]; then
        print_warning "检测到通过 nvm npm 安装"
        return 0  # nvm 安装（需要修复）
    elif [[ "$CLAUDE_PATH" == *"/opt/homebrew/bin/"* ]] || [[ "$CLAUDE_PATH" == *"/usr/local/bin/"* ]]; then
        print_success "检测到通过 Homebrew npm 安装"
        return 2  # Homebrew 安装（正常）
    elif [[ "$CLAUDE_PATH" == *"/.local/bin/"* ]]; then
        print_success "检测到原生安装"
        return 3  # 原生安装（正常）
    else
        print_warning "未知安装方式: $CLAUDE_PATH"
        return 4  # 未知安装方式
    fi
}

# 检查 npm 全局包中是否有 Claude CLI
check_npm_claude() {
    # 检查当前 npm 是否安装了 Claude CLI
    if npm list -g @anthropic-ai/claude-code &> /dev/null; then
        NPM_PATH=$(npm root -g 2>/dev/null)
        print_info "检测到 npm 全局包: $NPM_PATH/@anthropic-ai/claude-code"
        
        # 检查是否是 nvm 管理的 npm
        if [[ "$NPM_PATH" == *"/.nvm/versions/node/"* ]]; then
            print_warning "通过 nvm npm 安装"
            return 0  # nvm npm 安装
        else
            print_success "通过系统 npm 安装"
            return 1  # 系统 npm 安装
        fi
    else
        return 2  # npm 中未安装
    fi
}

# 检测 nvm 环境
detect_nvm_env() {
    # 检查 nvm 是否存在
    if [ -d "$HOME/.nvm" ] || command -v nvm &> /dev/null; then
        print_info "检测到 nvm 环境"
        
        # 检查当前使用的 Node.js 版本
        if command -v node &> /dev/null; then
            NODE_PATH=$(which node)
            print_info "当前 Node.js 路径: $NODE_PATH"
            
            if [[ "$NODE_PATH" == *"/.nvm/versions/node/"* ]]; then
                NODE_VERSION=$(node --version 2>/dev/null)
                print_info "当前 Node.js 版本: $NODE_VERSION"
                return 0
            fi
        fi
    fi
    return 1
}

# 备份 Claude CLI 配置文件
backup_claude_configs() {
    print_info "备份 Claude CLI 配置文件..."
    
    # 创建备份目录
    local backup_dir="$HOME/.claude-backup-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    print_info "备份目录: $backup_dir"
    
    local backup_success=true
    local files_backed_up=0
    
    # 定义要备份的配置文件路径
    local config_files=(
        "$HOME/.claude/settings.json"
        "$HOME/.claude/claude.json"
        ".claude/settings.json"
        ".claude/settings.local.json"
        ".claude/claude.json"
        "claude.json"
        "配置.json"
    )
    
    # 备份用户级配置
    if [ -d "$HOME/.claude" ]; then
        print_info "备份用户级配置目录..."
        if cp -r "$HOME/.claude" "$backup_dir/user-claude-config" 2>/dev/null; then
            print_success "已备份: ~/.claude/ → $backup_dir/user-claude-config/"
            ((files_backed_up++))
        fi
    fi
    
    # 备份项目级配置
    if [ -d ".claude" ]; then
        print_info "备份项目级配置目录..."
        if cp -r ".claude" "$backup_dir/project-claude-config" 2>/dev/null; then
            print_success "已备份: .claude/ → $backup_dir/project-claude-config/"
            ((files_backed_up++))
        fi
    fi
    
    # 备份当前目录下的配置文件
    for config_file in "${config_files[@]}"; do
        if [ -f "$config_file" ]; then
            local backup_name=$(basename "$config_file")
            local source_dir=$(dirname "$config_file")
            
            # 创建相应的备份子目录
            local backup_subdir="$backup_dir/configs"
            if [[ "$source_dir" == "$HOME/.claude" ]]; then
                backup_subdir="$backup_dir/user-configs"
            elif [[ "$source_dir" == ".claude" ]]; then
                backup_subdir="$backup_dir/project-configs"
            fi
            
            mkdir -p "$backup_subdir"
            
            if cp "$config_file" "$backup_subdir/$backup_name" 2>/dev/null; then
                print_success "已备份: $config_file → $backup_subdir/$backup_name"
                ((files_backed_up++))
            fi
        fi
    done
    
    # 备份结果总结
    if [ $files_backed_up -gt 0 ]; then
        print_success "备份完成: $files_backed_up 个文件已备份到 $backup_dir"
        
        # 创建备份说明文件
        cat > "$backup_dir/backup-info.txt" << EOF
Claude CLI 配置备份
==================
备份时间: $(date)
备份原因: Claude CLI 重新安装前的配置备份
原始路径: $(pwd)

备份内容:
- user-claude-config/: ~/.claude/ 目录内容
- project-claude-config/: .claude/ 目录内容  
- user-configs/: ~/.claude/ 下的配置文件
- project-configs/: .claude/ 下的配置文件
- configs/: 当前目录下的配置文件

恢复方法:
1. 重新安装 Claude CLI 后
2. 将相应配置文件复制回原位置
3. 重启终端或运行 'source ~/.bashrc' / 'source ~/.zshrc'
EOF
        
        return 0
    else
        print_info "未找到需要备份的配置文件"
        # 删除空的备份目录
        rmdir "$backup_dir" 2>/dev/null
        return 1
    fi
}

# 完全清理 Claude CLI
complete_cleanup_claude() {
    print_info "正在完全清理 Claude CLI..."
    
    # 先备份配置文件
    backup_claude_configs
    
    local cleanup_success=true
    
    # 1. 尝试通过 npm 卸载
    print_info "检查并卸载 npm 全局包..."
    if npm list -g @anthropic-ai/claude-code &> /dev/null; then
        if npm uninstall -g @anthropic-ai/claude-code; then
            print_success "成功卸载 npm 全局包"
        else
            print_error "npm 卸载失败"
            cleanup_success=false
        fi
    else
        print_info "npm 全局包中未找到 Claude CLI"
    fi
    
    # 2. 检查并清理可能的符号链接
    print_info "检查符号链接..."
    local possible_paths=(
        "/usr/local/bin/claude"
        "/opt/homebrew/bin/claude"
        "$HOME/.local/bin/claude"
    )
    
    for path in "${possible_paths[@]}"; do
        if [ -L "$path" ] || [ -f "$path" ]; then
            print_info "删除: $path"
            if rm -f "$path" 2>/dev/null; then
                print_success "已删除: $path"
            fi
        fi
    done
    
    # 3. 验证清理结果
    print_info "验证清理结果..."
    if command -v claude &> /dev/null; then
        REMAINING_PATH=$(which claude 2>/dev/null)
        print_warning "仍然检测到 Claude CLI: $REMAINING_PATH"
        cleanup_success=false
    else
        print_success "Claude CLI 已完全清理"
    fi
    
    if [ "$cleanup_success" = true ]; then
        print_success "清理完成，配置文件已备份，可以安全重新安装"
        return 0
    else
        print_error "清理不完全，可能需要手动处理"
        return 1
    fi
}

# 检测 Homebrew
check_homebrew() {
    if command -v brew &> /dev/null; then
        print_success "检测到 Homebrew"
        return 0
    else
        print_error "未检测到 Homebrew"
        return 1
    fi
}

# 安装 Homebrew Node.js（与 nvm 并存）
install_homebrew_node() {
    print_info "正在通过 Homebrew 安装 Node.js（与 nvm 并存）..."
    print_info "这不会影响你现有的 nvm 环境"
    
    if brew install node; then
        print_success "Homebrew Node.js 安装成功"
        
        # 临时调整 PATH 确保使用 Homebrew 版本
        export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
        
        NODE_PATH=$(which node)
        print_info "Node.js 路径: $NODE_PATH"
        
        print_info "将在 shell 配置中设置 PATH 优先级..."
        setup_path_priority
        
        return 0
    else
        print_error "Homebrew Node.js 安装失败"
        return 1
    fi
}

# 设置 PATH 优先级
setup_path_priority() {
    local shell_config=""
    
    # 检测当前 shell
    if [[ "$SHELL" == *"zsh"* ]]; then
        shell_config="$HOME/.zshrc"
    elif [[ "$SHELL" == *"bash"* ]]; then
        shell_config="$HOME/.bashrc"
    else
        print_warning "无法检测 shell 类型，请手动配置 PATH"
        return 1
    fi
    
    # 检查是否已经配置
    if grep -q "# Claude CLI Homebrew Priority" "$shell_config" 2>/dev/null; then
        print_success "PATH 优先级已配置"
        return 0
    fi
    
    # 添加 PATH 配置
    echo "" >> "$shell_config"
    echo "# Claude CLI Homebrew Priority" >> "$shell_config"
    echo "# 确保 Homebrew 路径优先于 nvm，用于全局工具如 Claude CLI" >> "$shell_config"
    echo 'export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"' >> "$shell_config"
    echo "" >> "$shell_config"
    
    print_success "已配置 PATH 优先级到 $shell_config"
    print_info "请运行 'source $shell_config' 或重新打开终端"
}

# 安装 Claude CLI 通过 Homebrew npm
install_claude_via_homebrew() {
    print_info "正在通过 Homebrew npm 安装 Claude CLI..."
    
    if npm install -g @anthropic-ai/claude-code; then
        print_success "Claude CLI 安装成功"
        CLAUDE_PATH=$(which claude)
        print_info "Claude CLI 路径: $CLAUDE_PATH"
        print_info "运行 'claude --version' 验证安装"
        return 0
    else
        print_error "Claude CLI 安装失败"
        return 1
    fi
}

# 检测和修复 Claude CLI 安装问题
detect_and_fix_claude() {
    print_info "检测 Claude CLI 安装环境..."
    
    # 检测 nvm 环境
    if detect_nvm_env; then
        echo ""
    fi
    
    # 检测 Claude CLI 安装情况
    detect_claude_installation
    DETECTION_RESULT=$?
    
    echo ""
    
    case $DETECTION_RESULT in
        0)  # nvm 安装 - 需要修复
            print_warning "问题说明:"
            print_warning "Claude CLI 通过 nvm 管理的 npm 安装"
            print_warning "这会导致 Node.js 版本切换时 Claude CLI 不可用"
            echo ""
            
            # 显示当前环境信息
            print_info "当前环境信息:"
            check_npm_claude
            echo ""
            
            read -p "是否要修复此问题？这将完全卸载当前版本并重新安装 (y/N): " -n 1 -r
            echo
            
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_info "开始修复流程..."
                
                # 完全清理现有安装
                if complete_cleanup_claude; then
                    echo ""
                    print_info "选择新的安装方式:"
                    echo "1) 通过 Homebrew + npm 安装 (推荐，与 nvm 并存)"
                    echo "2) 继续使用当前安装方式"
                    echo ""
                    read -p "请选择 (1-2): " -n 1 -r
                    echo
                    
                    case $REPLY in
                        1)
                            if check_homebrew; then
                                # 检查是否已有 Homebrew Node.js
                                NODE_PATH=$(which node 2>/dev/null)
                                if [[ "$NODE_PATH" == *"/opt/homebrew/bin/node"* ]] || [[ "$NODE_PATH" == *"/usr/local/bin/node"* ]]; then
                                    print_success "检测到 Homebrew Node.js"
                                    install_claude_via_homebrew
                                else
                                    print_info "需要安装 Homebrew Node.js（与 nvm 并存）"
                                    if install_homebrew_node; then
                                        install_claude_via_homebrew
                                    fi
                                fi
                                # 修复完成，直接返回，跳过后续安装
                                return 0
                            else
                                print_error "需要先安装 Homebrew: https://brew.sh"
                                print_info "将继续使用标准安装方式"
                            fi
                            ;;
                        2)
                            print_info "将继续使用标准安装方式"
                            ;;
                        *)
                            print_error "无效选择，将继续使用标准安装方式"
                            ;;
                    esac
                else
                    print_error "清理失败，将继续使用标准安装方式"
                fi
            else
                print_info "跳过修复，将继续使用标准安装方式"
            fi
            ;;
        1)  # 未安装
            print_info "Claude CLI 未安装，将进行安装"
            ;;
        2)  # Homebrew 安装 - 正常
            print_success "Claude CLI 通过 Homebrew npm 安装，配置正常"
            print_success "不受 nvm 版本切换影响"
            return 0  # 跳过后续安装
            ;;
        3)  # 原生安装 - 正常
            print_success "Claude CLI 原生安装，配置正常"
            print_success "独立于 Node.js 环境运行"
            return 0  # 跳过后续安装
            ;;
        4)  # 未知安装方式
            print_warning "检测到未知的 Claude CLI 安装方式"
            print_info "路径: $CLAUDE_PATH"
            print_info "将继续使用标准安装方式"
            ;;
    esac
    
    return 1  # 继续标准安装流程
}

# 安装 Claude Code
install_claude_code() {
    # 首先执行检测和修复功能
    if detect_and_fix_claude; then
        # 如果检测到正常安装或已修复，直接返回
        print_success "Claude CLI 检测完成，跳过安装步骤"
        return 0
    fi
    
    # 清理旧的配置文件
    print_info "检查旧配置文件..."
    
    local found_old_files=false
    
    # 检查是否存在旧配置文件
    if [ -f "$CLAUDE_CONFIG_FILE" ]; then
        found_old_files=true
        print_warning "检测到旧配置文件，建议删除以避免运行错误"
        echo
        echo "发现以下配置文件："
        
        if [ -f "$CLAUDE_CONFIG_FILE" ]; then
            echo "  - $CLAUDE_CONFIG_FILE"
        fi
        
        
        echo
        print_info "不删除旧配置文件可能会导致 Claude Code 运行时报错"
        
        # Display prompt with default value Y
        echo -ne "是否删除这些旧配置文件？[Y/n]: "
        echo -ne "${GREEN}Y${NC}"
        # Move cursor back one position
        echo -ne "\b"
        read -r REPLY
        
        # Default to Y if user just presses Enter
        if [[ -z "$REPLY" ]] || [[ $REPLY =~ ^[Yy]$ ]]; then
            # 删除 ~/.claude.json 文件
            if [ -f "$CLAUDE_CONFIG_FILE" ]; then
                rm -f "$CLAUDE_CONFIG_FILE"
                print_success "已删除 $CLAUDE_CONFIG_FILE"
            fi
            
            
            # 如果 .claude 目录为空，也删除该目录
            if [ -d "$CLAUDE_DIR" ]; then
                if [ -z "$(ls -A "$CLAUDE_DIR")" ]; then
                    rmdir "$CLAUDE_DIR"
                    print_info "已删除空目录 $CLAUDE_DIR"
                fi
            fi
            
            print_success "旧配置文件清理完成"
        else
            print_info "保留旧配置文件"
        fi
    fi
    
    if command -v "$CLAUDE_COMMAND" &> /dev/null; then
        print_info "Claude Code 已安装"
        
        # 获取环境类型
        local env_type=$(detect_environment)
        
        # macOS 和 Linux 系统直接跳过，不询问
        if [[ "$env_type" == "macos" ]] || [[ "$env_type" == "linux" ]] || [[ "$env_type" == "wsl" ]]; then
            print_info "检测到已安装 Claude Code，跳过安装步骤"
            return 0
        fi
        
        # 其他系统（如 Windows Git Bash）仍然询问
        read -p "是否要重新安装 Claude Code? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 0
        fi
        
        print_info "卸载旧版本..."
        npm uninstall -g "$NPM_PACKAGE" 2>/dev/null || true
    fi
    
    print_info "安装 Claude Code..."
    
    # 检查 npm
    if ! command -v npm &> /dev/null; then
        print_error "npm 未安装，无法继续"
        return 1
    fi
    
    # 全局安装
    if npm install -g "$NPM_PACKAGE"; then
        print_success "Claude Code 安装成功"
        
        # 验证安装
        if command -v "$CLAUDE_COMMAND" &> /dev/null; then
            local version=$("$CLAUDE_COMMAND" --version 2>/dev/null || echo "未知版本")
            print_info "已安装版本: $version"
        fi
    else
        print_error "Claude Code 安装失败"
        return 1
    fi
}

# 检测并修复 API key 中错误添加的 ant- 前缀
check_and_fix_api_key() {
    # 同时检查 claude.json 文件（虽然不应该包含 API key，但以防万一）
    if [ -f "$CLAUDE_CONFIG_FILE" ]; then
        # 检查是否错误地存储了 API key
        if grep -q "apiKey" "$CLAUDE_CONFIG_FILE" 2>/dev/null; then
            print_warning "检测到 claude.json 中包含 API key，正在清理..."
            
            # 使用 jq 删除 apiKey 字段
            if command -v jq &> /dev/null; then
                jq 'del(.apiKey)' "$CLAUDE_CONFIG_FILE" > "$CLAUDE_CONFIG_FILE.tmp" && \
                mv "$CLAUDE_CONFIG_FILE.tmp" "$CLAUDE_CONFIG_FILE"
                print_success "已从 claude.json 中移除 API key"
            fi
        fi
    fi
}

# 配置 Claude Code
configure_claude_code() {
    print_info "配置 Claude Code..."
    
    # 获取环境类型
    local env_type=$(detect_environment)
    
    # macOS 系统跳过配置文件创建
    if [[ "$env_type" == "macos" ]]; then
        print_info "macOS 系统：跳过配置文件创建，仅设置环境变量"
    else
        # 非 macOS 系统创建配置文件
        # 创建 .claude 目录
        if [ ! -d "$CLAUDE_DIR" ]; then
            mkdir -p "$CLAUDE_DIR"
        fi
        
        # 备份原配置（如果存在）
        if [ -f "$CLAUDE_CONFIG_FILE" ]; then
            cp "$CLAUDE_CONFIG_FILE" "$CLAUDE_CONFIG_FILE.backup"
            print_info "原配置已备份为 .claude.json.backup"
        fi
        
        # 更新 .claude.json 文件（不包含 API KEY）
        if [ -f "$CLAUDE_CONFIG_FILE" ]; then
            # 使用 jq 更新现有配置
            if command -v jq &> /dev/null; then
                jq --arg url "$API_BASE_URL" \
                    '. + {"apiBaseUrl": $url}' \
                    "$CLAUDE_CONFIG_FILE" > "$CLAUDE_CONFIG_FILE.tmp" && \
                    mv "$CLAUDE_CONFIG_FILE.tmp" "$CLAUDE_CONFIG_FILE"
            else
                # 如果没有 jq，创建新的配置文件
                cat > "$CLAUDE_CONFIG_FILE" << EOF
{
  "apiBaseUrl": "$API_BASE_URL",
  "installMethod": "script",
  "autoUpdates": true
}
EOF
            fi
        else
            # 创建新的 .claude.json 文件
            cat > "$CLAUDE_CONFIG_FILE" << EOF
{
  "apiBaseUrl": "$API_BASE_URL",
  "installMethod": "script",
  "autoUpdates": true
}
EOF
        fi
        
        print_success "配置文件创建完成: $CLAUDE_CONFIG_FILE"
    fi
    
    # 配置系统环境变量
    print_info "配置系统环境变量..."
    
    # 获取正确的 shell 配置文件
    local shell_config=""
    local env_type=$(detect_environment)
    
    if [[ "$env_type" == "macos" ]]; then
        # macOS 特殊处理：检测默认 shell
        local default_shell=$(echo $SHELL)
        print_info "检测到 macOS 默认 Shell: $default_shell"
        
        if [[ "$default_shell" == *"zsh"* ]]; then
            shell_config="$HOME/.zshrc"
            print_info "使用 zsh 配置文件: $shell_config"
        else
            # bash 在 macOS 上通常使用 .bash_profile
            shell_config="$HOME/.bash_profile"
            print_info "使用 bash 配置文件: $shell_config"
        fi
        
        # 如果配置文件不存在，创建它
        if [ ! -f "$shell_config" ]; then
            touch "$shell_config"
            print_info "创建配置文件: $shell_config"
        fi
    else
        # 非 macOS 系统的处理
        if [ -f "$HOME/.bashrc" ]; then
            shell_config="$HOME/.bashrc"
        elif [ -f "$HOME/.bash_profile" ]; then
            shell_config="$HOME/.bash_profile"
        elif [ -f "$HOME/.zshrc" ]; then
            shell_config="$HOME/.zshrc"
        else
            shell_config="$HOME/.bashrc"
            touch "$shell_config"
        fi
        
        # 对于root用户，确保同时更新.profile
        if [ "$EUID" -eq 0 ] || [ "$(whoami)" = "root" ]; then
            print_info "检测到root用户，将同时配置多个shell文件"
        fi
    fi
    
    # 清理旧的环境变量
    sed -i.bak '/ANTHROPIC_BASE_URL/d' "$shell_config" 2>/dev/null || true
    sed -i.bak '/ANTHROPIC_AUTH_TOKEN/d' "$shell_config" 2>/dev/null || true
    
    # 添加新的环境变量
    echo "" >> "$shell_config"
    echo "# Anthropic API Configuration" >> "$shell_config"
    echo "export ANTHROPIC_BASE_URL=\"$API_BASE_URL\"" >> "$shell_config"
    echo "export ANTHROPIC_AUTH_TOKEN=\"$API_KEY\"" >> "$shell_config"
    
    # 对于root用户，同时写入.profile以确保环境变量生效
    if [ "$EUID" -eq 0 ] || [ "$(whoami)" = "root" ]; then
        if [ "$shell_config" != "$HOME/.profile" ]; then
            print_info "同时更新 $HOME/.profile"
            sed -i.bak '/ANTHROPIC_BASE_URL/d' "$HOME/.profile" 2>/dev/null || true
            sed -i.bak '/ANTHROPIC_AUTH_TOKEN/d' "$HOME/.profile" 2>/dev/null || true
            echo "" >> "$HOME/.profile"
            echo "# Anthropic API Configuration" >> "$HOME/.profile"
            echo "export ANTHROPIC_BASE_URL=\"$API_BASE_URL\"" >> "$HOME/.profile"
            echo "export ANTHROPIC_AUTH_TOKEN=\"$API_KEY\"" >> "$HOME/.profile"
        fi
    fi
    
    # 配置系统级环境变量（如果有权限）- macOS 跳过此步骤
    if [[ "$env_type" != "macos" ]]; then
        local has_system_access=false
        if [ "$EUID" -eq 0 ]; then
            has_system_access=true
        elif command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
            has_system_access=true
        fi
        
        if [ "$has_system_access" = true ] && [ -w "/etc/environment" -o "$EUID" -eq 0 ]; then
            print_info "配置系统级环境变量..."
            
            # 清理旧配置
            if [ "$EUID" -eq 0 ]; then
                sed -i '/ANTHROPIC_BASE_URL/d' /etc/environment 2>/dev/null || true
                sed -i '/ANTHROPIC_AUTH_TOKEN/d' /etc/environment 2>/dev/null || true
                echo "ANTHROPIC_BASE_URL=\"$API_BASE_URL\"" >> /etc/environment
                echo "ANTHROPIC_AUTH_TOKEN=\"$API_KEY\"" >> /etc/environment
            elif command -v sudo &> /dev/null; then
                sudo sed -i '/ANTHROPIC_BASE_URL/d' /etc/environment 2>/dev/null || true
                sudo sed -i '/ANTHROPIC_AUTH_TOKEN/d' /etc/environment 2>/dev/null || true
                echo "ANTHROPIC_BASE_URL=\"$API_BASE_URL\"" | sudo tee -a /etc/environment > /dev/null
                echo "ANTHROPIC_AUTH_TOKEN=\"$API_KEY\"" | sudo tee -a /etc/environment > /dev/null
            fi
            
            print_success "系统级环境变量配置完成"
        else
            print_info "跳过系统级环境变量配置（需要 sudo 权限）"
        fi
    else
        print_info "macOS 系统：跳过系统级配置文件写入"
    fi
    
    print_success "所有配置完成！"
    
    # 立即应用配置，无需重新登录
    print_info "正在应用配置..."
    
    # 1. 立即导出环境变量到当前会话
    export ANTHROPIC_BASE_URL="$API_BASE_URL"
    export ANTHROPIC_AUTH_TOKEN="$API_KEY"
    
    # 2. 如果 Claude 正在运行，终止它以使用新配置
    if pgrep -f claude > /dev/null 2>&1; then
        print_info "检测到 Claude 正在运行，正在重启..."
        pkill -f claude 2>/dev/null || true
        sleep 1
    fi
    
    # 3. 清理可能的缓存
    if [ -d "$CLAUDE_DIR/cache" ]; then
        rm -rf "$CLAUDE_DIR/cache"
    fi
    
    # 4. 验证配置是否生效
    print_info "验证配置..."
    if command -v claude &> /dev/null; then
        # 测试连接
        if claude --version > /dev/null 2>&1; then
            print_success "Claude CLI 配置成功！"
            print_info "您现在可以直接使用 'claude' 命令，无需重新登录"
        else
            print_warning "Claude CLI 已安装但可能需要重新启动终端"
            print_info "您也可以执行: source $shell_config"
        fi
    fi
    
    # 5. 创建解决方案使配置立即生效
    print_info "应用即时生效方案..."
    
    # 检查是否有 sudo 权限或是 root 用户
    local can_use_sudo=false
    if [ "$EUID" -eq 0 ]; then
        can_use_sudo=true
    elif command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
        can_use_sudo=true
    fi
    
    if [ "$can_use_sudo" = true ]; then
        # 有权限，使用系统级安装
        # 备份原始 claude 命令
        if [ -f /usr/bin/claude ] && [ ! -f /usr/bin/claude.original ]; then
            sudo mv /usr/bin/claude /usr/bin/claude.original
            print_info "已备份原始 claude 命令"
        fi
    else
        # 没有权限，使用用户级安装
        print_warning "无 sudo 权限，将使用用户级安装"
        local user_bin_dir="$HOME/.local/bin"
        
        # 创建用户 bin 目录
        if [ ! -d "$user_bin_dir" ]; then
            mkdir -p "$user_bin_dir"
            print_info "创建用户 bin 目录: $user_bin_dir"
        fi
        
        # 检查 PATH 是否包含用户 bin 目录
        if [[ ":$PATH:" != *":$user_bin_dir:"* ]]; then
            print_info "添加 $user_bin_dir 到 PATH"
            echo "" >> "$shell_config"
            echo "# Add user bin to PATH" >> "$shell_config"
            echo "export PATH=\"\$PATH:$user_bin_dir\"" >> "$shell_config"
        fi
    fi
    
    # 创建新的 claude 命令作为包装器
    cat > /tmp/claude-wrapper << 'EOF'
#!/bin/bash
# Claude CLI 智能包装器 - 自动加载配置

# 查找原始 claude 命令
CLAUDE_BIN="/usr/bin/claude.original"
if [ ! -f "$CLAUDE_BIN" ]; then
    # 尝试其他位置
    for bin in /usr/local/bin/claude /opt/claude/claude $(which claude 2>/dev/null); do
        if [ -f "$bin" ] && [ "$bin" != "$0" ]; then
            CLAUDE_BIN="$bin"
            break
        fi
    done
fi

# 读取配置文件
CONFIG_FILE="$HOME/.claude.json"
if [ -f "$CONFIG_FILE" ]; then
    # 使用 grep 和 sed 提取值（兼容性更好）
    # 不再从配置文件读取 API_KEY
    API_BASE_URL=$(grep -o '"apiBaseUrl"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" | sed 's/.*:.*"\(.*\)"/\1/')
fi

# API KEY 现在只从环境变量读取
API_KEY="${ANTHROPIC_AUTH_TOKEN:-${ANTHROPIC_API_KEY:-}}"

# 使用环境变量作为后备
API_BASE_URL="${API_BASE_URL:-${ANTHROPIC_BASE_URL:-https://api5.ai}}"

# 如果没有配置，提示用户
if [ -z "$API_KEY" ]; then
    echo "错误：未找到 API 配置"
    echo "请运行安装脚本：curl -sSL https://1.api5.ai/install.sh | bash"
    exit 1
fi

# 导出环境变量
export ANTHROPIC_BASE_URL="$API_BASE_URL"
export ANTHROPIC_AUTH_TOKEN="$API_KEY"

# 执行原始命令
exec "$CLAUDE_BIN" "$@"
EOF
    
    # 安装新的包装器
    if [ "$can_use_sudo" = true ]; then
        # 系统级安装
        sudo mv /tmp/claude-wrapper /usr/bin/claude
        sudo chmod +x /usr/bin/claude
        
        # 同时创建 claude-ai 作为备用
        sudo cp /usr/bin/claude /usr/local/bin/claude-ai
    else
        # 用户级安装
        mv /tmp/claude-wrapper "$user_bin_dir/claude"
        chmod +x "$user_bin_dir/claude"
        
        # 同时创建 claude-ai 作为备用
        cp "$user_bin_dir/claude" "$user_bin_dir/claude-ai"
    fi
    
    # 创建一个恢复脚本
    if [ "$can_use_sudo" = true ]; then
        cat > /tmp/claude-restore << 'EOF'
#!/bin/bash
# 恢复原始 claude 命令
if [ -f /usr/bin/claude.original ]; then
    sudo mv /usr/bin/claude.original /usr/bin/claude
    echo "已恢复原始 claude 命令"
else
    echo "未找到原始备份"
fi
EOF
        sudo mv /tmp/claude-restore /usr/local/bin/claude-restore
        sudo chmod +x /usr/local/bin/claude-restore
    else
        cat > "$user_bin_dir/claude-restore" << 'EOF'
#!/bin/bash
# 恢复原始 claude 命令
echo "用户级安装不需要恢复"
echo "如需卸载，请删除: ~/.local/bin/claude"
EOF
        chmod +x "$user_bin_dir/claude-restore"
    fi
    
    print_success "配置已应用，立即生效！"
    
    # 自动检测和修复 API key 中的 ant- 前缀
    print_info "检测 API key 配置..."
    check_and_fix_api_key
    
    print_info "现在您可以直接使用："
    echo "  claude '你的问题'"
    echo
    print_info "如需恢复原始命令，运行："
    echo "  claude-restore"
}

# 显示使用说明
show_usage() {
    echo
    echo -e "${WHITE}=========================================="
    echo -e "    🎉 Claude Code 安装配置完成！"
    echo -e "==========================================${NC}"
    echo
    echo -e "${WHITE}配置信息:${NC}"
    echo "  API Key: $API_KEY"
    echo "  API URL: $API_BASE_URL"
    echo "  配置文件: $CLAUDE_CONFIG_FILE"
    echo
    echo -e "${WHITE}使用方法:${NC}"
    echo "  claude --help    - 查看帮助"
    echo "  claude \"你的问题\" - 与 Claude 对话"
    echo
    echo -e "${WHITE}环境变量:${NC}"
    echo "  已配置 ANTHROPIC_BASE_URL"
    echo "  已配置 ANTHROPIC_AUTH_TOKEN"
    echo
    
    # 检查 PATH
    if ! command -v claude &> /dev/null; then
        print_warning "claude 命令未在 PATH 中，可能需要重新加载 shell："
        echo "  source ~/.bashrc"
        echo "  或重新打开终端"
    fi
    
    # 对root用户的特别提示
    if [ "$EUID" -eq 0 ] || [ "$(whoami)" = "root" ]; then
        echo
        print_info "Root用户注意事项："
        echo "  环境变量已写入 ~/.bashrc 和 ~/.profile"
        echo "  请执行以下命令之一使其生效："
        echo "    source ~/.bashrc"
        echo "    source ~/.profile"
        echo "  或重新登录"
    fi
}

# 获取用户输入的API配置
get_api_config() {
    # 检查是否通过环境变量或参数提供了 API Key
    if [ -n "$CLAUDE_API_KEY" ]; then
        API_KEY="$CLAUDE_API_KEY"
        print_info "使用环境变量中的 API Key"
    fi
    
    if [ -n "$CLAUDE_API_URL" ]; then
        API_BASE_URL="$CLAUDE_API_URL"
        print_info "使用环境变量中的 API URL: $API_BASE_URL"
    fi
    
    # 如果没有提供 API Key，则进入交互模式
    if [ -z "$API_KEY" ]; then
        echo
        print_info "请输入您的 API 配置信息："
        echo
        
        # 获取 API Key
        while [ -z "$API_KEY" ]; do
            # 使用 /dev/tty 来读取用户输入，即使在管道中也能工作
            if [ -t 0 ]; then
                read -p "请输入您的 API Key: " API_KEY
            else
                read -p "请输入您的 API Key: " API_KEY < /dev/tty
            fi
            if [ -z "$API_KEY" ]; then
                print_error "API Key 不能为空！"
                sleep 1  # 避免无限循环太快
            fi
        done
        
        # 默认使用 api5.ai
        API_BASE_URL="https://api5.ai"
    fi
    
    echo
    print_success "配置信息："
    echo "  API Key: ${API_KEY:0:10}..."
    echo "  API URL: $API_BASE_URL"
    echo
}

# 主函数
main() {
    clear
    echo -e "${WHITE}"
    echo "================================================"
    echo "    🚀 Claude Code 远程一键安装脚本    "
    echo "================================================"
    echo -e "${NC}"
    
    # 获取 API 配置
    get_api_config
    
    # 检测环境
    local env_type=$(detect_environment)
    print_info "检测到环境: $env_type"
    
    # 检查权限
    if [[ "$env_type" != "macos" ]]; then
        if ! check_sudo; then
            print_error "无法获取必要的权限"
            exit 1
        fi
    fi
    
    # 根据环境安装依赖
    case "$env_type" in
        wsl)
            install_wsl_packages
            ;;
        macos)
            install_macos_packages
            ;;
        linux)
            install_linux_packages
            ;;
        windows_bash)
            print_warning "检测到 Windows Git Bash/MSYS 环境"
            print_info "建议使用 WSL2 以获得更好的体验"
            install_linux_packages
            ;;
        *)
            print_error "不支持的操作系统: $env_type"
            exit 1
            ;;
    esac
    
    # 安装 Claude Code
    if ! install_claude_code; then
        print_error "Claude Code 安装失败"
        exit 1
    fi
    
    # 配置 Claude Code
    configure_claude_code
    
    # 显示使用说明
    show_usage
}

# 运行主函数
main "$@"