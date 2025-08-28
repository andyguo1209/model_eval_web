#!/usr/bin/env python3
"""
测试Copilot API调用并查看详细日志
用于调试"无有效内容返回"问题
"""

import os
import sys
import json
import asyncio
import aiohttp
from datetime import datetime

# 添加项目路径
sys.path.insert(0, '/Users/guozhenhua/PycharmProjects/model-evaluation-web')

# 设置Cookie环境变量
os.environ['COPILOT_COOKIE_PROD'] = 'passport=MTc1NjE5NzQ3NnxEWDhFQVFMX2dBQUJFQUVRQUFEX3h2LUFBQUVHYzNSeWFXNW5EQVVBQTJwM2RBWnpkSEpwYm1jTV82b0FfNmRsZVVwb1lrZGphVTlwU2tsVmVra3hUbWxKYzBsdVVqVmpRMGsyU1d0d1dGWkRTamt1WlhsS1dVeFZSbmRqUXpGS1drTkpOazFwZDJsYVdHaDNTV3B2ZUU1NlZUUk9lbWMxVGtSak1reERTbkJhUjFaMVpFZHNNR1ZUU1RaSmFrVTFUa1JaZUUxRVVYaE5la0Y0VGxSQk1FMXFRVEJPUkVGcFpsRXVSSFJxZGtablowNU5Oa1I2ZERCNU5ITTJSMlp1U0ZKVmMyZ3haR2RtY0d4RVQyMUVjM1pNT0VGNVRRPT18SOjP0DDR0uZxVe4bmTrWgyBXeqtjXkhsBbneAYm6PZ0=; __TRACKER__USER_INFO__={"userUniqueId":"1841767668273647616","userId":"1841767668273647616","webId":"38eab303-caf5-43a2-bb66-28ca74981314"}; copilot_prd=MTc1NjIwMDk3NnxEWDhFQVFMX2dBQUJFQUVRQUFEX3h2LUFBQUVHYzNSeWFXNW5EQVVBQTJwM2RBWnpkSEpwYm1jTV82b0FfNmRsZVVwb1lrZGphVTlwU2tsVmVra3hUbWxKYzBsdVVqVmpRMGsyU1d0d1dGWkRTamt1WlhsS1dVeFZSbmRqUXpGS1drTkpOazFwZDJsYVdHaDNTV3B2ZUU1NlZUUk9lbXQ1VDFSak1reERTbkJhUjFaMVpFZHNNR1ZUU1RaSmFrVTBUa1JGYTA1cVl6Sk9hbWQ1VG5wTk1rNUVZekpOVkZscFpsRXVOamRyWTI1cGJHOTNiMnRxTTBZeGMwVnRObWw0VXpVeU9GaHVWWHB2WkRKcE1VWmlWV05aWVVab01BPT18iXfqTriIMvbQHt96ompsK0HtF1xEXrlNvpiRm9-EZag='

async def test_copilot_api():
    """测试Copilot API调用"""
    print("🧪 Copilot API调用测试")
    print("=" * 60)
    
    # 测试配置
    test_cases = [
        {
            "name": "HKGAI-V1-PROD",
            "url": "https://copilot.hkgai.org/copilot/api/instruction/completion",
            "model": "HKGAI-V1",
            "cookie_env": "COPILOT_COOKIE_PROD",
            "query": "介绍深度学习"
        }
    ]
    
    for test_case in test_cases:
        print(f"\n🔧 测试 {test_case['name']}")
        print(f"📋 URL: {test_case['url']}")
        print(f"🤖 Model: {test_case['model']}")
        print(f"❓ Query: {test_case['query']}")
        
        # 获取Cookie
        cookie = os.getenv(test_case['cookie_env'])
        if not cookie:
            print(f"❌ 缺少Cookie环境变量: {test_case['cookie_env']}")
            continue
        
        print(f"🍪 Cookie: {cookie[:50]}...")
        
        # 构建请求
        headers = {
            "Content-Type": "application/json",
            "X-App-Id": "2",
            "Cookie": cookie
        }
        
        payload = {
            "key": "common_writing",
            "parameters": [
                {
                    "key": "user_instruction",
                    "value": test_case['query']
                },
                {
                    "key": "uploaded_rel",
                    "value": ""
                },
                {
                    "key": "with_search",
                    "value": "false"
                },
                {
                    "key": "files",
                    "value": "[]"
                }
            ],
            "model": test_case['model'],
            "stream": True
        }
        
        print(f"📤 Request Payload:")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        
        # 发送请求
        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                print(f"\n⏰ 发送请求...")
                start_time = datetime.now()
                
                async with session.post(test_case['url'], headers=headers, json=payload) as resp:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    print(f"📊 响应状态: HTTP {resp.status}")
                    print(f"⏱️ 响应时间: {elapsed:.2f}秒")
                    
                    if resp.status == 200:
                        # 获取原始响应文本
                        raw_response = await resp.text()
                        print(f"📄 原始响应长度: {len(raw_response)} 字符")
                        
                        # 保存原始响应到文件
                        with open(f"raw_response_{test_case['name']}.txt", 'w', encoding='utf-8') as f:
                            f.write(raw_response)
                        print(f"💾 原始响应已保存到: raw_response_{test_case['name']}.txt")
                        
                        # 显示前500字符
                        print(f"\n📋 原始响应前500字符:")
                        print("=" * 40)
                        print(raw_response[:500])
                        print("=" * 40)
                        
                        # 解析响应
                        print(f"\n🔍 解析响应内容...")
                        content = extract_copilot_content(raw_response.splitlines())
                        print(f"✅ 解析结果长度: {len(content)} 字符")
                        
                        if content.strip():
                            print(f"📝 解析内容前200字符:")
                            print("=" * 40)
                            print(content[:200])
                            print("=" * 40)
                        else:
                            print("❌ 解析后无有效内容")
                            
                        # 分析响应结构
                        analyze_response_structure(raw_response)
                        
                    else:
                        error_text = await resp.text()
                        print(f"❌ 请求失败: HTTP {resp.status}")
                        print(f"📄 错误内容: {error_text[:200]}...")
                        
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            import traceback
            traceback.print_exc()

def extract_copilot_content(stream: list) -> str:
    """提取Copilot流式响应的内容（增强调试版本）"""
    print(f"\n🔍 开始解析流式响应，共 {len(stream)} 行")
    
    buffer = []
    current_event = None
    append_count = 0
    finish_count = 0
    
    for i, raw_line in enumerate(stream):
        line = raw_line.strip()
        if not line:
            continue
        
        print(f"  行 {i:3d}: {line[:100]}{'...' if len(line) > 100 else ''}")
        
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
            print(f"    ▶️ 事件类型: {current_event}")
            continue
        
        if line.startswith("data:") and current_event == "APPEND":
            append_count += 1
            json_part = line[len("data:"):].strip()
            print(f"    📊 APPEND数据: {json_part[:100]}{'...' if len(json_part) > 100 else ''}")
            
            try:
                payload = json.loads(json_part)
                
                # 提取choices[0].delta.content
                choices = payload.get("choices", [])
                if choices and len(choices) > 0:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        buffer.append(content)
                        print(f"    ✅ 提取内容: {repr(content)}")
                    else:
                        print(f"    ⚠️ Delta中无content字段")
                else:
                    print(f"    ⚠️ 无choices数据")
                    
            except json.JSONDecodeError as e:
                print(f"    ❌ JSON解析失败: {e}")
                continue
            except (KeyError, IndexError, TypeError) as e:
                print(f"    ❌ 数据结构解析失败: {e}")
                continue
        
        elif line.startswith("data:") and current_event == "FINISH":
            finish_count += 1
            print(f"    🏁 FINISH事件")
            break
        
        elif line.startswith("data:"):
            print(f"    ℹ️ 其他事件类型 {current_event}: {line[:100]}")
    
    result = "".join(buffer)
    print(f"\n📊 解析统计:")
    print(f"  APPEND事件: {append_count} 个")
    print(f"  FINISH事件: {finish_count} 个")
    print(f"  提取片段: {len(buffer)} 个")
    print(f"  总字符数: {len(result)}")
    
    return result

def analyze_response_structure(raw_response: str) -> None:
    """分析响应结构"""
    print(f"\n🔍 响应结构分析:")
    
    lines = raw_response.splitlines()
    event_types = {}
    data_lines = 0
    
    current_event = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("event:"):
            event_type = line[len("event:"):].strip()
            event_types[event_type] = event_types.get(event_type, 0) + 1
            current_event = event_type
        elif line.startswith("data:"):
            data_lines += 1
            
            # 尝试解析JSON
            json_part = line[len("data:"):].strip()
            if json_part and current_event:
                try:
                    data = json.loads(json_part)
                    print(f"  📋 {current_event} 数据结构: {list(data.keys())}")
                    
                    if current_event == "APPEND" and "choices" in data:
                        choices = data["choices"]
                        if choices and len(choices) > 0:
                            choice = choices[0]
                            print(f"    Choice字段: {list(choice.keys())}")
                            if "delta" in choice:
                                delta = choice["delta"]
                                print(f"    Delta字段: {list(delta.keys())}")
                except:
                    pass
    
    print(f"  总行数: {len(lines)}")
    print(f"  数据行: {data_lines}")
    print(f"  事件类型: {event_types}")

if __name__ == "__main__":
    print("🚀 启动Copilot API测试")
    asyncio.run(test_copilot_api())
    print("\n✅ 测试完成")
