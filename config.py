"""
模型评测系统 - 配置文件
=============================================

必需配置:
- GOOGLE_API_KEY: Gemini评测API密钥
- ARK_API_KEY_HKGAI_V1: HKGAI-V1模型API密钥  
- ARK_API_KEY_HKGAI_V2: HKGAI-V2模型API密钥

可选配置 (Copilot模型):
- COPILOT_COOKIE_PROD: 生产环境Cookie
- COPILOT_COOKIE_TEST: 测试环境Cookie
- COPILOT_COOKIE_NET: 备用环境Cookie

请在.env文件或系统环境变量中设置这些配置
"""

import os
from utils.env_manager import env_manager

# 首先从.env文件加载环境变量
env_vars = env_manager.load_env()
for key, value in env_vars.items():
    os.environ[key] = value

# ============================================
# API配置
# ============================================

# === 评测系统核心API ===
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# === Legacy模型API密钥 ===
ARK_API_KEY_HKGAI_V1 = os.getenv("ARK_API_KEY_HKGAI_V1")
ARK_API_KEY_HKGAI_V2 = os.getenv("ARK_API_KEY_HKGAI_V2")

# === Copilot模型Cookie配置 ===
# 生产环境 (copilot.hkgai.org)
COPILOT_COOKIE_PROD = os.getenv("COPILOT_COOKIE_PROD", "")

# 测试环境 (copilot-test.hkgai.org)  
COPILOT_COOKIE_TEST = os.getenv("COPILOT_COOKIE_TEST", "")

# 备用环境 (copilot.hkgai.net)
COPILOT_COOKIE_NET = os.getenv("COPILOT_COOKIE_NET", "")

# Flask配置
SECRET_KEY = os.getenv("SECRET_KEY", "model-evaluation-web-2024")
DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"

# 文件上传配置
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))  # 16MB
UPLOAD_TIMEOUT = int(os.getenv("UPLOAD_TIMEOUT", 300))  # 5分钟

# 并发配置
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 10))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 60))

# Gemini 特定配置
GEMINI_CONCURRENT_REQUESTS = int(os.getenv("GEMINI_CONCURRENT_REQUESTS", 3))  # Gemini并发数，避免过载
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", 4096))  # Gemini最大输出token数

def check_api_keys():
    """检查必需的API密钥是否已配置"""
    missing_keys = []
    
    # 检查核心评测API（必需）
    if not GOOGLE_API_KEY:
        missing_keys.append("GOOGLE_API_KEY")
    
    # 检查Legacy模型API（必需）
    if not ARK_API_KEY_HKGAI_V1:
        missing_keys.append("ARK_API_KEY_HKGAI_V1")
        
    if not ARK_API_KEY_HKGAI_V2:
        missing_keys.append("ARK_API_KEY_HKGAI_V2")
    
    return missing_keys

def check_copilot_models():
    """检查Copilot模型配置状态（可选）"""
    copilot_status = {
        "COPILOT_COOKIE_PROD": bool(COPILOT_COOKIE_PROD),
        "COPILOT_COOKIE_TEST": bool(COPILOT_COOKIE_TEST), 
        "COPILOT_COOKIE_NET": bool(COPILOT_COOKIE_NET)
    }
    
    available_count = sum(copilot_status.values())
    total_count = len(copilot_status)
    
    return {
        "status": copilot_status,
        "available_count": available_count,
        "total_count": total_count,
        "has_any": available_count > 0
    }

def get_model_availability():
    """获取所有模型的可用性状态"""
    # 基础模型状态
    base_models = {
        "HKGAI-V1": bool(ARK_API_KEY_HKGAI_V1),
        "HKGAI-V2": bool(ARK_API_KEY_HKGAI_V2)
    }
    
    # Copilot模型状态
    copilot_models = {
        "HKGAI-V1-PROD": bool(COPILOT_COOKIE_PROD),
        "HKGAI-V1-Thinking-PROD": bool(COPILOT_COOKIE_PROD),
        "HKGAI-V1-TEST": bool(COPILOT_COOKIE_TEST),
        "HKGAI-V1-Thinking-TEST": bool(COPILOT_COOKIE_TEST),
        "HKGAI-V1-NET": bool(COPILOT_COOKIE_NET),
        "HKGAI-V1-Thinking-NET": bool(COPILOT_COOKIE_NET)
    }
    
    # 评测系统状态
    evaluation_status = {
        "gemini_api": bool(GOOGLE_API_KEY)
    }
    
    return {
        "base_models": base_models,
        "copilot_models": copilot_models,
        "evaluation": evaluation_status,
        "summary": {
            "base_available": sum(base_models.values()),
            "base_total": len(base_models),
            "copilot_available": sum(copilot_models.values()),
            "copilot_total": len(copilot_models),
            "evaluation_ready": evaluation_status["gemini_api"]
        }
    }

def print_configuration_status():
    """打印配置状态信息"""
    print("\n" + "="*50)
    print("🔧 模型评测系统 - 配置状态")
    print("="*50)
    
    # 检查必需配置
    missing_keys = check_api_keys()
    if missing_keys:
        print("❌ 缺少必需配置:")
        for key in missing_keys:
            print(f"   - {key}")
    else:
        print("✅ 所有必需配置已就绪")
    
    # 检查模型可用性
    availability = get_model_availability()
    summary = availability["summary"]
    
    print(f"\n📊 模型可用性:")
    print(f"   🏠 Legacy模型: {summary['base_available']}/{summary['base_total']} 可用")
    print(f"   🚀 Copilot模型: {summary['copilot_available']}/{summary['copilot_total']} 可用")
    print(f"   🤖 评测系统: {'✅ 就绪' if summary['evaluation_ready'] else '❌ 未配置'}")
    
    # 详细模型状态
    print(f"\n📋 详细状态:")
    for model, status in availability["base_models"].items():
        icon = "✅" if status else "❌"
        print(f"   {icon} {model}")
    
    if summary['copilot_available'] > 0:
        print(f"\n🚀 可用的Copilot模型:")
        for model, status in availability["copilot_models"].items():
            if status:
                print(f"   ✅ {model}")
    
    if summary['copilot_available'] < summary['copilot_total']:
        print(f"\n💡 要启用更多Copilot模型，请配置以下环境变量:")
        copilot_check = check_copilot_models()
        for env_var, configured in copilot_check["status"].items():
            if not configured:
                print(f"   - {env_var}")
    
    print("="*50)
