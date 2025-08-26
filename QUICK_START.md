# 🚀 AI模型评测系统快速开始指南

## 📥 快速部署

### 一键部署 (推荐)

```bash
# 下载并运行一键部署脚本
curl -fsSL https://raw.githubusercontent.com/your-repo/model-evaluation-web/main/deploy.sh | bash

# 或者手动下载执行
wget https://github.com/your-repo/model-evaluation-web/raw/main/deploy.sh
chmod +x deploy.sh
./deploy.sh
```

### 手动部署 (5分钟)

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/model-evaluation-web.git
cd model-evaluation-web

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp config.env.template .env
nano .env  # 编辑配置文件

# 5. 初始化数据库
python3 -c "from database import EvaluationDatabase; EvaluationDatabase()"

# 6. 启动服务
python3 app.py
```

## ⚙️ 必需配置

编辑 `.env` 文件，配置以下必需项：

```bash
# API密钥 (必填)
GOOGLE_API_KEY=your_google_api_key_here
ARK_API_KEY_HKGAI_V1=your_hkgai_v1_key_here  
ARK_API_KEY_HKGAI_V2=your_hkgai_v2_key_here

# Flask密钥 (生成随机字符串)
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

## 🌐 访问系统

- **本地开发**: http://localhost:5001
- **生产环境**: http://your-domain.com

## 📋 系统要求

- Python 3.8+
- 2GB+ RAM  
- 10GB+ 磁盘空间
- Ubuntu/CentOS/macOS

## 🔧 生产部署

### Nginx + Systemd (推荐)

系统已自动配置：
- Systemd服务：`model-evaluation.service`
- Nginx配置：`/etc/nginx/sites-available/model-evaluation`
- SSL支持：Let's Encrypt自动配置

### 管理命令

```bash
# 服务管理
sudo systemctl start model-evaluation    # 启动
sudo systemctl stop model-evaluation     # 停止  
sudo systemctl restart model-evaluation  # 重启
sudo systemctl status model-evaluation   # 状态

# 查看日志
sudo journalctl -u model-evaluation -f

# 备份数据
./backup.sh

# 更新应用
./update.sh
```

## 📊 功能概览

- ✅ **多模型评测**: Google Gemini, HKGAI-V1/V2
- ✅ **智能评分**: 自动评分 + 人工标注
- ✅ **结果分析**: 统计图表 + 性能对比
- ✅ **历史管理**: 结果存储 + 标签分类
- ✅ **数据导出**: 完整报告 + 筛选结果
- ✅ **实时更新**: 评分修改实时刷新

## 🔗 相关链接

- [详细部署文档](DEPLOYMENT.md)
- [功能说明文档](FEATURE_SUMMARY.md)
- [API配置指南](API_CONFIG_GUIDE.md)
- [问题反馈](https://github.com/your-repo/model-evaluation-web/issues)

---

🎉 **部署完成后，您就可以开始使用AI模型评测系统了！**
