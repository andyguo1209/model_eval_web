"""
评测结果历史管理系统
提供专业的结果存储、检索、标签管理功能
"""

import os
import shutil
import json
from datetime import datetime
from typing import List, Dict, Optional
from database import db
import pandas as pd

class EvaluationHistoryManager:
    def __init__(self):
        self.results_dir = "results_history"
        self.ensure_directories()
    
    def ensure_directories(self):
        """确保必要的目录存在"""
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(os.path.join(self.results_dir, "archived"), exist_ok=True)
    
    def save_evaluation_result(self, 
                             evaluation_data: Dict,
                             result_file_path: str,
                             project_id: str = None) -> str:
        """
        保存评测结果到历史记录
        
        Args:
            evaluation_data: 评测元数据
            result_file_path: 结果文件路径
            project_id: 项目ID
        
        Returns:
            result_id: 保存的结果ID
        """
        try:
            # 获取或生成结果名称
            custom_name = evaluation_data.get('custom_name', '').strip()
            
            if custom_name:
                # 使用自定义名称，并添加时间戳以避免冲突
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                result_name = f"{custom_name}_{timestamp}"
            else:
                # 自动生成结果名称
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dataset_name = os.path.splitext(os.path.basename(evaluation_data.get('dataset_file', 'unknown')))[0]
                models_str = "_".join(evaluation_data.get('models', []))[:50]  # 限制长度
                result_name = f"{dataset_name}_{models_str}_{timestamp}"
            
            # 复制结果文件到历史目录
            result_filename = f"{result_name}.csv"
            dest_path = os.path.join(self.results_dir, result_filename)
            shutil.copy2(result_file_path, dest_path)
            
            # 生成结果摘要
            result_summary = self._generate_result_summary(result_file_path, evaluation_data)
            
            # 自动生成标签
            tags = self._generate_auto_tags(evaluation_data, result_summary)
            
            # 保存完整的评测元数据，包括时间信息用于持久化分析
            metadata = {
                'start_time': evaluation_data.get('start_time'),
                'end_time': evaluation_data.get('end_time'),
                'question_count': evaluation_data.get('question_count', 0),
                'evaluation_settings': {
                    'mode': evaluation_data.get('evaluation_mode', 'unknown'),
                    'models': evaluation_data.get('models', []),
                    'dataset_name': os.path.splitext(os.path.basename(evaluation_data.get('dataset_file', '')))[0]
                },
                'analysis_generated': False  # 标记是否已生成分析数据
            }
            
            # 保存到数据库
            result_id = db.save_evaluation_result(
                project_id=project_id or self._get_default_project_id(),
                name=result_name,
                dataset_file=evaluation_data.get('dataset_file', ''),
                models=evaluation_data.get('models', []),
                result_file=dest_path,
                evaluation_mode=evaluation_data.get('evaluation_mode', 'unknown'),
                result_summary=result_summary,
                tags=tags,
                created_by=evaluation_data.get('created_by', 'system'),
                metadata=metadata
            )
            
            print(f"✅ 评测结果已保存: {result_id}")
            return result_id
            
        except Exception as e:
            print(f"❌ 保存评测结果失败: {e}")
            raise
    
    def get_history_list(self, 
                        project_id: str = None,
                        tags: List[str] = None,
                        limit: int = 20,
                        offset: int = 0,
                        created_by: str = None,
                        include_all_users: bool = False) -> Dict:
        """获取历史记录列表（支持用户权限过滤）"""
        try:
            results = db.get_evaluation_history(
                project_id=project_id,
                tags=tags,
                limit=limit,
                offset=offset,
                created_by=created_by,
                include_all_users=include_all_users
            )
            
            # 添加文件存在性检查和额外信息
            for result in results:
                result['file_exists'] = os.path.exists(result['result_file'])
                result['file_size'] = self._get_file_size(result['result_file'])
                result['download_url'] = f"/api/history/download/{result['id']}"
                result['view_url'] = f"/view_history/{result['id']}"
                # 标注功能已移除
                
                # 添加创建者信息
                if result.get('created_by'):
                    creator_info = db.get_user_by_id(result['created_by'])
                    result['creator_name'] = creator_info['display_name'] if creator_info else '未知用户'
                    result['creator_username'] = creator_info['username'] if creator_info else 'unknown'
                else:
                    result['creator_name'] = '系统'
                    result['creator_username'] = 'system'
            
            return {
                'success': True,
                'results': results,
                'total': len(results),
                'has_more': len(results) == limit
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
    
    def get_result_detail(self, result_id: str) -> Dict:
        """获取单个结果的详细信息"""
        try:
            results = db.get_evaluation_history()
            result = next((r for r in results if r['id'] == result_id), None)
            
            if not result:
                return {'success': False, 'error': '结果不存在'}
            
            # 读取结果文件内容
            if os.path.exists(result['result_file']):
                df = pd.read_csv(result['result_file'])
                result['data_preview'] = df.head(10).to_dict('records')
                result['total_rows'] = len(df)
                result['columns'] = df.columns.tolist()
            
            # 标注功能已移除
            result['annotations'] = []
            result['annotation_count'] = 0
            
            return {
                'success': True,
                'result': result
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def rename_result(self, result_id: str, new_name: str) -> bool:
        """重命名历史记录"""
        try:
            if not new_name.strip():
                return False
                
            # 添加时间戳以避免冲突
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            full_name = f"{new_name.strip()}_{timestamp}"
            
            # 更新数据库
            return db.update_evaluation_result_name(result_id, full_name)
            
        except Exception as e:
            print(f"重命名结果失败: {e}")
            return False
    
    def delete_result(self, result_id: str) -> Dict:
        """删除历史记录和对应的CSV文件"""
        try:
            # 获取结果信息
            detail = self.get_result_detail(result_id)
            if not detail['success']:
                return detail
            
            result = detail['result']
            deleted_files = []
            
            # 删除所有相关的CSV文件
            file_path = result['result_file']
            result_name = result['name']
            
            print(f"🗑️ 开始删除评测结果: {result_name} (ID: {result_id})")
            
            # 1. 删除原始文件路径指向的文件
            if file_path:
                if os.path.isabs(file_path):
                    # 绝对路径
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        deleted_files.append(file_path)
                        print(f"✅ 删除原始文件: {file_path}")
                else:
                    # 相对路径，尝试多个可能的位置
                    possible_paths = [
                        file_path,  # 原始相对路径
                        os.path.join('results', os.path.basename(file_path)),
                        os.path.join('results_history', os.path.basename(file_path)),
                        os.path.join('results', file_path),
                        os.path.join('results_history', file_path)
                    ]
                    
                    for path in possible_paths:
                        if os.path.exists(path):
                            os.remove(path)
                            deleted_files.append(path)
                            print(f"✅ 删除文件: {path}")
            
            # 2. 根据结果名称查找可能的文件
            # 生成可能的文件名模式
            base_name = result_name.replace(' ', '_')  # 替换空格为下划线
            possible_filenames = [
                f"{base_name}.csv",
                f"{result_name}.csv",
                f"evaluation_result_{result_name}.csv",
                # 处理可能的时间戳后缀
                f"{base_name}*.csv",
            ]
            
            # 搜索可能的目录
            search_dirs = ['results', 'results_history', '.']
            
            for search_dir in search_dirs:
                if not os.path.exists(search_dir):
                    continue
                    
                try:
                    for filename in os.listdir(search_dir):
                        if filename.endswith('.csv'):
                            # 检查文件名是否匹配
                            for pattern in possible_filenames:
                                if pattern.endswith('*.csv'):
                                    # 模糊匹配
                                    pattern_prefix = pattern[:-5]  # 移除 '*.csv'
                                    if filename.startswith(pattern_prefix):
                                        file_full_path = os.path.join(search_dir, filename)
                                        if file_full_path not in deleted_files:
                                            os.remove(file_full_path)
                                            deleted_files.append(file_full_path)
                                            print(f"✅ 删除匹配文件: {file_full_path}")
                                else:
                                    # 精确匹配
                                    if filename == pattern:
                                        file_full_path = os.path.join(search_dir, filename)
                                        if file_full_path not in deleted_files:
                                            os.remove(file_full_path)
                                            deleted_files.append(file_full_path)
                                            print(f"✅ 删除匹配文件: {file_full_path}")
                except OSError as e:
                    print(f"⚠️ 搜索目录 {search_dir} 时出错: {e}")
                    continue
            
            # 3. 从数据库删除（标记为已删除）
            with db._get_connection() as conn:
                db_cursor = conn.cursor()
                db_cursor.execute(
                    'UPDATE evaluation_results SET status = "deleted", archived_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (result_id,)
                )
                conn.commit()
            
            if deleted_files:
                file_list = '\n'.join([f"  - {f}" for f in deleted_files])
                print(f"✅ 评测结果删除完成，共删除 {len(deleted_files)} 个文件:\n{file_list}")
                return {
                    'success': True, 
                    'message': f'删除成功，共删除 {len(deleted_files)} 个相关文件',
                    'deleted_files': deleted_files
                }
            else:
                print(f"✅ 评测结果从数据库删除完成，但未找到相关的CSV文件")
                return {
                    'success': True, 
                    'message': '删除成功（未找到相关文件）',
                    'deleted_files': []
                }
            
        except Exception as e:
            print(f"❌ 删除评测结果失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def archive_old_results(self, days_threshold: int = 90) -> Dict:
        """归档旧结果"""
        try:
            archived_count = db.archive_old_results(days_threshold)
            
            # 移动文件到归档目录
            archived_results = db.get_evaluation_history(status='archived', limit=1000)
            moved_files = 0
            
            for result in archived_results:
                if os.path.exists(result['result_file']):
                    filename = os.path.basename(result['result_file'])
                    archive_path = os.path.join(self.results_dir, "archived", filename)
                    shutil.move(result['result_file'], archive_path)
                    
                    # 更新数据库中的文件路径
                    with db._get_connection() as conn:
                        db_cursor = conn.cursor()
                        db_cursor.execute(
                            'UPDATE evaluation_results SET result_file = ? WHERE id = ?',
                            (archive_path, result['id'])
                        )
                        conn.commit()
                    moved_files += 1
            
            return {
                'success': True,
                'archived_count': archived_count,
                'moved_files': moved_files
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def add_tags(self, result_id: str, tags: List[str]) -> Dict:
        """为结果添加标签"""
        try:
            # 获取当前标签
            detail = self.get_result_detail(result_id)
            if not detail['success']:
                return detail
            
            current_tags = set(detail['result']['tags'])
            new_tags = current_tags.union(set(tags))
            
            # 更新数据库
            with db._get_connection() as conn:
                db_cursor = conn.cursor()
                db_cursor.execute(
                    'UPDATE evaluation_results SET tags = ? WHERE id = ?',
                    (json.dumps(list(new_tags)), result_id)
                )
                conn.commit()
            
            return {'success': True, 'tags': list(new_tags)}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_available_tags(self) -> List[str]:
        """获取所有可用标签"""
        try:
            results = db.get_evaluation_history(limit=1000)
            all_tags = set()
            
            for result in results:
                all_tags.update(result['tags'])
            
            return sorted(list(all_tags))
            
        except Exception as e:
            return []
    
    def get_statistics(self) -> Dict:
        """获取历史统计信息"""
        try:
            stats = db.get_statistics()
            
            # 添加磁盘使用统计
            total_size = 0
            file_count = 0
            
            for root, dirs, files in os.walk(self.results_dir):
                for file in files:
                    if file.endswith('.csv'):
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            total_size += os.path.getsize(file_path)
                            file_count += 1
            
            stats.update({
                'total_disk_usage': self._format_file_size(total_size),
                'total_result_files': file_count,
                'available_tags_count': len(self.get_available_tags())
            })
            
            return stats
            
        except Exception as e:
            return {'error': str(e)}
    
    def _generate_result_summary(self, result_file: str, evaluation_data: Dict) -> Dict:
        """生成结果摘要统计"""
        try:
            df = pd.read_csv(result_file)
            
            summary = {
                'total_questions': int(len(df)),
                'models': evaluation_data.get('models', []),
                'evaluation_mode': evaluation_data.get('evaluation_mode'),
                'question_types': {},
                'model_scores': {},
                # 添加时间信息
                'start_time': evaluation_data.get('start_time'),
                'end_time': evaluation_data.get('end_time'),
                'question_count': evaluation_data.get('question_count', len(df))
            }
            
            # 统计题目类型分布
            if '类型' in df.columns:
                type_counts = df['类型'].value_counts()
                # 转换为Python原生数据类型
                summary['question_types'] = {str(k): int(v) for k, v in type_counts.items()}
            
            # 统计模型评分
            score_columns = [col for col in df.columns if '评分' in col]
            for col in score_columns:
                if col in df.columns:
                    model_name = col.replace('_评分', '').replace('评分', '')
                    scores = df[col].dropna()
                    if len(scores) > 0:
                        summary['model_scores'][model_name] = {
                            'avg_score': float(scores.mean()),
                            'max_score': float(scores.max()),
                            'min_score': float(scores.min()),
                            'scored_count': int(len(scores))
                        }
            
            return summary
            
        except Exception as e:
            return {'error': str(e)}
    
    def _generate_auto_tags(self, evaluation_data: Dict, result_summary: Dict) -> List[str]:
        """自动生成标签"""
        tags = []
        
        # 基于评测模式
        mode = evaluation_data.get('evaluation_mode')
        if mode:
            tags.append(f"模式_{mode}")
        
        # 基于模型数量
        model_count = len(evaluation_data.get('models', []))
        if model_count == 1:
            tags.append("单模型")
        elif model_count > 1:
            tags.append("多模型对比")
        
        # 基于题目数量
        total_questions = result_summary.get('total_questions', 0)
        if total_questions < 10:
            tags.append("小规模测试")
        elif total_questions < 100:
            tags.append("中等规模")
        else:
            tags.append("大规模测试")
        
        # 基于时间
        now = datetime.now()
        tags.append(f"{now.year}年{now.month}月")
        
        return tags
    
    def _get_default_project_id(self) -> str:
        """获取默认项目ID"""
        # 简单实现：总是返回第一个项目或创建默认项目
        try:
            with db._get_connection() as conn:
                db_cursor = conn.cursor()
                db_cursor.execute('SELECT id FROM projects LIMIT 1')
                result = db_cursor.fetchone()
                
                if result:
                    return result[0]
                else:
                    # 创建默认项目
                    return db.create_project("默认项目", "系统默认项目")
        except:
            return "default"
    
    def _get_file_size(self, file_path: str) -> str:
        """获取文件大小（格式化）"""
        try:
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                return self._format_file_size(size)
            return "0 B"
        except:
            return "未知"
    
    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.1f} {size_names[i]}"


# 创建全局历史管理器实例
history_manager = EvaluationHistoryManager()

if __name__ == "__main__":
    # 测试功能
    print("测试评测历史管理系统...")
    
    # 获取统计信息
    stats = history_manager.get_statistics()
    print(f"系统统计: {stats}")
    
    # 获取历史列表
    history = history_manager.get_history_list()
    print(f"历史记录数量: {len(history['results'])}")
    
    print("测试完成！")
