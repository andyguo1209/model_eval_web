#!/bin/bash

# AI模型评测Web系统 - 可选依赖安装脚本

echo "📦 AI模型评测系统 - 可选依赖安装工具"
echo "================================================"

# 定义可选依赖组
declare -A DEPS=(
    ["perf"]="psutil==5.9.5 memory-profiler==0.61.0 line-profiler==4.1.1"
    ["viz"]="matplotlib==3.7.2 seaborn==0.12.2 plotly==5.15.0"
    ["dev"]="jupyter==1.0.0 ipython==8.14.0 pytest==7.4.0 pytest-cov==4.1.0 black==23.7.0 flake8==6.0.0"
    ["analytics"]="scipy==1.11.1 scikit-learn==1.3.0 networkx==3.1"
    ["i18n"]="babel==2.12.1 flask-babel==3.1.0"
    ["export"]="xlsxwriter==3.1.2 reportlab==4.0.4"
    ["async"]="asyncio==3.4.3 uvloop==0.17.0"
    ["cache"]="redis==4.6.0 flask-caching==2.0.2"
    ["security"]="cryptography==41.0.3 flask-limiter==3.3.1 flask-cors==4.0.0"
    ["monitoring"]="prometheus-client==0.17.1 flask-prometheus-metrics==1.0.0"
)

declare -A DESC=(
    ["perf"]="性能分析和系统监控"
    ["viz"]="高级图表和数据可视化"
    ["dev"]="开发调试和测试"
    ["analytics"]="高级统计分析"
    ["i18n"]="多语言界面支持"
    ["export"]="增强数据导出功能"
    ["async"]="高级并发处理"
    ["cache"]="Redis缓存支持"
    ["security"]="安全增强功能"
    ["monitoring"]="系统监控功能"
)

# 显示可用的依赖组
show_available() {
    echo "🎯 可用的功能模块："
    echo ""
    local i=1
    for key in "${!DEPS[@]}"; do
        echo "$i) $key - ${DESC[$key]}"
        ((i++))
    done
    echo ""
    echo "a) all - 安装全部可选依赖"
    echo "q) quit - 退出"
    echo ""
}

# 安装指定依赖组
install_deps() {
    local group=$1
    if [[ -n "${DEPS[$group]}" ]]; then
        echo "📦 安装 $group (${DESC[$group]})..."
        echo "依赖包: ${DEPS[$group]}"
        echo ""
        pip install ${DEPS[$group]}
        if [ $? -eq 0 ]; then
            echo "✅ $group 依赖安装成功！"
        else
            echo "❌ $group 依赖安装失败"
            return 1
        fi
    else
        echo "❌ 未知的依赖组: $group"
        return 1
    fi
}

# 安装全部依赖
install_all() {
    echo "📦 安装全部可选依赖..."
    if [ -f "requirements-optional.txt" ]; then
        pip install -r requirements-optional.txt
        if [ $? -eq 0 ]; then
            echo "✅ 全部可选依赖安装成功！"
        else
            echo "❌ 可选依赖安装失败"
            return 1
        fi
    else
        echo "❌ 未找到 requirements-optional.txt 文件"
        return 1
    fi
}

# 检查pip
if ! command -v pip &> /dev/null; then
    echo "❌ 未找到pip，请先安装Python和pip"
    exit 1
fi

# 主循环
while true; do
    show_available
    read -p "请选择要安装的功能模块 (输入名称或编号): " choice
    
    case $choice in
        "q"|"quit")
            echo "👋 退出安装工具"
            break
            ;;
        "a"|"all")
            install_all
            echo ""
            ;;
        "perf"|"1")
            install_deps "perf"
            echo ""
            ;;
        "viz"|"2")
            install_deps "viz"
            echo ""
            ;;
        "dev"|"3")
            install_deps "dev"
            echo ""
            ;;
        "analytics"|"4")
            install_deps "analytics"
            echo ""
            ;;
        "i18n"|"5")
            install_deps "i18n"
            echo ""
            ;;
        "export"|"6")
            install_deps "export"
            echo ""
            ;;
        "async"|"7")
            install_deps "async"
            echo ""
            ;;
        "cache"|"8")
            install_deps "cache"
            echo ""
            ;;
        "security"|"9")
            install_deps "security"
            echo ""
            ;;
        "monitoring"|"10")
            install_deps "monitoring"
            echo ""
            ;;
        *)
            # 尝试直接安装输入的依赖组名
            if [[ -n "${DEPS[$choice]}" ]]; then
                install_deps "$choice"
                echo ""
            else
                echo "❌ 无效选择: $choice"
                echo ""
            fi
            ;;
    esac
done

echo "🎉 可选依赖安装完成！"
echo ""
echo "💡 使用提示："
echo "- 查看已安装包: pip list"
echo "- 启动系统: python start.py"
echo "- 环境问题: ./fix_environment.sh"
