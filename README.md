# 🚀 AI模型评测Web系统

一个功能强大且易于使用的AI模型评测系统，支持主观题和客观题评测，多模型对比分析。

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

##### 快速启动
```bash
# 1. 克隆项目
git clone https://github.com/your-repo/model-evaluation-web.git
cd model-evaluation-web

# 2. 一键启动 (自动创建环境并启动)
./start_conda.sh
```

##### 详细步骤
```bash
# 1. 克隆项目
git clone https://github.com/your-repo/model-evaluation-web.git
cd model-evaluation-web

# 2. 创建conda环境
conda env create -f environment.yml

# 3. 激活环境
conda activate model-evaluation-web

# 4. 配置环境变量
cp config.env.template .env
nano .env  # 编辑API密钥配置

# 5. 启动服务
python start.py
```

#### 方式2: 使用pip/venv

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/model-evaluation-web.git
cd model-evaluation-web

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp config.env.template .env
nano .env  # 编辑API密钥配置

# 5. 启动服务
python start.py
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

- **Python**: 3.8+ (推荐 3.9)
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
1. 启动系统：`python3 start.py`
2. 访问 http://localhost:5001
3. 在页面上输入API密钥并保存

#### 方法三：环境变量
```bash
export GOOGLE_API_KEY="your_api_key"
export ARK_API_KEY_HKGAI_V1="your_hkgai_v1_key"
export ARK_API_KEY_HKGAI_V2="your_hkgai_v2_key"
python3 start.py
```

## 🌐 访问系统

### 开发环境
- **主页**: http://localhost:5001
- **历史管理**: http://localhost:5001/history
- **手动标注**: http://localhost:5001/annotate/[result_id]

### 生产环境
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
├── app.py                 # 主应用程序
├── start.py              # 启动脚本
├── start_conda.sh        # Conda环境一键启动脚本
├── fix_environment.sh    # 环境修复脚本
├── database.py           # 数据库管理
├── history_manager.py    # 历史管理
├── comparison_analysis.py # 对比分析
├── environment.yml       # Conda环境配置
├── requirements.txt      # pip依赖配置
├── config.env.template   # 环境变量模板
├── templates/            # HTML模板
├── static/              # 静态资源
├── utils/               # 工具模块
├── data/                # 示例数据
├── results/             # 评测结果
├── results_history/     # 历史结果
├── TROUBLESHOOTING.md   # 问题解决指南
└── DEPLOYMENT.md        # 部署指南
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