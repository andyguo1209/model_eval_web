"""
配置文件
请在系统环境变量中设置以下API密钥
"""

import os

# API配置
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ARK_API_KEY_HKGAI_V1 = os.getenv("ARK_API_KEY_HKGAI_V1")
ARK_API_KEY_HKGAI_V2 = os.getenv("ARK_API_KEY_HKGAI_V2")

# Flask配置
SECRET_KEY = os.getenv("SECRET_KEY", "model-evaluation-web-2024")
DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"

# 文件上传配置
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))  # 16MB
UPLOAD_TIMEOUT = int(os.getenv("UPLOAD_TIMEOUT", 300))  # 5分钟

# 并发配置
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 10))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 60))

def check_api_keys():
    """检查必需的API密钥是否已配置"""
    missing_keys = []
    
    if not GOOGLE_API_KEY:
        missing_keys.append("GOOGLE_API_KEY")
    
    if not ARK_API_KEY_HKGAI_V1:
        missing_keys.append("ARK_API_KEY_HKGAI_V1")
        
    if not ARK_API_KEY_HKGAI_V2:
        missing_keys.append("ARK_API_KEY_HKGAI_V2")
    
    return missing_keys
