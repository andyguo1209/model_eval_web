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
            cursor = conn.cursor()
            
            # 1. 评测项目表
            cursor.execute('''
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
            cursor.execute('''
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS annotations (
                    id TEXT PRIMARY KEY,
                    result_id TEXT NOT NULL,
                    question_index INTEGER NOT NULL,
                    question_text TEXT,
                    model_name TEXT NOT NULL,
                    model_answer TEXT,
                    
                    -- 标注维度
                    correctness_score INTEGER, -- 1-5分
                    relevance_score INTEGER, -- 1-5分
                    safety_score INTEGER, -- 1-5分
                    creativity_score INTEGER, -- 1-5分
                    logic_consistency BOOLEAN, -- 逻辑一致性
                    
                    -- 标注元信息
                    annotator TEXT NOT NULL, -- 标注员ID
                    annotation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    annotation_notes TEXT, -- 标注备注
                    confidence_level INTEGER, -- 标注信心程度 1-5
                    
                    -- 审核信息
                    reviewer TEXT, -- 审核员ID
                    review_status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
                    review_time TIMESTAMP,
                    review_notes TEXT,
                    
                    FOREIGN KEY (result_id) REFERENCES evaluation_results (id)
                )
            ''')
            
            # 4. 标注标准表
            cursor.execute('''
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
            cursor.execute('''
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
            
            # 6. 用户表（简化版本）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    display_name TEXT,
                    role TEXT DEFAULT 'annotator', -- 'admin', 'reviewer', 'annotator', 'viewer'
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP,
                    preferences TEXT -- JSON格式存储用户偏好设置
                )
            ''')
            
            # 创建索引提高查询性能
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_project ON evaluation_results(project_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_created ON evaluation_results(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_annotations_result ON annotations(result_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_annotations_annotator ON annotations(annotator)')
            
            conn.commit()
    
    def create_project(self, name: str, description: str = "", created_by: str = "system") -> str:
        """创建新项目"""
        project_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
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
            cursor = conn.cursor()
            cursor.execute('''
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
            cursor = conn.cursor()
            
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
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
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
            cursor = conn.cursor()
            cursor.execute('''
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
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM annotations WHERE result_id = ?
                ORDER BY question_index, model_name
            ''', (result_id,))
            
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            
            return [dict(zip(columns, row)) for row in rows]
    
    def archive_old_results(self, days_threshold: int = 90) -> int:
        """归档旧的评测结果"""
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE evaluation_results 
                SET status = 'archived', archived_at = ?
                WHERE created_at < ? AND status = 'completed'
            ''', (datetime.now().isoformat(), cutoff_date.isoformat()))
            
            archived_count = cursor.rowcount
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
            cursor = conn.cursor()
            
            stats = {}
            
            # 总评测次数
            cursor.execute('SELECT COUNT(*) FROM evaluation_results')
            stats['total_evaluations'] = cursor.fetchone()[0]
            
            # 总标注数
            cursor.execute('SELECT COUNT(*) FROM annotations')
            stats['total_annotations'] = cursor.fetchone()[0]
            
            # 活跃项目数
            cursor.execute('SELECT COUNT(*) FROM projects WHERE status = "active"')
            stats['active_projects'] = cursor.fetchone()[0]
            
            # 最近7天的评测数
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cursor.execute(
                'SELECT COUNT(*) FROM evaluation_results WHERE created_at > ?',
                (week_ago,)
            )
            stats['recent_evaluations'] = cursor.fetchone()[0]
            
            return stats


# 创建全局数据库实例
db = EvaluationDatabase()

if __name__ == "__main__":
    # 测试数据库功能
    print("初始化高级评测系统数据库...")
    
    # 创建默认项目
    project_id = db.create_project("默认项目", "系统默认项目")
    print(f"创建项目: {project_id}")
    
    # 获取统计信息
    stats = db.get_statistics()
    print(f"系统统计: {stats}")
    
    print("数据库初始化完成！")
