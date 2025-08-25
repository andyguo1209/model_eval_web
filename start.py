#!/usr/bin/env python3
"""
AI模型评测系统启动脚本
"""

import os
import sys
from config import check_api_keys
from utils.env_manager import env_manager

def print_banner():
    """打印启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                     AI模型评测Web系统                        ║
║                   Model Evaluation System                   ║
╠══════════════════════════════════════════════════════════════╣
║  功能特性：                                                   ║
║  • 支持主观题/客观题评测                                      ║
║  • 多模型对比分析                                            ║
║  • 美观的Web界面                                             ║
║  • 实时进度监控                                              ║
║  • 结果在线查看和导出                                         ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)

def check_dependencies():
    """检查依赖包"""
    required_packages = {
        'flask': 'flask',
        'pandas': 'pandas', 
        'aiohttp': 'aiohttp',
        'google-generativeai': 'google.generativeai',
        'openpyxl': 'openpyxl',
        'werkzeug': 'werkzeug'
    }
    
    missing_packages = []
    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
    
    if missing_packages:
        print("❌ 缺少依赖包:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n请运行以下命令安装依赖:")
        print("pip install -r requirements.txt")
        return False
    
    return True

def check_environment():
    """检查环境配置"""
    print("🔧 检查环境配置...")
    
    # 检查API密钥
    missing_keys = check_api_keys()
    if missing_keys:
        print("⚠️  缺少以下API密钥:")
        for key in missing_keys:
            print(f"   - {key}")
        print("\n请设置环境变量:")
        for key in missing_keys:
            print(f"export {key}='your_api_key_here'")
        print("\n或者在运行前临时设置:")
        for key in missing_keys:
            print(f"{key}='your_api_key_here' python start.py")
        return False
    
    print("✅ API密钥配置完成")
    return True

def check_directories():
    """检查和创建必要目录"""
    print("📁 检查目录结构...")
    
    directories = ['uploads', 'results', 'data', 'static/css', 'static/js', 'templates']
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"   📂 创建目录: {directory}")
    
    print("✅ 目录结构检查完成")

def show_usage_tips():
    """显示使用提示"""
    print("\n📋 使用提示:")
    print("1. 准备测试文件（Excel/CSV格式）")
    print("   - 主观题：包含 query, type 列")
    print("   - 客观题：包含 query, answer, type 列")
    print("2. 访问 http://localhost:5000")
    print("3. 按照页面引导完成评测")
    print("4. 查看结果或下载报告")
    
    print("\n📊 示例数据:")
    if os.path.exists('data/sample_subjective.csv'):
        print("   📄 主观题示例: data/sample_subjective.csv")
    if os.path.exists('data/sample_objective.csv'):
        print("   📄 客观题示例: data/sample_objective.csv")

def main():
    """主函数"""
    print_banner()
    
    print("🚀 正在启动AI模型评测系统...")
    
    # 首先加载.env文件中的环境变量
    print("📁 加载本地配置...")
    env_vars = env_manager.load_env()
    if env_vars:
        api_keys = [k for k in env_vars.keys() if 'API_KEY' in k]
        if api_keys:
            print(f"✅ 从.env文件加载了 {len(api_keys)} 个API密钥")
            for key in api_keys:
                print(f"   - {key}: ****")
        else:
            print(f"📄 从.env文件加载了 {len(env_vars)} 个配置项")
    else:
        print("📄 未找到.env文件或文件为空")
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查目录
    check_directories()
    
    # 检查环境（非阻塞）
    if not check_environment():
        print("\n⚠️  API密钥未配置，部分功能可能无法使用")
        print("💡 提示：您可以通过Web界面的'API配置'按钮保存密钥到本地文件")
        print("系统仍将启动，请在使用前配置API密钥")
    
    # 显示使用提示
    show_usage_tips()
    
    print("\n🌐 启动Web服务...")
    print("访问地址: http://localhost:5001")
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    
    # 启动Flask应用
    try:
        from app import app
        app.run(debug=True, host='0.0.0.0', port=5001)
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
