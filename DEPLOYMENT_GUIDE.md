# 🚀 高级AI模型评测系统 - 部署指南

## 📋 系统要求

### 环境依赖
- **Python**: 3.8+
- **操作系统**: Windows/macOS/Linux
- **内存**: 最低4GB，推荐8GB+
- **存储**: 最低1GB可用空间

### Python包依赖
```bash
Flask>=2.3.0
pandas>=1.5.0
numpy>=1.21.0
aiohttp>=3.8.0
google-generativeai>=0.3.0
sqlite3 (Python内置)
```

## 🔧 快速部署

### 1. 克隆项目
```bash
# 克隆项目（高级功能分支）
git clone https://github.com/andyguo1209/model_eval_web.git
cd model_eval_web
git checkout feature/advanced-evaluation-system

# 或者直接克隆指定分支
git clone -b feature/advanced-evaluation-system https://github.com/andyguo1209/model_eval_web.git
cd model_eval_web
```

### 2. 创建虚拟环境
```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
# macOS/Linux:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 配置API密钥
创建 `.env` 文件并配置API密钥：
```bash
# 创建配置文件
touch .env

# 编辑配置文件，添加以下内容：
GOOGLE_API_KEY=your_google_gemini_api_key
ARK_API_KEY_HKGAI_V1=your_hkgai_v1_key
ARK_API_KEY_HKGAI_V2=your_hkgai_v2_key
```

### 5. 初始化数据库
```bash
# 初始化数据库（自动创建表结构）
python3 database.py
```

### 6. 启动系统
```bash
# 使用启动脚本（推荐）
python3 start.py

# 或者直接启动Flask应用
python3 app.py
```

### 7. 访问系统
打开浏览器访问：http://localhost:5001

## 🎯 功能使用指南

### 基础评测功能
1. **上传数据文件**
   - 支持CSV/Excel格式
   - 客观题需包含：query, answer, type列
   - 主观题需包含：query, type列

2. **选择评测模型**
   - Google Gemini（需配置API Key）
   - HKGAI-V1/V2（需配置API Key）

3. **开始评测**
   - 自动检测评测模式
   - 实时显示评测进度
   - 生成详细评测报告

### 高级功能使用

#### 📊 历史管理
- **访问路径**: http://localhost:5001/history
- **功能**:
  - 查看所有历史评测记录
  - 按时间、模型、标签筛选
  - 下载历史结果文件
  - 删除不需要的记录
  - 查看详细统计信息

#### 🏷️ 人工标注
- **访问方式**: 在历史记录中点击"标注"按钮
- **标注维度**:
  - 正确性评分（1-5分）
  - 相关性评分（1-5分）
  - 安全性评分（1-5分）
  - 创造性评分（1-5分）
  - 逻辑一致性（是/否）

- **快捷操作**:
  - 数字键1-5：快速评分
  - 方向键←→：切换题目
  - Ctrl+S：保存标注

#### 📈 对比分析
- **模型对比**: 选择多个评测结果进行横向对比
- **趋势分析**: 查看模型性能随时间变化
- **性能报告**: 生成综合性能分析报告

## 🔧 系统配置

### 数据库配置
系统默认使用SQLite数据库，文件位于 `evaluation_system.db`

如需使用其他数据库，修改 `database.py` 中的连接配置：
```python
# 修改DATABASE_PATH变量
DATABASE_PATH = 'your_custom_database.db'
```

### 存储配置
- **上传文件**: `uploads/` 目录
- **结果文件**: `results/` 目录  
- **历史文件**: `results_history/` 目录
- **归档文件**: `results_history/archived/` 目录

### API配置
在 `app.py` 中的 `SUPPORTED_MODELS` 字典可添加新的模型：
```python
SUPPORTED_MODELS = {
    "NEW_MODEL": {
        "url": "your_api_endpoint",
        "model": "model_name",
        "token_env": "YOUR_API_KEY_ENV",
        "headers_template": {
            "Content-Type": "application/json"
        }
    }
}
```

## 🚀 生产环境部署

### 使用Gunicorn（推荐）
```bash
# 安装Gunicorn
pip install gunicorn

# 启动生产服务器
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

### 使用Docker部署
```dockerfile
# Dockerfile示例
FROM python:3.9-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt
RUN python3 database.py

EXPOSE 5001
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "app:app"]
```

### Nginx反向代理
```nginx
server {
    listen 80;
    server_name your_domain.com;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🔒 安全配置

### 1. API密钥安全
- 不要将API密钥提交到代码仓库
- 使用环境变量或配置文件管理密钥
- 定期轮换API密钥

### 2. 文件上传安全
- 系统已内置文件类型检查
- 文件名安全处理（使用secure_filename）
- 建议设置文件大小限制

### 3. 数据库安全
- 定期备份数据库文件
- 设置适当的文件权限
- 考虑数据加密（生产环境）

## 📊 性能优化

### 1. 数据库优化
- 定期执行数据归档（自动/手动）
- 清理无用的临时文件
- 监控数据库大小

### 2. 并发优化
- 使用异步处理评测任务
- 配置适当的worker数量
- 监控内存使用情况

### 3. 缓存策略
- 静态文件缓存
- API响应缓存
- 数据库查询缓存

## 🐛 故障排除

### 常见问题

#### 1. 端口占用
```bash
# 查看端口占用
lsof -ti:5001 | xargs kill -9

# 或修改端口
python3 start.py --port 5002
```

#### 2. API密钥错误
- 检查 `.env` 文件是否存在
- 验证API密钥格式和有效性
- 查看启动日志中的密钥加载信息

#### 3. 数据库错误
```bash
# 重新初始化数据库
rm evaluation_system.db
python3 database.py
```

#### 4. 依赖包冲突
```bash
# 重新创建虚拟环境
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 日志查看
- 应用日志：控制台输出
- 错误日志：检查Python错误信息
- 访问日志：浏览器开发者工具

## 📞 技术支持

### 联系方式
- **GitHub**: https://github.com/andyguo1209/model_eval_web
- **Issues**: 在GitHub仓库提交Issue
- **文档**: 查看项目README和功能文档

### 社区支持
- 查看已有Issues寻找解决方案
- 参与Discussions讨论
- 贡献代码和文档改进

---

## 🎉 祝您使用愉快！

这是一个功能完整、专业可靠的AI模型评测平台。如有任何问题，欢迎随时联系或提交Issue。
