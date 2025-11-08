"""
图片处理工具类
提供各种图片格式转换和处理功能
"""

import os
from typing import List
from PIL import Image, ImageDraw, ImageFont


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
    
    @staticmethod
    def add_text_to_image(image_path: str, text: str, position: str = "bottom_right", 
                         font_size: int = 12, text_color: tuple = (255, 255, 255), 
                         bg_color: tuple = (0, 0, 0, 180)) -> bool:
        """
        在图片上添加文字
        
        Args:
            image_path: 图片路径
            text: 要添加的文字
            position: 文字位置 (bottom_right, bottom_left, top_right, top_left)
            font_size: 字体大小
            text_color: 文字颜色 (R, G, B)
            bg_color: 背景颜色 (R, G, B, A)
            
        Returns:
            bool: 是否添加成功
        """
        try:
            img = Image.open(image_path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)
            
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except:
                font = ImageFont.load_default()
            
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            padding = 5
            img_width, img_height = img.size
            
            if position == "bottom_right":
                x = img_width - text_width - padding * 2
                y = img_height - text_height - padding * 2
            elif position == "bottom_left":
                x = padding
                y = img_height - text_height - padding * 2
            elif position == "top_right":
                x = img_width - text_width - padding * 2
                y = padding
            else:  # top_left
                x = padding
                y = padding
            
            draw.rectangle([x - padding, y - padding, x + text_width + padding, y + text_height + padding], 
                          fill=bg_color)
            draw.text((x, y), text, font=font, fill=text_color)
            
            result = Image.alpha_composite(img, overlay)
            result.convert('RGB').save(image_path)
            
            return True
            
        except Exception as e:
            print(f"Error adding text to image: {e}")
            return False

