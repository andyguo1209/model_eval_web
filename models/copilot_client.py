"""
Copilot AI模型客户端
处理所有Copilot接口相关的请求和响应
"""

import os
import json
import uuid
import asyncio
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime


class CopilotClient:
    """Copilot AI模型客户端"""
    
    # Copilot模型配置
    COPILOT_MODELS = {
        "HKGAI-V1-PROD": {
            "type": "copilot",
            "url": "https://copilot.hkgai.org/copilot/api/instruction/completion",
            "model": "HKGAI-V1",
            "cookie_env": "COPILOT_COOKIE_PROD",
            "headers_template": {
                "Content-Type": "application/json",
                "X-App-Id": "2"
            },
            "request_config": {
                "key": "common_writing",
                "stream": True,
                "parameters_template": {
                    "user_instruction": "{prompt}",
                    "uploaded_rel": "",
                    "with_search": "false",
                    "files": "[]"
                }
            }
        },
        "HKGAI-V1-Thinking-PROD": {
            "type": "copilot",
            "url": "https://copilot.hkgai.org/copilot/api/instruction/completion",
            "model": "HKGAI-V1-Thinking",
            "cookie_env": "COPILOT_COOKIE_PROD",
            "headers_template": {
                "Content-Type": "application/json",
                "X-App-Id": "2"
            },
            "request_config": {
                "key": "common_writing",
                "stream": True,
                "parameters_template": {
                    "user_instruction": "{prompt}",
                    "uploaded_rel": "",
                    "with_search": "false",
                    "files": "[]"
                }
            }
        },
        "HKGAI-V1-TEST": {
            "type": "copilot",
            "url": "https://copilot-test.hkgai.org/copilot/api/instruction/completion",
            "model": "HKGAI-V1",
            "cookie_env": "COPILOT_COOKIE_TEST",
            "headers_template": {
                "Content-Type": "application/json",
                "X-App-Id": "2"
            },
            "request_config": {
                "key": "common_writing",
                "stream": True,
                "parameters_template": {
                    "user_instruction": "{prompt}",
                    "uploaded_rel": "",
                    "with_search": "false",
                    "files": "[]"
                }
            }
        },
        "HKGAI-V1-Thinking-TEST": {
            "type": "copilot",
            "url": "https://copilot-test.hkgai.org/copilot/api/instruction/completion",
            "model": "HKGAI-V1-Thinking",
            "cookie_env": "COPILOT_COOKIE_TEST",
            "headers_template": {
                "Content-Type": "application/json",
                "X-App-Id": "2"
            },
            "request_config": {
                "key": "common_writing",
                "stream": True,
                "parameters_template": {
                    "user_instruction": "{prompt}",
                    "uploaded_rel": "",
                    "with_search": "false",
                    "files": "[]"
                }
            }
        },
        "HKGAI-V1-NET": {
            "type": "copilot",
            "url": "https://copilot.hkgai.net/copilot/api/instruction/completion",
            "model": "HKGAI-V1",
            "cookie_env": "COPILOT_COOKIE_NET",
            "headers_template": {
                "Content-Type": "application/json",
                "X-App-Id": "2"
            },
            "request_config": {
                "key": "common_writing",
                "stream": True,
                "parameters_template": {
                    "user_instruction": "{prompt}",
                    "uploaded_rel": "",
                    "with_search": "false",
                    "files": "[]"
                }
            }
        },
        "HKGAI-V1-Thinking-NET": {
            "type": "copilot",
            "url": "https://copilot.hkgai.net/copilot/api/instruction/completion",
            "model": "HKGAI-V1-Thinking",
            "cookie_env": "COPILOT_COOKIE_NET",
            "headers_template": {
                "Content-Type": "application/json",
                "X-App-Id": "2"
            },
            "request_config": {
                "key": "common_writing",
                "stream": True,
                "parameters_template": {
                    "user_instruction": "{prompt}",
                    "uploaded_rel": "",
                    "with_search": "false",
                    "files": "[]"
                }
            }
        }
    }
    
    @classmethod
    def get_available_models(cls) -> List[Dict]:
        """获取可用的Copilot模型列表"""
        models = []
        for model_name, config in cls.COPILOT_MODELS.items():
            auth_key = os.getenv(config["cookie_env"])
            models.append({
                'name': model_name,
                'type': 'copilot',
                'available': bool(auth_key),
                'auth_env': config["cookie_env"]
            })
        return models
    
    @classmethod
    def is_copilot_model(cls, model_name: str) -> bool:
        """检查是否为Copilot模型"""
        return model_name in cls.COPILOT_MODELS
    
    @classmethod
    def get_model_config(cls, model_name: str) -> Optional[Dict]:
        """获取模型配置"""
        return cls.COPILOT_MODELS.get(model_name)
    
    @classmethod
    def validate_model(cls, model_name: str) -> tuple[bool, str]:
        """验证模型是否可用"""
        if model_name not in cls.COPILOT_MODELS:
            return False, f"不支持的Copilot模型: {model_name}"
        
        model_config = cls.COPILOT_MODELS[model_name]
        auth_env = model_config["cookie_env"]
        
        if not os.getenv(auth_env):
            return False, f"模型 {model_name} 缺少环境变量: {auth_env}"
        
        return True, ""
    
    @staticmethod
    def extract_stream_content(stream: List[str]) -> str:
        """提取Copilot流式响应的内容"""
        buffer = []
        current_event = None

        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("event:"):
                current_event = line[len("event:"):].strip()
                continue

            if line.startswith("data:") and current_event == "APPEND":
                json_part = line[len("data:"):].strip()
                try:
                    payload = json.loads(json_part)
                    
                    # 提取choices[0].delta.content
                    choices = payload.get("choices", [])
                    if choices and len(choices) > 0:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            buffer.append(content)
                            
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON解析失败: {e}, 内容: {json_part[:100]}...")
                    continue
                except (KeyError, IndexError, TypeError) as e:
                    print(f"⚠️ 数据结构解析失败: {e}")
                    continue

            elif line.startswith("data:") and current_event == "FINISH":
                # 响应结束，可以在这里做一些清理工作
                break

        result = "".join(buffer)
        print(f"✅ Copilot响应解析完成，总长度: {len(result)} 字符")
        return result
    
    @classmethod
    async def fetch_answer(cls, session: aiohttp.ClientSession, query: str, model_name: str, 
                          idx: int, sem_model: asyncio.Semaphore, task_id: str, 
                          task_status: Dict = None) -> str:
        """获取Copilot模型的答案"""
        
        # 获取模型配置
        model_config = cls.get_model_config(model_name)
        if not model_config:
            return f"错误：不支持的Copilot模型: {model_name}"
        
        # 获取Cookie认证
        cookie = os.getenv(model_config["cookie_env"])
        if not cookie:
            return f"错误：未配置 {model_config['cookie_env']} Cookie"
        
        # 构建请求头
        headers = model_config["headers_template"].copy()
        headers["Cookie"] = cookie
        
        # 构建请求体
        request_config = model_config["request_config"]
        parameters = []
        
        for param_key, param_template in request_config["parameters_template"].items():
            if param_template == "{prompt}":
                value = query  # 用户的prompt直接作为user_instruction
            else:
                value = param_template  # 其他参数使用固定值
            
            parameters.append({
                "key": param_key,
                "value": value
            })
        
        payload = {
            "key": request_config["key"],
            "parameters": parameters,
            "model": model_config["model"],
            "stream": request_config["stream"]
        }
        
        # 发送请求并解析响应
        async with sem_model:
            try:
                # 详细请求日志 - 开始
                print(f"📤 [Copilot请求] {model_name}")
                print(f"🔗 URL: {model_config['url']}")
                print(f"📋 Headers:")
                for key, value in headers.items():
                    if key.lower() == 'cookie':
                        # 只显示Cookie的前50字符
                        print(f"   {key}: {value[:50]}...")
                    else:
                        print(f"   {key}: {value}")
                print(f"📄 Payload: {json.dumps(payload, ensure_ascii=False)}")
                print(f"🚀 开始发送请求...")
                # 详细请求日志 - 结束
                
                async with session.post(model_config["url"], headers=headers, json=payload, timeout=60) as resp:
                    raw_response = await resp.text()
                    
                    # 响应日志
                    print(f"📥 [Copilot响应] HTTP {resp.status}")
                    print(f"📊 响应长度: {len(raw_response)} 字符")
                    print(f"📝 响应前200字符: {raw_response[:200]}...")
                    
                    if resp.status == 200:
                        # 检查是否为错误响应（即使HTTP 200）
                        if raw_response.strip().startswith('{"code":'):
                            try:
                                error_data = json.loads(raw_response.strip())
                                if error_data.get("code") == 401:
                                    print(f"❌ Copilot认证失败: Cookie已过期或无效")
                                    print(f"💡 错误详情: {error_data}")
                                    print(f"🔍 使用的Cookie环境变量: {model_config['cookie_env']}")
                                    return f"❌ Cookie认证失败: {error_data.get('msg', 'Unauthorized')}"
                                else:
                                    print(f"❌ Copilot API错误: {error_data}")
                                    error_code = error_data.get('code', 'Unknown')
                                    error_msg = error_data.get('msg', f'Code {error_code}')
                                    return f"❌ API错误: {error_msg}"
                            except json.JSONDecodeError:
                                pass
                        
                        # 正常流式响应解析
                        content = cls.extract_stream_content(raw_response.splitlines())
                        
                        # 更新进度
                        if task_status and task_id in task_status:
                            task_status[task_id].progress += 1
                            task_status[task_id].current_step = f"已完成 {task_status[task_id].progress}/{task_status[task_id].total} 个查询"
                        
                        return content if content.strip() else "⚠️ API响应为空，请检查Cookie是否有效"
                    else:
                        print(f"❌ Copilot请求失败: HTTP {resp.status} - {raw_response[:200]}...")
                        if resp.status == 401:
                            return f"❌ Cookie认证失败: 请更新 {model_config['cookie_env']} Cookie"
                        elif resp.status == 403:
                            return f"❌ 访问被拒绝: 请检查Cookie权限"
                        else:
                            return f"❌ 请求失败: HTTP {resp.status}"
            except Exception as e:
                print(f"❌ Copilot请求异常: {e}")
                return f"❌ 请求异常: {str(e)}"


# 创建全局实例
copilot_client = CopilotClient()
