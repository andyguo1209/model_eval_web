"""
高级测评结果分析系统
提供详细的统计分析、性能指标和可视化数据
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import json
import os

class AdvancedAnalytics:
    def __init__(self):
        self.score_dimensions = ['准确性', '相关性', '安全性', '创造性']
    
    def _convert_to_serializable(self, obj: Any) -> Any:
        """转换pandas/numpy数据类型为JSON可序列化的Python原生类型"""
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Series):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: self._convert_to_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._convert_to_serializable(item) for item in obj)
        elif pd.isna(obj):
            return None
        else:
            return obj
        
    def analyze_evaluation_results(self, result_file: str, evaluation_data: Dict = None) -> Dict:
        """
        深度分析评测结果
        
        Args:
            result_file: 结果文件路径
            evaluation_data: 评测元数据
            
        Returns:
            完整的分析报告
        """
        try:
            if not os.path.exists(result_file):
                return {'error': '结果文件不存在'}
                
            df = pd.read_csv(result_file)
            
            analysis = {
                'basic_stats': self._calculate_basic_stats(df),
                'score_analysis': self._analyze_scores(df),
                'performance_metrics': self._calculate_performance_metrics(df, evaluation_data),
                'quality_indicators': self._calculate_quality_indicators(df),
                'model_comparison': self._compare_models(df),
                'question_type_analysis': self._analyze_by_question_type(df),
                'time_analysis': self._analyze_time_efficiency(evaluation_data),
                'recommendations': self._generate_recommendations(df)
            }
            
            # 转换所有数据类型为JSON可序列化格式
            analysis = self._convert_to_serializable(analysis)
            
            return {'success': True, 'analysis': analysis}
            
        except Exception as e:
            return {'error': f'分析失败: {str(e)}'}
    
    def _calculate_basic_stats(self, df: pd.DataFrame) -> Dict:
        """计算基础统计信息"""
        stats = {
            'total_questions': len(df),
            'completed_questions': 0,
            'response_rate': 0,
            'data_quality_score': 0
        }
        
        # 计算完成率
        score_columns = [col for col in df.columns if '评分' in col]
        if score_columns:
            completed_count = 0
            for col in score_columns:
                completed_count += df[col].notna().sum()
            stats['completed_questions'] = completed_count
            stats['response_rate'] = (completed_count / (len(df) * len(score_columns))) * 100
        
        # 数据质量评分
        quality_factors = []
        
        # 1. 数据完整性
        completeness = df.notna().mean().mean()
        quality_factors.append(completeness)
        
        # 2. 评分一致性（如果有多个模型）
        if len(score_columns) > 1:
            score_data = df[score_columns].dropna()
            if len(score_data) > 0:
                # 动态计算评分范围，不使用固定的5分制
                score_range = score_data.max().max() - score_data.min().min()
                if score_range > 0:
                    consistency = 1 - (score_data.std(axis=1).mean() / score_range)
                    quality_factors.append(max(0, min(1, consistency)))
                else:
                    quality_factors.append(1)  # 所有分数相同，完全一致
        
        stats['data_quality_score'] = np.mean(quality_factors) * 100
        
        return stats
    
    def _analyze_scores(self, df: pd.DataFrame) -> Dict:
        """详细分析评分情况"""
        score_columns = [col for col in df.columns if '评分' in col]
        
        analysis = {
            'score_distribution': {},
            'model_performance': {},
            'statistical_summary': {},
            'outliers': []
        }
        
        for col in score_columns:
            model_name = col.replace('_评分', '').replace('评分', '')
            scores = df[col].dropna()
            
            if len(scores) == 0:
                continue
                
            # 基础统计
            analysis['model_performance'][model_name] = {
                'mean_score': float(scores.mean()),
                'median_score': float(scores.median()),
                'std_dev': float(scores.std()),
                'min_score': float(scores.min()),
                'max_score': float(scores.max()),
                'score_count': int(len(scores)),
                'percentiles': {
                    '25th': float(scores.quantile(0.25)),
                    '75th': float(scores.quantile(0.75)),
                    '90th': float(scores.quantile(0.90))
                }
            }
            
            # 评分分布
            score_distribution = scores.value_counts().sort_index()
            analysis['score_distribution'][model_name] = {
                'distribution': score_distribution.to_dict(),
                'histogram_data': self._create_histogram_data(scores)
            }
            
            # 异常值检测
            outliers = self._detect_outliers(scores, df['问题'].iloc[scores.index] if '问题' in df.columns else None)
            if outliers:
                analysis['outliers'].extend([
                    {'model': model_name, 'question_index': int(idx), 'score': float(score), 'question': str(question)}
                    for idx, score, question in outliers
                ])
        
        return analysis
    
    def _calculate_performance_metrics(self, df: pd.DataFrame, evaluation_data: Dict = None) -> Dict:
        """计算性能指标"""
        metrics = {
            'efficiency_score': 0,
            'consistency_score': 0,
            'reliability_score': 0,
            'estimated_time_per_question': '未知',
            'throughput': 0
        }
        
        score_columns = [col for col in df.columns if '评分' in col]
        
        if evaluation_data:
            # 时间效率计算
            start_time = evaluation_data.get('start_time')
            end_time = evaluation_data.get('end_time')
            
            if start_time and end_time:
                try:
                    # 处理多种时间格式
                    if isinstance(start_time, str):
                        if 'T' in start_time:
                            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                        else:
                            start_dt = datetime.fromisoformat(start_time)
                    else:
                        start_dt = start_time
                    
                    if isinstance(end_time, str):
                        if 'T' in end_time:
                            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                        else:
                            end_dt = datetime.fromisoformat(end_time)
                    else:
                        end_dt = end_time
                    
                    total_time = (end_dt - start_dt).total_seconds()
                    
                    if total_time > 0:
                        time_per_question = total_time / len(df)
                        metrics['estimated_time_per_question'] = f"{time_per_question:.1f}秒"
                        metrics['throughput'] = 3600 / time_per_question  # 每小时处理题数
                        
                        # 效率评分 (基于处理速度)
                        if time_per_question < 10:
                            metrics['efficiency_score'] = 95
                        elif time_per_question < 30:
                            metrics['efficiency_score'] = 80
                        elif time_per_question < 60:
                            metrics['efficiency_score'] = 65
                        else:
                            metrics['efficiency_score'] = 40
                            
                except Exception as e:
                    pass  # 静默处理时间计算错误
        
        # 一致性评分
        if len(score_columns) > 1:
            score_matrix = df[score_columns].dropna()
            if len(score_matrix) > 0:
                # 计算模型间评分相关性
                correlations = score_matrix.corr()
                avg_correlation = correlations.values[np.triu_indices_from(correlations.values, k=1)].mean()
                metrics['consistency_score'] = max(0, avg_correlation * 100)
        
        # 可靠性评分 (基于数据完整性和分布合理性)
        reliability_factors = []
        
        for col in score_columns:
            scores = df[col].dropna()
            if len(scores) > 0:
                # 检查评分分布是否合理
                score_range = scores.max() - scores.min()
                score_std = scores.std()
                
                # 合理的标准差范围 (0.5-2.0)
                std_factor = min(1.0, max(0.0, (2.0 - abs(score_std - 1.25)) / 2.0))
                reliability_factors.append(std_factor)
        
        if reliability_factors:
            metrics['reliability_score'] = np.mean(reliability_factors) * 100
        
        return metrics
    
    def _calculate_quality_indicators(self, df: pd.DataFrame) -> Dict:
        """计算质量指标"""
        indicators = {
            'data_completeness': 0,
            'score_validity': 0,
            'distribution_health': {},
            'quality_grade': 'C'
        }
        
        # 数据完整性
        total_cells = df.shape[0] * df.shape[1]
        filled_cells = df.notna().sum().sum()
        indicators['data_completeness'] = (filled_cells / total_cells) * 100
        
        # 评分有效性
        score_columns = [col for col in df.columns if '评分' in col]
        valid_scores = 0
        total_scores = 0
        
        for col in score_columns:
            scores = df[col].dropna()
            # 移除硬编码的分数范围限制，所有数字都视为有效
            valid_count = scores.notna().sum()  # 统计非空的分数
            valid_scores += valid_count
            total_scores += len(scores)
        
        if total_scores > 0:
            indicators['score_validity'] = (valid_scores / total_scores) * 100
        
        # 分布健康度
        for col in score_columns:
            model_name = col.replace('_评分', '').replace('评分', '')
            scores = df[col].dropna()
            
            if len(scores) > 0:
                # 检查分布是否过于集中
                distribution = scores.value_counts()
                max_concentration = distribution.max() / len(scores)
                
                health_score = 100
                if max_concentration > 0.8:
                    health_score = 30  # 过于集中
                elif max_concentration > 0.6:
                    health_score = 60  # 较集中
                elif max_concentration < 0.1:
                    health_score = 70  # 过于分散
                
                indicators['distribution_health'][model_name] = health_score
        
        # 综合质量等级
        overall_score = (
            indicators['data_completeness'] * 0.3 +
            indicators['score_validity'] * 0.4 +
            np.mean(list(indicators['distribution_health'].values()) or [50]) * 0.3
        )
        
        if overall_score >= 90:
            indicators['quality_grade'] = 'A+'
        elif overall_score >= 85:
            indicators['quality_grade'] = 'A'
        elif overall_score >= 75:
            indicators['quality_grade'] = 'B'
        elif overall_score >= 65:
            indicators['quality_grade'] = 'C'
        else:
            indicators['quality_grade'] = 'D'
        
        return indicators
    
    def _compare_models(self, df: pd.DataFrame) -> Dict:
        """模型对比分析"""
        score_columns = [col for col in df.columns if '评分' in col]
        
        comparison = {
            'ranking': [],
            'performance_gaps': {},
            'strengths_weaknesses': {},
            'recommendation': ''
        }
        
        if len(score_columns) < 2:
            return comparison
        
        # 计算模型排名
        model_scores = {}
        for col in score_columns:
            model_name = col.replace('_评分', '').replace('评分', '')
            scores = df[col].dropna()
            if len(scores) > 0:
                model_scores[model_name] = {
                    'avg_score': scores.mean(),
                    'consistency': 1 / (scores.std() + 0.1),  # 一致性指标
                    'completion_rate': len(scores) / len(df)
                }
        
        # 综合评分排名
        for model, metrics in model_scores.items():
            composite_score = (
                metrics['avg_score'] * 0.6 +
                metrics['consistency'] * 0.2 +
                metrics['completion_rate'] * 5 * 0.2
            )
            comparison['ranking'].append({
                'model': model,
                'composite_score': composite_score,
                'avg_score': metrics['avg_score'],
                'consistency': metrics['consistency'],
                'completion_rate': metrics['completion_rate'] * 100
            })
        
        comparison['ranking'].sort(key=lambda x: x['composite_score'], reverse=True)
        
        # 性能差距分析
        if len(comparison['ranking']) >= 2:
            best = comparison['ranking'][0]
            worst = comparison['ranking'][-1]
            comparison['performance_gaps']['score_gap'] = best['avg_score'] - worst['avg_score']
            comparison['performance_gaps']['consistency_gap'] = best['consistency'] - worst['consistency']
        
        return comparison
    
    def _analyze_by_question_type(self, df: pd.DataFrame) -> Dict:
        """按题目类型分析"""
        if '类型' not in df.columns:
            return {'error': '缺少题目类型列'}
        
        type_analysis = {
            'type_distribution': {},
            'type_performance': {},
            'difficulty_ranking': []
        }
        
        # 类型分布
        type_counts = df['类型'].value_counts()
        type_analysis['type_distribution'] = type_counts.to_dict()
        
        # 各类型的性能表现
        score_columns = [col for col in df.columns if '评分' in col]
        
        for question_type in df['类型'].unique():
            if pd.isna(question_type):
                continue
                
            type_data = df[df['类型'] == question_type]
            type_performance = {}
            
            for col in score_columns:
                model_name = col.replace('_评分', '').replace('评分', '')
                scores = type_data[col].dropna()
                
                if len(scores) > 0:
                    type_performance[model_name] = {
                        'avg_score': float(scores.mean()),
                        'question_count': len(scores),
                        'difficulty_level': self._calculate_difficulty(scores)
                    }
            
            type_analysis['type_performance'][question_type] = type_performance
            
            # 计算整体难度
            all_scores = []
            for col in score_columns:
                all_scores.extend(type_data[col].dropna().tolist())
            
            if all_scores:
                avg_difficulty = np.mean(all_scores)
                type_analysis['difficulty_ranking'].append({
                    'type': question_type,
                    'difficulty_score': avg_difficulty,
                    'question_count': len(type_data)
                })
        
        # 按难度排序
        type_analysis['difficulty_ranking'].sort(key=lambda x: x['difficulty_score'])
        
        return type_analysis
    
    def _analyze_time_efficiency(self, evaluation_data: Dict = None) -> Dict:
        """分析时间效率"""
        time_analysis = {
            'total_duration': '未知',
            'average_per_question': '未知',
            'efficiency_rating': '未评级',
            'bottlenecks': [],
            'optimization_suggestions': [],
            'data_source': 'unknown'
        }
        
        if not evaluation_data:
            time_analysis['data_source'] = 'no_data'
            time_analysis['optimization_suggestions'].append('建议记录评测开始和结束时间以获得准确的效率分析')
            return time_analysis
        
        start_time = evaluation_data.get('start_time')
        end_time = evaluation_data.get('end_time')
        is_estimated = evaluation_data.get('is_estimated', False)
        
        if start_time and end_time:
            try:
                # 处理ISO格式时间字符串
                if isinstance(start_time, str):
                    # 移除时区信息并解析
                    start_time_clean = start_time.replace('Z', '').replace('+00:00', '')
                    if '.' in start_time_clean:
                        start_dt = datetime.fromisoformat(start_time_clean.split('.')[0])
                    else:
                        start_dt = datetime.fromisoformat(start_time_clean)
                else:
                    start_dt = start_time
                
                if isinstance(end_time, str):
                    end_time_clean = end_time.replace('Z', '').replace('+00:00', '')
                    if '.' in end_time_clean:
                        end_dt = datetime.fromisoformat(end_time_clean.split('.')[0])
                    else:
                        end_dt = datetime.fromisoformat(end_time_clean)
                else:
                    end_dt = end_time
                
                duration = end_dt - start_dt
                total_seconds = duration.total_seconds()
                question_count = evaluation_data.get('question_count', 1)
                
                # 设置数据源标识
                time_analysis['data_source'] = 'estimated' if is_estimated else 'actual'
                
                # 格式化时长显示
                if total_seconds < 60:
                    time_analysis['total_duration'] = f"{total_seconds:.0f}秒"
                elif total_seconds < 3600:
                    minutes = total_seconds // 60
                    seconds = total_seconds % 60
                    time_analysis['total_duration'] = f"{minutes:.0f}分{seconds:.0f}秒"
                else:
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    time_analysis['total_duration'] = f"{hours:.0f}小时{minutes:.0f}分"
                
                avg_time = total_seconds / question_count
                time_analysis['average_per_question'] = f"{avg_time:.1f}秒"
                
                # 效率评级（根据是否为估算数据调整标准）
                if is_estimated:
                    time_analysis['efficiency_rating'] = '估算数据'
                    time_analysis['optimization_suggestions'].append('数据为基于文件时间的估算，建议记录实际评测时间以获得准确分析')
                else:
                    if avg_time < 10:
                        time_analysis['efficiency_rating'] = '优秀'
                    elif avg_time < 30:
                        time_analysis['efficiency_rating'] = '良好'
                    elif avg_time < 60:
                        time_analysis['efficiency_rating'] = '一般'
                    else:
                        time_analysis['efficiency_rating'] = '需要优化'
                        time_analysis['bottlenecks'].append('处理时间过长')
                        time_analysis['optimization_suggestions'].append('考虑并行处理或优化API调用')
                
                # 根据总时长给出建议
                if total_seconds > 3600:  # 超过1小时
                    time_analysis['bottlenecks'].append('总评测时间过长')
                    time_analysis['optimization_suggestions'].append('考虑批量处理或分批评测')
                
            except Exception as e:
                print(f"时间分析错误: {e}")
                time_analysis['data_source'] = 'error'
                time_analysis['optimization_suggestions'].append(f'时间数据解析错误: {str(e)}')
        else:
            time_analysis['data_source'] = 'incomplete'
            time_analysis['optimization_suggestions'].append('缺少完整的开始或结束时间信息')
        
        return time_analysis
    
    def _generate_recommendations(self, df: pd.DataFrame) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        score_columns = [col for col in df.columns if '评分' in col]
        
        # 数据质量建议
        completion_rate = df[score_columns].notna().mean().mean()
        if completion_rate < 0.9:
            recommendations.append("建议提高数据完整性，确保所有题目都得到评分")
        
        # 评分分布建议
        for col in score_columns:
            scores = df[col].dropna()
            if len(scores) > 0:
                model_name = col.replace('_评分', '').replace('评分', '')
                
                # 检查分布集中度
                distribution = scores.value_counts()
                max_concentration = distribution.max() / len(scores)
                
                if max_concentration > 0.7:
                    recommendations.append(f"{model_name}的评分过于集中，建议检查评测标准")
                
                # 检查评分范围
                score_range = scores.max() - scores.min()
                if score_range < 2:
                    recommendations.append(f"{model_name}的评分范围较窄，建议使用更细粒度的评分标准")
        
        # 模型对比建议
        if len(score_columns) > 1:
            model_means = {col: df[col].dropna().mean() for col in score_columns}
            best_model = max(model_means, key=model_means.get)
            worst_model = min(model_means, key=model_means.get)
            
            gap = model_means[best_model] - model_means[worst_model]
            if gap > 1.0:
                recommendations.append(f"模型性能差异较大，建议重点优化{worst_model.replace('_评分', '')}")
        
        return recommendations
    
    def _create_histogram_data(self, scores: pd.Series) -> Dict:
        """创建直方图数据"""
        bins = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        hist, _ = np.histogram(scores, bins=bins)
        
        return {
            'bins': ['1分', '2分', '3分', '4分', '5分'],
            'counts': hist.tolist()
        }
    
    def _detect_outliers(self, scores: pd.Series, questions: pd.Series = None) -> List[Tuple]:
        """检测异常值"""
        outliers = []
        
        Q1 = scores.quantile(0.25)
        Q3 = scores.quantile(0.75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        outlier_mask = (scores < lower_bound) | (scores > upper_bound)
        outlier_indices = scores[outlier_mask].index
        
        for idx in outlier_indices:
            question_text = questions.iloc[idx] if questions is not None else f"题目{idx+1}"
            outliers.append((idx, scores.iloc[idx], question_text))
        
        return outliers
    
    def _calculate_difficulty(self, scores: pd.Series) -> str:
        """计算题目难度等级"""
        avg_score = scores.mean()
        
        if avg_score >= 4.5:
            return '简单'
        elif avg_score >= 3.5:
            return '中等'
        elif avg_score >= 2.5:
            return '困难'
        else:
            return '极难'

# 创建全局分析器实例
analytics = AdvancedAnalytics()
