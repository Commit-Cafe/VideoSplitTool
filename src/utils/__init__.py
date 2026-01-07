"""
工具函数层
提供文件操作、格式化、日志、临时文件管理等基础功能
"""
from .file_utils import (
    get_temp_dir, clean_temp_files, is_valid_video,
    ensure_dir, get_unique_filename, VALID_VIDEO_EXTENSIONS,
    get_base_path
)
from .format_utils import (
    format_duration, format_video_info, get_video_orientation, format_file_size
)
from .logger import logger, cleanup_old_logs, setup_logger
from .temp_manager import global_temp_manager, cleanup_on_exit, TempFileManager

__all__ = [
    # 文件工具
    'get_temp_dir', 'clean_temp_files', 'is_valid_video',
    'ensure_dir', 'get_unique_filename', 'VALID_VIDEO_EXTENSIONS',
    # 格式化工具
    'format_duration', 'format_video_info', 'get_video_orientation', 'format_file_size',
    # 日志
    'logger', 'cleanup_old_logs', 'setup_logger', 'get_base_path',
    # 临时文件管理
    'global_temp_manager', 'cleanup_on_exit', 'TempFileManager'
]
