"""
DataLink 认证服务模块

负责处理与 DataLink 认证服务器的交互
"""

import requests
import webbrowser
import time
from typing import Optional, Dict, Callable
from urllib.parse import urlencode


class AuthService:
    """DataLink 认证服务"""
    
    def __init__(self, base_url: str, auth_frontend_url: str = None, timeout: int = 60):
        """
        初始化认证服务
        
        Args:
            base_url: DataLink API 基础地址（例如：http://localhost:8080/api）
            auth_frontend_url: 认证前端页面地址
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        # 认证服务器是统一的，不区分频道
        # 始终使用生产环境的认证服务器地址
        self.auth_url = "https://datalink.orca3d.cn:8081/auth/v1"
        
        # 认证前端页面地址
        if auth_frontend_url:
            self.auth_frontend_url = auth_frontend_url
        else:
            # 认证前端页面和认证服务在同一个服务器
            self.auth_frontend_url = "https://datalink.orca3d.cn:8081/auth/v1/frontend"
    
    def get_nonce(self) -> Optional[str]:
        """
        获取认证 nonce
        
        Returns:
            nonce 字符串，失败返回 None
        """
        try:
            url = f"{self.auth_url}/nonce/"
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('nonce')
            
            print(f"获取 nonce 失败: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            print(f"获取 nonce 失败: {e}")
            return None
    
    def verify_nonce(self, nonce: str, max_retries: int = 60, retry_interval: float = 2.0) -> Optional[Dict[str, str]]:
        """
        验证 nonce 并获取 token（轮询方式）
        
        Args:
            nonce: 要验证的 nonce
            max_retries: 最大重试次数
            retry_interval: 重试间隔（秒）
        
        Returns:
            包含 username, accessToken, refreshToken 的字典，失败返回 None
        """
        try:
            url = f"{self.auth_url}/nonce/verify/"
            
            for i in range(max_retries):
                try:
                    response = requests.post(
                        url,
                        json={'nonce': nonce},
                        timeout=self.timeout
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        return {
                            'username': data.get('username'),
                            'access_token': data.get('accessToken'),
                            'refresh_token': data.get('refreshToken')
                        }
                    
                    # 如果还未授权，继续等待
                    if i < max_retries - 1:
                        time.sleep(retry_interval)
                    
                except requests.exceptions.Timeout:
                    if i < max_retries - 1:
                        time.sleep(retry_interval)
                    continue
            
            print(f"验证 nonce 超时（尝试 {max_retries} 次）")
            return None
            
        except Exception as e:
            print(f"验证 nonce 失败: {e}")
            return None
    
    def open_auth_page(self, nonce: str, redirect_url: str = "http://127.0.0.1:34511/") -> bool:
        """
        在浏览器中打开认证页面
        
        Args:
            nonce: 认证 nonce
            redirect_url: 认证完成后的重定向地址
        
        Returns:
            是否成功打开浏览器
        """
        try:
            # 构造认证URL
            # server 参数应该指向 API 服务器
            # 如果是本地开发，使用生产环境的 API 服务器
            if 'localhost' in self.base_url or '127.0.0.1' in self.base_url:
                # 本地开发时，使用生产环境的 API 服务器
                server_url = "datalink.orca3d.cn:7000"
            else:
                # 生产环境时，使用配置的服务器
                server_url = self.base_url.replace('/api', '').replace('https://', '').replace('http://', '')
            
            params = {
                'server': server_url,
                'nonce': nonce,
                'next': redirect_url
            }
            
            auth_url = f"{self.auth_frontend_url}/?{urlencode(params)}"
            
            # 打开浏览器
            webbrowser.open(auth_url)
            return True
            
        except Exception as e:
            print(f"打开浏览器失败: {e}")
            return False
    
    def authenticate(self, progress_callback: Optional[Callable[[str], None]] = None, window=None) -> Optional[Dict[str, str]]:
        """
        完整的认证流程
        
        Args:
            progress_callback: 进度回调函数
            window: AuthWindow 实例（用于更新进度）
        
        Returns:
            包含 username, access_token, refresh_token 的字典，失败返回 None
        """
        # 1. 获取 nonce
        msg = "正在获取认证 nonce..."
        if progress_callback:
            progress_callback(msg)
        if window:
            window.update_status(msg)
        
        nonce = self.get_nonce()
        if not nonce:
            msg = "获取 nonce 失败"
            if progress_callback:
                progress_callback(msg)
            if window:
                window.update_status(msg)
            return None
        
        # 2. 打开浏览器
        msg = "正在打开浏览器进行认证..."
        if progress_callback:
            progress_callback(msg)
        if window:
            window.update_status(msg)
        
        if not self.open_auth_page(nonce):
            msg = "无法打开浏览器"
            if progress_callback:
                progress_callback(msg)
            if window:
                window.update_status(msg)
            return None
        
        # 3. 等待用户完成认证
        msg = "请在浏览器中完成认证..."
        if progress_callback:
            progress_callback(msg)
        if window:
            window.update_status(msg)
        
        credentials = self.verify_nonce(nonce)
        
        if credentials:
            msg = f"认证成功: {credentials['username']}"
            if progress_callback:
                progress_callback(msg)
            if window:
                window.update_status(msg)
            return credentials
        else:
            msg = "认证失败或超时"
            if progress_callback:
                progress_callback(msg)
            if window:
                window.update_status(msg)
            return None
    
    def verify_token(self, username: str, access_token: str) -> bool:
        """
        验证 token 是否有效
        
        Args:
            username: 用户名
            access_token: 访问令牌
        
        Returns:
            token 是否有效
        """
        try:
            # 使用 DataLink 的 token 验证接口
            # auth_url 已经包含 /auth/v1，所以直接加 /verify/
            url = f"{self.auth_url}/verify/"
            response = requests.post(
                url,
                data={
                    'username': username,
                    'access_token': access_token
                },
                timeout=self.timeout
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"验证 token 失败: {e}")
            return False

