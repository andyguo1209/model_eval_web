# AI模型评测系统部署指南

## 📋 系统要求

### 最低配置
- **操作系统**: Ubuntu 18.04+ / CentOS 7+ / macOS 10.15+
- **Python**: 3.8+
- **内存**: 2GB RAM
- **硬盘**: 10GB 可用空间
- **网络**: 支持外网访问（用于API调用）

### 推荐配置
- **操作系统**: Ubuntu 20.04 LTS
- **Python**: 3.9+
- **内存**: 4GB+ RAM
- **硬盘**: 20GB+ SSD
- **CPU**: 2核心+

## 🚀 一键部署

### 方式一：快速部署脚本

```bash
# 下载并运行一键部署脚本
curl -fsSL https://raw.githubusercontent.com/your-repo/model-evaluation-web/main/deploy.sh | bash
```

### 方式二：手动执行部署脚本

```bash
# 1. 下载部署脚本
wget https://raw.githubusercontent.com/your-repo/model-evaluation-web/main/deploy.sh

# 2. 赋予执行权限
chmod +x deploy.sh

# 3. 运行部署脚本
./deploy.sh
```

## 📦 手动安装步骤

### 1. 系统环境准备

#### Ubuntu/Debian系统
```bash
# 更新系统包
sudo apt update && sudo apt upgrade -y

# 安装必要的系统依赖
sudo apt install -y python3 python3-pip python3-venv git nginx supervisor redis-server

# 安装Node.js (可选，用于前端构建工具)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

#### CentOS/RHEL系统
```bash
# 更新系统包
sudo yum update -y

# 安装EPEL仓库
sudo yum install -y epel-release

# 安装必要的系统依赖
sudo yum install -y python3 python3-pip git nginx supervisor redis

# 安装Node.js (可选)
curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
sudo yum install -y nodejs
```

#### macOS系统
```bash
# 安装Homebrew (如果没有)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装必要依赖
brew install python3 git nginx supervisor redis
```

### 2. 下载项目代码

```bash
# 创建项目目录
sudo mkdir -p /opt/model-evaluation-web
cd /opt/model-evaluation-web

# 克隆项目代码
git clone https://github.com/your-repo/model-evaluation-web.git .

# 设置目录权限
sudo chown -R $USER:$USER /opt/model-evaluation-web
```

### 3. Python环境配置

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 升级pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt
```

### 4. 环境变量配置

```bash
# 创建环境配置文件
cp .env.example .env

# 编辑环境配置
nano .env
```

**必填环境变量**：
```bash
# API密钥配置
GOOGLE_API_KEY=your_google_api_key_here
ARK_API_KEY_HKGAI_V1=your_hkgai_v1_key_here
ARK_API_KEY_HKGAI_V2=your_hkgai_v2_key_here

# Flask配置
FLASK_ENV=production
SECRET_KEY=your_secret_key_here

# 数据库配置
DATABASE_URL=sqlite:///evaluation_system.db

# 文件存储配置
UPLOAD_FOLDER=/opt/model-evaluation-web/uploads
RESULTS_FOLDER=/opt/model-evaluation-web/results

# 服务器配置
HOST=0.0.0.0
PORT=5001
```

### 5. 数据库初始化

```bash
# 激活虚拟环境
source venv/bin/activate

# 初始化数据库
python3 -c "
from database import DatabaseManager
db = DatabaseManager()
print('数据库初始化完成')
"

# 创建必要目录
mkdir -p uploads results results_history data logs
```

### 6. 服务配置

#### Systemd服务配置 (推荐)

创建服务文件：
```bash
sudo nano /etc/systemd/system/model-evaluation.service
```

服务文件内容：
```ini
[Unit]
Description=AI Model Evaluation Web Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/model-evaluation-web
Environment=PATH=/opt/model-evaluation-web/venv/bin
ExecStart=/opt/model-evaluation-web/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
# 重新加载systemd配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start model-evaluation

# 设置开机自启
sudo systemctl enable model-evaluation

# 查看服务状态
sudo systemctl status model-evaluation
```

## 🌐 Nginx配置

### 1. 创建Nginx配置文件

```bash
sudo nano /etc/nginx/sites-available/model-evaluation
```

### 2. Nginx配置内容

```nginx
# AI模型评测系统 Nginx配置
server {
    listen 80;
    server_name your-domain.com;  # 替换为您的域名
    
    # 重定向HTTP到HTTPS (可选)
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;  # 替换为您的域名
    
    # SSL证书配置 (可选，用于HTTPS)
    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # 安全headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
    
    # 日志配置
    access_log /var/log/nginx/model-evaluation.access.log;
    error_log /var/log/nginx/model-evaluation.error.log;
    
    # 客户端上传大小限制
    client_max_body_size 100M;
    
    # 静态文件处理
    location /static/ {
        alias /opt/model-evaluation-web/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # 上传文件处理
    location /uploads/ {
        alias /opt/model-evaluation-web/uploads/;
        expires 1d;
    }
    
    # 结果文件处理
    location /results/ {
        alias /opt/model-evaluation-web/results/;
        expires 1d;
    }
    
    # 主应用代理
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket支持 (如果需要)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # API接口特殊配置
    location /api/ {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # API超时配置 (更长的超时时间)
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
    
    # 健康检查
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

### 3. 启用配置

```bash
# 创建软链接启用站点
sudo ln -s /etc/nginx/sites-available/model-evaluation /etc/nginx/sites-enabled/

# 删除默认配置 (可选)
sudo rm -f /etc/nginx/sites-enabled/default

# 测试配置
sudo nginx -t

# 重启Nginx
sudo systemctl restart nginx

# 设置开机自启
sudo systemctl enable nginx
```

## 🔒 SSL/HTTPS配置 (推荐)

### 使用Let's Encrypt免费证书

```bash
# 安装Certbot
sudo apt install certbot python3-certbot-nginx

# 获取SSL证书
sudo certbot --nginx -d your-domain.com

# 设置自动续期
sudo crontab -e
# 添加以下行：
# 0 12 * * * /usr/bin/certbot renew --quiet
```

## 🔧 性能优化

### 1. 系统调优

```bash
# 优化文件描述符限制
echo '* soft nofile 65535' | sudo tee -a /etc/security/limits.conf
echo '* hard nofile 65535' | sudo tee -a /etc/security/limits.conf

# 优化内核参数
sudo nano /etc/sysctl.conf
# 添加以下内容：
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 2048
vm.swappiness = 10
```

### 2. 应用性能优化

```bash
# 安装Gunicorn (生产WSGI服务器)
source venv/bin/activate
pip install gunicorn gevent

# 创建Gunicorn配置
nano gunicorn.conf.py
```

Gunicorn配置文件：
```python
# Gunicorn配置文件
bind = "127.0.0.1:5001"
workers = 4
worker_class = "gevent"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 300
keepalive = 2
preload_app = True
```

更新Systemd服务：
```ini
ExecStart=/opt/model-evaluation-web/venv/bin/gunicorn -c gunicorn.conf.py app:app
```

## 📊 监控和日志

### 1. 应用日志配置

```python
# 在app.py中添加日志配置
import logging
from logging.handlers import RotatingFileHandler

if not app.debug:
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
```

### 2. 系统监控

```bash
# 安装htop进程监控
sudo apt install htop

# 监控系统资源
htop

# 监控应用进程
sudo systemctl status model-evaluation

# 查看应用日志
sudo journalctl -u model-evaluation -f
```

## 🔧 维护操作

### 日常维护命令

```bash
# 查看服务状态
sudo systemctl status model-evaluation nginx

# 重启服务
sudo systemctl restart model-evaluation

# 查看实时日志
sudo journalctl -u model-evaluation -f

# 备份数据库
cp evaluation_system.db evaluation_system.db.backup.$(date +%Y%m%d_%H%M%S)

# 清理临时文件
find /tmp -name "*model-evaluation*" -mtime +7 -delete

# 更新应用
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart model-evaluation
```

### 数据备份

```bash
#!/bin/bash
# backup.sh - 数据备份脚本

BACKUP_DIR="/opt/backups/model-evaluation"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# 备份数据库
cp /opt/model-evaluation-web/evaluation_system.db "$BACKUP_DIR/database_$DATE.db"

# 备份上传文件
tar -czf "$BACKUP_DIR/uploads_$DATE.tar.gz" -C /opt/model-evaluation-web uploads/

# 备份结果文件
tar -czf "$BACKUP_DIR/results_$DATE.tar.gz" -C /opt/model-evaluation-web results/

# 删除7天前的备份
find "$BACKUP_DIR" -name "*" -mtime +7 -delete

echo "备份完成: $DATE"
```

## 🐛 故障排查

### 常见问题

1. **服务无法启动**
   ```bash
   # 检查日志
   sudo journalctl -u model-evaluation --no-pager
   
   # 检查端口占用
   sudo netstat -tlnp | grep :5001
   ```

2. **API调用失败**
   ```bash
   # 检查环境变量
   cat .env
   
   # 测试API连接
   curl -v http://localhost:5001/health
   ```

3. **文件上传失败**
   ```bash
   # 检查目录权限
   ls -la uploads/ results/
   
   # 修复权限
   sudo chown -R www-data:www-data uploads/ results/
   ```

4. **数据库问题**
   ```bash
   # 检查数据库文件
   ls -la evaluation_system.db
   
   # 测试数据库连接
   python3 -c "import sqlite3; conn = sqlite3.connect('evaluation_system.db'); print('OK')"
   ```

## 📞 技术支持

- **文档地址**: https://your-docs-site.com
- **问题反馈**: https://github.com/your-repo/model-evaluation-web/issues
- **邮箱支持**: support@your-domain.com

---

🎉 **恭喜！** 您的AI模型评测系统已成功部署！

访问地址: `https://your-domain.com`
