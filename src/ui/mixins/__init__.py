"""
UI Mixins 模块
将 main_window.py 的功能拆分为多个 Mixin 类，提高代码可维护性

各 Mixin 职责:
- DividerMixin: 曲线分界线功能（编辑、生成蒙版、同步等）
- PreviewMixin: 预览渲染逻辑（模板预览、拼接预览、分割线等）
- DiagramMixin: 效果示意图（可拖拽调整区块）
- CoverMixin: 封面设置（类型选择、帧时间、图片等）
- AudioMixin: 音频设置（音源选择、音量调节、试听等）
- ProcessingMixin: 视频处理（批量处理、进度跟踪、结果显示）
"""

from .divider_mixin import DividerMixin
from .preview_mixin import PreviewMixin
from .diagram_mixin import DiagramMixin
from .cover_mixin import CoverMixin
from .audio_mixin import AudioMixin
from .processing_mixin import ProcessingMixin

__all__ = [
    'DividerMixin',
    'PreviewMixin',
    'DiagramMixin',
    'CoverMixin',
    'AudioMixin',
    'ProcessingMixin',
]
