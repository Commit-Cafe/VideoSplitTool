"""
智能错误诊断和处理模块
"""
import os
from typing import Tuple, List

from ..utils.logger import logger
from ..utils.file_utils import is_valid_video


class ErrorDiagnostics:
    """FFmpeg错误诊断器"""

    @staticmethod
    def diagnose_ffmpeg_error(stderr: str, context: dict = None) -> Tuple[str, List[str]]:
        """
        诊断FFmpeg错误并提供修复建议

        Args:
            stderr: FFmpeg的错误输出
            context: 上下文信息，如 {"audio_source": "template", "has_audio": False}

        Returns:
            Tuple[str, List[str]]: (错误描述, 修复建议列表)
        """
        stderr_lower = stderr.lower()
        context = context or {}

        # 文件不存在错误
        if "no such file" in stderr_lower or "does not exist" in stderr_lower:
            return (
                "视频文件路径无效或文件已被移动/删除",
                [
                    "检查文件是否存在",
                    "确认文件路径中没有特殊字符",
                    "尝试将文件移动到纯英文路径",
                    "重新选择视频文件"
                ]
            )

        # 音频流匹配错误
        if "matches no streams" in stderr_lower and "outa" in stderr_lower:
            return (
                "您选择了音频选项，但视频没有音频轨道",
                [
                    "在音频设置中选择'静音'选项",
                    "添加自定义音频文件",
                    "使用带有音频的视频",
                    "如果两个视频都没有音频，请选择'静音'"
                ]
            )

        # 通用的音频流错误
        if "audio" in stderr_lower and ("stream" in stderr_lower or "codec" in stderr_lower):
            return (
                "音频处理失败",
                [
                    "检查视频是否有音频轨道",
                    "尝试选择'静音'选项",
                    "检查音频编解码器是否支持"
                ]
            )

        # 视频数据无效
        if "invalid data" in stderr_lower or "corrupt" in stderr_lower:
            return (
                "视频文件损坏或格式不完整",
                [
                    "使用视频播放器测试文件是否能正常播放",
                    "使用HandBrake等工具重新编码视频",
                    "尝试使用其他视频文件"
                ]
            )

        # 编码失败
        if "conversion failed" in stderr_lower or "encoding" in stderr_lower:
            return (
                "视频编码失败",
                [
                    "视频分辨率可能过大，尝试使用较小的视频",
                    "检查磁盘空间是否充足",
                    "检查输出路径是否有写入权限"
                ]
            )

        # 滤镜错误
        if "filter" in stderr_lower or "scale" in stderr_lower:
            return (
                "视频滤镜处理失败",
                [
                    "视频尺寸可能异常(0x0或过大)",
                    "尝试调整分割比例",
                    "检查视频文件是否完整"
                ]
            )

        # 权限错误
        if "permission denied" in stderr_lower or "access denied" in stderr_lower:
            return (
                "文件访问权限不足",
                [
                    "检查输出目录是否有写入权限",
                    "关闭正在使用该文件的其他程序",
                    "以管理员身份运行程序",
                    "选择其他输出目录"
                ]
            )

        # 磁盘空间不足
        if "no space" in stderr_lower or "disk full" in stderr_lower:
            return (
                "磁盘空间不足",
                [
                    "清理磁盘空间",
                    "选择其他磁盘作为输出目录",
                    "删除不需要的临时文件"
                ]
            )

        # 超时错误
        if "timeout" in stderr_lower:
            return (
                "处理超时",
                [
                    "视频文件过大，需要更长时间",
                    "关闭其他占用CPU的程序",
                    "检查视频文件是否损坏导致无限循环"
                ]
            )

        # 封面相关错误
        if "anullsrc" in stderr_lower or "concat" in stderr_lower:
            return (
                "封面处理失败",
                [
                    "暂时不使用封面功能",
                    "检查封面时长设置（不要过长）",
                    "确保主视频有音频（如果选择了音频选项）"
                ]
            )

        # 提取关键错误信息
        key_error = ErrorDiagnostics._extract_key_error(stderr)

        return (
            f"FFmpeg处理失败: {key_error}",
            [
                "查看详细错误日志了解更多信息",
                "检查视频文件格式是否支持",
                "尝试使用DEBUG_FFMPEG_ERROR.md中的诊断步骤"
            ]
        )

    @staticmethod
    def _extract_key_error(stderr: str) -> str:
        """从FFmpeg错误输出中提取关键错误信息"""
        lines = stderr.strip().split('\n')

        # 查找包含Error的行
        for line in reversed(lines):
            line_lower = line.lower()
            if 'error' in line_lower:
                line = line.replace('[error]', '').replace('Error', '').strip()
                if line and len(line) < 200:
                    return line

        return ' '.join(lines[-3:]) if len(lines) >= 3 else stderr[:200]


class InputValidator:
    """输入验证器"""

    @staticmethod
    def validate_video_file(file_path: str) -> Tuple[bool, str]:
        """
        验证视频文件

        Args:
            file_path: 视频文件路径

        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        from .ffmpeg_utils import FFmpegHelper

        if not file_path:
            return False, "文件路径为空"

        if not os.path.exists(file_path):
            return False, "文件不存在"

        if not os.path.isfile(file_path):
            return False, "路径不是文件"

        if not os.access(file_path, os.R_OK):
            return False, "文件没有读取权限"

        if not is_valid_video(file_path):
            return False, "文件格式不支持（仅支持mp4, avi, mkv, mov等）"

        # 尝试获取视频信息验证文件完整性
        info = FFmpegHelper.get_video_info(file_path)
        if not info:
            return False, "无法读取视频信息，文件可能损坏"

        if info.width == 0 or info.height == 0:
            return False, "视频尺寸无效"

        if info.duration <= 0:
            return False, "视频时长无效"

        return True, ""

    @staticmethod
    def validate_split_ratio(ratio: float) -> Tuple[bool, str]:
        """验证分割比例"""
        if not isinstance(ratio, (int, float)):
            return False, "分割比例必须是数字"

        if ratio < 0.1 or ratio > 0.9:
            return False, "分割比例必须在0.1-0.9之间"

        return True, ""

    @staticmethod
    def validate_scale_percent(percent: int) -> Tuple[bool, str]:
        """验证缩放百分比"""
        if not isinstance(percent, int):
            return False, "缩放百分比必须是整数"

        if percent < 50 or percent > 200:
            return False, "缩放百分比必须在50-200之间"

        return True, ""

    @staticmethod
    def validate_output_directory(dir_path: str) -> Tuple[bool, str]:
        """验证输出目录"""
        if not dir_path:
            return False, "输出目录为空"

        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
                return True, ""
            except OSError as e:
                return False, f"无法创建输出目录: {e}"

        if not os.path.isdir(dir_path):
            return False, "路径不是目录"

        if not os.access(dir_path, os.W_OK):
            return False, "输出目录没有写入权限"

        return True, ""

    @staticmethod
    def validate_cover_duration(duration: float, video_duration: float) -> Tuple[bool, str]:
        """验证封面时长"""
        if not isinstance(duration, (int, float)):
            return False, "封面时长必须是数字"

        if duration <= 0:
            return False, "封面时长必须大于0"

        if duration > 30:
            return False, "封面时长不建议超过30秒"

        if duration > video_duration:
            return False, f"封面时长({duration}秒)不能超过视频时长({video_duration:.1f}秒)"

        return True, ""


def format_error_message(error_desc: str, suggestions: List[str]) -> str:
    """
    格式化错误消息（带建议）

    Args:
        error_desc: 错误描述
        suggestions: 修复建议列表

    Returns:
        str: 格式化后的错误消息
    """
    message = f"错误: {error_desc}\n\n"
    message += "建议的解决方法:\n"
    for i, suggestion in enumerate(suggestions, 1):
        message += f"{i}. {suggestion}\n"
    return message.strip()
