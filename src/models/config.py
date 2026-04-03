"""
应用配置模型
"""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class SplitMode(Enum):
    """分割模式"""
    HORIZONTAL = "horizontal"  # 左右分割
    VERTICAL = "vertical"      # 上下分割


class PositionOrder(Enum):
    """位置顺序"""
    TEMPLATE_FIRST = "template_first"  # 模板在前
    LIST_FIRST = "list_first"          # 列表在前


class OutputSizeMode(Enum):
    """输出尺寸模式"""
    TEMPLATE = "template"  # 跟随模板
    LIST = "list"          # 跟随列表（一对一）
    CUSTOM = "custom"      # 自定义


class ScaleMode(Enum):
    """缩放模式"""
    FIT = "fit"        # 适应（留黑边）
    FILL = "fill"      # 填充（裁剪）
    STRETCH = "stretch"  # 拉伸


class AudioSource(Enum):
    """音频来源"""
    TEMPLATE = "template"
    LIST = "list"
    MIX = "mix"
    CUSTOM = "custom"
    NONE = "none"


@dataclass
class DialogDirsConfig:
    """对话框目录配置"""
    template_dir: str = ""      # 模板视频选择目录
    list_dir: str = ""          # 列表视频选择目录
    output_dir: str = ""        # 输出目录

    def to_dict(self) -> dict:
        return {
            'template_dir': self.template_dir,
            'list_dir': self.list_dir,
            'output_dir': self.output_dir,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DialogDirsConfig':
        return cls(
            template_dir=data.get('template_dir', ''),
            list_dir=data.get('list_dir', ''),
            output_dir=data.get('output_dir', ''),
        )


@dataclass
class MergeConfig:
    """拼接配置"""
    use_part_a: bool = True   # 使用模板左/上部分
    use_part_b: bool = False  # 使用模板右/下部分
    use_part_c: bool = True   # 使用列表左/上部分
    use_part_d: bool = False  # 使用列表右/下部分

    def get_combinations(self) -> List[str]:
        """获取所有拼接组合"""
        combinations = []
        template_parts = []
        list_parts = []

        if self.use_part_a:
            template_parts.append('a')
        if self.use_part_b:
            template_parts.append('b')
        if self.use_part_c:
            list_parts.append('c')
        if self.use_part_d:
            list_parts.append('d')

        for t in template_parts:
            for l in list_parts:
                combinations.append(f"{t}+{l}")

        return combinations


@dataclass
class OutputConfig:
    """输出配置"""
    size_mode: str = "template"
    width: int = 1920
    height: int = 1080
    scale_mode: str = "fit"


@dataclass
class AppConfig:
    """
    应用全局配置

    Attributes:
        template_video: 模板视频路径
        output_dir: 输出目录
        split_mode: 分割模式
        split_ratio: 模板分割比例
        position_order: 位置顺序
        merge_config: 拼接配置
        output_config: 输出配置
        audio_source: 音频来源
        custom_audio_path: 自定义音频路径
        dialog_dirs: 对话框目录配置
    """
    template_video: str = ""
    output_dir: str = ""
    split_mode: str = "horizontal"
    split_ratio: float = 0.5
    position_order: str = "template_first"
    merge_config: MergeConfig = field(default_factory=MergeConfig)
    output_config: OutputConfig = field(default_factory=OutputConfig)
    audio_source: str = "template"
    custom_audio_path: Optional[str] = None
    dialog_dirs: DialogDirsConfig = field(default_factory=DialogDirsConfig)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'template_video': self.template_video,
            'output_dir': self.output_dir,
            'split_mode': self.split_mode,
            'split_ratio': self.split_ratio,
            'position_order': self.position_order,
            'merge_config': {
                'use_part_a': self.merge_config.use_part_a,
                'use_part_b': self.merge_config.use_part_b,
                'use_part_c': self.merge_config.use_part_c,
                'use_part_d': self.merge_config.use_part_d,
            },
            'output_config': {
                'size_mode': self.output_config.size_mode,
                'width': self.output_config.width,
                'height': self.output_config.height,
                'scale_mode': self.output_config.scale_mode,
            },
            'audio_source': self.audio_source,
            'custom_audio_path': self.custom_audio_path,
            'dialog_dirs': self.dialog_dirs.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'AppConfig':
        """从字典创建实例"""
        merge_data = data.get('merge_config', {})
        output_data = data.get('output_config', {})
        dialog_dirs_data = data.get('dialog_dirs', {})

        return cls(
            template_video=data.get('template_video', ''),
            output_dir=data.get('output_dir', ''),
            split_mode=data.get('split_mode', 'horizontal'),
            split_ratio=data.get('split_ratio', 0.5),
            position_order=data.get('position_order', 'template_first'),
            merge_config=MergeConfig(
                use_part_a=merge_data.get('use_part_a', True),
                use_part_b=merge_data.get('use_part_b', False),
                use_part_c=merge_data.get('use_part_c', True),
                use_part_d=merge_data.get('use_part_d', False),
            ),
            output_config=OutputConfig(
                size_mode=output_data.get('size_mode', 'template'),
                width=output_data.get('width', 1920),
                height=output_data.get('height', 1080),
                scale_mode=output_data.get('scale_mode', 'fit'),
            ),
            audio_source=data.get('audio_source', 'template'),
            custom_audio_path=data.get('custom_audio_path'),
            dialog_dirs=DialogDirsConfig.from_dict(dialog_dirs_data),
        )
