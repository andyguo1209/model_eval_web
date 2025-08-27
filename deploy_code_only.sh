#!/bin/bash

# =============================================================================
# 模型评测系统 - 仅更新代码部署脚本
# 功能：保留数据库、配置文件和用户数据，仅更新应用代码
# =============================================================================

set -e  # 遇到错误立即退出

# 配置变量
PROJECT_DIR="/Users/guozhenhua/PycharmProjects/model-evaluation-web"
BACKUP_DIR="/tmp/model_eval_backup_$(date +%Y%m%d_%H%M%S)"
REPO_URL="https://github.com/andyguo1209/model_eval_web.git"
BRANCH="main"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否在正确目录
check_directory() {
    if [ ! -f "app.py" ] || [ ! -f "database.py" ]; then
        log_error "当前目录不是模型评测系统根目录！"
        log_error "请在包含 app.py 和 database.py 的目录中运行此脚本"
        exit 1
    fi
    log_info "当前目录: $(pwd)"
}

# 创建备份目录
create_backup_dir() {
    log_info "创建备份目录: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
}

# 需要保护的文件和目录列表
PROTECTED_ITEMS=(
    "evaluation_system.db"           # 主数据库
    "evaluation_system.db.backup"   # 数据库备份
    ".env"                          # 环境配置文件（如果存在）
    "config.env"                    # 配置文件（如果存在）
    "uploads/"                      # 用户上传文件
    "results/"                      # 评测结果
    "results_history/"              # 历史结果
    "cookies.txt"                   # 会话文件（如果存在）
    "logs/"                         # 日志目录（如果存在）
    "nginx.conf"                    # Nginx配置（如果存在）
    "gunicorn.conf.py"             # Gunicorn配置（如果存在）
)

# 备份重要文件
backup_protected_files() {
    log_info "🔒 开始备份重要文件和目录..."
    
    for item in "${PROTECTED_ITEMS[@]}"; do
        if [ -e "$item" ]; then
            log_info "备份: $item"
            
            # 如果是目录，递归复制
            if [ -d "$item" ]; then
                cp -r "$item" "$BACKUP_DIR/"
            else
                cp "$item" "$BACKUP_DIR/"
            fi
        else
            log_warning "跳过不存在的项目: $item"
        fi
    done
    
    log_success "备份完成！备份位置: $BACKUP_DIR"
}

# 停止服务
stop_services() {
    log_info "🛑 停止相关服务..."
    
    # 停止可能运行的Flask应用
    if pgrep -f "python.*app.py" > /dev/null; then
        log_info "停止 Flask 应用..."
        pkill -f "python.*app.py" || true
        sleep 2
    fi
    
    # 停止可能运行的Gunicorn
    if pgrep -f "gunicorn" > /dev/null; then
        log_info "停止 Gunicorn 服务..."
        pkill -f "gunicorn" || true
        sleep 2
    fi
    
    log_success "服务已停止"
}

# 更新代码
update_code() {
    log_info "📦 开始更新代码..."
    
    # 检查Git状态
    if [ -d ".git" ]; then
        log_info "检测到Git仓库，使用Git更新..."
        
        # 保存当前分支
        current_branch=$(git branch --show-current)
        log_info "当前分支: $current_branch"
        
        # 拉取最新代码
        log_info "拉取最新代码..."
        git fetch origin
        git checkout "$BRANCH"
        git pull origin "$BRANCH"
        
        log_success "Git更新完成"
    else
        log_warning "未检测到Git仓库，请手动更新代码或重新克隆仓库"
        return 1
    fi
}

# 恢复重要文件
restore_protected_files() {
    log_info "🔄 恢复重要文件和目录..."
    
    for item in "${PROTECTED_ITEMS[@]}"; do
        backup_path="$BACKUP_DIR/$item"
        
        if [ -e "$backup_path" ]; then
            log_info "恢复: $item"
            
            # 如果目标已存在，先删除
            if [ -e "$item" ]; then
                rm -rf "$item"
            fi
            
            # 恢复文件/目录
            if [ -d "$backup_path" ]; then
                cp -r "$backup_path" .
            else
                cp "$backup_path" .
            fi
        fi
    done
    
    log_success "文件恢复完成"
}

# 更新Python依赖
update_dependencies() {
    log_info "📚 检查并更新Python依赖..."
    
    if [ -f "requirements.txt" ]; then
        log_info "更新Python包..."
        pip3 install -r requirements.txt --upgrade
        log_success "依赖更新完成"
    else
        log_warning "未找到 requirements.txt 文件"
    fi
}

# 验证关键文件
verify_files() {
    log_info "🔍 验证关键文件..."
    
    # 检查数据库文件
    if [ -f "evaluation_system.db" ]; then
        log_success "✅ 数据库文件存在"
    else
        log_error "❌ 数据库文件丢失！"
        return 1
    fi
    
    # 检查核心代码文件
    core_files=("app.py" "database.py" "config.py")
    for file in "${core_files[@]}"; do
        if [ -f "$file" ]; then
            log_success "✅ $file 存在"
        else
            log_error "❌ $file 丢失！"
            return 1
        fi
    done
    
    # 检查重要目录
    important_dirs=("templates" "static" "uploads" "results")
    for dir in "${important_dirs[@]}"; do
        if [ -d "$dir" ]; then
            log_success "✅ $dir/ 目录存在"
        else
            log_error "❌ $dir/ 目录丢失！"
            return 1
        fi
    done
    
    log_success "文件验证通过"
}

# 启动服务
start_services() {
    log_info "🚀 启动服务..."
    
    # 检查是否有自定义启动脚本
    if [ -f "gunicorn_service.sh" ] && [ -x "gunicorn_service.sh" ]; then
        log_info "使用Gunicorn启动脚本..."
        ./gunicorn_service.sh &
        sleep 3
    else
        log_info "使用Flask开发服务器启动..."
        nohup python3 app.py > /dev/null 2>&1 &
        sleep 3
    fi
    
    # 验证服务是否启动
    if pgrep -f "(python.*app.py|gunicorn)" > /dev/null; then
        log_success "服务启动成功"
    else
        log_error "服务启动失败"
        return 1
    fi
}

# 清理备份（可选）
cleanup_backup() {
    read -p "是否删除临时备份目录? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "清理备份目录: $BACKUP_DIR"
        rm -rf "$BACKUP_DIR"
        log_success "备份目录已清理"
    else
        log_info "备份目录保留在: $BACKUP_DIR"
    fi
}

# 显示部署摘要
show_summary() {
    echo
    echo "=================================================="
    echo -e "${GREEN}🎉 部署完成摘要${NC}"
    echo "=================================================="
    echo "📁 项目目录: $PROJECT_DIR"
    echo "💾 备份位置: $BACKUP_DIR"
    echo "🔄 更新分支: $BRANCH"
    echo "📊 保护的文件/目录:"
    for item in "${PROTECTED_ITEMS[@]}"; do
        if [ -e "$item" ]; then
            echo "   ✅ $item"
        fi
    done
    echo
    echo "🌐 服务状态:"
    if pgrep -f "(python.*app.py|gunicorn)" > /dev/null; then
        echo "   ✅ 应用服务正在运行"
    else
        echo "   ❌ 应用服务未运行"
    fi
    echo "=================================================="
}

# 主函数
main() {
    echo "=================================================="
    echo -e "${BLUE}🚀 模型评测系统 - 仅更新代码部署${NC}"
    echo "=================================================="
    echo
    
    # 执行部署步骤
    check_directory
    create_backup_dir
    backup_protected_files
    stop_services
    update_code
    restore_protected_files
    update_dependencies
    verify_files
    start_services
    
    echo
    log_success "🎉 代码更新部署完成！"
    
    # 显示摘要
    show_summary
    
    # 清理选项
    cleanup_backup
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
