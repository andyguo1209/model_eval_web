#!/bin/bash

# AI模型评测Web系统 - Conda环境启动脚本

echo "🐍 AI模型评测系统 - Conda环境启动"
echo "======================================"

# 检查conda是否安装
if ! command -v conda &> /dev/null; then
    echo "❌ 未检测到conda，请先安装Anaconda或Miniconda"
    echo "📥 下载链接: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# 初始化conda
eval "$(conda shell.bash hook)"

# 检查环境是否存在
if ! conda env list | grep -q "model-evaluation-web"; then
    echo "⚠️  未找到model-evaluation-web环境"
    echo "🔧 正在创建conda环境..."
    
    if [ -f "environment.yml" ]; then
        conda env create -f environment.yml
        if [ $? -ne 0 ]; then
            echo "❌ 环境创建失败"
            exit 1
        fi
    else
        echo "❌ 未找到environment.yml文件"
        exit 1
    fi
fi

# 激活环境
echo "🔗 激活conda环境: model-evaluation-web"
conda activate model-evaluation-web

# 检查环境是否正确激活
if [ "$CONDA_DEFAULT_ENV" != "model-evaluation-web" ]; then
    echo "❌ 环境激活失败"
    exit 1
fi

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到.env配置文件"
    if [ -f "config.env.template" ]; then
        echo "📝 创建.env配置文件模板..."
        cp config.env.template .env
        echo "✅ 已创建.env文件，请编辑填入您的API密钥"
        echo "   nano .env"
        echo ""
    fi
fi

# 验证关键依赖
echo "🧪 验证环境依赖..."
python -c "
try:
    import numpy as np
    import pandas as pd
    import flask
    print(f'✅ numpy: {np.__version__}')
    print(f'✅ pandas: {pd.__version__}')
    print(f'✅ flask: {flask.__version__}')
    print('✅ 环境验证成功！')
except ImportError as e:
    print(f'❌ 依赖验证失败: {e}')
    exit(1)
" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "❌ 环境验证失败，请重新创建环境"
    echo "   conda env remove -n model-evaluation-web"
    echo "   conda env create -f environment.yml"
    exit 1
fi

echo ""
echo "🚀 启动AI模型评测系统..."
echo "📍 当前环境: $CONDA_DEFAULT_ENV"
echo "🌐 访问地址: http://localhost:5001"
echo ""
echo "按 Ctrl+C 停止服务"
echo "================================="

# 启动系统
python start.py

# 脚本结束时的清理
echo ""
echo "👋 感谢使用AI模型评测系统"
echo "💡 环境仍保持激活状态，可继续使用"
echo "   - 停用环境: conda deactivate"
echo "   - 重新启动: ./start_conda.sh"
