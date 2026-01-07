"""
UI层
提供GUI组件和对话框
"""
from .compat import get_video_info, extract_frame
from .main_window import MainWindow, VideoSplitApp
from .dialogs import VideoSettingsDialog
from .widgets import ScrollableFrame

__all__ = [
    'MainWindow', 'VideoSplitApp', 'VideoSettingsDialog', 'ScrollableFrame',
    'get_video_info', 'extract_frame'
]
