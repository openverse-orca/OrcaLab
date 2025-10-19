#!/usr/bin/env python3
"""
测试 OrcaLab 启动流程中的资产同步功能

这个脚本模拟 run.py 中的资产同步部分，但不启动 GUI
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from orcalab.config_service import ConfigService
from orcalab.project_util import check_project_folder, copy_packages, get_cache_folder
from orcalab.asset_sync_service import sync_assets


def main():
    print("=" * 70)
    print("  OrcaLab 启动流程资产同步测试")
    print("=" * 70)
    print()
    
    # 1. 检查项目文件夹
    print("📁 检查项目文件夹...")
    check_project_folder()
    print("✅ 项目文件夹检查完成")
    print()
    
    # 2. 加载配置
    print("⚙️  加载配置文件...")
    config_service = ConfigService()
    config_service.init_config(os.path.dirname(__file__))
    print("✅ 配置加载完成")
    print()
    
    # 3. 显示配置信息
    print("📋 配置信息:")
    print(f"   - DataLink 用户名: {config_service.datalink_username()}")
    print(f"   - DataLink API: {config_service.datalink_base_url()}")
    print(f"   - 启用同步: {config_service.datalink_enable_sync()}")
    print(f"   - 配置的 paks: {len(config_service.paks())} 个")
    print(f"   - 缓存目录: {get_cache_folder()}")
    print()
    
    # 4. 复制配置的 pak 包
    if config_service.init_paks() and config_service.paks():
        print("📦 复制配置的 pak 包...")
        copy_packages(config_service.paks())
        print("✅ pak 包复制完成")
        print()
    else:
        print("ℹ️  跳过 pak 包复制")
        print()
    
    # 5. 执行资产同步
    print("🔄 开始资产同步...")
    if not sync_assets(config_service):
        print("⚠️  资产同步失败，但程序将继续启动")
        print("   如果需要使用订阅的资产包，请检查网络连接和认证配置")
    else:
        print("✅ 资产同步完成")
    
    print()
    print("=" * 70)
    print("  启动流程资产同步测试完成")
    print("=" * 70)
    print()
    print("提示：实际启动 OrcaLab 时，资产同步会在这个位置自动执行。")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

