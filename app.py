import os
import json
import uuid
import asyncio
import aiohttp
import pandas as pd
import time
import re
import csv
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, redirect, url_for, session
from werkzeug.utils import secure_filename
# Removed google.generativeai import as we're using direct API calls
from typing import Dict, Any, List, Optional
import threading
from utils.env_manager import env_manager

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
app.config['DATA_FOLDER'] = 'data'

# 确保文件夹存在
for folder in [app.config['UPLOAD_FOLDER'], app.config['RESULTS_FOLDER'], app.config['DATA_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

# 支持的模型配置
SUPPORTED_MODELS = {
    "HKGAI-V1": {
        "url": "https://chat.hkchat.app/goapi/v1/chat/stream",
        "model": "HKGAI-V1",
        "token_env": "ARK_API_KEY_HKGAI_V1",
        "headers_template": {
            "Accept": "text/event-stream",
            "Content-Type": "application/json"
        }
    },
    "HKGAI-V2": {
        "url": "https://test.hkchat.app/goapi/v1/chat/stream",
        "model": "HKGAI-V2", 
        "token_env": "ARK_API_KEY_HKGAI_V2",
        "headers_template": {
            "Accept": "text/event-stream",
            "Content-Type": "application/json"
        }
    }
    # 可以在这里添加更多模型
}

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

def extract_stream_content(stream) -> str:
    """提取HKGAI流式响应的内容"""
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

async def fetch_model_answer(session: aiohttp.ClientSession, query: str, model_config: dict, idx: int, sem_model: asyncio.Semaphore, task_id: str, request_headers: dict = None) -> str:
    """获取单个模型的答案"""
    # 先从环境变量获取，如果没有则从请求头获取
    token = os.getenv(model_config["token_env"])
    if not token and request_headers:
        model_name = model_config["model"]
        token = request_headers.get(f'X-{model_name.replace("-", "-")}-Key')
    
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
                    content = extract_stream_content(raw.splitlines())
                    
                    # 更新进度
                    if task_id in task_status:
                        task_status[task_id].progress += 1
                        task_status[task_id].current_step = f"已完成 {task_status[task_id].progress}/{task_status[task_id].total} 个查询"
                    
                    return content if content.strip() else "无有效内容返回"
                else:
                    return f"请求失败: HTTP {resp.status}"
        except Exception as e:
            return f"请求异常: {str(e)}"

async def get_multiple_model_answers(queries: List[str], selected_models: List[str], task_id: str, request_headers: dict = None) -> Dict[str, List[str]]:
    """获取多个模型的答案"""
    connector = aiohttp.TCPConnector(limit_per_host=10)
    timeout = aiohttp.ClientTimeout(total=60)
    sem_model = asyncio.Semaphore(5)  # 控制并发数

    results = {model: [] for model in selected_models}
    
    if task_id in task_status:
        task_status[task_id].total = len(queries) * len(selected_models)
        task_status[task_id].status = "获取模型答案中"

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # 为每个模型创建任务
        for model_name in selected_models:
            if model_name not in SUPPORTED_MODELS:
                continue
                
            model_config = SUPPORTED_MODELS[model_name]
            tasks = []
            
            for i, query in enumerate(queries):
                tasks.append(fetch_model_answer(session, query, model_config, i, sem_model, task_id, request_headers))
            
            # 获取该模型的所有答案
            answers = await asyncio.gather(*tasks)
            results[model_name] = answers

    return results

def detect_evaluation_mode(df: pd.DataFrame) -> str:
    """自动检测评测模式"""
    if 'answer' in df.columns:
        return 'objective'  # 客观题评测
    else:
        return 'subjective'  # 主观题评测

def parse_json_str(s: str) -> Dict[str, Any]:
    """解析JSON字符串"""
    s = (s or "").strip()
    if not s:
        return {}
    try:
        # 去掉可能的markdown格式
        if '```json' in s:
            s = s.split('```json')[1].split('```')[0]
        elif '```' in s:
            s = s.split('```')[1].split('```')[0]
        
        result = json.loads(s.strip())
        print(f"✅ JSON解析成功: {len(result)} 个模型结果")
        return result
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败: {e}")
        return {}



async def query_gemini_model(prompt: str, api_key: str = None) -> str:
    """查询Gemini模型 使用数据库配置的端点"""
    from database import db
    
    # 使用传入的API密钥或默认密钥
    actual_api_key = api_key or GOOGLE_API_KEY
    
    if not actual_api_key:
        return "Gemini模型调用失败: 未配置GOOGLE_API_KEY"
    
    # 从数据库获取配置
    api_endpoint = db.get_system_config('gemini_api_endpoint', 'https://generativelanguage.googleapis.com/v1beta/models')
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
    
    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "tools": [
            {
                "google_search": {}
            }
        ]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data, timeout=timeout) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # 提取结果文本
                    if "candidates" in result and len(result["candidates"]) > 0:
                        candidate = result["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            parts = candidate["content"]["parts"]
                            if len(parts) > 0 and "text" in parts[0]:
                                text_result = parts[0]["text"]
                                print(f"✅ Gemini评测成功，返回长度: {len(text_result)}")
                                return text_result
                    
                    print(f"⚠️ Gemini返回格式异常: {result}")
                    return "Gemini模型调用失败: 返回格式异常"
                else:
                    error_text = await response.text()
                    print(f"❌ Gemini API请求失败: HTTP {response.status} - {error_text}")
                    return f"Gemini模型调用失败: HTTP {response.status} - {error_text}"
                    
    except Exception as e:
        print(f"❌ Gemini评测失败: {e}")
        return f"Gemini模型调用失败: {str(e)}"

def build_subjective_eval_prompt(query: str, answers: Dict[str, str], question_type: str = "", filename: str = None) -> str:
    """构建主观题评测提示"""
    type_context = f"问题类型: {question_type}\n" if question_type else ""
    
    models_text = ""
    for i, (model_name, answer) in enumerate(answers.items(), 1):
        models_text += f"模型{i}({model_name})回答: {answer}\n\n"
    
    model_keys = list(answers.keys())
    json_format = {f"模型{i+1}": {"评分": "0-5", "理由": "评分理由"} for i in range(len(model_keys))}
    
    # 获取自定义提示词
    custom_prompt = """你是一位专业的大模型测评工程师，请根据以下标准对模型回答进行客观、公正的评测：

评分标准：
- 5分：回答优秀 - 逻辑清晰、内容准确、表述完整、有深度见解，语言地道自然
- 4分：回答良好 - 基本正确、逻辑合理、表述清楚、符合要求，语言表达流畅  
- 3分：回答一般 - 内容基础、有一定价值、但深度不够或略有瑕疵，语言基本通顺
- 2分：回答较差 - 价值有限、逻辑混乱或有明显错误，但仍有部分可取之处，语言表达欠佳
- 1分：回答很差 - 几乎无价值、严重错误或偏离主题，但尚有一定相关性，语言生硬
- 0分：无回答或完全无关 - 拒绝回答、无意义内容或完全偏离问题

特别评分维度：
🌟 香港口语化 & 语言跟随加分：
- 若回答能够恰当使用香港本地用语、口语化表达，且能根据问题语境调整语言风格，可在基础分数上额外加分
- 语言跟随能力强（如问题用粤语或港式表达，回答也能相应调整）：+0.5分
- 自然融入香港本地文化表达和习惯用语：+0.5分  
- 最高可加1分，总分不超过5分

评测要求：请保持客观中立，重点关注内容的准确性、逻辑性、完整性、实用性，以及语言本地化程度。"""
    
    if filename:
        print(f"🔍 [评测引擎] 正在检查文件 {filename} 是否有自定义提示词...")
        try:
            file_prompt = db.get_file_prompt(filename)
            if file_prompt:
                prompt_length = len(file_prompt)
                print(f"✅ [评测引擎] 使用文件 {filename} 的自定义提示词，长度: {prompt_length} 字符")
                custom_prompt = file_prompt
            else:
                print(f"📝 [评测引擎] 文件 {filename} 未设置自定义提示词，使用系统默认提示词")
        except Exception as e:
            print(f"⚠️ [评测引擎] 获取文件 {filename} 的自定义提示词失败: {e}")
            print(f"🔄 [评测引擎] 回退到使用系统默认提示词")
    
    return f"""
{custom_prompt}

=== 评测任务 ===
{type_context}问题: {query}

=== 模型回答 ===
{models_text}

=== 评测要求 ===
1. 请为每个模型的回答打分（0-5分，整数）
2. 提供详细的评分理由
3. 确保评分客观公正，基于事实和逻辑

请严格按照以下JSON格式输出，不要包含其他任何文字: {json.dumps(json_format, ensure_ascii=False)}
"""

def build_objective_eval_prompt(query: str, standard_answer: str, answers: Dict[str, str], question_type: str = "") -> str:
    """构建客观题评测提示"""
    type_context = f"问题类型: {question_type}\n" if question_type else ""
    
    models_text = ""
    for i, (model_name, answer) in enumerate(answers.items(), 1):
        models_text += f"模型{i}({model_name})回答: {answer}\n\n"
    
    model_keys = list(answers.keys())
    json_format = {f"模型{i+1}": {"评分": "0-5", "准确性": "正确/部分正确/错误", "理由": "评分理由"} for i in range(len(model_keys))}
    
    return f"""
你是一位专业的大模型测评工程师，请根据标准答案对模型回答进行客观、精确的评测。

=== 评分标准 ===
- 5分：完全正确 - 答案准确无误，表述清晰完整，逻辑严密，语言地道自然
- 4分：基本正确 - 核心内容正确，表述清楚，仅有轻微瑕疵或表达不够完美，语言流畅
- 3分：部分正确 - 包含正确要素，但存在遗漏、错误或表述不清，语言基本通顺
- 2分：大部分错误 - 主要内容错误，但仍有部分正确元素或相关信息，语言表达欠佳
- 1分：完全错误但相关 - 答案错误但与问题相关，显示了一定理解，语言生硬
- 0分：完全错误或无关 - 答案完全错误、无关或拒绝回答

=== 特别评分维度 ===
🌟 香港口语化 & 语言跟随加分：
- 若回答能够恰当使用香港本地用语、口语化表达，且能根据问题语境调整语言风格，可在基础分数上额外加分
- 语言跟随能力强（如问题用粤语或港式表达，回答也能相应调整）：+0.5分
- 自然融入香港本地文化表达和习惯用语：+0.5分  
- 最高可加1分，总分不超过5分

=== 准确性评估标准 ===
- 正确：答案与标准答案一致、等价或在合理范围内
- 部分正确：答案包含标准答案的部分要素但不完整
- 错误：答案与标准答案相悖、无关或存在重大错误

=== 评测任务 ===
{type_context}问题: {query}
标准答案: {standard_answer}

=== 模型回答 ===
{models_text}

=== 评测要求 ===
1. 严格对照标准答案进行评分
2. 重点评估内容的准确性、完整性和语言本地化程度  
3. 提供详细的评分依据和理由
4. 客观公正，基于事实判断

请严格按照以下JSON格式输出，不要包含其他任何文字: {json.dumps(json_format, ensure_ascii=False)}
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
        
        for i, row in enumerate(data):
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
                prompt = build_objective_eval_prompt(query, standard_answer, current_answers, question_type)
            else:
                prompt = build_subjective_eval_prompt(query, current_answers, question_type, filename)
            
            try:
                print(f"🔄 开始评测第{i+1}题...")
                gem_raw = await query_gemini_model(prompt, google_api_key)
                result_json = parse_json_str(gem_raw)
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
            
            writer.writerow(row_data)
            
            # 更新进度
            if task_id in task_status:
                task_status[task_id].progress += 1
                task_status[task_id].current_step = f"已评测 {task_status[task_id].progress}/{task_status[task_id].total} 题"

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

@app.route('/get_uploaded_files', methods=['GET'])
@login_required
def get_uploaded_files():
    """获取已上传的文件列表"""
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        files = []
        
        if os.path.exists(upload_folder):
            for filename in os.listdir(upload_folder):
                if filename.endswith(('.xlsx', '.xls', '.csv')):
                    filepath = os.path.join(upload_folder, filename)
                    stat = os.stat(filepath)
                    
                    # 确保文件有提示词记录
                    db.create_file_prompt_if_not_exists(filename)
                    
                    # 获取提示词信息
                    prompt_info = db.get_file_prompt_info(filename)
                    has_custom_prompt = prompt_info is not None
                    
                    files.append({
                        'filename': filename,
                        'size': stat.st_size,
                        'upload_time': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        'size_formatted': f"{stat.st_size / 1024:.1f} KB" if stat.st_size < 1024*1024 else f"{stat.st_size / (1024*1024):.1f} MB",
                        'has_custom_prompt': has_custom_prompt,
                        'prompt_updated_at': prompt_info['updated_at'] if prompt_info else None
                    })
        
        # 按上传时间倒序排列
        files.sort(key=lambda x: x['upload_time'], reverse=True)
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        return jsonify({'error': f'获取文件列表失败: {str(e)}'}), 500

@app.route('/delete_file/<filename>', methods=['DELETE'])
@login_required
def delete_file(filename):
    """删除上传的文件"""
    try:
        filename = secure_filename(filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404
        
        os.remove(filepath)
        return jsonify({'success': True, 'message': f'文件 {filename} 已删除'})
    except Exception as e:
        return jsonify({'error': f'删除文件失败: {str(e)}'}), 500

@app.route('/download_uploaded_file/<filename>', methods=['GET'])
@login_required
def download_uploaded_file(filename):
    """下载上传的文件"""
    try:
        filename = secure_filename(filename)
        upload_folder = app.config['UPLOAD_FOLDER']
        return send_from_directory(upload_folder, filename, as_attachment=True)
    except Exception as e:
        return jsonify({'error': f'下载文件失败: {str(e)}'}), 500

@app.route('/check_file_exists/<filename>', methods=['GET'])
@login_required
def check_file_exists(filename):
    """检查文件是否已存在"""
    filename = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    exists = os.path.exists(filepath)
    return jsonify({'exists': exists, 'filename': filename})

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
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # 如果文件存在且不允许覆盖，返回提示
        if os.path.exists(filepath) and not overwrite:
            return jsonify({
                'error': 'file_exists',
                'message': f'文件 "{filename}" 已存在，是否要覆盖？',
                'filename': filename
            }), 409
        
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
            
            # 为新上传的文件创建默认提示词记录
            current_user = db.get_user_by_id(session['user_id'])
            created_by = current_user['username'] if current_user else 'system'
            db.create_file_prompt_if_not_exists(filename, created_by=created_by)
            
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

def analyze_existing_file(filename):
    """分析已存在的文件"""
    try:
        filename = secure_filename(filename)
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
    models = []
    for model_name, config in SUPPORTED_MODELS.items():
        # 先检查环境变量，再检查HTTP头部
        token = os.getenv(config["token_env"]) or request.headers.get(f'X-{model_name.replace("-", "-")}-Key')
        models.append({
            'name': model_name,
            'available': bool(token),
            'token_env': config["token_env"]
        })
    
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
    
    if not filename:
        return jsonify({'error': '缺少文件名'}), 400
    
    if not selected_models:
        return jsonify({'error': '请至少选择一个模型'}), 400
    
    if not GOOGLE_API_KEY:
        return jsonify({'error': '请配置GOOGLE_API_KEY环境变量'}), 400
    
    # 检查选中的模型是否可用
    for model_name in selected_models:
        if model_name not in SUPPORTED_MODELS:
            return jsonify({'error': f'不支持的模型: {model_name}'}), 400
        
        token_env = SUPPORTED_MODELS[model_name]["token_env"]
        if not os.getenv(token_env):
            return jsonify({'error': f'模型 {model_name} 缺少环境变量: {token_env}'}), 400
    
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
        
        # 在主线程中获取所有需要的数据
        headers_dict = dict(request.headers)
        google_api_key = GOOGLE_API_KEY or request.headers.get('X-Google-API-Key')
        data_list = df.to_dict('records')
        queries = [str(row.get("query", "")) for row in data_list]
        
        def task():
            try:
                # 第一步：获取模型答案
                model_results = run_async_task(get_multiple_model_answers, queries, selected_models, task_id, headers_dict)
                
                # 第二步：评测
                output_file = run_async_task(evaluate_models, data_list, mode, model_results, task_id, google_api_key, filename)
                
                task_status[task_id].status = "完成"
                task_status[task_id].result_file = os.path.basename(output_file)
                task_status[task_id].current_step = f"评测完成，结果已保存到 {os.path.basename(output_file)}"
                task_status[task_id].end_time = datetime.now()
                
                # 保存到历史记录
                try:
                    evaluation_data = {
                        'dataset_file': filename,
                        'models': selected_models,
                        'evaluation_mode': mode,
                        'start_time': task_status[task_id].start_time.isoformat(),
                        'end_time': task_status[task_id].end_time.isoformat() if task_status[task_id].end_time else None,
                        'question_count': len(data_list)
                    }
                    history_manager.save_evaluation_result(evaluation_data, output_file)
                except Exception as e:
                    print(f"保存历史记录失败: {e}")
                
            except Exception as e:
                task_status[task_id].status = "失败"
                task_status[task_id].error_message = str(e)
                print(f"评测任务失败: {e}")  # 添加日志
        
        # 在后台运行任务
        thread = threading.Thread(target=task)
        thread.start()
        
        return jsonify({'success': True, 'task_id': task_id})
        
    except Exception as e:
        return jsonify({'error': f'处理错误: {str(e)}'}), 400

@app.route('/task_status/<task_id>')
@login_required
def get_task_status(task_id):
    """获取任务状态"""
    if task_id not in task_status:
        return jsonify({'error': '任务不存在'}), 404
    
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
    """通过result_id下载历史记录结果文件"""
    try:
        # 获取数据库中的结果信息
        if db:
            result = db.get_result_by_id(result_id)
            if result and result.get('result_file'):
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
        if analytics:
            # 尝试从task_status获取时间数据
            evaluation_data = None
            for task_id, task in task_status.items():
                if (hasattr(task, 'result_file') and 
                    task.result_file == filename and
                    hasattr(task, 'start_time') and hasattr(task, 'end_time')):
                    evaluation_data = {
                        'start_time': task.start_time.isoformat() if task.start_time else None,
                        'end_time': task.end_time.isoformat() if task.end_time else None,
                        'question_count': len(df)
                    }
                    break
            
            # 如果没有找到时间数据，使用文件的创建和修改时间作为估算
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
                except Exception as e:
                    pass  # 静默处理文件时间获取错误
                    evaluation_data = {'question_count': len(df)}
            
            analysis_result = analytics.analyze_evaluation_results(
                result_file=filepath,
                evaluation_data=evaluation_data
            )
            
            if analysis_result.get('success'):
                advanced_stats = analysis_result['analysis']
        
        current_user = db.get_user_by_id(session['user_id'])
        return render_template('results.html', 
                             filename=filename,
                             columns=df.columns.tolist(),
                             data=df.to_dict('records'),
                             advanced_stats=advanced_stats,
                             current_user=current_user)
    except Exception as e:
        return jsonify({'error': f'读取结果文件错误: {str(e)}'}), 400


@app.route('/save_api_keys', methods=['POST'])
@login_required
def save_api_keys():
    """保存API密钥到本地.env文件"""
    try:
        data = request.get_json()
        
        # 获取API密钥
        google_key = data.get('google_api_key', '').strip()
        hkgai_v1_key = data.get('hkgai_v1_key', '').strip()
        hkgai_v2_key = data.get('hkgai_v2_key', '').strip()
        
        # 准备要保存的环境变量
        env_vars_to_save = {}
        
        if google_key:
            env_vars_to_save['GOOGLE_API_KEY'] = google_key
        if hkgai_v1_key:
            env_vars_to_save['ARK_API_KEY_HKGAI_V1'] = hkgai_v1_key
        if hkgai_v2_key:
            env_vars_to_save['ARK_API_KEY_HKGAI_V2'] = hkgai_v2_key
        
        if not env_vars_to_save:
            return jsonify({
                'success': False,
                'message': '没有提供任何API密钥'
            })
        
        # 保存到.env文件
        success = env_manager.save_env_vars(env_vars_to_save)
        
        if success:
            # API密钥已保存，无需额外配置（使用直接API调用）
            return jsonify({
                'success': True,
                'message': f'已成功保存{len(env_vars_to_save)}个API密钥到本地文件',
                'saved_keys': list(env_vars_to_save.keys())
            })
        else:
            return jsonify({
                'success': False,
                'message': '保存API密钥失败，请检查文件权限'
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
        if env_exists:
            env_vars = env_manager.load_env()
            api_keys = ['GOOGLE_API_KEY', 'ARK_API_KEY_HKGAI_V1', 'ARK_API_KEY_HKGAI_V2']
            saved_keys = [key for key in api_keys if key in env_vars and env_vars[key]]
        
        return jsonify({
            'env_file_path': env_path,
            'env_file_exists': env_exists,
            'saved_keys': saved_keys,
            'total_saved': len(saved_keys)
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
    """获取历史记录列表"""
    if not history_manager:
        return jsonify({'success': False, 'error': '历史管理功能未启用'}), 503
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        search = request.args.get('search', '')
        mode = request.args.get('mode', '')
        tags = request.args.get('tags', '')
        
        # 解析标签
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()] if tags else None
        
        # 计算偏移量
        offset = (page - 1) * limit
        
        # 获取历史记录
        history = history_manager.get_history_list(
            tags=tag_list,
            limit=limit,
            offset=offset
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
    """查看历史评测结果详情"""
    try:
        # 获取历史记录详情
        result_detail = history_manager.get_result_detail(result_id)
        if not result_detail:
            return jsonify({'error': '结果不存在'}), 404
        
        result = result_detail.get('result', {})
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

@app.route('/api/history/delete/<result_id>', methods=['DELETE'])
@login_required
def delete_history_result(result_id):
    """删除历史评测结果"""
    try:
        success = history_manager.delete_result(result_id)
        if success:
            return jsonify({'success': True, 'message': '删除成功'})
        else:
            return jsonify({'success': False, 'error': '删除失败'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update_score', methods=['POST'])
@login_required
def update_score():
    """修改评分"""
    try:
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
        
        # 验证评分范围
        if not isinstance(new_score, int) or new_score < 0 or new_score > 5:
            return jsonify({'success': False, 'error': '评分必须在0-5分之间'}), 400
        
        # 首先尝试更新数据库
        if db:
            try:
                # 根据文件名查找result_id
                result_id = db.get_result_id_by_filename(filename)
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
            except Exception as e:
                print(f"⚠️ 数据库更新异常: {e}")
        
        # 同时更新CSV文件以保持兼容性
        filepath = os.path.join(app.config['RESULTS_FOLDER'], filename)
        if os.path.exists(filepath):
            # 读取CSV文件
            df = pd.read_csv(filepath, encoding='utf-8-sig')
            
            # 验证行索引
            if row_index < 0 or row_index >= len(df):
                return jsonify({'success': False, 'error': '行索引超出范围'}), 400
            
            # 验证列名
            if score_column not in df.columns:
                return jsonify({'success': False, 'error': f'列 {score_column} 不存在'}), 400
            
            # 更新评分
            df.loc[row_index, score_column] = new_score
            
            # 如果有理由列，也更新理由
            reason_column = score_column.replace('评分', '理由')
            if reason_column in df.columns and reason:
                current_reason = df.loc[row_index, reason_column] or ''
                # 添加修改记录
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                modification_note = f"\n[{timestamp}] 手动修改为{new_score}分: {reason}"
                df.loc[row_index, reason_column] = current_reason + modification_note
            
            # 保存文件
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            print(f"✅ CSV文件评分已更新: {filename} 第{row_index+1}行 {score_column} -> {new_score}分")
        else:
            # 如果CSV文件不存在但数据库操作成功，仍然返回成功
            if db and result_id:
                print(f"⚠️ CSV文件不存在，但数据库更新成功")
            else:
                return jsonify({'success': False, 'error': '文件不存在且数据库中无记录'}), 404
        
        return jsonify({
            'success': True,
            'message': f'{model_name} 的评分已更新为 {new_score} 分'
        })
        
    except Exception as e:
        print(f"❌ 更新评分失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'更新失败: {str(e)}'}), 500

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
                    
                    for score in range(6):  # 0-5分
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
        filename = secure_filename(filename)
        
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
        filename = secure_filename(filename)
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


# 初始化默认管理员账户
try:
    if db:
        db.init_default_admin()
except Exception as e:
    print(f"⚠️ 初始化默认管理员失败: {e}")


if __name__ == '__main__':
    print("🚀 模型评测Web系统启动中...")
    print("📋 请确保设置以下环境变量:")
    print("   - GOOGLE_API_KEY: Gemini评测API密钥")
    print("   - ARK_API_KEY_HKGAI_V1: HKGAI-V1模型API密钥")
    print("   - ARK_API_KEY_HKGAI_V2: HKGAI-V2模型API密钥")
    print("🌐 访问地址: http://localhost:8080")
    app.run(debug=True, host='0.0.0.0', port=8080)
