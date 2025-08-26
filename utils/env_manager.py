#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境变量管理工具
负责.env文件的读取、写入和更新
"""

import os
import re
from typing import Dict, Optional
from pathlib import Path

class EnvManager:
    """环境变量管理器"""
    
    def __init__(self, env_file: str = ".env"):
        """
        初始化环境变量管理器
        
        Args:
            env_file: .env文件路径，默认为项目根目录的.env
        """
        self.env_file = Path(env_file)
        self.project_root = Path(__file__).parent.parent
        self.env_path = self.project_root / self.env_file
        
    def load_env(self) -> Dict[str, str]:
        """
        加载.env文件中的环境变量
        
        Returns:
            字典格式的环境变量
        """
        env_vars = {}
        
        if not self.env_path.exists():
            print("💡 未找到.env文件，将使用环境变量或Web界面配置")
            return env_vars
            
        try:
            with open(self.env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释行
                    if not line or line.startswith('#'):
                        continue
                        
                    # 解析键值对
                    match = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$', line)
                    if match:
                        key, value = match.groups()
                        # 移除引号
                        value = value.strip('"\'')
                        env_vars[key] = value
                        
        except Exception as e:
            print(f"⚠️ 读取.env文件失败: {e}")
            
        return env_vars
    
    def save_env_var(self, key: str, value: str) -> bool:
        """
        保存单个环境变量到.env文件
        
        Args:
            key: 环境变量名
            value: 环境变量值
            
        Returns:
            是否保存成功
        """
        return self.save_env_vars({key: value})
    
    def save_env_vars(self, env_vars: Dict[str, str]) -> bool:
        """
        保存多个环境变量到.env文件
        
        Args:
            env_vars: 环境变量字典
            
        Returns:
            是否保存成功
        """
        try:
            # 读取现有内容
            existing_vars = self.load_env()
            existing_lines = []
            
            if self.env_path.exists():
                with open(self.env_path, 'r', encoding='utf-8') as f:
                    existing_lines = f.readlines()
            
            # 更新现有变量
            existing_vars.update(env_vars)
            
            # 准备新内容
            new_lines = []
            updated_keys = set()
            
            # 处理现有行，更新已存在的变量
            for line in existing_lines:
                stripped_line = line.strip()
                if not stripped_line or stripped_line.startswith('#'):
                    new_lines.append(line)
                    continue
                    
                match = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$', stripped_line)
                if match:
                    key = match.group(1)
                    if key in env_vars:
                        # 更新现有变量
                        new_lines.append(f'{key}="{env_vars[key]}"\n')
                        updated_keys.add(key)
                    else:
                        # 保持原有变量
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            
            # 添加新变量
            for key, value in env_vars.items():
                if key not in updated_keys:
                    new_lines.append(f'{key}="{value}"\n')
            
            # 写入文件
            with open(self.env_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
                
            # 更新当前进程的环境变量
            for key, value in env_vars.items():
                os.environ[key] = value
                
            print(f"✅ 已保存API密钥到 {self.env_path}")
            return True
            
        except Exception as e:
            print(f"❌ 保存.env文件失败: {e}")
            return False
    
    def get_env_var(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        获取环境变量值
        
        Args:
            key: 环境变量名
            default: 默认值
            
        Returns:
            环境变量值
        """
        # 优先从当前进程环境变量获取
        value = os.getenv(key)
        if value:
            return value
            
        # 从.env文件获取
        env_vars = self.load_env()
        return env_vars.get(key, default)
    
    def delete_env_var(self, key: str) -> bool:
        """
        删除环境变量
        
        Args:
            key: 环境变量名
            
        Returns:
            是否删除成功
        """
        try:
            if not self.env_path.exists():
                return True
                
            new_lines = []
            
            with open(self.env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped_line = line.strip()
                    if stripped_line and not stripped_line.startswith('#'):
                        match = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$', stripped_line)
                        if match and match.group(1) == key:
                            continue  # 跳过要删除的变量
                    new_lines.append(line)
            
            with open(self.env_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
                
            # 从当前进程环境变量中删除
            if key in os.environ:
                del os.environ[key]
                
            return True
            
        except Exception as e:
            print(f"❌ 删除环境变量失败: {e}")
            return False
    
    def get_env_file_path(self) -> str:
        """获取.env文件路径"""
        return str(self.env_path)
    
    def env_file_exists(self) -> bool:
        """检查.env文件是否存在"""
        return self.env_path.exists()

# 全局实例
env_manager = EnvManager()
