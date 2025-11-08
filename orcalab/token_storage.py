"""
Token 存储管理模块

负责 DataLink 认证 token 的本地存储和读取
Token 存储在 ~/Orca/orcalab_token.json
"""

import json
import pathlib
import os
from typing import Optional, Dict
from datetime import datetime
import logging


logger = logging.getLogger(__name__)


class TokenStorage:
    """Token 存储管理器"""
    
    TOKEN_FILE = pathlib.Path(os.path.expanduser("~/Orca/orcalab_token.json"))
    
    @classmethod
    def save_token(cls, username: str, access_token: str, refresh_token: Optional[str] = None) -> bool:
        """
        保存 token 到本地
        
        Args:
            username: 用户名
            access_token: 访问令牌
            refresh_token: 刷新令牌（可选）
        
        Returns:
            是否保存成功
        """
        try:
            data = {
                'username': username,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'saved_at': datetime.now().isoformat()
            }
            
            with open(cls.TOKEN_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.exception("保存 token 失败: %s", e)
            return False
    
    @classmethod
    def load_token(cls) -> Optional[Dict[str, str]]:
        """
        从本地加载 token
        
        Returns:
            包含 username, access_token, refresh_token 的字典，如果不存在则返回 None
        """
        try:
            if not cls.TOKEN_FILE.exists():
                return None
            
            with open(cls.TOKEN_FILE, 'r') as f:
                data = json.load(f)
            
            # 验证数据完整性
            if 'username' in data and 'access_token' in data:
                return {
                    'username': data['username'],
                    'access_token': data['access_token'],
                    'refresh_token': data.get('refresh_token'),
                    'saved_at': data.get('saved_at')
                }
            
            return None
            
        except Exception as e:
            logger.exception("加载 token 失败: %s", e)
            return None
    
    @classmethod
    def clear_token(cls) -> bool:
        """
        清除本地 token
        
        Returns:
            是否清除成功
        """
        try:
            if cls.TOKEN_FILE.exists():
                cls.TOKEN_FILE.unlink()
            return True
            
        except Exception as e:
            logger.exception("清除 token 失败: %s", e)
            return False
    
    @classmethod
    def has_token(cls) -> bool:
        """
        检查是否存在有效的 token
        
        Returns:
            是否存在 token
        """
        token_data = cls.load_token()
        return token_data is not None

