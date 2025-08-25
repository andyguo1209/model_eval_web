import os
import json
import uuid
import asyncio
import aiohttp
import pandas as pd
import time
import re
import csv
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename
import google.generativeai as genai
from typing import Dict, Any, List, Optional
import threading
from utils.env_manager import env_manager

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
        "url": "https://chat.hkchat.app/goapi/v1/chat/stream",
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
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

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
        return json.loads(s)
    except json.JSONDecodeError:
        return {}



async def query_gemini_model(prompt: str, api_key: str = None) -> str:
    """查询Gemini模型"""
    def call_model():
        # 使用传入的API密钥或默认密钥
        if api_key:
            genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        resp = model.generate_content(prompt)
        return resp.text if resp and resp.text else ""
    
    return await asyncio.to_thread(call_model)

def build_subjective_eval_prompt(query: str, answers: Dict[str, str], question_type: str = "") -> str:
    """构建主观题评测提示"""
    type_context = f"问题类型: {question_type}\n" if question_type else ""
    
    models_text = ""
    for i, (model_name, answer) in enumerate(answers.items(), 1):
        models_text += f"模型{i}({model_name})回答: {answer}\n\n"
    
    model_keys = list(answers.keys())
    json_format = {f"模型{i+1}": {"评分": "0-5", "理由": "评分理由"} for i in range(len(model_keys))}
    
    return f"""
请对以下AI模型回答进行主观质量评分（0-5分，整数）。

{type_context}问题: {query}

{models_text}

评分标准:
- 5分: 回答优秀，逻辑清晰，内容丰富
- 4分: 回答良好，基本符合要求
- 3分: 回答一般，有一定价值
- 2分: 回答较差，价值有限
- 1分: 回答很差，几乎无价值
- 0分: 无回答或完全无关

只输出JSON格式，不要其他文字: {json.dumps(json_format, ensure_ascii=False)}
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
请对照标准答案为AI模型回答评分（0-5分，整数）。

{type_context}问题: {query}
标准答案: {standard_answer}

{models_text}

评分标准:
- 5分: 完全正确，表述清晰
- 4分: 基本正确，略有瑕疵
- 3分: 部分正确
- 2分: 大部分错误但有正确元素
- 1分: 完全错误但相关
- 0分: 完全错误或无关

只输出JSON格式: {json.dumps(json_format, ensure_ascii=False)}
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

async def evaluate_models(data: List[Dict], mode: str, model_results: Dict[str, List[str]], task_id: str, google_api_key: str = None) -> str:
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
                prompt = build_subjective_eval_prompt(query, current_answers, question_type)
            
            try:
                gem_raw = await query_gemini_model(prompt, google_api_key)
                result_json = parse_json_str(gem_raw)
            except Exception as e:
                print(f"评测第{i+1}题时出错: {e}")
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

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/upload_file', methods=['POST'])
def upload_file():
    """上传评测文件"""
    if 'file' not in request.files:
        return jsonify({'error': '没有选择文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    if file and file.filename.endswith(('.xlsx', '.xls', '.csv')):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
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

@app.route('/get_available_models', methods=['GET'])
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
        
        def task():
            try:
                # 从请求头获取API密钥
                headers_dict = dict(request.headers)
                
                # 第一步：获取模型答案
                model_results = run_async_task(get_multiple_model_answers, queries, selected_models, task_id, headers_dict)
                
                # 第二步：评测
                google_api_key = GOOGLE_API_KEY or request.headers.get('X-Google-API-Key')
                output_file = run_async_task(evaluate_models, data_list, mode, model_results, task_id, google_api_key)
                
                task_status[task_id].status = "完成"
                task_status[task_id].result_file = output_file
                task_status[task_id].current_step = f"评测完成，结果已保存到 {os.path.basename(output_file)}"
                
            except Exception as e:
                task_status[task_id].status = "失败"
                task_status[task_id].error_message = str(e)
        
        # 在后台运行任务
        thread = threading.Thread(target=task)
        thread.start()
        
        return jsonify({'success': True, 'task_id': task_id})
        
    except Exception as e:
        return jsonify({'error': f'处理错误: {str(e)}'}), 400

@app.route('/task_status/<task_id>')
def get_task_status(task_id):
    """获取任务状态"""
    if task_id not in task_status:
        return jsonify({'error': '任务不存在'}), 404
    
    task = task_status[task_id]
    elapsed_time = (datetime.now() - task.start_time).total_seconds()
    
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
def download_file(filename):
    """下载结果文件"""
    filepath = os.path.join(app.config['RESULTS_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        return jsonify({'error': '文件不存在'}), 404

@app.route('/view_results/<filename>')
def view_results(filename):
    """查看评测结果"""
    filepath = os.path.join(app.config['RESULTS_FOLDER'], filename)
    if not os.path.exists(filepath):
        return jsonify({'error': '文件不存在'}), 404
    
    try:
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        return render_template('results.html', 
                             filename=filename,
                             columns=df.columns.tolist(),
                             data=df.to_dict('records'))
    except Exception as e:
        return jsonify({'error': f'读取结果文件错误: {str(e)}'}), 400


@app.route('/save_api_keys', methods=['POST'])
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
            # 重新配置Google Generative AI（如果有Google密钥）
            if google_key:
                genai.configure(api_key=google_key)
            
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


if __name__ == '__main__':
    print("🚀 模型评测Web系统启动中...")
    print("📋 请确保设置以下环境变量:")
    print("   - GOOGLE_API_KEY: Gemini评测API密钥")
    print("   - ARK_API_KEY_HKGAI_V1: HKGAI-V1模型API密钥")
    print("   - ARK_API_KEY_HKGAI_V2: HKGAI-V2模型API密钥")
    print("🌐 访问地址: http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)
