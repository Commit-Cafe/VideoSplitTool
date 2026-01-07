"""
视频项数据模型
"""
import os
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class CoverType(Enum):
    """封面类型枚举"""
    NONE = "none"
    FRAME = "frame"
    IMAGE = "image"


class CoverSource(Enum):
    """封面帧来源枚举"""
    TEMPLATE = "template"
    LIST = "list"
    MERGED = "merged"


@dataclass
class VideoItem:
    """
    视频列表项数据结构

    Attributes:
        path: 视频文件路径
        name: 视频文件名
        split_ratio: 分割比例 (0.1-0.9)
        scale_percent: 缩放百分比 (50-200)
        output_ratio: 输出比例 - 上/左部分在输出中占的比例 (0.1-0.9)，None表示跟随split_ratio
        cover_type: 封面类型
        cover_frame_time: 封面帧时间点(秒)
        cover_image_path: 外部封面图片路径
        cover_duration: 封面显示时长(秒)
        cover_frame_source: 封面帧来源
    """
    path: str
    name: str = field(init=False)
    split_ratio: float = 0.5
    scale_percent: int = 100
    output_ratio: Optional[float] = None  # None表示跟随split_ratio
    cover_type: str = "none"
    cover_frame_time: float = 0.0
    cover_image_path: Optional[str] = None
    cover_duration: float = 1.0
    cover_frame_source: str = "template"

    def __post_init__(self):
        """初始化后处理"""
        self.name = os.path.basename(self.path)

    def get_output_ratio(self) -> float:
        """获取实际输出比例，如果未设置则返回分割比例"""
        return self.output_ratio if self.output_ratio is not None else self.split_ratio

    def get_summary(self) -> tuple:
        """
        获取设置摘要，用于列表显示

        Returns:
            tuple: (分割比例, 缩放比例, 封面信息)
        """
        cover_str = "无"
        if self.cover_type == CoverType.FRAME.value:
            cover_str = f"帧{self.cover_duration}s"
        elif self.cover_type == CoverType.IMAGE.value:
            cover_str = f"图{self.cover_duration}s"
        return f"{int(self.split_ratio * 100)}%", f"{self.scale_percent}%", cover_str

    def to_dict(self) -> dict:
        """转换为字典，用于序列化"""
        return {
            'path': self.path,
            'split_ratio': self.split_ratio,
            'scale_percent': self.scale_percent,
            'output_ratio': self.output_ratio,
            'cover_type': self.cover_type,
            'cover_frame_time': self.cover_frame_time,
            'cover_image_path': self.cover_image_path,
            'cover_duration': self.cover_duration,
            'cover_frame_source': self.cover_frame_source
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'VideoItem':
        """从字典创建实例"""
        item = cls(
            path=data['path'],
            split_ratio=data.get('split_ratio', 0.5),
            scale_percent=data.get('scale_percent', 100),
            output_ratio=data.get('output_ratio'),
            cover_type=data.get('cover_type', 'none'),
            cover_frame_time=data.get('cover_frame_time', 0.0),
            cover_image_path=data.get('cover_image_path'),
            cover_duration=data.get('cover_duration', 1.0),
            cover_frame_source=data.get('cover_frame_source', 'template')
        )
        return item

    def validate(self) -> tuple:
        """
        验证数据有效性

        Returns:
            tuple: (是否有效, 错误信息)
        """
        if not os.path.exists(self.path):
            return False, f"文件不存在: {self.path}"

        if not 0.1 <= self.split_ratio <= 0.9:
            return False, f"分割比例超出范围: {self.split_ratio}"

        if not 50 <= self.scale_percent <= 200:
            return False, f"缩放比例超出范围: {self.scale_percent}"

        if self.output_ratio is not None and not 0.1 <= self.output_ratio <= 0.9:
            return False, f"输出比例超出范围: {self.output_ratio}"

        if self.cover_type == CoverType.IMAGE.value and self.cover_image_path:
            if not os.path.exists(self.cover_image_path):
                return False, f"封面图片不存在: {self.cover_image_path}"

        return True, ""
