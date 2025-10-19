#!/usr/bin/env python3
"""
OrcaLab 资产同步功能测试

测试场景：
1. 测试查询订阅列表
2. 测试检查本地文件
3. 测试下载缺失的资产包
4. 测试清理不需要的pak文件
5. 测试完整同步流程

使用方法：
    python test_asset_sync.py --username <用户名> --token <访问令牌>

示例：
    export TEST_USERNAME=your_username
    export TEST_TOKEN=your_token
    python test_asset_sync.py
"""

import argparse
import os
import sys
import shutil
import pathlib
from typing import List

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from orcalab.asset_sync_service import AssetSyncService


class TestAssetSync:
    """资产同步测试类"""
    
    def __init__(self, username: str, token: str, base_url: str = "http://localhost:8080/api"):
        self.username = username
        self.token = token
        self.base_url = base_url
        self.test_dir = pathlib.Path(__file__).parent / "test_cache"
        self.test_passed = 0
        self.test_failed = 0
        
    def setup(self):
        """测试前准备"""
        print("=" * 70)
        print("🧪 OrcaLab 资产同步测试")
        print("=" * 70)
        print(f"用户名: {self.username}")
        print(f"API地址: {self.base_url}")
        print(f"测试目录: {self.test_dir}")
        print()
        
        # 创建测试目录
        self.test_dir.mkdir(parents=True, exist_ok=True)
    
    def teardown(self, auto_cleanup=False):
        """测试后清理"""
        print("\n" + "=" * 70)
        print("🧹 清理测试环境")
        print("=" * 70)
        
        # 询问是否保留测试文件
        try:
            if auto_cleanup:
                keep = 'n'
            else:
                keep = input("是否保留测试下载的文件？(y/n) [n]: ").strip().lower()
            
            if keep != 'y':
                if self.test_dir.exists():
                    shutil.rmtree(self.test_dir)
                    print(f"✅ 已删除测试目录: {self.test_dir}")
            else:
                print(f"ℹ️  保留测试目录: {self.test_dir}")
        except (KeyboardInterrupt, EOFError):
            print("\n跳过清理")
    
    def print_test_header(self, test_name: str):
        """打印测试标题"""
        print("\n" + "-" * 70)
        print(f"🧪 测试: {test_name}")
        print("-" * 70)
    
    def assert_true(self, condition: bool, message: str):
        """断言为真"""
        if condition:
            print(f"✅ PASS: {message}")
            self.test_passed += 1
        else:
            print(f"❌ FAIL: {message}")
            self.test_failed += 1
    
    def assert_not_none(self, value, message: str):
        """断言不为None"""
        self.assert_true(value is not None, message)
    
    def test_query_subscribed_packages(self, sync_service: AssetSyncService):
        """测试查询订阅列表"""
        self.print_test_header("查询订阅的资产包列表")
        
        packages = sync_service.query_subscribed_packages()
        
        self.assert_not_none(packages, "能够成功查询订阅列表")
        
        if packages is not None:
            self.assert_true(isinstance(packages, list), "返回的是列表类型")
            print(f"ℹ️  订阅的资产包数量: {len(packages)}")
            
            if packages:
                pkg = packages[0]
                self.assert_true('id' in pkg, "资产包包含 id 字段")
                self.assert_true('name' in pkg, "资产包包含 name 字段")
                self.assert_true('size' in pkg, "资产包包含 size 字段")
                
                # 检查文件名（兼容驼峰和下划线）
                has_file_name = 'fileName' in pkg or 'file_name' in pkg
                self.assert_true(has_file_name, "资产包包含 fileName 或 file_name 字段")
        
        return packages
    
    def test_check_local_packages(self, sync_service: AssetSyncService, packages: List):
        """测试检查本地文件"""
        self.print_test_header("检查本地资产包")
        
        if not packages:
            print("⚠️  没有订阅的资产包，跳过此测试")
            return []
        
        missing = sync_service.check_local_packages(packages)
        
        self.assert_not_none(missing, "能够成功检查本地文件")
        self.assert_true(isinstance(missing, list), "返回的是列表类型")
        
        print(f"ℹ️  缺失的资产包数量: {len(missing)}")
        
        return missing
    
    def test_download_package(self, sync_service: AssetSyncService, packages: List):
        """测试下载资产包"""
        self.print_test_header("下载资产包")
        
        if not packages:
            print("⚠️  没有需要下载的资产包，跳过此测试")
            return
        
        # 只测试第一个资产包
        pkg = packages[0]
        package_id = pkg['id']
        file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")
        
        print(f"测试下载: {pkg['name']} ({file_name})")
        
        # 获取下载链接
        download_info = sync_service.get_download_url(package_id)
        self.assert_not_none(download_info, "能够获取下载链接")
        
        if download_info:
            download_url = download_info.get('downloadUrl') or download_info.get('download_url')
            size = download_info.get('size')
            
            self.assert_not_none(download_url, "下载链接不为空")
            self.assert_not_none(size, "文件大小不为空")
            
            # 执行下载
            if download_url and size:
                success = sync_service.download_package(package_id, file_name, download_url, size)
                self.assert_true(success, "下载成功")
                
                # 验证文件存在
                local_path = sync_service.cache_folder / file_name
                self.assert_true(local_path.exists(), "下载的文件存在于本地")
                
                if local_path.exists():
                    actual_size = local_path.stat().st_size
                    print(f"ℹ️  文件大小: {actual_size} bytes (预期: {size} bytes)")
    
    def test_clean_unsubscribed_packages(self, sync_service: AssetSyncService, packages: List):
        """测试清理不需要的pak文件"""
        self.print_test_header("清理不需要的资产包")
        
        # 创建一个测试用的pak文件（模拟不在订阅列表中的文件）
        test_pak = sync_service.cache_folder / "test_unsubscribed.pak"
        test_pak.write_text("test content")
        
        self.assert_true(test_pak.exists(), "创建测试pak文件成功")
        
        # 收集订阅的文件名
        subscribed_file_names = set()
        for pkg in packages:
            file_name = pkg.get('fileName') or pkg.get('file_name', f"{pkg['id']}.pak")
            subscribed_file_names.add(file_name)
        
        # 执行清理
        sync_service.clean_unsubscribed_packages(subscribed_file_names)
        
        # 验证测试文件被删除
        self.assert_true(not test_pak.exists(), "不在订阅列表中的pak文件被删除")
    
    def test_full_sync(self, sync_service: AssetSyncService):
        """测试完整同步流程"""
        self.print_test_header("完整同步流程")
        
        success = sync_service.sync_packages()
        self.assert_true(success, "完整同步流程执行成功")
    
    def run_all_tests(self, auto_cleanup=False):
        """运行所有测试"""
        self.setup()
        
        try:
            # 创建同步服务
            sync_service = AssetSyncService(
                username=self.username,
                access_token=self.token,
                base_url=self.base_url,
                cache_folder=self.test_dir,
                config_paks=[],  # 测试时不使用配置的pak
                timeout=60
            )
            
            # 测试1: 查询订阅列表
            packages = self.test_query_subscribed_packages(sync_service)
            
            # 测试2: 检查本地文件
            if packages is not None:
                missing = self.test_check_local_packages(sync_service, packages)
                
                # 测试3: 下载资产包（只测试第一个）
                if missing:
                    self.test_download_package(sync_service, missing[:1])
                
                # 测试4: 清理不需要的pak文件
                self.test_clean_unsubscribed_packages(sync_service, packages)
            
            # 测试5: 完整同步流程（重新创建测试目录）
            if self.test_dir.exists():
                shutil.rmtree(self.test_dir)
            self.test_dir.mkdir(parents=True, exist_ok=True)
            
            sync_service_full = AssetSyncService(
                username=self.username,
                access_token=self.token,
                base_url=self.base_url,
                cache_folder=self.test_dir,
                config_paks=[],
                timeout=60
            )
            self.test_full_sync(sync_service_full)
            
        except Exception as e:
            print(f"\n❌ 测试过程中出现异常: {e}")
            import traceback
            traceback.print_exc()
            self.test_failed += 1
        finally:
            self.print_results()
            self.teardown(auto_cleanup=auto_cleanup)
    
    def print_results(self):
        """打印测试结果"""
        print("\n" + "=" * 70)
        print("📊 测试结果")
        print("=" * 70)
        print(f"✅ 通过: {self.test_passed}")
        print(f"❌ 失败: {self.test_failed}")
        print(f"📈 总计: {self.test_passed + self.test_failed}")
        
        if self.test_failed == 0:
            print("\n🎉 所有测试通过！")
        else:
            print(f"\n⚠️  有 {self.test_failed} 个测试失败")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="OrcaLab 资产同步功能测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 使用命令行参数
  python test_asset_sync.py --username test_user --token abc123xyz

  # 使用环境变量
  export TEST_USERNAME=test_user
  export TEST_TOKEN=abc123xyz
  python test_asset_sync.py

  # 指定不同的API地址
  python test_asset_sync.py --base-url http://localhost:8000/api
        """
    )
    
    parser.add_argument(
        '--username',
        type=str,
        default=os.environ.get('TEST_USERNAME'),
        help='用户名（或使用环境变量 TEST_USERNAME）'
    )
    
    parser.add_argument(
        '--token',
        type=str,
        default=os.environ.get('TEST_TOKEN'),
        help='访问令牌（或使用环境变量 TEST_TOKEN）'
    )
    
    parser.add_argument(
        '--base-url',
        type=str,
        default="http://localhost:8080/api",
        help='后端API地址（默认: http://localhost:8080/api）'
    )
    
    parser.add_argument(
        '--auto-cleanup',
        action='store_true',
        help='自动清理测试文件，不询问'
    )
    
    args = parser.parse_args()
    
    # 验证参数
    if not args.username:
        print("❌ 错误：缺少用户名（使用 --username 或设置环境变量 TEST_USERNAME）")
        parser.print_help()
        sys.exit(1)
    
    if not args.token:
        print("❌ 错误：缺少访问令牌（使用 --token 或设置环境变量 TEST_TOKEN）")
        parser.print_help()
        sys.exit(1)
    
    # 运行测试
    test = TestAssetSync(
        username=args.username,
        token=args.token,
        base_url=args.base_url
    )
    
    try:
        test.run_all_tests(auto_cleanup=args.auto_cleanup)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)


if __name__ == '__main__':
    main()

