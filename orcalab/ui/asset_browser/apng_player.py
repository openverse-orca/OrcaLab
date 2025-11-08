"""
APNG 播放器 - 用于在 Qt 中播放 APNG 动画

由于 Qt 默认不支持 APNG，这个类使用 Python 的 apng 库手动解码帧
"""

from typing import List
from PySide6 import QtCore, QtGui
from pathlib import Path
import io


class ApngPlayer(QtCore.QObject):
    """APNG 动画播放器"""
    
    frame_changed = QtCore.Signal()
    
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        
        self.file_path = file_path
        self.frames: List[QtGui.QImage] = []
        self.delays: List[int] = []  # 毫秒
        self.current_frame = 0
        self.is_playing = False
        
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._next_frame)
        
        self._load_apng()
    
    def _load_apng(self):
        """加载 APNG 文件（使用 Pillow）"""
        try:
            from PIL import Image
            import io
        except ImportError:
            print("错误: 需要安装 Pillow 库")
            print("运行: pip install Pillow")
            return
        
        try:
            pil_img = Image.open(self.file_path)
            
            n_frames = getattr(pil_img, "n_frames", 1)
            
            frame_sizes = []
            
            for i in range(n_frames):
                pil_img.seek(i)  # 切换到第 i 帧
                
                # 转换为 RGBA（确保有 alpha 通道）
                frame_rgba = pil_img.convert('RGBA')
                frame_sizes.append(frame_rgba.size)
                
                # 转换为 QImage
                data = frame_rgba.tobytes("raw", "RGBA")
                qimage = QtGui.QImage(
                    data,
                    frame_rgba.width,
                    frame_rgba.height,
                    QtGui.QImage.Format.Format_RGBA8888
                )
                
                self.frames.append(qimage.copy())
                
                delay_ms = pil_img.info.get('duration', 100)
                self.delays.append(delay_ms)
            
        except Exception as e:
            print(f"[ApngPlayer] 加载失败: {e}")
    
    def frame_count(self) -> int:
        return len(self.frames)
    
    def is_valid(self) -> bool:
        return len(self.frames) > 0
    
    def current_image(self) -> QtGui.QImage:
        if not self.frames:
            return QtGui.QImage()
        return self.frames[self.current_frame]
    
    def current_pixmap(self) -> QtGui.QPixmap:
        return QtGui.QPixmap.fromImage(self.current_image())
    
    def start(self):
        if not self.is_valid():
            return
        
        self.is_playing = True
        self.current_frame = 0
        self._schedule_next_frame()
    
    def stop(self):
        self.is_playing = False
        self._timer.stop()
    
    def _schedule_next_frame(self):
        if not self.is_playing or not self.delays:
            return
        
        delay = self.delays[self.current_frame]
        self._timer.start(delay)
    
    def _next_frame(self):
        self._timer.stop()
        
        if not self.is_playing:
            return
        
        self.current_frame = (self.current_frame + 1) % len(self.frames)
        self.frame_changed.emit()
        
        self._schedule_next_frame()
    
    def set_scaled_size(self, size: QtCore.QSize, keep_aspect_ratio: bool = True):
        scaled_frames = []
        
        aspect_mode = (
            QtCore.Qt.AspectRatioMode.KeepAspectRatio if keep_aspect_ratio 
            else QtCore.Qt.AspectRatioMode.IgnoreAspectRatio
        )
        
        for frame in self.frames:
            scaled = frame.scaled(
                size,
                aspect_mode,
                QtCore.Qt.TransformationMode.SmoothTransformation  # 高质量缩放
            )
            scaled_frames.append(scaled)
        
        self.frames = scaled_frames

