#!/usr/bin/env python3
"""
测试资产同步进度窗口

这个脚本单独测试同步进度窗口的显示和交互
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from PySide6 import QtWidgets
from orcalab.config_service import ConfigService
from orcalab.asset_sync_ui import run_asset_sync_ui


def main():
    print("=" * 70)
    print("  测试资产同步进度窗口")
    print("=" * 70)
    print()
    
    # 加载配置
    print("加载配置...")
    config_service = ConfigService()
    config_service.init_config(os.path.dirname(__file__))
    
    # 检查认证信息
    if not config_service.datalink_username() or not config_service.datalink_token():
        print("❌ DataLink 认证信息未配置")
        print("   请在 orca.config.user.toml 中配置 username 和 token")
        return 1
    
    print(f"用户名: {config_service.datalink_username()}")
    print(f"API: {config_service.datalink_base_url()}")
    print()
    
    # 创建 Qt 应用
    app = QtWidgets.QApplication(sys.argv)
    
    # 运行同步（带UI）
    print("显示同步进度窗口...")
    sync_result = run_asset_sync_ui(config_service)
    
    print()
    print("=" * 70)
    if sync_result:
        print("✅ 同步完成！")
    else:
        print("❌ 同步失败！")
    print("=" * 70)
    
    return 0 if sync_result else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

