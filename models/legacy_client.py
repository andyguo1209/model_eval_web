"""
Legacy AI模型客户端
处理原有的HKGAI-V1/V2模型接口
"""

import os
import json
import uuid
import asyncio
import aiohttp
from typing import Dict, List, Optional


class LegacyClient:
    """Legacy AI模型客户端"""
    
    # Legacy模型配置
    LEGACY_MODELS = {
        "HKGAI-V1": {
            "type": "legacy",
            "url": "https://chat.hkchat.app/goapi/v1/chat/stream",
            "model": "HKGAI-V1",
            "token_env": "ARK_API_KEY_HKGAI_V1",
            "headers_template": {
                "Accept": "text/event-stream",
                "Content-Type": "application/json"
            }
        },
        "HKGAI-V2": {
            "type": "legacy",
            "url": "https://test.hkchat.app/goapi/v1/chat/stream",
            "model": "HKGAI-V2", 
            "token_env": "ARK_API_KEY_HKGAI_V2",
            "headers_template": {
                "Accept": "text/event-stream",
                "Content-Type": "application/json"
            }
        }
    }
    
    @classmethod
    def get_available_models(cls) -> List[Dict]:
        """获取可用的Legacy模型列表"""
        models = []
        for model_name, config in cls.LEGACY_MODELS.items():
            auth_key = os.getenv(config["token_env"])
            models.append({
                'name': model_name,
                'type': 'legacy',
                'available': bool(auth_key),
                'auth_env': config["token_env"]
            })
        return models
    
    @classmethod
    def is_legacy_model(cls, model_name: str) -> bool:
        """检查是否为Legacy模型"""
        return model_name in cls.LEGACY_MODELS
    
    @classmethod
    def get_model_config(cls, model_name: str) -> Optional[Dict]:
        """获取模型配置"""
        return cls.LEGACY_MODELS.get(model_name)
    
    @classmethod
    def validate_model(cls, model_name: str) -> tuple[bool, str]:
        """验证模型是否可用"""
        if model_name not in cls.LEGACY_MODELS:
            return False, f"不支持的Legacy模型: {model_name}"
        
        model_config = cls.LEGACY_MODELS[model_name]
        auth_env = model_config["token_env"]
        
        if not os.getenv(auth_env):
            return False, f"模型 {model_name} 缺少环境变量: {auth_env}"
        
        return True, ""
    
    @staticmethod
    def extract_stream_content(stream: List[str]) -> str:
        """提取Legacy流式响应的内容"""
        buffer = []
        current_event = None

        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("event:"):
                current_event = line[len("event:"):].strip()
                continue

            if line.startswith("data:") and current_event == "message":
                json_part = line[len("data:"):].strip()
                try:
                    payload = json.loads(json_part)
                    content = payload.get("content", "")
                    if content:
                        buffer.append(content)
                except json.JSONDecodeError:
                    continue

        return "".join(buffer)
    
    @classmethod
    async def fetch_answer(cls, session: aiohttp.ClientSession, query: str, model_name: str,
                          idx: int, sem_model: asyncio.Semaphore, task_id: str,
                          task_status: Dict = None, request_headers: Dict = None) -> str:
        """获取Legacy模型的答案"""
        
        # 获取模型配置
        model_config = cls.get_model_config(model_name)
        if not model_config:
            return f"错误：不支持的Legacy模型: {model_name}"
        
        # 获取Token认证
        token = os.getenv(model_config["token_env"])
        if not token and request_headers:
            model_name_key = model_config["model"]
            token = request_headers.get(f'X-{model_name_key.replace("-", "-")}-Key')
        
        if not token:
            return f"错误：未配置 {model_config['token_env']} API密钥"

        headers = model_config["headers_template"].copy()
        headers["Authorization"] = f"Bearer {token}"

        payload = {
            "model": model_config["model"],
            "features": {"web_search": False},
            "query": query,
            "chat_id": str(uuid.uuid4())
        }

        async with sem_model:
            try:
                async with session.post(model_config["url"], headers=headers, json=payload, timeout=60) as resp:
                    if resp.status == 200:
                        raw = await resp.text()
                        content = cls.extract_stream_content(raw.splitlines())
                        
                        # 更新进度
                        if task_status and task_id in task_status:
                            task_status[task_id].progress += 1
                            task_status[task_id].current_step = f"已完成 {task_status[task_id].progress}/{task_status[task_id].total} 个查询"
                        
                        return content if content.strip() else "无有效内容返回"
                    else:
                        return f"请求失败: HTTP {resp.status}"
            except Exception as e:
                return f"请求异常: {str(e)}"


# 创建全局实例
legacy_client = LegacyClient()
