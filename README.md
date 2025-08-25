# AI模型评测Web系统

一个功能强大且易于使用的AI模型评测系统，支持主观题和客观题评测，多模型对比分析。

## ✨ 主要特性

- 🎯 **智能评测模式**：自动识别主观题/客观题，或手动选择评测模式
- 🤖 **多模型支持**：支持HKGAI-V1、HKGAI-V2等多个模型，可灵活选择
- 📊 **美观的Web界面**：直观的步骤引导，实时进度显示
- 📈 **丰富的结果展示**：在线查看、筛选、排序，支持导出Excel
- ⚡ **高性能处理**：异步并发处理，支持大批量评测
- 🔍 **详细分析**：按类型统计，支持详细查看每个问题的评测结果

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Flask 2.3+
- pandas, aiohttp 等依赖包

### 安装步骤

1. **克隆项目**
```bash
cd /path/to/your/projects
git clone <repository-url>
cd model-evaluation-web
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置API密钥**
```bash
# 设置环境变量
export GOOGLE_API_KEY="your_google_api_key"
export ARK_API_KEY_HKGAI="your_hkgai_api_key"
```

4. **启动服务**
```bash
python app.py
```

5. **访问系统**
   打开浏览器访问：http://localhost:5000

## 📋 使用说明

### 1. 准备测试文件

#### 主观题评测文件格式：
```csv
query,type
写一首关于春天的诗,创意写作
请解释人工智能的基本概念,知识问答
如何看待远程工作的利弊,观点表达
```

#### 客观题评测文件格式：
```csv
query,answer,type
1+1等于几?,2,数学计算
中国的首都是哪里?,北京,地理知识
Python是哪一年发布的?,1991,技术知识
```

**必需列：**
- `query`：问题内容

**可选列：**
- `type`：问题类型（用于分类统计）
- `answer`：标准答案（客观题评测时需要）

### 2. 使用流程

1. **上传文件**：将Excel或CSV文件拖拽到上传区域
2. **选择模型**：勾选要评测的AI模型
3. **选择模式**：选择评测模式（自动检测/强制主观/强制客观）
4. **开始评测**：点击开始按钮，系统自动处理
5. **查看结果**：在线查看或下载Excel报告

### 3. 评测模式说明

- **主观题评测**：基于内容质量进行评分（0-5分）
  - 适用于：创意写作、观点表达、开放性问题等
  - 评分标准：逻辑性、完整性、创新性等

- **客观题评测**：基于标准答案进行准确性评分（0-5分）
  - 适用于：知识问答、数学计算、技术问题等
  - 评分标准：正确性、准确性、完整性等

## 📊 结果展示

### 统计概览
- 总题数、评测模型数量
- 按类型分布统计
- 模型评分统计

### 详细结果
- 支持搜索、筛选、排序
- 分页显示，可调整每页条数
- 点击展开查看完整答案和评测理由

### 导出功能
- Excel格式完整报告
- 包含所有原始数据和评测结果
- 支持筛选后导出

## 🔧 配置说明

### API密钥配置

系统需要以下API密钥：

1. **Google API Key**（必需）
   - 用于Gemini模型进行评测
   - 申请地址：https://ai.google.dev/

2. **HKGAI API Key**（必需）
   - 用于调用HKGAI模型获取答案
   - 联系HKGAI获取密钥

### 环境变量

```bash
# 必需
export GOOGLE_API_KEY="your_google_api_key"
export ARK_API_KEY_HKGAI="your_hkgai_api_key"

# 可选
export FLASK_DEBUG="True"
export MAX_CONCURRENT_REQUESTS="10"
export REQUEST_TIMEOUT="60"
```

## 📂 项目结构

```
model-evaluation-web/
├── app.py                 # Flask主应用
├── config.py              # 配置文件
├── requirements.txt       # 依赖包列表
├── templates/             # HTML模板
│   ├── index.html        # 主页
│   └── results.html      # 结果页
├── static/               # 静态文件
│   ├── css/
│   │   └── style.css     # 样式文件
│   └── js/
│       └── main.js       # 交互脚本
├── data/                 # 示例数据
│   ├── sample_subjective.csv
│   └── sample_objective.csv
├── uploads/              # 上传文件存储
├── results/              # 结果文件存储
└── README.md            # 说明文档
```

## 🧪 测试数据

系统提供了示例测试文件：

- `data/sample_subjective.csv`：主观题测试数据
- `data/sample_objective.csv`：客观题测试数据

可以直接使用这些文件测试系统功能。

## 🚨 常见问题

### Q: 上传文件后提示"缺少必需列"？
A: 请确保Excel文件包含`query`列，如果是客观题评测，还需要`answer`列。

### Q: 显示"模型不可用"？
A: 请检查是否正确设置了对应的API密钥环境变量。

### Q: 评测过程中出现超时？
A: 可以调整`REQUEST_TIMEOUT`环境变量增加超时时间，或减少并发数。

### Q: 如何添加新的AI模型？
A: 在`app.py`中的`SUPPORTED_MODELS`字典中添加新模型配置。

## 📝 更新日志

### v1.0.0 (2024-08-25)
- ✅ 完成基础评测功能
- ✅ 支持主观题/客观题评测
- ✅ 多模型选择和对比
- ✅ Web界面和结果展示
- ✅ 文件上传和导出功能

## 🤝 贡献

欢迎提交Issue和Pull Request来改进项目！

## 📄 许可证

MIT License

## 📞 联系方式

如有问题或建议，请联系开发者。
