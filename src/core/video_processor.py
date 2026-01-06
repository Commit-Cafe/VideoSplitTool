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
        scale_mode: str = None
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
            scale_mode: 缩放模式 (fit/fill/stretch)

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
            if output_width and output_height:
                out_width = output_width
                out_height = output_height
                logger.info(f"使用自定义输出尺寸: {out_width}x{out_height}")
            else:
                out_width = template_info.width
                out_height = template_info.height
                logger.info(f"使用模板视频尺寸: {out_width}x{out_height}")

            # 确定较长的时长
            max_duration = max(template_info.duration, target_info.duration)
            if max_duration <= 0:
                return ProcessResult(False, error="视频时长无效")

            # 检查音频状态
            template_has_audio = template_info.has_audio
            target_has_audio = target_info.has_audio

            self._report_progress(0.1, "构建处理命令")

            # 验证自定义音频文件
            if audio_source == "custom" and custom_audio_path:
                if not os.path.exists(custom_audio_path):
                    return ProcessResult(False, error=f"自定义音频文件不存在: {custom_audio_path}")

            # 构建filter_complex
            try:
                filter_complex = self._build_filter_complex(
                    split_mode, merge_mode,
                    split_ratio, target_split_ratio,
                    out_width, out_height,
                    template_info.duration, target_info.duration,
                    template_has_audio, target_has_audio,
                    target_scale_percent,
                    position_order,
                    audio_source,
                    scale_mode or "fit"
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

            if audio_source == "custom" and custom_audio_path:
                cmd.extend(['-stream_loop', '-1', '-i', custom_audio_path])

            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '[outv]',
            ])

            # 音频映射
            has_audio_output = False
            if audio_source == "none":
                pass
            elif audio_source == "custom" and custom_audio_path:
                cmd.extend(['-map', '2:a'])
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

            if main_has_audio:
                cmd = [
                    ffmpeg, '-y',
                    '-i', cover_video_path,
                    '-i', video_path,
                    '-filter_complex',
                    f'[0:v]scale={width}:{height}:force_original_aspect_ratio=disable,setsar=1[v0];'
                    f'[1:v]scale={width}:{height}:force_original_aspect_ratio=disable,setsar=1[v1];'
                    f'[v0][v1]concat=n=2:v=1:a=0[outv];'
                    f'anullsrc=channel_layout=stereo:sample_rate=44100:duration={cover_duration}[a0];'
                    f'[a0][1:a]concat=n=2:v=0:a=1[outa]',
                    '-map', '[outv]',
                    '-map', '[outa]',
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-shortest',
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
        scale_mode: str = "fit"
    ) -> str:
        """构建FFmpeg filter_complex字符串"""
        logger.debug(f"缩放模式: {scale_mode}")

        # 音频filter
        audio_filter = None
        if audio_source == "mix":
            if template_has_audio and target_has_audio:
                audio_filter = "[0:a][1:a]amix=inputs=2:duration=longest[outa]"
            elif template_has_audio:
                audio_filter = "[0:a]acopy[outa]"
            elif target_has_audio:
                audio_filter = "[1:a]acopy[outa]"
        elif audio_source == "template":
            if template_has_audio:
                audio_filter = "[0:a]acopy[outa]"
        elif audio_source == "list":
            if target_has_audio:
                audio_filter = "[1:a]acopy[outa]"

        swap_order = (position_order == "list_first")
        scale_factor = target_scale_percent / 100.0
        target_scaled_width = int(out_width * scale_factor)
        target_scaled_height = int(out_height * scale_factor)

        if split_mode == self.SPLIT_HORIZONTAL:
            template_part_a_width = int(out_width * split_ratio)
            template_part_b_width = out_width - template_part_a_width
            target_part_c_width = int(target_scaled_width * target_split_ratio)
            target_part_d_width = target_scaled_width - target_part_c_width

            video_filter = self._build_horizontal_filter(
                merge_mode, swap_order,
                out_width, out_height,
                template_part_a_width, template_part_b_width,
                target_scaled_width, target_scaled_height,
                target_part_c_width, target_part_d_width
            )
        else:
            template_part_a_height = int(out_height * split_ratio)
            template_part_b_height = out_height - template_part_a_height
            target_part_c_height = int(target_scaled_height * target_split_ratio)
            target_part_d_height = target_scaled_height - target_part_c_height

            video_filter = self._build_vertical_filter(
                merge_mode, swap_order,
                out_width, out_height,
                template_part_a_height, template_part_b_height,
                target_scaled_width, target_scaled_height,
                target_part_c_height, target_part_d_height
            )

        if audio_filter:
            return f"{video_filter};{audio_filter}"
        return video_filter

    def _build_horizontal_filter(
        self, merge_mode: str, swap_order: bool,
        out_width: int, out_height: int,
        part_a_width: int, part_b_width: int,
        target_width: int, target_height: int,
        part_c_width: int, part_d_width: int
    ) -> str:
        """构建水平分割滤镜"""
        if merge_mode == self.MERGE_A_C:
            if swap_order:
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_c_width}:{target_height}:0:0,"
                    f"scale={part_a_width}:{out_height}:force_original_aspect_ratio=disable[vc];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_b_width}:{out_height}:{out_width}-{part_b_width}:0[va];"
                    f"[vc][va]hstack=inputs=2[outv]"
                )
            else:
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_a_width}:{out_height}:0:0[va];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_c_width}:{target_height}:0:0,"
                    f"scale={part_b_width}:{out_height}:force_original_aspect_ratio=disable[vc];"
                    f"[va][vc]hstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_A_D:
            if swap_order:
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_d_width}:{target_height}:{target_width}-{part_d_width}:0,"
                    f"scale={part_a_width}:{out_height}:force_original_aspect_ratio=disable[vd];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_b_width}:{out_height}:{out_width}-{part_b_width}:0[va];"
                    f"[vd][va]hstack=inputs=2[outv]"
                )
            else:
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_a_width}:{out_height}:0:0[va];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_d_width}:{target_height}:{target_width}-{part_d_width}:0,"
                    f"scale={part_b_width}:{out_height}:force_original_aspect_ratio=disable[vd];"
                    f"[va][vd]hstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_B_C:
            if swap_order:
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_c_width}:{target_height}:0:0,"
                    f"scale={part_b_width}:{out_height}:force_original_aspect_ratio=disable[vc];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_a_width}:{out_height}:0:0[vb];"
                    f"[vc][vb]hstack=inputs=2[outv]"
                )
            else:
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_b_width}:{out_height}:{out_width}-{part_b_width}:0[vb];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_c_width}:{target_height}:0:0,"
                    f"scale={part_a_width}:{out_height}:force_original_aspect_ratio=disable[vc];"
                    f"[vb][vc]hstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_B_D:
            if swap_order:
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_d_width}:{target_height}:{target_width}-{part_d_width}:0,"
                    f"scale={part_b_width}:{out_height}:force_original_aspect_ratio=disable[vd];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_a_width}:{out_height}:0:0[vb];"
                    f"[vd][vb]hstack=inputs=2[outv]"
                )
            else:
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_b_width}:{out_height}:{out_width}-{part_b_width}:0[vb];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={part_d_width}:{target_height}:{target_width}-{part_d_width}:0,"
                    f"scale={part_a_width}:{out_height}:force_original_aspect_ratio=disable[vd];"
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
        part_c_height: int, part_d_height: int
    ) -> str:
        """构建垂直分割滤镜"""
        if merge_mode == self.MERGE_A_C:
            if swap_order:
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_c_height}:0:0,"
                    f"scale={out_width}:{part_a_height}:force_original_aspect_ratio=disable[vc];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_b_height}:0:{out_height}-{part_b_height}[va];"
                    f"[vc][va]vstack=inputs=2[outv]"
                )
            else:
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_a_height}:0:0[va];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_c_height}:0:0,"
                    f"scale={out_width}:{part_b_height}:force_original_aspect_ratio=disable[vc];"
                    f"[va][vc]vstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_A_D:
            if swap_order:
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_d_height}:0:{target_height}-{part_d_height},"
                    f"scale={out_width}:{part_a_height}:force_original_aspect_ratio=disable[vd];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_b_height}:0:{out_height}-{part_b_height}[va];"
                    f"[vd][va]vstack=inputs=2[outv]"
                )
            else:
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_a_height}:0:0[va];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_d_height}:0:{target_height}-{part_d_height},"
                    f"scale={out_width}:{part_b_height}:force_original_aspect_ratio=disable[vd];"
                    f"[va][vd]vstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_B_C:
            if swap_order:
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_c_height}:0:0,"
                    f"scale={out_width}:{part_b_height}:force_original_aspect_ratio=disable[vc];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_a_height}:0:0[vb];"
                    f"[vc][vb]vstack=inputs=2[outv]"
                )
            else:
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_b_height}:0:{out_height}-{part_b_height}[vb];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_c_height}:0:0,"
                    f"scale={out_width}:{part_a_height}:force_original_aspect_ratio=disable[vc];"
                    f"[vb][vc]vstack=inputs=2[outv]"
                )
        elif merge_mode == self.MERGE_B_D:
            if swap_order:
                return (
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_d_height}:0:{target_height}-{part_d_height},"
                    f"scale={out_width}:{part_b_height}:force_original_aspect_ratio=disable[vd];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_a_height}:0:0[vb];"
                    f"[vd][vb]vstack=inputs=2[outv]"
                )
            else:
                return (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                    f"crop={out_width}:{part_b_height}:0:{out_height}-{part_b_height}[vb];"
                    f"[1:v]scale={target_width}:{target_height}:force_original_aspect_ratio=disable,"
                    f"crop={target_width}:{part_d_height}:0:{target_height}-{part_d_height},"
                    f"scale={out_width}:{part_a_height}:force_original_aspect_ratio=disable[vd];"
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
