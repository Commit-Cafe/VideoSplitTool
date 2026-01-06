"""
FFmpeg 工具类
封装所有 FFmpeg 相关操作
"""
import subprocess
import os
import sys
from typing import Optional, Dict, Any
from dataclasses import dataclass


# FFmpeg 路径缓存
_ffmpeg_path: Optional[str] = None
_ffprobe_path: Optional[str] = None


def get_base_path() -> str:
    """获取程序基础路径（支持PyInstaller打包）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        # 开发环境：返回项目根目录
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_ffmpeg_path() -> str:
    """获取 ffmpeg 可执行文件路径"""
    global _ffmpeg_path
    if _ffmpeg_path:
        return _ffmpeg_path

    base_path = get_base_path()

    # 查找顺序：
    # 1. 程序目录下的 ffmpeg/bin/ffmpeg.exe
    # 2. 程序目录下的 ffmpeg-*/bin/ffmpeg.exe
    # 3. 系统PATH中的ffmpeg

    local_path = os.path.join(base_path, 'ffmpeg', 'bin', 'ffmpeg.exe')
    if os.path.exists(local_path):
        _ffmpeg_path = local_path
        return _ffmpeg_path

    # 检查 ffmpeg-*/bin 目录
    if os.path.exists(base_path):
        for item in os.listdir(base_path):
            if item.startswith('ffmpeg') and os.path.isdir(os.path.join(base_path, item)):
                local_path = os.path.join(base_path, item, 'bin', 'ffmpeg.exe')
                if os.path.exists(local_path):
                    _ffmpeg_path = local_path
                    return _ffmpeg_path

    _ffmpeg_path = 'ffmpeg'
    return _ffmpeg_path


def get_ffprobe_path() -> str:
    """获取 ffprobe 可执行文件路径"""
    global _ffprobe_path
    if _ffprobe_path:
        return _ffprobe_path

    base_path = get_base_path()

    local_path = os.path.join(base_path, 'ffmpeg', 'bin', 'ffprobe.exe')
    if os.path.exists(local_path):
        _ffprobe_path = local_path
        return _ffprobe_path

    if os.path.exists(base_path):
        for item in os.listdir(base_path):
            if item.startswith('ffmpeg') and os.path.isdir(os.path.join(base_path, item)):
                local_path = os.path.join(base_path, item, 'bin', 'ffprobe.exe')
                if os.path.exists(local_path):
                    _ffprobe_path = local_path
                    return _ffprobe_path

    _ffprobe_path = 'ffprobe'
    return _ffprobe_path


def check_ffmpeg() -> bool:
    """检查 FFmpeg 是否可用"""
    try:
        ffmpeg = get_ffmpeg_path()
        result = subprocess.run(
            [ffmpeg, '-version'],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


@dataclass
class VideoInfo:
    """视频信息数据类"""
    width: int = 0
    height: int = 0
    duration: float = 0.0
    has_audio: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'width': self.width,
            'height': self.height,
            'duration': self.duration,
            'has_audio': self.has_audio
        }


class FFmpegHelper:
    """FFmpeg 辅助类"""

    @staticmethod
    def get_video_info(video_path: str) -> Optional[VideoInfo]:
        """
        获取视频信息

        Args:
            video_path: 视频文件路径

        Returns:
            VideoInfo 对象或 None
        """
        try:
            ffprobe = get_ffprobe_path()
            cmd = [
                ffprobe,
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,duration',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0:s=,',
                video_path
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if result.returncode != 0:
                return None

            output = result.stdout.strip()
            lines = output.split('\n')
            stream_info = lines[0].split(',') if lines else []

            width = int(stream_info[0]) if len(stream_info) > 0 and stream_info[0] else 0
            height = int(stream_info[1]) if len(stream_info) > 1 and stream_info[1] else 0

            duration = 0.0
            if len(stream_info) > 2 and stream_info[2]:
                duration = float(stream_info[2])
            elif len(lines) > 1 and lines[1]:
                duration = float(lines[1])

            has_audio = FFmpegHelper.check_has_audio(video_path)

            return VideoInfo(
                width=width,
                height=height,
                duration=duration,
                has_audio=has_audio
            )
        except Exception as e:
            print(f"获取视频信息失败: {e}")
            return None

    @staticmethod
    def check_has_audio(video_path: str) -> bool:
        """检查视频是否有音频轨道"""
        try:
            ffprobe = get_ffprobe_path()
            cmd = [
                ffprobe,
                '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_type',
                '-of', 'csv=p=0',
                video_path
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            return 'audio' in result.stdout.lower()
        except Exception:
            return False

    @staticmethod
    def extract_frame(video_path: str, output_path: str, time_pos: float = 0) -> bool:
        """
        从视频中提取一帧

        Args:
            video_path: 视频路径
            output_path: 输出图片路径
            time_pos: 提取帧的时间位置（秒）

        Returns:
            bool: 是否成功
        """
        try:
            ffmpeg = get_ffmpeg_path()
            cmd = [
                ffmpeg,
                '-y',
                '-ss', str(time_pos),
                '-i', video_path,
                '-vframes', '1',
                '-q:v', '2',
                output_path
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            return result.returncode == 0 and os.path.exists(output_path)
        except Exception as e:
            print(f"提取帧失败: {e}")
            return False

    @staticmethod
    def image_to_video(image_path: str, output_path: str, duration: float = 3.0,
                       width: int = None, height: int = None) -> bool:
        """
        将图片转换为视频片段

        Args:
            image_path: 输入图片路径
            output_path: 输出视频路径
            duration: 视频时长（秒）
            width: 输出视频宽度（可选）
            height: 输出视频高度（可选）

        Returns:
            bool: 是否成功
        """
        try:
            ffmpeg = get_ffmpeg_path()
            cmd = [
                ffmpeg, '-y',
                '-loop', '1',
                '-i', image_path,
                '-c:v', 'libx264',
                '-t', str(duration),
                '-pix_fmt', 'yuv420p',
                '-r', '30',
            ]

            if width and height:
                cmd.extend(['-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
                                   f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2'])

            cmd.append(output_path)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            return result.returncode == 0 and os.path.exists(output_path)
        except Exception as e:
            print(f"图片转视频失败: {e}")
            return False

    @staticmethod
    def get_video_duration(video_path: str) -> float:
        """获取视频时长（秒）"""
        try:
            ffprobe = get_ffprobe_path()
            cmd = [
                ffprobe,
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                video_path
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
            return 0.0
        except Exception:
            return 0.0
