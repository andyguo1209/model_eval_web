import os
import json
import uuid
import asyncio
import aiohttp
import pandas as pd
import time
import re
import csv
import sqlite3
from datetime import datetime, timedelta

# 注册分析API蓝图
from routes.analytics_api import analytics_bp
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, redirect, url_for, session
from werkzeug.utils import secure_filename
# Removed google.generativeai import as we're using direct API calls
from typing import Dict, Any, List, Optional, Tuple
import unicodedata
import threading
from utils.env_manager import env_manager
from config import GEMINI_MAX_OUTPUT_TOKENS, GEMINI_CONCURRENT_REQUESTS

# 导入新的模型客户端
from models.model_factory import model_factory

def secure_chinese_filename(filename):
    """
    支持中文的安全文件名处理函数
    保留中文字符，同时确保文件名安全
    """
    if not filename:
        return filename
    
    # 移除路径分隔符和其他危险字符（保留中文标点符号）
    dangerous_chars = ['/', '\\', '..', '<', '>', '"', '|', '?', '*', '\0']
    safe_filename = filename
    
    # 特别处理ASCII冒号（危险），但保留中文冒号（安全）
    safe_filename = safe_filename.replace(':', '_')  # 只替换ASCII冒号
    
    for char in dangerous_chars:
        safe_filename = safe_filename.replace(char, '_')
    
    # 移除开头和结尾的点号和空格（Windows文件名限制）
    safe_filename = safe_filename.strip('. ')
    
    # 限制文件名长度（考虑中文字符）
    if len(safe_filename.encode('utf-8')) > 200:  # 200字节限制
        # 保留扩展名
        if '.' in safe_filename:
            name, ext = safe_filename.rsplit('.', 1)
            # 截断名称部分，保留扩展名
            max_name_bytes = 200 - len(ext.encode('utf-8')) - 1  # -1 for dot
            while len(name.encode('utf-8')) > max_name_bytes and name:
                name = name[:-1]
            safe_filename = f"{name}.{ext}"
        else:
            # 没有扩展名，直接截断
            while len(safe_filename.encode('utf-8')) > 200 and safe_filename:
                safe_filename = safe_filename[:-1]
    
    # 如果文件名为空或只有扩展名，提供默认名称
    if not safe_filename or safe_filename.startswith('.'):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if '.' in filename:
            ext = filename.split('.')[-1]
            safe_filename = f"file_{timestamp}.{ext}"
        else:
            safe_filename = f"file_{timestamp}"
    
    return safe_filename

# 🔧 加载.env文件中的环境变量
print("🔧 加载环境变量...")
env_vars = env_manager.load_env()
if env_vars:
    # 设置环境变量到当前进程
    for key, value in env_vars.items():
        os.environ[key] = value
    api_keys = [k for k in env_vars.keys() if 'API_KEY' in k]
    if api_keys:
        print(f"✅ 从.env文件加载了 {len(api_keys)} 个API密钥")
        for key in api_keys:
            print(f"   - {key}: ****")
    else:
        print(f"📄 从.env文件加载了 {len(env_vars)} 个配置项")
else:
    print("📄 未找到.env文件或文件为空，将使用系统环境变量")

# 导入新的历史管理和标注模块
try:
    from database import db
    from history_manager import history_manager
    from annotation_system import annotation_system
    from utils.advanced_analytics import analytics
except ImportError as e:
    print(f"警告: 无法导入高级功能模块: {e}")
    db = None
    history_manager = None
    annotation_system = None
    analytics = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'model-evaluation-web-2024'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULTS_FOLDER'] = 'results'

# 注册分析API蓝图
app.register_blueprint(analytics_bp)
app.config['DATA_FOLDER'] = 'data'

# 确保文件夹存在
for folder in [app.config['UPLOAD_FOLDER'], app.config['RESULTS_FOLDER'], app.config['DATA_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

# 模型配置现在由 model_factory 统一管理

# Google API配置
# 配置Google Gemini API
MODEL_NAME = "gemini-2.5-flash"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    print(f"✅ Gemini配置成功: {MODEL_NAME}")
else:
    print("⚠️ 未配置GOOGLE_API_KEY")

# 全局任务状态管理
task_status = {}

class TaskStatus:
    def __init__(self, task_id):
        self.task_id = task_id
        self.status = "待开始"
        self.progress = 0
        self.total = 0
        self.current_step = ""
        self.result_file = ""
        self.error_message = ""
        self.evaluation_mode = ""
        self.selected_models = []
        self.start_time = datetime.now()
        self.end_time = None
        self.question_count = 0

# 流式响应解析现在由各自的客户端模块处理

# 模型答案获取现在由 model_factory 统一处理

async def get_multiple_model_answers(queries: List[str], selected_models: List[str], task_id: str, request_headers: dict = None) -> Dict[str, List[str]]:
    """获取多个模型的答案"""
    return await model_factory.get_multiple_model_answers(queries, selected_models, task_id, task_status, request_headers)

def detect_evaluation_mode(df: pd.DataFrame) -> str:
    """自动检测评测模式"""
    if 'answer' in df.columns:
        return 'objective'  # 客观题评测
    else:
        return 'subjective'  # 主观题评测

def parse_json_str(s: str) -> Dict[str, Any]:
    """解析JSON字符串 - 增强版，支持多种格式和错误恢复"""
    s = (s or "").strip()
    if not s:
        print("⚠️ JSON解析: 输入为空")
        return {}
    
    print(f"🔍 JSON解析: 开始解析长度为 {len(s)} 的字符串")
    print(f"📝 JSON解析: 原始内容前100字符: {s[:100]}...")
    
    # 预处理：移除常见的非JSON前缀和后缀
    original_s = s
    
    try:
        # 1. 处理markdown代码块
        if '```json' in s.lower():
            # 找到第一个```json和对应的结束```
            start_marker = s.lower().find('```json')
            if start_marker != -1:
                start_pos = start_marker + 7  # len('```json')
                # 从start_pos开始查找结束的```
                remaining = s[start_pos:]
                end_marker = remaining.find('```')
                if end_marker != -1:
                    s = remaining[:end_marker].strip()
                    print(f"✂️ JSON解析: 从markdown中提取JSON，长度: {len(s)}")
                else:
                    # 没有找到结束标记，取从```json后的所有内容
                    s = remaining.strip()
                    print(f"⚠️ JSON解析: 未找到结束markdown标记，使用剩余内容")
        
        elif '```' in s:
            # 通用代码块处理
            parts = s.split('```')
            if len(parts) >= 3:
                s = parts[1].strip()
                print(f"✂️ JSON解析: 从通用代码块中提取内容，长度: {len(s)}")
            elif len(parts) == 2:
                # 只有开始标记，没有结束标记
                s = parts[1].strip()
                print(f"⚠️ JSON解析: 只找到开始代码块标记")
        
        # 2. 移除常见的前缀文本
        prefixes_to_remove = [
            "这是评测结果:",
            "评测结果如下:",
            "根据评测标准，结果为:",
            "JSON格式输出:",
            "输出结果:",
            "结果:",
            "评分:",
        ]
        
        for prefix in prefixes_to_remove:
            if s.lower().startswith(prefix.lower()):
                s = s[len(prefix):].strip()
                print(f"✂️ JSON解析: 移除前缀 '{prefix}'")
                break
        
        # 3. 查找JSON对象的开始和结束
        # 找到第一个 { 或 [
        json_start = -1
        for i, char in enumerate(s):
            if char in '{[':
                json_start = i
                break
        
        if json_start == -1:
            print(f"❌ JSON解析: 未找到JSON起始符号 {{ 或 [")
            return {}
        
        # 从起始位置开始提取JSON
        s = s[json_start:]
        
        # 4. 尝试解析JSON
        try:
            result = json.loads(s)
            print(f"✅ JSON解析成功: 包含 {len(result)} 个顶级键")
            return result
        except json.JSONDecodeError as json_error:
            print(f"⚠️ 第一次JSON解析失败: {json_error}")
            
            # 5. 尝试修复常见的JSON错误
            fixed_attempts = []
            
            # 尝试1: 移除多余的逗号
            s_fixed = re.sub(r',\s*}', '}', s)  # 移除}前的逗号
            s_fixed = re.sub(r',\s*]', ']', s_fixed)  # 移除]前的逗号
            fixed_attempts.append(("移除多余逗号", s_fixed))
            
            # 尝试2: 修复未闭合的引号（简单情况）
            if s.count('"') % 2 != 0:
                s_fixed = s + '"'
                fixed_attempts.append(("添加缺失引号", s_fixed))
            
            # 尝试3: 添加缺失的闭合括号
            open_braces = s.count('{')
            close_braces = s.count('}')
            if open_braces > close_braces:
                s_fixed = s + '}' * (open_braces - close_braces)
                fixed_attempts.append(("添加缺失的}", s_fixed))
            
            # 尝试4: 查找最大的有效JSON片段
            brace_count = 0
            last_valid_pos = -1
            for i, char in enumerate(s):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_valid_pos = i + 1
                        break
            
            if last_valid_pos > 0:
                s_fixed = s[:last_valid_pos]
                fixed_attempts.append(("提取完整JSON片段", s_fixed))
            
            # 逐一尝试修复后的JSON
            for attempt_name, attempt_json in fixed_attempts:
                try:
                    result = json.loads(attempt_json)
                    print(f"✅ JSON解析成功 (使用{attempt_name}): 包含 {len(result)} 个顶级键")
                    return result
                except json.JSONDecodeError:
                    continue
            
            # 6. 如果所有尝试都失败，尝试提取关键信息
            print(f"⚠️ 所有JSON修复尝试失败，尝试提取关键信息")
            print(f"📝 原始响应内容: {original_s[:500]}...")
            
            # 使用正则表达式提取评分信息
            extracted_data = {}
            
            # 查找模型评分信息
            model_pattern = r'"?模型(\d+)"?\s*[:：]\s*{[^}]*"?评分"?\s*[:：]\s*["\']?(\d+)["\']?[^}]*}'
            matches = re.findall(model_pattern, original_s)
            
            for model_num, score in matches:
                key = f"模型{model_num}"
                try:
                    extracted_data[key] = {"评分": int(score), "理由": "自动提取的评分"}
                except ValueError:
                    pass
            
            if extracted_data:
                print(f"✅ 使用正则提取到 {len(extracted_data)} 个模型的评分")
                return extracted_data
            
            # 7. 最后的备用方案：返回空字典但记录详细错误
            print(f"❌ JSON解析完全失败")
            print(f"原始内容长度: {len(original_s)}")
            print(f"处理后内容: {s[:200]}...")
            print(f"JSON错误详情: {json_error}")
            
            return {}
    
    except Exception as e:
        print(f"❌ JSON解析过程中发生异常: {e}")
        print(f"异常类型: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return {}



def generate_default_evaluation_response(model_count: int = None, prompt: str = "") -> str:
    """生成默认的评测响应，当Gemini响应被截断时使用"""
    
    # 尝试从prompt中推断模型数量
    if model_count is None:
        # 在prompt中查找模型数量的线索
        import re
        model_pattern = r'模型(\d+)'
        matches = re.findall(model_pattern, prompt)
        if matches:
            model_count = max(int(match) for match in matches)
        else:
            # 默认假设有2个模型（常见情况）
            model_count = 2
    
    # 生成对应数量的模型评分
    default_response = {}
    for i in range(1, model_count + 1):
        default_response[f"模型{i}"] = {
            "评分": "3",
            "理由": "响应因达到最大token限制被截断，无法完整评测，给出中性评分"
        }
        
        # 如果是客观题，添加准确性字段
        if "准确性" in prompt or "标准答案" in prompt:
            default_response[f"模型{i}"]["准确性"] = "部分正确"
    
    import json
    return json.dumps(default_response, ensure_ascii=False)

async def query_gemini_model(prompt: str, api_key: str = None, retry_count: int = 3) -> str:
    """查询Gemini模型 使用数据库配置的端点 - 增强版，支持重试和更好的错误处理"""
    from database import db
    
    # 使用传入的API密钥或默认密钥
    actual_api_key = api_key or GOOGLE_API_KEY
    
    if not actual_api_key:
        return "Gemini模型调用失败: 未配置GOOGLE_API_KEY"
    
    # 从数据库获取配置
    api_endpoint = db.get_system_config('gemini_api_endpoint', 'https://gemini-proxy.hkgai.net/v1beta/models')
    model_name = db.get_system_config('gemini_model_name', MODEL_NAME)
    timeout_str = db.get_system_config('gemini_api_timeout', '60')
    
    try:
        timeout = int(timeout_str)
    except (ValueError, TypeError):
        timeout = 60
    
    # 构建 API 请求
    url = f"{api_endpoint}/{model_name}:generateContent"
    headers = {
        "x-goog-api-key": actual_api_key,
        "Content-Type": "application/json"
    }
    
    # 基础请求数据
    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,  # 降低随机性，提高JSON格式一致性
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": GEMINI_MAX_OUTPUT_TOKENS,
        }
    }
    
    # 尝试重试机制
    last_error = None
    for attempt in range(retry_count):
        try:
            print(f"🔄 Gemini API调用尝试 {attempt + 1}/{retry_count}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data, timeout=timeout) as response:
                    if response.status == 200:
                        try:
                            result = await response.json()
                        except json.JSONDecodeError as json_err:
                            print(f"⚠️ Gemini响应JSON解析失败: {json_err}")
                            # 尝试获取原始文本
                            text_response = await response.text()
                            print(f"📝 原始响应: {text_response[:200]}...")
                            if attempt < retry_count - 1:
                                continue
                            return f"Gemini模型调用失败: 响应JSON格式错误 - {json_err}"
                        
                        # 提取结果文本
                        if "candidates" in result and len(result["candidates"]) > 0:
                            candidate = result["candidates"][0]
                            
                            # 检查finishReason
                            if "finishReason" in candidate:
                                finish_reason = candidate["finishReason"]
                                
                                if finish_reason == "SAFETY":
                                    print(f"⚠️ Gemini响应被安全过滤器阻止")
                                    if attempt < retry_count - 1:
                                        # 稍微修改提示词重试
                                        data["contents"][0]["parts"][0]["text"] = prompt + "\n\n请严格按照JSON格式输出评测结果。"
                                        continue
                                    return "Gemini模型调用失败: 内容被安全过滤器阻止"
                                
                                elif finish_reason == "MAX_TOKENS":
                                    print(f"⚠️ Gemini响应因达到最大token限制被截断")
                                    print(f"📊 使用情况: {result.get('usageMetadata', {})}")
                                    
                                    # 尝试从不完整的响应中提取内容
                                    partial_text = None
                                    if "content" in candidate:
                                        content = candidate["content"]
                                        if "parts" in content and len(content["parts"]) > 0:
                                            if "text" in content["parts"][0]:
                                                partial_text = content["parts"][0]["text"]
                                                print(f"📝 获取到部分响应: {len(partial_text)} 字符")
                                        else:
                                            print(f"⚠️ content字段异常，缺少parts: {content}")
                                    
                                    # 如果有部分内容，尝试返回
                                    if partial_text and partial_text.strip():
                                        return partial_text
                                    
                                    # 如果没有可用内容，生成基于问题数量的默认评分结构
                                    print(f"⚠️ 无法获取完整响应，生成默认评分")
                                    
                                    # 使用智能默认响应生成
                                    return generate_default_evaluation_response(prompt=prompt)
                                
                                elif finish_reason in ["RECITATION", "OTHER"]:
                                    print(f"⚠️ Gemini响应因其他原因停止: {finish_reason}")
                                    if attempt < retry_count - 1:
                                        continue
                                    return f"Gemini模型调用失败: {finish_reason}"
                            
                            if "content" in candidate and "parts" in candidate["content"]:
                                parts = candidate["content"]["parts"]
                                if len(parts) > 0 and "text" in parts[0]:
                                    text_result = parts[0]["text"]
                                    
                                    # 验证返回的内容是否包含JSON结构
                                    if not text_result.strip():
                                        print(f"⚠️ Gemini返回空内容")
                                        if attempt < retry_count - 1:
                                            continue
                                        return "Gemini模型调用失败: 返回内容为空"
                                    
                                    # 检查是否包含可能的JSON结构
                                    if '{' not in text_result and '[' not in text_result:
                                        print(f"⚠️ Gemini返回内容不包含JSON结构: {text_result[:100]}...")
                                        if attempt < retry_count - 1:
                                            # 修改提示词强调JSON格式要求
                                            data["contents"][0]["parts"][0]["text"] = prompt + "\n\n重要：必须严格按照JSON格式输出，不要包含任何解释文字。"
                                            continue
                                    
                                    print(f"✅ Gemini评测成功，返回长度: {len(text_result)}")
                                    return text_result
                        
                        # 如果到这里，说明响应格式异常
                        print(f"⚠️ Gemini返回格式异常: {result}")
                        
                        # 检查是否有错误信息
                        if "error" in result:
                            error_msg = result["error"].get("message", "未知错误")
                            print(f"❌ Gemini API返回错误: {error_msg}")
                            if attempt < retry_count - 1:
                                await asyncio.sleep(1)  # 等待1秒后重试
                                continue
                            print(f"⚠️ API错误，生成默认评分")
                            return generate_default_evaluation_response(prompt=prompt)
                        
                        if attempt < retry_count - 1:
                            continue
                            
                        # 最后一次重试失败，生成默认响应避免完全失败
                        print(f"⚠️ 所有重试均失败，生成默认评分以继续评测")
                        return generate_default_evaluation_response(prompt=prompt)
                        
                    elif response.status == 429:  # 速率限制
                        print(f"⚠️ Gemini API速率限制，等待重试...")
                        if attempt < retry_count - 1:
                            await asyncio.sleep(2 ** attempt)  # 指数退避
                            continue
                        error_text = await response.text()
                        print(f"⚠️ 速率限制，生成默认评分")
                        return generate_default_evaluation_response(prompt=prompt)
                        
                    elif response.status == 400:  # 请求错误
                        error_text = await response.text()
                        print(f"❌ Gemini API请求错误: {error_text}")
                        try:
                            error_json = json.loads(error_text)
                            if "error" in error_json:
                                error_detail = error_json["error"].get("message", error_text)
                                print(f"⚠️ API参数错误，生成默认评分")
                                return generate_default_evaluation_response(prompt=prompt)
                        except:
                            pass
                        print(f"⚠️ 请求参数错误，生成默认评分")
                        return generate_default_evaluation_response(prompt=prompt)
                        
                    else:
                        error_text = await response.text()
                        print(f"❌ Gemini API请求失败: HTTP {response.status} - {error_text[:200]}...")
                        if attempt < retry_count - 1:
                            await asyncio.sleep(1)
                            continue
                        print(f"⚠️ HTTP错误，生成默认评分")
                        return generate_default_evaluation_response(prompt=prompt)
                        
        except asyncio.TimeoutError:
            print(f"⏰ Gemini API请求超时 (尝试 {attempt + 1}/{retry_count})")
            last_error = "请求超时"
            if attempt < retry_count - 1:
                await asyncio.sleep(2)
                continue
                
        except aiohttp.ClientError as client_err:
            print(f"🌐 Gemini API网络错误: {client_err}")
            last_error = f"网络连接错误: {client_err}"
            if attempt < retry_count - 1:
                await asyncio.sleep(1)
                continue
                
        except Exception as e:
            print(f"❌ Gemini评测异常 (尝试 {attempt + 1}/{retry_count}): {e}")
            last_error = str(e)
            if attempt < retry_count - 1:
                await asyncio.sleep(1)
                continue
    
    # 所有重试都失败了
    print(f"❌ Gemini API调用完全失败，已尝试 {retry_count} 次")
    print(f"⚠️ 生成默认评分以避免评测中断")
    
    # 生成默认响应确保评测流程继续
    return generate_default_evaluation_response(prompt=prompt)

def build_subjective_eval_prompt(query: str, answers: Dict[str, str], question_type: str = "", filename: str = None) -> str:
    """构建主观题评测提示"""
    type_context = f"问题类型: {question_type}\n" if question_type else ""
    
    models_text = ""
    for i, (model_name, answer) in enumerate(answers.items(), 1):
        models_text += f"模型{i}({model_name})回答: {answer}\n\n"
    
    model_keys = list(answers.keys())
    
    # 默认评分范围和格式
    default_score_range = "按提示词中的评分标准"
    score_instruction = "请严格按照上述提示词中定义的评分标准进行评分"
    score_validation = "评分必须符合提示词中定义的评分标准和范围"
    json_format = {f"模型{i+1}": {"评分": "按提示词标准", "理由": "评分理由"} for i in range(len(model_keys))}
    
    # 初始化为空的自定义提示词
    custom_prompt = None
    
    if filename:
        print(f"🔍 [评测引擎] 正在检查文件 {filename} 是否有自定义提示词...")
        try:
            file_prompt = db.get_file_prompt(filename)
            if file_prompt:
                prompt_length = len(file_prompt)
                print(f"✅ [评测引擎] 使用文件 {filename} 的自定义提示词，长度: {prompt_length} 字符")
                custom_prompt = file_prompt
                
                # 如果使用自定义提示词，更新评分指导
                score_instruction = "请严格按照上述自定义提示词中定义的评分标准进行评分"
                score_validation = "评分必须符合自定义提示词中定义的评分标准和范围"
            else:
                print(f"❌ [评测引擎] 文件 {filename} 未设置自定义提示词！")
                raise ValueError(f"文件 {filename} 必须设置自定义评测提示词才能进行主观题评测。请在管理后台为该文件配置评测提示词。")
        except Exception as e:
            if "必须设置自定义评测提示词" in str(e):
                raise e
            print(f"⚠️ [评测引擎] 获取文件 {filename} 的自定义提示词失败: {e}")
            raise ValueError(f"无法获取文件 {filename} 的评测提示词，请检查文件设置或联系管理员。")
    else:
        print(f"❌ [评测引擎] 主观题评测必须提供文件名以获取自定义提示词！")
        raise ValueError("主观题评测必须设置自定义评测提示词。请确保上传的文件已配置相应的评测标准。")
    
    if not custom_prompt:
        raise ValueError("未找到有效的自定义评测提示词，无法进行主观题评测。")
    
    return f"""
{custom_prompt}

=== 评测任务 ===
{type_context}问题: {query}

=== 模型回答 ===
{models_text}

=== 评测要求 ===
1. {score_instruction}
2. 提供详细的评分理由
3. 确保评分客观公正，基于事实和逻辑

=== 关键输出格式要求 ===
❗重要：必须严格按照JSON格式输出，不得包含任何解释文字❗

✅ 正确格式示例：
{json.dumps(json_format, ensure_ascii=False, indent=2)}

❌ 错误格式：
- 不要添加"以下是评测结果："等前缀
- 不要使用markdown代码块```json```
- 不要在JSON前后添加任何说明文字
- 不要使用不标准的引号或符号

⚠️ 格式检查清单：
1. 输出必须以 {{ 开始，以 }} 结束
2. 所有字符串必须用双引号包围
3. {score_validation}
4. 理由字段不能为空
5. JSON结构必须完整且有效

请现在输出评测结果的JSON：
"""

def build_objective_eval_prompt(query: str, standard_answer: str, answers: Dict[str, str], question_type: str = "", filename: str = None) -> str:
    """构建客观题评测提示"""
    type_context = f"问题类型: {question_type}\n" if question_type else ""
    
    models_text = ""
    for i, (model_name, answer) in enumerate(answers.items(), 1):
        models_text += f"模型{i}({model_name})回答: {answer}\n\n"
    
    model_keys = list(answers.keys())
    
    # 默认评分范围和格式
    score_instruction = "请严格按照上述提示词中定义的评分标准进行评分"
    score_validation = "评分必须符合提示词中定义的评分标准和范围"
    json_format = {f"模型{i+1}": {"评分": "按提示词标准", "准确性": "正确/部分正确/错误", "理由": "评分理由"} for i in range(len(model_keys))}
    
    # 初始化为空的自定义提示词
    custom_prompt = None
    
    if filename:
        print(f"🔍 [客观题评测引擎] 正在检查文件 {filename} 是否有自定义提示词...")
        try:
            file_prompt = db.get_file_prompt(filename)
            if file_prompt:
                prompt_length = len(file_prompt)
                print(f"✅ [客观题评测引擎] 使用文件 {filename} 的自定义提示词，长度: {prompt_length} 字符")
                custom_prompt = file_prompt
                
                # 如果使用自定义提示词，更新评分指导
                score_instruction = "请严格按照上述自定义提示词中定义的评分标准进行评分"
                score_validation = "评分必须符合自定义提示词中定义的评分标准和范围"
            else:
                print(f"❌ [客观题评测引擎] 文件 {filename} 未设置自定义提示词！")
                raise ValueError(f"文件 {filename} 必须设置自定义评测提示词才能进行客观题评测。请在管理后台为该文件配置评测提示词。")
        except Exception as e:
            if "必须设置自定义评测提示词" in str(e):
                raise e
            print(f"⚠️ [客观题评测引擎] 获取文件 {filename} 的自定义提示词失败: {e}")
            raise ValueError(f"无法获取文件 {filename} 的评测提示词，请检查文件设置或联系管理员。")
    else:
        print(f"❌ [客观题评测引擎] 客观题评测必须提供文件名以获取自定义提示词！")
        raise ValueError("客观题评测必须设置自定义评测提示词。请确保上传的文件已配置相应的评测标准。")
    
    if not custom_prompt:
        raise ValueError("未找到有效的自定义评测提示词，无法进行客观题评测。")
    
    return f"""
{custom_prompt}

=== 评测任务 ===
{type_context}问题: {query}
标准答案: {standard_answer}

=== 模型回答 ===
{models_text}

=== 评测要求 ===
1. {score_instruction}
2. 重点评估内容的准确性、完整性和语言本地化程度  
3. 提供详细的评分依据和理由
4. 客观公正，基于事实判断

=== 关键输出格式要求 ===
❗重要：必须严格按照JSON格式输出，不得包含任何解释文字❗

✅ 正确格式示例：
{json.dumps(json_format, ensure_ascii=False, indent=2)}

❌ 错误格式：
- 不要添加"以下是评测结果："等前缀
- 不要使用markdown代码块```json```
- 不要在JSON前后添加任何说明文字
- 不要使用不标准的引号或符号

⚠️ 格式检查清单：
1. 输出必须以 {{ 开始，以 }} 结束
2. 所有字符串必须用双引号包围
3. {score_validation}
4. 准确性必须是"正确"、"部分正确"或"错误"之一
5. 理由字段不能为空
6. JSON结构必须完整且有效

请现在输出评测结果的JSON：
"""

def flatten_json(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """平铺JSON字典"""
    flat_data = {}
    for key, value in data.items():
        new_key = f"{prefix}_{key}" if prefix else key
        if isinstance(value, dict):
            flat_data.update(flatten_json(value, new_key))
        elif isinstance(value, list):
            flat_data[new_key] = str(value)
        else:
            flat_data[new_key] = value
    return flat_data

async def evaluate_models(data: List[Dict], mode: str, model_results: Dict[str, List[str]], task_id: str, google_api_key: str = None, filename: str = None) -> str:
    """评测模型表现"""
    if task_id in task_status:
        task_status[task_id].status = "评测中"
        task_status[task_id].total = len(data)
        task_status[task_id].progress = 0
        
        # 更新数据库状态
        db.update_task_status(task_id, "running")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(app.config['RESULTS_FOLDER'], f"evaluation_result_{timestamp}.csv")
    
    # 准备CSV表头
    model_names = list(model_results.keys())
    base_headers = ['序号', '类型', 'query']
    
    if mode == 'objective':
        base_headers.append('标准答案')
    
    # 动态生成模型相关的列
    eval_headers = []
    for i, model_name in enumerate(model_names, 1):
        eval_headers.extend([
            f'{model_name}_答案',
            f'{model_name}_评分',
            f'{model_name}_理由'
        ])
        if mode == 'objective':
            eval_headers.append(f'{model_name}_准确性')
    
    headers = base_headers + eval_headers
    
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        # 创建并发任务来评测所有问题，添加实时进度更新
        print(f"🚀 开始并发评测，并发数: {GEMINI_CONCURRENT_REQUESTS}")
        semaphore = asyncio.Semaphore(GEMINI_CONCURRENT_REQUESTS)
        
        # 进度计数器（线程安全）
        import threading
        progress_lock = threading.Lock()
        completed_count = [0]  # 使用列表以便在闭包中修改
        
        async def evaluate_single_question(i: int, row: Dict) -> Tuple[int, List]:
            """评测单个问题"""
            async with semaphore:
                try:
                    # 检查任务是否被取消
                    if task_id in task_status:
                        # 检查数据库状态
                        db_task = db.get_running_task(task_id)
                        if not db_task or db_task['status'] == 'cancelled':
                            print(f"任务 {task_id} 已被取消，跳过第{i+1}题")
                            return i, []
                    
                    query = str(row.get("query", ""))
                    question_type = str(row.get("type", "未分类"))
                    standard_answer = str(row.get("answer", "")) if mode == 'objective' else ""
                    
                    # 获取各模型的答案
                    current_answers = {}
                    for model_name in model_names:
                        if i < len(model_results[model_name]):
                            current_answers[model_name] = model_results[model_name][i]
                        else:
                            current_answers[model_name] = "获取答案失败"
                    
                    # 构建评测提示
                    if mode == 'objective':
                        prompt = build_objective_eval_prompt(query, standard_answer, current_answers, question_type, filename)
                    else:
                        prompt = build_subjective_eval_prompt(query, current_answers, question_type, filename)
                    
                    try:
                        print(f"🔄 开始评测第{i+1}题...")
                        gem_raw = await query_gemini_model(prompt, google_api_key)
                        result_json = parse_json_str(gem_raw)
                        print(f"✅ 完成评测第{i+1}题")
                    except Exception as e:
                        print(f"❌ 评测第{i+1}题时出错: {e}")
                        result_json = {}
                    
                    # 构造CSV行数据
                    row_data = [i+1, question_type, query]
                    if mode == 'objective':
                        row_data.append(standard_answer)
                    
                    # 添加各模型的结果
                    for j, model_name in enumerate(model_names, 1):
                        model_key = f"模型{j}"
                        row_data.append(current_answers[model_name])  # 模型答案
                        
                        if model_key in result_json:
                            row_data.append(result_json[model_key].get("评分", ""))  # 评分
                            row_data.append(result_json[model_key].get("理由", ""))  # 理由
                            if mode == 'objective':
                                row_data.append(result_json[model_key].get("准确性", ""))  # 准确性
                        else:
                            row_data.extend(["", ""])  # 评分、理由
                            if mode == 'objective':
                                row_data.append("")  # 准确性
                    
                    # 实时更新进度
                    with progress_lock:
                        completed_count[0] += 1
                        current_progress = completed_count[0]
                        
                        if task_id in task_status:
                            task_status[task_id].progress = current_progress
                            task_status[task_id].current_step = f"已评测 {current_progress}/{len(data)} 题 (第{i+1}题完成)"
                            
                            # 同时更新数据库
                            try:
                                db.update_task_progress(task_id, current_progress, task_status[task_id].current_step)
                            except Exception as e:
                                print(f"⚠️ 更新数据库进度失败: {e}")
                    
                    return i, row_data
                    
                except Exception as e:
                    print(f"❌ 评测第{i+1}题出现异常: {e}")
                    # 即使失败也要更新进度
                    with progress_lock:
                        completed_count[0] += 1
                        current_progress = completed_count[0]
                        if task_id in task_status:
                            task_status[task_id].progress = current_progress
                            task_status[task_id].current_step = f"已处理 {current_progress}/{len(data)} 题 (第{i+1}题失败)"
                            try:
                                db.update_task_progress(task_id, current_progress, task_status[task_id].current_step)
                            except:
                                pass
                    return i, []
        
        # 创建所有评测任务
        tasks = [evaluate_single_question(i, row) for i, row in enumerate(data)]
        
        # 并发执行所有任务
        print(f"📊 开始并发执行 {len(tasks)} 个评测任务...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 按序号排序并写入CSV
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                print(f"❌ 评测任务异常: {result}")
                continue
            if len(result) == 2 and len(result[1]) > 0:  # 有效结果
                valid_results.append(result)
        
        # 按题目序号排序
        valid_results.sort(key=lambda x: x[0])
        
        # 写入CSV
        print(f"📝 写入CSV文件，共 {len(valid_results)} 条有效记录...")
        for i, (question_index, row_data) in enumerate(valid_results):
            writer.writerow(row_data)
        
        print(f"✅ 并发评测完成，成功处理 {len(valid_results)}/{len(data)} 题")

    return output_file

def run_async_task(func, *args):
    """在新线程中运行异步任务"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(func(*args))
    finally:
        loop.close()


# ===== 用户认证装饰器 =====

def login_required(f):
    """登录验证装饰器"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': '需要登录', 'redirect': '/login'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """管理员权限验证装饰器"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': '需要登录', 'redirect': '/login'}), 401
            return redirect(url_for('login'))
        
        user = db.get_user_by_id(session['user_id'])
        if not user or user['role'] != 'admin':
            if request.is_json:
                return jsonify({'error': '需要管理员权限'}), 403
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function


# ===== 路由定义 =====

@app.route('/')
def index():
    """首页"""
    # 如果未登录，显示欢迎页面
    if 'user_id' not in session:
        return render_template('welcome.html')
    
    # 如果已登录，显示主系统页面
    current_user = db.get_user_by_id(session['user_id'])
    return render_template('index.html', current_user=current_user)


@app.route('/welcome')
def welcome():
    """欢迎页面"""
    return render_template('welcome.html')

def auto_fix_file_path(file_record):
    """
    自动修复文件路径 - 当数据库中的文件路径不存在时，尝试在uploads目录中找到匹配的文件
    """
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            return None
            
        db_filename = file_record['filename']
        uploaded_by = file_record['uploaded_by']
        
        print(f"🔍 搜索匹配文件: {db_filename}")
        
        # 获取uploads目录中的所有文件
        actual_files = [f for f in os.listdir(upload_folder) 
                       if f.endswith(('.xlsx', '.xls', '.csv'))]
        
        # 获取用户信息以便匹配
        uploader_info = db.get_user_by_id(uploaded_by)
        username = uploader_info['username'] if uploader_info else None
        display_name = uploader_info['display_name'] if uploader_info else None
        
        print(f"🔍 用户信息: username={username}, display_name={display_name}")
        
        # 匹配策略
        def calculate_similarity(actual_file, db_file):
            """计算文件名相似度"""
            score = 0
            
            # 1. 如果用户名在文件名中，优先匹配
            if username and username in actual_file:
                score += 50
            if display_name and display_name in actual_file:
                score += 50
                
            # 2. 去除用户名后的文件名相似度
            clean_actual = actual_file.replace(username or '', '').replace(display_name or '', '')
            clean_db = db_file.replace(username or '', '').replace(display_name or '', '')
            
            # 去除数字和特殊字符进行比较
            import re
            clean_actual = re.sub(r'[0-9_\-]+', '', clean_actual)
            clean_db = re.sub(r'[0-9_\-]+', '', clean_db)
            
            if clean_actual.lower() in clean_db.lower() or clean_db.lower() in clean_actual.lower():
                score += 30
                
            # 3. 扩展名匹配
            if actual_file.split('.')[-1] == db_file.split('.')[-1]:
                score += 10
                
            return score
        
        # 寻找最佳匹配
        best_match = None
        best_score = 0
        
        for actual_file in actual_files:
            score = calculate_similarity(actual_file, db_filename)
            print(f"  📊 {actual_file}: 匹配分数 {score}")
            
            if score > best_score and score >= 40:  # 最低匹配阈值
                best_match = actual_file
                best_score = score
        
        if best_match:
            new_filepath = os.path.join(upload_folder, best_match)
            
            # 更新数据库记录
            try:
                with sqlite3.connect(db.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE uploaded_files 
                        SET filename = ?, file_path = ?, original_filename = ?
                        WHERE id = ?
                    ''', (best_match, new_filepath, best_match, file_record['id']))
                    conn.commit()
                    
                print(f"✅ 数据库更新成功: {db_filename} -> {best_match}")
                return new_filepath
                
            except Exception as e:
                print(f"❌ 数据库更新失败: {e}")
                return None
        else:
            print(f"❌ 未找到匹配文件")
            return None
            
    except Exception as e:
        print(f"❌ 自动修复失败: {e}")
        return None


@app.route('/get_uploaded_files', methods=['GET'])
@login_required
def get_uploaded_files():
    """获取已上传的文件列表（按用户权限过滤）"""
    try:
        current_user = db.get_user_by_id(session['user_id'])
        is_admin = current_user and current_user['role'] == 'admin'
        
        # 获取用户筛选参数（仅管理员可用）
        selected_user = request.args.get('user_id') if is_admin else None
        
        upload_folder = app.config['UPLOAD_FOLDER']
        files = []
        
        # 先从数据库获取文件记录
        if is_admin:
            if selected_user:
                # 管理员查看指定用户的文件
                db_files = db.get_user_uploaded_files(uploaded_by=selected_user, include_all_users=False)
            else:
                # 管理员查看所有用户的文件
                db_files = db.get_user_uploaded_files(include_all_users=True)
        else:
            # 普通用户只能看自己的文件
            db_files = db.get_user_uploaded_files(uploaded_by=session['user_id'], include_all_users=False)
        
        # 处理数据库中的文件记录
        for file_record in db_files:
            try:
                filepath = file_record['file_path']
                
                # 🔧 自动文件名同步检查
                if not os.path.exists(filepath):
                    print(f"🔍 文件不存在，尝试自动修复: {file_record['filename']}")
                    
                    # 尝试在uploads目录中找到匹配的文件
                    fixed_filepath = auto_fix_file_path(file_record)
                    if fixed_filepath:
                        filepath = fixed_filepath
                        print(f"✅ 自动修复成功: {file_record['filename']} -> {filepath}")
                    else:
                        print(f"❌ 无法自动修复: {file_record['filename']}")
                        continue
                
                if os.path.exists(filepath):
                    stat = os.stat(filepath)
                    
                    # 确保文件有提示词记录
                    db.create_file_prompt_if_not_exists(file_record['filename'])
                    
                    # 获取提示词信息
                    prompt_info = db.get_file_prompt_info(file_record['filename'])
                    has_custom_prompt = prompt_info is not None
                    
                    # 获取上传者信息
                    uploader_info = db.get_user_by_id(file_record['uploaded_by'])
                    uploader_name = uploader_info['display_name'] if uploader_info else '未知用户'
                    
                    files.append({
                        'filename': file_record['filename'],
                        'original_filename': file_record['original_filename'],
                        'size': stat.st_size,
                        'upload_time': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        'size_formatted': f"{stat.st_size / 1024:.1f} KB" if stat.st_size < 1024*1024 else f"{stat.st_size / (1024*1024):.1f} MB",
                        'has_custom_prompt': has_custom_prompt,
                        'prompt_updated_at': prompt_info['updated_at'] if prompt_info else None,
                        'uploaded_by': file_record['uploaded_by'],
                        'uploader_name': uploader_name,
                        'mode': file_record.get('mode', 'unknown'),
                        'total_count': file_record.get('total_count', 0)
                    })
                    
                    print(f"✅ 加载测试集文件: {file_record['filename']} (上传者: {uploader_name})")
            except Exception as file_error:
                print(f"❌ 处理文件记录 {file_record.get('filename', 'unknown')} 时出错: {file_error}")
                continue
        
        # 如果是管理员且没有选择特定用户，还需要检查文件系统中的遗留文件（没有数据库记录的）
        if is_admin and not selected_user and os.path.exists(upload_folder):
            existing_filenames = {f['filename'] for f in files}
            
            try:
                filenames = os.listdir(upload_folder)
                for filename in filenames:
                    if filename.endswith(('.xlsx', '.xls', '.csv')) and filename not in existing_filenames:
                        try:
                            filepath = os.path.join(upload_folder, filename)
                            if not os.path.exists(filepath):
                                continue
                                
                            stat = os.stat(filepath)
                            
                            # 确保文件有提示词记录
                            db.create_file_prompt_if_not_exists(filename)
                            
                            # 获取提示词信息
                            prompt_info = db.get_file_prompt_info(filename)
                            has_custom_prompt = prompt_info is not None
                            
                            files.append({
                                'filename': filename,
                                'original_filename': filename,
                                'size': stat.st_size,
                                'upload_time': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                                'size_formatted': f"{stat.st_size / 1024:.1f} KB" if stat.st_size < 1024*1024 else f"{stat.st_size / (1024*1024):.1f} MB",
                                'has_custom_prompt': has_custom_prompt,
                                'prompt_updated_at': prompt_info['updated_at'] if prompt_info else None,
                                'uploaded_by': 'legacy',
                                'uploader_name': '历史数据',
                                'mode': 'unknown',
                                'total_count': 0
                            })
                            
                            print(f"✅ 加载遗留文件: {filename}")
                            
                        except Exception as file_error:
                            print(f"❌ 处理遗留文件 {filename} 时出错: {file_error}")
                            continue
            except UnicodeDecodeError as e:
                print(f"⚠️ 编码错误: {e}")
        
        # 按上传时间倒序排列
        files.sort(key=lambda x: x['upload_time'], reverse=True)
        print(f"📋 共找到 {len(files)} 个测试集文件")
        
        # 获取用户列表（仅管理员需要）
        users_list = []
        if is_admin:
            users_list = db.list_users()
        
        # 设置正确的响应头确保中文正确传输
        response = jsonify({
            'success': True, 
            'files': files,
            'is_admin': is_admin,
            'users': users_list,
            'selected_user': selected_user
        })
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
        
    except Exception as e:
        print(f"❌ 获取文件列表失败: {e}")
        return jsonify({'error': f'获取文件列表失败: {str(e)}'}), 500

@app.route('/api/debug/files', methods=['GET'])
@login_required  
def debug_files():
    """调试：显示文件系统中的所有文件"""
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        debug_info = {
            'upload_folder': upload_folder,
            'folder_exists': os.path.exists(upload_folder),
            'all_files': [],
            'supported_files': [],
            'chinese_files': []
        }
        
        if os.path.exists(upload_folder):
            # 获取所有文件
            all_files = os.listdir(upload_folder)
            debug_info['all_files'] = all_files
            
            # 过滤支持的文件格式
            supported_files = [f for f in all_files if f.endswith(('.xlsx', '.xls', '.csv'))]
            debug_info['supported_files'] = supported_files
            
            # 查找包含中文的文件
            chinese_files = [f for f in supported_files if any('\u4e00' <= char <= '\u9fff' for char in f)]
            debug_info['chinese_files'] = chinese_files
            
            # 文件详细信息
            file_details = []
            for filename in supported_files:
                filepath = os.path.join(upload_folder, filename)
                try:
                    stat = os.stat(filepath)
                    file_details.append({
                        'filename': filename,
                        'size': stat.st_size,
                        'is_chinese': any('\u4e00' <= char <= '\u9fff' for char in filename),
                        'encoded_bytes': list(filename.encode('utf-8')),
                        'upload_time': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except Exception as e:
                    file_details.append({
                        'filename': filename,
                        'error': str(e)
                    })
            
            debug_info['file_details'] = file_details
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({'error': f'调试失败: {str(e)}'}), 500

@app.route('/api/debug/csv_file_status/<path:filename>')
@login_required
def debug_csv_file_status(filename):
    """调试CSV文件状态"""
    try:
        # 计算文件路径
        filepath = os.path.join(app.config['RESULTS_FOLDER'], filename)
        
        # 检查文件系统状态
        file_exists = os.path.exists(filepath)
        
        # 检查数据库状态
        result_id = None
        db_record = None
        if db:
            result_id = db.get_result_id_by_filename(filename)
            if result_id:
                # 获取数据库中的详细记录
                with sqlite3.connect(db.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT * FROM evaluation_results WHERE id = ?', (result_id,))
                    row = cursor.fetchone()
                    if row:
                        columns = [description[0] for description in cursor.description]
                        db_record = dict(zip(columns, row))
        
        # 检查可能的文件位置
        possible_files = []
        
        # 在results目录中查找
        if os.path.exists(app.config['RESULTS_FOLDER']):
            for file in os.listdir(app.config['RESULTS_FOLDER']):
                if filename in file or file in filename:
                    possible_files.append({
                        'path': os.path.join(app.config['RESULTS_FOLDER'], file),
                        'location': 'results',
                        'filename': file
                    })
        
        # 在results_history目录中查找
        history_path = os.path.join(os.path.dirname(app.config['RESULTS_FOLDER']), 'results_history')
        if os.path.exists(history_path):
            for file in os.listdir(history_path):
                if filename in file or file in filename:
                    possible_files.append({
                        'path': os.path.join(history_path, file),
                        'location': 'results_history',
                        'filename': file
                    })
        
        return jsonify({
            'filename': filename,
            'target_filepath': filepath,
            'file_exists': file_exists,
            'database_result_id': result_id,
            'database_record': db_record,
            'possible_files': possible_files,
            'results_folder': app.config['RESULTS_FOLDER'],
            'files_in_results': os.listdir(app.config['RESULTS_FOLDER']) if os.path.exists(app.config['RESULTS_FOLDER']) else []
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_file/<filename>', methods=['DELETE'])
@login_required
def delete_file(filename):
    """删除上传的文件（含权限检查）"""
    try:
        current_user = db.get_user_by_id(session['user_id'])
        is_admin = current_user and current_user['role'] == 'admin'
        
        filename = secure_chinese_filename(filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404
        
        # 权限检查：查找文件的上传记录
        file_record = db.get_uploaded_file_by_filename(filename)
        if file_record:
            # 普通用户只能删除自己上传的文件
            if not is_admin and file_record['uploaded_by'] != session['user_id']:
                return jsonify({'error': '没有权限删除此文件'}), 403
            
            # 软删除数据库记录
            db.delete_uploaded_file_record(file_record['id'])
        elif not is_admin:
            # 如果没有数据库记录且用户不是管理员，禁止删除
            return jsonify({'error': '没有权限删除此文件'}), 403
        
        os.remove(filepath)
        print(f"✅ 文件已删除: {filename} (用户: {current_user['display_name']})")
        return jsonify({'success': True, 'message': f'文件 {filename} 已删除'})
    except Exception as e:
        return jsonify({'error': f'删除文件失败: {str(e)}'}), 500

@app.route('/download_uploaded_file/<filename>', methods=['GET'])
@login_required
def download_uploaded_file(filename):
    """下载上传的文件"""
    try:
        filename = secure_chinese_filename(filename)
        upload_folder = app.config['UPLOAD_FOLDER']
        return send_from_directory(upload_folder, filename, as_attachment=True)
    except Exception as e:
        return jsonify({'error': f'下载文件失败: {str(e)}'}), 500

@app.route('/check_file_exists/<filename>', methods=['GET'])
@login_required
def check_file_exists(filename):
    """检查文件是否已存在"""
    filename = secure_chinese_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    exists = os.path.exists(filepath)
    return jsonify({'exists': exists, 'filename': filename})

@app.route('/api/dataset/rename', methods=['PUT'])
@login_required
def rename_dataset_file():
    """重命名数据集文件"""
    try:
        data = request.get_json()
        original_filename = data.get('original_filename', '').strip()
        new_filename = data.get('new_filename', '').strip()
        
        if not original_filename or not new_filename:
            return jsonify({'success': False, 'error': '文件名不能为空'}), 400
        
        # 安全文件名处理
        original_filename = secure_chinese_filename(original_filename)
        new_filename = secure_chinese_filename(new_filename)
        print(f"🏷️ 重命名文件: '{original_filename}' -> '{new_filename}'")
        
        # 构建文件路径
        upload_folder = app.config['UPLOAD_FOLDER']
        original_path = os.path.join(upload_folder, original_filename)
        new_path = os.path.join(upload_folder, new_filename)
        
        # 检查原文件是否存在
        if not os.path.exists(original_path):
            return jsonify({'success': False, 'error': '原文件不存在'}), 404
        
        # 检查新文件名是否已存在
        if os.path.exists(new_path):
            return jsonify({'success': False, 'error': '目标文件名已存在'}), 400
        
        # 重命名文件
        os.rename(original_path, new_path)
        print(f"✅ 文件重命名成功: {original_filename} -> {new_filename}")
        
        # 🔧 更新数据库中的uploaded_files记录
        try:
            if db:
                # 更新uploaded_files表中的记录
                import sqlite3
                with sqlite3.connect(db.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE uploaded_files 
                        SET filename = ?, file_path = ?, original_filename = ?
                        WHERE filename = ? AND is_active = 1
                    ''', (new_filename, new_path, new_filename, original_filename))
                    
                    if cursor.rowcount > 0:
                        conn.commit()
                        print(f"✅ 数据库记录已更新: {original_filename} -> {new_filename}")
                    else:
                        print(f"⚠️ 未找到数据库记录: {original_filename}")
                        
        except Exception as e:
            print(f"⚠️ 更新数据库记录时出现警告: {e}")
            # 不阻断重命名操作，仅记录警告
        
        # 更新数据库中的文件提示词关联（如果存在）
        try:
            if db:
                # 检查是否有与原文件名关联的提示词
                old_prompt_info = db.get_file_prompt_info(original_filename)
                if old_prompt_info:
                    old_prompt = old_prompt_info['custom_prompt']
                    updated_by = old_prompt_info['updated_by']
                    
                    # 为新文件名设置相同的提示词
                    success = db.set_file_prompt(new_filename, old_prompt, updated_by)
                    if success:
                        print(f"✅ 提示词关联已更新: {original_filename} -> {new_filename}")
                        
                        # 删除旧的提示词记录（避免数据冗余）
                        deleted = db.delete_file_prompt(original_filename)
                        if deleted:
                            print(f"🗑️ 已删除旧文件的提示词记录: {original_filename}")
                        else:
                            print(f"⚠️ 删除旧文件提示词记录失败: {original_filename}")
                    else:
                        print(f"❌ 设置新文件提示词失败: {new_filename}")
                else:
                    print(f"📝 原文件 {original_filename} 没有提示词记录，无需迁移")
        except Exception as e:
            print(f"⚠️ 更新提示词关联时出现警告: {e}")
            # 不阻断重命名操作，仅记录警告
        
        return jsonify({
            'success': True, 
            'message': '文件重命名成功',
            'original_filename': original_filename,
            'new_filename': new_filename
        })
        
    except Exception as e:
        print(f"❌ 文件重命名失败: {e}")
        return jsonify({'success': False, 'error': f'重命名失败: {str(e)}'}), 500

@app.route('/upload_file', methods=['POST'])
@login_required
def upload_file():
    """上传评测文件"""
    # 检查是否是选择历史文件
    if request.content_type == 'application/json':
        data = request.get_json()
        existing_file = data.get('existing_file')
        if existing_file:
            return analyze_existing_file(existing_file)
    
    if 'file' not in request.files:
        return jsonify({'error': '没有选择文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    # 检查是否允许覆盖
    overwrite = request.form.get('overwrite', 'false').lower() == 'true'
    
    if file and file.filename.endswith(('.xlsx', '.xls', '.csv')):
        filename = secure_chinese_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        print(f"📤 上传文件: 原始名称='{file.filename}' -> 安全名称='{filename}'")
        
        # 检查文件冲突，考虑用户权限
        current_user_id = session['user_id']
        file_conflict_result = check_file_conflict(filename, current_user_id, overwrite)
        if file_conflict_result:
            return file_conflict_result
        
        file.save(filepath)
        
        try:
            # 读取文件
            if filename.endswith('.csv'):
                df = pd.read_csv(filepath, encoding='utf-8-sig')
            else:
                df = pd.read_excel(filepath, engine='openpyxl')
            
            # 检查必需列
            if 'query' not in df.columns:
                return jsonify({'error': '文件必须包含"query"列'}), 400
            
            # 检测评测模式
            mode = detect_evaluation_mode(df)
            
            # 统计信息
            total_count = len(df)
            type_counts = df['type'].value_counts().to_dict() if 'type' in df.columns else {'未分类': total_count}
            
            # 获取文件大小
            file_size = os.path.getsize(filepath)
            
            # 为新上传的文件创建默认提示词记录
            current_user = db.get_user_by_id(session['user_id'])
            created_by = current_user['username'] if current_user else 'system'
            db.create_file_prompt_if_not_exists(filename, created_by=created_by)
            
            # 保存文件上传记录到数据库
            file_id = db.save_uploaded_file(
                filename=filename,
                original_filename=file.filename,
                file_path=filepath,
                uploaded_by=session['user_id'],
                file_type='dataset',
                mode=mode,
                total_count=total_count,
                file_size=file_size,
                metadata={
                    'type_counts': type_counts,
                    'has_answer': 'answer' in df.columns,
                    'has_type': 'type' in df.columns,
                    'columns': list(df.columns)
                }
            )
            
            if file_id:
                print(f"✅ 保存文件上传记录: {filename} (ID: {file_id}, 用户: {current_user['display_name']})")
            else:
                print(f"⚠️ 保存文件上传记录失败: {filename}")
            
            return jsonify({
                'success': True,
                'filename': filename,
                'mode': mode,
                'total_count': total_count,
                'type_counts': type_counts,
                'preview': df.head(5).to_dict('records'),
                'has_answer': 'answer' in df.columns,
                'has_type': 'type' in df.columns
            })
        except Exception as e:
            return jsonify({'error': f'文件解析错误: {str(e)}'}), 400
    
    return jsonify({'error': '不支持的文件格式，请上传 .xlsx、.xls 或 .csv 文件'}), 400

def check_file_conflict(filename, current_user_id, overwrite):
    """检查文件冲突，考虑用户权限"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    current_user = db.get_user_by_id(current_user_id)
    is_admin = current_user and current_user['role'] == 'admin'
    
    # 检查数据库中的文件记录
    file_record = db.get_uploaded_file_by_filename(filename)
    file_exists_in_system = os.path.exists(filepath)
    
    if file_record or file_exists_in_system:
        if not overwrite:
            # 检查文件所有者
            if file_record:
                file_owner_id = file_record['uploaded_by']
                file_owner = db.get_user_by_id(file_owner_id)
                file_owner_name = file_owner['display_name'] if file_owner else '未知用户'
                
                if file_owner_id != current_user_id and not is_admin:
                    # 不同用户的文件，建议重命名
                    current_user = db.get_user_by_id(current_user_id)
                    current_user_name = current_user['display_name'] if current_user and current_user['display_name'] else current_user['username'] if current_user else 'user'
                    
                    # 生成建议的文件名，确保不与现有文件冲突
                    name_part, ext_part = os.path.splitext(filename)
                    suggested_filename = f"{name_part}_{current_user_name}{ext_part}"
                    
                    # 检查建议的文件名是否也存在冲突
                    counter = 1
                    while True:
                        suggested_filepath = os.path.join(app.config['UPLOAD_FOLDER'], suggested_filename)
                        suggested_file_record = db.get_uploaded_file_by_filename(suggested_filename)
                        
                        # 如果文件不存在，或者是当前用户自己的文件，则可以使用
                        if not os.path.exists(suggested_filepath) and not suggested_file_record:
                            break
                        elif suggested_file_record and suggested_file_record['uploaded_by'] == current_user_id:
                            break
                        else:
                            # 文件名冲突，添加数字后缀
                            suggested_filename = f"{name_part}_{current_user_name}_{counter}{ext_part}"
                            counter += 1
                            if counter > 100:  # 防止无限循环
                                suggested_filename = f"{name_part}_{current_user_id}_{int(time.time())}{ext_part}"
                                break
                    
                    return jsonify({
                        'error': 'file_owned_by_other_suggest_rename',
                        'message': f'文件 "{filename}" 已被用户 "{file_owner_name}" 上传。',
                        'filename': filename,
                        'owner': file_owner_name,
                        'suggested_filename': suggested_filename,
                        'current_user_name': current_user_name
                    }), 409
                elif file_owner_id == current_user_id:
                    # 自己的文件，询问是否覆盖
                    return jsonify({
                        'error': 'file_exists_own',
                        'message': f'您已上传过文件 "{filename}"，是否要覆盖？',
                        'filename': filename
                    }), 409
                elif is_admin:
                    # 管理员可以覆盖任何文件，但需要确认
                    return jsonify({
                        'error': 'file_exists_admin',
                        'message': f'文件 "{filename}" 已被用户 "{file_owner_name}" 上传，您是管理员，是否要覆盖？',
                        'filename': filename,
                        'owner': file_owner_name
                    }), 409
            else:
                # 文件存在于系统但没有数据库记录（遗留文件）
                if is_admin:
                    return jsonify({
                        'error': 'file_exists_legacy',
                        'message': f'文件 "{filename}" 已存在（其他用户数据），是否要覆盖？',
                        'filename': filename
                    }), 409
                else:
                    # 普通用户不能覆盖遗留文件，提供智能重命名建议
                    current_user = db.get_user_by_id(current_user_id)
                    current_user_name = current_user['display_name'] if current_user and current_user['display_name'] else current_user['username'] if current_user else 'user'
                    
                    # 生成建议的文件名，确保不与现有文件冲突
                    name_part, ext_part = os.path.splitext(filename)
                    suggested_filename = f"{name_part}_{current_user_name}{ext_part}"
                    
                    # 检查建议的文件名是否也存在冲突
                    counter = 1
                    while True:
                        suggested_filepath = os.path.join(app.config['UPLOAD_FOLDER'], suggested_filename)
                        suggested_file_record = db.get_uploaded_file_by_filename(suggested_filename)
                        
                        # 如果文件不存在，或者是当前用户自己的文件，则可以使用
                        if not os.path.exists(suggested_filepath) and not suggested_file_record:
                            break
                        elif suggested_file_record and suggested_file_record['uploaded_by'] == current_user_id:
                            break
                        else:
                            # 文件名冲突，添加数字后缀
                            suggested_filename = f"{name_part}_{current_user_name}_{counter}{ext_part}"
                            counter += 1
                            if counter > 100:  # 防止无限循环
                                suggested_filename = f"{name_part}_{current_user_id}_{int(time.time())}{ext_part}"
                                break
                    
                    return jsonify({
                        'error': 'file_legacy_suggest_rename',
                        'message': f'文件 "{filename}" 是系统历史数据。',
                        'filename': filename,
                        'owner': '历史数据',
                        'suggested_filename': suggested_filename,
                        'current_user_name': current_user_name
                    }), 409
        else:
            # 用户确认覆盖，再次检查权限
            if file_record:
                file_owner_id = file_record['uploaded_by']
                if file_owner_id != current_user_id and not is_admin:
                    return jsonify({
                        'error': 'permission_denied',
                        'message': '您没有权限覆盖其他用户的文件。'
                    }), 403
    
    return None  # 没有冲突

def analyze_existing_file(filename):
    """分析已存在的文件"""
    try:
        filename = secure_chinese_filename(filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404
        
        # 读取文件
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath, encoding='utf-8-sig')
        else:
            df = pd.read_excel(filepath, engine='openpyxl')
        
        # 检查必需列
        if 'query' not in df.columns:
            return jsonify({'error': '文件必须包含"query"列'}), 400
        
        # 检测评测模式
        mode = detect_evaluation_mode(df)
        
        # 统计信息
        total_count = len(df)
        type_counts = df['type'].value_counts().to_dict() if 'type' in df.columns else {'未分类': total_count}
        
        # 生成预览数据
        preview_data = df.head(3).to_dict('records')
        
        return jsonify({
            'success': True,
            'filename': filename,
            'mode': mode,
            'total_count': total_count,
            'type_counts': type_counts,
            'has_answer': 'answer' in df.columns,
            'has_type': 'type' in df.columns,
            'preview': preview_data
        })
        
    except Exception as e:
        return jsonify({'error': f'分析文件失败: {str(e)}'}), 500

@app.route('/get_available_models', methods=['GET'])
@login_required
def get_available_models():
    """获取可用模型列表"""
    # 使用model_factory获取所有可用模型
    models = model_factory.get_available_models()
    
    # 检查Google API密钥
    google_key = GOOGLE_API_KEY or request.headers.get('X-Google-API-Key')
    
    return jsonify({
        'models': models,
        'gemini_available': bool(google_key)
    })

@app.route('/start_evaluation', methods=['POST'])
@login_required
def start_evaluation():
    """开始评测"""
    data = request.get_json()
    filename = data.get('filename')
    selected_models = data.get('selected_models', [])
    force_mode = data.get('force_mode')  # 'auto', 'subjective', 'objective'
    custom_name = data.get('custom_name', '').strip()  # 自定义结果名称
    save_to_history = data.get('save_to_history', True)  # 是否保存到历史记录
    
    if not filename:
        return jsonify({'error': '缺少文件名'}), 400
    
    if not selected_models:
        return jsonify({'error': '请至少选择一个模型'}), 400
    
    if not GOOGLE_API_KEY:
        return jsonify({'error': '请配置GOOGLE_API_KEY环境变量'}), 400
    
    # 检查选中的模型是否可用
    is_valid, error_msg = model_factory.validate_models(selected_models)
    if not is_valid:
        return jsonify({'error': error_msg}), 400
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        return jsonify({'error': '文件不存在'}), 400
    
    try:
        # 读取文件
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath, encoding='utf-8-sig')
        else:
            df = pd.read_excel(filepath, engine='openpyxl')
        
        # 确定评测模式
        if force_mode == 'auto':
            mode = detect_evaluation_mode(df)
        else:
            mode = force_mode
        
        # 验证模式和数据的匹配
        if mode == 'objective' and 'answer' not in df.columns:
            return jsonify({'error': '客观题评测模式需要文件包含"answer"列'}), 400
        
        # 如果没有type列，添加默认值
        if 'type' not in df.columns:
            df['type'] = '未分类'
        
        data_list = df.to_dict('records')
        queries = [str(row['query']) for row in data_list]
        
        task_id = str(uuid.uuid4())
        task_status[task_id] = TaskStatus(task_id)
        task_status[task_id].evaluation_mode = mode
        task_status[task_id].selected_models = selected_models
        task_status[task_id].start_time = datetime.now()
        task_status[task_id].question_count = len(data_list)
        
        # 同时保存到数据库
        task_name = f"{os.path.basename(filename)}_{mode}评测"
        current_user_id = session.get('user_id', 'anonymous')
        db.create_running_task(
            task_id=task_id,
            task_name=task_name,
            dataset_file=filepath,
            dataset_filename=filename,
            evaluation_mode=mode,
            selected_models=selected_models,
            total=len(data_list),
            created_by=current_user_id
        )
        
        # 在主线程中获取所有需要的数据
        headers_dict = dict(request.headers)
        google_api_key = GOOGLE_API_KEY or request.headers.get('X-Google-API-Key')
        data_list = df.to_dict('records')
        queries = [str(row.get("query", "")) for row in data_list]
        
        def task(user_id, task_custom_name, task_save_to_history):
            try:
                # 第一步：获取模型答案
                model_results = run_async_task(get_multiple_model_answers, queries, selected_models, task_id, headers_dict)
                
                # 第二步：评测
                output_file = run_async_task(evaluate_models, data_list, mode, model_results, task_id, google_api_key, filename)
                
                task_status[task_id].status = "完成"
                task_status[task_id].result_file = os.path.basename(output_file)
                task_status[task_id].current_step = f"评测完成，结果已保存到 {os.path.basename(output_file)}"
                task_status[task_id].end_time = datetime.now()
                
                # 同时更新数据库
                db.update_task_status(task_id, "completed", result_file=output_file)
                
                # 保存到历史记录
                if task_save_to_history:
                    try:
                        evaluation_data = {
                            'dataset_file': filename,
                            'models': selected_models,
                            'evaluation_mode': mode,
                            'start_time': task_status[task_id].start_time.isoformat(),
                            'end_time': task_status[task_id].end_time.isoformat() if task_status[task_id].end_time else None,
                            'question_count': len(data_list),
                            'custom_name': task_custom_name,  # 传递自定义名称
                            'created_by': user_id  # 使用传递的用户ID
                        }
                        history_manager.save_evaluation_result(evaluation_data, output_file)
                    except Exception as e:
                        print(f"保存历史记录失败: {e}")
                
            except Exception as e:
                task_status[task_id].status = "失败"
                task_status[task_id].error_message = str(e)
                print(f"评测任务失败: {e}")  # 添加日志
                
                # 同时更新数据库
                db.update_task_status(task_id, "failed", error_message=str(e))
        
        # 在后台运行任务
        thread = threading.Thread(target=task, args=(current_user_id, custom_name, save_to_history))
        thread.start()
        
        return jsonify({'success': True, 'task_id': task_id})
        
    except Exception as e:
        return jsonify({'error': f'处理错误: {str(e)}'}), 400

@app.route('/task_status/<task_id>')
@login_required
def get_task_status(task_id):
    """获取任务状态"""
    # 先检查内存中是否有此任务
    if task_id in task_status:
        task = task_status[task_id]
        elapsed_time = (datetime.now() - task.start_time).total_seconds() if hasattr(task, 'start_time') and task.start_time else 0
        
        return jsonify({
            'status': task.status,
            'progress': task.progress,
            'total': task.total,
            'current_step': task.current_step,
            'result_file': os.path.basename(task.result_file) if task.result_file else "",
            'error_message': task.error_message,
            'evaluation_mode': task.evaluation_mode,
            'selected_models': task.selected_models,
            'elapsed_time': f"{elapsed_time:.1f}秒"
        })
    
    # 如果内存中没有，尝试从数据库获取
    try:
        current_user_id = session.get('user_id', 'anonymous')
        db_task = db.get_running_task(task_id)
        
        if not db_task:
            return jsonify({'error': '任务不存在'}), 404
            
        if db_task['created_by'] != current_user_id:
            return jsonify({'error': '无权限访问此任务'}), 403
        
        # 任务已完成或失败，返回最终状态
        if db_task['status'] in ['completed', 'failed']:
            return jsonify({
                'status': '完成' if db_task['status'] == 'completed' else '失败',
                'progress': db_task.get('total', 0),
                'total': db_task.get('total', 0),
                'current_step': db_task.get('current_step', ''),
                'result_file': os.path.basename(db_task.get('result_file', '')) if db_task.get('result_file') else "",
                'error_message': db_task.get('error_message', ''),
                'evaluation_mode': db_task.get('evaluation_mode', ''),
                'selected_models': db_task.get('selected_models', []),
                'elapsed_time': "已完成"
            })
        else:
            # 任务还在运行但内存中没有（可能是服务器重启了）
            return jsonify({'error': '任务状态丢失，请重新连接任务'}), 404
            
    except Exception as e:
        print(f"❌ 获取任务状态失败: {e}")
        return jsonify({'error': '获取任务状态失败'}), 500

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    """下载结果文件"""
    filepath = os.path.join(app.config['RESULTS_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        return jsonify({'error': '文件不存在'}), 404

@app.route('/api/history/download/<result_id>')
@login_required
def download_history_result(result_id):
    """通过result_id下载历史记录结果文件（含权限检查）"""
    try:
        current_user = db.get_user_by_id(session['user_id'])
        is_admin = current_user and current_user['role'] == 'admin'
        
        # 获取数据库中的结果信息
        if db:
            result = db.get_result_by_id(result_id)
            if result and result.get('result_file'):
                # 权限检查：普通用户只能下载自己的结果
                if not is_admin and result.get('created_by') != session['user_id']:
                    return jsonify({'error': '没有权限访问此结果'}), 403
                
                result_file = result['result_file']
                
                # 检查文件是否存在
                if os.path.exists(result_file):
                    return send_file(result_file, as_attachment=True)
                else:
                    # 如果绝对路径不存在，尝试在results文件夹中查找
                    filename = os.path.basename(result_file)
                    filepath = os.path.join(app.config['RESULTS_FOLDER'], filename)
                    if os.path.exists(filepath):
                        return send_file(filepath, as_attachment=True)
                    
                    return jsonify({'error': '结果文件不存在'}), 404
            else:
                return jsonify({'error': '找不到该评测记录'}), 404
        else:
            return jsonify({'error': '数据库连接失败'}), 500
            
    except Exception as e:
        print(f"下载历史记录失败: {str(e)}")
        return jsonify({'error': f'下载失败: {str(e)}'}), 500

@app.route('/view_results/<filename>')
@login_required
def view_results(filename):
    """查看评测结果"""
    filepath = os.path.join(app.config['RESULTS_FOLDER'], filename)
    if not os.path.exists(filepath):
        return jsonify({'error': '文件不存在'}), 404
    
    try:
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        # 获取高级分析结果
        advanced_stats = None
        print(f"🔍 [view_results] 正在为文件 {filename} 生成统计分析...")
        print(f"📊 [view_results] Analytics 模块状态: {'可用' if analytics else '不可用'}")
        
        if analytics:
            try:
                # 优先从数据库获取持久化的时间数据
                evaluation_data = None
                result_id = db.get_result_id_by_filename(filename)
                if result_id:
                    result_detail = db.get_result_by_id(result_id)
                    if result_detail and result_detail.get('metadata'):
                        try:
                            metadata = json.loads(result_detail['metadata'])
                            if metadata.get('start_time') and metadata.get('end_time'):
                                evaluation_data = {
                                    'start_time': metadata['start_time'],
                                    'end_time': metadata['end_time'],
                                    'question_count': metadata.get('question_count', len(df)),
                                    'from_database': True
                                }
                                print(f"✅ [view_results] 从数据库获取到持久化时间数据")
                        except Exception as e:
                            print(f"⚠️ [view_results] 解析数据库元数据失败: {e}")
                
                # 如果没有数据库数据，尝试从task_status获取时间数据
                if not evaluation_data:
                    for task_id, task in task_status.items():
                        if (hasattr(task, 'result_file') and 
                            task.result_file == filename and
                            hasattr(task, 'start_time') and hasattr(task, 'end_time')):
                            evaluation_data = {
                                'start_time': task.start_time.isoformat() if task.start_time else None,
                                'end_time': task.end_time.isoformat() if task.end_time else None,
                                'question_count': len(df),
                                'from_task_status': True
                            }
                            print(f"✅ [view_results] 从任务状态获取到时间数据")
                            break
                
                # 如果还是没有找到时间数据，使用文件的创建和修改时间作为估算
                if not evaluation_data or not evaluation_data.get('start_time') or not evaluation_data.get('end_time'):
                    try:
                        file_stat = os.stat(filepath)
                        # 估算：假设每题需要30秒处理时间
                        estimated_duration = len(df) * 30
                        file_mtime = datetime.fromtimestamp(file_stat.st_mtime)
                        estimated_start = file_mtime - timedelta(seconds=estimated_duration)
                        
                        evaluation_data = {
                            'start_time': estimated_start.isoformat(),
                            'end_time': file_mtime.isoformat(), 
                            'question_count': len(df),
                            'is_estimated': True
                        }
                        print(f"⏰ [view_results] 使用估算时间数据")
                    except Exception as e:
                        print(f"⚠️ [view_results] 获取文件时间失败: {e}")
                        evaluation_data = {'question_count': len(df)}
                
                print(f"🔄 [view_results] 开始分析评测结果...")
                analysis_result = analytics.analyze_evaluation_results(
                    result_file=filepath,
                    evaluation_data=evaluation_data
                )
                
                if analysis_result.get('success'):
                    advanced_stats = analysis_result['analysis']
                    print(f"✅ [view_results] 成功生成高级统计分析")
                else:
                    print(f"❌ [view_results] 分析失败: {analysis_result.get('error', '未知错误')}")
            
            except Exception as e:
                print(f"❌ [view_results] 分析过程出错: {e}")
                advanced_stats = None
        
        # 如果没有高级统计，也要确保有基础的统计数据用于前端显示
        if not advanced_stats:
            print(f"📝 [view_results] 生成基础统计数据作为后备方案")
            # 创建基础统计数据，确保前端能显示基本的图表
            try:
                # 简单的分数统计
                score_columns = [col for col in df.columns if '评分' in col or 'score' in col.lower()]
                if score_columns:
                    basic_stats = {
                        'basic_stats': {
                            'total_questions': len(df),
                            'response_rate': 100.0
                        },
                        'score_analysis': {
                            'model_performance': {},
                            'score_distribution': {}
                        },
                        'performance_metrics': {
                            'estimated_time_per_question': '30秒 (估算)',
                            'throughput': 120  # 每小时120题
                        }
                    }
                    
                    # 为每个模型计算基础统计
                    model_columns = [col for col in df.columns if col not in ['问题', '标准答案', '问题类型']]
                    for col in model_columns:
                        if '评分' in col:
                            model_name = col.replace('评分', '').strip()
                            scores = pd.to_numeric(df[col], errors='coerce').dropna()
                            if len(scores) > 0:
                                basic_stats['score_analysis']['model_performance'][model_name] = {
                                    'avg_score': float(scores.mean()),
                                    'total_score': float(scores.sum()),
                                    'question_count': len(scores)
                                }
                    
                    advanced_stats = basic_stats
                    print(f"✅ [view_results] 生成基础统计数据成功")
            except Exception as e:
                print(f"⚠️ [view_results] 生成基础统计数据失败: {e}")
        
        # 查找结果详情以支持分享功能
        result_detail = None
        try:
            result_id = db.get_result_id_by_filename(filename)
            if result_id:
                result_detail = db.get_result_by_id(result_id)
                print(f"✅ [view_results] 找到结果详情: {result_id}")
            else:
                print(f"⚠️ [view_results] 未找到文件 {filename} 对应的数据库记录")
        except Exception as e:
            print(f"⚠️ [view_results] 查找结果详情失败: {e}")
        
        current_user = db.get_user_by_id(session['user_id'])
        return render_template('results.html', 
                             filename=filename,
                             columns=df.columns.tolist(),
                             data=df.to_dict('records'),
                             advanced_stats=advanced_stats,
                             current_user=current_user,
                             result_detail=result_detail)
    except Exception as e:
        return jsonify({'error': f'读取结果文件错误: {str(e)}'}), 400


@app.route('/save_api_keys', methods=['POST'])
@login_required
def save_api_keys():
    """保存API密钥和Cookie到本地.env文件"""
    try:
        data = request.get_json()
        
        # 获取API密钥
        google_key = data.get('google_api_key', '').strip()
        hkgai_v1_key = data.get('hkgai_v1_key', '').strip()
        hkgai_v2_key = data.get('hkgai_v2_key', '').strip()
        
        # 获取Copilot Cookie
        copilot_cookie_prod = data.get('copilot_cookie_prod', '').strip()
        copilot_cookie_test = data.get('copilot_cookie_test', '').strip()
        copilot_cookie_net = data.get('copilot_cookie_net', '').strip()
        
        # 准备要保存的环境变量
        env_vars_to_save = {}
        
        # 添加API密钥
        if google_key:
            env_vars_to_save['GOOGLE_API_KEY'] = google_key
        if hkgai_v1_key:
            env_vars_to_save['ARK_API_KEY_HKGAI_V1'] = hkgai_v1_key
        if hkgai_v2_key:
            env_vars_to_save['ARK_API_KEY_HKGAI_V2'] = hkgai_v2_key
        
        # 添加Copilot Cookie
        if copilot_cookie_prod:
            env_vars_to_save['COPILOT_COOKIE_PROD'] = copilot_cookie_prod
        if copilot_cookie_test:
            env_vars_to_save['COPILOT_COOKIE_TEST'] = copilot_cookie_test
        if copilot_cookie_net:
            env_vars_to_save['COPILOT_COOKIE_NET'] = copilot_cookie_net
        
        if not env_vars_to_save:
            return jsonify({
                'success': False,
                'message': '没有提供任何API密钥或Cookie'
            })
        
        # 保存到.env文件
        success = env_manager.save_env_vars(env_vars_to_save)
        
        if success:
            # 统计保存的类型
            api_keys_count = sum(1 for key in env_vars_to_save.keys() if 'API_KEY' in key or 'GOOGLE_API_KEY' in key)
            cookies_count = sum(1 for key in env_vars_to_save.keys() if 'COOKIE' in key)
            
            message_parts = []
            if api_keys_count > 0:
                message_parts.append(f'{api_keys_count}个API密钥')
            if cookies_count > 0:
                message_parts.append(f'{cookies_count}个Cookie')
            
            message = f'已成功保存{" 和 ".join(message_parts)}到本地文件'
            
            return jsonify({
                'success': True,
                'message': message,
                'saved_keys': list(env_vars_to_save.keys())
            })
        else:
            return jsonify({
                'success': False,
                'message': '保存配置失败，请检查文件权限'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'保存API密钥时发生错误: {str(e)}'
        })


@app.route('/get_env_status', methods=['GET'])
@login_required
def get_env_status():
    """获取.env文件状态信息"""
    try:
        env_path = env_manager.get_env_file_path()
        env_exists = env_manager.env_file_exists()
        
        saved_keys = []
        saved_cookies = []
        
        if env_exists:
            env_vars = env_manager.load_env()
            
            # 检查API密钥
            api_keys = ['GOOGLE_API_KEY', 'ARK_API_KEY_HKGAI_V1', 'ARK_API_KEY_HKGAI_V2']
            saved_keys = [key for key in api_keys if key in env_vars and env_vars[key]]
            
            # 检查Copilot Cookie
            copilot_cookies = ['COPILOT_COOKIE_PROD', 'COPILOT_COOKIE_TEST', 'COPILOT_COOKIE_NET']
            saved_cookies = [key for key in copilot_cookies if key in env_vars and env_vars[key]]
        
        return jsonify({
            'env_file_path': env_path,
            'env_file_exists': env_exists,
            'saved_keys': saved_keys,
            'saved_cookies': saved_cookies,
            'total_saved': len(saved_keys) + len(saved_cookies)
        })
        
    except Exception as e:
        return jsonify({
            'error': f'获取环境状态失败: {str(e)}'
        })


# ===== 历史管理相关路由 =====

@app.route('/history')
@login_required
def history_page():
    """历史管理页面"""
    if not history_manager:
        return "历史管理功能未启用", 503
    current_user = db.get_user_by_id(session['user_id'])
    return render_template('history.html', current_user=current_user)

@app.route('/api/history/statistics')
@login_required
def get_history_statistics():
    """获取历史统计信息"""
    if not history_manager:
        return jsonify({'error': '历史管理功能未启用'}), 503
    try:
        stats = history_manager.get_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history/list')
@login_required
def get_history_list():
    """获取历史记录列表（按用户权限过滤）"""
    if not history_manager:
        return jsonify({'success': False, 'error': '历史管理功能未启用'}), 503
    try:
        current_user = db.get_user_by_id(session['user_id'])
        is_admin = current_user and current_user['role'] == 'admin'
        
        # 获取查询参数
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        search = request.args.get('search', '')
        mode = request.args.get('mode', '')
        tags = request.args.get('tags', '')
        selected_user = request.args.get('user_id') if is_admin else None
        
        # 解析标签
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()] if tags else None
        
        # 计算偏移量
        offset = (page - 1) * limit
        
        # 确定用户过滤参数
        if is_admin:
            if selected_user:
                # 管理员查看指定用户的记录
                created_by = selected_user
                include_all_users = False
            else:
                # 管理员查看所有用户的记录
                created_by = None
                include_all_users = True
        else:
            # 普通用户只能看自己的记录
            created_by = session['user_id']
            include_all_users = False
        
        # 获取历史记录
        history = history_manager.get_history_list(
            tags=tag_list,
            limit=limit,
            offset=offset,
            created_by=created_by,
            include_all_users=include_all_users
        )
        
        # 简单的搜索过滤（在返回的结果中过滤）
        if search and history['success']:
            filtered_results = []
            search_lower = search.lower()
            for result in history['results']:
                if (search_lower in result['name'].lower() or 
                    any(search_lower in model.lower() for model in result['models'])):
                    filtered_results.append(result)
            history['results'] = filtered_results
        
        # 模式过滤
        if mode and history['success']:
            history['results'] = [r for r in history['results'] if r['evaluation_mode'] == mode]
        
        # 为管理员添加额外信息
        if is_admin and history.get('success'):
            users_list = db.list_users()
            history['users'] = users_list
            history['is_admin'] = True
            history['selected_user'] = selected_user
        else:
            history['is_admin'] = False
        
        return jsonify(history)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/history/detail/<result_id>')
@login_required
def get_history_detail(result_id):
    """获取历史记录详情"""
    if not history_manager:
        return jsonify({'success': False, 'error': '历史管理功能未启用'}), 503
    try:
        detail = history_manager.get_result_detail(result_id)
        return jsonify(detail)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/history/tags')
@login_required
def get_available_tags():
    """获取可用标签列表"""
    if not history_manager:
        return jsonify([]), 503
    try:
        tags = history_manager.get_available_tags()
        return jsonify(tags)
    except Exception as e:
        return jsonify([]), 500

# ===== 标注系统相关路由 =====

@app.route('/annotate/<result_id>')
@login_required
def annotate_page(result_id):
    """标注页面"""
    if not annotation_system:
        return "标注功能未启用", 503
    current_user = db.get_user_by_id(session['user_id'])
    return render_template('annotate.html', result_id=result_id, current_user=current_user)

@app.route('/api/annotation/data/<result_id>')
@login_required
def get_annotation_data(result_id):
    """获取标注数据"""
    if not annotation_system:
        return jsonify({'success': False, 'error': '标注功能未启用'}), 503
    try:
        data = annotation_system.get_annotation_data(result_id)
        return jsonify(data)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/annotation/save', methods=['POST'])
@login_required
def save_annotation():
    """保存标注"""
    if not annotation_system:
        return jsonify({'success': False, 'error': '标注功能未启用'}), 503
    try:
        data = request.get_json()
        result = annotation_system.save_annotation(
            result_id=data['result_id'],
            question_index=data['question_index'],
            model_name=data['model_name'],
            annotation_data=data['annotation_data'],
            annotator=data.get('annotator', 'default')
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/annotation/progress/<result_id>')
@login_required
def get_annotation_progress(result_id):
    """获取标注进度"""
    if not annotation_system:
        return jsonify({'success': False, 'error': '标注功能未启用'}), 503
    try:
        progress = annotation_system.get_annotation_progress(result_id)
        return jsonify(progress)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/annotation/statistics/<result_id>')
@login_required
def get_annotation_statistics(result_id):
    """获取标注统计"""
    if not annotation_system:
        return jsonify({'success': False, 'error': '标注功能未启用'}), 503
    try:
        stats = annotation_system.get_annotation_statistics(result_id)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/view_history/<result_id>')
@login_required
def view_history(result_id):
    """查看历史评测结果详情（含权限检查）"""
    try:
        current_user = db.get_user_by_id(session['user_id'])
        is_admin = current_user and current_user['role'] == 'admin'
        
        # 获取历史记录详情
        result_detail = history_manager.get_result_detail(result_id)
        if not result_detail:
            return jsonify({'error': '结果不存在'}), 404
        
        # 权限检查：普通用户只能查看自己的结果
        result = result_detail.get('result', {})
        if not is_admin and result.get('created_by') != session['user_id']:
            return jsonify({'error': '没有权限访问此结果'}), 403
        result_file = result.get('result_file')
        
        if not result_file:
            return jsonify({'error': '结果文件路径为空'}), 404
            
        # 简单直接的路径处理
        if os.path.exists(result_file):
            filepath = result_file
        else:
            return jsonify({
                'error': '结果文件不存在',
                'result_file': result_file,
                'working_dir': os.getcwd(),
                'file_exists_check': os.path.exists(result_file)
            }), 404
            
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        # 获取高级分析结果
        task_data = result_detail.get('result', {})
        evaluation_data = {
            'start_time': task_data.get('start_time'),
            'end_time': task_data.get('end_time'),
            'question_count': len(df)
        }
        
        # 如果没有时间数据，使用文件的创建和修改时间作为估算
        if not evaluation_data.get('start_time') or not evaluation_data.get('end_time'):
            try:
                file_stat = os.stat(filepath)
                # 估算：假设每题需要30秒处理时间
                estimated_duration = len(df) * 30
                file_mtime = datetime.fromtimestamp(file_stat.st_mtime)
                estimated_start = file_mtime - timedelta(seconds=estimated_duration)
                
                evaluation_data.update({
                    'start_time': estimated_start.isoformat(),
                    'end_time': file_mtime.isoformat(),
                    'is_estimated': True
                })
            except Exception as e:
                pass  # 静默处理文件时间获取错误
        
        analysis_result = analytics.analyze_evaluation_results(
            result_file=filepath,
            evaluation_data=evaluation_data
        )
        
        advanced_stats = None
        if analysis_result.get('success'):
            advanced_stats = analysis_result['analysis']
        
        current_user = db.get_user_by_id(session['user_id'])
        return render_template('results.html', 
                             filename=result_file,
                             columns=df.columns.tolist(),
                             data=df.to_dict('records'),
                             result_detail=result_detail,
                             advanced_stats=advanced_stats,
                             current_user=current_user)
    except Exception as e:
        return jsonify({'error': f'处理异常: {str(e)}'}), 500

@app.route('/api/history/rename/<result_id>', methods=['PUT'])
@login_required
def rename_history_result(result_id):
    """重命名历史评测结果"""
    try:
        data = request.get_json()
        new_name = data.get('new_name', '').strip()
        
        if not new_name:
            return jsonify({'success': False, 'error': '名称不能为空'}), 400
            
        if len(new_name) > 100:
            return jsonify({'success': False, 'error': '名称长度不能超过100个字符'}), 400
        
        success = history_manager.rename_result(result_id, new_name)
        if success:
            return jsonify({'success': True, 'message': '重命名成功'})
        else:
            return jsonify({'success': False, 'error': '重命名失败'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/history/delete/<result_id>', methods=['DELETE'])
@login_required
def delete_history_result(result_id):
    """删除历史评测结果和对应的CSV文件"""
    try:
        result = history_manager.delete_result(result_id)
        if result.get('success'):
            return jsonify({
                'success': True, 
                'message': result.get('message', '删除成功'),
                'deleted_files': result.get('deleted_files', [])
            })
        else:
            return jsonify({'success': False, 'error': result.get('error', '删除失败')}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/debug_score_update', methods=['POST'])
@login_required
def debug_score_update():
    """调试评分更新功能 - 返回详细的文件和数据库状态"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        
        print(f"\n🔍 [调试] 开始调试文件: {filename}")
        
        # 检查文件状态
        filepath = os.path.join(app.config['RESULTS_FOLDER'], filename)
        file_exists = os.path.exists(filepath)
        
        debug_info = {
            'filename': filename,
            'filepath': filepath,
            'file_exists': file_exists,
            'results_folder': app.config['RESULTS_FOLDER']
        }
        
        if file_exists:
            # 读取文件信息
            df = pd.read_csv(filepath, encoding='utf-8-sig')
            debug_info.update({
                'file_rows': len(df),
                'file_columns': list(df.columns),
                'score_columns': [col for col in df.columns if '评分' in col],
                'reason_columns': [col for col in df.columns if '理由' in col]
            })
        
        # 检查数据库状态
        if db:
            result_id = db.get_result_id_by_filename(filename)
            debug_info.update({
                'database_connected': True,
                'database_result_id': result_id
            })
        else:
            debug_info.update({
                'database_connected': False,
                'database_result_id': None
            })
        
        print(f"🔍 [调试] 调试信息: {debug_info}")
        
        return jsonify({
            'success': True,
            'debug_info': debug_info
        })
        
    except Exception as e:
        print(f"❌ [调试] 调试失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update_score', methods=['POST'])
@login_required
def update_score():
    """修改评分"""
    try:
        # 权限检查：只有admin和reviewer可以修改评分
        current_user = db.get_user_by_id(session['user_id'])
        if not current_user or current_user['role'] not in ['admin', 'reviewer']:
            return jsonify({'success': False, 'error': '您没有权限修改评分'}), 403
        data = request.get_json()
        filename = data.get('filename')
        row_index = data.get('row_index')
        score_column = data.get('score_column')
        new_score = data.get('new_score')
        reason = data.get('reason')
        model_name = data.get('model_name')
        
        # 验证参数
        if not filename or row_index is None or not score_column or new_score is None:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        # 验证评分必须为数字（不限制范围，完全由用户提示词决定）
        if not isinstance(new_score, (int, float)):
            return jsonify({'success': False, 'error': '评分必须为数字'}), 400
        
        # 计算理由列名（确保在所有执行路径中都定义）
        reason_column = score_column.replace('评分', '理由')
        
        # 首先尝试更新数据库
        print(f"🔍 [数据库] 开始查找文件 {filename} 对应的数据库记录...")
        result_id = None
        if db:
            try:
                # 根据文件名查找result_id（传递原始文件名，函数内部会处理路径前缀）
                result_id = db.get_result_id_by_filename(filename)
                print(f"🔍 [数据库] 查找结果: result_id = {result_id}")
                
                if result_id:
                    # 根据评分列确定评分类型
                    if '评分' in score_column:
                        score_type = 'correctness'  # 默认为正确性评分，可以根据具体列名细化
                        if '相关' in score_column:
                            score_type = 'relevance'
                        elif '安全' in score_column:
                            score_type = 'safety'
                        elif '创意' in score_column or '创造' in score_column:
                            score_type = 'creativity'
                    
                    print(f"📝 [数据库] 准备更新: result_id={result_id}, 行={row_index}, 模型={model_name}, 类型={score_type}, 评分={new_score}")
                    
                    # 更新数据库中的评分
                    success = db.update_annotation_score(
                        result_id=result_id,
                        question_index=row_index,
                        model_name=model_name,
                        score_type=score_type,
                        new_score=new_score,
                        reason=reason,
                        annotator='manual_edit'
                    )
                    
                    if success:
                        print(f"✅ 数据库评分已更新: {filename} 第{row_index+1}行 {model_name} -> {new_score}分")
                    else:
                        print(f"⚠️ 数据库更新失败，继续更新CSV文件")
                else:
                    print(f"⚠️ 数据库中未找到文件 {filename} 的记录，跳过数据库更新")
            except Exception as e:
                print(f"⚠️ 数据库更新异常: {e}")
                import traceback
                traceback.print_exc()
        
        # 同时更新CSV文件以保持兼容性
        # 处理文件名，去除可能的路径前缀
        clean_filename = filename
        if filename.startswith('results_history/'):
            clean_filename = filename.replace('results_history/', '', 1)
            print(f"📁 [文件名处理] 检测到history路径前缀，清理后: {clean_filename}")
        elif filename.startswith('results/'):
            clean_filename = filename.replace('results/', '', 1)
            print(f"📁 [文件名处理] 检测到results路径前缀，清理后: {clean_filename}")
        
        # 首先尝试原始路径（适用于传入完整路径的情况）
        if filename.startswith('results_history/'):
            filepath = filename  # 直接使用原始路径
            print(f"📁 [CSV文件] 使用完整路径: {filepath}")
        else:
            filepath = os.path.join(app.config['RESULTS_FOLDER'], clean_filename)
            print(f"📁 [CSV文件] 目标文件路径: {filepath}")
        
        print(f"📁 [CSV文件] 文件是否存在: {os.path.exists(filepath)}")
        
        # 如果文件不存在，尝试在其他位置查找
        if not os.path.exists(filepath):
            print(f"🔍 [文件查找] 在主路径未找到文件，开始在其他位置搜索...")
            found_filepath = None
            
            # 在results_history目录中查找
            history_path = os.path.join(os.path.dirname(app.config['RESULTS_FOLDER']), 'results_history')
            if os.path.exists(history_path):
                history_filepath = os.path.join(history_path, clean_filename)
                if os.path.exists(history_filepath):
                    found_filepath = history_filepath
                    print(f"✅ [文件查找] 在results_history中找到文件: {found_filepath}")
            
            # 在results目录中查找（如果原来用的是history路径）
            if not found_filepath:
                results_filepath = os.path.join(app.config['RESULTS_FOLDER'], clean_filename)
                if os.path.exists(results_filepath):
                    found_filepath = results_filepath
                    print(f"✅ [文件查找] 在results中找到文件: {found_filepath}")
            
            # 如果找到文件，使用该路径
            if found_filepath:
                filepath = found_filepath
        
        if os.path.exists(filepath):
            print(f"📖 [CSV文件] 开始读取文件...")
            # 读取CSV文件
            df = pd.read_csv(filepath, encoding='utf-8-sig')
            print(f"📊 [CSV文件] 文件行数: {len(df)}, 列数: {len(df.columns)}")
            print(f"📊 [CSV文件] 列名: {list(df.columns)}")
            
            # 验证行索引
            if row_index < 0 or row_index >= len(df):
                print(f"❌ [CSV文件] 行索引 {row_index} 超出范围 [0, {len(df)-1}]")
                return jsonify({'success': False, 'error': '行索引超出范围'}), 400
            
            # 验证列名
            if score_column not in df.columns:
                print(f"❌ [CSV文件] 评分列 '{score_column}' 不存在")
                print(f"📊 [CSV文件] 可用的列: {list(df.columns)}")
                return jsonify({'success': False, 'error': f'列 {score_column} 不存在'}), 400
            
            print(f"📝 [CSV文件] 准备更新第 {row_index} 行的 '{score_column}' 列")
            print(f"📝 [CSV文件] 原值: {df.loc[row_index, score_column]} -> 新值: {new_score}")
            
            # 更新评分
            df.loc[row_index, score_column] = new_score
            
            # 如果有理由列，也更新理由
            if reason_column in df.columns and reason:
                print(f"📝 [CSV文件] 更新理由列 '{reason_column}'")
                print(f"📝 [CSV文件] 原理由: {str(df.loc[row_index, reason_column])[:50]}...")
                print(f"📝 [CSV文件] 新理由: {reason[:50]}...")
                df.loc[row_index, reason_column] = reason
            elif reason:
                print(f"⚠️ [CSV文件] 理由列 '{reason_column}' 不存在，跳过理由更新")
            else:
                print(f"ℹ️ [CSV文件] 没有提供理由，跳过理由更新")
            
            # 保存文件前先备份
            backup_path = filepath + '.backup'
            print(f"💾 [备份] 准备备份原文件...")
            if os.path.exists(filepath):
                import shutil
                shutil.copy2(filepath, backup_path)
                print(f"✅ [备份] 已创建文件备份: {backup_path}")
            
            # 保存文件
            print(f"💾 [保存] 开始保存CSV文件到: {filepath}")
            try:
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
                print(f"✅ [保存] CSV文件保存完成")
            except Exception as save_error:
                print(f"❌ [保存] CSV文件保存失败: {save_error}")
                return jsonify({'success': False, 'error': f'文件保存失败: {str(save_error)}'}), 500
            
            # 验证保存是否成功
            print(f"🔍 [验证] 开始验证文件保存结果...")
            if os.path.exists(filepath):
                try:
                    # 重新读取文件验证更新
                    verify_df = pd.read_csv(filepath, encoding='utf-8-sig')
                    print(f"🔍 [验证] 重新读取文件成功，行数: {len(verify_df)}")
                    
                    if row_index < len(verify_df):
                        saved_score = verify_df.loc[row_index, score_column]
                        saved_reason = verify_df.loc[row_index, reason_column] if reason_column in verify_df.columns else None
                        
                        print(f"🔍 [验证] 文件中第{row_index}行的数据:")
                        print(f"   评分列 '{score_column}': {saved_score} (期望: {new_score})")
                        if reason_column in verify_df.columns:
                            print(f"   理由列 '{reason_column}': {str(saved_reason)[:100]}...")
                        
                        score_match = str(saved_score) == str(new_score)
                        reason_match = (not reason) or (saved_reason and str(saved_reason) == str(reason))
                        
                        if score_match:
                            print(f"✅ [验证] 评分保存成功: {saved_score}")
                        else:
                            print(f"❌ [验证] 评分保存失败: 期望 {new_score}, 实际 {saved_score}")
                            
                        if reason and reason_column in verify_df.columns:
                            if reason_match:
                                print(f"✅ [验证] 理由保存成功")
                            else:
                                print(f"❌ [验证] 理由保存失败")
                                print(f"   期望: {reason}")
                                print(f"   实际: {saved_reason}")
                        
                        if not (score_match and reason_match):
                            print(f"⚠️ [验证] 数据保存验证失败，但继续返回成功状态")
                            
                    else:
                        print(f"❌ [验证] 行索引 {row_index} 超出验证文件范围 [0, {len(verify_df)-1}]")
                        
                except Exception as verify_error:
                    print(f"❌ [验证] 文件验证失败: {verify_error}")
            else:
                print(f"❌ [验证] 文件保存失败，文件不存在: {filepath}")
        else:
            # 如果CSV文件不存在但数据库操作成功，仍然返回成功
            if db and result_id:
                print(f"⚠️ CSV文件未找到: {filename}")
                print(f"📋 在以下位置搜索过文件:")
                print(f"   - {os.path.join(app.config['RESULTS_FOLDER'], filename)}")
                history_path = os.path.join(os.path.dirname(app.config['RESULTS_FOLDER']), 'results_history')
                print(f"   - {os.path.join(history_path, filename)}")
                print(f"✅ 数据库更新成功，但CSV文件同步失败")
            else:
                return jsonify({'success': False, 'error': '文件不存在且数据库中无记录'}), 404
        
        print(f"🎉 [完成] 评分更新操作完成，准备返回结果")
        
        # 准备返回信息
        csv_updated = os.path.exists(filepath)
        database_updated = result_id is not None
        
        # 构建消息
        if csv_updated and database_updated:
            message = f'{model_name} 的评分已更新为 {new_score} 分'
        elif database_updated and not csv_updated:
            message = f'{model_name} 的评分已更新为 {new_score} 分 (仅数据库，CSV文件未找到)'
        else:
            message = f'评分更新失败'
        
        return jsonify({
            'success': True,
            'message': message,
            'updated_score': new_score,
            'updated_reason': reason,
            'score_column': score_column,
            'reason_column': reason_column,
            'row_index': row_index,  # 这是CSV文件中的实际行索引（从0开始）
            'debug_info': {
                'filename': filename,
                'target_filepath': os.path.join(app.config['RESULTS_FOLDER'], filename),
                'actual_filepath': filepath,
                'file_exists': csv_updated,
                'database_result_id': result_id,
                'model_name': model_name,
                'csv_updated': csv_updated,
                'database_updated': database_updated,
                'file_location': 'results_history' if 'results_history' in filepath else 'results' if csv_updated else 'not_found'
            }
        })
        
    except Exception as e:
        print(f"❌ 更新评分失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 提供更详细的错误信息用于调试
        error_details = {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'filename': data.get('filename', 'unknown'),
            'row_index': data.get('row_index', 'unknown'),
            'score_column': data.get('score_column', 'unknown'),
            'model_name': data.get('model_name', 'unknown')
        }
        
        print(f"🔍 [错误详情] {error_details}")
        
        return jsonify({
            'success': False, 
            'error': f'更新失败: {str(e)}',
            'debug_info': error_details
        }), 500

@app.route('/api/generate_report/<path:filename>')
@app.route('/api/generate_report/<path:filename>/<format_type>')
@login_required
def generate_complete_report(filename, format_type='excel'):
    """生成完整报告API - 支持Excel和CSV格式"""
    try:
        # 验证格式类型
        if format_type not in ['excel', 'csv']:
            format_type = 'excel'
        
        # 确定文件路径
        if filename.startswith('results_history/'):
            # 如果filename已经包含results_history路径，直接使用
            filepath = filename
        elif filename.startswith('evaluation_result_'):
            # 常规评测结果文件
            filepath = os.path.join(app.config['RESULTS_FOLDER'], filename)
        else:
            # 其他历史文件，放在results_history目录下
            filepath = os.path.join('results_history', filename)
        
        print(f"🔍 尝试访问文件: {filepath}")
        
        if not os.path.exists(filepath):
            print(f"❌ 文件不存在: {filepath}")
            # 如果文件不存在，尝试其他可能的路径
            alternative_paths = []
            
            # 如果原路径包含results_history，尝试去掉这部分
            if 'results_history/' in filename:
                base_filename = filename.replace('results_history/', '')
                alternative_paths.extend([
                    os.path.join('results_history', base_filename),
                    os.path.join(app.config['RESULTS_FOLDER'], base_filename),
                    base_filename
                ])
            
            # 尝试其他路径
            for alt_path in alternative_paths:
                if os.path.exists(alt_path):
                    filepath = alt_path
                    print(f"✅ 找到备用路径: {filepath}")
                    break
            else:
                return jsonify({'error': f'文件不存在: {filename}'}), 404
        
        # 读取评测数据
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        # 使用高级分析引擎生成报告
        from utils.advanced_analytics import AdvancedAnalytics
        analytics = AdvancedAnalytics()
        
        # 尝试获取evaluation_data
        evaluation_data = None
        
        # 从数据库获取评测数据
        if db:
            try:
                result_id = db.get_result_id_by_filename(filename)
                if result_id:
                    result_info = db.get_result_by_id(result_id)
                    if result_info:
                        evaluation_data = {
                            'start_time': result_info.get('created_at'),
                            'end_time': result_info.get('completed_at'),
                            'question_count': len(df),
                            'models': result_info.get('models', '[]'),
                            'evaluation_mode': result_info.get('evaluation_mode', 'unknown')
                        }
            except Exception as e:
                print(f"⚠️ 无法从数据库获取evaluation_data: {e}")
        
        # 如果数据库中没有找到，使用文件时间估算
        if not evaluation_data:
            try:
                import time
                file_stat = os.stat(filepath)
                file_creation_time = datetime.fromtimestamp(file_stat.st_ctime)
                file_modification_time = datetime.fromtimestamp(file_stat.st_mtime)
                
                # 估算每题30秒的处理时间
                estimated_duration = len(df) * 30  # 秒
                estimated_start_time = file_modification_time - timedelta(seconds=estimated_duration)
                
                evaluation_data = {
                    'start_time': estimated_start_time.isoformat(),
                    'end_time': file_modification_time.isoformat(),
                    'question_count': len(df),
                    'models': '[]',
                    'evaluation_mode': 'estimated',
                    'is_estimated': True
                }
            except Exception as e:
                pass  # 静默处理估算错误
                evaluation_data = {
                    'start_time': None,
                    'end_time': None,
                    'question_count': len(df),
                    'models': '[]',
                    'evaluation_mode': 'unknown'
                }
        
        # 生成统计分析
        analysis_response = analytics.analyze_evaluation_results(filepath, evaluation_data)
        
        # 处理分析结果
        if analysis_response.get('success'):
            analysis_result = analysis_response.get('analysis', {})
        else:
            print(f"⚠️ 分析失败: {analysis_response.get('error', '未知错误')}")
            # 使用基础分析作为备选
            analysis_result = {
                'basic_stats': {
                    'total_questions': len(df),
                    'total_models': len([col for col in df.columns if '评分' in col]),
                    'average_score': 0,
                    'evaluation_duration': '未知'
                },
                'quality_indicators': {},
                'model_performance': {},
                'time_analysis': {
                    'total_duration': '未知',
                    'average_per_question': '未知',
                    'efficiency_rating': '未评级',
                    'data_source': 'fallback'
                }
            }
        
        # 获取原文件名（不含扩展名和路径）
        base_filename = os.path.basename(filename)  # 只取文件名，不含路径
        base_name = os.path.splitext(base_filename)[0]
        
        # 创建临时文件
        import tempfile
        temp_dir = tempfile.gettempdir()
        
        if format_type == 'excel':
            # 生成Excel格式报告
            report_filename = f"{base_name}_完整报告.xlsx"
            temp_path = os.path.join(temp_dir, report_filename)
            
            # 创建Excel写入器
            with pd.ExcelWriter(temp_path, engine='openpyxl') as writer:
                # 工作表1: 原始数据
                df.to_excel(writer, sheet_name='原始数据', index=False)
                
                # 工作表2: 统计摘要
                summary_data = []
                basic_stats = analysis_result.get('basic_stats', {})
                time_analysis = analysis_result.get('time_analysis', {})
                
                summary_data.append(['报告信息', ''])
                summary_data.append(['文件名', filename])
                summary_data.append(['生成时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                summary_data.append(['', ''])
                
                summary_data.append(['基础统计', ''])
                summary_data.append(['总题目数', basic_stats.get('total_questions', 0)])
                summary_data.append(['参与模型数', basic_stats.get('total_models', 0)])
                summary_data.append(['平均评分', f"{basic_stats.get('average_score', 0):.2f}"])
                summary_data.append(['评测时长', basic_stats.get('evaluation_duration', '未知')])
                summary_data.append(['', ''])
                
                # 质量指标
                quality_indicators = analysis_result.get('quality_indicators', {})
                if quality_indicators:
                    summary_data.append(['质量指标', ''])
                    for key, value in quality_indicators.items():
                        if key == 'data_completeness':
                            summary_data.append(['数据完整性', f"{value:.1f}%"])
                        elif key == 'score_validity':
                            summary_data.append(['评分有效性', f"{value:.1f}%"])
                        elif key == 'consistency_score':
                            summary_data.append(['一致性评分', f"{value:.1f}%"])
                    summary_data.append(['', ''])
                
                # 时间效率指标
                if time_analysis:
                    summary_data.append(['时间效率指标', ''])
                    summary_data.append(['总评测时长', time_analysis.get('total_duration', '未知')])
                    summary_data.append(['平均每题时长', time_analysis.get('average_per_question', '未知')])
                    summary_data.append(['效率评级', time_analysis.get('efficiency_rating', '未评级')])
                    
                    data_source = time_analysis.get('data_source', 'unknown')
                    if data_source == 'estimated':
                        summary_data.append(['数据来源', '基于文件时间估算'])
                    elif data_source == 'actual':
                        summary_data.append(['数据来源', '实际记录时间'])
                    elif data_source == 'no_data':
                        summary_data.append(['数据来源', '无时间数据'])
                    else:
                        summary_data.append(['数据来源', '未知'])
                    
                    # 添加优化建议
                    suggestions = time_analysis.get('optimization_suggestions', [])
                    if suggestions:
                        summary_data.append(['', ''])
                        summary_data.append(['优化建议', ''])
                        for i, suggestion in enumerate(suggestions[:3], 1):  # 最多显示3条建议
                            summary_data.append([f'建议{i}', suggestion])
                
                summary_df = pd.DataFrame(summary_data, columns=['项目', '值'])
                summary_df.to_excel(writer, sheet_name='统计摘要', index=False)
                
                # 工作表3: 模型性能对比
                model_performance = analysis_result.get('model_performance', {})
                if model_performance:
                    performance_data = []
                    for i, (model, stats) in enumerate(model_performance.items(), 1):
                        performance_data.append([
                            i,  # 排名
                            model,  # 模型名
                            f"{stats.get('average_score', 0):.2f}",  # 平均分
                            stats.get('total_score', 0),  # 总分
                            stats.get('question_count', 0),  # 题目数
                            f"{stats.get('consistency_score', 0):.2f}" if stats.get('consistency_score') else 'N/A'  # 一致性
                        ])
                    
                    performance_df = pd.DataFrame(performance_data, 
                                                columns=['排名', '模型名称', '平均评分', '总分', '题目数', '一致性评分'])
                    performance_df.to_excel(writer, sheet_name='模型性能对比', index=False)
                
                # 工作表4: 分数分布统计
                score_columns = [col for col in df.columns if '评分' in col]
                if score_columns:
                    models = [col.replace('_评分', '') for col in score_columns]
                    distribution_data = []
                    
                    # 动态确定分数范围
                    all_scores = []
                    for col in score_columns:
                        scores = df[col].dropna()
                        all_scores.extend([s for s in scores if isinstance(s, (int, float)) and not pd.isna(s)])
                    
                    if all_scores:
                        min_score = int(min(all_scores))
                        max_score = int(max(all_scores))
                        # 确保范围合理
                        min_score = max(0, min_score)
                        max_score = min(10, max_score)
                    else:
                        min_score, max_score = 0, 5
                    
                    for score in range(min_score, max_score + 1):
                        row = [f"{score}分"]
                        for col in score_columns:
                            count = (df[col] == score).sum()
                            total = df[col].notna().sum()
                            percentage = (count / total * 100) if total > 0 else 0
                            row.append(f"{count} ({percentage:.1f}%)")
                        distribution_data.append(row)
                    
                    distribution_df = pd.DataFrame(distribution_data, 
                                                 columns=['分数'] + models)
                    distribution_df.to_excel(writer, sheet_name='分数分布统计', index=False)
            
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            
        else:  # CSV格式
            # 生成增强的CSV格式报告
            report_filename = f"{base_name}_完整报告.csv"
            temp_path = os.path.join(temp_dir, report_filename)
            
            # 创建增强的CSV报告
            enhanced_data = []
            
            # 添加报告头信息
            enhanced_data.append(['AI模型评测完整报告', '', '', ''])
            enhanced_data.append(['文件名', filename, '', ''])
            enhanced_data.append(['生成时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), '', ''])
            enhanced_data.append(['', '', '', ''])
            
            # 添加统计摘要
            basic_stats = analysis_result.get('basic_stats', {})
            enhanced_data.append(['基础统计信息', '', '', ''])
            enhanced_data.append(['总题目数', basic_stats.get('total_questions', 0), '', ''])
            enhanced_data.append(['参与模型数', basic_stats.get('total_models', 0), '', ''])
            enhanced_data.append(['平均评分', f"{basic_stats.get('average_score', 0):.2f}", '', ''])
            enhanced_data.append(['评测时长', basic_stats.get('evaluation_duration', '未知'), '', ''])
            enhanced_data.append(['', '', '', ''])
            
            # 添加时间效率指标
            time_analysis = analysis_result.get('time_analysis', {})
            if time_analysis:
                enhanced_data.append(['时间效率指标', '', '', ''])
                enhanced_data.append(['总评测时长', time_analysis.get('total_duration', '未知'), '', ''])
                enhanced_data.append(['平均每题时长', time_analysis.get('average_per_question', '未知'), '', ''])
                enhanced_data.append(['效率评级', time_analysis.get('efficiency_rating', '未评级'), '', ''])
                
                data_source = time_analysis.get('data_source', 'unknown')
                source_desc = {
                    'estimated': '基于文件时间估算',
                    'actual': '实际记录时间',
                    'no_data': '无时间数据',
                    'incomplete': '时间数据不完整',
                    'error': '时间数据解析错误',
                    'fallback': '备用数据源'
                }.get(data_source, '未知')
                enhanced_data.append(['数据来源', source_desc, '', ''])
                enhanced_data.append(['', '', '', ''])
            
            # 添加原始数据表头
            enhanced_data.append(['原始评测数据', '', '', ''])
            enhanced_data.append(df.columns.tolist())
            
            # 添加原始数据
            for _, row in df.iterrows():
                enhanced_data.append([str(row[col]) if pd.notna(row[col]) else '' for col in df.columns])
            
            # 写入CSV文件
            import csv
            with open(temp_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerows(enhanced_data)
            
            mimetype = 'text/csv; charset=utf-8'
        
        # 返回文件供下载
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=report_filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        print(f"❌ 生成报告失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'生成报告失败: {str(e)}'}), 500

@app.route('/api/export_filtered', methods=['POST'])
@login_required
def export_filtered_results():
    """导出筛选结果API"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        filtered_data = data.get('filtered_data', [])
        filters = data.get('filters', {})
        
        if not filename:
            return jsonify({'error': '缺少文件名参数'}), 400
        
        if not filtered_data:
            return jsonify({'error': '没有要导出的数据'}), 400
        
        # 创建DataFrame
        df = pd.DataFrame(filtered_data)
        
        # 获取原文件名（不含扩展名）
        base_name = os.path.splitext(filename)[0]
        
        # 生成筛选条件描述
        filter_desc = []
        if filters.get('search'):
            filter_desc.append(f"搜索_{filters['search']}")
        if filters.get('type'):
            filter_desc.append(f"类型_{filters['type']}")
        if filters.get('score_range'):
            filter_desc.append(f"分数_{filters['score_range']}")
        
        filter_suffix = "_".join(filter_desc) if filter_desc else "筛选结果"
        export_filename = f"{base_name}_{filter_suffix}.csv"
        
        # 创建临时文件
        import tempfile
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, export_filename)
        
        # 保存CSV文件
        df.to_csv(temp_path, index=False, encoding='utf-8-sig')
        
        # 返回文件供下载
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=export_filename,
            mimetype='text/csv; charset=utf-8'
        )
        
    except Exception as e:
        print(f"❌ 导出筛选结果失败: {str(e)}")
        return jsonify({'error': f'导出失败: {str(e)}'}), 500


# ===== 用户认证路由 =====

@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if request.method == 'GET':
        # 如果已经登录，重定向到首页
        if 'user_id' in session:
            return redirect(url_for('index'))
        return render_template('login.html')
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            username = data.get('username', '').strip()
            password = data.get('password', '')
            
            if not username or not password:
                return jsonify({
                    'success': False,
                    'message': '用户名和密码不能为空'
                }), 400
            
            # 验证用户
            user = db.verify_user(username, password)
            if user:
                # 设置session
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['display_name'] = user['display_name']
                session['role'] = user['role']
                
                return jsonify({
                    'success': True,
                    'message': '登录成功',
                    'user': {
                        'username': user['username'],
                        'display_name': user['display_name'],
                        'role': user['role']
                    },
                    'redirect': '/admin' if user['role'] == 'admin' else '/'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '用户名或密码错误'
                }), 401
                
        except Exception as e:
            print(f"❌ 登录错误: {e}")
            return jsonify({
                'success': False,
                'message': '登录过程中发生错误'
            }), 500


@app.route('/logout', methods=['POST'])
def logout():
    """用户退出登录"""
    session.clear()
    return jsonify({'success': True, 'message': '已退出登录', 'redirect': '/login'})


@app.route('/admin')
@admin_required
def admin():
    """管理员页面"""
    current_user = db.get_user_by_id(session['user_id'])
    return render_template('admin.html', current_user=current_user)

@app.route('/admin/configs')
@admin_required
def admin_configs_page():
    """系统配置管理页面"""
    current_user = db.get_user_by_id(session['user_id'])
    return render_template('admin_configs.html', current_user=current_user)

@app.route('/admin/scoring')
@admin_required
def admin_scoring_page():
    """评分标准管理页面"""
    current_user = db.get_user_by_id(session['user_id'])
    return render_template('admin_scoring.html', current_user=current_user)


@app.route('/admin/users', methods=['GET'])
@admin_required
def get_users():
    """获取用户列表"""
    try:
        users = db.list_users()
        return jsonify(users)
    except Exception as e:
        print(f"❌ 获取用户列表错误: {e}")
        return jsonify({'error': '获取用户列表失败'}), 500


@app.route('/admin/users', methods=['POST'])
@admin_required
def create_user():
    """创建新用户"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        display_name = data.get('displayName', '').strip()
        email = data.get('email', '').strip()
        role = data.get('role', 'annotator')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': '用户名和密码不能为空'
            }), 400
        
        if len(password) < 6:
            return jsonify({
                'success': False,
                'message': '密码长度不能少于6位'
            }), 400
        
        # 创建用户
        user_id = db.create_user(
            username=username,
            password=password,
            role=role,
            display_name=display_name or None,
            email=email or None,
            created_by=session['user_id']
        )
        
        return jsonify({
            'success': True,
            'message': '用户创建成功',
            'user_id': user_id
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        print(f"❌ 创建用户错误: {e}")
        return jsonify({
            'success': False,
            'message': '创建用户失败'
        }), 500


@app.route('/admin/users/<user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """更新用户信息"""
    try:
        data = request.get_json()
        
        # 过滤允许更新的字段
        update_data = {}
        for field in ['display_name', 'role', 'email', 'is_active']:
            if field in data:
                if field == 'display_name':
                    update_data[field] = data['displayName'] if 'displayName' in data else data[field]
                else:
                    update_data[field] = data[field]
        
        if not update_data:
            return jsonify({
                'success': False,
                'message': '没有需要更新的字段'
            }), 400
        
        # 更新用户
        success = db.update_user(user_id, **update_data)
        
        if success:
            return jsonify({
                'success': True,
                'message': '用户更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '用户不存在或更新失败'
            }), 404
            
    except Exception as e:
        print(f"❌ 更新用户错误: {e}")
        return jsonify({
            'success': False,
            'message': '更新用户失败'
        }), 500


@app.route('/admin/users/<user_id>/password', methods=['PUT'])
@admin_required
def change_user_password(user_id):
    """修改用户密码"""
    try:
        data = request.get_json()
        new_password = data.get('password', '')
        
        if not new_password:
            return jsonify({
                'success': False,
                'message': '新密码不能为空'
            }), 400
        
        if len(new_password) < 6:
            return jsonify({
                'success': False,
                'message': '密码长度不能少于6位'
            }), 400
        
        # 修改密码
        success = db.change_password(user_id, new_password)
        
        if success:
            return jsonify({
                'success': True,
                'message': '密码修改成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '用户不存在或密码修改失败'
            }), 404
            
    except Exception as e:
        print(f"❌ 修改密码错误: {e}")
        return jsonify({
            'success': False,
            'message': '修改密码失败'
        }), 500


# ========== 文件提示词管理路由 ==========

@app.route('/api/file-prompt/<filename>', methods=['GET'])
@login_required
def get_file_prompt(filename):
    """获取文件的自定义提示词"""
    try:
        filename = secure_chinese_filename(filename)
        
        # 获取当前用户信息
        current_user = db.get_user_by_id(session['user_id'])
        username = current_user['username'] if current_user else 'unknown'
        
        print(f"📝 [提示词查看] 用户 {username} 正在查看文件 {filename} 的提示词")
        
        # 确保文件存在
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(filepath):
            print(f"⚠️ [提示词查看] 文件不存在: {filename}")
            return jsonify({'error': '文件不存在'}), 404
        
        # 确保文件有提示词记录
        created_by = username if current_user else 'system'
        db.create_file_prompt_if_not_exists(filename, created_by=created_by)
        
        # 获取提示词信息
        prompt_info = db.get_file_prompt_info(filename)
        
        if prompt_info:
            prompt_length = len(prompt_info['custom_prompt'])
            print(f"✅ [提示词查看] 成功获取文件 {filename} 的提示词，长度: {prompt_length} 字符")
            
            return jsonify({
                'success': True,
                'filename': prompt_info['filename'],
                'custom_prompt': prompt_info['custom_prompt'],
                'updated_at': prompt_info['updated_at'],
                'updated_by': prompt_info['updated_by']
            })
        else:
            print(f"❌ [提示词查看] 获取文件 {filename} 的提示词失败")
            return jsonify({'error': '获取提示词失败'}), 500
            
    except Exception as e:
        print(f"❌ [提示词查看] 获取文件提示词错误: {e}")
        return jsonify({'error': f'获取提示词失败: {str(e)}'}), 500

@app.route('/api/file-prompt/<filename>', methods=['POST'])
@login_required
def set_file_prompt(filename):
    """设置文件的自定义提示词"""
    try:
        filename = secure_chinese_filename(filename)
        data = request.get_json()
        custom_prompt = data.get('custom_prompt', '').strip()
        
        # 获取当前用户信息
        current_user = db.get_user_by_id(session['user_id'])
        username = current_user['username'] if current_user else 'unknown'
        
        print(f"✏️ [提示词编辑] 用户 {username} 正在编辑文件 {filename} 的提示词")
        
        if not custom_prompt:
            print(f"⚠️ [提示词编辑] 提示词为空，用户: {username}, 文件: {filename}")
            return jsonify({'error': '提示词不能为空'}), 400
        
        prompt_length = len(custom_prompt)
        print(f"📊 [提示词编辑] 新提示词长度: {prompt_length} 字符")
        
        # 确保文件存在
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(filepath):
            print(f"⚠️ [提示词编辑] 文件不存在: {filename}")
            return jsonify({'error': '文件不存在'}), 404
        
        # 获取旧提示词进行对比
        old_prompt_info = db.get_file_prompt_info(filename)
        old_prompt = old_prompt_info['custom_prompt'] if old_prompt_info else ''
        old_length = len(old_prompt)
        
        # 保存提示词
        updated_by = username if current_user else 'system'
        success = db.set_file_prompt(filename, custom_prompt, updated_by)
        
        if success:
            print(f"✅ [提示词编辑] 成功保存文件 {filename} 的提示词")
            print(f"📈 [提示词编辑] 长度变化: {old_length} → {prompt_length} 字符 (变化: {prompt_length - old_length:+d})")
            
            return jsonify({
                'success': True,
                'message': '提示词保存成功',
                'filename': filename,
                'custom_prompt': custom_prompt
            })
        else:
            print(f"❌ [提示词编辑] 保存文件 {filename} 的提示词失败")
            return jsonify({'error': '保存提示词失败'}), 500
            
    except Exception as e:
        print(f"❌ [提示词编辑] 设置文件提示词错误: {e}")
        return jsonify({'error': f'保存提示词失败: {str(e)}'}), 500

@app.route('/api/file-data/<filename>', methods=['GET'])
@login_required
def get_file_data(filename):
    """获取文件数据内容用于编辑"""
    try:
        filename = secure_chinese_filename(filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404
        
        # 权限检查
        current_user_id = session['user_id']
        current_user = db.get_user_by_id(current_user_id)
        is_admin_or_reviewer = current_user and current_user['role'] in ['admin', 'reviewer']
        
        # 检查文件所有者
        file_record = db.get_uploaded_file_by_filename(filename)
        if file_record:
            file_owner_id = file_record['uploaded_by']
            if file_owner_id != current_user_id and not is_admin_or_reviewer:
                return jsonify({'error': '您没有权限编辑此文件'}), 403
        elif not is_admin_or_reviewer:
            # 历史文件，只有管理员和reviewer可以编辑
            return jsonify({'error': '您没有权限编辑历史文件'}), 403
        
        # 读取文件数据
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath, encoding='utf-8-sig')
        else:
            df = pd.read_excel(filepath, engine='openpyxl')
        
        # 转换为可编辑的格式
        columns = df.columns.tolist()
        data = df.to_dict('records')
        
        # 确保所有值都是字符串，避免前端显示问题
        for row in data:
            for key in row:
                if row[key] is None or pd.isna(row[key]):
                    row[key] = ''
                else:
                    row[key] = str(row[key])
        
        print(f"📖 用户 {current_user_id} 获取文件 {filename} 数据，包含 {len(data)} 行")
        
        return jsonify({
            'success': True,
            'filename': filename,
            'columns': columns,
            'data': data,
            'total_rows': len(data)
        })
        
    except Exception as e:
        print(f"获取文件数据失败: {e}")
        return jsonify({'error': f'获取文件数据失败: {str(e)}'}), 500

@app.route('/api/file-data/<filename>', methods=['POST'])
@login_required
def save_file_data(filename):
    """保存编辑后的文件数据"""
    try:
        filename = secure_chinese_filename(filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # 权限检查（与获取数据相同的逻辑）
        current_user_id = session['user_id']
        current_user = db.get_user_by_id(current_user_id)
        is_admin_or_reviewer = current_user and current_user['role'] in ['admin', 'reviewer']
        
        file_record = db.get_uploaded_file_by_filename(filename)
        if file_record:
            file_owner_id = file_record['uploaded_by']
            if file_owner_id != current_user_id and not is_admin_or_reviewer:
                return jsonify({'error': '您没有权限保存此文件'}), 403
        elif not is_admin_or_reviewer:
            return jsonify({'error': '您没有权限保存历史文件'}), 403
        
        # 获取前端发送的数据
        request_data = request.get_json()
        if not request_data or 'data' not in request_data:
            return jsonify({'error': '缺少数据'}), 400
        
        data = request_data['data']
        
        if not data:
            return jsonify({'error': '数据为空'}), 400
        
        # 验证必需的列
        if data:
            first_row = data[0]
            if 'query' not in first_row:
                return jsonify({'error': '数据必须包含"query"列'}), 400
        
        # 转换为DataFrame
        df = pd.DataFrame(data)
        
        # 创建备份
        backup_path = filepath + '.backup'
        if os.path.exists(filepath):
            import shutil
            shutil.copy2(filepath, backup_path)
            print(f"📋 创建文件备份: {backup_path}")
        
        # 保存文件
        try:
            if filename.endswith('.csv'):
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
            else:
                df.to_excel(filepath, index=False, engine='openpyxl')
            
            print(f"💾 用户 {current_user_id} 保存文件 {filename}，包含 {len(data)} 行")
            
            # 更新数据库记录
            if file_record:
                file_size = os.path.getsize(filepath)
                # 检测评测模式
                mode = detect_evaluation_mode(df)
                
                # 更新文件记录
                db.save_uploaded_file(
                    filename=filename,
                    original_filename=filename,
                    file_path=filepath,
                    uploaded_by=current_user_id,
                    file_type='dataset',
                    mode=mode,
                    total_count=len(df),
                    file_size=file_size
                )
                print(f"📝 更新文件记录: {filename}")
            
            return jsonify({
                'success': True,
                'message': '文件保存成功',
                'filename': filename,
                'total_rows': len(data)
            })
            
        except Exception as save_error:
            # 如果保存失败，恢复备份
            if os.path.exists(backup_path):
                import shutil
                shutil.move(backup_path, filepath)
                print(f"🔄 保存失败，已恢复备份")
            raise save_error
        finally:
            # 清理备份文件
            if os.path.exists(backup_path):
                os.remove(backup_path)
                
    except Exception as e:
        print(f"保存文件数据失败: {e}")
        return jsonify({'error': f'保存文件数据失败: {str(e)}'}), 500

@app.route('/api/file-prompts', methods=['GET'])
@login_required
def list_file_prompts():
    """获取所有文件提示词列表（仅管理员或查看用途）"""
    try:
        prompts = db.list_all_file_prompts()
        return jsonify({
            'success': True,
            'prompts': prompts
        })
    except Exception as e:
        print(f"❌ 获取文件提示词列表错误: {e}")
        return jsonify({'error': f'获取提示词列表失败: {str(e)}'}), 500


# ========== 系统配置管理路由 ==========

@app.route('/admin/api/configs', methods=['GET'])
@admin_required
def get_system_configs():
    """获取系统配置列表"""
    try:
        category = request.args.get('category', None)
        configs = db.get_all_system_configs(category)
        
        # 隐藏敏感配置的值
        for config in configs:
            if config.get('is_sensitive'):
                config['config_value'] = '****'
        
        return jsonify({
            'success': True,
            'configs': configs
        })
    except Exception as e:
        print(f"❌ 获取系统配置错误: {e}")
        return jsonify({
            'success': False,
            'message': '获取系统配置失败'
        }), 500

@app.route('/admin/api/configs', methods=['POST'])
@admin_required
def create_system_config():
    """创建系统配置"""
    try:
        data = request.get_json()
        config_key = data.get('config_key', '').strip()
        config_value = data.get('config_value', '').strip()
        config_type = data.get('config_type', 'string')
        description = data.get('description', '')
        category = data.get('category', 'general')
        is_sensitive = data.get('is_sensitive', False)
        
        if not config_key or not config_value:
            return jsonify({
                'success': False,
                'message': '配置项键名和值不能为空'
            }), 400
        
        # 获取当前用户
        current_user = db.get_user_by_id(session['user_id'])
        updated_by = current_user['username'] if current_user else 'admin'
        
        success = db.set_system_config(
            config_key, config_value, config_type, 
            description, category, is_sensitive, updated_by
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': '配置项创建成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '配置项创建失败'
            }), 500
            
    except Exception as e:
        print(f"❌ 创建系统配置错误: {e}")
        return jsonify({
            'success': False,
            'message': '创建配置项失败'
        }), 500

@app.route('/admin/api/configs/<config_key>', methods=['PUT'])
@admin_required
def update_system_config(config_key):
    """更新系统配置"""
    try:
        data = request.get_json()
        config_value = data.get('config_value', '').strip()
        config_type = data.get('config_type', 'string')
        description = data.get('description', '')
        category = data.get('category', 'general')
        is_sensitive = data.get('is_sensitive', False)
        
        if not config_value:
            return jsonify({
                'success': False,
                'message': '配置值不能为空'
            }), 400
        
        # 获取当前用户
        current_user = db.get_user_by_id(session['user_id'])
        updated_by = current_user['username'] if current_user else 'admin'
        
        success = db.set_system_config(
            config_key, config_value, config_type, 
            description, category, is_sensitive, updated_by
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': '配置项更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '配置项更新失败'
            }), 500
            
    except Exception as e:
        print(f"❌ 更新系统配置错误: {e}")
        return jsonify({
            'success': False,
            'message': '更新配置项失败'
        }), 500

@app.route('/admin/api/configs/<config_key>', methods=['DELETE'])
@admin_required
def delete_system_config(config_key):
    """删除系统配置"""
    try:
        success = db.delete_system_config(config_key)
        
        if success:
            return jsonify({
                'success': True,
                'message': '配置项删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '配置项不存在或删除失败'
            }), 404
            
    except Exception as e:
        print(f"❌ 删除系统配置错误: {e}")
        return jsonify({
            'success': False,
            'message': '删除配置项失败'
        }), 500

# ========== 评分标准管理路由 ==========

@app.route('/admin/scoring-criteria', methods=['GET'])
@admin_required
def get_scoring_criteria():
    """获取评分标准列表"""
    try:
        criteria_type = request.args.get('type', None)
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        criteria_list = db.get_all_scoring_criteria(criteria_type, active_only)
        
        return jsonify({
            'success': True,
            'criteria': criteria_list
        })
    except Exception as e:
        print(f"❌ 获取评分标准错误: {e}")
        return jsonify({
            'success': False,
            'message': '获取评分标准失败'
        }), 500

@app.route('/admin/scoring-criteria', methods=['POST'])
@admin_required
def create_scoring_criteria():
    """创建评分标准"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '')
        criteria_type = data.get('criteria_type', 'subjective')
        criteria_config = data.get('criteria_config', {})
        dataset_pattern = data.get('dataset_pattern', None)
        is_default = data.get('is_default', False)
        
        if not name or not criteria_config:
            return jsonify({
                'success': False,
                'message': '评分标准名称和配置不能为空'
            }), 400
        
        # 获取当前用户
        current_user = db.get_user_by_id(session['user_id'])
        created_by = current_user['username'] if current_user else 'admin'
        
        criteria_id = db.create_scoring_criteria(
            name, description, criteria_type, criteria_config,
            dataset_pattern, is_default, created_by
        )
        
        if criteria_id:
            return jsonify({
                'success': True,
                'message': '评分标准创建成功',
                'criteria_id': criteria_id
            })
        else:
            return jsonify({
                'success': False,
                'message': '评分标准创建失败'
            }), 500
            
    except Exception as e:
        print(f"❌ 创建评分标准错误: {e}")
        return jsonify({
            'success': False,
            'message': '创建评分标准失败'
        }), 500

@app.route('/admin/scoring-criteria/<criteria_id>', methods=['GET'])
@admin_required
def get_scoring_criteria_detail(criteria_id):
    """获取评分标准详情"""
    try:
        criteria = db.get_scoring_criteria(criteria_id)
        
        if criteria:
            return jsonify({
                'success': True,
                'criteria': criteria
            })
        else:
            return jsonify({
                'success': False,
                'message': '评分标准不存在'
            }), 404
            
    except Exception as e:
        print(f"❌ 获取评分标准详情错误: {e}")
        return jsonify({
            'success': False,
            'message': '获取评分标准详情失败'
        }), 500

@app.route('/admin/scoring-criteria/<criteria_id>', methods=['PUT'])
@admin_required
def update_scoring_criteria(criteria_id):
    """更新评分标准"""
    try:
        data = request.get_json()
        
        update_fields = {}
        for field in ['name', 'description', 'criteria_config', 'dataset_pattern', 'is_default', 'is_active']:
            if field in data:
                update_fields[field] = data[field]
        
        if not update_fields:
            return jsonify({
                'success': False,
                'message': '没有提供要更新的字段'
            }), 400
        
        success = db.update_scoring_criteria(criteria_id, **update_fields)
        
        if success:
            return jsonify({
                'success': True,
                'message': '评分标准更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '评分标准不存在或更新失败'
            }), 404
            
    except Exception as e:
        print(f"❌ 更新评分标准错误: {e}")
        return jsonify({
            'success': False,
            'message': '更新评分标准失败'
        }), 500

@app.route('/admin/scoring-criteria/<criteria_id>', methods=['DELETE'])
@admin_required
def delete_scoring_criteria(criteria_id):
    """删除评分标准"""
    try:
        success = db.delete_scoring_criteria(criteria_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '评分标准删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '评分标准不存在或删除失败'
            }), 404
            
    except Exception as e:
        print(f"❌ 删除评分标准错误: {e}")
        return jsonify({
            'success': False,
            'message': '删除评分标准失败'
        }), 500

# ========== 移除了普通用户的评分标准查看功能 ==========
# 已简化为只保留"编辑提示词"功能，评分标准现在只能通过提示词编辑查看


# ========== 任务管理路由 ==========

@app.route('/api/tasks/running', methods=['GET'])
@login_required
def get_running_tasks():
    """获取正在进行的任务列表"""
    try:
        current_user_id = session.get('user_id', 'anonymous')
        tasks = db.get_running_tasks(status='running', created_by=current_user_id)
        
        # 合并内存中的任务状态信息
        for task in tasks:
            task_id = task['task_id']
            if task_id in task_status:
                memory_task = task_status[task_id]
                task.update({
                    'memory_status': memory_task.status,
                    'memory_progress': memory_task.progress,
                    'memory_current_step': memory_task.current_step,
                    'is_active': True
                })
            else:
                task['is_active'] = False
        
        return jsonify({
            'success': True,
            'tasks': tasks
        })
    except Exception as e:
        print(f"❌ 获取运行任务失败: {e}")
        return jsonify({'error': f'获取任务列表失败: {str(e)}'}), 500



@app.route('/api/tasks/<task_id>/cancel', methods=['DELETE'])
@login_required
def cancel_task(task_id):
    """取消/删除任务"""
    try:
        # 检查任务是否存在且属于当前用户
        current_user_id = session.get('user_id', 'anonymous')
        task = db.get_running_task(task_id)
        
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        
        if task['created_by'] != current_user_id:
            return jsonify({'error': '无权限操作此任务'}), 403
        
        # 从内存中删除任务状态
        if task_id in task_status:
            del task_status[task_id]
        
        # 从数据库中删除任务记录
        db.delete_running_task(task_id)
        
        return jsonify({
            'success': True,
            'message': '任务已删除'
        })
    except Exception as e:
        print(f"❌ 删除任务失败: {e}")
        return jsonify({'error': f'删除任务失败: {str(e)}'}), 500

@app.route('/api/tasks/<task_id>/connect', methods=['POST'])
@login_required
def connect_to_task(task_id):
    """连接到现有任务（重新进入进度页面）"""
    try:
        # 检查任务是否存在且属于当前用户
        current_user_id = session.get('user_id', 'anonymous')
        task = db.get_running_task(task_id)
        
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        
        if task['created_by'] != current_user_id:
            return jsonify({'error': '无权限访问此任务'}), 403
        
        # 如果内存中没有此任务，尝试从数据库恢复
        if task_id not in task_status and task['status'] == 'running':
            # 重新创建内存中的任务状态
            task_status[task_id] = TaskStatus(task_id)
            task_status[task_id].evaluation_mode = task['evaluation_mode']
            task_status[task_id].selected_models = task['selected_models']
            task_status[task_id].progress = task['progress']
            task_status[task_id].total = task['total']
            task_status[task_id].current_step = task['current_step']
            task_status[task_id].status = "运行中"
            
            # 从数据库时间戳解析
            if task['started_at']:
                task_status[task_id].start_time = datetime.fromisoformat(task['started_at'])
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'task': task
        })
    except Exception as e:
        print(f"❌ 连接任务失败: {e}")
        return jsonify({'error': f'连接任务失败: {str(e)}'}), 500


# ========== 分享功能路由 ==========

@app.route('/api/share/create', methods=['POST'])
@login_required
def create_share():
    """创建分享链接"""
    try:
        data = request.get_json()
        result_id = data.get('result_id')
        share_type = data.get('share_type', 'public')  # 'public' 或 'user_specific'
        title = data.get('title', '')
        description = data.get('description', '')
        expires_hours = data.get('expires_hours', 0)  # 0表示永不过期
        allow_download = data.get('allow_download', False)
        password = data.get('password', '')
        access_limit = data.get('access_limit', 0)  # 0表示无限制
        shared_to = data.get('shared_to', None)  # 特定用户分享
        
        if not result_id:
            return jsonify({'error': '缺少结果ID'}), 400
        
        # 验证result_id存在且用户有权限分享
        result_detail = db.get_result_by_id(result_id)
        if not result_detail:
            return jsonify({'error': '评测结果不存在'}), 404
        
        current_user_id = session['user_id']
        current_user = db.get_user_by_id(current_user_id)
        
        # 检查权限：只有结果创建者或管理员可以分享
        if (result_detail['created_by'] != current_user_id and 
            current_user['role'] != 'admin'):
            return jsonify({'error': '您没有权限分享此结果'}), 403
        
        # 创建分享链接
        share_info = db.create_share_link(
            result_id=result_id,
            shared_by=current_user_id,
            share_type=share_type,
            title=title or result_detail['name'],
            description=description,
            expires_hours=expires_hours if expires_hours > 0 else None,
            allow_download=allow_download,
            password=password if password else None,
            access_limit=access_limit,
            shared_to=shared_to
        )
        
        if share_info:
            # 生成分享URL
            share_url = url_for('view_shared_result', 
                              share_token=share_info['share_token'], 
                              _external=True)
            
            return jsonify({
                'success': True,
                'share_id': share_info['share_id'],
                'share_url': share_url,
                'share_token': share_info['share_token'],
                'expires_at': share_info['expires_at'],
                'message': '分享链接创建成功'
            })
        else:
            return jsonify({'error': '创建分享链接失败'}), 500
            
    except Exception as e:
        print(f"❌ 创建分享链接错误: {e}")
        return jsonify({'error': f'创建分享链接失败: {str(e)}'}), 500

@app.route('/api/share/my-shares', methods=['GET'])
@login_required
def get_my_shares():
    """获取当前用户的分享链接"""
    try:
        current_user_id = session['user_id']
        include_revoked = request.args.get('include_revoked', 'false').lower() == 'true'
        
        shares = db.get_user_shared_links(current_user_id, include_revoked)
        
        # 为每个分享添加完整的URL
        for share in shares:
            share['share_url'] = url_for('view_shared_result', 
                                       share_token=share['share_token'], 
                                       _external=True)
            
            # 检查是否过期
            if share['expires_at']:
                expire_time = datetime.fromisoformat(share['expires_at'])
                share['is_expired'] = datetime.now() > expire_time
            else:
                share['is_expired'] = False
        
        return jsonify({
            'success': True,
            'shares': shares
        })
        
    except Exception as e:
        print(f"❌ 获取分享列表错误: {e}")
        return jsonify({'error': f'获取分享列表失败: {str(e)}'}), 500

@app.route('/api/share/<share_id>/revoke', methods=['POST'])
@login_required
def revoke_share(share_id):
    """撤销分享链接"""
    try:
        current_user_id = session['user_id']
        current_user = db.get_user_by_id(current_user_id)
        
        # TODO: 验证分享所有权（可以加个检查）
        
        success = db.revoke_share_link(share_id, current_user_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '分享链接已撤销'
            })
        else:
            return jsonify({'error': '撤销分享链接失败'}), 500
            
    except Exception as e:
        print(f"❌ 撤销分享链接错误: {e}")
        return jsonify({'error': f'撤销分享链接失败: {str(e)}'}), 500

@app.route('/api/share/<share_id>/logs', methods=['GET'])
@login_required
def get_share_logs(share_id):
    """获取分享链接访问日志"""
    try:
        current_user_id = session['user_id']
        # TODO: 验证分享所有权
        
        limit = int(request.args.get('limit', 50))
        logs = db.get_share_access_logs(share_id, limit)
        
        return jsonify({
            'success': True,
            'logs': logs
        })
        
    except Exception as e:
        print(f"❌ 获取分享日志错误: {e}")
        return jsonify({'error': f'获取分享日志失败: {str(e)}'}), 500

@app.route('/share/<share_token>')
def view_shared_result(share_token):
    """查看分享的评测结果（公开访问）"""
    try:
        # 获取请求信息
        ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
        user_agent = request.headers.get('User-Agent', '')
        user_id = session.get('user_id', None)
        
        # 检查是否需要密码验证
        password = request.args.get('password', '')
        
        # 验证分享链接访问权限
        access_result = db.verify_share_access(share_token, password)
        
        if not access_result['valid']:
            if access_result.get('require_password'):
                # 显示密码输入页面
                return render_template('shared_password.html', 
                                     share_token=share_token,
                                     error_message=access_result['reason'])
            else:
                # 显示错误信息
                return render_template('shared_error.html', 
                                     error_message=access_result['reason']), 403
        
        share_info = access_result['share_info']
        
        # 记录访问
        db.record_share_access(share_token, ip_address, user_agent, user_id)
        
        # 读取评测结果文件
        result_file_path = share_info.get('result_file')
        if not result_file_path:
            return render_template('shared_error.html', 
                                 error_message='分享链接缺少结果文件信息'), 404
        
        if not os.path.exists(result_file_path):
            # 尝试不同的路径查找
            alternative_paths = [
                result_file_path,
                os.path.join('results', os.path.basename(result_file_path)),
                os.path.join('results_history', os.path.basename(result_file_path)),
                os.path.join(app.config.get('RESULTS_FOLDER', 'results'), os.path.basename(result_file_path))
            ]
            
            found_path = None
            for path in alternative_paths:
                if os.path.exists(path):
                    found_path = path
                    print(f"🔍 在备用路径找到文件: {path}")
                    break
            
            if found_path:
                result_file_path = found_path
            else:
                return render_template('shared_error.html', 
                                     error_message=f'结果文件不存在: {os.path.basename(result_file_path)}'), 404
        
        # 读取CSV数据
        try:
            df = pd.read_csv(result_file_path, encoding='utf-8-sig')
            print(f"📊 [分享页面] 成功读取CSV文件，数据形状: {df.shape}")
        except Exception as e:
            print(f"❌ [分享页面] 读取CSV文件失败: {e}")
            return render_template('shared_error.html', 
                                 error_message=f'读取结果文件失败: {str(e)}'), 500
        
        # 验证DataFrame
        if df is None or df.empty:
            return render_template('shared_error.html', 
                                 error_message='结果文件为空或无效'), 500
        
        # 准备数据
        try:
            # 安全地处理 models 字段
            models_data = share_info.get('models', [])
            if not isinstance(models_data, list):
                print(f"⚠️ [分享页面] models字段类型异常: {type(models_data)}, 值: {models_data}")
                if isinstance(models_data, str):
                    try:
                        # 尝试JSON解析
                        import json
                        models_data = json.loads(models_data)
                        if not isinstance(models_data, list):
                            models_data = []
                    except:
                        models_data = []
                else:
                    models_data = []
            
            # 清理DataFrame数据，确保所有值都是安全的类型
            cleaned_data = []
            for record in df.to_dict('records'):
                cleaned_record = {}
                for key, value in record.items():
                    # 将所有值转换为安全的字符串或数字
                    if pd.isna(value) or value is None:
                        cleaned_record[key] = ''
                    elif isinstance(value, (int, float)):
                        cleaned_record[key] = value
                    else:
                        cleaned_record[key] = str(value)
                cleaned_data.append(cleaned_record)
            
            result_data = {
                'filename': os.path.basename(result_file_path),
                'columns': df.columns.tolist(),
                'data': cleaned_data,  # 使用清理后的数据
                'share_info': {
                    'title': share_info.get('title', share_info.get('result_name', '未知结果')),
                    'description': share_info.get('description', ''),
                    'shared_by_name': share_info.get('shared_by_name', '未知用户'),
                    'created_at': share_info.get('created_at', ''),
                    'evaluation_mode': share_info.get('evaluation_mode', ''),
                    'models': models_data,  # 确保是列表类型
                    'allow_download': share_info.get('allow_download', False)
                }
            }
            
            # 验证数据结构
            print(f"📝 [分享页面] 数据准备完成:")
            print(f"  - 列数: {len(df.columns)}")
            print(f"  - 行数: {len(df)}")
            print(f"  - models类型: {type(result_data['share_info']['models'])}")
            print(f"  - models内容: {result_data['share_info']['models']}")
            print(f"  - columns类型: {type(result_data['columns'])}")
            print(f"  - data类型: {type(result_data['data'])}")
            
        except Exception as e:
            print(f"❌ [分享页面] 数据准备失败: {e}")
            import traceback
            print(f"🐛 [分享页面] 错误堆栈: {traceback.format_exc()}")
            return render_template('shared_error.html', 
                                 error_message=f'数据处理失败: {str(e)}'), 500
        
        # 获取统计分析（如果analytics可用）
        advanced_stats = None
        print(f"🔍 [分享页面] Analytics 模块状态: {'可用' if analytics else '不可用'}")
        
        if analytics:
            try:
                # 预处理数据：清理评分列中的字符串格式
                print(f"🧹 [分享页面] 开始清理数据...")
                try:
                    # 找到所有评分列
                    score_columns = [col for col in df.columns if isinstance(col, str) and '评分' in col]
                    print(f"🔍 [分享页面] 发现评分列: {score_columns}")
                    
                    # 清理每个评分列的数据
                    for col in score_columns:
                        if col in df.columns:
                            # 清理字符串格式的分数（如"0分"变成0）
                            def clean_score(x):
                                if pd.isna(x):
                                    return x
                                if isinstance(x, str):
                                    # 移除"分"字符，尝试转换为数字
                                    clean_x = x.replace('分', '').strip()
                                    try:
                                        return float(clean_x)
                                    except (ValueError, TypeError):
                                        return None
                                return x
                            
                            df[col] = df[col].apply(clean_score)
                            print(f"✅ [分享页面] 清理评分列 {col} 完成")
                    
                    # 将清理后的数据保存回临时文件
                    df.to_csv(result_file_path, index=False, encoding='utf-8')
                    print(f"✅ [分享页面] 清理后的数据已保存")
                
                except Exception as clean_error:
                    print(f"⚠️ [分享页面] 数据清理过程出错: {clean_error}")
                
                evaluation_data = {
                    'evaluation_mode': share_info.get('evaluation_mode', ''),
                    'models': share_info.get('models', []),
                    'question_count': len(df),
                    'start_time': share_info.get('result_created_at', ''),
                    'end_time': share_info.get('result_created_at', '')
                }
                
                print(f"🔄 [分享页面] 开始分析评测结果...")
                analysis_result = analytics.analyze_evaluation_results(
                    result_file=result_file_path,
                    evaluation_data=evaluation_data
                )
                
                if analysis_result.get('success'):
                    advanced_stats = analysis_result['analysis']
                    print(f"✅ [分享页面] 成功生成高级统计分析")
                    
                    # 验证和修复高级分析数据结构
                    if advanced_stats:
                        print(f"🔍 [分享页面] 高级分析数据结构: {type(advanced_stats)}")
                        print(f"🔍 [分享页面] 高级分析内容: {advanced_stats}")
                        
                        # 确保 total_responses 字段存在且为数字
                        if 'total_responses' not in advanced_stats or not isinstance(advanced_stats.get('total_responses'), (int, float)):
                            print(f"⚠️ [分享页面] 高级分析缺少或类型错误的 total_responses，正在修复...")
                            
                            # 尝试从分数分布计算总响应数
                            total_responses = 0
                            if (advanced_stats.get('score_analysis') and 
                                isinstance(advanced_stats['score_analysis'], dict) and
                                advanced_stats['score_analysis'].get('score_distribution')):
                                
                                score_dist = advanced_stats['score_analysis']['score_distribution']
                                if isinstance(score_dist, dict):
                                    total_responses = sum(v for v in score_dist.values() if isinstance(v, (int, float)))
                            
                            # 如果还是0，使用DataFrame行数
                            if total_responses == 0:
                                total_responses = len(df)
                            
                            advanced_stats['total_responses'] = total_responses
                            print(f"✅ [分享页面] 设置 total_responses = {total_responses}")
                else:
                    print(f"❌ [分享页面] 分析失败: {analysis_result.get('error', '未知错误')}")
            except Exception as e:
                print(f"❌ [分享页面] 分析过程出错: {e}")
        
        # 如果没有高级统计，生成基础的统计数据用于前端显示
        if not advanced_stats:
            print(f"📝 [分享页面] 生成基础统计数据作为后备方案")
            try:
                # 确保df是有效的DataFrame
                if not isinstance(df, pd.DataFrame):
                    print(f"❌ [分享页面] df不是DataFrame类型: {type(df)}")
                    raise ValueError(f"数据类型错误: {type(df)}")
                    
                # 简单的分数统计
                score_columns = [col for col in df.columns if isinstance(col, str) and ('评分' in col or 'score' in col.lower())]
                print(f"🔍 [分享页面] 找到评分列: {score_columns}")
                
                basic_stats = {
                    'basic_stats': {
                        'total_questions': len(df),
                        'response_rate': 100.0
                    },
                    'score_analysis': {
                        'model_performance': {},
                        'score_distribution': {}
                    },
                    'model_rankings': [],
                    'performance_metrics': {
                        'estimated_time_per_question': '30秒 (估算)',
                        'throughput': 120  # 每小时120题
                    },
                    'total_responses': 0  # 默认值，后续会更新
                }
                
                if score_columns:
                    # 为每个模型计算基础统计
                    model_scores = {}
                    for col in score_columns:
                        try:
                            if '评分' in col:
                                model_name = col.replace('_评分', '').replace('评分', '').strip()
                                print(f"🔄 [分享页面] 处理模型: {model_name}, 列: {col}")
                                
                                # 安全地处理分数数据
                                scores_series = pd.to_numeric(df[col], errors='coerce').dropna()
                                if not isinstance(scores_series, pd.Series):
                                    print(f"⚠️ [分享页面] scores_series 类型异常: {type(scores_series)}")
                                    continue
                                    
                                scores_count = len(scores_series)
                                if scores_count > 0:
                                    avg_score = float(scores_series.mean())
                                    median_score = float(scores_series.median())
                                    std_dev = float(scores_series.std()) if scores_count > 1 else 0.0
                                    min_score = float(scores_series.min())
                                    max_score = float(scores_series.max())
                                    
                                    # 计算分位数
                                    try:
                                        percentiles = {
                                            '25th': float(scores_series.quantile(0.25)),
                                            '75th': float(scores_series.quantile(0.75)),
                                            '90th': float(scores_series.quantile(0.90))
                                        }
                                    except:
                                        percentiles = {'25th': min_score, '75th': max_score, '90th': max_score}
                                    
                                    model_scores[model_name] = avg_score
                                    basic_stats['score_analysis']['model_performance'][model_name] = {
                                        'mean_score': avg_score,  # 模板期望的字段名
                                        'avg_score': avg_score,   # 保持兼容性
                                        'median_score': median_score,
                                        'std_dev': std_dev,
                                        'min_score': min_score,
                                        'max_score': max_score,
                                        'score_count': scores_count,
                                        'total_score': float(scores_series.sum()),
                                        'question_count': scores_count,
                                        'percentiles': percentiles
                                    }
                                    print(f"✅ [分享页面] {model_name}: 平均分={avg_score:.2f}, 题数={scores_count}")
                        except Exception as col_error:
                            print(f"⚠️ [分享页面] 处理列 {col} 时出错: {col_error}")
                            continue
                    
                    # 生成模型排名
                    if model_scores:
                        try:
                            sorted_models = sorted(model_scores.items(), key=lambda x: x[1], reverse=True)
                            basic_stats['model_rankings'] = [
                                {'model': model, 'avg_score': score} 
                                for model, score in sorted_models
                            ]
                            print(f"📊 [分享页面] 模型排名生成完成: {len(basic_stats['model_rankings'])} 个模型")
                        except Exception as ranking_error:
                            print(f"⚠️ [分享页面] 生成模型排名时出错: {ranking_error}")
                    
                    # 分数分布统计
                    try:
                        all_scores = []
                        for col in score_columns:
                            scores_series = pd.to_numeric(df[col], errors='coerce').dropna()
                            if isinstance(scores_series, pd.Series):
                                scores_list = scores_series.tolist()
                                all_scores.extend(scores_list)
                        
                        if all_scores and len(all_scores) > 0:
                            from collections import Counter
                            # 处理所有数字类型的评分（不限制范围，完全由用户定义）
                            valid_scores = []
                            for score in all_scores:
                                if isinstance(score, (int, float)) and not pd.isna(score):
                                    # 将分数转换为适当的数据类型
                                    if isinstance(score, float) and score.is_integer():
                                        valid_scores.append(int(score))
                                    else:
                                        valid_scores.append(float(score))
                            score_counts = Counter(valid_scores)
                            basic_stats['score_analysis']['score_distribution'] = dict(score_counts)
                            basic_stats['total_responses'] = len(all_scores)
                            print(f"📈 [分享页面] 分数分布统计完成: {len(valid_scores)} 个有效分数")
                    except Exception as dist_error:
                        print(f"⚠️ [分享页面] 生成分数分布时出错: {dist_error}")
                else:
                    # 没有评分列时，设置基础的 total_responses
                    basic_stats['total_responses'] = len(df)
                    print(f"📝 [分享页面] 没有评分列，设置 total_responses = {len(df)}")
                
                advanced_stats = basic_stats
                print(f"✅ [分享页面] 基础统计数据生成成功")
                print(f"📊 [分享页面] 统计数据内容: {advanced_stats}")
                print(f"📊 [分享页面] model_rankings: {advanced_stats.get('model_rankings', [])}")
                print(f"📊 [分享页面] score_distribution: {advanced_stats.get('score_analysis', {}).get('score_distribution', {})}")
                
            except Exception as e:
                print(f"❌ [分享页面] 生成基础统计数据失败: {e}")
                import traceback
                print(f"🐛 [分享页面] 详细错误堆栈: {traceback.format_exc()}")
                # 提供最基本的统计数据
                print(f"🚨 [分享页面] 使用最小化统计数据作为最后备用方案")
                advanced_stats = {
                    'basic_stats': {
                        'total_questions': len(df) if isinstance(df, pd.DataFrame) else 0,
                        'response_rate': 100.0
                    },
                    'score_analysis': {'model_performance': {}, 'score_distribution': {}},
                    'model_rankings': [],
                    'performance_metrics': {'estimated_time_per_question': '未知', 'throughput': 0},
                    'total_responses': 0
                }
        
        # 渲染分享页面
        try:
            print(f"🎨 [分享页面] 开始渲染模板...")
            return render_template('shared_result.html', 
                                 result_data=result_data,
                                 advanced_stats=advanced_stats,
                                 share_token=share_token)
        except Exception as render_error:
            print(f"❌ [分享页面] 模板渲染失败: {render_error}")
            import traceback
            print(f"🐛 [分享页面] 渲染错误堆栈: {traceback.format_exc()}")
            return render_template('shared_error.html', 
                                 error_message=f'页面渲染失败: {str(render_error)}'), 500
        
    except Exception as e:
        print(f"❌ 查看分享结果错误: {e}")
        return render_template('shared_error.html', 
                             error_message=f'加载分享内容失败: {str(e)}'), 500

@app.route('/share/<share_token>/download')
def download_shared_result(share_token):
    """下载分享的评测结果文件"""
    try:
        # 验证分享链接访问权限
        password = request.args.get('password', '')
        access_result = db.verify_share_access(share_token, password)
        
        if not access_result['valid']:
            return jsonify({'error': access_result['reason']}), 403
        
        share_info = access_result['share_info']
        
        # 检查是否允许下载
        if not share_info.get('allow_download', False):
            return jsonify({'error': '此分享不允许下载文件'}), 403
        
        # 记录访问
        ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
        user_agent = request.headers.get('User-Agent', '')
        user_id = session.get('user_id', None)
        db.record_share_access(share_token, ip_address, user_agent, user_id)
        
        # 提供文件下载
        result_file_path = share_info.get('result_file')
        if not result_file_path:
            return jsonify({'error': '分享链接缺少结果文件信息'}), 404
        
        if not os.path.exists(result_file_path):
            # 尝试不同的路径查找
            alternative_paths = [
                result_file_path,
                os.path.join('results', os.path.basename(result_file_path)),
                os.path.join('results_history', os.path.basename(result_file_path)),
                os.path.join(app.config.get('RESULTS_FOLDER', 'results'), os.path.basename(result_file_path))
            ]
            
            found_path = None
            for path in alternative_paths:
                if os.path.exists(path):
                    found_path = path
                    print(f"🔍 下载时在备用路径找到文件: {path}")
                    break
            
            if found_path:
                result_file_path = found_path
            else:
                return jsonify({'error': f'文件不存在: {os.path.basename(result_file_path)}'}), 404
        
        return send_file(
            result_file_path,
            as_attachment=True,
            download_name=f"shared_{os.path.basename(result_file_path)}"
        )
        
    except Exception as e:
        print(f"❌ 下载分享文件错误: {e}")
        return jsonify({'error': f'下载失败: {str(e)}'}), 500

# ========== 后台任务：清理过期分享链接 ==========

def cleanup_expired_shares():
    """清理过期的分享链接"""
    try:
        expired_count = db.cleanup_expired_shares()
        if expired_count > 0:
            print(f"🧹 清理了 {expired_count} 个过期的分享链接")
    except Exception as e:
        print(f"⚠️ 清理过期分享链接失败: {e}")

def start_background_tasks():
    """启动后台任务"""
    import threading
    import time
    
    def background_worker():
        while True:
            try:
                # 每小时清理一次过期分享链接
                cleanup_expired_shares()
                time.sleep(3600)  # 1小时
            except Exception as e:
                print(f"⚠️ 后台任务执行失败: {e}")
                time.sleep(300)  # 5分钟后重试
    
    # 启动后台线程
    cleanup_thread = threading.Thread(target=background_worker, daemon=True)
    cleanup_thread.start()
    print("🔄 后台清理任务已启动")

# 初始化默认管理员账户
try:
    if db:
        db.init_default_admin()
        # 启动后台任务
        start_background_tasks()
except Exception as e:
    print(f"⚠️ 初始化默认管理员失败: {e}")


if __name__ == '__main__':
    print("🚀 模型评测Web系统启动中...")
    
    # 显示配置状态
    from config import print_configuration_status
    print_configuration_status()
    
    print("\n🌐 访问地址: http://localhost:8080")
    print("📖 配置帮助: python3 test_config.py")
    app.run(debug=True, host='0.0.0.0', port=8080)
