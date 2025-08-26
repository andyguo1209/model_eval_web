#!/bin/bash

# AI模型评测Web系统 - 环境修复脚本
# 解决常见的部署环境问题

echo "🔧 AI模型评测系统环境修复工具"
echo "========================================"

# 检查是否安装了conda
echo "🔍 检查环境管理工具..."
CONDA_AVAILABLE=false
PIP_AVAILABLE=false

if command -v conda &> /dev/null; then
    CONDA_AVAILABLE=true
    echo "✅ 发现Conda环境管理器"
    conda_version=$(conda --version 2>&1)
    echo "   $conda_version"
fi

if command -v pip3 &> /dev/null; then
    PIP_AVAILABLE=true
    echo "✅ 发现pip包管理器"
fi

# 用户选择环境管理方式
if [ "$CONDA_AVAILABLE" = true ]; then
    echo ""
    echo "🎯 选择环境管理方式:"
    echo "1) 使用Conda管理环境 (推荐)"
    echo "2) 使用pip/venv管理环境"
    echo "3) 自动选择"
    
    read -p "请选择 (1-3, 默认为1): " choice
    case $choice in
        2)
            USE_CONDA=false
            ;;
        3)
            USE_CONDA=true
            ;;
        *)
            USE_CONDA=true
            ;;
    esac
else
    if [ "$PIP_AVAILABLE" = false ]; then
        echo "❌ 未发现conda或pip，请先安装Python环境管理工具"
        exit 1
    fi
    USE_CONDA=false
    echo "📋 将使用pip/venv环境管理"
fi

# 检查Python版本
echo ""
echo "📋 检查Python版本..."
python_version=$(python3 --version 2>&1 | cut -d " " -f 2)
echo "当前Python版本: $python_version"

# 环境设置和依赖安装
echo ""
if [ "$USE_CONDA" = true ]; then
    echo "🐍 使用Conda环境管理"
    
    # 检查是否已存在环境
    if conda env list | grep -q "model-evaluation-web"; then
        echo "⚠️  发现已存在的conda环境: model-evaluation-web"
        read -p "是否删除并重新创建? (y/N): " recreate
        if [[ $recreate =~ ^[Yy]$ ]]; then
            echo "🗑️  删除现有环境..."
            conda env remove -n model-evaluation-web -y
        else
            echo "📦 更新现有环境..."
            conda env update -f environment.yml
            if [ $? -eq 0 ]; then
                echo "✅ 环境更新成功"
            else
                echo "❌ 环境更新失败，尝试重新创建..."
                conda env remove -n model-evaluation-web -y
                conda env create -f environment.yml
            fi
        fi
    else
        echo "📦 创建新的conda环境..."
        echo "💡 建议使用Python 3.10以获得最佳兼容性"
        conda env create -f environment.yml
    fi
    
    if [ $? -eq 0 ]; then
        echo "✅ Conda环境创建/更新成功"
        echo "🔧 激活环境进行验证..."
        
        # 激活环境并验证
        source $(conda info --base)/etc/profile.d/conda.sh
        conda activate model-evaluation-web
        
        # 验证关键包
        python -c "
import numpy as np
import pandas as pd
import flask
print(f'✅ numpy: {np.__version__}')
print(f'✅ pandas: {pd.__version__}')
print(f'✅ flask: {flask.__version__}')
print('✅ Conda环境验证成功！')
" 2>/dev/null
        
        INSTALL_SUCCESS=$?
    else
        echo "❌ Conda环境创建失败，回退到pip安装"
        USE_CONDA=false
    fi
fi

if [ "$USE_CONDA" = false ]; then
    echo "📦 使用pip/venv环境管理"
    
    # 创建虚拟环境
    if [ ! -d "venv" ]; then
        echo "🐍 创建Python虚拟环境..."
        python3 -m venv venv
    fi
    
    echo "🔗 激活虚拟环境..."
    source venv/bin/activate
    
    # 修复numpy/pandas兼容性问题
    echo "🔧 修复numpy/pandas兼容性问题..."
    echo "卸载可能冲突的包..."
    pip uninstall -y numpy pandas -q 2>/dev/null || true

    echo "安装兼容的numpy版本..."
    pip install "numpy>=1.21.0,<1.25.0" --force-reinstall

    echo "安装pandas..."
    pip install "pandas==2.0.3" --force-reinstall

    echo "安装其他依赖..."
    pip install Flask==2.3.3
    pip install aiohttp==3.8.5
    pip install google-generativeai==0.7.2
    pip install openpyxl==3.1.2
    pip install Werkzeug==2.3.7
    pip install python-dotenv==1.0.0
    
    # 验证安装
    python -c "
import numpy as np
import pandas as pd
import flask
print(f'✅ numpy: {np.__version__}')
print(f'✅ pandas: {pd.__version__}')
print(f'✅ flask: {flask.__version__}')
print('✅ pip环境验证成功！')
" 2>/dev/null
    
    INSTALL_SUCCESS=$?
fi

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

if [ $INSTALL_SUCCESS -eq 0 ]; then
    echo ""
    echo "🎉 环境修复完成！"
    echo ""
    echo "📋 下一步："
    echo "1. 编辑 .env 文件，填入您的API密钥"
    echo "   nano .env"
    echo ""
    if [ "$USE_CONDA" = true ]; then
        echo "2. 激活conda环境"
        echo "   conda activate model-evaluation-web"
        echo ""
        echo "3. 启动系统"
        echo "   python start.py"
        echo ""
        echo "4. 访问系统"
        echo "   http://localhost:5001"
        echo ""
        echo "💡 环境管理命令:"
        echo "   - 激活环境: conda activate model-evaluation-web"
        echo "   - 停用环境: conda deactivate"
        echo "   - 删除环境: conda env remove -n model-evaluation-web"
        echo "   - 更新环境: conda env update -f environment.yml"
    else
        echo "2. 激活虚拟环境"
        echo "   source venv/bin/activate"
        echo ""
        echo "3. 启动系统"
        echo "   python start.py"
        echo ""
        echo "4. 访问系统"
        echo "   http://localhost:5001"
        echo ""
        echo "💡 环境管理命令:"
        echo "   - 激活环境: source venv/bin/activate"
        echo "   - 停用环境: deactivate"
        echo "   - 删除环境: rm -rf venv"
    fi
    echo ""
    echo "💡 提示: 如果没有API密钥，系统仍可启动，您可以在Web界面中配置"
else
    echo "❌ 环境验证失败，请检查错误信息"
    exit 1
fi
