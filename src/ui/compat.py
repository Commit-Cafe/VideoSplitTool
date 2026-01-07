"""
兼容性函数模块
提供给 UI 组件使用的工具函数
"""
from ..core.ffmpeg_utils import FFmpegHelper


def get_video_info(video_path):
    """获取视频信息（返回字典格式）"""
    info = FFmpegHelper.get_video_info(video_path)
    if info:
        return info.to_dict()
    return None


extract_frame = FFmpegHelper.extract_frame
