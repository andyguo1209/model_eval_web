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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    archived_at TIMESTAMP,
                    metadata TEXT, -- JSON格式存储额外元数据
                    FOREIGN KEY (project_id) REFERENCES projects (id)
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
            
            # 创建索引提高查询性能
            db_cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_project ON evaluation_results(project_id)')
            db_cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_created ON evaluation_results(created_at)')
            db_cursor.execute('CREATE INDEX IF NOT EXISTS idx_annotations_result ON annotations(result_id)')
            db_cursor.execute('CREATE INDEX IF NOT EXISTS idx_annotations_annotator ON annotations(annotator)')
            
            conn.commit()
    
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
                             tags: List[str] = None) -> str:
        """保存评测结果"""
        result_id = str(uuid.uuid4())
        
        # 计算数据集hash用于版本管理
        dataset_hash = self._calculate_file_hash(dataset_file)
        
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            db_cursor.execute('''
                INSERT INTO evaluation_results 
                (id, project_id, name, dataset_file, dataset_hash, models, result_file, 
                 result_summary, evaluation_mode, tags, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                result_id, project_id, name, dataset_file, dataset_hash,
                json.dumps(models), result_file, 
                json.dumps(result_summary or {}),
                evaluation_mode,
                json.dumps(tags or []),
                datetime.now().isoformat()
            ))
            conn.commit()
        return result_id
    
    def get_evaluation_history(self, 
                             project_id: str = None,
                             limit: int = 50,
                             offset: int = 0,
                             status: str = None,
                             tags: List[str] = None) -> List[Dict]:
        """获取评测历史记录"""
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            
            query = '''
                SELECT id, project_id, name, dataset_file, models, result_file,
                       result_summary, evaluation_mode, status, tags, 
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
                    'created_at': row[10],
                    'completed_at': row[11]
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
        """根据结果文件名获取result_id"""
        with sqlite3.connect(self.db_path) as conn:
            db_cursor = conn.cursor()
            db_cursor.execute('''
                SELECT id FROM evaluation_results 
                WHERE result_file = ? OR result_file LIKE ?
            ''', (filename, f'%/{filename}'))
            
            result = db_cursor.fetchone()
            return result[0] if result else None
    
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
    
    # ========== 评分标准管理方法 ==========
    
    def create_scoring_criteria(self, name: str, description: str, criteria_type: str,
                              criteria_config: Dict, dataset_pattern: str = None,
                              is_default: bool = False, created_by: str = 'system') -> str:
        """创建评分标准"""
        criteria_id = str(uuid.uuid4())
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO scoring_criteria 
                (id, name, description, criteria_type, criteria_config, dataset_pattern, 
                 is_default, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                criteria_id, name, description, criteria_type, 
                json.dumps(criteria_config), dataset_pattern, is_default, created_by
            ))
            conn.commit()
            return criteria_id
    
    def get_scoring_criteria(self, criteria_id: str) -> Optional[Dict]:
        """获取指定评分标准"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, description, criteria_type, criteria_config, dataset_pattern,
                       is_default, is_active, created_by, created_at, updated_at
                FROM scoring_criteria WHERE id = ?
            ''', (criteria_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'criteria_type': row[3],
                    'criteria_config': json.loads(row[4]),
                    'dataset_pattern': row[5],
                    'is_default': bool(row[6]),
                    'is_active': bool(row[7]),
                    'created_by': row[8],
                    'created_at': row[9],
                    'updated_at': row[10]
                }
            return None
    
    def get_all_scoring_criteria(self, criteria_type: str = None, active_only: bool = True) -> List[Dict]:
        """获取所有评分标准"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT id, name, description, criteria_type, criteria_config, dataset_pattern,
                       is_default, is_active, created_by, created_at, updated_at
                FROM scoring_criteria WHERE 1=1
            '''
            params = []
            
            if criteria_type:
                query += ' AND criteria_type = ?'
                params.append(criteria_type)
            
            if active_only:
                query += ' AND is_active = 1'
            
            query += ' ORDER BY is_default DESC, created_at DESC'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'criteria_type': row[3],
                    'criteria_config': json.loads(row[4]),
                    'dataset_pattern': row[5],
                    'is_default': bool(row[6]),
                    'is_active': bool(row[7]),
                    'created_by': row[8],
                    'created_at': row[9],
                    'updated_at': row[10]
                }
                for row in rows
            ]
    
    def update_scoring_criteria(self, criteria_id: str, name: str = None, description: str = None,
                              criteria_config: Dict = None, dataset_pattern: str = None,
                              is_default: bool = None, is_active: bool = None) -> bool:
        """更新评分标准"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 构建动态更新语句
            updates = []
            params = []
            
            if name is not None:
                updates.append('name = ?')
                params.append(name)
            if description is not None:
                updates.append('description = ?')
                params.append(description)
            if criteria_config is not None:
                updates.append('criteria_config = ?')
                params.append(json.dumps(criteria_config))
            if dataset_pattern is not None:
                updates.append('dataset_pattern = ?')
                params.append(dataset_pattern)
            if is_default is not None:
                updates.append('is_default = ?')
                params.append(is_default)
            if is_active is not None:
                updates.append('is_active = ?')
                params.append(is_active)
            
            if not updates:
                return False
            
            updates.append('updated_at = ?')
            params.append(datetime.now().isoformat())
            params.append(criteria_id)
            
            query = f'UPDATE scoring_criteria SET {", ".join(updates)} WHERE id = ?'
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_scoring_criteria(self, criteria_id: str) -> bool:
        """删除评分标准"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM scoring_criteria WHERE id = ?', (criteria_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_default_scoring_criteria(self, criteria_type: str) -> Optional[Dict]:
        """获取指定类型的默认评分标准"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, description, criteria_type, criteria_config, dataset_pattern,
                       is_default, is_active, created_by, created_at, updated_at
                FROM scoring_criteria 
                WHERE criteria_type = ? AND is_default = 1 AND is_active = 1
                ORDER BY created_at DESC LIMIT 1
            ''', (criteria_type,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'criteria_type': row[3],
                    'criteria_config': json.loads(row[4]),
                    'dataset_pattern': row[5],
                    'is_default': bool(row[6]),
                    'is_active': bool(row[7]),
                    'created_by': row[8],
                    'created_at': row[9],
                    'updated_at': row[10]
                }
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
                default_prompt = """你是一位专业的大模型测评工程师，请根据以下标准对模型回答进行客观、公正的评测：

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
