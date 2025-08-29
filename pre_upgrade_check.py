#!/usr/bin/env python3
"""
🔍 升级前检查脚本
检查系统环境和数据完整性，确保可以安全升级
"""

import os
import sqlite3
import sys
from datetime import datetime
import json

def print_header():
    print("=" * 60)
    print("🔍 HKGAI模型评测系统 - 升级前检查")
    print("=" * 60)
    print()

def check_files():
    """检查必要文件是否存在"""
    print("📁 检查系统文件...")
    
    required_files = [
        "app.py",
        "database.py", 
        "evaluation_system.db"
    ]
    
    optional_files = [
        "config.py",
        "requirements.txt",
        ".env"
    ]
    
    missing_files = []
    for file in required_files:
        if os.path.exists(file):
            size = os.path.getsize(file)
            print(f"✅ {file} ({size:,} bytes)")
        else:
            print(f"❌ {file} - 缺失")
            missing_files.append(file)
    
    for file in optional_files:
        if os.path.exists(file):
            size = os.path.getsize(file)
            print(f"ℹ️  {file} ({size:,} bytes)")
        else:
            print(f"⚠️  {file} - 可选文件，未找到")
    
    if missing_files:
        print(f"\n❌ 缺少必要文件: {', '.join(missing_files)}")
        return False
    
    print("✅ 文件检查通过")
    return True

def check_database():
    """检查数据库状态"""
    print("\n🗄️  检查数据库...")
    
    db_path = "evaluation_system.db"
    if not os.path.exists(db_path):
        print("❌ 数据库文件不存在")
        return False
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 检查表结构
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = [
                'users', 'evaluation_results', 'projects', 
                'annotations', 'running_tasks'
            ]
            
            missing_tables = [t for t in required_tables if t not in tables]
            
            if missing_tables:
                print(f"❌ 缺少必要表: {', '.join(missing_tables)}")
                return False
            
            # 统计数据量
            stats = {}
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    stats[table] = count
                    print(f"📊 {table}: {count:,} 条记录")
                except Exception as e:
                    print(f"⚠️  无法统计表 {table}: {e}")
            
            # 检查是否已有分享功能表
            share_tables = ['shared_links', 'shared_access_logs']
            existing_share_tables = [t for t in share_tables if t in tables]
            
            if existing_share_tables:
                print(f"\nℹ️  已存在分享表: {', '.join(existing_share_tables)}")
                print("   可能已经升级过，请检查功能是否正常")
            else:
                print(f"\n📝 需要创建分享表: {', '.join(share_tables)}")
            
            print("✅ 数据库检查通过")
            return True
            
    except Exception as e:
        print(f"❌ 数据库检查失败: {e}")
        return False

def check_python_environment():
    """检查Python环境"""
    print("\n🐍 检查Python环境...")
    
    # Python版本
    python_version = sys.version
    print(f"📌 Python版本: {python_version}")
    
    if sys.version_info < (3, 6):
        print("❌ Python版本过低，需要 3.6+")
        return False
    
    # 检查必要的包
    required_packages = [
        'sqlite3',
        'flask',
        'werkzeug',
        'hashlib',
        'uuid',
        'datetime',
        'json',
        'os',
        'pandas'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - 未安装")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ 缺少必要包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    print("✅ Python环境检查通过")
    return True

def check_disk_space():
    """检查磁盘空间"""
    print("\n💾 检查磁盘空间...")
    
    try:
        # 获取当前目录的磁盘使用情况
        statvfs = os.statvfs('.')
        free_bytes = statvfs.f_frsize * statvfs.f_bavail
        total_bytes = statvfs.f_frsize * statvfs.f_blocks
        
        free_mb = free_bytes / (1024 * 1024)
        total_mb = total_bytes / (1024 * 1024)
        
        print(f"📊 总空间: {total_mb:.1f} MB")
        print(f"📊 可用空间: {free_mb:.1f} MB")
        
        # 检查是否有足够空间用于备份
        if os.path.exists("evaluation_system.db"):
            db_size = os.path.getsize("evaluation_system.db") / (1024 * 1024)
            print(f"📊 数据库大小: {db_size:.1f} MB")
            
            if free_mb < db_size * 2:
                print("⚠️  磁盘空间不足，可能无法完成备份")
                print("   建议清理磁盘空间或移动到其他位置")
                return False
        
        print("✅ 磁盘空间充足")
        return True
        
    except Exception as e:
        print(f"⚠️  无法检查磁盘空间: {e}")
        return True  # 不阻止升级

def check_running_processes():
    """检查是否有运行中的进程"""
    print("\n🔄 检查运行中的进程...")
    
    try:
        import subprocess
        
        # 检查是否有app.py进程
        result = subprocess.run(['pgrep', '-f', 'python.*app.py'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"⚠️  发现运行中的进程: {', '.join(pids)}")
            print("   升级前需要停止服务")
            return False
        else:
            print("✅ 没有运行中的服务进程")
            return True
            
    except Exception as e:
        print(f"⚠️  无法检查进程: {e}")
        return True  # 不阻止升级

def generate_report():
    """生成检查报告"""
    print("\n📋 生成检查报告...")
    
    report = {
        "check_time": datetime.now().isoformat(),
        "system_info": {
            "python_version": sys.version,
            "platform": sys.platform,
            "cwd": os.getcwd()
        }
    }
    
    try:
        with open("pre_upgrade_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print("✅ 检查报告已保存: pre_upgrade_report.json")
    except Exception as e:
        print(f"⚠️  无法保存报告: {e}")

def main():
    print_header()
    
    all_checks_passed = True
    
    # 执行各项检查
    checks = [
        ("文件检查", check_files),
        ("数据库检查", check_database), 
        ("Python环境检查", check_python_environment),
        ("磁盘空间检查", check_disk_space),
        ("进程检查", check_running_processes)
    ]
    
    for check_name, check_func in checks:
        try:
            if not check_func():
                all_checks_passed = False
        except Exception as e:
            print(f"❌ {check_name}时发生错误: {e}")
            all_checks_passed = False
    
    # 生成报告
    generate_report()
    
    # 总结
    print("\n" + "=" * 60)
    if all_checks_passed:
        print("🎉 所有检查通过！可以安全进行升级")
        print("\n📋 下一步:")
        print("   1. 执行: ./upgrade.sh")
        print("   2. 或按照 UPGRADE_GUIDE.md 手动升级")
    else:
        print("⚠️  部分检查未通过，请解决问题后重新检查")
        print("\n📋 建议:")
        print("   1. 解决上述问题")
        print("   2. 重新运行: python3 pre_upgrade_check.py") 
        print("   3. 查看详细指南: UPGRADE_GUIDE.md")
    
    print("=" * 60)
    
    return all_checks_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
