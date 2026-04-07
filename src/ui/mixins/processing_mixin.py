"""
视频处理功能 Mixin
处理视频的批量处理、进度跟踪、结果显示等
"""
import os
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from ...utils.logger import logger
from ...core.error_handler import InputValidator
from ...core.ffmpeg_utils import FFmpegHelper


def get_video_info(video_path):
    """获取视频信息的辅助函数"""
    info = FFmpegHelper.get_video_info(video_path)
    if info:
        return info.to_dict()
    return None


class ProcessingMixin:
    """视频处理功能混入类

    需要主类提供以下属性：
    - is_processing: bool
    - processing_stopped: bool
    - template_video: tk.StringVar
    - video_items: list
    - output_dir: tk.StringVar
    - start_btn, stop_btn: ttk.Button
    - progress: ttk.Progressbar
    - status_var: tk.StringVar
    - processor: VideoProcessor
    - root: tk.Tk
    - 各种设置变量 (audio_source, split_mode, split_ratio, etc.)

    需要主类提供以下方法：
    - _get_merge_combinations(): 获取拼接组合
    - _apply_global_cover_settings(): 应用全局封面设置
    - _generate_output_filename(): 生成输出文件名
    - _generate_divider_mask(): 生成分界线蒙版
    """

    def _start_processing(self):
        """开始处理"""
        if self.is_processing:
            messagebox.showinfo("提示", "正在处理中，请等待完成")
            return

        template_path = self.template_video.get()
        if not template_path:
            messagebox.showwarning("警告", "请选择模板视频")
            return

        is_valid, error_msg = InputValidator.validate_video_file(template_path)
        if not is_valid:
            messagebox.showerror("模板视频错误", f"模板视频无效:\n{error_msg}")
            return

        if not self.video_items:
            messagebox.showwarning("警告", "请添加要处理的视频")
            return

        for i, video_item in enumerate(self.video_items, 1):
            is_valid, error_msg = InputValidator.validate_video_file(video_item.path)
            if not is_valid:
                messagebox.showerror(
                    "列表视频错误",
                    f"第{i}个视频 '{video_item.name}' 无效:\n{error_msg}"
                )
                return

        output_path = self.output_dir.get()
        if not output_path:
            messagebox.showwarning("警告", "请选择输出目录")
            return

        is_valid, error_msg = InputValidator.validate_output_directory(output_path)
        if not is_valid:
            messagebox.showerror("输出目录错误", f"输出目录无效:\n{error_msg}")
            return

        combinations = self._get_merge_combinations()
        if not combinations:
            messagebox.showwarning("警告", "请至少勾选模板和列表各一个部分")
            return

        # 将全局封面设置应用到各视频项
        self._apply_global_cover_settings()

        self.is_processing = True
        self.processing_stopped = False
        self.start_btn.config(state='disabled', text="处理中...")
        self.stop_btn.config(state='normal')
        self.progress.configure(value=0)

        thread = threading.Thread(target=self._process_videos, args=(combinations,))
        thread.daemon = False
        thread.start()
        logger.info(f"启动处理线程，共 {len(self.video_items)} 个视频，{len(combinations)} 种组合")

    def _process_videos(self, merge_combinations):
        """处理视频（后台线程）"""
        total_tasks = len(self.video_items) * len(merge_combinations)
        success_count = 0
        results = []
        task_index = 0

        for i, video_item in enumerate(self.video_items):
            for merge_mode in merge_combinations:
                # 检查是否被停止
                if self.processing_stopped:
                    self.root.after(0, lambda: self.status_var.set("处理已停止"))
                    self.root.after(0, lambda: self._on_processing_complete(results, success_count, total_tasks, stopped=True))
                    return

                task_index += 1
                task_desc = f"{video_item.name} ({merge_mode.upper()})"
                self.root.after(0, lambda v=task_desc: self.status_var.set(f"正在处理: {v}"))
                self.root.after(
                    0, lambda p=(task_index / total_tasks) * 100: self.progress.configure(value=p)
                )

                base_name = os.path.splitext(video_item.name)[0]
                if len(merge_combinations) > 1:
                    output_filename = self._generate_output_filename(
                        f"{base_name}_{merge_mode}", task_index
                    )
                else:
                    output_filename = self._generate_output_filename(base_name, i + 1)
                output_path = os.path.join(self.output_dir.get(), output_filename)

                def progress_callback(progress, message):
                    overall = ((task_index - 1 + progress) / total_tasks) * 100
                    self.root.after(0, lambda p=overall: self.progress.configure(value=p))
                    self.root.after(0, lambda m=message: self.status_var.set(m))

                self.processor.set_progress_callback(progress_callback)

                audio_source = self.audio_source.get()
                custom_audio = self.custom_audio_path.get() if audio_source == "custom" else None

                size_mode = self.output_size_mode.get()
                if size_mode == "custom":
                    out_width = self.output_width.get()
                    out_height = self.output_height.get()
                    scale_mode = self.scale_mode.get()
                elif size_mode == "list":
                    video_info = get_video_info(video_item.path)
                    if video_info and video_info.get('width', 0) > 0 and video_info.get('height', 0) > 0:
                        out_width = video_info.get('width')
                        out_height = video_info.get('height')
                        logger.debug(f"跟随列表视频尺寸: {video_item.name} -> {out_width}x{out_height}")
                    else:
                        out_width = None
                        out_height = None
                        logger.warning(f"无法获取列表视频尺寸: {video_item.name}，将使用模板尺寸")
                    scale_mode = "fit"
                else:
                    out_width = None
                    out_height = None
                    scale_mode = None

                # 确定输出比例
                if self.output_ratio_enabled.get():
                    current_output_ratio = self.output_ratio.get()
                else:
                    current_output_ratio = None  # None表示跟随分割比例

                # 确定输出时长
                duration_mode = self.output_duration_mode.get()

                # 确定分界线参数
                divider_mask = None
                if self.divider_enabled.get():
                    # 检查视频是否有独立的曲线设置
                    if video_item.curve_points:
                        # 使用视频的独立曲线设置生成蒙版
                        divider_mask = self._generate_divider_mask(
                            curve_points=video_item.curve_points,
                            suffix=f"_{i}"
                        )
                    elif self.divider_curve_points:
                        # 使用全局曲线设置
                        if not self._divider_mask_path:
                            self._generate_divider_mask()
                        divider_mask = self._divider_mask_path

                result = self.processor.process_videos(
                    template_video=self.template_video.get(),
                    target_video=video_item.path,
                    output_path=output_path,
                    split_mode=self.split_mode.get(),
                    merge_mode=merge_mode,
                    split_ratio=self.split_ratio.get(),
                    target_split_ratio=video_item.split_ratio,
                    target_scale_percent=video_item.scale_percent,
                    cover_type=video_item.cover_type,
                    cover_frame_time=video_item.cover_frame_time,
                    cover_image_path=video_item.cover_image_path,
                    cover_duration=video_item.cover_duration,
                    cover_frame_source=video_item.cover_frame_source,
                    position_order=self.position_order.get(),
                    audio_source=audio_source,
                    custom_audio_path=custom_audio,
                    output_width=out_width,
                    output_height=out_height,
                    scale_mode=scale_mode,
                    output_ratio=current_output_ratio,
                    duration_mode=duration_mode,
                    template_scale_mode=self.template_scale_mode.get(),
                    list_scale_mode=self.list_scale_mode.get(),
                    template_volume=self.template_volume.get(),
                    list_volume=self.list_volume.get(),
                    custom_volume=self.custom_volume.get(),
                    divider_mask_path=divider_mask,
                    divider_color=self.divider_color.get(),
                    divider_width=self.divider_width.get(),
                    process_mode=self.process_mode.get()
                )

                result_name = f"{video_item.name} ({merge_mode.upper()})"
                results.append({'name': result_name, 'success': result.success, 'error': result.error})
                if result.success:
                    success_count += 1

        self.root.after(0, lambda: self.progress.configure(value=100))
        self.root.after(0, lambda: self.status_var.set(f"处理完成: 成功 {success_count}/{total_tasks}"))
        self.root.after(0, lambda: self._on_processing_complete(results, success_count, total_tasks))

    def _stop_processing(self):
        """停止处理"""
        if self.is_processing and not self.processing_stopped:
            self.processing_stopped = True
            self.stop_btn.config(state='disabled')
            self.status_var.set("正在停止...")
            logger.info("用户请求停止处理")

    def _notify_complete(self, success_count, total_tasks):
        try:
            if os.name == 'nt':
                import ctypes
                import winsound
                FLASHW_ALL = 3
                FLASHW_TIMERNOFG = 12
                class FLASHWINFO(ctypes.Structure):
                    _fields_ = [
                        ('cbSize', ctypes.c_uint),
                        ('hwnd', ctypes.c_void_p),
                        ('dwFlags', ctypes.c_uint),
                        ('uCount', ctypes.c_uint),
                        ('dwTimeout', ctypes.c_uint),
                    ]
                hwnd = int(self.root.winfo_id())
                fi = FLASHWINFO()
                fi.cbSize = ctypes.sizeof(fi)
                fi.hwnd = hwnd
                fi.dwFlags = FLASHW_ALL | FLASHW_TIMERNOFG
                fi.uCount = 5
                fi.dwTimeout = 0
                ctypes.windll.user32.FlashWindowEx(ctypes.byref(fi))
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            else:
                self.root.bell()
        except Exception:
            try:
                self.root.bell()
            except Exception:
                pass

    def _on_processing_complete(self, results, success_count, total_tasks, stopped=False):
        """处理完成后的回调"""
        self.is_processing = False
        self.processing_stopped = False
        self.start_btn.config(state='normal', text="开始处理")
        self.stop_btn.config(state='disabled')
        self._notify_complete(success_count, total_tasks)
        if stopped:
            messagebox.showinfo("处理已停止", f"已完成 {success_count}/{total_tasks} 个任务")
        else:
            self._show_results(results, success_count, total_tasks)

    def _show_results(self, results: list, success_count: int, total: int):
        """显示处理结果"""
        result_window = tk.Toplevel(self.root)
        result_window.title("处理结果")
        result_window.geometry("500x400")
        result_window.transient(self.root)

        title_text = f"处理完成: 成功 {success_count}/{total}"
        color = 'green' if success_count == total else 'orange'
        ttk.Label(
            result_window, text=title_text, font=('Arial', 12, 'bold'), foreground=color
        ).pack(pady=10)

        frame = ttk.Frame(result_window)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text = tk.Text(frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, font=('Consolas', 10))
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)

        text.tag_configure('success', foreground='green')
        text.tag_configure('error', foreground='red')
        text.tag_configure('filename', foreground='blue', font=('Consolas', 10, 'bold'))

        for i, result in enumerate(results):
            text.insert(tk.END, f"{i + 1}. {result['name']}\n", 'filename')
            if result['success']:
                text.insert(tk.END, "   状态: 成功\n\n", 'success')
            else:
                text.insert(tk.END, f"   状态: 失败\n   原因: {result['error']}\n\n", 'error')

        text.config(state=tk.DISABLED)

        btn_frame = ttk.Frame(result_window)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="打开输出目录", command=self._open_output_dir).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=result_window.destroy).pack(side=tk.LEFT, padx=5)

        self._open_output_dir()

    def _open_output_dir(self):
        """打开输出目录"""
        output_dir = self.output_dir.get()
        if output_dir and os.path.exists(output_dir):
            if os.name == 'nt':
                os.startfile(output_dir)
            else:
                subprocess.run(['xdg-open', output_dir])
