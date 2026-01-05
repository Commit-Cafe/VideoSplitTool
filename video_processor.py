"""
视频处理核心模块
使用FFmpeg进行视频分割和拼接
"""
import subprocess
import os
import uuid
from typing import Callable, Optional
from utils import (get_video_info, get_temp_dir, get_ffmpeg_path,
                   extract_frame, image_to_video)
from error_handler import ErrorDiagnostics, format_error_message
from logger import logger


class ProcessResult:
    """处理结果"""
    def __init__(self, success: bool, message: str = "", error: str = ""):
        self.success = success
        self.message = message
        self.error = error


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

    def _run_ffmpeg(self, cmd: list, description: str = "", context: dict = None) -> tuple[bool, str]:
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

    def _parse_ffmpeg_error(self, stderr: str) -> str:
        """解析FFmpeg错误信息，提取关键错误"""
        if not stderr:
            return "未知错误"

        stderr_lower = stderr.lower()

        # 常见错误模式（按优先级排序）
        error_patterns = [
            # 音频相关
            ("does not contain any stream", "视频不包含音频轨道"),
            ("Stream map '.*:a' matches no streams", "视频没有音频轨道"),
            ("amix", "音频混合失败(可能某个视频没有音频)"),
            ("Audio encoding failed", "音频编码失败"),
            # 视频相关
            ("Invalid data found", "视频文件损坏或格式不支持"),
            ("Video encoding failed", "视频编码失败"),
            ("Error while decoding", "视频解码错误"),
            ("Could not find codec", "找不到解码器"),
            # 文件相关
            ("No such file or directory", "文件不存在"),
            ("Permission denied", "文件权限不足，可能被占用"),
            ("Error opening input", "无法打开输入文件"),
            ("Output file is empty", "输出文件为空"),
            # 格式相关
            ("moov atom not found", "视频文件不完整(moov原子缺失)"),
            ("Avi header at the end", "视频文件头损坏"),
            ("Avi non-interleaved", "AVI文件格式问题"),
            ("Avi timecode chunk", "AVI时间码错误"),
            # 其他
            ("Invalid argument", "FFmpeg参数错误"),
            ("matches no streams", "没有匹配的流(可能缺少音频/视频轨道)"),
        ]

        for pattern, message in error_patterns:
            if pattern.lower() in stderr_lower:
                return message

        # 提取最后一行有意义的错误
        lines = stderr.strip().split('\n')
        for line in reversed(lines):
            line = line.strip()
            if line and not line.startswith('frame=') and not line.startswith('size='):
                if 'error' in line.lower() or 'invalid' in line.lower() or 'failed' in line.lower():
                    # 截取关键部分
                    if len(line) > 120:
                        line = line[:120] + "..."
                    return f"FFmpeg错误: {line}"

        return "FFmpeg处理失败，请检查视频文件格式"

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
            target_split_ratio: 目标视频分割比例 (0.1-0.9)，None则使用模板比例
            target_scale_percent: 目标视频缩放百分比 (50-200)
            cover_type: 封面类型 (none/frame/image)
            cover_frame_time: 封面帧时间点（秒）
            cover_image_path: 封面图片路径
            cover_duration: 封面显示时长（秒）
            cover_frame_source: 封面帧来源 (template/list)
            position_order: 位置顺序 (template_first/list_first)
            audio_source: 音频来源 (template/list/mix/custom/none)
            custom_audio_path: 自定义音频文件路径
            output_width: 自定义输出宽度，None则使用模板视频宽度
            output_height: 自定义输出高度，None则使用模板视频高度
            scale_mode: 缩放模式 (fit/fill/stretch)，None则默认fit

        Returns:
            ProcessResult: 处理结果
        """
        temp_files = []  # 用于跟踪临时文件

        try:
            self._report_progress(0.05, "获取视频信息")

            # 如果未指定目标视频分割比例，使用模板比例
            if target_split_ratio is None:
                target_split_ratio = split_ratio

            # 检查文件是否存在
            if not os.path.exists(template_video):
                return ProcessResult(False, error=f"模板视频不存在: {template_video}")
            if not os.path.exists(target_video):
                return ProcessResult(False, error=f"目标视频不存在: {target_video}")

            # 获取视频信息
            template_info = get_video_info(template_video)
            target_info = get_video_info(target_video)

            if not template_info:
                return ProcessResult(False, error="无法获取模板视频信息，文件可能损坏")
            if not target_info:
                return ProcessResult(False, error="无法获取目标视频信息，文件可能损坏")

            # 检查视频尺寸
            if template_info['width'] == 0 or template_info['height'] == 0:
                return ProcessResult(False, error="模板视频尺寸无效")
            if target_info['width'] == 0 or target_info['height'] == 0:
                return ProcessResult(False, error="目标视频尺寸无效")

            # 确定输出尺寸
            if output_width and output_height:
                # 使用自定义尺寸
                out_width = output_width
                out_height = output_height
                logger.info(f"使用自定义输出尺寸: {out_width}x{out_height}")
            else:
                # 使用模板视频的尺寸
                out_width = template_info['width']
                out_height = template_info['height']
                logger.info(f"使用模板视频尺寸: {out_width}x{out_height}")

            # 确定较长的时长
            max_duration = max(template_info['duration'], target_info['duration'])
            if max_duration <= 0:
                return ProcessResult(False, error="视频时长无效")

            # 检查音频状态
            template_has_audio = template_info.get('has_audio', False)
            target_has_audio = target_info.get('has_audio', False)

            self._report_progress(0.1, "构建处理命令")

            # 验证自定义音频文件
            if audio_source == "custom" and custom_audio_path:
                if not os.path.exists(custom_audio_path):
                    return ProcessResult(False, error=f"自定义音频文件不存在: {custom_audio_path}")

            # 根据拼接模式构建filter_complex
            try:
                filter_complex = self._build_filter_complex(
                    split_mode, merge_mode,
                    split_ratio, target_split_ratio,
                    out_width, out_height,
                    template_info['duration'], target_info['duration'],
                    template_has_audio, target_has_audio,
                    target_scale_percent,
                    position_order,
                    audio_source,
                    scale_mode or "fit"  # 默认使用fit模式
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

            # 如果使用自定义音频，添加第三个输入
            if audio_source == "custom" and custom_audio_path:
                cmd.extend(['-stream_loop', '-1', '-i', custom_audio_path])

            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '[outv]',
            ])

            # 根据音频配置决定是否添加音频映射
            has_audio_output = False
            if audio_source == "none":
                # 静音：不添加音频
                pass
            elif audio_source == "custom" and custom_audio_path:
                # 自定义音频：使用第三个输入
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
                # 根据帧来源选择视频
                if cover_frame_source == "template":
                    frame_source_video = template_video
                elif cover_frame_source == "list":
                    frame_source_video = target_video
                elif cover_frame_source == "merged":
                    # 使用拼接后的视频作为帧来源
                    frame_source_video = output_path
                else:
                    # 默认使用列表视频
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
        """
        为视频添加封面

        Args:
            video_path: 当前输出视频路径
            width: 视频宽度
            height: 视频高度
            cover_type: 封面类型 (frame/image)
            cover_frame_time: 封面帧时间点
            cover_image_path: 封面图片路径
            cover_duration: 封面时长
            source_video: 源视频（用于提取帧）
            temp_files: 临时文件列表

        Returns:
            ProcessResult: 处理结果
        """
        temp_dir = get_temp_dir()
        unique_id = str(uuid.uuid4())[:8]

        try:
            # 根据封面类型获取封面图片
            if cover_type == "frame":
                # 从源视频提取帧
                cover_frame_path = os.path.join(temp_dir, f"cover_frame_{unique_id}.jpg")
                if not extract_frame(source_video, cover_frame_path, cover_frame_time):
                    return ProcessResult(False, error="提取封面帧失败")
                temp_files.append(cover_frame_path)
                image_path = cover_frame_path
            elif cover_type == "image":
                if not cover_image_path or not os.path.exists(cover_image_path):
                    return ProcessResult(False, error="封面图片不存在")
                image_path = cover_image_path
            else:
                return ProcessResult(True)  # 无封面，直接返回成功

            # 将封面图片转换为视频
            cover_video_path = os.path.join(temp_dir, f"cover_video_{unique_id}.mp4")
            if not image_to_video(image_path, cover_video_path, cover_duration, width, height):
                return ProcessResult(False, error="封面图片转视频失败")
            temp_files.append(cover_video_path)

            # 拼接封面视频和主视频
            final_output = os.path.join(temp_dir, f"final_{unique_id}.mp4")

            ffmpeg = get_ffmpeg_path()

            # 检查主视频是否有音频
            from utils import check_has_audio
            main_has_audio = check_has_audio(video_path)

            if main_has_audio:
                # 主视频有音频：为封面添加静音，然后拼接视频和音频
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
                # 主视频没有音频：只处理视频
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
                # 用最终文件替换原输出文件
                import shutil
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
                print(f"无法删除临时文件 {temp_file}: {e}")
            except Exception as e:
                print(f"删除临时文件时发生错误 {temp_file}: {e}")

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
        """
        构建FFmpeg filter_complex字符串

        Args:
            split_mode: 分割方式
            merge_mode: 拼接方式
            split_ratio: 模板视频分割比例
            target_split_ratio: 目标视频分割比例
            out_width: 输出宽度
            out_height: 输出高度
            template_duration: 模板视频时长
            target_duration: 目标视频时长
            template_has_audio: 模板视频是否有音频
            target_has_audio: 目标视频是否有音频
            target_scale_percent: 目标视频缩放百分比
            position_order: 位置顺序 (template_first/list_first)
            audio_source: 音频来源 (template/list/mix/custom/none)
            scale_mode: 缩放模式 (fit/fill/stretch)
        """
        # 记录缩放模式（当前实现使用stretch模式，fit和fill模式需要更复杂的filter构建）
        logger.debug(f"缩放模式: {scale_mode}")
        # TODO: 完整实现fit和fill模式需要重构filter构建逻辑
        # fit: 使用force_original_aspect_ratio=decrease + pad
        # fill: 使用force_original_aspect_ratio=increase + crop
        # stretch: 使用force_original_aspect_ratio=disable (当前行为)

        # 根据audio_source构建音频部分的filter
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
        # audio_source == "custom" or "none" 时不需要audio_filter

        # 判断是否需要交换位置顺序
        swap_order = (position_order == "list_first")

        # 计算目标视频缩放后的尺寸
        scale_factor = target_scale_percent / 100.0
        target_scaled_width = int(out_width * scale_factor)
        target_scaled_height = int(out_height * scale_factor)

        if split_mode == self.SPLIT_HORIZONTAL:
            # 左右分割
            # 模板: a = 左半部分, b = 右半部分
            # 目标: c = 左半部分, d = 右半部分
            template_part_a_width = int(out_width * split_ratio)
            template_part_b_width = out_width - template_part_a_width

            # 目标视频使用独立的分割比例
            target_part_c_width = int(target_scaled_width * target_split_ratio)
            target_part_d_width = target_scaled_width - target_part_c_width

            if merge_mode == self.MERGE_A_C:
                # 模板左 + 目标左 -> 拼成左右
                # 目标视频的c部分需要缩放到 part_b_width
                if swap_order:
                    # 列表在前：C + A
                    video_filter = (
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_part_c_width}:{target_scaled_height}:0:0,"
                        f"scale={template_part_a_width}:{out_height}:force_original_aspect_ratio=disable[vc];"
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_b_width}:{out_height}:{out_width}-{template_part_b_width}:0[va];"
                        f"[vc][va]hstack=inputs=2[outv]"
                    )
                else:
                    # 模板在前：A + C
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_a_width}:{out_height}:0:0[va];"
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_part_c_width}:{target_scaled_height}:0:0,"
                        f"scale={template_part_b_width}:{out_height}:force_original_aspect_ratio=disable[vc];"
                        f"[va][vc]hstack=inputs=2[outv]"
                    )
            elif merge_mode == self.MERGE_A_D:
                # 模板左 + 目标右
                if swap_order:
                    # 列表在前：D + A
                    video_filter = (
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_part_d_width}:{target_scaled_height}:{target_scaled_width}-{target_part_d_width}:0,"
                        f"scale={template_part_a_width}:{out_height}:force_original_aspect_ratio=disable[vd];"
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_b_width}:{out_height}:{out_width}-{template_part_b_width}:0[va];"
                        f"[vd][va]hstack=inputs=2[outv]"
                    )
                else:
                    # 模板在前：A + D
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_a_width}:{out_height}:0:0[va];"
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_part_d_width}:{target_scaled_height}:{target_scaled_width}-{target_part_d_width}:0,"
                        f"scale={template_part_b_width}:{out_height}:force_original_aspect_ratio=disable[vd];"
                        f"[va][vd]hstack=inputs=2[outv]"
                    )
            elif merge_mode == self.MERGE_B_C:
                # 模板右 + 目标左
                if swap_order:
                    # 列表在前：C + B
                    video_filter = (
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_part_c_width}:{target_scaled_height}:0:0,"
                        f"scale={template_part_b_width}:{out_height}:force_original_aspect_ratio=disable[vc];"
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_a_width}:{out_height}:0:0[vb];"
                        f"[vc][vb]hstack=inputs=2[outv]"
                    )
                else:
                    # 模板在前：B + C
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_b_width}:{out_height}:{out_width}-{template_part_b_width}:0[vb];"
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_part_c_width}:{target_scaled_height}:0:0,"
                        f"scale={template_part_a_width}:{out_height}:force_original_aspect_ratio=disable[vc];"
                        f"[vb][vc]hstack=inputs=2[outv]"
                    )
            elif merge_mode == self.MERGE_B_D:
                # 模板右 + 目标右
                if swap_order:
                    # 列表在前：D + B
                    video_filter = (
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_part_d_width}:{target_scaled_height}:{target_scaled_width}-{target_part_d_width}:0,"
                        f"scale={template_part_b_width}:{out_height}:force_original_aspect_ratio=disable[vd];"
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_a_width}:{out_height}:0:0[vb];"
                        f"[vd][vb]hstack=inputs=2[outv]"
                    )
                else:
                    # 模板在前：B + D
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_b_width}:{out_height}:{out_width}-{template_part_b_width}:0[vb];"
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_part_d_width}:{target_scaled_height}:{target_scaled_width}-{target_part_d_width}:0,"
                        f"scale={template_part_a_width}:{out_height}:force_original_aspect_ratio=disable[vd];"
                        f"[vb][vd]hstack=inputs=2[outv]"
                    )
            elif merge_mode == self.MERGE_GRID:
                # 四宫格
                half_width = out_width // 2
                half_height = out_height // 2
                video_filter = (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_a_width}:{out_height}:0:0,scale={half_width}:{half_height}[va];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_b_width}:{out_height}:{out_width}-{template_part_b_width}:0,scale={half_width}:{half_height}[vb];"
                    f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,crop={target_part_c_width}:{target_scaled_height}:0:0,scale={half_width}:{half_height}[vc];"
                    f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,crop={target_part_d_width}:{target_scaled_height}:{target_scaled_width}-{target_part_d_width}:0,scale={half_width}:{half_height}[vd];"
                    f"[va][vb]hstack=inputs=2[top];"
                    f"[vc][vd]hstack=inputs=2[bottom];"
                    f"[top][bottom]vstack=inputs=2[outv]"
                )
            else:
                raise ValueError(f"未知的拼接方式: {merge_mode}")

            # 组合视频和音频filter
            if audio_filter:
                filter_str = f"{video_filter};{audio_filter}"
            else:
                filter_str = video_filter

        else:
            # 上下分割
            # 模板: a = 上半部分, b = 下半部分
            # 目标: c = 上半部分, d = 下半部分
            template_part_a_height = int(out_height * split_ratio)
            template_part_b_height = out_height - template_part_a_height

            # 目标视频使用独立的分割比例
            target_part_c_height = int(target_scaled_height * target_split_ratio)
            target_part_d_height = target_scaled_height - target_part_c_height

            if merge_mode == self.MERGE_A_C:
                # 模板上 + 目标上 -> 拼成上下
                if swap_order:
                    # 列表在前：C + A
                    video_filter = (
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_scaled_width}:{target_part_c_height}:0:0,"
                        f"scale={out_width}:{template_part_a_height}:force_original_aspect_ratio=disable[vc];"
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_b_height}:0:{out_height}-{template_part_b_height}[va];"
                        f"[vc][va]vstack=inputs=2[outv]"
                    )
                else:
                    # 模板在前：A + C
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_a_height}:0:0[va];"
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_scaled_width}:{target_part_c_height}:0:0,"
                        f"scale={out_width}:{template_part_b_height}:force_original_aspect_ratio=disable[vc];"
                        f"[va][vc]vstack=inputs=2[outv]"
                    )
            elif merge_mode == self.MERGE_A_D:
                # 模板上 + 目标下
                if swap_order:
                    # 列表在前：D + A
                    video_filter = (
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_scaled_width}:{target_part_d_height}:0:{target_scaled_height}-{target_part_d_height},"
                        f"scale={out_width}:{template_part_a_height}:force_original_aspect_ratio=disable[vd];"
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_b_height}:0:{out_height}-{template_part_b_height}[va];"
                        f"[vd][va]vstack=inputs=2[outv]"
                    )
                else:
                    # 模板在前：A + D
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_a_height}:0:0[va];"
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_scaled_width}:{target_part_d_height}:0:{target_scaled_height}-{target_part_d_height},"
                        f"scale={out_width}:{template_part_b_height}:force_original_aspect_ratio=disable[vd];"
                        f"[va][vd]vstack=inputs=2[outv]"
                    )
            elif merge_mode == self.MERGE_B_C:
                # 模板下 + 目标上
                if swap_order:
                    # 列表在前：C + B
                    video_filter = (
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_scaled_width}:{target_part_c_height}:0:0,"
                        f"scale={out_width}:{template_part_b_height}:force_original_aspect_ratio=disable[vc];"
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_a_height}:0:0[vb];"
                        f"[vc][vb]vstack=inputs=2[outv]"
                    )
                else:
                    # 模板在前：B + C
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_b_height}:0:{out_height}-{template_part_b_height}[vb];"
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_scaled_width}:{target_part_c_height}:0:0,"
                        f"scale={out_width}:{template_part_a_height}:force_original_aspect_ratio=disable[vc];"
                        f"[vb][vc]vstack=inputs=2[outv]"
                    )
            elif merge_mode == self.MERGE_B_D:
                # 模板下 + 目标下
                if swap_order:
                    # 列表在前：D + B
                    video_filter = (
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_scaled_width}:{target_part_d_height}:0:{target_scaled_height}-{target_part_d_height},"
                        f"scale={out_width}:{template_part_b_height}:force_original_aspect_ratio=disable[vd];"
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_a_height}:0:0[vb];"
                        f"[vd][vb]vstack=inputs=2[outv]"
                    )
                else:
                    # 模板在前：B + D
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_b_height}:0:{out_height}-{template_part_b_height}[vb];"
                        f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,"
                        f"crop={target_scaled_width}:{target_part_d_height}:0:{target_scaled_height}-{target_part_d_height},"
                        f"scale={out_width}:{template_part_a_height}:force_original_aspect_ratio=disable[vd];"
                        f"[vb][vd]vstack=inputs=2[outv]"
                    )
            elif merge_mode == self.MERGE_GRID:
                # 四宫格
                half_width = out_width // 2
                half_height = out_height // 2
                video_filter = (
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_a_height}:0:0,scale={half_width}:{half_height}[va];"
                    f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_b_height}:0:{out_height}-{template_part_b_height},scale={half_width}:{half_height}[vb];"
                    f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,crop={target_scaled_width}:{target_part_c_height}:0:0,scale={half_width}:{half_height}[vc];"
                    f"[1:v]scale={target_scaled_width}:{target_scaled_height}:force_original_aspect_ratio=disable,crop={target_scaled_width}:{target_part_d_height}:0:{target_scaled_height}-{target_part_d_height},scale={half_width}:{half_height}[vd];"
                    f"[va][vb]hstack=inputs=2[top];"
                    f"[vc][vd]hstack=inputs=2[bottom];"
                    f"[top][bottom]vstack=inputs=2[outv]"
                )
            else:
                raise ValueError(f"未知的拼接方式: {merge_mode}")

            # 组合视频和音频filter
            if audio_filter:
                filter_str = f"{video_filter};{audio_filter}"
            else:
                filter_str = video_filter

        return filter_str
