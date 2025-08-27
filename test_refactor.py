#!/usr/bin/env python3
"""
重构测试脚本
验证模块化重构后的功能是否正常
"""

import sys
import os

# 添加项目路径到sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试模块导入"""
    try:
        from models.model_factory import model_factory
        from models.copilot_client import copilot_client
        from models.legacy_client import legacy_client
        print("✅ 所有模块导入成功")
        return True
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return False

def test_model_factory():
    """测试模型工厂功能"""
    try:
        from models.model_factory import model_factory
        
        # 测试获取所有模型
        all_models = model_factory.get_all_models()
        print(f"✅ 获取所有模型: {len(all_models)} 个")
        
        # 测试获取可用模型
        available_models = model_factory.get_available_models()
        print(f"✅ 获取可用模型: {len(available_models)} 个")
        
        # 测试模型类型检测
        legacy_model = "HKGAI-V1"
        copilot_model = "HKGAI-V1-PROD"
        
        print(f"✅ {legacy_model} 类型: {model_factory.get_model_type(legacy_model)}")
        print(f"✅ {copilot_model} 类型: {model_factory.get_model_type(copilot_model)}")
        
        # 测试模型验证
        is_valid, msg = model_factory.validate_model(legacy_model)
        print(f"✅ {legacy_model} 验证: {is_valid} - {msg}")
        
        is_valid, msg = model_factory.validate_model(copilot_model)
        print(f"✅ {copilot_model} 验证: {is_valid} - {msg}")
        
        return True
    except Exception as e:
        print(f"❌ 模型工厂测试失败: {e}")
        return False

def test_legacy_client():
    """测试Legacy客户端"""
    try:
        from models.legacy_client import legacy_client
        
        models = legacy_client.get_available_models()
        print(f"✅ Legacy客户端: {len(models)} 个模型")
        for model in models:
            print(f"   - {model['name']}: {'可用' if model['available'] else '不可用'}")
        
        return True
    except Exception as e:
        print(f"❌ Legacy客户端测试失败: {e}")
        return False

def test_copilot_client():
    """测试Copilot客户端"""
    try:
        from models.copilot_client import copilot_client
        
        models = copilot_client.get_available_models()
        print(f"✅ Copilot客户端: {len(models)} 个模型")
        for model in models:
            print(f"   - {model['name']}: {'可用' if model['available'] else '不可用'}")
        
        return True
    except Exception as e:
        print(f"❌ Copilot客户端测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🧪 开始重构功能测试...")
    print("=" * 50)
    
    tests = [
        ("模块导入", test_imports),
        ("Legacy客户端", test_legacy_client),
        ("Copilot客户端", test_copilot_client),
        ("模型工厂", test_model_factory),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 测试: {test_name}")
        print("-" * 30)
        if test_func():
            passed += 1
            print(f"✅ {test_name} 测试通过")
        else:
            print(f"❌ {test_name} 测试失败")
    
    print("\n" + "=" * 50)
    print(f"🎯 测试结果: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！重构成功！")
        return True
    else:
        print("⚠️ 部分测试失败，需要检查代码")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
