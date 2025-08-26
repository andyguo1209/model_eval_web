#!/bin/bash

# AI模型评测Web系统 - 环境修复脚本
# 解决常见的部署环境问题

echo "🔧 AI模型评测系统环境修复工具"
echo "========================================"

# 检查Python版本
echo "📋 检查Python版本..."
python_version=$(python3 --version 2>&1 | cut -d " " -f 2)
echo "当前Python版本: $python_version"

# 检查pip
echo "📋 检查pip..."
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3未安装，请先安装pip"
    exit 1
fi

# 修复numpy/pandas兼容性问题
echo "🔧 修复numpy/pandas兼容性问题..."
echo "卸载可能冲突的包..."
pip3 uninstall -y numpy pandas -q 2>/dev/null || true

echo "安装兼容的numpy版本..."
pip3 install "numpy>=1.21.0,<1.25.0" --force-reinstall

echo "安装pandas..."
pip3 install "pandas==2.0.3" --force-reinstall

echo "安装其他依赖..."
pip3 install Flask==2.3.3
pip3 install aiohttp==3.8.5
pip3 install google-generativeai==0.7.2
pip3 install openpyxl==3.1.2
pip3 install Werkzeug==2.3.7
pip3 install python-dotenv==1.0.0

# 创建.env文件模板
echo "📝 创建.env配置文件..."
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# AI模型评测系统配置文件
# 请填入您的API密钥

# Google Gemini API密钥 (必需)
# 获取地址: https://makersuite.google.com/
GOOGLE_API_KEY=""

# HKGAI模型API密钥 (可选)
ARK_API_KEY_HKGAI_V1=""
ARK_API_KEY_HKGAI_V2=""

# Flask配置 (可选)
SECRET_KEY="model-evaluation-web-2024"
FLASK_DEBUG="True"

# 文件上传配置 (可选)
MAX_CONTENT_LENGTH="16777216"
UPLOAD_TIMEOUT="300"

# 并发配置 (可选)
MAX_CONCURRENT_REQUESTS="10"
REQUEST_TIMEOUT="60"
EOF
    echo "✅ 已创建 .env 配置文件"
else
    echo "⚠️  .env 文件已存在，跳过创建"
fi

# 创建必要目录
echo "📁 创建必要目录..."
mkdir -p uploads results data static/css static/js templates results_history

# 验证安装
echo "🧪 验证安装..."
python3 -c "
import numpy as np
import pandas as pd
import flask
print(f'✅ numpy: {np.__version__}')
print(f'✅ pandas: {pd.__version__}')
print(f'✅ flask: {flask.__version__}')
print('✅ 所有依赖包安装成功！')
" 2>/dev/null

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 环境修复完成！"
    echo ""
    echo "📋 下一步："
    echo "1. 编辑 .env 文件，填入您的API密钥"
    echo "   nano .env"
    echo ""
    echo "2. 启动系统"
    echo "   python3 start.py"
    echo ""
    echo "3. 访问系统"
    echo "   http://localhost:5001"
    echo ""
    echo "💡 提示: 如果没有API密钥，系统仍可启动，您可以在Web界面中配置"
else
    echo "❌ 环境验证失败，请检查错误信息"
    exit 1
fi
