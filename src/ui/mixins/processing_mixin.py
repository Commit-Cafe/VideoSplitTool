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

    def _validate_processing_inputs(self):
        """
        验证处理前的所有输入

        Returns:
            (ok, title, message):
              - ok: True 表示可以开始处理
              - title: 弹窗标题（"警告"用 showwarning，其他用 showerror）
              - message: 弹窗内容
        """
        is_image_logo = self.process_mode.get() == "image_logo"

        template_path = self.template_video.get()
        if not template_path:
            return False, "警告", "请选择模板视频"

        is_valid, error_msg = InputValidator.validate_video_file(template_path)
        if not is_valid:
            return False, "模板视频错误", f"模板视频无效:\n{error_msg}"

        # image_logo 模式：不需要列表视频（logo 叠加在模板上）
        if not is_image_logo:
            if not self.video_items:
                return False, "警告", "请添加要处理的视频"
            for i, video_item in enumerate(self.video_items, 1):
                is_valid, error_msg = InputValidator.validate_video_file(video_item.path)
                if not is_valid:
                    return False, "列表视频错误", f"第{i}个视频 '{video_item.name}' 无效:\n{error_msg}"
        else:
            if not self.logo_enabled.get():
                return False, "警告", "图片 Logo 模式需要启用 Logo"
            logo_p = self.logo_path.get()
            if not logo_p or not os.path.isfile(logo_p):
                return False, "警告", "请选择有效的 Logo 图片文件"

        output_path = self.output_dir.get()
        if not output_path:
            return False, "警告", "请选择输出目录"

        is_valid, error_msg = InputValidator.validate_output_directory(output_path)
        if not is_valid:
            return False, "输出目录错误", f"输出目录无效:\n{error_msg}"

        combinations = self._get_merge_combinations()
        if not combinations:
            return False, "警告", "请至少勾选模板和列表各一个部分"

        return True, "", ""

    def _start_processing(self):
        """开始处理"""
        if self.is_processing:
            messagebox.showinfo("提示", "正在处理中，请等待完成")
            return

        ok, title, msg = self._validate_processing_inputs()
        if not ok:
            if title in ("警告",):
                messagebox.showwarning(title, msg)
            else:
                messagebox.showerror(title, msg)
            return

        combinations = self._get_merge_combinations()

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
        is_image_logo = self.process_mode.get() == "image_logo"
        video_count = 1 if is_image_logo else len(self.video_items)
        logger.info(f"启动处理线程，共 {video_count} 个视频，{len(combinations)} 种组合")

    def _process_videos(self, merge_combinations):
        """处理视频（后台线程）"""
        is_image_logo = self.process_mode.get() == "image_logo"

        # 构建任务列表：
        # - image_logo 模式：以模板视频作为唯一"目标"，循环 1 次
        # - 其他模式：遍历 self.video_items 中的每个列表视频
        if is_image_logo:
            from types import SimpleNamespace
            template_path = self.template_video.get()
            tasks = [SimpleNamespace(
                path=template_path,
                name=os.path.basename(template_path),
                split_ratio=self.split_ratio.get(),
                scale_percent=None,
                cover_type=self.global_cover_type.get(),
                cover_frame_time=self.global_cover_frame_time.get(),
                cover_image_path=None,
                cover_duration=0.0,
                cover_frame_source='list',
                curve_points=None,
            )]
        else:
            tasks = self.video_items

        total_tasks = len(tasks) * len(merge_combinations)
        success_count = 0
        results = []
        task_index = 0

        for i, video_item in enumerate(tasks):
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
                    process_mode=self.process_mode.get(),
                    # ========== 图片 logo 参数 ==========
                    logo_enabled=self.logo_enabled.get() and self.process_mode.get() == "image_logo",
                    logo_path=self.logo_path.get() if self.logo_enabled.get() else None,
                    logo_size_percent=self.logo_size_percent.get(),
                    logo_x_percent=self.logo_x_percent.get(),
                    logo_y_percent=self.logo_y_percent.get(),
                    logo_angle=self.logo_angle.get(),
                    logo_opacity=float(self.logo_opacity.get()) / 100.0
                )

                result_name = f"{video_item.name} ({merge_mode.upper()})"
                results.append({
                    'name': result_name,
                    'success': result.success,
                    'error': result.error,
                    'output_path': output_path,  # 完整输出路径（用于在成功窗口显示）
                })
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
        result_window.geometry("640x460")
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
        text.tag_configure('filepath', foreground='#0066cc')

        for i, result in enumerate(results):
            text.insert(tk.END, f"{i + 1}. {result['name']}\n", 'filename')
            if result['success']:
                text.insert(tk.END, "   状态: 成功\n", 'success')
                output_path = result.get('output_path', '')
                if output_path:
                    text.insert(tk.END, f"   输出: {output_path}\n", 'filepath')
                text.insert(tk.END, "\n")
            else:
                text.insert(tk.END, f"   状态: 失败\n   原因: {result['error']}\n\n", 'error')

        text.config(state=tk.DISABLED)

        btn_frame = ttk.Frame(result_window)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="打开输出目录", command=self._open_output_dir).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="复制首个成功文件路径", command=lambda: self._copy_first_success_path(results)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=result_window.destroy).pack(side=tk.LEFT, padx=5)

        # 如果有成功的任务，自动打开输出目录
        if any(r['success'] for r in results):
            self._open_output_dir()

    def _copy_first_success_path(self, results: list):
        """复制首个成功任务的输出路径到剪贴板"""
        from tkinter import messagebox
        for r in results:
            if r['success'] and r.get('output_path'):
                path = r['output_path']
                try:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(path)
                    messagebox.showinfo("已复制", f"路径已复制到剪贴板：\n{path}")
                except Exception as e:
                    messagebox.showerror("复制失败", str(e))
                return
        messagebox.showinfo("提示", "没有成功的任务可复制")

    def _test_output_dir(self):
        """测试输出目录是否可写入（UI 工具按钮）"""
        from tkinter import messagebox

        output_dir = self.output_dir.get()
        if not output_dir:
            messagebox.showwarning("提示", "请先选择输出目录")
            return

        # 调用 VideoProcessor 的详细诊断方法
        ok, msg = self.processor._check_output_writability(output_dir)
        if ok:
            messagebox.showinfo(
                "输出目录可写",
                f"目录 {output_dir} 可正常写入。\n\n可以开始处理。"
            )
        else:
            # 提供两种选择：手动修复 / 用临时目录
            full_msg = (
                f"{msg}\n\n"
                f"建议：\n"
                f"  • 点击旁边的『用临时目录』按钮，一键切换到系统临时目录\n"
                f"  • 或手动修改输出目录（右键该目录 → 属性 → 安全 → 赋予写权限）"
            )
            messagebox.showerror("输出目录不可写", full_msg)

    def _use_temp_output_dir(self):
        """将输出目录设置为系统临时目录（被锁目录的临时解决方案）"""
        from tkinter import messagebox
        import tempfile

        temp_dir = tempfile.gettempdir()
        self.output_dir.set(temp_dir)
        messagebox.showinfo(
            "已切换到临时目录",
            f"输出目录已设置为系统临时目录：\n{temp_dir}\n\n"
            f"提示：处理完成后请手动将文件复制到您想要的目录。"
        )

    def _open_output_dir(self):
        """在 Windows 资源管理器中打开输出目录（让用户看到生成的所有文件）"""
        from tkinter import messagebox
        import subprocess
        import os

        output_dir = self.output_dir.get()
        if not output_dir:
            messagebox.showwarning("提示", "请先选择输出目录")
            return

        if not os.path.isdir(output_dir):
            messagebox.showwarning(
                "目录不存在",
                f"输出目录 {output_dir} 不存在。\n请先点击「测试」检查，或用「用临时目录」切换。"
            )
            return

        try:
            # Windows 上用 explorer 打开
            subprocess.Popen(f'explorer "{output_dir}"')
        except Exception as e:
            messagebox.showerror("打开失败", f"无法打开目录: {e}")
