#!/bin/bash

# AI模型评测系统一键部署脚本
# 支持Ubuntu/Debian, CentOS/RHEL, macOS系统

set -e  # 遇到错误立即退出

# 颜色定义
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

# 检测操作系统
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/debian_version ]; then
            OS="debian"
            DISTRO=$(lsb_release -si 2>/dev/null || echo "Unknown")
        elif [ -f /etc/redhat-release ]; then
            OS="redhat"
            DISTRO=$(cat /etc/redhat-release | awk '{print $1}')
        else
            OS="linux"
            DISTRO="Unknown"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        DISTRO="macOS"
    else
        log_error "不支持的操作系统: $OSTYPE"
        exit 1
    fi
    
    log_info "检测到操作系统: $DISTRO ($OS)"
}

# 检查是否以root权限运行
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_warning "检测到以root权限运行，建议使用普通用户运行此脚本"
        read -p "是否继续? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 安装系统依赖
install_system_deps() {
    log_info "安装系统依赖..."
    
    case $OS in
        "debian")
            sudo apt update
            sudo apt install -y python3 python3-pip python3-venv git nginx supervisor curl wget unzip
            ;;
        "redhat")
            sudo yum update -y
            sudo yum install -y epel-release
            sudo yum install -y python3 python3-pip git nginx supervisor curl wget unzip
            ;;
        "macos")
            # 检查是否安装了Homebrew
            if ! command -v brew &> /dev/null; then
                log_info "安装Homebrew..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            fi
            brew install python3 git nginx supervisor
            ;;
        *)
            log_error "不支持的操作系统"
            exit 1
            ;;
    esac
    
    log_success "系统依赖安装完成"
}

# 检查Python版本
check_python() {
    log_info "检查Python环境..."
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MAJOR" -eq 3 -a "$PYTHON_MINOR" -lt 8 ]; then
        log_error "需要Python 3.8或更高版本，当前版本: $PYTHON_VERSION"
        exit 1
    fi
    
    log_success "Python版本检查通过: $PYTHON_VERSION"
}

# 设置项目目录
setup_project_dir() {
    log_info "设置项目目录..."
    
    # 默认安装路径
    DEFAULT_INSTALL_PATH="/opt/model-evaluation-web"
    
    echo "请选择安装路径:"
    echo "1) $DEFAULT_INSTALL_PATH (推荐)"
    echo "2) 当前目录 ($(pwd)/model-evaluation-web)"
    echo "3) 自定义路径"
    
    read -p "请选择 (1-3) [1]: " choice
    choice=${choice:-1}
    
    case $choice in
        1)
            INSTALL_PATH="$DEFAULT_INSTALL_PATH"
            USE_SUDO=true
            ;;
        2)
            INSTALL_PATH="$(pwd)/model-evaluation-web"
            USE_SUDO=false
            ;;
        3)
            read -p "请输入安装路径: " INSTALL_PATH
            if [[ "$INSTALL_PATH" == /opt/* ]] || [[ "$INSTALL_PATH" == /usr/* ]]; then
                USE_SUDO=true
            else
                USE_SUDO=false
            fi
            ;;
        *)
            log_error "无效选择"
            exit 1
            ;;
    esac
    
    # 创建目录
    if [ "$USE_SUDO" = true ]; then
        sudo mkdir -p "$INSTALL_PATH"
        sudo chown $USER:$USER "$INSTALL_PATH"
    else
        mkdir -p "$INSTALL_PATH"
    fi
    
    cd "$INSTALL_PATH"
    log_success "项目目录设置完成: $INSTALL_PATH"
}

# 下载项目代码
download_code() {
    log_info "下载项目代码..."
    
    if [ -d ".git" ]; then
        log_info "检测到已存在的git仓库，执行更新..."
        git pull origin main
    else
        echo "请选择代码获取方式:"
        echo "1) Git克隆 (推荐，需要git仓库地址)"
        echo "2) 从本地复制 (适用于已下载的代码)"
        
        read -p "请选择 (1-2) [1]: " choice
        choice=${choice:-1}
        
        case $choice in
            1)
                read -p "请输入Git仓库地址: " GIT_REPO
                if [ -z "$GIT_REPO" ]; then
                    log_error "Git仓库地址不能为空"
                    exit 1
                fi
                git clone "$GIT_REPO" .
                ;;
            2)
                read -p "请输入源代码路径: " SOURCE_PATH
                if [ ! -d "$SOURCE_PATH" ]; then
                    log_error "源代码路径不存在: $SOURCE_PATH"
                    exit 1
                fi
                cp -r "$SOURCE_PATH"/* .
                ;;
            *)
                log_error "无效选择"
                exit 1
                ;;
        esac
    fi
    
    log_success "代码下载完成"
}

# 设置Python虚拟环境
setup_python_env() {
    log_info "设置Python虚拟环境..."
    
    # 创建虚拟环境
    python3 -m venv venv
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    # 安装依赖
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        log_error "requirements.txt 文件不存在"
        exit 1
    fi
    
    log_success "Python环境设置完成"
}

# 配置环境变量
setup_env_vars() {
    log_info "配置环境变量..."
    
    if [ ! -f ".env" ]; then
        if [ -f "config.env.template" ]; then
            cp config.env.template .env
        else
            # 创建基础配置文件
            cat > .env << 'EOF'
# API密钥配置
GOOGLE_API_KEY=your_google_api_key_here
ARK_API_KEY_HKGAI_V1=your_hkgai_v1_key_here
ARK_API_KEY_HKGAI_V2=your_hkgai_v2_key_here

# Flask配置
FLASK_ENV=production
SECRET_KEY=generated_secret_key_here

# 数据库配置
DATABASE_URL=sqlite:///evaluation_system.db

# 服务器配置
HOST=0.0.0.0
PORT=5001
EOF
        fi
    fi
    
    # 生成SECRET_KEY
    if grep -q "generated_secret_key_here" .env; then
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        sed -i.bak "s/generated_secret_key_here/$SECRET_KEY/" .env
        rm .env.bak 2>/dev/null || true
    fi
    
    log_warning "请编辑 .env 文件，配置您的API密钥"
    log_info "配置文件位置: $INSTALL_PATH/.env"
    
    read -p "是否现在编辑配置文件? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ${EDITOR:-nano} .env
    fi
    
    log_success "环境变量配置完成"
}

# 初始化数据库
init_database() {
    log_info "初始化数据库..."
    
    source venv/bin/activate
    
    # 创建必要目录
    mkdir -p uploads results results_history data logs
    
    # 初始化数据库
    python3 -c "
from database import EvaluationDatabase
try:
    db = EvaluationDatabase()
    print('数据库初始化完成')
except Exception as e:
    print(f'数据库初始化失败: {e}')
    exit(1)
"
    
    log_success "数据库初始化完成"
}

# 创建systemd服务
create_systemd_service() {
    if [ "$OS" = "macos" ]; then
        log_info "macOS系统跳过systemd服务创建"
        return 0
    fi
    
    log_info "创建systemd服务..."
    
    SERVICE_FILE="/etc/systemd/system/model-evaluation.service"
    
    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=AI Model Evaluation Web Service
After=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_PATH
Environment=PATH=$INSTALL_PATH/venv/bin
ExecStart=$INSTALL_PATH/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    # 重新加载systemd
    sudo systemctl daemon-reload
    
    # 启用服务
    sudo systemctl enable model-evaluation
    
    log_success "systemd服务创建完成"
}

# 配置Nginx
setup_nginx() {
    log_info "配置Nginx..."
    
    read -p "请输入域名 (留空使用localhost): " DOMAIN
    DOMAIN=${DOMAIN:-localhost}
    
    if [ "$OS" = "macos" ]; then
        NGINX_CONFIG="/usr/local/etc/nginx/servers/model-evaluation.conf"
        sudo mkdir -p /usr/local/etc/nginx/servers
    else
        NGINX_CONFIG="/etc/nginx/sites-available/model-evaluation"
        sudo mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
    fi
    
    sudo tee "$NGINX_CONFIG" > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    client_max_body_size 100M;
    
    # 静态文件处理
    location /static/ {
        alias $INSTALL_PATH/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # 上传文件处理
    location /uploads/ {
        alias $INSTALL_PATH/uploads/;
        expires 1d;
    }
    
    # 结果文件处理
    location /results/ {
        alias $INSTALL_PATH/results/;
        expires 1d;
    }
    
    # 主应用代理
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
    
    # 健康检查
    location /health {
        access_log off;
        return 200 "healthy\\n";
        add_header Content-Type text/plain;
    }
}
EOF
    
    # 启用站点 (非macOS)
    if [ "$OS" != "macos" ]; then
        sudo ln -sf /etc/nginx/sites-available/model-evaluation /etc/nginx/sites-enabled/
        
        # 禁用默认站点
        sudo rm -f /etc/nginx/sites-enabled/default
    fi
    
    # 测试配置
    sudo nginx -t
    
    log_success "Nginx配置完成"
}

# 启动服务
start_services() {
    log_info "启动服务..."
    
    if [ "$OS" != "macos" ]; then
        # 启动应用服务
        sudo systemctl start model-evaluation
        
        # 重启Nginx
        sudo systemctl restart nginx
        
        # 检查服务状态
        if sudo systemctl is-active --quiet model-evaluation; then
            log_success "应用服务启动成功"
        else
            log_error "应用服务启动失败"
            sudo systemctl status model-evaluation --no-pager
        fi
        
        if sudo systemctl is-active --quiet nginx; then
            log_success "Nginx服务启动成功"
        else
            log_error "Nginx服务启动失败"
            sudo systemctl status nginx --no-pager
        fi
    else
        log_info "macOS系统请手动启动服务:"
        echo "1. 启动应用: cd $INSTALL_PATH && source venv/bin/activate && python app.py"
        echo "2. 启动Nginx: sudo nginx"
    fi
}

# 安装SSL证书 (可选)
install_ssl() {
    if [ "$OS" = "macos" ]; then
        log_info "macOS系统跳过SSL安装"
        return 0
    fi
    
    read -p "是否安装SSL证书? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        return 0
    fi
    
    log_info "安装Let's Encrypt SSL证书..."
    
    # 安装certbot
    if [ "$OS" = "debian" ]; then
        sudo apt install -y certbot python3-certbot-nginx
    elif [ "$OS" = "redhat" ]; then
        sudo yum install -y certbot python3-certbot-nginx
    fi
    
    # 获取证书
    read -p "请输入邮箱地址: " EMAIL
    if [ -n "$EMAIL" ] && [ "$DOMAIN" != "localhost" ]; then
        sudo certbot --nginx -d "$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive
        log_success "SSL证书安装完成"
    else
        log_warning "跳过SSL证书安装 (需要有效域名和邮箱)"
    fi
}

# 创建维护脚本
create_maintenance_scripts() {
    log_info "创建维护脚本..."
    
    # 创建备份脚本
    cat > backup.sh << 'EOF'
#!/bin/bash
# 数据备份脚本

BACKUP_DIR="/opt/backups/model-evaluation"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# 备份数据库
cp evaluation_system.db "$BACKUP_DIR/database_$DATE.db"

# 备份上传文件
tar -czf "$BACKUP_DIR/uploads_$DATE.tar.gz" uploads/

# 备份结果文件  
tar -czf "$BACKUP_DIR/results_$DATE.tar.gz" results/

# 删除7天前的备份
find "$BACKUP_DIR" -name "*" -mtime +7 -delete

echo "备份完成: $DATE"
EOF
    
    chmod +x backup.sh
    
    # 创建更新脚本
    cat > update.sh << 'EOF'
#!/bin/bash
# 应用更新脚本

set -e

echo "开始更新应用..."

# 备份当前版本
./backup.sh

# 拉取最新代码
git pull origin main

# 激活虚拟环境
source venv/bin/activate

# 更新依赖
pip install -r requirements.txt

# 重启服务
if command -v systemctl &> /dev/null; then
    sudo systemctl restart model-evaluation
fi

echo "更新完成"
EOF
    
    chmod +x update.sh
    
    log_success "维护脚本创建完成"
}

# 显示部署结果
show_result() {
    log_success "部署完成！"
    
    echo
    echo "=========================================="
    echo "🎉 AI模型评测系统部署成功！"
    echo "=========================================="
    echo
    echo "📍 安装路径: $INSTALL_PATH"
    echo "🌐 访问地址: http://$DOMAIN"
    echo "⚙️  配置文件: $INSTALL_PATH/.env"
    echo
    echo "🔧 管理命令:"
    echo "  启动服务: sudo systemctl start model-evaluation"
    echo "  停止服务: sudo systemctl stop model-evaluation"
    echo "  重启服务: sudo systemctl restart model-evaluation"
    echo "  查看状态: sudo systemctl status model-evaluation"
    echo "  查看日志: sudo journalctl -u model-evaluation -f"
    echo
    echo "📝 维护脚本:"
    echo "  数据备份: ./backup.sh"
    echo "  应用更新: ./update.sh"
    echo
    echo "⚠️  重要提醒:"
    echo "  1. 请编辑 $INSTALL_PATH/.env 配置API密钥"
    echo "  2. 确保防火墙开放80/443端口"
    echo "  3. 定期运行备份脚本保护数据"
    echo
    echo "📚 更多文档: 请查看 DEPLOYMENT.md"
    echo "=========================================="
}

# 主函数
main() {
    echo "=========================================="
    echo "🚀 AI模型评测系统一键部署脚本"
    echo "=========================================="
    echo
    
    # 环境检查
    detect_os
    check_root
    
    # 安装依赖
    install_system_deps
    check_python
    
    # 设置项目
    setup_project_dir
    download_code
    setup_python_env
    setup_env_vars
    
    # 初始化
    init_database
    
    # 配置服务
    create_systemd_service
    setup_nginx
    
    # 启动服务
    start_services
    
    # 可选配置
    install_ssl
    
    # 创建维护脚本
    create_maintenance_scripts
    
    # 显示结果
    show_result
}

# 错误处理
trap 'log_error "部署过程中发生错误，请检查日志"; exit 1' ERR

# 运行主函数
main "$@"
