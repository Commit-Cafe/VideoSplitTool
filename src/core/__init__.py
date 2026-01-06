"""
核心业务层
提供FFmpeg操作、视频处理、错误诊断等核心功能
"""
from .ffmpeg_utils import (
    FFmpegHelper, VideoInfo,
    get_ffmpeg_path, get_ffprobe_path, get_base_path, check_ffmpeg
)
from .error_handler import ErrorDiagnostics, InputValidator, format_error_message
from .video_processor import VideoProcessor, ProcessResult

__all__ = [
    # FFmpeg工具
    'FFmpegHelper', 'VideoInfo',
    'get_ffmpeg_path', 'get_ffprobe_path', 'get_base_path', 'check_ffmpeg',
    # 错误处理
    'ErrorDiagnostics', 'InputValidator', 'format_error_message',
    # 视频处理
    'VideoProcessor', 'ProcessResult'
]
