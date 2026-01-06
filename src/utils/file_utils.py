"""
文件操作工具函数
"""
import os
import tempfile
from typing import Set

# 有效视频扩展名
VALID_VIDEO_EXTENSIONS: Set[str] = {
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'
}


def get_temp_dir() -> str:
    """获取临时目录"""
    temp_dir = os.path.join(tempfile.gettempdir(), 'video_pin')
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def clean_temp_files(temp_dir: str = None):
    """清理临时文件"""
    if temp_dir is None:
        temp_dir = get_temp_dir()

    if os.path.exists(temp_dir):
        for file in os.listdir(temp_dir):
            try:
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except OSError as e:
                print(f"无法删除临时文件 {file}: {e}")
            except Exception as e:
                print(f"删除临时文件时发生错误 {file}: {e}")


def is_valid_video(file_path: str) -> bool:
    """
    检查是否是有效的视频文件

    Args:
        file_path: 文件路径

    Returns:
        bool: 是否是有效视频文件
    """
    if not file_path:
        return False

    ext = os.path.splitext(file_path)[1].lower()
    return ext in VALID_VIDEO_EXTENSIONS and os.path.isfile(file_path)


def ensure_dir(dir_path: str) -> bool:
    """
    确保目录存在

    Args:
        dir_path: 目录路径

    Returns:
        bool: 是否成功
    """
    try:
        os.makedirs(dir_path, exist_ok=True)
        return True
    except Exception:
        return False


def get_unique_filename(base_path: str, prefix: str = "", suffix: str = "") -> str:
    """
    生成唯一文件名

    Args:
        base_path: 基础目录
        prefix: 文件名前缀
        suffix: 文件名后缀（扩展名）

    Returns:
        str: 唯一文件路径
    """
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    filename = f"{prefix}_{unique_id}{suffix}" if prefix else f"{unique_id}{suffix}"
    return os.path.join(base_path, filename)
