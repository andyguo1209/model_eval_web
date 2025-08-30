#!/bin/bash

# 模型评测Web系统后台启动脚本
# 使用方法: ./start_background.sh [start|stop|restart|status]

# ========== 配置区域 ==========
APP_DIR="/Users/guozhenhua/PycharmProjects/model-evaluation-web"  # 项目路径
ENV_PATH="$HOME/miniconda3"                                       # Conda路径（如果使用Conda）
ENV_NAME="myenv"                                                  # 虚拟环境名称
PYTHON_PATH="python3"                                             # Python可执行文件路径
APP_MODULE="app.py"                                               # 应用模块
HOST="0.0.0.0"                                                    # 绑定地址
PORT="8080"                                                       # 绑定端口

# 日志配置
LOG_DIR="$APP_DIR/logs"
ACCESS_LOG="$LOG_DIR/access.log"
ERROR_LOG="$LOG_DIR/error.log"
APP_LOG="$LOG_DIR/app.log"
PID_FILE="$APP_DIR/app.pid"

# ========== 函数定义 ==========

# 初始化日志目录
init_logs() {
    if [ ! -d "$LOG_DIR" ]; then
        mkdir -p "$LOG_DIR"
        echo "✅ 创建日志目录: $LOG_DIR"
    fi
}

# 检测虚拟环境类型和激活
activate_env() {
    echo "🔧 检测和激活虚拟环境..."
    
    # 检测是否使用Conda
    if [ -f "$ENV_PATH/bin/activate" ] && [ -d "$ENV_PATH/envs/$ENV_NAME" ]; then
        echo "📦 使用Conda环境: $ENV_NAME"
        source "$ENV_PATH/bin/activate"
        conda activate "$ENV_NAME"
        return 0
    fi
    
    # 检测是否使用venv
    if [ -f "$APP_DIR/venv/bin/activate" ]; then
        echo "📦 使用venv环境"
        source "$APP_DIR/venv/bin/activate"
        return 0
    fi
    
    # 检测是否有requirements.txt，提示安装依赖
    if [ -f "$APP_DIR/requirements.txt" ]; then
        echo "⚠️  未找到虚拟环境，使用系统Python环境"
        echo "💡 建议先创建虚拟环境：python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    fi
}

# 启动应用
start() {
    echo "🚀 启动模型评测Web系统..."
    
    # 检查是否已经在运行
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "❌ 应用已在运行 (PID: $PID)"
            return 1
        else
            echo "🧹 删除过时的PID文件"
            rm -f "$PID_FILE"
        fi
    fi
    
    # 切换到应用目录
    cd "$APP_DIR" || {
        echo "❌ 无法切换到应用目录: $APP_DIR"
        exit 1
    }
    
    # 初始化日志
    init_logs
    
    # 激活虚拟环境
    activate_env
    
    # 设置环境变量（可选）
    export FLASK_ENV=production
    export FLASK_APP=app.py
    
    # 启动应用（后台运行）
    echo "📋 启动参数："
    echo "   - 应用目录: $APP_DIR"
    echo "   - 监听地址: $HOST:$PORT"
    echo "   - 访问日志: $ACCESS_LOG"
    echo "   - 错误日志: $ERROR_LOG"
    echo "   - 应用日志: $APP_LOG"
    echo "   - PID文件: $PID_FILE"
    
    # 启动方式1：直接使用Python运行（推荐用于开发环境）
    nohup $PYTHON_PATH "$APP_MODULE" > "$APP_LOG" 2>&1 &
    APP_PID=$!
    
    # 启动方式2：使用Gunicorn运行（取消注释以使用，适合生产环境）
    # nohup gunicorn --bind $HOST:$PORT --workers 4 --access-logfile "$ACCESS_LOG" --error-logfile "$ERROR_LOG" app:app > "$APP_LOG" 2>&1 &
    # APP_PID=$!
    
    # 保存PID
    echo $APP_PID > "$PID_FILE"
    
    # 等待应用启动
    sleep 3
    
    # 检查启动状态
    if ps -p $APP_PID > /dev/null 2>&1; then
        echo "✅ 应用启动成功!"
        echo "🌐 访问地址: http://localhost:$PORT"
        echo "📊 PID: $APP_PID"
        echo "📋 日志文件:"
        echo "   - 应用日志: tail -f $APP_LOG"
        echo "   - 错误日志: tail -f $ERROR_LOG"
    else
        echo "❌ 应用启动失败，请检查日志: $APP_LOG"
        rm -f "$PID_FILE"
        return 1
    fi
}

# 停止应用
stop() {
    echo "🛑 停止模型评测Web系统..."
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "📋 停止进程 (PID: $PID)"
            kill -TERM $PID
            
            # 等待进程优雅退出
            for i in {1..10}; do
                if ! ps -p $PID > /dev/null 2>&1; then
                    echo "✅ 应用已停止"
                    rm -f "$PID_FILE"
                    return 0
                fi
                sleep 1
            done
            
            # 强制杀死进程
            echo "⚠️  强制停止进程"
            kill -KILL $PID 2>/dev/null || true
            rm -f "$PID_FILE"
            echo "✅ 应用已强制停止"
        else
            echo "⚠️  PID文件存在但进程未运行"
            rm -f "$PID_FILE"
        fi
    else
        echo "⚠️  未找到PID文件，应用可能未运行"
    fi
}

# 重启应用
restart() {
    echo "🔄 重启模型评测Web系统..."
    stop
    sleep 2
    start
}

# 查看状态
status() {
    echo "📊 模型评测Web系统状态:"
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "✅ 应用正在运行 (PID: $PID)"
            
            # 显示进程信息
            echo "📋 进程信息:"
            ps -p $PID -o pid,ppid,etime,cmd
            
            # 显示端口占用情况
            echo "🌐 端口占用:"
            netstat -tlnp 2>/dev/null | grep ":$PORT " || echo "   未检测到端口占用"
            
            # 显示最近的日志
            if [ -f "$APP_LOG" ]; then
                echo "📋 最近的应用日志:"
                tail -5 "$APP_LOG"
            fi
        else
            echo "❌ PID文件存在但进程未运行"
            echo "🧹 清理PID文件: $PID_FILE"
            rm -f "$PID_FILE"
        fi
    else
        echo "❌ 应用未运行（未找到PID文件）"
    fi
}

# 显示日志
logs() {
    echo "📋 实时查看应用日志 (Ctrl+C退出):"
    if [ -f "$APP_LOG" ]; then
        tail -f "$APP_LOG"
    else
        echo "❌ 日志文件不存在: $APP_LOG"
    fi
}

# 显示帮助信息
help() {
    echo "模型评测Web系统后台启动脚本"
    echo ""
    echo "使用方法:"
    echo "  $0 [命令]"
    echo ""
    echo "可用命令:"
    echo "  start    - 启动应用"
    echo "  stop     - 停止应用"
    echo "  restart  - 重启应用"
    echo "  status   - 查看运行状态"
    echo "  logs     - 实时查看日志"
    echo "  help     - 显示此帮助信息"
    echo ""
    echo "配置说明:"
    echo "  - 修改脚本顶部的配置区域来调整启动参数"
    echo "  - 日志文件位于 $LOG_DIR 目录"
    echo "  - PID文件: $PID_FILE"
    echo ""
    echo "示例:"
    echo "  $0 start          # 启动应用"
    echo "  $0 status         # 查看状态"
    echo "  $0 logs           # 查看日志"
    echo "  $0 stop           # 停止应用"
}

# ========== 主程序 ==========

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    help|--help|-h)
        help
        ;;
    *)
        echo "❌ 未知命令: $1"
        echo "💡 使用 '$0 help' 查看帮助信息"
        exit 1
        ;;
esac
