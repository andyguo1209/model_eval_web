"""
高级分析API路由
提供详细的统计分析和可视化数据接口
"""

from flask import Blueprint, jsonify, request
from utils.advanced_analytics import analytics
import os

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')

@analytics_bp.route('/result/<result_id>')
def get_result_analysis(result_id):
    """获取特定结果的详细分析"""
    try:
        from history_manager import history_manager
        
        # 获取结果详情
        detail = history_manager.get_result_detail(result_id)
        if not detail['success']:
            return jsonify({'error': '结果不存在'}), 404
        
        result_file = detail['result']['result_file']
        
        # 构建评测数据
        evaluation_data = {
            'start_time': detail['result'].get('start_time'),
            'end_time': detail['result'].get('end_time'),
            'question_count': detail['result'].get('total_rows', 0)
        }
        
        # 执行分析
        analysis = analytics.analyze_evaluation_results(result_file, evaluation_data)
        
        return jsonify(analysis)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/compare')
def compare_results():
    """对比多个评测结果"""
    try:
        result_ids = request.args.getlist('result_ids')
        
        if len(result_ids) < 2:
            return jsonify({'error': '至少需要两个结果进行对比'}), 400
        
        from history_manager import history_manager
        comparison_data = []
        
        for result_id in result_ids:
            detail = history_manager.get_result_detail(result_id)
            if detail['success']:
                result_file = detail['result']['result_file']
                evaluation_data = {
                    'start_time': detail['result'].get('start_time'),
                    'end_time': detail['result'].get('end_time'),
                    'question_count': detail['result'].get('total_rows', 0)
                }
                
                analysis = analytics.analyze_evaluation_results(result_file, evaluation_data)
                if analysis.get('success'):
                    comparison_data.append({
                        'result_id': result_id,
                        'name': detail['result']['name'],
                        'analysis': analysis['analysis']
                    })
        
        # 生成对比报告
        comparison_report = generate_comparison_report(comparison_data)
        
        return jsonify({
            'success': True,
            'comparison': comparison_report
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/performance_trends')
def get_performance_trends():
    """获取性能趋势分析"""
    try:
        from history_manager import history_manager
        
        # 获取最近的评测记录
        history = history_manager.get_history_list(limit=50)
        
        if not history['success']:
            return jsonify({'error': '获取历史数据失败'}), 500
        
        trends = analyze_performance_trends(history['results'])
        
        return jsonify({
            'success': True,
            'trends': trends
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_comparison_report(comparison_data):
    """生成对比报告"""
    if len(comparison_data) < 2:
        return {'error': '数据不足'}
    
    report = {
        'summary': {},
        'performance_comparison': {},
        'efficiency_comparison': {},
        'quality_comparison': {},
        'recommendations': []
    }
    
    # 性能对比
    performance_scores = []
    for item in comparison_data:
        analysis = item['analysis']
        score_analysis = analysis.get('score_analysis', {})
        model_performance = score_analysis.get('model_performance', {})
        
        if model_performance:
            avg_scores = [perf['mean_score'] for perf in model_performance.values()]
            if avg_scores:
                performance_scores.append({
                    'name': item['name'],
                    'average_score': sum(avg_scores) / len(avg_scores)
                })
    
    report['performance_comparison'] = sorted(performance_scores, 
                                            key=lambda x: x['average_score'], 
                                            reverse=True)
    
    # 效率对比
    efficiency_scores = []
    for item in comparison_data:
        analysis = item['analysis']
        performance_metrics = analysis.get('performance_metrics', {})
        
        efficiency_scores.append({
            'name': item['name'],
            'efficiency_score': performance_metrics.get('efficiency_score', 0),
            'time_per_question': performance_metrics.get('estimated_time_per_question', '未知')
        })
    
    report['efficiency_comparison'] = efficiency_scores
    
    # 质量对比
    quality_scores = []
    for item in comparison_data:
        analysis = item['analysis']
        quality_indicators = analysis.get('quality_indicators', {})
        
        quality_scores.append({
            'name': item['name'],
            'quality_grade': quality_indicators.get('quality_grade', 'C'),
            'data_completeness': quality_indicators.get('data_completeness', 0)
        })
    
    report['quality_comparison'] = quality_scores
    
    return report

def analyze_performance_trends(results):
    """分析性能趋势"""
    trends = {
        'score_trends': [],
        'efficiency_trends': [],
        'quality_trends': [],
        'insights': []
    }
    
    # 按时间排序
    sorted_results = sorted(results, key=lambda x: x['created_at'])
    
    # 分析评分趋势
    for result in sorted_results[-10:]:  # 最近10个结果
        if result.get('result_summary'):
            summary = result['result_summary']
            model_scores = summary.get('model_scores', {})
            
            if model_scores:
                avg_scores = [score['avg_score'] for score in model_scores.values()]
                if avg_scores:
                    trends['score_trends'].append({
                        'date': result['created_at'][:10],
                        'average_score': sum(avg_scores) / len(avg_scores),
                        'name': result['name']
                    })
    
    # 生成洞察
    if len(trends['score_trends']) >= 3:
        recent_scores = [item['average_score'] for item in trends['score_trends'][-3:]]
        early_scores = [item['average_score'] for item in trends['score_trends'][:3]]
        
        if sum(recent_scores) / len(recent_scores) > sum(early_scores) / len(early_scores):
            trends['insights'].append('模型性能呈上升趋势')
        else:
            trends['insights'].append('模型性能需要关注')
    
    return trends
