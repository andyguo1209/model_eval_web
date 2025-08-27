#!/usr/bin/env python3
"""
登录功能测试脚本
验证用户认证系统是否正常工作
"""

import requests
import json
import sys

BASE_URL = "http://localhost:5001"

def test_login_page():
    """测试登录页面是否正常访问"""
    print("🧪 测试登录页面访问...")
    try:
        response = requests.get(f"{BASE_URL}/login")
        if response.status_code == 200:
            print("✅ 登录页面访问正常")
            return True
        else:
            print(f"❌ 登录页面访问失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 登录页面访问异常: {e}")
        return False

def test_admin_login():
    """测试管理员登录"""
    print("🧪 测试管理员登录...")
    try:
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        
        response = requests.post(
            f"{BASE_URL}/login",
            json=login_data,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ 管理员登录成功")
                print(f"   用户信息: {result.get('user')}")
                return True, response.cookies
            else:
                print(f"❌ 登录失败: {result.get('message')}")
                return False, None
        else:
            print(f"❌ 登录请求失败: HTTP {response.status_code}")
            return False, None
            
    except Exception as e:
        print(f"❌ 登录测试异常: {e}")
        return False, None

def test_invalid_login():
    """测试无效登录"""
    print("🧪 测试无效登录...")
    try:
        login_data = {
            "username": "invalid_user",
            "password": "wrong_password"
        }
        
        response = requests.post(
            f"{BASE_URL}/login",
            json=login_data,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 401:
            result = response.json()
            if not result.get('success'):
                print("✅ 无效登录正确被拒绝")
                return True
            else:
                print("❌ 无效登录错误地被接受")
                return False
        else:
            print(f"❌ 无效登录响应码错误: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 无效登录测试异常: {e}")
        return False

def test_admin_page(cookies):
    """测试管理员页面访问"""
    print("🧪 测试管理员页面访问...")
    try:
        response = requests.get(f"{BASE_URL}/admin", cookies=cookies)
        if response.status_code == 200:
            print("✅ 管理员页面访问正常")
            return True
        else:
            print(f"❌ 管理员页面访问失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 管理员页面访问异常: {e}")
        return False

def test_users_api(cookies):
    """测试用户API"""
    print("🧪 测试用户API...")
    try:
        response = requests.get(f"{BASE_URL}/admin/users", cookies=cookies)
        if response.status_code == 200:
            users = response.json()
            print(f"✅ 用户API正常，共有 {len(users)} 个用户")
            return True
        else:
            print(f"❌ 用户API失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 用户API测试异常: {e}")
        return False

def test_logout(cookies):
    """测试退出登录"""
    print("🧪 测试退出登录...")
    try:
        response = requests.post(f"{BASE_URL}/logout", cookies=cookies)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ 退出登录成功")
                return True
            else:
                print(f"❌ 退出登录失败: {result.get('message')}")
                return False
        else:
            print(f"❌ 退出登录请求失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 退出登录测试异常: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始登录功能测试...")
    print(f"🌐 测试地址: {BASE_URL}")
    print("-" * 50)
    
    test_results = []
    
    # 测试1: 登录页面访问
    test_results.append(test_login_page())
    
    # 测试2: 无效登录
    test_results.append(test_invalid_login())
    
    # 测试3: 管理员登录
    login_success, cookies = test_admin_login()
    test_results.append(login_success)
    
    if login_success and cookies:
        # 测试4: 管理员页面访问
        test_results.append(test_admin_page(cookies))
        
        # 测试5: 用户API
        test_results.append(test_users_api(cookies))
        
        # 测试6: 退出登录
        test_results.append(test_logout(cookies))
    else:
        print("❌ 由于登录失败，跳过后续测试")
        test_results.extend([False, False, False])
    
    # 测试结果汇总
    print("-" * 50)
    print("📊 测试结果汇总:")
    
    test_names = [
        "登录页面访问",
        "无效登录拒绝",
        "管理员登录",
        "管理员页面访问",
        "用户API调用",
        "退出登录"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {i+1}. {name}: {status}")
    
    passed_count = sum(test_results)
    total_count = len(test_results)
    
    print(f"\n🎯 测试总结: {passed_count}/{total_count} 通过")
    
    if passed_count == total_count:
        print("🎉 所有测试通过！登录系统工作正常。")
        return True
    else:
        print("⚠️ 部分测试失败，请检查系统配置。")
        return False

if __name__ == "__main__":
    print("📋 登录功能测试开始")
    print("⚠️ 请确保应用程序正在运行 (python3 start.py)")
    print()
    
    success = main()
    sys.exit(0 if success else 1)
