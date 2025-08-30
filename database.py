"""
高级评测系统数据库模型
支持评测结果历史管理、人工标注、协作功能
"""

import sqlite3
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import os

DATABASE_PATH = 'evaluation_system.db'

class EvaluationDatabase:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.init_database()
    
    def _get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            
            # 1. 评测项目表
            db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    settings TEXT -- JSON格式存储项目配置
                )
            ''')
            
            # 2. 评测结果历史表
            db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS evaluation_results (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    name TEXT NOT NULL,
                    dataset_file TEXT NOT NULL,
                    dataset_hash TEXT, -- 数据集内容hash，用于版本管理
                    models TEXT NOT NULL, -- JSON格式存储参与评测的模型列表
                    result_file TEXT NOT NULL,
                    result_summary TEXT, -- JSON格式存储结果摘要统计
                    evaluation_mode TEXT, -- 'objective' or 'subjective'
                    status TEXT DEFAULT 'completed', -- 'running', 'completed', 'failed', 'archived'
                    tags TEXT, -- JSON格式存储标签列表
                    created_by TEXT, -- 创建者用户ID
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    archived_at TIMESTAMP,
                    metadata TEXT, -- JSON格式存储额外元数据
                    FOREIGN KEY (project_id) REFERENCES projects (id),
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
            ''')
            
            # 3. 人工标注表
            db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS annotations (
                    id TEXT PRIMARY KEY,
                    result_id TEXT NOT NULL,
                    question_index INTEGER NOT NULL,
                    question_text TEXT,
                    model_name TEXT NOT NULL,
                    model_answer TEXT,
                    
                    -- 标注维度
                    correctness_score INTEGER, -- 0-5分
                    relevance_score INTEGER, -- 0-5分
                    safety_score INTEGER, -- 0-5分
                    creativity_score INTEGER, -- 0-5分
                    logic_consistency BOOLEAN, -- 逻辑一致性
                    
                    -- 标注元信息
                    annotator TEXT NOT NULL, -- 标注员ID
                    annotation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    annotation_notes TEXT, -- 标注备注
                    confidence_level INTEGER, -- 标注信心程度 0-5
                    
                    -- 审核信息
                    reviewer TEXT, -- 审核员ID
                    review_status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
                    review_time TIMESTAMP,
                    review_notes TEXT,
                    
                    FOREIGN KEY (result_id) REFERENCES evaluation_results (id)
                )
            ''')
            
            # 4. 标注标准表
            db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS annotation_standards (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    dimension_name TEXT NOT NULL,
                    dimension_type TEXT NOT NULL, -- 'score', 'boolean', 'categorical'
                    description TEXT,
                    scale_definition TEXT, -- JSON格式存储评分标准定义
                    examples TEXT, -- JSON格式存储示例
                    weight REAL DEFAULT 1.0, -- 权重
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects (id)
                )
            ''')
            
            # 5. 对比分析表
            db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS comparison_analyses (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    result_ids TEXT NOT NULL, -- JSON格式存储参与对比的结果ID列表
                    analysis_type TEXT NOT NULL, -- 'model_comparison', 'time_trend', 'dataset_comparison'
                    analysis_config TEXT, -- JSON格式存储分析配置
                    analysis_result TEXT, -- JSON格式存储分析结果
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 6. 用户表（包含登录认证）
            db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name TEXT,
                    role TEXT DEFAULT 'annotator', -- 'admin', 'reviewer', 'annotator', 'viewer'
                    email TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP,
                    last_login TIMESTAMP,
                    preferences TEXT, -- JSON格式存储用户偏好设置
                    created_by TEXT
                )
            ''')
            
            # 7. 运行时任务管理表
            db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS running_tasks (
                    task_id TEXT PRIMARY KEY,
                    task_name TEXT NOT NULL,
                    status TEXT DEFAULT 'running', -- 'running', 'paused', 'completed', 'failed', 'cancelled'
                    
                    -- 任务配置
                    dataset_file TEXT NOT NULL,
                    dataset_filename TEXT NOT NULL,
                    evaluation_mode TEXT NOT NULL, -- 'objective' or 'subjective'
                    selected_models TEXT NOT NULL, -- JSON格式存储模型列表
                    
                    -- 进度信息
                    progress INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 0,
                    current_step TEXT DEFAULT '',
                    
                    -- 时间信息
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    paused_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    
                    -- 结果信息
                    result_file TEXT,
                    error_message TEXT,
                    
                    -- 元数据
                    metadata TEXT, -- JSON格式存储额外信息
                    created_by TEXT
                )
            ''')
            
            # 8. 系统配置表
            db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_configs (
                    id TEXT PRIMARY KEY,
                    config_key TEXT UNIQUE NOT NULL,
                    config_value TEXT,
                    config_type TEXT DEFAULT 'string', -- 'string', 'number', 'boolean', 'json'
                    description TEXT,
                    category TEXT DEFAULT 'general',
                    is_sensitive BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by TEXT DEFAULT 'system'
                )
            ''')
            
            # 9. 文件提示词管理表
            db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS file_prompts (
                    id TEXT PRIMARY KEY,
                    filename TEXT UNIQUE NOT NULL,
                    custom_prompt TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT DEFAULT 'system',
                    updated_by TEXT DEFAULT 'system'
                )
            ''')
            
            # 10. 文件上传记录表
            db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS uploaded_files (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    file_type TEXT, -- 'dataset', 'result', 'other'
                    mode TEXT, -- 'objective', 'subjective', 'unknown'
                    total_count INTEGER DEFAULT 0, -- 记录数量
                    uploaded_by TEXT NOT NULL, -- 上传者用户ID
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    metadata TEXT, -- JSON格式存储文件元数据
                    FOREIGN KEY (uploaded_by) REFERENCES users (id)
                )
            ''')
            
            # 11. 分享链接表
            db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS shared_links (
                    id TEXT PRIMARY KEY,
                    share_token TEXT UNIQUE NOT NULL, -- 分享令牌，用于生成公开链接
                    result_id TEXT NOT NULL, -- 关联的评测结果ID
                    share_type TEXT NOT NULL, -- 'public', 'user_specific'
                    shared_by TEXT NOT NULL, -- 分享者用户ID
                    shared_to TEXT, -- 被分享者用户ID（仅user_specific类型使用）
                    
                    -- 分享设置
                    title TEXT, -- 自定义分享标题
                    description TEXT, -- 分享描述
                    allow_download BOOLEAN DEFAULT 0, -- 是否允许下载原始数据
                    password_protected TEXT, -- 访问密码（可选）
                    
                    -- 时间控制
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP, -- 过期时间（NULL表示永不过期）
                    
                    -- 访问统计
                    view_count INTEGER DEFAULT 0, -- 访问次数
                    last_accessed TIMESTAMP, -- 最后访问时间
                    access_limit INTEGER DEFAULT 0, -- 访问次数限制（0表示无限制）
                    
                    -- 状态管理
                    is_active BOOLEAN DEFAULT 1, -- 是否激活
                    revoked_at TIMESTAMP, -- 撤销时间
                    revoked_by TEXT, -- 撤销者用户ID
                    
                    FOREIGN KEY (result_id) REFERENCES evaluation_results (id),
                    FOREIGN KEY (shared_by) REFERENCES users (id),
                    FOREIGN KEY (shared_to) REFERENCES users (id),
                    FOREIGN KEY (revoked_by) REFERENCES users (id)
                )
            ''')
            
            # 12. 分享访问记录表
            db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS shared_access_logs (
                    id TEXT PRIMARY KEY,
                    share_id TEXT NOT NULL, -- 分享链接ID
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT, -- 访问者IP
                    user_agent TEXT, -- 浏览器信息
                    user_id TEXT, -- 如果是登录用户访问
                    
                    FOREIGN KEY (share_id) REFERENCES shared_links (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # 执行数据库迁移
            self._migrate_database(db_cursor)
            
            # 创建索引提高查询性能
            self._create_indexes(db_cursor)
            
            conn.commit()
    
    def _migrate_database(self, cursor):
        """执行数据库迁移，安全地添加新字段"""
        print("🔄 检查数据库迁移...")
        
        # 检查并添加 evaluation_results 表的 created_by 字段
        try:
            cursor.execute("PRAGMA table_info(evaluation_results)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'created_by' not in columns:
                print("➕ 添加 evaluation_results.created_by 字段...")
                cursor.execute("ALTER TABLE evaluation_results ADD COLUMN created_by TEXT")
                
                # 为现有记录设置默认值
                cursor.execute("UPDATE evaluation_results SET created_by = 'legacy' WHERE created_by IS NULL")
                print("✅ evaluation_results.created_by 字段添加完成")
        except Exception as e:
            print(f"⚠️ 迁移 evaluation_results 表时出错: {e}")
        
        # 检查并添加 running_tasks 表的 created_by 字段
        try:
            cursor.execute("PRAGMA table_info(running_tasks)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'created_by' not in columns:
                print("➕ 添加 running_tasks.created_by 字段...")
                cursor.execute("ALTER TABLE running_tasks ADD COLUMN created_by TEXT")
                
                # 为现有记录设置默认值
                cursor.execute("UPDATE running_tasks SET created_by = 'legacy' WHERE created_by IS NULL")
                print("✅ running_tasks.created_by 字段添加完成")
        except Exception as e:
            print(f"⚠️ 迁移 running_tasks 表时出错: {e}")
        
        print("✅ 数据库迁移完成")
    
    def _create_indexes(self, cursor):
        """创建索引，处理可能的错误"""
        indexes = [
            ('idx_results_project', 'evaluation_results', 'project_id'),
            ('idx_results_created', 'evaluation_results', 'created_at'),
            ('idx_results_created_by', 'evaluation_results', 'created_by'),
            ('idx_annotations_result', 'annotations', 'result_id'),
            ('idx_annotations_annotator', 'annotations', 'annotator'),
            ('idx_running_tasks_status', 'running_tasks', 'status'),
            ('idx_running_tasks_created', 'running_tasks', 'created_at'),
            ('idx_running_tasks_created_by', 'running_tasks', 'created_by'),
            ('idx_uploaded_files_user', 'uploaded_files', 'uploaded_by'),
            ('idx_uploaded_files_active', 'uploaded_files', 'is_active'),
            ('idx_shared_links_token', 'shared_links', 'share_token'),
            ('idx_shared_links_result', 'shared_links', 'result_id'),
            ('idx_shared_links_shared_by', 'shared_links', 'shared_by'),
            ('idx_shared_links_active', 'shared_links', 'is_active'),
            ('idx_shared_access_logs_share', 'shared_access_logs', 'share_id'),
        ]
        
        for index_name, table_name, column_name in indexes:
            try:
                cursor.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})')
            except Exception as e:
                print(f"⚠️ 创建索引 {index_name} 失败: {e}")
        
        # 复合索引
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_uploaded_files_type ON uploaded_files(file_type, uploaded_by)')
        except Exception as e:
            print(f"⚠️ 创建复合索引 idx_uploaded_files_type 失败: {e}")
        
        print("✅ 索引创建完成")

    def create_project(self, name: str, description: str = "", created_by: str = "system") -> str:
        """创建新项目"""
        project_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            db_cursor.execute('''
                INSERT INTO projects (id, name, description, created_by)
                VALUES (?, ?, ?, ?)
            ''', (project_id, name, description, created_by))
            conn.commit()
        return project_id
    
    def save_evaluation_result(self, 
                             project_id: str,
                             name: str,
                             dataset_file: str,
                             models: List[str],
                             result_file: str,
                             evaluation_mode: str,
                             result_summary: Dict = None,
                             tags: List[str] = None,
                             created_by: str = 'system',
                             metadata: Dict = None) -> str:
        """保存评测结果"""
        result_id = str(uuid.uuid4())
        
        # 计算数据集hash用于版本管理
        dataset_hash = self._calculate_file_hash(dataset_file)
        
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            db_cursor.execute('''
                INSERT INTO evaluation_results 
                (id, project_id, name, dataset_file, dataset_hash, models, result_file, 
                 result_summary, evaluation_mode, tags, created_by, completed_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                result_id, project_id, name, dataset_file, dataset_hash,
                json.dumps(models), result_file, 
                json.dumps(result_summary or {}),
                evaluation_mode,
                json.dumps(tags or []),
                created_by,
                datetime.now().isoformat(),
                json.dumps(metadata or {})
            ))
            conn.commit()
        return result_id
    
    def get_evaluation_history(self, 
                             project_id: str = None,
                             limit: int = 50,
                             offset: int = 0,
                             status: str = None,
                             tags: List[str] = None,
                             created_by: str = None,
                             include_all_users: bool = False) -> List[Dict]:
        """获取评测历史记录"""
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            
            query = '''
                SELECT id, project_id, name, dataset_file, models, result_file,
                       result_summary, evaluation_mode, status, tags, created_by,
                       created_at, completed_at
                FROM evaluation_results
                WHERE status != 'deleted'
            '''
            params = []
            
            if project_id:
                query += ' AND project_id = ?'
                params.append(project_id)
            
            if status:
                query += ' AND status = ?'
                params.append(status)
                
            # 用户权限过滤
            if not include_all_users and created_by:
                query += ' AND created_by = ?'
                params.append(created_by)
            
            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            db_cursor.execute(query, params)
            rows = db_cursor.fetchall()
            
            results = []
            for row in rows:
                result = {
                    'id': row[0],
                    'project_id': row[1],
                    'name': row[2],
                    'dataset_file': row[3],
                    'models': json.loads(row[4]) if row[4] else [],
                    'result_file': row[5],
                    'result_summary': json.loads(row[6]) if row[6] else {},
                    'evaluation_mode': row[7],
                    'status': row[8],
                    'tags': json.loads(row[9]) if row[9] else [],
                    'created_by': row[10],
                    'created_at': row[11],
                    'completed_at': row[12]
                }
                
                # 标签过滤
                if tags:
                    result_tags = set(result['tags'])
                    if not any(tag in result_tags for tag in tags):
                        continue
                
                results.append(result)
            
            return results
    
    def save_annotation(self,
                       result_id: str,
                       question_index: int,
                       question_text: str,
                       model_name: str,
                       model_answer: str,
                       annotator: str,
                       **annotation_data) -> str:
        """保存人工标注"""
        annotation_id = str(uuid.uuid4())
        
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            db_cursor.execute('''
                INSERT INTO annotations 
                (id, result_id, question_index, question_text, model_name, model_answer,
                 correctness_score, relevance_score, safety_score, creativity_score,
                 logic_consistency, annotator, annotation_notes, confidence_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                annotation_id, result_id, question_index, question_text, 
                model_name, model_answer,
                annotation_data.get('correctness_score'),
                annotation_data.get('relevance_score'),
                annotation_data.get('safety_score'),
                annotation_data.get('creativity_score'),
                annotation_data.get('logic_consistency'),
                annotator,
                annotation_data.get('annotation_notes', ''),
                annotation_data.get('confidence_level', 3)
            ))
            conn.commit()
        return annotation_id
    
    def get_annotations(self, result_id: str) -> List[Dict]:
        """获取评测结果的所有标注"""
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            db_cursor.execute('''
                SELECT * FROM annotations WHERE result_id = ?
                ORDER BY question_index, model_name
            ''', (result_id,))
            
            rows = db_cursor.fetchall()
            columns = [description[0] for description in db_cursor.description]
            
            return [dict(zip(columns, row)) for row in rows]
    
    def get_result_id_by_filename(self, filename: str) -> Optional[str]:
        """根据结果文件名获取result_id，支持多目录查找和路径修复"""
        import os
        
        # 处理文件名，去除可能的路径前缀
        clean_filename = filename
        if filename.startswith('results_history/'):
            clean_filename = filename.replace('results_history/', '', 1)
            print(f"🔍 [数据库] 检测到history路径前缀，清理后: {clean_filename}")
        elif filename.startswith('results/'):
            clean_filename = filename.replace('results/', '', 1)
            print(f"🔍 [数据库] 检测到results路径前缀，清理后: {clean_filename}")
        
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            
            # 首先尝试直接匹配（使用原始文件名和清理后的文件名）
            search_patterns = [filename, clean_filename, f'%/{clean_filename}', f'%{clean_filename}']
            
            for pattern in search_patterns:
                db_cursor.execute('''
                    SELECT id, result_file FROM evaluation_results 
                    WHERE result_file = ? OR result_file LIKE ?
                ''', (pattern, f'%/{pattern}'))
                
                result = db_cursor.fetchone()
                if result:
                    result_id, stored_path = result
                    print(f"🔍 [数据库] 找到匹配记录: {result_id}, 存储路径: {stored_path}")
                    return result_id  # 找到记录就直接返回，不再检查文件是否存在
            
            # 如果直接匹配失败，尝试通过文件名模糊匹配查找可能的记录
            # 处理从 results/ 目录访问但数据库记录在 results_history/ 的情况
            base_filename = clean_filename.replace('.csv', '')
            
            # 尝试通过时间戳匹配 - evaluation_result_YYYYMMDD_HHMMSS.csv 格式
            if base_filename.startswith('evaluation_result_'):
                timestamp_part = base_filename.replace('evaluation_result_', '')
                print(f"🔍 [数据库] 尝试通过时间戳匹配: {timestamp_part}")
                
                db_cursor.execute('''
                    SELECT id, result_file FROM evaluation_results 
                    WHERE result_file LIKE ? OR result_file LIKE ?
                    ORDER BY created_at DESC
                ''', (f'%{timestamp_part}%', f'%{clean_filename}%'))
                
                results = db_cursor.fetchall()
                if results:
                    # 优先选择最近的记录
                    result_id, stored_path = results[0]
                    print(f"✅ [数据库] 通过时间戳匹配找到记录: {result_id}, 路径: {stored_path}")
                    return result_id
            
            # 如果还是找不到，尝试通过数据集名称匹配
            print(f"🔍 [数据库] 尝试通过数据集名称模糊匹配...")
            db_cursor.execute('''
                SELECT id, result_file, dataset_file FROM evaluation_results 
                WHERE dataset_file LIKE ? 
                ORDER BY created_at DESC
                LIMIT 10
            ''', (f'%{base_filename.split("_")[0]}%',))
            
            fuzzy_results = db_cursor.fetchall()
            if fuzzy_results:
                print(f"🔍 [数据库] 找到 {len(fuzzy_results)} 个可能的匹配记录")
                for result_id, stored_path, dataset_file in fuzzy_results:
                    print(f"   - {result_id}: {dataset_file} -> {stored_path}")
                
                # 返回最近的一个
                result_id = fuzzy_results[0][0]
                print(f"✅ [数据库] 选择最近的记录: {result_id}")
                return result_id
            
            print(f"❌ [数据库] 未找到文件 {clean_filename} (原始: {filename}) 对应的数据库记录")
            return None
    
    def get_result_by_id(self, result_id: str) -> Optional[Dict]:
        """根据result_id获取评测结果详情"""
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            db_cursor.execute('''
                SELECT * FROM evaluation_results WHERE id = ?
            ''', (result_id,))
            
            result = db_cursor.fetchone()
            if result:
                columns = [description[0] for description in db_cursor.description]
                return dict(zip(columns, result))
            return None
    
    def update_annotation_score(self, 
                               result_id: str,
                               question_index: int,
                               model_name: str,
                               score_type: str,
                               new_score: int,
                               reason: str = '',
                               annotator: str = 'manual_edit') -> bool:
        """更新标注评分"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                db_cursor = conn.cursor()
                
                # 首先检查是否已存在该记录
                db_cursor.execute('''
                    SELECT id FROM annotations 
                    WHERE result_id = ? AND question_index = ? AND model_name = ?
                ''', (result_id, question_index, model_name))
                
                existing = db_cursor.fetchone()
                
                if existing:
                    # 更新现有记录
                    update_field = f"{score_type}_score"
                    db_cursor.execute(f'''
                        UPDATE annotations 
                        SET {update_field} = ?, 
                            annotation_notes = COALESCE(annotation_notes, '') || ?, 
                            annotation_time = CURRENT_TIMESTAMP,
                            annotator = ?
                        WHERE id = ?
                    ''', (new_score, f'\n[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 手动修改{score_type}评分为{new_score}分: {reason}', annotator, existing[0]))
                else:
                    # 创建新记录
                    annotation_id = str(uuid.uuid4())
                    score_data = {
                        'correctness_score': new_score if score_type == 'correctness' else None,
                        'relevance_score': new_score if score_type == 'relevance' else None,
                        'safety_score': new_score if score_type == 'safety' else None,
                        'creativity_score': new_score if score_type == 'creativity' else None,
                        'annotation_notes': f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 手动创建{score_type}评分: {new_score}分 - {reason}'
                    }
                    
                    db_cursor.execute('''
                        INSERT INTO annotations 
                        (id, result_id, question_index, model_name, 
                         correctness_score, relevance_score, safety_score, creativity_score,
                         annotator, annotation_notes, confidence_level)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        annotation_id, result_id, question_index, model_name,
                        score_data['correctness_score'], score_data['relevance_score'], 
                        score_data['safety_score'], score_data['creativity_score'],
                        annotator, score_data['annotation_notes'], 3
                    ))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"更新评分失败: {e}")
            return False
    
    def archive_old_results(self, days_threshold: int = 90) -> int:
        """归档旧的评测结果"""
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            db_cursor.execute('''
                UPDATE evaluation_results 
                SET status = 'archived', archived_at = ?
                WHERE created_at < ? AND status = 'completed'
            ''', (datetime.now().isoformat(), cutoff_date.isoformat()))
            
            archived_count = db_cursor.rowcount
            conn.commit()
            
        return archived_count
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件hash"""
        import hashlib
        if not os.path.exists(file_path):
            return ""
        
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def get_statistics(self) -> Dict:
        """获取系统统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            
            stats = {}
            
            # 总评测次数
            db_cursor.execute('SELECT COUNT(*) FROM evaluation_results')
            stats['total_evaluations'] = db_cursor.fetchone()[0]
            
            # 总标注数
            db_cursor.execute('SELECT COUNT(*) FROM annotations')
            stats['total_annotations'] = db_cursor.fetchone()[0]
            
            # 活跃项目数
            db_cursor.execute('SELECT COUNT(*) FROM projects WHERE status = "active"')
            stats['active_projects'] = db_cursor.fetchone()[0]
            
            # 最近7天的评测数
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            db_cursor.execute(
                'SELECT COUNT(*) FROM evaluation_results WHERE created_at > ?',
                (week_ago,)
            )
            stats['recent_evaluations'] = db_cursor.fetchone()[0]
            
            return stats
    
    # ===== 用户管理方法 =====
    def create_user(self, username: str, password: str, role: str = 'annotator', 
                   display_name: str = None, email: str = None, created_by: str = 'system') -> str:
        """创建新用户"""
        import hashlib
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        display_name = display_name or username
        
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            try:
                db_cursor.execute('''
                    INSERT INTO users (id, username, password_hash, display_name, role, email, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, username, password_hash, display_name, role, email, created_by))
                conn.commit()
                return user_id
            except sqlite3.IntegrityError:
                raise ValueError(f"用户名 '{username}' 已存在")
    
    def verify_user(self, username: str, password: str) -> Dict:
        """验证用户登录"""
        import hashlib
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            db_cursor.execute('''
                SELECT id, username, display_name, role, email, is_active
                FROM users 
                WHERE username = ? AND password_hash = ? AND is_active = 1
            ''', (username, password_hash))
            
            result = db_cursor.fetchone()
            if result:
                # 更新最后登录时间
                db_cursor.execute('''
                    UPDATE users SET last_login = CURRENT_TIMESTAMP, last_active = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (result[0],))
                conn.commit()
                
                return {
                    'id': result[0],
                    'username': result[1],
                    'display_name': result[2],
                    'role': result[3],
                    'email': result[4],
                    'is_active': result[5]
                }
            return None
    
    def get_user_by_id(self, user_id: str) -> Dict:
        """根据ID获取用户信息"""
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            db_cursor.execute('''
                SELECT id, username, display_name, role, email, is_active, created_at, last_login
                FROM users 
                WHERE id = ?
            ''', (user_id,))
            
            result = db_cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'username': result[1],
                    'display_name': result[2],
                    'role': result[3],
                    'email': result[4],
                    'is_active': result[5],
                    'created_at': result[6],
                    'last_login': result[7]
                }
            return None
    
    def list_users(self, role: str = None) -> List[Dict]:
        """获取用户列表"""
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            if role:
                db_cursor.execute('''
                    SELECT id, username, display_name, role, email, is_active, created_at, last_login
                    FROM users 
                    WHERE role = ?
                    ORDER BY created_at DESC
                ''', (role,))
            else:
                db_cursor.execute('''
                    SELECT id, username, display_name, role, email, is_active, created_at, last_login
                    FROM users 
                    ORDER BY created_at DESC
                ''')
            
            results = db_cursor.fetchall()
            return [{
                'id': row[0],
                'username': row[1],
                'display_name': row[2],
                'role': row[3],
                'email': row[4],
                'is_active': row[5],
                'created_at': row[6],
                'last_login': row[7]
            } for row in results]
    
    def update_user(self, user_id: str, **kwargs) -> bool:
        """更新用户信息"""
        allowed_fields = ['display_name', 'role', 'email', 'is_active']
        updates = []
        values = []
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = ?")
                values.append(value)
        
        if not updates:
            return False
        
        values.append(user_id)
        
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            db_cursor.execute(f'''
                UPDATE users SET {', '.join(updates)}, last_active = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', values)
            conn.commit()
            return db_cursor.rowcount > 0
    
    def change_password(self, user_id: str, new_password: str) -> bool:
        """修改用户密码"""
        import hashlib
        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            db_cursor.execute('''
                UPDATE users SET password_hash = ?, last_active = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (password_hash, user_id))
            conn.commit()
            return db_cursor.rowcount > 0
    
    def delete_user(self, user_id: str) -> bool:
        """删除用户（软删除，设置为非活跃）"""
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            db_cursor.execute('''
                UPDATE users SET is_active = 0
                WHERE id = ?
            ''', (user_id,))
            conn.commit()
            return db_cursor.rowcount > 0
    
    def init_default_admin(self, username: str = 'admin', password: str = 'admin123'):
        """初始化默认管理员账户"""
        try:
            existing_admin = None
            with sqlite3.connect(self.db_path) as conn:
                db_cursor = conn.cursor()
                db_cursor.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
                admin_count = db_cursor.fetchone()[0]
                
                if admin_count == 0:
                    admin_id = self.create_user(
                        username=username,
                        password=password,
                        role='admin',
                        display_name='系统管理员',
                        email='admin@system.local',
                        created_by='system'
                    )
                    print(f"✅ 创建默认管理员账户: {username} / {password}")
                    return admin_id
                else:
                    print(f"ℹ️ 管理员账户已存在，跳过创建")
                    return None
        except Exception as e:
            print(f"❌ 创建默认管理员失败: {e}")
            return None
    
    # ========== 系统配置管理方法 ==========
    
    def get_system_config(self, config_key: str, default_value: str = None) -> str:
        """获取系统配置值"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT config_value FROM system_configs WHERE config_key = ?', (config_key,))
            result = cursor.fetchone()
            return result[0] if result else default_value
    
    def set_system_config(self, config_key: str, config_value: str, config_type: str = 'string', 
                         description: str = '', category: str = 'general', is_sensitive: bool = False,
                         updated_by: str = 'system') -> bool:
        """设置系统配置"""
        config_id = f"config_{config_key}"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO system_configs 
                (id, config_key, config_value, config_type, description, category, is_sensitive, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                config_id, config_key, config_value, config_type, 
                description, category, is_sensitive, datetime.now().isoformat(), updated_by
            ))
            conn.commit()
            return True
    
    def get_all_system_configs(self, category: str = None) -> List[Dict]:
        """获取所有系统配置"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute('''
                    SELECT config_key, config_value, config_type, description, category, is_sensitive, 
                           created_at, updated_at, updated_by
                    FROM system_configs WHERE category = ? ORDER BY config_key
                ''', (category,))
            else:
                cursor.execute('''
                    SELECT config_key, config_value, config_type, description, category, is_sensitive,
                           created_at, updated_at, updated_by
                    FROM system_configs ORDER BY category, config_key
                ''')
            
            rows = cursor.fetchall()
            return [
                {
                    'config_key': row[0],
                    'config_value': row[1],
                    'config_type': row[2],
                    'description': row[3],
                    'category': row[4],
                    'is_sensitive': bool(row[5]),
                    'created_at': row[6],
                    'updated_at': row[7],
                    'updated_by': row[8]
                }
                for row in rows
            ]
    
    def delete_system_config(self, config_key: str) -> bool:
        """删除系统配置"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM system_configs WHERE config_key = ?', (config_key,))
            conn.commit()
            return cursor.rowcount > 0
    
    # ========== 评分标准管理方法 (已废弃) ==========
    # 注意: 以下方法已废弃，系统已简化为只使用文件提示词功能
    
    def create_scoring_criteria(self, name: str = None, description: str = None, criteria_type: str = None,
                              criteria_config: Dict = None, dataset_pattern: str = None,
                              is_default: bool = False, created_by: str = 'system') -> str:
        """创建评分标准 - 已废弃，请使用文件提示词功能"""
        print("⚠️ [废弃警告] create_scoring_criteria方法已废弃，请使用文件提示词功能")
        return None
    
    def get_scoring_criteria(self, criteria_id: str) -> Optional[Dict]:
        """获取指定评分标准 - 已废弃，请使用文件提示词功能"""
        print("⚠️ [废弃警告] get_scoring_criteria方法已废弃，请使用文件提示词功能")
        return None
    
    def get_all_scoring_criteria(self, criteria_type: str = None, active_only: bool = True) -> List[Dict]:
        """获取所有评分标准 - 已废弃，请使用文件提示词功能"""
        print("⚠️ [废弃警告] get_all_scoring_criteria方法已废弃，请使用文件提示词功能")
        return []
    
    def update_scoring_criteria(self, criteria_id: str, **kwargs) -> bool:
        """更新评分标准 - 已废弃，请使用文件提示词功能"""
        print("⚠️ [废弃警告] update_scoring_criteria方法已废弃，请使用文件提示词功能")
        return False
    
    def delete_scoring_criteria(self, criteria_id: str) -> bool:
        """删除评分标准 - 已废弃，请使用文件提示词功能"""
        print("⚠️ [废弃警告] delete_scoring_criteria方法已废弃，请使用文件提示词功能")
        return False
    
    def get_default_scoring_criteria(self, criteria_type: str) -> Optional[Dict]:
        """获取默认评分标准 - 已废弃，请使用文件提示词功能"""
        print("⚠️ [废弃警告] get_default_scoring_criteria方法已废弃，请使用文件提示词功能")
        return None
    # ========== 文件提示词管理方法 ==========
    
    def get_file_prompt(self, filename: str) -> Optional[str]:
        """获取文件的自定义提示词"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT custom_prompt FROM file_prompts WHERE filename = ?', (filename,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def set_file_prompt(self, filename: str, custom_prompt: str, updated_by: str = 'system') -> bool:
        """设置文件的自定义提示词"""
        prompt_id = f"prompt_{filename}_{int(datetime.now().timestamp())}"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO file_prompts 
                (id, filename, custom_prompt, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (prompt_id, filename, custom_prompt, datetime.now().isoformat(), updated_by))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_file_prompt_info(self, filename: str) -> Optional[Dict]:
        """获取文件提示词的完整信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT filename, custom_prompt, created_at, updated_at, created_by, updated_by
                FROM file_prompts WHERE filename = ?
            ''', (filename,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'filename': row[0],
                    'custom_prompt': row[1],
                    'created_at': row[2],
                    'updated_at': row[3],
                    'created_by': row[4],
                    'updated_by': row[5]
                }
            return None
    
    def create_file_prompt_if_not_exists(self, filename: str, default_prompt: str = None, created_by: str = 'system') -> bool:
        """如果文件提示词不存在则创建默认的"""
        if self.get_file_prompt(filename) is None:
            if default_prompt is None:
                # 尝试根据文件内容判断是否为客观题
                is_objective = self._detect_objective_questions(filename)
                
                if is_objective:
                    # 客观题默认提示词
                    default_prompt = """你是一位专业的大模型测评工程师，请根据以下要求对模型的回答进行客观、公正的评测：

1. **评分标准**

   * 如果模型回答与参考答案一致，给 1 分；
   * 如果模型回答与参考答案不一致，给 0 分。

2. **评测要求**

   * 必须明确给出分数（只能是 0 或 1）；
   * 必须提供合理、简洁、逻辑自洽的理由；
   * 理由必须基于答案是否与参考答案一致，而不是主观评价。

3. **示例**

* 示例 1：
  题目：北京是中国的首都吗？
  参考答案：是
  模型回答：是
  评测结果：评分 1，理由：模型回答与参考答案一致，正确指出北京是中国的首都。

* 示例 2：
  题目：2+2 等于几？
  参考答案：4
  模型回答：5
  评测结果：评分 0，理由：模型回答与参考答案不符，参考答案是 4，但模型回答为 5，因此错误。

* 示例 3：
  题目：美国总统是谁？（截至2025年8月）
  参考答案：乔·拜登
  模型回答：特朗普
  评测结果：评分 0，理由：参考答案是乔·拜登，但模型回答为特朗普，与事实不符。"""
                else:
                    # 主观题或其他类型的通用指导提示词
                    default_prompt = """请为此文件设置自定义的评测提示词。

⚠️ 重要提示：
- 系统不再提供默认的评分标准
- 您需要根据具体的评测需求自定义评分标准和范围
- 评分范围可以是 0-1分、0-5分、0-10分等，完全由您决定
- 请确保评测提示词包含清晰的评分标准和评测要求

📋 建议的提示词结构：
1. 角色定义：明确评测者的身份和任务
2. 评分标准：定义每个分数对应的质量水平
3. 评测维度：列出需要考虑的评测角度
4. 特殊要求：任何特定的评测规则或注意事项

请在管理后台编辑此提示词以开始评测。"""
            
            prompt_id = f"prompt_{filename}_{int(datetime.now().timestamp())}"
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO file_prompts 
                    (id, filename, custom_prompt, created_by, updated_by)
                    VALUES (?, ?, ?, ?, ?)
                ''', (prompt_id, filename, default_prompt, created_by, created_by))
                conn.commit()
                return cursor.rowcount > 0
        return False
    
    def _detect_objective_questions(self, filename: str) -> bool:
        """检测文件是否包含客观题（通过检查是否有标准答案列）"""
        try:
            import pandas as pd
            import os
            
            # 构建可能的文件路径
            possible_paths = [
                filename,
                f"uploads/{filename}",
                f"results/{filename}",
                f"data/{filename}"
            ]
            
            filepath = None
            for path in possible_paths:
                if os.path.exists(path):
                    filepath = path
                    break
            
            if not filepath:
                return False
                
            # 读取文件的列名
            df = pd.read_csv(filepath, nrows=0)  # 只读取列名，不读取数据
            columns = [col.lower() for col in df.columns]
            
            # 检查是否包含标准答案相关的列名
            objective_indicators = [
                '标准答案', '参考答案', '正确答案', '答案',
                'standard_answer', 'reference_answer', 'correct_answer', 'answer',
                '标准', '参考', '正确'
            ]
            
            for indicator in objective_indicators:
                for col in columns:
                    if indicator.lower() in col:
                        return True
                        
            return False
            
        except Exception as e:
            print(f"⚠️ [检测客观题] 检测失败: {e}")
            # 如果检测失败，默认返回False（使用通用提示词）
            return False
    
    def delete_file_prompt(self, filename: str) -> bool:
        """删除文件的提示词记录"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM file_prompts WHERE filename = ?', (filename,))
            conn.commit()
            return cursor.rowcount > 0
    
    def list_all_file_prompts(self) -> List[Dict]:
        """获取所有文件提示词列表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT filename, custom_prompt, created_at, updated_at, created_by, updated_by
                FROM file_prompts ORDER BY updated_at DESC
            ''')
            
            rows = cursor.fetchall()
            return [
                {
                    'filename': row[0],
                    'custom_prompt': row[1],
                    'created_at': row[2],
                    'updated_at': row[3],
                    'created_by': row[4],
                    'updated_by': row[5]
                }
                for row in rows
            ]
    
    # ========== 运行时任务管理方法 ==========
    
    def create_running_task(self, task_id: str, task_name: str, dataset_file: str, 
                           dataset_filename: str, evaluation_mode: str, selected_models: List[str],
                           total: int, created_by: str = 'system') -> bool:
        """创建运行时任务记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO running_tasks 
                    (task_id, task_name, dataset_file, dataset_filename, evaluation_mode, 
                     selected_models, total, started_at, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task_id, task_name, dataset_file, dataset_filename, evaluation_mode,
                    json.dumps(selected_models), total, datetime.now().isoformat(), created_by
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"创建运行时任务失败: {e}")
            return False
    
    def update_task_progress(self, task_id: str, progress: int, current_step: str = '') -> bool:
        """更新任务进度"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE running_tasks 
                    SET progress = ?, current_step = ?
                    WHERE task_id = ?
                ''', (progress, current_step, task_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"更新任务进度失败: {e}")
            return False
    
    def update_task_status(self, task_id: str, status: str, **kwargs) -> bool:
        """更新任务状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 构建更新字段
                update_fields = ['status = ?']
                values = [status]
                
                # 根据状态添加时间戳
                if status == 'paused':
                    update_fields.append('paused_at = ?')
                    values.append(datetime.now().isoformat())
                elif status == 'completed':
                    update_fields.append('completed_at = ?')
                    values.append(datetime.now().isoformat())
                    if 'result_file' in kwargs:
                        update_fields.append('result_file = ?')
                        values.append(kwargs['result_file'])
                elif status == 'failed':
                    if 'error_message' in kwargs:
                        update_fields.append('error_message = ?')
                        values.append(kwargs['error_message'])
                
                values.append(task_id)
                
                cursor.execute(f'''
                    UPDATE running_tasks 
                    SET {', '.join(update_fields)}
                    WHERE task_id = ?
                ''', values)
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"更新任务状态失败: {e}")
            return False
    
    def update_evaluation_result_name(self, result_id: str, new_name: str) -> bool:
        """更新评测结果名称"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE evaluation_results 
                    SET name = ?
                    WHERE id = ?
                ''', (new_name, result_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"更新结果名称失败: {e}")
            return False
    
    def get_running_task(self, task_id: str) -> Optional[Dict]:
        """获取运行时任务信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM running_tasks WHERE task_id = ?
                ''', (task_id,))
                
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    task_data = dict(zip(columns, row))
                    # 解析JSON字段
                    if task_data.get('selected_models'):
                        task_data['selected_models'] = json.loads(task_data['selected_models'])
                    if task_data.get('metadata'):
                        task_data['metadata'] = json.loads(task_data['metadata'])
                    return task_data
                return None
        except Exception as e:
            print(f"获取运行时任务失败: {e}")
            return None
    
    def get_running_tasks(self, status: str = None, created_by: str = None) -> List[Dict]:
        """获取运行时任务列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = 'SELECT * FROM running_tasks'
                params = []
                conditions = []
                
                if status:
                    conditions.append('status = ?')
                    params.append(status)
                
                if created_by:
                    conditions.append('created_by = ?')
                    params.append(created_by)
                
                if conditions:
                    query += ' WHERE ' + ' AND '.join(conditions)
                
                query += ' ORDER BY created_at DESC'
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                columns = [description[0] for description in cursor.description]
                tasks = []
                for row in rows:
                    task_data = dict(zip(columns, row))
                    # 解析JSON字段
                    if task_data.get('selected_models'):
                        task_data['selected_models'] = json.loads(task_data['selected_models'])
                    if task_data.get('metadata'):
                        task_data['metadata'] = json.loads(task_data['metadata'])
                    tasks.append(task_data)
                
                return tasks
        except Exception as e:
            print(f"获取运行时任务列表失败: {e}")
            return []
    
    # ========== 文件上传记录管理方法 ==========
    
    def save_uploaded_file(self, filename: str, original_filename: str, file_path: str, 
                          uploaded_by: str, file_type: str = 'dataset', mode: str = 'unknown',
                          total_count: int = 0, file_size: int = 0, metadata: Dict = None) -> str:
        """保存文件上传记录，如果同用户同名文件已存在则更新记录"""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 先检查是否已存在相同用户和文件名的记录
                cursor.execute('''
                    SELECT id FROM uploaded_files 
                    WHERE filename = ? AND uploaded_by = ? AND is_active = 1
                ''', (filename, uploaded_by))
                
                existing_record = cursor.fetchone()
                
                if existing_record:
                    # 更新现有记录
                    file_id = existing_record[0]
                    cursor.execute('''
                        UPDATE uploaded_files 
                        SET original_filename = ?, file_path = ?, file_size = ?, 
                            mode = ?, total_count = ?, metadata = ?, uploaded_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (
                        original_filename, file_path, file_size, mode, total_count,
                        json.dumps(metadata or {}), file_id
                    ))
                    print(f"📝 更新文件记录: {filename} (用户: {uploaded_by})")
                else:
                    # 创建新记录
                    file_id = str(uuid.uuid4())
                    cursor.execute('''
                        INSERT INTO uploaded_files 
                        (id, filename, original_filename, file_path, file_size, file_type, mode, 
                         total_count, uploaded_by, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        file_id, filename, original_filename, file_path, file_size, 
                        file_type, mode, total_count, uploaded_by, 
                        json.dumps(metadata or {})
                    ))
                    print(f"📁 创建文件记录: {filename} (用户: {uploaded_by})")
                
                conn.commit()
                return file_id
        except Exception as e:
            print(f"保存文件上传记录失败: {e}")
            return None
    
    def get_user_uploaded_files(self, uploaded_by: str = None, file_type: str = None, 
                               include_all_users: bool = False) -> List[Dict]:
        """获取用户上传的文件列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT id, filename, original_filename, file_path, file_size, file_type, 
                           mode, total_count, uploaded_by, uploaded_at, metadata
                    FROM uploaded_files 
                    WHERE is_active = 1
                '''
                params = []
                
                # 用户权限过滤
                if not include_all_users and uploaded_by:
                    query += ' AND uploaded_by = ?'
                    params.append(uploaded_by)
                
                if file_type:
                    query += ' AND file_type = ?'
                    params.append(file_type)
                
                query += ' ORDER BY uploaded_at DESC'
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                files = []
                for row in rows:
                    file_info = {
                        'id': row[0],
                        'filename': row[1],
                        'original_filename': row[2],
                        'file_path': row[3],
                        'file_size': row[4],
                        'file_type': row[5],
                        'mode': row[6],
                        'total_count': row[7],
                        'uploaded_by': row[8],
                        'uploaded_at': row[9],
                        'metadata': json.loads(row[10]) if row[10] else {}
                    }
                    files.append(file_info)
                
                return files
        except Exception as e:
            print(f"获取用户上传文件失败: {e}")
            return []
    
    def delete_uploaded_file_record(self, file_id: str) -> bool:
        """删除文件上传记录（软删除）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE uploaded_files SET is_active = 0 
                    WHERE id = ?
                ''', (file_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"删除文件上传记录失败: {e}")
            return False
    
    def get_uploaded_file_by_filename(self, filename: str, uploaded_by: str = None) -> Optional[Dict]:
        """根据文件名获取上传记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT id, filename, original_filename, file_path, file_size, file_type, 
                           mode, total_count, uploaded_by, uploaded_at, metadata
                    FROM uploaded_files 
                    WHERE filename = ? AND is_active = 1
                '''
                params = [filename]
                
                if uploaded_by:
                    query += ' AND uploaded_by = ?'
                    params.append(uploaded_by)
                
                cursor.execute(query, params)
                row = cursor.fetchone()
                
                if row:
                    return {
                        'id': row[0],
                        'filename': row[1],
                        'original_filename': row[2],
                        'file_path': row[3],
                        'file_size': row[4],
                        'file_type': row[5],
                        'mode': row[6],
                        'total_count': row[7],
                        'uploaded_by': row[8],
                        'uploaded_at': row[9],
                        'metadata': json.loads(row[10]) if row[10] else {}
                    }
                return None
        except Exception as e:
            print(f"获取文件上传记录失败: {e}")
            return None
    
    def delete_running_task(self, task_id: str) -> bool:
        """删除运行时任务记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM running_tasks WHERE task_id = ?', (task_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"删除运行时任务失败: {e}")
            return False
    
    def cleanup_completed_tasks(self, days_old: int = 7) -> int:
        """清理旧的已完成任务"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM running_tasks 
                    WHERE status IN ('completed', 'failed', 'cancelled') 
                    AND completed_at < ?
                ''', (cutoff_date,))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            print(f"清理已完成任务失败: {e}")
            return 0
    
    # ========== 分享管理方法 ==========
    
    def create_share_link(self, result_id: str, shared_by: str, share_type: str = 'public',
                         title: str = None, description: str = None, expires_hours: int = None,
                         allow_download: bool = False, password: str = None, 
                         access_limit: int = 0, shared_to: str = None) -> Dict:
        """创建分享链接"""
        import secrets
        import hashlib
        
        try:
            share_id = str(uuid.uuid4())
            share_token = secrets.token_urlsafe(32)  # 生成安全的分享令牌
            
            # 计算过期时间
            expires_at = None
            if expires_hours and expires_hours > 0:
                expires_at = (datetime.now() + timedelta(hours=expires_hours)).isoformat()
            
            # 处理密码保护
            password_hash = None
            if password:
                password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO shared_links 
                    (id, share_token, result_id, share_type, shared_by, shared_to,
                     title, description, allow_download, password_protected,
                     expires_at, access_limit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    share_id, share_token, result_id, share_type, shared_by, shared_to,
                    title, description, allow_download, password_hash,
                    expires_at, access_limit
                ))
                conn.commit()
                
                return {
                    'share_id': share_id,
                    'share_token': share_token,
                    'result_id': result_id,
                    'share_type': share_type,
                    'expires_at': expires_at,
                    'access_limit': access_limit
                }
        except Exception as e:
            print(f"创建分享链接失败: {e}")
            return None
    
    def get_share_link_by_token(self, share_token: str) -> Optional[Dict]:
        """根据分享令牌获取分享信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sl.*, er.name as result_name, er.evaluation_mode, 
                           er.models, er.created_at as result_created_at, er.result_file,
                           u.display_name as shared_by_name, u.username as shared_by_username
                    FROM shared_links sl
                    LEFT JOIN evaluation_results er ON sl.result_id = er.id
                    LEFT JOIN users u ON sl.shared_by = u.id
                    WHERE sl.share_token = ? AND sl.is_active = 1
                ''', (share_token,))
                
                row = cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    share_info = dict(zip(columns, row))
                    
                    # 解析JSON字段
                    if share_info.get('models'):
                        share_info['models'] = json.loads(share_info['models'])
                    
                    return share_info
                return None
        except Exception as e:
            print(f"获取分享链接失败: {e}")
            return None
    
    def verify_share_access(self, share_token: str, password: str = None) -> Dict:
        """验证分享链接访问权限"""
        share_info = self.get_share_link_by_token(share_token)
        
        if not share_info:
            return {'valid': False, 'reason': '分享链接不存在或已失效'}
        
        # 检查是否过期
        if share_info['expires_at']:
            expire_time = datetime.fromisoformat(share_info['expires_at'])
            if datetime.now() > expire_time:
                return {'valid': False, 'reason': '分享链接已过期'}
        
        # 检查访问次数限制
        if share_info['access_limit'] > 0:
            if share_info['view_count'] >= share_info['access_limit']:
                return {'valid': False, 'reason': '分享链接访问次数已达上限'}
        
        # 检查密码保护
        if share_info['password_protected']:
            if not password:
                return {'valid': False, 'reason': '需要访问密码', 'require_password': True}
            
            import hashlib
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if password_hash != share_info['password_protected']:
                return {'valid': False, 'reason': '访问密码错误', 'require_password': True}
        
        return {'valid': True, 'share_info': share_info}
    
    def record_share_access(self, share_token: str, ip_address: str = None,
                           user_agent: str = None, user_id: str = None) -> bool:
        """记录分享链接访问"""
        try:
            share_info = self.get_share_link_by_token(share_token)
            if not share_info:
                return False
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 记录访问日志
                log_id = str(uuid.uuid4())
                cursor.execute('''
                    INSERT INTO shared_access_logs 
                    (id, share_id, ip_address, user_agent, user_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (log_id, share_info['id'], ip_address, user_agent, user_id))
                
                # 更新分享链接的访问统计
                cursor.execute('''
                    UPDATE shared_links 
                    SET view_count = view_count + 1, last_accessed = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (share_info['id'],))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"记录分享访问失败: {e}")
            return False
    
    def get_user_shared_links(self, user_id: str, include_revoked: bool = False) -> List[Dict]:
        """获取用户创建的分享链接列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT sl.*, er.name as result_name, er.evaluation_mode,
                           er.models, er.created_at as result_created_at
                    FROM shared_links sl
                    LEFT JOIN evaluation_results er ON sl.result_id = er.id
                    WHERE sl.shared_by = ?
                '''
                params = [user_id]
                
                if not include_revoked:
                    query += ' AND sl.is_active = 1'
                
                query += ' ORDER BY sl.created_at DESC'
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                shares = []
                for row in rows:
                    columns = [description[0] for description in cursor.description]
                    share_info = dict(zip(columns, row))
                    
                    # 解析JSON字段
                    if share_info.get('models'):
                        share_info['models'] = json.loads(share_info['models'])
                    
                    shares.append(share_info)
                
                return shares
        except Exception as e:
            print(f"获取用户分享链接失败: {e}")
            return []
    
    def revoke_share_link(self, share_id: str, revoked_by: str) -> bool:
        """撤销分享链接"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE shared_links 
                    SET is_active = 0, revoked_at = CURRENT_TIMESTAMP, revoked_by = ?
                    WHERE id = ?
                ''', (revoked_by, share_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"撤销分享链接失败: {e}")
            return False
    
    def get_share_access_logs(self, share_id: str, limit: int = 50) -> List[Dict]:
        """获取分享链接访问日志"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sal.*, u.display_name as user_name, u.username
                    FROM shared_access_logs sal
                    LEFT JOIN users u ON sal.user_id = u.id
                    WHERE sal.share_id = ?
                    ORDER BY sal.accessed_at DESC
                    LIMIT ?
                ''', (share_id, limit))
                
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"获取分享访问日志失败: {e}")
            return []
    
    def cleanup_expired_shares(self) -> int:
        """清理过期的分享链接"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE shared_links 
                    SET is_active = 0
                    WHERE expires_at IS NOT NULL 
                    AND expires_at < CURRENT_TIMESTAMP 
                    AND is_active = 1
                ''')
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            print(f"清理过期分享链接失败: {e}")
            return 0


# 创建全局数据库实例
db = EvaluationDatabase()

if __name__ == "__main__":
    # 测试数据库功能
    print("初始化高级评测系统数据库...")
    
    # 创建默认项目
    project_id = db.create_project("默认项目", "系统默认项目")
    print(f"创建项目: {project_id}")
    
    # 初始化默认管理员账户
    admin_id = db.init_default_admin()
    if admin_id:
        print(f"创建管理员账户: {admin_id}")
    
    # 获取统计信息
    stats = db.get_statistics()
    print(f"系统统计: {stats}")
    
    print("数据库初始化完成！")
