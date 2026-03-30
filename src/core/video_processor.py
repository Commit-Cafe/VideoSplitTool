"""
视频处理核心模块
使用FFmpeg进行视频分割和拼接
"""
import subprocess
import os
import uuid
import shutil
from typing import Callable, Optional
from dataclasses import dataclass

from .ffmpeg_utils import get_ffmpeg_path, FFmpegHelper
from .error_handler import ErrorDiagnostics, format_error_message
from ..utils.logger import logger
from ..utils.file_utils import get_temp_dir


@dataclass
class ProcessResult:
    """处理结果"""
    success: bool
    message: str = ""
    error: str = ""


def _make_even(n: int) -> int:
    """确保数值是偶数（libx264要求宽高必须是偶数）"""
    return n if n % 2 == 0 else n - 1


def _build_scale_filter(width: int, height: int, mode: str = "stretch") -> str:
    """
    根据缩放模式构建FFmpeg scale滤镜字符串

    Args:
        width: 目标宽度
        height: 目标高度
        mode: 缩放模式
            - "stretch": 拉伸填满（可能变形）
            - "fill": 填充裁切（保持比例，裁剪超出部分）
            - "fit": 适应留黑边（保持比例，添加黑边）

    Returns:
        FFmpeg scale滤镜字符串
    """
    if mode == "fill":
        # 填充模式：放大到覆盖目标区域，然后居中裁剪
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
    elif mode == "fit":
        # 适应模式：缩小到适应目标区域，然后居中添加黑边
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        )
    else:
        # 拉伸模式（默认）：直接拉伸到目标尺寸
        return f"scale={width}:{height}:force_original_aspect_ratio=disable"


class VideoProcessor:
    """视频处理器"""

    # 拼接方式常量
    MERGE_A_C = "a+c"  # 模板左/上 + 列表左/上
    MERGE_A_D = "a+d"  # 模板左/上 + 列表右/下
    MERGE_B_C = "b+c"  # 模板右/下 + 列表左/上
    MERGE_B_D = "b+d"  # 模板右/下 + 列表右/下
    MERGE_GRID = "grid"  # 四宫格

    # 分割方式常量
    SPLIT_HORIZONTAL = "horizontal"  # 左右分割
    SPLIT_VERTICAL = "vertical"  # 上下分割

    def __init__(self):
        self.temp_dir = get_temp_dir()
        self._progress_callback: Optional[Callable[[float, str], None]] = None
        self.last_error = ""

    def set_progress_callback(self, callback: Callable[[float, str], None]):
        """设置进度回调函数"""
        self._progress_callback = callback

    def _report_progress(self, progress: float, message: str):
        """报告进度"""
        if self._progress_callback:
            self._progress_callback(progress, message)

    def _run_ffmpeg(self, cmd: list, description: str = "", context: dict = None) -> tuple:
        """
        运行FFmpeg命令，返回(成功与否, 错误信息)

        Args:
            cmd: FFmpeg命令列表
            description: 操作描述
            context: 上下文信息（用于错误诊断）
        """
        try:
            self._report_progress(0, f"正在{description}...")
            logger.info(f"执行FFmpeg命令: {description}")
            logger.debug(f"FFmpeg命令: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg执行失败，返回码: {result.returncode}")
                logger.debug(f"FFmpeg stderr: {result.stderr}")

                # 使用智能错误诊断
                error_desc, suggestions = ErrorDiagnostics.diagnose_ffmpeg_error(
                    result.stderr,
                    context
                )
                error_msg = format_error_message(error_desc, suggestions)
                return False, error_msg

            logger.info(f"FFmpeg执行成功: {description}")
            return True, ""

        except FileNotFoundError:
            logger.error("FFmpeg未找到")
            return False, "FFmpeg未找到，请确保已安装并添加到PATH"
        except Exception as e:
            logger.exception(f"运行FFmpeg异常: {e}")
            return False, f"运行FFmpeg失败: {str(e)}"

    def process_videos(
        self,
        template_video: str,
        target_video: str,
        output_path: str,
        split_mode: str,
        merge_mode: str,
        split_ratio: float = 0.5,
        target_split_ratio: float = None,
        target_scale_percent: int = 100,
        cover_type: str = "none",
        cover_frame_time: float = 0.0,
        cover_image_path: str = None,
        cover_duration: float = 3.0,
        cover_frame_source: str = "template",
        position_order: str = "template_first",
        audio_source: str = "template",
        custom_audio_path: str = None,
        output_width: int = None,
        output_height: int = None,
        scale_mode: str = None,
        output_ratio: float = None,
        duration_mode: str = "template",
        template_scale_mode: str = "fit",
        list_scale_mode: str = "fit",
        template_volume: int = 100,
        list_volume: int = 100,
        custom_volume: int = 100,
        divider_mask_path: str = None,
        divider_color: str = "#FFFFFF",
        divider_width: int = 0,
        process_mode: str = "split"
    ) -> ProcessResult:
        """
        处理视频：分割并拼接

        Args:
            template_video: 模板视频路径
            target_video: 目标视频路径
            output_path: 输出路径
            split_mode: 分割方式 (horizontal/vertical)
            merge_mode: 拼接方式 (a+c, a+d, b+c, b+d, grid)
            split_ratio: 模板视频分割比例 (0.1-0.9)
            target_split_ratio: 目标视频分割比例 (0.1-0.9)
            target_scale_percent: 目标视频缩放百分比 (50-200)
            cover_type: 封面类型 (none/frame/image)
            cover_frame_time: 封面帧时间点（秒）
            cover_image_path: 封面图片路径
            cover_duration: 封面显示时长（秒）
            cover_frame_source: 封面帧来源 (template/list/merged)
            position_order: 位置顺序 (template_first/list_first)
            audio_source: 音频来源 (template/list/mix/custom/none)
            custom_audio_path: 自定义音频文件路径
            output_width: 自定义输出宽度
            output_height: 自定义输出高度
            scale_mode: 缩放模式 (fit/fill/stretch) - 通用模式，如未指定独立模式则使用此值
            output_ratio: 输出比例 - 上/左部分在输出中占的比例 (0.1-0.9)，None表示跟随split_ratio
            duration_mode: 输出时长模式 (template/list)
            template_scale_mode: 模板视频缩放模式 (fit/fill/stretch)
            list_scale_mode: 列表视频缩放模式 (fit/fill/stretch)
            template_volume: 模板音频音量百分比 (0-200)
            list_volume: 列表音频音量百分比 (0-200)
            custom_volume: 自定义音频音量百分比 (0-200)

        Returns:
            ProcessResult: 处理结果
        """
        temp_files = []

        try:
            self._report_progress(0.05, "获取视频信息")

            if target_split_ratio is None:
                target_split_ratio = split_ratio

            # 检查文件是否存在
            if not os.path.exists(template_video):
                return ProcessResult(False, error=f"模板视频不存在: {template_video}")
            if not os.path.exists(target_video):
                return ProcessResult(False, error=f"目标视频不存在: {target_video}")

            # 获取视频信息
            template_info = FFmpegHelper.get_video_info(template_video)
            target_info = FFmpegHelper.get_video_info(target_video)

            if not template_info:
                return ProcessResult(False, error="无法获取模板视频信息，文件可能损坏")
            if not target_info:
                return ProcessResult(False, error="无法获取目标视频信息，文件可能损坏")

            # 检查视频尺寸
            if template_info.width == 0 or template_info.height == 0:
                return ProcessResult(False, error="模板视频尺寸无效")
            if target_info.width == 0 or target_info.height == 0:
                return ProcessResult(False, error="目标视频尺寸无效")

            # 确定输出尺寸
            if output_width is not None and output_height is not None and output_width > 0 and output_height > 0:
                out_width = output_width
                out_height = output_height
                logger.info(f"使用自定义输出尺寸: {out_width}x{out_height}")
            else:
                out_width = template_info.width
                out_height = template_info.height
                logger.info(f"使用模板视频尺寸: {out_width}x{out_height}")

            # 根据 duration_mode 确定输出时长
            if duration_mode == "list":
                max_duration = target_info.duration
                logger.info(f"使用列表视频时长: {max_duration:.2f}秒")
            else:
                max_duration = template_info.duration
                logger.info(f"使用模板视频时长: {max_duration:.2f}秒")

            if max_duration <= 0:
                return ProcessResult(False, error="视频时长无效")

            # 检查音频状态
            template_has_audio = template_info.has_audio
            target_has_audio = target_info.has_audio
            logger.debug(f"音频状态: 模板={template_has_audio}, 目标={target_has_audio}, 音频来源={audio_source}")

            # 检查模板视频是否有透明通道
            template_has_alpha = template_info.has_alpha
            logger.info(f"模板视频透明通道: {template_has_alpha}")

            self._report_progress(0.1, "构建处理命令")

            # 验证自定义音频文件
            if audio_source == "custom" and custom_audio_path:
                if not os.path.exists(custom_audio_path):
                    return ProcessResult(False, error=f"自定义音频文件不存在: {custom_audio_path}")

            # 构建filter_complex
            try:
                # 如果没有指定 output_ratio，则使用 split_ratio
                actual_output_ratio = output_ratio if output_ratio is not None else split_ratio

                # 检查是否使用曲线蒙版
                use_mask = divider_mask_path and os.path.exists(divider_mask_path)

                # 检查是否使用视频叠加模式
                if process_mode == "overlay":
                    logger.info("使用视频叠加模式")
                    filter_complex = self._build_overlay_filter_complex(
                        out_width, out_height,
                        template_has_audio, target_has_audio,
                        audio_source,
                        scale_mode or "fit",
                        template_scale_mode,
                        list_scale_mode,
                        template_volume,
                        list_volume
                    )
                # 检查是否使用透明通道模式（模板视频有alpha通道时）
                elif template_has_alpha and not use_mask:
                    logger.info("检测到模板视频有透明通道，使用overlay模式")
                    filter_complex = self._build_alpha_filter_complex(
                        split_mode, merge_mode,
                        split_ratio, target_split_ratio,
                        out_width, out_height,
                        template_has_audio, target_has_audio,
                        target_scale_percent,
                        position_order,
                        audio_source,
                        scale_mode or "fit",
                        actual_output_ratio,
                        template_scale_mode,
                        list_scale_mode,
                        template_volume,
                        list_volume
                    )
                elif use_mask:
                    logger.info(f"使用曲线蒙版: {divider_mask_path}")
                    filter_complex = self._build_mask_filter_complex(
                        out_width, out_height,
                        template_has_audio, target_has_audio,
                        position_order,
                        audio_source,
                        template_scale_mode,
                        list_scale_mode,
                        template_volume,
                        list_volume,
                        divider_color,
                        divider_width
                    )
                else:
                    filter_complex = self._build_filter_complex(
                        split_mode, merge_mode,
                        split_ratio, target_split_ratio,
                        out_width, out_height,
                        template_info.duration, target_info.duration,
                        template_has_audio, target_has_audio,
                        target_scale_percent,
                        position_order,
                        audio_source,
                        scale_mode or "fit",
                        actual_output_ratio,
                        template_scale_mode,
                        list_scale_mode,
                        template_volume,
                        list_volume
                    )
            except ValueError as e:
                return ProcessResult(False, error=str(e))

            # 构建FFmpeg命令
            ffmpeg = get_ffmpeg_path()
            cmd = [
                ffmpeg, '-y',
                '-stream_loop', '-1', '-i', template_video,
                '-stream_loop', '-1', '-i', target_video,
            ]

            # 如果使用蒙版，添加蒙版图片作为输入
            if use_mask:
                cmd.extend(['-i', divider_mask_path])

            if audio_source == "custom" and custom_audio_path:
                cmd.extend(['-stream_loop', '-1', '-i', custom_audio_path])

            # 如果是自定义音频，添加音量滤镜
            if audio_source == "custom" and custom_audio_path:
                custom_vol = custom_volume / 100.0
                custom_audio_filter = f";[2:a]volume={custom_vol}[outa]"
                filter_complex = filter_complex + custom_audio_filter

            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '[outv]',
            ])

            # 音频映射
            has_audio_output = False
            if audio_source == "none":
                logger.debug("音频模式: 静音，不映射音频")
            elif audio_source == "custom" and custom_audio_path:
                cmd.extend(['-map', '[outa]'])
                cmd.extend(['-c:a', 'aac', '-b:a', '128k'])
                has_audio_output = True
            elif audio_source == "template" and template_has_audio:
                cmd.extend(['-map', '[outa]'])
                cmd.extend(['-c:a', 'aac', '-b:a', '128k'])
                has_audio_output = True
            elif audio_source == "list" and target_has_audio:
                cmd.extend(['-map', '[outa]'])
                cmd.extend(['-c:a', 'aac', '-b:a', '128k'])
                has_audio_output = True
            elif audio_source == "mix" and (template_has_audio or target_has_audio):
                cmd.extend(['-map', '[outa]'])
                cmd.extend(['-c:a', 'aac', '-b:a', '128k'])
                has_audio_output = True

            # 根据是否有alpha通道选择输出编码
            if template_has_alpha and output_path.lower().endswith('.mov'):
                # MOV格式支持alpha通道，使用ProRes 4444编码
                cmd.extend([
                    '-t', str(max_duration),
                    '-c:v', 'prores_ks',
                    '-profile:v', '4444',
                    '-pix_fmt', 'yuva444p10le',
                    output_path
                ])
                logger.info("使用ProRes 4444编码（支持透明通道）")
            else:
                cmd.extend([
                    '-t', str(max_duration),
                    '-c:v', 'libx264',
                    '-preset', 'medium',
                    '-crf', '23',
                    output_path
                ])

            self._report_progress(0.2, "处理视频")

            success, error_msg = self._run_ffmpeg(cmd, "处理视频")

            if not success:
                self._report_progress(0, "处理失败")
                return ProcessResult(False, error=error_msg)

            # 处理封面
            if cover_type != "none" and success:
                self._report_progress(0.8, "处理封面")
                if cover_frame_source == "template":
                    frame_source_video = template_video
                elif cover_frame_source == "list":
                    frame_source_video = target_video
                elif cover_frame_source == "merged":
                    frame_source_video = output_path
                else:
                    frame_source_video = target_video

                cover_result = self._add_cover_to_video(
                    output_path, out_width, out_height,
                    cover_type, cover_frame_time, cover_image_path,
                    cover_duration, frame_source_video, temp_files
                )
                if not cover_result.success:
                    return cover_result

            # 清理临时文件
            self._cleanup_temp_files(temp_files)

            self._report_progress(1.0, "处理完成")
            return ProcessResult(True, message="处理成功")

        except Exception as e:
            self._cleanup_temp_files(temp_files)
            error_msg = f"处理异常: {str(e)}"
            self._report_progress(0, error_msg)
            return ProcessResult(False, error=error_msg)

    def _add_cover_to_video(
        self,
        video_path: str,
        width: int,
        height: int,
        cover_type: str,
        cover_frame_time: float,
        cover_image_path: str,
        cover_duration: float,
        source_video: str,
        temp_files: list
    ) -> ProcessResult:
        """为视频添加封面"""
        temp_dir = get_temp_dir()
        unique_id = str(uuid.uuid4())[:8]

        try:
            if cover_type == "frame":
                cover_frame_path = os.path.join(temp_dir, f"cover_frame_{unique_id}.jpg")
                if not FFmpegHelper.extract_frame(source_video, cover_frame_path, cover_frame_time):
                    return ProcessResult(False, error="提取封面帧失败")
                temp_files.append(cover_frame_path)
                image_path = cover_frame_path
            elif cover_type == "image":
                if not cover_image_path or not os.path.exists(cover_image_path):
                    return ProcessResult(False, error="封面图片不存在")
                image_path = cover_image_path
            else:
                return ProcessResult(True)

            # 将封面图片转换为视频
            cover_video_path = os.path.join(temp_dir, f"cover_video_{unique_id}.mp4")
            if not FFmpegHelper.image_to_video(image_path, cover_video_path, cover_duration, width, height):
                return ProcessResult(False, error="封面图片转视频失败")
            temp_files.append(cover_video_path)

            # 拼接封面视频和主视频
            final_output = os.path.join(temp_dir, f"final_{unique_id}.mp4")
            ffmpeg = get_ffmpeg_path()
            main_has_audio = FFmpegHelper.check_has_audio(video_path)
            logger.debug(f"封面处理: 主视频音频状态={main_has_audio}, video_path={video_path}")

            if main_has_audio:
                # 使用标准采样率44100Hz（最常见的采样率）
                sample_rate = 44100
                logger.debug(f"封面处理: 生成静音封面音频，采样率={sample_rate}Hz")

                cmd = [
                    ffmpeg, '-y',
                    '-i', cover_video_path,
                    '-i', video_path,
                    '-filter_complex',
                    f'[0:v]scale={width}:{height}:force_original_aspect_ratio=disable,setsar=1[v0];'
                    f'[1:v]scale={width}:{height}:force_original_aspect_ratio=disable,setsar=1[v1];'
                    f'[v0][v1]concat=n=2:v=1:a=0[outv];'
                    f'anullsrc=channel_layout=stereo:sample_rate={sample_rate}:duration={cover_duration}[a0];'
                    f'[a0][1:a]concat=n=2:v=0:a=1[outa]',
                    '-map', '[outv]',
                    '-map', '[outa]',
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-preset', 'medium',
                    '-crf', '23',
                    final_output
                ]
            else:
                cmd = [
                    ffmpeg, '-y',
                    '-i', cover_video_path,
                    '-i', video_path,
                    '-filter_complex',
                    f'[0:v]scale={width}:{height}:force_original_aspect_ratio=disable,setsar=1[v0];'
                    f'[1:v]scale={width}:{height}:force_original_aspect_ratio=disable,setsar=1[v1];'
                    f'[v0][v1]concat=n=2:v=1:a=0[outv]',
                    '-map', '[outv]',
                    '-c:v', 'libx264',
                    '-preset', 'medium',
                    '-crf', '23',
                    final_output
                ]

            success, error_msg = self._run_ffmpeg(cmd, "添加封面")

            if success:
                shutil.move(final_output, video_path)
                return ProcessResult(True)
            else:
                return ProcessResult(False, error=f"添加封面失败: {error_msg}")

        except Exception as e:
            return ProcessResult(False, error=f"添加封面异常: {str(e)}")

    def _cleanup_temp_files(self, temp_files: list):
        """清理临时文件"""
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except OSError as e:
                logger.warning(f"无法删除临时文件 {temp_file}: {e}")

    def _build_overlay_filter_complex(
        self,
        out_width: int,
        out_height: int,
        template_has_audio: bool = True,
        target_has_audio: bool = True,
        audio_source: str = "template",
        scale_mode: str = "fit",
        template_scale_mode: str = "fit",
        list_scale_mode: str = "fit",
        template_volume: int = 100,
        list_volume: int = 100
    ) -> str:
        """
        构建视频叠加滤镜 - 前景视频（模板）居中叠加在背景视频（列表）上

        Args:
            out_width: 输出宽度
            out_height: 输出高度
            template_has_audio: 模板是否有音频
            target_has_audio: 目标是否有音频
            audio_source: 音频来源
            scale_mode: 通用缩放模式
            template_scale_mode: 模板缩放模式
            list_scale_mode: 列表缩放模式
            template_volume: 模板音量
            list_volume: 列表音量
        """
        out_width = _make_even(out_width)
        out_height = _make_even(out_height)

        template_vol = template_volume / 100.0
        list_vol = list_volume / 100.0

        # 音频滤镜
        audio_filter = None
        if audio_source == "mix":
            if template_has_audio and target_has_audio:
                audio_filter = f"[0:a]volume={template_vol}[a0];[1:a]volume={list_vol}[a1];[a0][a1]amix=inputs=2:duration=longest[outa]"
            elif template_has_audio:
                audio_filter = f"[0:a]volume={template_vol}[outa]"
            elif target_has_audio:
                audio_filter = f"[1:a]volume={list_vol}[outa]"
        elif audio_source == "template":
            if template_has_audio:
                audio_filter = f"[0:a]volume={template_vol}[outa]"
        elif audio_source == "list":
            if target_has_audio:
                audio_filter = f"[1:a]volume={list_vol}[outa]"

        # 缩放滤镜
        bg_scale = _build_scale_filter(out_width, out_height, list_scale_mode)
        fg_scale = _build_scale_filter(out_width, out_height, template_scale_mode)

        # [0:v]=模板(前景), [1:v]=列表(背景)
        video_filter = (
            f"[1:v]{bg_scale}[bg];"
            f"[0:v]{fg_scale}[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2:format=yuv420[outv]"
        )

        if audio_filter:
            return f"{video_filter};{audio_filter}"
        return video_filter

    def _build_alpha_filter_complex(
        self,
        split_mode: str,
        merge_mode: str,
        split_ratio: float,
        target_split_ratio: float,
        out_width: int,
        out_height: int,
        template_has_audio: bool = True,
        target_has_audio: bool = True,
        target_scale_percent: int = 100,
        position_order: str = "template_first",
        audio_source: str = "template",
        scale_mode: str = "fit",
        output_ratio: float = None,
        template_scale_mode: str = "fit",
        list_scale_mode: str = "fit",
        template_volume: int = 100,
        list_volume: int = 100
    ) -> str:
        """
        构建支持透明通道的filter_complex字符串
        使用overlay滤镜将模板视频叠加到列表视频上，透明部分显示列表视频内容

        Args:
            参数同 _build_filter_complex
        """
        logger.debug(f"透明通道模式: 模板缩放={template_scale_mode}, 列表缩放={list_scale_mode}")
        logger.debug(f"音量设置: 模板={template_volume}%, 列表={list_volume}%")

        # 计算音量倍数
        template_vol = template_volume / 100.0
        list_vol = list_volume / 100.0

        # 音频filter
        audio_filter = None
        if audio_source == "mix":
            if template_has_audio and target_has_audio:
                audio_filter = f"[0:a]volume={template_vol}[a0];[1:a]volume={list_vol}[a1];[a0][a1]amix=inputs=2:duration=longest[outa]"
            elif template_has_audio:
                audio_filter = f"[0:a]volume={template_vol}[outa]"
            elif target_has_audio:
                audio_filter = f"[1:a]volume={list_vol}[outa]"
        elif audio_source == "template":
            if template_has_audio:
                audio_filter = f"[0:a]volume={template_vol}[outa]"
        elif audio_source == "list":
            if target_has_audio:
                audio_filter = f"[1:a]volume={list_vol}[outa]"

        scale_factor = target_scale_percent / 100.0
        target_scaled_width = _make_even(int(out_width * scale_factor))
        target_scaled_height = _make_even(int(out_height * scale_factor))
        out_width = _make_even(out_width)
        out_height = _make_even(out_height)

        actual_output_ratio = output_ratio if output_ratio is not None else split_ratio

        # 构建缩放滤镜
        template_scale = _build_scale_filter(out_width, out_height, template_scale_mode)
        list_scale = _build_scale_filter(out_width, out_height, list_scale_mode)

        # 确定前景和背景
        # 模板视频有透明通道，应该作为前景叠加在列表视频上
        swap_order = (position_order == "list_first")

        if swap_order:
            # 列表视频在前景，模板视频在背景（不常见，但支持）
            bg_scale = list_scale
            fg_scale = template_scale
            bg_input = "1:v"
            fg_input = "0:v"
        else:
            # 模板视频在前景（透明部分会显示背景），列表视频在背景
            bg_scale = list_scale
            fg_scale = template_scale
            bg_input = "1:v"
            fg_input = "0:v"

        # 计算裁剪区域
        if split_mode == self.SPLIT_HORIZONTAL:
            # 水平分割
            part_width = _make_even(int(out_width * actual_output_ratio))

            if merge_mode == self.MERGE_A_C:
                # 使用左半部分
                video_filter = (
                    f"[{bg_input}]{bg_scale},crop={part_width}:{out_height}:0:0[bg];"
                    f"[{fg_input}]{fg_scale},crop={part_width}:{out_height}:0:0[fg];"
                    f"[bg][fg]overlay=0:0:format=yuv420[outv]"
                )
            elif merge_mode == self.MERGE_A_D:
                # 模板左半 + 列表右半（列表右半没有透明通道，使用普通hstack）
                list_part_width = _make_even(int(target_scaled_width * target_split_ratio))
                bg_out_width = out_width - part_width
                video_filter = (
                    f"[{fg_input}]{fg_scale},crop={part_width}:{out_height}:0:0[fg];"
                    f"[{bg_input}]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_scaled_width - list_part_width}:{target_scaled_height}:{list_part_width}:0,"
                    f"scale={bg_out_width}:{out_height}:force_original_aspect_ratio=disable[bg];"
                    f"[fg][bg]hstack=inputs=2[outv]"
                )
            elif merge_mode == self.MERGE_B_C:
                # 模板右半 + 列表左半
                list_part_width = _make_even(int(target_scaled_width * target_split_ratio))
                fg_out_width = out_width - part_width
                video_filter = (
                    f"[{fg_input}]{fg_scale},crop={out_width - part_width}:{out_height}:{part_width}:0,"
                    f"scale={fg_out_width}:{out_height}:force_original_aspect_ratio=disable[fg];"
                    f"[{bg_input}]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                    f"crop={list_part_width}:{target_scaled_height}:0:0,"
                    f"scale={part_width}:{out_height}:force_original_aspect_ratio=disable[bg];"
                    f"[bg][fg]hstack=inputs=2[outv]"
                )
            elif merge_mode == self.MERGE_B_D:
                # 使用右半部分
                video_filter = (
                    f"[{bg_input}]{bg_scale},crop={out_width - part_width}:{out_height}:{part_width}:0[bg];"
                    f"[{fg_input}]{fg_scale},crop={out_width - part_width}:{out_height}:{part_width}:0[fg];"
                    f"[bg][fg]overlay=0:0:format=yuv420[outv]"
                )
            else:
                # GRID模式
                half_width = out_width // 2
                half_height = out_height // 2
                video_filter = (
                    f"[{fg_input}]{fg_scale},crop={half_width}:{half_height}:0:0[tl];"
                    f"[{fg_input}]{fg_scale},crop={half_width}:{half_height}:{half_width}:0[tr];"
                    f"[{bg_input}]{bg_scale},crop={half_width}:{half_height}:0:0[bl];"
                    f"[{bg_input}]{bg_scale},crop={half_width}:{half_height}:{half_width}:0[br];"
                    f"[tl][tr]hstack=inputs=2[top];"
                    f"[bl][br]hstack=inputs=2[bottom];"
                    f"[top][bottom]vstack=inputs=2[outv]"
                )
        else:
            # 垂直分割
            part_height = _make_even(int(out_height * actual_output_ratio))

            if merge_mode == self.MERGE_A_C:
                # 使用上半部分
                video_filter = (
                    f"[{bg_input}]{bg_scale},crop={out_width}:{part_height}:0:0[bg];"
                    f"[{fg_input}]{fg_scale},crop={out_width}:{part_height}:0:0[fg];"
                    f"[bg][fg]overlay=0:0:format=yuv420[outv]"
                )
            elif merge_mode == self.MERGE_A_D:
                list_part_height = _make_even(int(target_scaled_height * target_split_ratio))
                bg_out_height = out_height - part_height
                video_filter = (
                    f"[{fg_input}]{fg_scale},crop={out_width}:{part_height}:0:0[fg];"
                    f"[{bg_input}]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_scaled_width}:{target_scaled_height - list_part_height}:0:{list_part_height},"
                    f"scale={out_width}:{bg_out_height}:force_original_aspect_ratio=disable[bg];"
                    f"[fg][bg]vstack=inputs=2[outv]"
                )
            elif merge_mode == self.MERGE_B_C:
                list_part_height = _make_even(int(target_scaled_height * target_split_ratio))
                fg_out_height = out_height - part_height
                video_filter = (
                    f"[{fg_input}]{fg_scale},crop={out_width}:{out_height - part_height}:0:{part_height},"
                    f"scale={out_width}:{fg_out_height}:force_original_aspect_ratio=disable[fg];"
                    f"[{bg_input}]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_scaled_width}:{list_part_height}:0:0,"
                    f"scale={out_width}:{part_height}:force_original_aspect_ratio=disable[bg];"
                    f"[bg][fg]vstack=inputs=2[outv]"
                )
            elif merge_mode == self.MERGE_B_D:
                video_filter = (
                    f"[{bg_input}]{bg_scale},crop={out_width}:{out_height - part_height}:0:{part_height}[bg];"
                    f"[{fg_input}]{fg_scale},crop={out_width}:{out_height - part_height}:0:{part_height}[fg];"
                    f"[bg][fg]overlay=0:0:format=yuv420[outv]"
                )
            else:
                # GRID模式
                half_width = out_width // 2
                half_height = out_height // 2
                video_filter = (
                    f"[{fg_input}]{fg_scale},crop={half_width}:{half_height}:0:0[tl];"
                    f"[{fg_input}]{fg_scale},crop={half_width}:{half_height}:0:{half_height}[tr];"
                    f"[{bg_input}]{bg_scale},crop={half_width}:{half_height}:0:0[bl];"
                    f"[{bg_input}]{bg_scale},crop={half_width}:{half_height}:0:{half_height}[br];"
                    f"[tl][tr]hstack=inputs=2[top];"
                    f"[bl][br]hstack=inputs=2[bottom];"
                    f"[top][bottom]vstack=inputs=2[outv]"
                )

        if audio_filter:
            return f"{video_filter};{audio_filter}"
        return video_filter

    def _build_filter_complex(
        self,
        split_mode: str,
        merge_mode: str,
        split_ratio: float,
        target_split_ratio: float,
        out_width: int,
        out_height: int,
        template_duration: float,
        target_duration: float,
        template_has_audio: bool = True,
        target_has_audio: bool = True,
        target_scale_percent: int = 100,
        position_order: str = "template_first",
        audio_source: str = "template",
        scale_mode: str = "fit",
        output_ratio: float = None,
        template_scale_mode: str = "fit",
        list_scale_mode: str = "fit",
        template_volume: int = 100,
        list_volume: int = 100
    ) -> str:
        """构建FFmpeg filter_complex字符串

        Args:
            output_ratio: 输出比例 - 上/左部分在输出中占的比例，None表示跟随split_ratio
            template_scale_mode: 模板视频缩放模式 (fit/fill/stretch)
            list_scale_mode: 列表视频缩放模式 (fit/fill/stretch)
            template_volume: 模板音频音量百分比 (0-200)
            list_volume: 列表音频音量百分比 (0-200)
        """
        logger.debug(f"缩放模式: 模板={template_scale_mode}, 列表={list_scale_mode}")
        logger.debug(f"音量设置: 模板={template_volume}%, 列表={list_volume}%")

        # 计算音量倍数
        template_vol = template_volume / 100.0
        list_vol = list_volume / 100.0

        # 音频filter（带音量控制）
        audio_filter = None
        if audio_source == "mix":
            if template_has_audio and target_has_audio:
                audio_filter = f"[0:a]volume={template_vol}[a0];[1:a]volume={list_vol}[a1];[a0][a1]amix=inputs=2:duration=longest[outa]"
            elif template_has_audio:
                audio_filter = f"[0:a]volume={template_vol}[outa]"
            elif target_has_audio:
                audio_filter = f"[1:a]volume={list_vol}[outa]"
        elif audio_source == "template":
            if template_has_audio:
                audio_filter = f"[0:a]volume={template_vol}[outa]"
        elif audio_source == "list":
            if target_has_audio:
                audio_filter = f"[1:a]volume={list_vol}[outa]"

        swap_order = (position_order == "list_first")
        scale_factor = target_scale_percent / 100.0
        # 确保所有尺寸是偶数（libx264要求）
        target_scaled_width = _make_even(int(out_width * scale_factor))
        target_scaled_height = _make_even(int(out_height * scale_factor))
        out_width = _make_even(out_width)
        out_height = _make_even(out_height)

        # 使用 output_ratio 决定输出中各部分的大小，如果未指定则使用 split_ratio
        actual_output_ratio = output_ratio if output_ratio is not None else split_ratio

        if split_mode == self.SPLIT_HORIZONTAL:
            # 输出中各部分的宽度（由 output_ratio 决定）
            template_part_a_width = _make_even(int(out_width * actual_output_ratio))
            template_part_b_width = out_width - template_part_a_width
            # 从列表视频裁剪的区域（由 target_split_ratio 决定）
            target_part_c_width = _make_even(int(target_scaled_width * target_split_ratio))
            target_part_d_width = target_scaled_width - target_part_c_width

            video_filter = self._build_horizontal_filter(
                merge_mode, swap_order,
                out_width, out_height,
                template_part_a_width, template_part_b_width,
                target_scaled_width, target_scaled_height,
                target_part_c_width, target_part_d_width,
                template_scale_mode, list_scale_mode
            )
        else:
            # 输出中各部分的高度（由 output_ratio 决定）
            template_part_a_height = _make_even(int(out_height * actual_output_ratio))
            template_part_b_height = out_height - template_part_a_height
            # 从列表视频裁剪的区域（由 target_split_ratio 决定）
            target_part_c_height = _make_even(int(target_scaled_height * target_split_ratio))
            target_part_d_height = target_scaled_height - target_part_c_height

            video_filter = self._build_vertical_filter(
                merge_mode, swap_order,
                out_width, out_height,
                template_part_a_height, template_part_b_height,
                target_scaled_width, target_scaled_height,
                target_part_c_height, target_part_d_height,
                template_scale_mode, list_scale_mode
            )

        if audio_filter:
            return f"{video_filter};{audio_filter}"
        return video_filter

    def _build_mask_filter_complex(
        self,
        out_width: int,
        out_height: int,
        template_has_audio: bool,
        target_has_audio: bool,
        position_order: str,
        audio_source: str,
        template_scale_mode: str,
        list_scale_mode: str,
        template_volume: int,
        list_volume: int,
        divider_color: str = "#FFFFFF",
        divider_width: int = 0
    ) -> str:
        """构建基于蒙版的视频合成滤镜

        使用蒙版图片将两个视频混合，实现曲线分界线效果。
        蒙版中白色区域显示第一个视频，黑色区域显示第二个视频。

        Args:
            out_width: 输出宽度
            out_height: 输出高度
            template_has_audio: 模板是否有音频
            target_has_audio: 目标是否有音频
            position_order: 位置顺序
            audio_source: 音频来源
            template_scale_mode: 模板缩放模式
            list_scale_mode: 列表缩放模式
            template_volume: 模板音量
            list_volume: 列表音量
            divider_color: 分界线颜色
            divider_width: 分界线宽度
        """
        template_vol = template_volume / 100.0
        list_vol = list_volume / 100.0

        # 音频filter
        audio_filter = None
        if audio_source == "mix":
            if template_has_audio and target_has_audio:
                audio_filter = f"[0:a]volume={template_vol}[a0];[1:a]volume={list_vol}[a1];[a0][a1]amix=inputs=2:duration=longest[outa]"
            elif template_has_audio:
                audio_filter = f"[0:a]volume={template_vol}[outa]"
            elif target_has_audio:
                audio_filter = f"[1:a]volume={list_vol}[outa]"
        elif audio_source == "template":
            if template_has_audio:
                audio_filter = f"[0:a]volume={template_vol}[outa]"
        elif audio_source == "list":
            if target_has_audio:
                audio_filter = f"[1:a]volume={list_vol}[outa]"

        # 确定哪个视频在前景（通过蒙版显示），哪个在背景
        swap_order = (position_order == "list_first")

        # 构建缩放滤镜
        template_scale = _build_scale_filter(out_width, out_height, template_scale_mode)
        list_scale = _build_scale_filter(out_width, out_height, list_scale_mode)

        if swap_order:
            # 列表视频在前景（白色区域），模板视频在背景
            fg_input = "1:v"
            bg_input = "0:v"
            fg_scale = list_scale
            bg_scale = template_scale
        else:
            # 模板视频在前景（白色区域），列表视频在背景
            fg_input = "0:v"
            bg_input = "1:v"
            fg_scale = template_scale
            bg_scale = list_scale

        # 视频滤镜：
        # 1. 缩放两个视频到输出尺寸
        # 2. 将蒙版缩放到输出尺寸并转换为alpha通道
        # 3. 使用alphamerge将蒙版应用到前景视频
        # 4. 使用overlay将前景视频叠加到背景视频上

        # 如果有分界线宽度，需要在蒙版边缘绘制线条
        if divider_width > 0:
            # 使用geq滤镜扩展蒙版边缘来创建分界线效果
            # 先检测边缘，然后用颜色填充
            # 注意：split后原始标签被消费，需要分成3份用于不同用途
            video_filter = (
                f"[{fg_input}]{fg_scale}[fg];"
                f"[{bg_input}]{bg_scale}[bg];"
                # 缩放蒙版并分成3份：用于边缘检测(2份)和alphamerge(1份)
                f"[2:v]scale={out_width}:{out_height},format=gray,split=3[mask1][mask2][mask3];"
                # 创建分界线：通过膨胀和腐蚀检测边缘
                f"[mask1]erosion=threshold0=128:threshold1=128:threshold2=128:threshold3=128[eroded];"
                f"[mask2][eroded]blend=all_expr='if(gt(A,B),255,0)'[edge];"
                # 创建彩色分界线
                f"color=c={divider_color}:s={out_width}x{out_height}[line_color];"
                f"[line_color][edge]alphamerge[line];"
                # 使用mask3进行视频合并
                f"[fg][mask3]alphamerge[fg_alpha];"
                f"[bg][fg_alpha]overlay=0:0[merged];"
                f"[merged][line]overlay=0:0[outv]"
            )
        else:
            video_filter = (
                f"[{fg_input}]{fg_scale}[fg];"
                f"[{bg_input}]{bg_scale}[bg];"
                f"[2:v]scale={out_width}:{out_height},format=gray[mask];"
                f"[fg][mask]alphamerge[fg_alpha];"
                f"[bg][fg_alpha]overlay=0:0[outv]"
            )

        if audio_filter:
            return f"{video_filter};{audio_filter}"
        return video_filter

    def _build_horizontal_filter(
        self, merge_mode: str, swap_order: bool,
        out_width: int, out_height: int,
        part_a_width: int, part_b_width: int,
        target_width: int, target_height: int,
        part_c_width: int, part_d_width: int,
        template_scale_mode: str = "fit",
        list_scale_mode: str = "fit"
    ) -> str:
        """构建水平分割滤镜"""
        # 根据缩放模式生成最终缩放滤镜
        t_scale_left = _build_scale_filter(part_a_width, out_height, template_scale_mode)
        t_scale_right = _build_scale_filter(part_b_width, out_height, template_scale_mode)
        l_scale_left = _build_scale_filter(part_a_width, out_height, list_scale_mode)
        l_scale_right = _build_scale_filter(part_b_width, out_height, list_scale_mode)

        if merge_mode == self.MERGE_A_C:
            if swap_order:
                # 列表C在左，模板A在右
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_c_width}:{target_height}:0:0,"
                    f"{l_scale_left}[vc];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_a_width}:{out_height}:0:0,"
                    f"{t_scale_right}[va];"
                    f"[vc][va]hstack=inputs=2[outv]"
                )
            else:
                # 模板A在左，列表C在右
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_a_width}:{out_height}:0:0,"
                    f"{t_scale_left}[va];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_c_width}:{target_height}:0:0,"
                    f"{l_scale_right}[vc];"
                    f"[va][vc]hstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_A_D:
            if swap_order:
                # 列表D在左，模板A在右
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_d_width}:{target_height}:{target_width}-{part_d_width}:0,"
                    f"{l_scale_left}[vd];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_a_width}:{out_height}:0:0,"
                    f"{t_scale_right}[va];"
                    f"[vd][va]hstack=inputs=2[outv]"
                )
            else:
                # 模板A在左，列表D在右
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_a_width}:{out_height}:0:0,"
                    f"{t_scale_left}[va];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_d_width}:{target_height}:{target_width}-{part_d_width}:0,"
                    f"{l_scale_right}[vd];"
                    f"[va][vd]hstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_B_C:
            if swap_order:
                # 列表C在左，模板B在右
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_c_width}:{target_height}:0:0,"
                    f"{l_scale_left}[vc];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_b_width}:{out_height}:{out_width}-{part_b_width}:0,"
                    f"{t_scale_right}[vb];"
                    f"[vc][vb]hstack=inputs=2[outv]"
                )
            else:
                # 模板B在左，列表C在右
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_b_width}:{out_height}:{out_width}-{part_b_width}:0,"
                    f"{t_scale_left}[vb];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_c_width}:{target_height}:0:0,"
                    f"{l_scale_right}[vc];"
                    f"[vb][vc]hstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_B_D:
            if swap_order:
                # 列表D在左，模板B在右
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_d_width}:{target_height}:{target_width}-{part_d_width}:0,"
                    f"{l_scale_left}[vd];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_b_width}:{out_height}:{out_width}-{part_b_width}:0,"
                    f"{t_scale_right}[vb];"
                    f"[vd][vb]hstack=inputs=2[outv]"
                )
            else:
                # 模板B在左，列表D在右
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_b_width}:{out_height}:{out_width}-{part_b_width}:0,"
                    f"{t_scale_left}[vb];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_d_width}:{target_height}:{target_width}-{part_d_width}:0,"
                    f"{l_scale_right}[vd];"
                    f"[vb][vd]hstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_GRID:
            half_width = out_width // 2
            half_height = out_height // 2
            return (
                f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                f"crop={part_a_width}:{out_height}:0:0,scale={half_width}:{half_height}[va];"
                f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                f"crop={part_b_width}:{out_height}:{out_width}-{part_b_width}:0,scale={half_width}:{half_height}[vb];"
                f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                f"crop={part_c_width}:{target_height}:0:0,scale={half_width}:{half_height}[vc];"
                f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                f"crop={part_d_width}:{target_height}:{target_width}-{part_d_width}:0,scale={half_width}:{half_height}[vd];"
                f"[va][vb]hstack=inputs=2[top];"
                f"[vc][vd]hstack=inputs=2[bottom];"
                f"[top][bottom]vstack=inputs=2[outv]"
            )
        else:
            raise ValueError(f"未知的拼接方式: {merge_mode}")

    def _build_vertical_filter(
        self, merge_mode: str, swap_order: bool,
        out_width: int, out_height: int,
        part_a_height: int, part_b_height: int,
        target_width: int, target_height: int,
        part_c_height: int, part_d_height: int,
        template_scale_mode: str = "fit",
        list_scale_mode: str = "fit"
    ) -> str:
        """构建垂直分割滤镜"""
        # 根据缩放模式生成最终缩放滤镜
        t_scale_top = _build_scale_filter(out_width, part_a_height, template_scale_mode)
        t_scale_bottom = _build_scale_filter(out_width, part_b_height, template_scale_mode)
        l_scale_top = _build_scale_filter(out_width, part_a_height, list_scale_mode)
        l_scale_bottom = _build_scale_filter(out_width, part_b_height, list_scale_mode)

        if merge_mode == self.MERGE_A_C:
            if swap_order:
                # 列表C在上，模板A在下
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_c_height}:0:0,"
                    f"{l_scale_top}[vc];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_a_height}:0:0,"
                    f"{t_scale_bottom}[va];"
                    f"[vc][va]vstack=inputs=2[outv]"
                )
            else:
                # 模板A在上，列表C在下
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_a_height}:0:0,"
                    f"{t_scale_top}[va];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_c_height}:0:0,"
                    f"{l_scale_bottom}[vc];"
                    f"[va][vc]vstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_A_D:
            if swap_order:
                # 列表D在上，模板A在下
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_d_height}:0:{target_height}-{part_d_height},"
                    f"{l_scale_top}[vd];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_a_height}:0:0,"
                    f"{t_scale_bottom}[va];"
                    f"[vd][va]vstack=inputs=2[outv]"
                )
            else:
                # 模板A在上，列表D在下
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_a_height}:0:0,"
                    f"{t_scale_top}[va];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_d_height}:0:{target_height}-{part_d_height},"
                    f"{l_scale_bottom}[vd];"
                    f"[va][vd]vstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_B_C:
            if swap_order:
                # 列表C在上，模板B在下
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_c_height}:0:0,"
                    f"{l_scale_top}[vc];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_b_height}:0:{out_height}-{part_b_height},"
                    f"{t_scale_bottom}[vb];"
                    f"[vc][vb]vstack=inputs=2[outv]"
                )
            else:
                # 模板B在上，列表C在下
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_b_height}:0:{out_height}-{part_b_height},"
                    f"{t_scale_top}[vb];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_c_height}:0:0,"
                    f"{l_scale_bottom}[vc];"
                    f"[vb][vc]vstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_B_D:
            if swap_order:
                # 列表D在上，模板B在下
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_d_height}:0:{target_height}-{part_d_height},"
                    f"{l_scale_top}[vd];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_b_height}:0:{out_height}-{part_b_height},"
                    f"{t_scale_bottom}[vb];"
                    f"[vd][vb]vstack=inputs=2[outv]"
                )
            else:
                # 模板B在上，列表D在下
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_b_height}:0:{out_height}-{part_b_height},"
                    f"{t_scale_top}[vb];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_d_height}:0:{target_height}-{part_d_height},"
                    f"{l_scale_bottom}[vd];"
                    f"[vb][vd]vstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_GRID:
            half_width = out_width // 2
            half_height = out_height // 2
            return (
                f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                f"crop={out_width}:{part_a_height}:0:0,scale={half_width}:{half_height}[va];"
                f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                f"crop={out_width}:{part_b_height}:0:{out_height}-{part_b_height},scale={half_width}:{half_height}[vb];"
                f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                f"crop={target_width}:{part_c_height}:0:0,scale={half_width}:{half_height}[vc];"
                f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                f"crop={target_width}:{part_d_height}:0:{target_height}-{part_d_height},scale={half_width}:{half_height}[vd];"
                f"[va][vb]hstack=inputs=2[top];"
                f"[vc][vd]hstack=inputs=2[bottom];"
                f"[top][bottom]vstack=inputs=2[outv]"
            )
        else:
            raise ValueError(f"未知的拼接方式: {merge_mode}")
