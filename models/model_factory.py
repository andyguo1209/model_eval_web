"""
模型工厂
统一管理和调度所有AI模型客户端
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional, Tuple
from .copilot_client import copilot_client
from .legacy_client import legacy_client


class ModelFactory:
    """模型工厂类"""
    
    def __init__(self):
        self.clients = {
            'copilot': copilot_client,
            'legacy': legacy_client
        }
    
    def get_all_models(self) -> Dict[str, Dict]:
        """获取所有支持的模型配置"""
        all_models = {}
        
        # 添加Legacy模型
        all_models.update(legacy_client.LEGACY_MODELS)
        
        # 添加Copilot模型  
        all_models.update(copilot_client.COPILOT_MODELS)
        
        return all_models
    
    def get_available_models(self) -> List[Dict]:
        """获取所有可用模型列表"""
        models = []
        
        # 获取Legacy模型
        models.extend(legacy_client.get_available_models())
        
        # 获取Copilot模型
        models.extend(copilot_client.get_available_models())
        
        return models
    
    def get_model_type(self, model_name: str) -> Optional[str]:
        """获取模型类型"""
        if legacy_client.is_legacy_model(model_name):
            return 'legacy'
        elif copilot_client.is_copilot_model(model_name):
            return 'copilot'
        return None
    
    def get_model_config(self, model_name: str) -> Optional[Dict]:
        """获取模型配置"""
        model_type = self.get_model_type(model_name)
        if model_type == 'legacy':
            return legacy_client.get_model_config(model_name)
        elif model_type == 'copilot':
            return copilot_client.get_model_config(model_name)
        return None
    
    def validate_model(self, model_name: str) -> Tuple[bool, str]:
        """验证模型是否可用"""
        model_type = self.get_model_type(model_name)
        if model_type == 'legacy':
            return legacy_client.validate_model(model_name)
        elif model_type == 'copilot':
            return copilot_client.validate_model(model_name)
        return False, f"不支持的模型: {model_name}"
    
    def validate_models(self, model_names: List[str]) -> Tuple[bool, str]:
        """批量验证模型"""
        for model_name in model_names:
            is_valid, error_msg = self.validate_model(model_name)
            if not is_valid:
                return False, error_msg
        return True, ""
    
    async def fetch_model_answer(self, session: aiohttp.ClientSession, query: str, 
                                model_name: str, idx: int, sem_model: asyncio.Semaphore, 
                                task_id: str, task_status: Dict = None, 
                                request_headers: Dict = None) -> str:
        """统一的模型答案获取入口"""
        
        model_type = self.get_model_type(model_name)
        
        if model_type == 'copilot':
            return await copilot_client.fetch_answer(
                session, query, model_name, idx, sem_model, task_id, task_status
            )
        elif model_type == 'legacy':
            return await legacy_client.fetch_answer(
                session, query, model_name, idx, sem_model, task_id, task_status, request_headers
            )
        else:
            return f"不支持的模型类型: {model_name}"
    
    async def get_multiple_model_answers(self, queries: List[str], selected_models: List[str], 
                                       task_id: str, task_status: Dict = None,
                                       request_headers: Dict = None) -> Dict[str, List[str]]:
        """获取多个模型的答案"""
        connector = aiohttp.TCPConnector(limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=60)
        sem_model = asyncio.Semaphore(5)  # 控制并发数

        results = {model: [] for model in selected_models}
        
        if task_status and task_id in task_status:
            task_status[task_id].total = len(queries) * len(selected_models)
            task_status[task_id].status = "获取模型答案中"

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # 为每个模型创建任务
            for model_name in selected_models:
                # 验证模型是否支持
                if not self.get_model_type(model_name):
                    continue
                    
                tasks = []
                
                for i, query in enumerate(queries):
                    tasks.append(self.fetch_model_answer(
                        session, query, model_name, i, sem_model, task_id, task_status, request_headers
                    ))
                
                # 获取该模型的所有答案
                answers = await asyncio.gather(*tasks)
                results[model_name] = answers

        return results


# 创建全局模型工厂实例
model_factory = ModelFactory()
