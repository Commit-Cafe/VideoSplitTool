"""
图片元数据工具
使用 Pillow 读取图片尺寸、是否有 alpha 通道
"""
from dataclasses import dataclass
from typing import Optional

from PIL import Image


@dataclass
class ImageInfo:
    """图片元数据"""
    width: int
    height: int
    has_alpha: bool


def get_image_info(image_path: str) -> Optional[ImageInfo]:
    """
    获取图片元数据

    Args:
        image_path: 图片文件路径

    Returns:
        ImageInfo 实例；文件不存在或读取失败返回 None
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            has_alpha = img.mode in ('RGBA', 'LA', 'PA') or 'transparency' in img.info
            return ImageInfo(width=width, height=height, has_alpha=has_alpha)
    except (FileNotFoundError, OSError):
        return None
    except Exception:
        return None
