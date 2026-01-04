"""
工具函数模块
"""
import subprocess
import os
import sys
import tempfile
from typing import Optional, Tuple

# FFmpeg路径缓存
_ffmpeg_path = None
_ffprobe_path = None


def get_base_path() -> str:
    """获取程序基础路径（支持PyInstaller打包）"""
    if getattr(sys, 'frozen', False):
        # 打包后的exe运行
        return os.path.dirname(sys.executable)
    else:
        # 开发环境运行
        return os.path.dirname(os.path.abspath(__file__))


def get_ffmpeg_path() -> str:
    """获取ffmpeg可执行文件路径"""
    global _ffmpeg_path
    if _ffmpeg_path:
        return _ffmpeg_path

    base_path = get_base_path()

    # 查找顺序：
    # 1. 程序目录下的 ffmpeg/bin/ffmpeg.exe
    # 2. 程序目录下的 ffmpeg-*/bin/ffmpeg.exe
    # 3. 系统PATH中的ffmpeg

    # 检查 ffmpeg/bin 目录
    local_path = os.path.join(base_path, 'ffmpeg', 'bin', 'ffmpeg.exe')
    if os.path.exists(local_path):
        _ffmpeg_path = local_path
        return _ffmpeg_path

    # 检查 ffmpeg-*/bin 目录（支持版本号目录名）
    for item in os.listdir(base_path):
        if item.startswith('ffmpeg') and os.path.isdir(os.path.join(base_path, item)):
            local_path = os.path.join(base_path, item, 'bin', 'ffmpeg.exe')
            if os.path.exists(local_path):
                _ffmpeg_path = local_path
                return _ffmpeg_path

    # 使用系统PATH
    _ffmpeg_path = 'ffmpeg'
    return _ffmpeg_path


def get_ffprobe_path() -> str:
    """获取ffprobe可执行文件路径"""
    global _ffprobe_path
    if _ffprobe_path:
        return _ffprobe_path

    base_path = get_base_path()

    # 检查 ffmpeg/bin 目录
    local_path = os.path.join(base_path, 'ffmpeg', 'bin', 'ffprobe.exe')
    if os.path.exists(local_path):
        _ffprobe_path = local_path
        return _ffprobe_path

    # 检查 ffmpeg-*/bin 目录
    for item in os.listdir(base_path):
        if item.startswith('ffmpeg') and os.path.isdir(os.path.join(base_path, item)):
            local_path = os.path.join(base_path, item, 'bin', 'ffprobe.exe')
            if os.path.exists(local_path):
                _ffprobe_path = local_path
                return _ffprobe_path

    # 使用系统PATH
    _ffprobe_path = 'ffprobe'
    return _ffprobe_path


def check_ffmpeg() -> bool:
    """检查FFmpeg是否可用"""
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


def get_video_info(video_path: str) -> Optional[dict]:
    """
    获取视频信息（分辨率、时长、是否有音频等）

    Returns:
        dict: {'width': int, 'height': int, 'duration': float, 'has_audio': bool} 或 None
    """
    try:
        ffprobe = get_ffprobe_path()
        # 获取视频流信息
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

        # 解析流信息
        stream_info = lines[0].split(',') if lines else []
        width = int(stream_info[0]) if len(stream_info) > 0 and stream_info[0] else 0
        height = int(stream_info[1]) if len(stream_info) > 1 and stream_info[1] else 0

        # 获取时长（优先从流获取，否则从格式获取）
        duration = 0.0
        if len(stream_info) > 2 and stream_info[2]:
            duration = float(stream_info[2])
        elif len(lines) > 1 and lines[1]:
            duration = float(lines[1])

        # 检查是否有音频流
        has_audio = check_has_audio(video_path)

        return {
            'width': width,
            'height': height,
            'duration': duration,
            'has_audio': has_audio
        }
    except Exception as e:
        print(f"获取视频信息失败: {e}")
        return None


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
    except (OSError, subprocess.SubprocessError) as e:
        print(f"检查音频轨道失败: {e}")
        return False
    except Exception as e:
        print(f"检查音频轨道时发生未知错误: {e}")
        return False


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


def get_temp_dir() -> str:
    """获取临时目录"""
    temp_dir = os.path.join(tempfile.gettempdir(), 'video_pin')
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def clean_temp_files(temp_dir: str = None):
    """清理临时文件"""
    if temp_dir is None:
        temp_dir = get_temp_dir()

    if os.path.exists(temp_dir):
        for file in os.listdir(temp_dir):
            try:
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except OSError as e:
                print(f"无法删除临时文件 {file}: {e}")
            except Exception as e:
                print(f"删除临时文件时发生错误 {file}: {e}")


def format_duration(seconds: float) -> str:
    """格式化时长显示"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def is_valid_video(file_path: str) -> bool:
    """检查是否是有效的视频文件"""
    valid_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
    ext = os.path.splitext(file_path)[1].lower()
    return ext in valid_extensions and os.path.isfile(file_path)


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

        # 如果指定了尺寸，添加缩放滤镜
        if width and height:
            cmd.extend(['-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2'])

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


def concat_videos(video_list: list, output_path: str) -> bool:
    """
    拼接多个视频文件

    Args:
        video_list: 视频文件路径列表
        output_path: 输出视频路径

    Returns:
        bool: 是否成功
    """
    try:
        if not video_list:
            return False

        ffmpeg = get_ffmpeg_path()
        temp_dir = get_temp_dir()

        # 创建临时文件列表
        list_file = os.path.join(temp_dir, 'concat_list.txt')
        with open(list_file, 'w', encoding='utf-8') as f:
            for video in video_list:
                # 使用绝对路径并转义
                abs_path = os.path.abspath(video).replace('\\', '/')
                f.write(f"file '{abs_path}'\n")

        cmd = [
            ffmpeg, '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',
            output_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

        # 清理临时文件
        try:
            os.remove(list_file)
        except OSError as e:
            print(f"无法删除临时列表文件: {e}")
        except Exception as e:
            print(f"删除临时列表文件时发生错误: {e}")

        return result.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        print(f"视频拼接失败: {e}")
        return False
