"""
图片处理工具类
提供各种图片格式转换和处理功能
"""

import os
from typing import List
from PIL import Image


class ImageProcessor:
    """图片处理工具类"""
    
    @staticmethod
    def create_apng_panorama(images: List[Image.Image], apng_path: str, duration: int = 200) -> bool:
        """
        创建APNG格式的全景图
        
        Args:
            images: PIL Image对象列表
            apng_path: 输出APNG文件路径
            duration: 每帧持续时间(毫秒)
            
        Returns:
            bool: 是否创建成功
        """
        try:
            if not images:
                return False
            
            # 确保所有图片都是RGBA模式以支持透明度
            processed_images = []
            for img in images:
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                processed_images.append(img)
            
            # 使用PIL的save方法创建APNG
            # APNG是PNG的扩展，PIL支持保存为APNG格式
            processed_images[0].save(
                apng_path,
                save_all=True,
                append_images=processed_images[1:],
                duration=duration,
                loop=0,  # 无限循环
                optimize=True,  # 优化文件大小
                format='PNG'  # 明确指定PNG格式
            )
            
            return True
            
        except Exception as e:
            print(f"Error creating APNG panorama: {e}")
            return False
