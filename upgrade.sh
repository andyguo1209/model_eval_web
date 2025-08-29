#!/bin/bash

# ================================
# 🚀 HKGAI模型评测系统 - 一键升级脚本
# ================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检查是否为root用户
check_permissions() {
    if [[ $EUID -eq 0 ]]; then
        log_warning "建议不要使用root用户执行升级"
        read -p "是否继续? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 检查必要的文件
check_requirements() {
    log_info "检查系统环境..."
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装"
        exit 1
    fi
    
    # 检查数据库文件
    if [ ! -f "evaluation_system.db" ]; then
        log_error "数据库文件不存在: evaluation_system.db"
        exit 1
    fi
    
    # 检查是否有正在运行的进程
    if pgrep -f "python.*app.py" > /dev/null; then
        log_warning "检测到正在运行的服务进程"
        PID=$(pgrep -f "python.*app.py")
        log_info "进程ID: $PID"
        read -p "是否自动停止? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            pkill -f "python.*app.py"
            log_success "服务已停止"
            sleep 2
        else
            log_warning "请手动停止服务后重新运行升级脚本"
            exit 1
        fi
    fi
    
    log_success "环境检查通过"
}

# 数据备份
backup_data() {
    log_info "开始数据备份..."
    
    if [ -f "upgrade_backup.sh" ]; then
        chmod +x upgrade_backup.sh
        ./upgrade_backup.sh
        if [ $? -eq 0 ]; then
            log_success "数据备份完成"
        else
            log_error "数据备份失败"
            exit 1
        fi
    else
        log_warning "未找到备份脚本，执行快速备份..."
        TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
        mkdir -p "backup_${TIMESTAMP}"
        cp evaluation_system.db "backup_${TIMESTAMP}/evaluation_system.db.backup"
        log_success "快速备份完成: backup_${TIMESTAMP}/"
    fi
}

# 数据库迁移
migrate_database() {
    log_info "开始数据库迁移..."
    
    if [ -f "db_migration.py" ]; then
        python3 db_migration.py
        if [ $? -eq 0 ]; then
            log_success "数据库迁移完成"
        else
            log_error "数据库迁移失败"
            exit 1
        fi
    else
        log_warning "未找到迁移脚本，检查是否需要手动迁移..."
        
        # 简单检查表是否存在
        python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('evaluation_system.db')
    cursor = conn.cursor()
    cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='shared_links'\")
    result = cursor.fetchone()
    if result:
        print('shared_links表已存在')
    else:
        print('需要创建shared_links表')
        exit(1)
    conn.close()
except Exception as e:
    print(f'数据库检查失败: {e}')
    exit(1)
"
        if [ $? -eq 0 ]; then
            log_success "数据库已为最新版本"
        else
            log_error "数据库需要手动迁移，请查看UPGRADE_GUIDE.md"
            exit 1
        fi
    fi
}

# 验证升级
verify_upgrade() {
    log_info "验证升级结果..."
    
    # 检查数据库表结构
    python3 -c "
import sqlite3
conn = sqlite3.connect('evaluation_system.db')
cursor = conn.cursor()
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
tables = [row[0] for row in cursor.fetchall()]
required_tables = ['shared_links', 'shared_access_logs']
missing_tables = [t for t in required_tables if t not in tables]
if missing_tables:
    print(f'缺少表: {missing_tables}')
    exit(1)
else:
    print('所有必需的表都存在')
conn.close()
"
    if [ $? -eq 0 ]; then
        log_success "数据库结构验证通过"
    else
        log_error "数据库结构验证失败"
        exit 1
    fi
    
    # 检查新增的模板文件
    template_files=("templates/shared_result.html" "templates/shared_password.html" "templates/shared_error.html")
    for file in "${template_files[@]}"; do
        if [ -f "$file" ]; then
            log_success "模板文件存在: $file"
        else
            log_warning "模板文件缺失: $file"
        fi
    done
}

# 启动服务
start_service() {
    log_info "准备启动服务..."
    
    read -p "是否现在启动服务? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        log_info "启动服务..."
        
        # 检查端口占用
        if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null ; then
            log_warning "端口8080已被占用"
            log_info "您可能需要手动启动服务到其他端口"
        else
            # 在后台启动服务
            nohup python3 app.py > app.log 2>&1 &
            sleep 3
            
            if pgrep -f "python.*app.py" > /dev/null; then
                log_success "服务启动成功! PID: $(pgrep -f 'python.*app.py')"
                log_info "访问地址: http://localhost:8080"
                log_info "日志文件: app.log"
            else
                log_error "服务启动失败，请检查 app.log"
            fi
        fi
    else
        log_info "跳过服务启动"
        log_info "请手动启动: python3 app.py"
    fi
}

# 主升级流程
main() {
    echo "================================"
    echo "🚀 HKGAI模型评测系统 - 升级工具"
    echo "================================"
    echo ""
    
    log_info "开始升级流程..."
    echo ""
    
    # 权限检查
    check_permissions
    
    # 环境检查
    check_requirements
    echo ""
    
    # 数据备份
    backup_data
    echo ""
    
    # 数据库迁移
    migrate_database
    echo ""
    
    # 验证升级
    verify_upgrade
    echo ""
    
    # 启动服务
    start_service
    echo ""
    
    log_success "升级完成! 🎉"
    echo ""
    echo "📋 升级摘要:"
    echo "   ✅ 数据已备份"
    echo "   ✅ 数据库已迁移"
    echo "   ✅ 新增分享功能"
    echo "   ✅ 模板文件已更新"
    echo ""
    echo "📞 如有问题请联系: guozhenhua@hkgai.org"
}

# 捕获中断信号
trap 'log_error "升级被中断"; exit 1' INT TERM

# 执行主函数
main "$@"
