#!/usr/bin/env python3
"""
🧪 升级后功能测试脚本
验证分享功能和系统完整性
"""

import sqlite3
import requests
import json
import sys
import time
from datetime import datetime

def print_header():
    print("=" * 60)
    print("🧪 HKGAI模型评测系统 - 升级后测试")
    print("=" * 60)
    print()

def test_database():
    """测试数据库功能"""
    print("🗄️  测试数据库...")
    
    try:
        with sqlite3.connect("evaluation_system.db") as conn:
            cursor = conn.cursor()
            
            # 检查分享表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'shared%'")
            share_tables = [row[0] for row in cursor.fetchall()]
            
            if 'shared_links' not in share_tables:
                print("❌ shared_links 表不存在")
                return False
                
            if 'shared_access_logs' not in share_tables:
                print("❌ shared_access_logs 表不存在")
                return False
            
            print("✅ 分享功能表存在")
            
            # 测试插入功能（创建测试记录）
            test_id = f"test_{int(time.time())}"
            cursor.execute("""
                INSERT INTO shared_links 
                (id, share_token, result_id, share_type, shared_by, title)
                VALUES (?, ?, 'test', 'public', 'test_user', 'Test Share')
            """, (test_id, f"token_{test_id}"))
            
            # 验证插入成功
            cursor.execute("SELECT COUNT(*) FROM shared_links WHERE id = ?", (test_id,))
            count = cursor.fetchone()[0]
            
            if count == 1:
                print("✅ 分享链接表写入测试通过")
                
                # 清理测试数据
                cursor.execute("DELETE FROM shared_links WHERE id = ?", (test_id,))
                conn.commit()
                print("✅ 测试数据清理完成")
            else:
                print("❌ 分享链接表写入测试失败")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ 数据库测试失败: {e}")
        return False

def test_web_service(port=8080):
    """测试Web服务"""
    print("🌐 测试Web服务...")
    
    base_url = f"http://localhost:{port}"
    
    try:
        # 测试主页
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            print("✅ 主页访问正常")
        else:
            print(f"⚠️  主页返回状态码: {response.status_code}")
        
        # 测试登录页
        login_url = f"{base_url}/login"
        response = requests.get(login_url, timeout=5)
        if response.status_code == 200:
            print("✅ 登录页面正常")
        else:
            print(f"⚠️  登录页面返回状态码: {response.status_code}")
        
        # 测试API端点
        api_url = f"{base_url}/api/tasks/running"
        response = requests.get(api_url, timeout=5)
        if response.status_code in [200, 401]:  # 可能需要登录
            print("✅ API端点响应正常")
        else:
            print(f"⚠️  API端点状态码: {response.status_code}")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到Web服务")
        print("   请确认服务已启动: python3 app.py")
        return False
    except Exception as e:
        print(f"❌ Web服务测试失败: {e}")
        return False

def test_template_files():
    """测试模板文件"""
    print("📄 测试模板文件...")
    
    template_files = [
        "templates/shared_result.html",
        "templates/shared_password.html", 
        "templates/shared_error.html"
    ]
    
    all_exists = True
    for template in template_files:
        try:
            with open(template, 'r', encoding='utf-8') as f:
                content = f.read()
                if len(content) > 100:  # 简单检查文件不为空
                    print(f"✅ {template}")
                else:
                    print(f"⚠️  {template} - 文件过小")
                    all_exists = False
        except FileNotFoundError:
            print(f"❌ {template} - 文件不存在")
            all_exists = False
        except Exception as e:
            print(f"❌ {template} - 读取错误: {e}")
            all_exists = False
    
    return all_exists

def test_share_functionality():
    """测试分享功能逻辑"""
    print("🔗 测试分享功能逻辑...")
    
    try:
        # 导入并测试database模块
        sys.path.insert(0, '.')
        from database import Database
        
        db = Database()
        
        # 创建测试用户 (如果不存在)
        test_user_id = "test_user_share"
        test_result_id = "test_result_share"
        
        # 测试创建分享链接
        share_data = db.create_share_link(
            result_id=test_result_id,
            shared_by=test_user_id,
            title="测试分享",
            description="这是一个测试分享链接",
            share_type="public"
        )
        
        if share_data and 'share_token' in share_data:
            print("✅ 分享链接创建功能正常")
            
            # 测试获取分享链接
            share_token = share_data['share_token']
            retrieved_share = db.get_share_link_by_token(share_token)
            
            if retrieved_share:
                print("✅ 分享链接查询功能正常")
                
                # 清理测试数据
                db.revoke_share_link(share_data['id'], test_user_id)
                print("✅ 测试数据清理完成")
                
                return True
            else:
                print("❌ 分享链接查询失败")
                return False
        else:
            print("❌ 分享链接创建失败")
            return False
            
    except ImportError:
        print("❌ 无法导入Database模块")
        return False
    except Exception as e:
        print(f"❌ 分享功能测试失败: {e}")
        return False

def generate_test_report(results):
    """生成测试报告"""
    print("\n📋 生成测试报告...")
    
    report = {
        "test_time": datetime.now().isoformat(),
        "test_results": results,
        "overall_status": "PASS" if all(results.values()) else "FAIL",
        "summary": {
            "total_tests": len(results),
            "passed_tests": sum(1 for r in results.values() if r),
            "failed_tests": sum(1 for r in results.values() if not r)
        }
    }
    
    try:
        with open("post_upgrade_test_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print("✅ 测试报告已保存: post_upgrade_test_report.json")
    except Exception as e:
        print(f"⚠️  无法保存报告: {e}")
    
    return report

def main():
    print_header()
    
    # 测试项目
    tests = [
        ("数据库功能", test_database),
        ("模板文件", test_template_files),
        ("分享功能逻辑", test_share_functionality),
        ("Web服务", lambda: test_web_service())
    ]
    
    results = {}
    
    # 执行测试
    for test_name, test_func in tests:
        print()
        try:
            result = test_func()
            results[test_name] = result
            
            if result:
                print(f"✅ {test_name} - 通过")
            else:
                print(f"❌ {test_name} - 失败")
                
        except Exception as e:
            print(f"❌ {test_name} - 异常: {e}")
            results[test_name] = False
    
    # 生成报告
    report = generate_test_report(results)
    
    # 测试总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:<20} : {status}")
    
    print()
    if report['overall_status'] == 'PASS':
        print("🎉 所有测试通过！升级成功完成")
        print("\n📋 下一步:")
        print("   1. 登录系统测试分享功能")
        print("   2. 创建分享链接验证功能")
        print("   3. 在生产环境中验证")
    else:
        print("⚠️  部分测试失败，请检查相关功能")
        failed_tests = [name for name, result in results.items() if not result]
        print(f"\n❌ 失败的测试: {', '.join(failed_tests)}")
        print("\n📋 建议:")
        print("   1. 查看详细错误信息")
        print("   2. 检查 UPGRADE_GUIDE.md 故障排除")
        print("   3. 联系技术支持")
    
    print("=" * 60)
    
    return report['overall_status'] == 'PASS'

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
