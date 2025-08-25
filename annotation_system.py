"""
专业人工标注系统
支持多维度标注、快捷操作、质量检查、协作功能
"""

import pandas as pd
from typing import Dict, List, Optional, Tuple
from database import db
import json
import os
from datetime import datetime

class AnnotationSystem:
    def __init__(self):
        self.annotation_dimensions = {
            'correctness': {
                'name': '正确性',
                'type': 'score',
                'scale': [1, 2, 3, 4, 5],
                'descriptions': {
                    1: '完全错误',
                    2: '大部分错误',
                    3: '部分正确',
                    4: '基本正确',
                    5: '完全正确'
                }
            },
            'relevance': {
                'name': '相关性',
                'type': 'score',
                'scale': [1, 2, 3, 4, 5],
                'descriptions': {
                    1: '完全不相关',
                    2: '基本不相关',
                    3: '部分相关',
                    4: '相关',
                    5: '高度相关'
                }
            },
            'safety': {
                'name': '安全性',
                'type': 'score',
                'scale': [1, 2, 3, 4, 5],
                'descriptions': {
                    1: '危险内容',
                    2: '有安全风险',
                    3: '一般',
                    4: '安全',
                    5: '非常安全'
                }
            },
            'creativity': {
                'name': '创造性',
                'type': 'score',
                'scale': [1, 2, 3, 4, 5],
                'descriptions': {
                    1: '无创新',
                    2: '创新较少',
                    3: '一般创新',
                    4: '有创新',
                    5: '高度创新'
                }
            },
            'logic_consistency': {
                'name': '逻辑一致性',
                'type': 'boolean',
                'options': [True, False],
                'descriptions': {
                    True: '逻辑一致',
                    False: '逻辑不一致'
                }
            }
        }
    
    def get_annotation_data(self, result_id: str) -> Dict:
        """获取待标注的数据"""
        try:
            # 获取评测结果详情
            results = db.get_evaluation_history()
            result = next((r for r in results if r['id'] == result_id), None)
            
            if not result:
                return {'success': False, 'error': '结果不存在'}
            
            # 读取结果文件
            if not os.path.exists(result['result_file']):
                return {'success': False, 'error': '结果文件不存在'}
            
            df = pd.read_csv(result['result_file'])
            
            # 提取标注所需的数据
            annotation_data = []
            for index, row in df.iterrows():
                question_data = {
                    'question_index': index,
                    'question_text': str(row.get('问题', row.get('query', ''))),
                    'question_type': str(row.get('类型', row.get('type', '未分类'))),
                    'models_answers': {}
                }
                
                # 提取各模型的回答
                for col in df.columns:
                    if col.endswith('_回答') or col.endswith('_answer'):
                        model_name = col.replace('_回答', '').replace('_answer', '')
                        question_data['models_answers'][model_name] = str(row.get(col, ''))
                
                annotation_data.append(question_data)
            
            # 获取已有标注
            existing_annotations = db.get_annotations(result_id)
            annotations_by_question = {}
            for ann in existing_annotations:
                key = f"{ann['question_index']}_{ann['model_name']}"
                annotations_by_question[key] = ann
            
            return {
                'success': True,
                'result_info': result,
                'annotation_data': annotation_data,
                'existing_annotations': annotations_by_question,
                'annotation_dimensions': self.annotation_dimensions,
                'total_questions': len(annotation_data),
                'total_models': len(result['models'])
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def save_annotation(self, 
                       result_id: str,
                       question_index: int,
                       model_name: str,
                       annotation_data: Dict,
                       annotator: str = 'default') -> Dict:
        """保存单个标注"""
        try:
            # 获取问题和回答内容
            annotation_data_full = self.get_annotation_data(result_id)
            if not annotation_data_full['success']:
                return annotation_data_full
            
            questions = annotation_data_full['annotation_data']
            if question_index >= len(questions):
                return {'success': False, 'error': '问题索引超出范围'}
            
            question = questions[question_index]
            model_answer = question['models_answers'].get(model_name, '')
            
            # 保存标注
            annotation_id = db.save_annotation(
                result_id=result_id,
                question_index=question_index,
                question_text=question['question_text'],
                model_name=model_name,
                model_answer=model_answer,
                annotator=annotator,
                **annotation_data
            )
            
            return {
                'success': True,
                'annotation_id': annotation_id,
                'message': '标注保存成功'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def batch_save_annotations(self, 
                              result_id: str,
                              annotations: List[Dict],
                              annotator: str = 'default') -> Dict:
        """批量保存标注"""
        try:
            saved_count = 0
            errors = []
            
            for ann in annotations:
                result = self.save_annotation(
                    result_id=result_id,
                    question_index=ann['question_index'],
                    model_name=ann['model_name'],
                    annotation_data=ann['annotation_data'],
                    annotator=annotator
                )
                
                if result['success']:
                    saved_count += 1
                else:
                    errors.append(f"问题{ann['question_index']}-{ann['model_name']}: {result['error']}")
            
            return {
                'success': len(errors) == 0,
                'saved_count': saved_count,
                'total_count': len(annotations),
                'errors': errors
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_annotation_progress(self, result_id: str) -> Dict:
        """获取标注进度"""
        try:
            # 获取基本信息
            annotation_data = self.get_annotation_data(result_id)
            if not annotation_data['success']:
                return annotation_data
            
            total_items = annotation_data['total_questions'] * annotation_data['total_models']
            annotated_items = len(annotation_data['existing_annotations'])
            
            progress = {
                'total_questions': annotation_data['total_questions'],
                'total_models': annotation_data['total_models'],
                'total_items': total_items,
                'annotated_items': annotated_items,
                'progress_percentage': (annotated_items / total_items * 100) if total_items > 0 else 0,
                'remaining_items': total_items - annotated_items
            }
            
            # 按模型统计进度
            model_progress = {}
            for model in annotation_data['result_info']['models']:
                model_annotated = sum(1 for key in annotation_data['existing_annotations'].keys() 
                                    if key.endswith(f"_{model}"))
                model_progress[model] = {
                    'annotated': model_annotated,
                    'total': annotation_data['total_questions'],
                    'percentage': (model_annotated / annotation_data['total_questions'] * 100) 
                                if annotation_data['total_questions'] > 0 else 0
                }
            
            progress['model_progress'] = model_progress
            
            # 按维度统计标注质量
            dimension_stats = {}
            for ann in annotation_data['existing_annotations'].values():
                for dim in self.annotation_dimensions.keys():
                    if dim not in dimension_stats:
                        dimension_stats[dim] = {'scores': [], 'count': 0}
                    
                    score = ann.get(f"{dim}_score")
                    if score is not None:
                        dimension_stats[dim]['scores'].append(score)
                        dimension_stats[dim]['count'] += 1
            
            # 计算平均分
            for dim, stats in dimension_stats.items():
                if stats['scores']:
                    stats['average'] = sum(stats['scores']) / len(stats['scores'])
                    stats['distribution'] = {}
                    for score in stats['scores']:
                        stats['distribution'][score] = stats['distribution'].get(score, 0) + 1
                else:
                    stats['average'] = 0
                    stats['distribution'] = {}
            
            progress['dimension_stats'] = dimension_stats
            
            return {
                'success': True,
                'progress': progress
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def export_annotations(self, result_id: str, format: str = 'csv') -> Dict:
        """导出标注结果"""
        try:
            annotations = db.get_annotations(result_id)
            
            if not annotations:
                return {'success': False, 'error': '没有标注数据'}
            
            # 准备导出数据
            export_data = []
            for ann in annotations:
                row = {
                    '问题序号': ann['question_index'],
                    '问题内容': ann['question_text'],
                    '模型名称': ann['model_name'],
                    '模型回答': ann['model_answer'],
                    '标注员': ann['annotator'],
                    '标注时间': ann['annotation_time'],
                    '正确性评分': ann['correctness_score'],
                    '相关性评分': ann['relevance_score'],
                    '安全性评分': ann['safety_score'],
                    '创造性评分': ann['creativity_score'],
                    '逻辑一致性': '是' if ann['logic_consistency'] else '否',
                    '置信度': ann['confidence_level'],
                    '标注备注': ann['annotation_notes'] or ''
                }
                export_data.append(row)
            
            # 创建文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"annotations_{result_id[:8]}_{timestamp}.{format}"
            filepath = os.path.join("results_history", filename)
            
            if format == 'csv':
                df = pd.DataFrame(export_data)
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
            elif format == 'excel':
                df = pd.DataFrame(export_data)
                df.to_excel(filepath, index=False)
            else:
                return {'success': False, 'error': '不支持的导出格式'}
            
            return {
                'success': True,
                'filename': filename,
                'filepath': filepath,
                'record_count': len(export_data)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_annotation_statistics(self, result_id: str) -> Dict:
        """获取标注统计分析"""
        try:
            annotations = db.get_annotations(result_id)
            
            if not annotations:
                return {'success': False, 'error': '没有标注数据'}
            
            # 基础统计
            stats = {
                'total_annotations': len(annotations),
                'unique_questions': len(set(ann['question_index'] for ann in annotations)),
                'unique_models': len(set(ann['model_name'] for ann in annotations)),
                'annotators': list(set(ann['annotator'] for ann in annotations))
            }
            
            # 按模型统计平均分
            model_stats = {}
            for ann in annotations:
                model = ann['model_name']
                if model not in model_stats:
                    model_stats[model] = {
                        'scores': {dim: [] for dim in self.annotation_dimensions.keys()},
                        'count': 0
                    }
                
                model_stats[model]['count'] += 1
                for dim in self.annotation_dimensions.keys():
                    score = ann.get(f"{dim}_score")
                    if score is not None:
                        model_stats[model]['scores'][dim].append(score)
            
            # 计算平均分和排名
            model_rankings = {}
            for model, data in model_stats.items():
                model_rankings[model] = {}
                for dim, scores in data['scores'].items():
                    if scores:
                        avg_score = sum(scores) / len(scores)
                        model_rankings[model][dim] = {
                            'average': round(avg_score, 2),
                            'count': len(scores),
                            'scores': scores
                        }
                    else:
                        model_rankings[model][dim] = {
                            'average': 0,
                            'count': 0,
                            'scores': []
                        }
            
            # 计算整体排名
            overall_rankings = []
            for model in model_rankings.keys():
                total_score = sum(
                    model_rankings[model][dim]['average'] 
                    for dim in ['correctness', 'relevance', 'safety', 'creativity']
                    if model_rankings[model][dim]['count'] > 0
                ) / 4  # 平均分
                
                overall_rankings.append({
                    'model': model,
                    'overall_score': round(total_score, 2),
                    'annotation_count': model_stats[model]['count']
                })
            
            overall_rankings.sort(key=lambda x: x['overall_score'], reverse=True)
            
            return {
                'success': True,
                'statistics': {
                    'basic_stats': stats,
                    'model_rankings': model_rankings,
                    'overall_rankings': overall_rankings
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def validate_annotation_quality(self, result_id: str) -> Dict:
        """验证标注质量"""
        try:
            annotations = db.get_annotations(result_id)
            
            quality_issues = []
            
            # 检查标注一致性
            question_annotations = {}
            for ann in annotations:
                question_idx = ann['question_index']
                if question_idx not in question_annotations:
                    question_annotations[question_idx] = []
                question_annotations[question_idx].append(ann)
            
            # 检查同一问题不同模型的标注是否存在异常差异
            for question_idx, anns in question_annotations.items():
                if len(anns) > 1:
                    correctness_scores = [ann['correctness_score'] for ann in anns if ann['correctness_score']]
                    if len(correctness_scores) > 1:
                        score_diff = max(correctness_scores) - min(correctness_scores)
                        if score_diff >= 3:  # 差异过大
                            quality_issues.append({
                                'type': 'large_score_difference',
                                'question_index': question_idx,
                                'description': f'问题{question_idx}的正确性评分差异过大: {min(correctness_scores)}-{max(correctness_scores)}',
                                'severity': 'medium'
                            })
            
            # 检查置信度过低的标注
            low_confidence = [ann for ann in annotations if ann['confidence_level'] and ann['confidence_level'] <= 2]
            if low_confidence:
                quality_issues.append({
                    'type': 'low_confidence',
                    'count': len(low_confidence),
                    'description': f'发现{len(low_confidence)}个置信度过低的标注（≤2分）',
                    'severity': 'low'
                })
            
            # 检查未完成的标注维度
            incomplete_annotations = []
            for ann in annotations:
                missing_dimensions = []
                for dim in ['correctness_score', 'relevance_score', 'safety_score']:
                    if not ann.get(dim):
                        missing_dimensions.append(dim)
                
                if missing_dimensions:
                    incomplete_annotations.append({
                        'annotation_id': ann['id'],
                        'question_index': ann['question_index'],
                        'model_name': ann['model_name'],
                        'missing_dimensions': missing_dimensions
                    })
            
            if incomplete_annotations:
                quality_issues.append({
                    'type': 'incomplete_annotations',
                    'count': len(incomplete_annotations),
                    'description': f'发现{len(incomplete_annotations)}个不完整的标注',
                    'details': incomplete_annotations[:10],  # 只显示前10个
                    'severity': 'high'
                })
            
            return {
                'success': True,
                'quality_check': {
                    'total_issues': len(quality_issues),
                    'issues': quality_issues,
                    'quality_score': max(0, 100 - len(quality_issues) * 10)  # 简单的质量评分
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}


# 创建全局标注系统实例
annotation_system = AnnotationSystem()

if __name__ == "__main__":
    # 测试标注系统
    print("测试人工标注系统...")
    
    # 获取标注维度信息
    dimensions = annotation_system.annotation_dimensions
    print(f"支持的标注维度: {list(dimensions.keys())}")
    
    print("标注系统初始化完成！")
