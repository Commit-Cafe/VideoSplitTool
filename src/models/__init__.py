"""
数据模型层
提供视频项、配置等数据结构定义
"""
from .video_item import VideoItem, CoverType, CoverSource
from .config import (
    AppConfig, MergeConfig, OutputConfig,
    SplitMode, PositionOrder, OutputSizeMode, ScaleMode, AudioSource
)

__all__ = [
    # 视频项
    'VideoItem', 'CoverType', 'CoverSource',
    # 配置
    'AppConfig', 'MergeConfig', 'OutputConfig',
    'SplitMode', 'PositionOrder', 'OutputSizeMode', 'ScaleMode', 'AudioSource'
]
