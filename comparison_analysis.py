"""
结果对比分析功能
支持模型横向对比、时间趋势分析、性能图表生成
"""

import pandas as pd
import json
from typing import Dict, List, Optional, Tuple
from database import db
import os
from datetime import datetime, timedelta
import numpy as np
import uuid

class ComparisonAnalysis:
    def __init__(self):
        self.comparison_types = {
            'model_comparison': '模型横向对比',
            'time_trend': '时间趋势分析',
            'dataset_comparison': '数据集对比',
            'performance_analysis': '性能深度分析'
        }
    
    def compare_models(self, result_ids: List[str], comparison_name: str = None) -> Dict:
        """模型横向对比分析"""
        try:
            if len(result_ids) < 2:
                return {'success': False, 'error': '至少需要2个结果进行对比'}
            
            # 获取结果详情
            results_data = []
            for result_id in result_ids:
                results = db.get_evaluation_history()
                result = next((r for r in results if r['id'] == result_id), None)
                if result and os.path.exists(result['result_file']):
                    df = pd.read_csv(result['result_file'])
                    result['data'] = df
                    results_data.append(result)
            
            if len(results_data) < 2:
                return {'success': False, 'error': '有效结果不足2个'}
            
            # 执行对比分析
            comparison = self._analyze_model_performance(results_data)
            
            # 保存对比结果到数据库
            comparison_id = self._save_comparison_analysis(
                name=comparison_name or f"模型对比_{datetime.now().strftime('%Y%m%d_%H%M')}",
                result_ids=result_ids,
                analysis_type='model_comparison',
                analysis_result=comparison
            )
            
            comparison['comparison_id'] = comparison_id
            return {'success': True, 'comparison': comparison}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def analyze_time_trend(self, model_names: List[str] = None, days: int = 30) -> Dict:
        """时间趋势分析"""
        try:
            # 获取指定时间范围内的结果
            cutoff_date = datetime.now() - timedelta(days=days)
            results = db.get_evaluation_history(limit=1000)
            
            # 过滤时间范围
            recent_results = []
            for result in results:
                result_date = datetime.fromisoformat(result['created_at'])
                if result_date >= cutoff_date:
                    recent_results.append(result)
            
            if len(recent_results) < 2:
                return {'success': False, 'error': f'最近{days}天内的结果不足2个'}
            
            # 分析趋势
            trend_data = self._analyze_time_trends(recent_results, model_names)
            
            return {'success': True, 'trend_analysis': trend_data}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def generate_performance_report(self, result_ids: List[str]) -> Dict:
        """生成综合性能报告"""
        try:
            # 获取结果数据
            results_data = []
            annotations_data = []
            
            for result_id in result_ids:
                # 获取评测结果
                results = db.get_evaluation_history()
                result = next((r for r in results if r['id'] == result_id), None)
                if result:
                    results_data.append(result)
                    
                    # 获取标注数据
                    annotations = db.get_annotations(result_id)
                    annotations_data.extend(annotations)
            
            # 生成报告
            report = self._generate_comprehensive_report(results_data, annotations_data)
            
            return {'success': True, 'report': report}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _analyze_model_performance(self, results_data: List[Dict]) -> Dict:
        """分析模型性能对比"""
        comparison = {
            'models': {},
            'metrics': {},
            'summary': {},
            'charts_data': {}
        }
        
        # 提取所有模型
        all_models = set()
        for result in results_data:
            all_models.update(result['models'])
        
        # 分析每个模型的性能
        for model in all_models:
            model_scores = []
            model_data = {
                'total_questions': 0,
                'avg_scores': {},
                'performance_by_dataset': {}
            }
            
            for result in results_data:
                if model in result['models'] and 'data' in result:
                    df = result['data']
                    
                    # 查找模型相关列
                    score_columns = [col for col in df.columns if model in col and '评分' in col]
                    
                    for col in score_columns:
                        scores = df[col].dropna()
                        if len(scores) > 0:
                            model_scores.extend(scores.tolist())
                            
                            if col not in model_data['avg_scores']:
                                model_data['avg_scores'][col] = []
                            model_data['avg_scores'][col].extend(scores.tolist())
                    
                    model_data['total_questions'] += len(df)
                    
                    # 按数据集记录性能
                    dataset_name = os.path.basename(result['dataset_file'])
                    model_data['performance_by_dataset'][dataset_name] = {
                        'questions': len(df),
                        'avg_score': np.mean(model_scores) if model_scores else 0
                    }
            
            # 计算平均分
            for metric, scores in model_data['avg_scores'].items():
                model_data['avg_scores'][metric] = {
                    'mean': np.mean(scores) if scores else 0,
                    'std': np.std(scores) if scores else 0,
                    'count': len(scores)
                }
            
            comparison['models'][model] = model_data
        
        # 生成对比指标
        comparison['metrics'] = self._calculate_comparison_metrics(comparison['models'])
        
        # 生成图表数据
        comparison['charts_data'] = self._generate_charts_data(comparison['models'])
        
        # 生成总结
        comparison['summary'] = self._generate_comparison_summary(comparison['models'])
        
        return comparison
    
    def _analyze_time_trends(self, results: List[Dict], model_names: List[str] = None) -> Dict:
        """分析时间趋势"""
        trend_data = {
            'time_series': {},
            'trend_summary': {},
            'performance_changes': {}
        }
        
        # 按时间排序
        results.sort(key=lambda x: x['created_at'])
        
        # 提取时间序列数据
        for result in results:
            date = result['created_at'][:10]  # 只取日期部分
            
            if date not in trend_data['time_series']:
                trend_data['time_series'][date] = {}
            
            # 获取每个模型的性能数据
            for model in result['models']:
                if model_names and model not in model_names:
                    continue
                
                if model not in trend_data['time_series'][date]:
                    trend_data['time_series'][date][model] = []
                
                # 从result_summary中获取性能数据
                summary = result.get('result_summary', {})
                model_scores = summary.get('model_scores', {})
                
                if model in model_scores:
                    avg_score = model_scores[model].get('avg_score', 0)
                    trend_data['time_series'][date][model].append(avg_score)
        
        # 计算趋势统计
        for model in set(sum([result['models'] for result in results], [])):
            if model_names and model not in model_names:
                continue
                
            model_timeline = []
            for date in sorted(trend_data['time_series'].keys()):
                if model in trend_data['time_series'][date]:
                    scores = trend_data['time_series'][date][model]
                    avg_score = np.mean(scores) if scores else 0
                    model_timeline.append((date, avg_score))
            
            if len(model_timeline) >= 2:
                # 计算趋势方向
                first_score = model_timeline[0][1]
                last_score = model_timeline[-1][1]
                trend_direction = "上升" if last_score > first_score else "下降" if last_score < first_score else "稳定"
                
                trend_data['trend_summary'][model] = {
                    'direction': trend_direction,
                    'change': last_score - first_score,
                    'change_percentage': ((last_score - first_score) / first_score * 100) if first_score > 0 else 0,
                    'data_points': len(model_timeline)
                }
        
        return trend_data
    
    def _generate_comprehensive_report(self, results_data: List[Dict], annotations_data: List[Dict]) -> Dict:
        """生成综合性能报告"""
        report = {
            'basic_stats': {},
            'model_rankings': {},
            'annotation_analysis': {},
            'recommendations': []
        }
        
        # 基础统计
        report['basic_stats'] = {
            'total_evaluations': len(results_data),
            'total_annotations': len(annotations_data),
            'evaluation_period': '',
            'total_questions': sum(r.get('result_summary', {}).get('total_questions', 0) for r in results_data)
        }
        
        if results_data:
            dates = [r['created_at'] for r in results_data]
            report['basic_stats']['evaluation_period'] = f"{min(dates)[:10]} 至 {max(dates)[:10]}"
        
        # 模型排名分析
        if annotations_data:
            model_performance = {}
            for ann in annotations_data:
                model = ann['model_name']
                if model not in model_performance:
                    model_performance[model] = {
                        'scores': {'correctness': [], 'relevance': [], 'safety': [], 'creativity': []},
                        'count': 0
                    }
                
                model_performance[model]['count'] += 1
                for dimension in ['correctness', 'relevance', 'safety', 'creativity']:
                    score = ann.get(f'{dimension}_score')
                    if score:
                        model_performance[model]['scores'][dimension].append(score)
            
            # 计算平均分和排名
            model_rankings = []
            for model, data in model_performance.items():
                avg_scores = {}
                overall_score = 0
                valid_dimensions = 0
                
                for dimension, scores in data['scores'].items():
                    if scores:
                        avg_score = np.mean(scores)
                        avg_scores[dimension] = round(avg_score, 2)
                        overall_score += avg_score
                        valid_dimensions += 1
                
                if valid_dimensions > 0:
                    overall_score = round(overall_score / valid_dimensions, 2)
                    
                model_rankings.append({
                    'model': model,
                    'overall_score': overall_score,
                    'dimension_scores': avg_scores,
                    'annotation_count': data['count']
                })
            
            model_rankings.sort(key=lambda x: x['overall_score'], reverse=True)
            report['model_rankings'] = model_rankings
        
        # 生成建议
        report['recommendations'] = self._generate_recommendations(report)
        
        return report
    
    def _calculate_comparison_metrics(self, models_data: Dict) -> Dict:
        """计算对比指标"""
        metrics = {
            'best_performer': None,
            'most_consistent': None,
            'score_distribution': {},
            'performance_gaps': {}
        }
        
        # 找出最佳表现者
        best_score = 0
        best_model = None
        
        for model, data in models_data.items():
            avg_scores = data.get('avg_scores', {})
            if avg_scores:
                # 计算总体平均分
                total_score = sum(score_data['mean'] for score_data in avg_scores.values())
                avg_total = total_score / len(avg_scores) if avg_scores else 0
                
                if avg_total > best_score:
                    best_score = avg_total
                    best_model = model
        
        metrics['best_performer'] = {
            'model': best_model,
            'score': round(best_score, 2)
        }
        
        return metrics
    
    def _generate_charts_data(self, models_data: Dict) -> Dict:
        """生成图表数据"""
        charts = {
            'radar_chart': {},
            'bar_chart': {},
            'performance_matrix': {}
        }
        
        # 雷达图数据
        dimensions = ['correctness', 'relevance', 'safety', 'creativity']
        for model, data in models_data.items():
            model_scores = []
            for dim in dimensions:
                # 查找对应维度的评分
                score_key = next((key for key in data.get('avg_scores', {}) if dim in key.lower()), None)
                if score_key:
                    score = data['avg_scores'][score_key].get('mean', 0)
                else:
                    score = 0
                model_scores.append(round(score, 2))
            
            charts['radar_chart'][model] = model_scores
        
        return charts
    
    def _generate_comparison_summary(self, models_data: Dict) -> Dict:
        """生成对比总结"""
        summary = {
            'total_models': len(models_data),
            'performance_insights': [],
            'strengths_weaknesses': {}
        }
        
        for model, data in models_data.items():
            avg_scores = data.get('avg_scores', {})
            if avg_scores:
                strengths = []
                weaknesses = []
                
                for metric, score_data in avg_scores.items():
                    score = score_data['mean']
                    if score >= 4:
                        strengths.append(metric)
                    elif score <= 2:
                        weaknesses.append(metric)
                
                summary['strengths_weaknesses'][model] = {
                    'strengths': strengths,
                    'weaknesses': weaknesses
                }
        
        return summary
    
    def _save_comparison_analysis(self, name: str, result_ids: List[str], 
                                 analysis_type: str, analysis_result: Dict) -> str:
        """保存对比分析结果"""
        try:
            comparison_id = str(uuid.uuid4())
            
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO comparison_analyses 
                    (id, name, result_ids, analysis_type, analysis_result, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    comparison_id,
                    name,
                    json.dumps(result_ids),
                    analysis_type,
                    json.dumps(analysis_result),
                    datetime.now().isoformat()
                ))
                conn.commit()
            
            return comparison_id
            
        except Exception as e:
            print(f"保存对比分析失败: {e}")
            return ""
    
    def _generate_recommendations(self, report: Dict) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        model_rankings = report.get('model_rankings', [])
        if model_rankings:
            best_model = model_rankings[0]
            worst_model = model_rankings[-1] if len(model_rankings) > 1 else None
            
            recommendations.append(f"推荐使用 {best_model['model']} 模型，综合评分最高：{best_model['overall_score']}")
            
            if worst_model and worst_model['overall_score'] < 3:
                recommendations.append(f"{worst_model['model']} 模型需要改进，综合评分较低：{worst_model['overall_score']}")
            
            # 分析维度表现
            dimension_performance = {}
            for model_data in model_rankings:
                for dim, score in model_data['dimension_scores'].items():
                    if dim not in dimension_performance:
                        dimension_performance[dim] = []
                    dimension_performance[dim].append(score)
            
            for dim, scores in dimension_performance.items():
                avg_score = np.mean(scores)
                if avg_score < 3:
                    recommendations.append(f"所有模型在{dim}维度表现较弱，平均分{avg_score:.1f}，建议重点关注")
        
        if not recommendations:
            recommendations.append("系统运行正常，继续保持现有配置")
        
        return recommendations


# 创建全局对比分析实例
comparison_analysis = ComparisonAnalysis()

if __name__ == "__main__":
    print("测试对比分析系统...")
    print("对比分析系统初始化完成！")
