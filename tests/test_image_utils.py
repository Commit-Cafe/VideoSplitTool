"""
图片元数据工具单元测试
运行：python tests/test_image_utils.py
"""
import os
import sys
import tempfile
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.image_utils import get_image_info, ImageInfo


def _make_test_image(path: str, width: int, height: int, has_alpha: bool):
    """创建测试用图片"""
    if has_alpha:
        img = Image.new('RGBA', (width, height), (255, 0, 0, 128))
    else:
        img = Image.new('RGB', (width, height), (255, 0, 0))
    img.save(path)


def test_get_image_info_rgba():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'logo.png')
        _make_test_image(path, 200, 100, has_alpha=True)
        info = get_image_info(path)
        assert info is not None, "应当返回 ImageInfo"
        assert info.width == 200
        assert info.height == 100
        assert info.has_alpha is True
    print("test_get_image_info_rgba OK")


def test_get_image_info_rgb():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'logo.jpg')
        _make_test_image(path, 300, 150, has_alpha=False)
        info = get_image_info(path)
        assert info is not None
        assert info.width == 300
        assert info.height == 150
        assert info.has_alpha is False
    print("test_get_image_info_rgb OK")


def test_get_image_info_not_exists():
    info = get_image_info('D:/不存在的文件.png')
    assert info is None, "不存在的图片应当返回 None"
    print("test_get_image_info_not_exists OK")


if __name__ == '__main__':
    test_get_image_info_rgba()
    test_get_image_info_rgb()
    test_get_image_info_not_exists()
    print("ALL OK")
