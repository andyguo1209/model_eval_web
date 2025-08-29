# 🚀 HKGAI模型评测Web系统

一个功能强大且易于使用的HKGAI模型评测系统，支持主观题和客观题评测，多模型对比分析。

## ✨ 主要特性

- 🎯 **智能评测模式**：自动识别主观题/客观题，或手动选择评测模式
- 🤖 **多模型支持**：支持Gemini、HKGAI-V1、HKGAI-V2等多个模型，可灵活选择
- 📊 **美观的Web界面**：直观的步骤引导，实时进度显示，现代化响应式设计
- 📈 **丰富的结果展示**：在线查看、筛选、排序，支持Excel/CSV多格式导出
- ⚡ **高性能处理**：异步并发处理，支持大批量评测
- 🔍 **详细分析**：按类型统计，支持详细查看每个问题的评测结果
- 📚 **历史管理**：完整的评测历史记录，支持版本管理和智能检索
- 🏷️ **人工标注**：专业的多维度标注系统（正确性、相关性、安全性、创造性、逻辑一致性）
- 📊 **对比分析**：模型性能对比、趋势分析、质量指标统计

## 🚀 快速开始

### 一键部署 (推荐)

```bash
# 下载并运行一键部署脚本
curl -fsSL https://raw.githubusercontent.com/your-repo/model-evaluation-web/main/deploy.sh | bash

# 或者手动下载执行
wget https://github.com/your-repo/model-evaluation-web/raw/main/deploy.sh
chmod +x deploy.sh
./deploy.sh
```

### 手动安装

#### 方式1: 使用Conda (推荐)

##### 1. 创建conda环境（可选）
```bash
# 建议使用 python 3.10
conda create -n model-evaluation-web python=3.10

# 激活conda环境
conda activate model-evaluation-web
```

##### 2. 安装依赖
```bash
# 克隆项目
git clone https://github.com/your-repo/model-evaluation-web.git
cd model-evaluation-web

# 使用environment.yml创建环境（推荐）
conda env create -f environment.yml
conda activate model-evaluation-web

# 或者使用pip安装
pip install -r requirements.txt
```

##### 3. 安装额外依赖（可选）

- 若要使用性能分析功能，需安装perf依赖：
```bash
pip install psutil memory-profiler line-profiler
```

- 若要使用可视化功能，需安装viz依赖：
```bash
pip install matplotlib seaborn plotly
```

- 若要使用开发调试功能，需安装dev依赖：
```bash
pip install jupyter ipython pytest pytest-cov black flake8
```

- 若使用高级分析功能，可按需安装analytics依赖：
```bash
pip install scipy scikit-learn networkx
```

- 安装全部可选依赖：
```bash
pip install -r requirements-optional.txt
```

##### 4. 配置和启动
```bash
# 配置环境变量
cp config.env.template .env
nano .env  # 编辑API密钥配置

# 安装 Gunicorn (推荐生产环境使用)
pip install gunicorn

# 启动服务 (开发模式)
python start.py

# 或使用 Gunicorn 启动 (推荐生产环境)
gunicorn --workers 4 --bind 0.0.0.0:5001 app:app

# 更推荐的配置（守护进程运行）
gunicorn --workers 4 --bind 0.0.0.0:5001 --daemon app:app
```

##### 快速启动（一键脚本）
```bash
# 自动创建环境并启动
./start_conda.sh
```

#### 方式2: 使用pip/venv

##### 1. 创建虚拟环境
```bash
# 建议使用 python 3.10
python3.10 -m venv model-evaluation-web
source model-evaluation-web/bin/activate  # Windows: model-evaluation-web\Scripts\activate
```

##### 2. 安装依赖
```bash
# 克隆项目
git clone https://github.com/your-repo/model-evaluation-web.git
cd model-evaluation-web

# 安装基础依赖
pip install -r requirements.txt

# 安装可选依赖（按需选择）
pip install -r requirements-optional.txt
```

##### 3. 配置和启动
```bash
# 配置环境变量
cp config.env.template .env
nano .env  # 编辑API密钥配置

# 安装 Gunicorn (推荐生产环境使用)
pip install gunicorn

# 启动服务 (开发模式)
python start.py

# 或使用 Gunicorn 启动 (推荐生产环境)
gunicorn --workers 4 --bind 0.0.0.0:5001 app:app

# 更推荐的配置（守护进程运行）
gunicorn --workers 4 --bind 0.0.0.0:5001 --daemon app:app
```

### 📦 可选依赖说明

系统支持按需安装额外功能模块：

| 功能模块 | 依赖包 | 用途 |
|---------|--------|------|
| **perf** | `psutil`, `memory-profiler`, `line-profiler` | 性能分析和系统监控 |
| **viz** | `matplotlib`, `seaborn`, `plotly` | 高级图表和数据可视化 |
| **dev** | `jupyter`, `ipython`, `pytest` | 开发调试和测试 |
| **analytics** | `scipy`, `scikit-learn`, `networkx` | 高级统计分析 |
| **i18n** | `babel`, `flask-babel` | 多语言界面支持 |
| **export** | `xlsxwriter`, `reportlab` | 增强数据导出功能 |
| **cache** | `redis`, `flask-caching` | Redis缓存支持 |
| **security** | `cryptography`, `flask-limiter` | 安全增强功能 |

#### 安装示例

##### 方式1: 交互式安装（推荐）
```bash
# 使用交互式脚本安装
./install_optional.sh
# 根据提示选择需要的功能模块
```

##### 方式2: 命令行安装
```bash
# 安装全部可选依赖
pip install -r requirements-optional.txt

# 按需安装
pip install psutil memory-profiler line-profiler    # 仅性能分析
pip install matplotlib seaborn plotly              # 仅可视化
pip install jupyter ipython pytest                 # 仅开发调试
pip install scipy scikit-learn networkx            # 仅高级分析
```

### 🛠️ 环境问题修复

如果遇到部署问题（如numpy/pandas兼容性错误），使用自动修复脚本：

```bash
# 自动诊断和修复环境问题
chmod +x fix_environment.sh
./fix_environment.sh
```

常见问题解决方案请参考 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## 🔧 环境配置

### 系统要求

- **Python**: 3.8+ (建议使用 3.10)
- **操作系统**: Windows/macOS/Linux
- **内存**: 最低2GB，推荐4GB+
- **存储**: 最低1GB可用空间
- **环境管理**: 推荐使用Conda，也支持pip/venv

### 环境管理工具安装

#### Conda (推荐)
```bash
# 安装Miniconda (轻量版)
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# 或安装Anaconda (完整版)
wget https://repo.anaconda.com/archive/Anaconda3-latest-Linux-x86_64.sh
bash Anaconda3-latest-Linux-x86_64.sh
```

#### pip (系统自带)
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install python3-pip python3-venv

# CentOS/RHEL
sudo yum install python3-pip

# macOS (使用Homebrew)
brew install python
```

### API密钥配置

系统需要以下API密钥：

#### 1. Google Gemini API密钥
```bash
GOOGLE_API_KEY=your_google_api_key_here
```
获取方式：访问 [Google AI Studio](https://makersuite.google.com/) 创建API密钥

#### 2. HKGAI模型API密钥
```bash
ARK_API_KEY_HKGAI_V1=your_hkgai_v1_key_here
ARK_API_KEY_HKGAI_V2=your_hkgai_v2_key_here
```
获取方式：联系HKGAI服务提供商

### 配置方法

#### 方法一：环境变量文件（推荐）
1. 复制模板：`cp config.env.template .env`
2. 编辑`.env`文件，填入您的API密钥
3. 启动系统

#### 方法二：Web界面配置
1. 启动系统：
   ```bash
   # 开发模式
   python3 start.py
   
   # 或生产模式 (推荐)
   gunicorn --workers 4 --bind 0.0.0.0:5001 app:app
   ```
2. 访问 http://localhost:5001
3. 在页面上输入API密钥并保存

#### 方法三：环境变量
```bash
export GOOGLE_API_KEY="your_api_key"
export ARK_API_KEY_HKGAI_V1="your_hkgai_v1_key"
export ARK_API_KEY_HKGAI_V2="your_hkgai_v2_key"

# 安装 Gunicorn (如果未安装)
pip install gunicorn

# 启动服务 (开发模式)
python3 start.py

# 或使用 Gunicorn 启动 (推荐生产环境)
gunicorn --workers 4 --bind 0.0.0.0:5001 app:app

# 更推荐的配置（守护进程运行）
gunicorn --workers 4 --bind 0.0.0.0:5001 --daemon app:app
```

## 🚀 生产环境启动配置

### Gunicorn 配置说明

推荐在生产环境中使用 Gunicorn 作为 WSGI 服务器：

#### 基础配置
```bash
# 安装 Gunicorn
pip install gunicorn

# 基本启动
gunicorn --workers 4 --bind 0.0.0.0:5001 app:app
```

#### 推荐配置
```bash
# 守护进程模式（后台运行）
gunicorn --workers 4 --bind 0.0.0.0:5001 --daemon app:app

# 完整配置（推荐生产环境）
gunicorn --workers 4 \
         --worker-class gevent \
         --worker-connections 1000 \
         --bind 0.0.0.0:5001 \
         --timeout 300 \
         --keepalive 2 \
         --max-requests 1000 \
         --max-requests-jitter 100 \
         --preload \
         --daemon \
         --pid /var/run/model-evaluation.pid \
         --access-logfile /var/log/model-evaluation-access.log \
         --error-logfile /var/log/model-evaluation-error.log \
         app:app
```

#### 配置参数说明
- `--workers 4`: 启动4个工作进程（建议为CPU核心数 × 2 + 1）
- `--worker-class gevent`: 使用gevent异步工作模式（需要`pip install gevent`）
- `--bind 0.0.0.0:5001`: 绑定到所有网络接口的5001端口
- `--timeout 300`: 工作进程超时时间（秒）
- `--daemon`: 后台守护进程模式
- `--preload`: 预加载应用代码（提高性能）

#### Systemd 服务配置
创建系统服务文件 `/etc/systemd/system/model-evaluation.service`：

```ini
[Unit]
Description=AI Model Evaluation Web Service
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/opt/model-evaluation-web
Environment=PATH=/opt/model-evaluation-web/venv/bin
ExecStart=/opt/model-evaluation-web/venv/bin/gunicorn --workers 4 --bind 0.0.0.0:5001 --daemon --pid /var/run/model-evaluation.pid app:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable model-evaluation
sudo systemctl start model-evaluation
```

## 🌐 访问系统

### 开发环境
- **主页**: http://localhost:5001
- **历史管理**: http://localhost:5001/history
- **手动标注**: http://localhost:5001/annotate/[result_id]

### 生产环境

#### Nginx配置

如果您需要在生产环境中使用nginx作为反向代理，以下是完整的配置方法：

##### 1. 安装nginx
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install nginx

# CentOS/RHEL
sudo yum install nginx

# macOS
brew install nginx
```

##### 2. 创建nginx配置文件
```bash
sudo nano /etc/nginx/sites-available/model-evaluation
```

##### 3. nginx配置内容

**完整的nginx配置文件** (`/etc/nginx/sites-available/model-evaluation`):

```nginx
# HKGAI模型评测系统 Nginx配置
# 支持HTTP和HTTPS，包含WebSocket支持和性能优化

# HTTP服务器配置 (可重定向到HTTPS)
server {
    listen 80;
    listen [::]:80;
    server_name your-domain.com www.your-domain.com;  # 替换为您的域名
    
    # 可选：重定向所有HTTP请求到HTTPS
    # 如果不使用HTTPS，请注释掉下面这行，并删除下面的HTTPS server块
    return 301 https://$server_name$request_uri;
}

# HTTPS服务器配置 (推荐)
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name your-domain.com www.your-domain.com;  # 替换为您的域名
    
    # SSL证书配置 (使用Let's Encrypt或其他SSL证书)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # SSL安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # 安全headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:;" always;
    
    # 日志配置
    access_log /var/log/nginx/model-evaluation.access.log combined;
    error_log /var/log/nginx/model-evaluation.error.log warn;
    
    # 客户端配置
    client_max_body_size 100M;
    client_body_timeout 60s;
    client_header_timeout 60s;
    client_body_buffer_size 128k;
    
    # Gzip压缩配置
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;
    
    # 静态文件处理
    location /static/ {
        alias /opt/model-evaluation-web/static/;  # 修改为您的实际路径
        expires 30d;
        add_header Cache-Control "public, immutable";
        add_header Vary Accept-Encoding;
        
        # 安全配置
        location ~* \.(js|css)$ {
            add_header Content-Type "text/plain";
        }
    }
    
    # 上传文件处理
    location /uploads/ {
        alias /opt/model-evaluation-web/uploads/;  # 修改为您的实际路径
        expires 1d;
        add_header Cache-Control "private, no-cache";
        
        # 安全限制
        location ~* \.(php|pl|py|jsp|asp|sh|cgi)$ {
            return 403;
        }
    }
    
    # 结果文件处理
    location /results/ {
        alias /opt/model-evaluation-web/results/;  # 修改为您的实际路径
        expires 1d;
        add_header Cache-Control "private, no-cache";
        
        # 安全限制
        location ~* \.(php|pl|py|jsp|asp|sh|cgi)$ {
            return 403;
        }
    }
    
    # 评测接口 (支持WebSocket和长时间连接)
    location /eval/ {
        proxy_pass http://localhost:5001/;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        
        # 评测相关的长超时配置
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        proxy_buffering off;
        proxy_cache_bypass $http_upgrade;
    }
    
    # API接口特殊配置
    location /api/ {
        proxy_pass http://localhost:5001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        
        # API长超时配置
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # API限流配置 (可选)
        # limit_req zone=api burst=10 nodelay;
    }
    
    # 文件上传接口
    location /upload {
        proxy_pass http://localhost:5001/upload;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 上传超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # 禁用缓冲以支持大文件上传
        proxy_request_buffering off;
        proxy_buffering off;
    }
    
    # WebSocket连接支持
    location /ws/ {
        proxy_pass http://localhost:5001/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket特殊配置
        proxy_cache_bypass $http_upgrade;
        proxy_buffering off;
        proxy_read_timeout 7d;
        proxy_send_timeout 7d;
    }
    
    # 主应用代理 (所有其他请求)
    location / {
        proxy_pass http://localhost:5001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        
        # 标准超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # 缓存配置
        proxy_cache_bypass $http_upgrade;
        proxy_no_cache $cookie_nocache $arg_nocache;
    }
    
    # 健康检查
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # 监控端点
    location /nginx_status {
        stub_status on;
        access_log off;
        allow 127.0.0.1;
        allow ::1;
        deny all;
    }
    
    # 安全配置 - 禁止访问敏感文件
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
    
    location ~ \.(sql|log|conf)$ {
        deny all;
        access_log off;
        log_not_found off;
    }
}

# 仅HTTP配置 (如果不使用HTTPS，使用此配置替换上面的HTTPS配置)
# server {
#     listen 80;
#     listen [::]:80;
#     server_name your-domain.com www.your-domain.com;
#     
#     # 在这里复制上面HTTPS server块中除SSL相关配置外的所有内容
# }
```

**额外的nginx主配置优化** (`/etc/nginx/nginx.conf`中的http块):

```nginx
# 在 http 块中添加以下配置

# 限流配置
limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=api:10m rate=5r/s;
limit_req_zone $binary_remote_addr zone=upload:10m rate=1r/s;

# 连接限制
limit_conn_zone $binary_remote_addr zone=addr:10m;

# 缓存配置
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=10g 
                 inactive=60m use_temp_path=off;

# 性能优化
sendfile on;
tcp_nopush on;
tcp_nodelay on;
keepalive_timeout 65;
types_hash_max_size 2048;
server_tokens off;

# 缓冲区大小
proxy_buffering on;
proxy_buffer_size 4k;
proxy_buffers 8 4k;
proxy_busy_buffers_size 8k;
```

##### 4. HTTPS配置 (可选但推荐)
如果您需要HTTPS支持，可以使用Let's Encrypt免费证书：

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

##### 5. 启用配置并启动nginx
```bash
# 创建软链接启用站点
sudo ln -s /etc/nginx/sites-available/model-evaluation /etc/nginx/sites-enabled/

# 删除默认配置 (可选)
sudo rm -f /etc/nginx/sites-enabled/default

# 测试配置
sudo nginx -t

# 重启nginx
sudo systemctl restart nginx

# 设置开机自启
sudo systemctl enable nginx
```

##### 6. 配置说明

- **端口配置**: nginx监听80端口（HTTP）和443端口（HTTPS）
- **文件上传**: 支持最大100MB文件上传
- **静态文件**: 自动处理CSS、JS等静态资源，启用缓存
- **代理设置**: 将请求转发到Flask应用（运行在5001端口）
- **超时配置**: API请求有更长的超时时间（5分钟）
- **安全headers**: 自动添加安全相关的HTTP头
- **日志记录**: 记录访问和错误日志便于调试

##### 7. 常用nginx管理命令
```bash
# 检查nginx状态
sudo systemctl status nginx

# 重启nginx
sudo systemctl restart nginx

# 重新加载配置
sudo systemctl reload nginx

# 查看错误日志
sudo tail -f /var/log/nginx/error.log

# 查看访问日志
sudo tail -f /var/log/nginx/access.log
```

详细的生产环境部署请参考 [DEPLOYMENT.md](DEPLOYMENT.md)

## 📋 使用指南

### 1. 评测流程

1. **准备数据文件**
   - 主观题：包含 `query`, `type` 列的CSV/Excel文件
   - 客观题：包含 `query`, `answer`, `type` 列的CSV/Excel文件

2. **上传并配置**
   - 访问系统主页，上传测试文件
   - 选择评测模型（可多选）
   - 选择评测模式（自动识别或手动指定）

3. **开始评测**
   - 点击"开始评测"按钮
   - 系统显示实时进度
   - 评测完成后自动跳转到结果页面

### 2. 结果分析

- **实时查看**：支持筛选、排序、分页
- **导出功能**：支持Excel完整报告、CSV增强报告、筛选结果导出
- **详细分析**：点击题目查看详细评测结果和评分理由
- **统计图表**：分数分布、模型对比、质量指标

### 3. 历史管理

- **智能检索**：按时间、模型、数据集、标签筛选
- **版本管理**：同一数据集的不同评测版本关联
- **批量操作**：支持批量下载、删除、归档

### 4. 人工标注

- **多维度评分**：正确性(0-5分)、相关性(0-5分)、安全性(0-5分)、创造性(0-5分)、逻辑一致性(0-5分)
- **快捷操作**：数字键0-5快速评分、方向键导航
- **实时更新**：修改后统计数据实时更新

## 🔥 高级功能

### 评测结果历史管理
- 📊 无限存储：按项目维度管理，支持无限历史记录
- 🔍 智能检索：多维度筛选和搜索
- 🏷️ 自动标签：基于内容自动生成分类标签
- 📈 趋势分析：历史数据对比和趋势展示

### 专业标注系统
- 🎯 多维度标注：5个核心维度的专业评分
- ⚡ 快速操作：键盘快捷键支持
- 📊 质量控制：自动质量检查和一致性分析
- 👥 协作支持：多人标注和结果合并

### 对比分析功能
- 📈 模型性能对比：详细的性能指标对比
- 📊 分数分布分析：可视化分数分布统计
- 🎯 质量指标评估：数据完整性、评分有效性分析
- 📋 自动化报告：专业的分析报告生成

## 📊 示例数据

系统提供了示例数据供您快速体验：

- **主观题示例**: `data/sample_subjective.csv`
- **客观题示例**: `data/sample_objective.csv`

## 🛠️ 项目结构

```
model-evaluation-web/
├── app.py                   # 主应用程序
├── start.py                # 启动脚本
├── start_conda.sh          # Conda环境一键启动脚本
├── fix_environment.sh      # 环境修复脚本
├── install_optional.sh     # 可选依赖交互式安装脚本
├── database.py             # 数据库管理
├── history_manager.py      # 历史管理
├── comparison_analysis.py   # 对比分析
├── environment.yml         # Conda环境配置
├── requirements.txt        # 基础依赖配置
├── requirements-optional.txt # 可选依赖配置
├── config.env.template     # 环境变量模板
├── templates/              # HTML模板
├── static/                # 静态资源
├── utils/                 # 工具模块
├── data/                  # 示例数据
├── results/               # 评测结果
├── results_history/       # 历史结果
├── TROUBLESHOOTING.md     # 问题解决指南
└── DEPLOYMENT.md          # 部署指南
```

## 🔄 API接口

### 核心评测API
- `POST /upload`: 文件上传
- `POST /evaluate`: 开始评测
- `GET /task_status/<task_id>`: 查询评测状态
- `GET /view_results/<filename>`: 查看结果

### 历史管理API
- `GET /api/history/list`: 获取历史列表
- `GET /api/history/download/<result_id>`: 下载历史结果
- `DELETE /api/history/delete/<result_id>`: 删除历史记录

### 标注系统API
- `POST /api/update_score`: 更新评分
- `GET /api/export_filtered`: 导出筛选结果

### 报告生成API
- `GET /api/generate_report/<filename>/excel`: Excel格式报告
- `GET /api/generate_report/<filename>/csv`: CSV格式报告

## 🔒 安全特性

- 🔐 API密钥安全存储
- 🛡️ 输入数据验证和清理
- 📝 操作日志记录
- 🚫 防止恶意文件上传
- 🔄 自动备份机制

详细安全信息请参考 [SECURITY.md](SECURITY.md)

## 📈 更新日志

查看 [CHANGELOG.md](CHANGELOG.md) 了解最新功能和改进。

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进这个项目！

### 开发环境设置
```bash
git clone https://github.com/your-repo/model-evaluation-web.git
cd model-evaluation-web
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 提交规范
- feat: 新功能
- fix: 修复bug
- docs: 文档更新
- style: 代码格式调整
- refactor: 代码重构

## 📄 许可证

本项目采用 MIT 许可证。

## 📞 支持与反馈

如果您在使用过程中遇到问题或有改进建议，请：

1. 查看文档和FAQ
2. 提交 [Issue](https://github.com/your-repo/model-evaluation-web/issues)
3. 发送邮件至：your-email@example.com

---

⭐ 如果这个项目对您有帮助，请给我们一个星标！