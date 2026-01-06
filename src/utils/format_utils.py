"""
格式化工具函数
"""


def format_duration(seconds: float) -> str:
    """
    格式化时长显示

    Args:
        seconds: 秒数

    Returns:
        str: 格式化的时间字符串 (MM:SS 或 HH:MM:SS)
    """
    if seconds < 0:
        seconds = 0

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def get_video_orientation(width: int, height: int) -> str:
    """
    根据视频宽高判断方向

    Args:
        width: 视频宽度
        height: 视频高度

    Returns:
        方向描述字符串: "横屏"、"竖屏"、"正方形" 或 "未知"
    """
    if width <= 0 or height <= 0:
        return "未知"

    if width > height:
        return "横屏"
    elif height > width:
        return "竖屏"
    else:
        return "正方形"


def format_video_info(width: int, height: int, duration: float = None) -> str:
    """
    格式化视频信息显示字符串

    Args:
        width: 视频宽度
        height: 视频高度
        duration: 视频时长（可选）

    Returns:
        格式化的视频信息字符串
    """
    if width <= 0 or height <= 0:
        return "无法获取视频信息"

    orientation = get_video_orientation(width, height)
    info_str = f"{width}x{height} ({orientation})"

    if duration is not None and duration > 0:
        info_str += f", 时长: {format_duration(duration)}"

    return info_str


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小

    Args:
        size_bytes: 字节数

    Returns:
        str: 格式化的大小字符串 (如 "1.5 MB")
    """
    if size_bytes < 0:
        return "0 B"

    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(size_bytes)

    for unit in units[:-1]:
        if size < 1024:
            return f"{size:.1f} {unit}" if size != int(size) else f"{int(size)} {unit}"
        size /= 1024

    return f"{size:.1f} {units[-1]}"
