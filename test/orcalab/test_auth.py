#!/usr/bin/env python3
"""
测试 DataLink 认证功能

用法：
    python test_auth.py
"""

import sys
from orcalab.token_storage import TokenStorage
from orcalab.auth_service import AuthService
from orcalab.config_service import ConfigService


def test_token_storage():
    """测试 Token 存储功能"""
    print("=" * 60)
    print("测试 Token 存储功能")
    print("=" * 60)
    
    # 1. 检查现有 token
    print("\n1. 检查现有 token...")
    token_data = TokenStorage.load_token()
    if token_data:
        print(f"✓ 找到现有 token")
        print(f"  用户名: {token_data.get('username')}")
        print(f"  保存时间: {token_data.get('saved_at')}")
    else:
        print("✗ 没有找到现有 token")
    
    # 2. 测试保存和加载
    print("\n2. 测试保存和加载...")
    test_username = "test_user"
    test_token = "test_token_12345"
    
    if TokenStorage.save_token(test_username, test_token):
        print("✓ Token 保存成功")
    else:
        print("✗ Token 保存失败")
        return False
    
    loaded_data = TokenStorage.load_token()
    if loaded_data and loaded_data['username'] == test_username:
        print("✓ Token 加载成功")
    else:
        print("✗ Token 加载失败")
        return False
    
    # 3. 恢复原始 token
    print("\n3. 恢复原始 token...")
    if token_data:
        TokenStorage.save_token(
            token_data['username'],
            token_data['access_token'],
            token_data.get('refresh_token')
        )
        print("✓ 已恢复原始 token")
    else:
        TokenStorage.clear_token()
        print("✓ 已清除测试 token")
    
    return True


def test_config_service():
    """测试配置服务"""
    print("\n" + "=" * 60)
    print("测试配置服务")
    print("=" * 60)
    
    import os
    
    # 初始化配置服务
    config_service = ConfigService()
    config_service.init_config(os.path.dirname(__file__))
    
    print("\n1. DataLink 配置信息:")
    print(f"  Base URL: {config_service.datalink_base_url()}")
    print(f"  Enable Sync: {config_service.datalink_enable_sync()}")
    print(f"  Timeout: {config_service.datalink_timeout()}")
    
    print("\n2. 认证信息:")
    username = config_service.datalink_username()
    token = config_service.datalink_token()
    
    if username:
        print(f"  ✓ 用户名: {username}")
    else:
        print(f"  ✗ 未找到用户名")
    
    if token:
        print(f"  ✓ Token: {token[:20]}... (已截断)")
    else:
        print(f"  ✗ 未找到 token")
    
    return True


def test_auth_service():
    """测试认证服务（不实际执行认证）"""
    print("\n" + "=" * 60)
    print("测试认证服务")
    print("=" * 60)
    
    import os
    
    # 初始化配置
    config_service = ConfigService()
    config_service.init_config(os.path.dirname(__file__))
    
    base_url = config_service.datalink_base_url()
    print(f"\n1. 创建认证服务 (base_url: {base_url})")
    
    auth_service = AuthService(base_url)
    print(f"  ✓ 认证服务创建成功")
    print(f"  Auth URL: {auth_service.auth_url}")
    print(f"  Auth Frontend URL: {auth_service.auth_frontend_url}")
    
    # 验证 URL 构造是否正确（认证服务器是统一的）
    expected_auth_url = "https://datalink.orca3d.cn:8081/auth/v1"
    expected_frontend_url = "https://datalink.orca3d.cn:8081/auth/v1/frontend"
    
    if auth_service.auth_url == expected_auth_url:
        print(f"  ✓ Auth URL 构造正确（使用统一认证服务器）")
    else:
        print(f"  ✗ Auth URL 构造错误：期望 {expected_auth_url}，实际 {auth_service.auth_url}")
        return False
    
    if auth_service.auth_frontend_url == expected_frontend_url:
        print(f"  ✓ Auth Frontend URL 构造正确")
    else:
        print(f"  ✗ Auth Frontend URL 构造错误：期望 {expected_frontend_url}，实际 {auth_service.auth_frontend_url}")
        return False
    
    # 测试 token 验证
    print("\n2. 测试 token 验证...")
    username = config_service.datalink_username()
    token = config_service.datalink_token()
    
    if username and token:
        print(f"  正在验证 token for {username}...")
        is_valid = auth_service.verify_token(username, token)
        if is_valid:
            print(f"  ✓ Token 有效")
        else:
            print(f"  ✗ Token 无效或已过期")
    else:
        print(f"  ⚠ 跳过验证（没有 username 或 token）")
    
    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("OrcaLab DataLink 认证系统测试")
    print("=" * 60)
    
    try:
        # 测试 Token 存储
        if not test_token_storage():
            print("\n✗ Token 存储测试失败")
            return 1
        
        # 测试配置服务
        if not test_config_service():
            print("\n✗ 配置服务测试失败")
            return 1
        
        # 测试认证服务
        if not test_auth_service():
            print("\n✗ 认证服务测试失败")
            return 1
        
        print("\n" + "=" * 60)
        print("✓ 所有测试通过")
        print("=" * 60)
        
        print("\n提示：")
        print("- Token 存储位置: ~/Orca/orcalab_token.json")
        print("- 如需重新认证，删除该文件后重启 OrcaLab")
        print("- 启动 OrcaLab 时会自动检测 token 并弹出登录窗口")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

