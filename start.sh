#!/bin/bash

# 快速启动脚本 - 模型评测Web系统
# 使用方法: ./start.sh [options]

echo "🚀 模型评测Web系统快速启动"

# 切换到脚本所在目录
cd "$(dirname "$0")" || exit 1

# 默认配置
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-"8080"}
ENV_NAME=${ENV_NAME:-"myenv"}

# 日志开关配置（可通过环境变量控制）
if [ -z "$ENABLE_VERBOSE_LOGGING" ]; then
    echo "💡 日志输出控制："
    echo "   - 启用详细日志：ENABLE_VERBOSE_LOGGING=true ./start.sh"
    echo "   - 禁用详细日志：ENABLE_VERBOSE_LOGGING=false ./start.sh"
    echo "   - 也可在管理后台 > 系统配置中动态调整"
fi

# 检测并激活Python环境
activate_python_env() {
    # 检查是否在虚拟环境中
    if [ -n "$VIRTUAL_ENV" ]; then
        echo "✅ 已在虚拟环境中: $(basename $VIRTUAL_ENV)"
        return 0
    fi
    
    # 尝试激活conda环境
    if command -v conda &> /dev/null; then
        echo "📦 尝试激活Conda环境: $ENV_NAME"
        source "$(conda info --base)/etc/profile.d/conda.sh"
        conda activate "$ENV_NAME" 2>/dev/null || echo "⚠️  Conda环境激活失败，使用系统Python"
        return 0
    fi
    
    # 尝试激活venv环境
    if [ -f "venv/bin/activate" ]; then
        echo "📦 激活venv环境"
        source venv/bin/activate
        return 0
    fi
    
    echo "⚠️  未检测到虚拟环境，使用系统Python"
}

# 检查依赖
check_dependencies() {
    echo "🔍 检查Python依赖..."
    
    if ! python3 -c "import flask" &> /dev/null; then
        echo "❌ 缺少Flask依赖"
        if [ -f "requirements.txt" ]; then
            echo "💡 请先安装依赖: pip install -r requirements.txt"
        fi
        exit 1
    fi
    
    echo "✅ 依赖检查通过"
}

# 显示配置信息
show_config() {
    echo ""
    echo "📋 启动配置:"
    echo "   🌐 监听地址: http://$HOST:$PORT"
    echo "   📁 工作目录: $(pwd)"
    echo "   🐍 Python版本: $(python3 --version 2>/dev/null || echo '未知')"
    echo "   🔍 详细日志: ${ENABLE_VERBOSE_LOGGING:-'默认(启用)'}"
    
    if [ -n "$VIRTUAL_ENV" ]; then
        echo "   📦 虚拟环境: $(basename $VIRTUAL_ENV)"
    fi
    
    echo ""
}

# 主启动函数
main() {
    # 处理参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --port|-p)
                PORT="$2"
                shift 2
                ;;
            --host|-h)
                HOST="$2"
                shift 2
                ;;
            --verbose|-v)
                export ENABLE_VERBOSE_LOGGING=true
                shift
                ;;
            --quiet|-q)
                export ENABLE_VERBOSE_LOGGING=false
                shift
                ;;
            --help)
                echo "使用方法: $0 [options]"
                echo ""
                echo "选项:"
                echo "  -p, --port PORT     指定端口 (默认: 8080)"
                echo "  -h, --host HOST     指定主机 (默认: 0.0.0.0)"
                echo "  -v, --verbose       启用详细日志"
                echo "  -q, --quiet         禁用详细日志"
                echo "      --help          显示帮助信息"
                echo ""
                echo "环境变量:"
                echo "  ENABLE_VERBOSE_LOGGING=true|false  控制日志详细程度"
                echo "  HOST=0.0.0.0                       监听地址"
                echo "  PORT=8080                           监听端口"
                echo "  ENV_NAME=myenv                      Conda环境名称"
                echo ""
                echo "示例:"
                echo "  $0                    # 默认启动"
                echo "  $0 -p 9000           # 指定端口"
                echo "  $0 --verbose         # 启用详细日志"
                echo "  $0 --quiet           # 禁用详细日志"
                exit 0
                ;;
            *)
                echo "❌ 未知参数: $1"
                echo "💡 使用 '$0 --help' 查看帮助"
                exit 1
                ;;
        esac
    done
    
    # 激活Python环境
    activate_python_env
    
    # 检查依赖
    check_dependencies
    
    # 显示配置
    show_config
    
    # 设置Flask环境变量
    export FLASK_APP=app.py
    export HOST=$HOST
    export PORT=$PORT
    
    # 启动应用
    echo "🎬 启动应用中..."
    echo "🚪 按 Ctrl+C 停止服务"
    echo "=================================================="
    
    # 使用Flask开发服务器启动
    python3 app.py
}

# 捕获Ctrl+C信号
trap 'echo -e "\n🛑 收到停止信号，正在关闭服务..."; exit 0' INT

# 运行主函数
main "$@"
