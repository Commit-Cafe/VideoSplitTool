"""
对话框组件
包含视频设置对话框等
"""
import tkinter as tk
from tkinter import ttk, filedialog
import os
import subprocess
from PIL import Image, ImageTk
from typing import Optional

from ..core.ffmpeg_utils import FFmpegHelper, get_ffmpeg_path
from ..utils.file_utils import get_temp_dir
from ..utils.format_utils import format_video_info
from ..utils.logger import logger
from .compat import get_video_info, extract_frame


class VideoSettingsDialog:
    """视频设置对话框"""

    def __init__(self, parent, video_item, split_mode: str, template_video: str = None, parent_app=None):
        self.result = None
        self.video_item = video_item
        self.split_mode = split_mode
        self.template_video = template_video
        self.parent_app = parent_app

        # 创建对话框
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"视频设置 - {video_item.name}")
        self.dialog.geometry("520x800")
        self.dialog.minsize(480, 750)
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 数据变量
        self.split_ratio = tk.DoubleVar(value=video_item.split_ratio)
        self.scale_percent = tk.IntVar(value=video_item.scale_percent)
        self.cover_type = tk.StringVar(value=video_item.cover_type)
        self.cover_frame_time = tk.DoubleVar(value=video_item.cover_frame_time)
        self.cover_image_path = tk.StringVar(value=video_item.cover_image_path or "")
        self.cover_duration = tk.DoubleVar(value=video_item.cover_duration)
        self.cover_frame_source = tk.StringVar(
            value=getattr(video_item, 'cover_frame_source', 'template')
        )

        # 预览相关
        self.preview_image = None
        self.preview_photo = None
        self.canvas_width = 300
        self.canvas_height = 170
        self.video_duration = 0
        self._preview_update_job = None

        self._create_widgets()
        self._load_video_preview()

        # 居中显示
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """创建对话框控件"""
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 按钮区域（先创建，pack到底部，确保始终可见）
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        btn_inner = ttk.Frame(btn_frame)
        btn_inner.pack(anchor=tk.CENTER)

        ttk.Button(btn_inner, text="确定", command=self._on_ok, width=10).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_inner, text="取消", command=self._on_cancel, width=10).pack(side=tk.LEFT, padx=10)

        # 分隔线
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        # 分割设置
        split_mode_text = "左右分割" if self.split_mode == "horizontal" else "上下分割"
        split_frame = ttk.LabelFrame(main_frame, text=f"分割设置（当前: {split_mode_text}）", padding="5")
        split_frame.pack(fill=tk.X, pady=5)

        # 分割模式提示
        if self.split_mode == "horizontal":
            mode_hint = "拖拽红线调整左右分割位置 (C=左, D=右)"
        else:
            mode_hint = "拖拽红线调整上下分割位置 (C=上, D=下)"
        ttk.Label(split_frame, text=mode_hint, foreground='gray').pack(anchor=tk.W, padx=3)

        # 视频信息显示
        self.video_info_var = tk.StringVar(value="正在加载视频信息...")
        ttk.Label(split_frame, textvariable=self.video_info_var, foreground='#0066cc').pack(
            anchor=tk.W, padx=3, pady=(2, 5)
        )

        # 预览画布
        self.preview_canvas = tk.Canvas(
            split_frame, width=self.canvas_width, height=self.canvas_height,
            bg='#333333', highlightthickness=1
        )
        self.preview_canvas.pack(pady=5)
        self.preview_canvas.bind('<Button-1>', self._on_canvas_click)
        self.preview_canvas.bind('<B1-Motion>', self._on_canvas_drag)

        # 分割比例滑块
        ratio_frame = ttk.Frame(split_frame)
        ratio_frame.pack(fill=tk.X, pady=3)
        ttk.Label(ratio_frame, text="分割位置:").pack(side=tk.LEFT, padx=3)
        self.ratio_scale = ttk.Scale(
            ratio_frame, from_=0.1, to=0.9,
            variable=self.split_ratio, orient=tk.HORIZONTAL,
            command=self._on_ratio_change
        )
        self.ratio_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self.ratio_label = ttk.Label(ratio_frame, text=f"{int(self.split_ratio.get() * 100)}%", width=5)
        self.ratio_label.pack(side=tk.LEFT)

        # 缩放设置
        scale_frame = ttk.LabelFrame(main_frame, text="缩放设置", padding="5")
        scale_frame.pack(fill=tk.X, pady=5)

        scale_inner = ttk.Frame(scale_frame)
        scale_inner.pack(fill=tk.X)
        ttk.Label(scale_inner, text="缩放比例:").pack(side=tk.LEFT, padx=3)
        self.scale_spinbox = ttk.Spinbox(
            scale_inner, from_=50, to=200, width=5,
            textvariable=self.scale_percent
        )
        self.scale_spinbox.pack(side=tk.LEFT, padx=3)
        ttk.Label(scale_inner, text="% (50-200)").pack(side=tk.LEFT)

        # 封面设置
        cover_frame = ttk.LabelFrame(main_frame, text="封面首帧设置", padding="5")
        cover_frame.pack(fill=tk.X, pady=5)

        # 封面类型选择
        ttk.Radiobutton(
            cover_frame, text="无封面", variable=self.cover_type,
            value="none", command=self._on_cover_type_change
        ).pack(anchor=tk.W)

        # 从视频选择帧
        ttk.Radiobutton(
            cover_frame, text="从视频选择帧", variable=self.cover_type,
            value="frame", command=self._on_cover_type_change
        ).pack(anchor=tk.W)

        self.frame_settings = ttk.Frame(cover_frame)
        self.frame_settings.pack(fill=tk.X, padx=20, pady=2)

        # 帧来源选择
        source_row = ttk.Frame(self.frame_settings)
        source_row.pack(fill=tk.X, pady=2)
        ttk.Label(source_row, text="帧来源:").pack(side=tk.LEFT)
        ttk.Radiobutton(
            source_row, text="模板视频", variable=self.cover_frame_source,
            value="template", command=self._on_frame_source_change
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            source_row, text="列表视频", variable=self.cover_frame_source,
            value="list", command=self._on_frame_source_change
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            source_row, text="拼接后视频", variable=self.cover_frame_source,
            value="merged", command=self._on_frame_source_change
        ).pack(side=tk.LEFT, padx=5)

        # 时间滑块行
        time_row = ttk.Frame(self.frame_settings)
        time_row.pack(fill=tk.X, pady=2)
        ttk.Label(time_row, text="时间点:").pack(side=tk.LEFT)
        self.time_scale = ttk.Scale(
            time_row, from_=0, to=100,
            variable=self.cover_frame_time, orient=tk.HORIZONTAL,
            command=self._on_frame_time_change
        )
        self.time_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self.time_label = ttk.Label(time_row, text="00:00", width=6)
        self.time_label.pack(side=tk.LEFT)

        # 封面帧预览
        preview_row = ttk.Frame(self.frame_settings)
        preview_row.pack(fill=tk.X, pady=5)
        ttk.Label(preview_row, text="预览:").pack(side=tk.LEFT, anchor=tk.N)
        self.cover_preview_canvas = tk.Canvas(
            preview_row, width=240, height=135,
            bg='#333333', highlightthickness=1
        )
        self.cover_preview_canvas.pack(side=tk.LEFT, padx=5)
        self.cover_preview_photo = None

        # 预览说明和手动刷新按钮
        preview_info = ttk.Frame(preview_row)
        preview_info.pack(side=tk.LEFT, padx=5)
        ttk.Label(preview_info, text="(自动更新)", foreground='gray', font=('Arial', 8)).pack()
        ttk.Button(preview_info, text="手动刷新", command=self._update_cover_preview, width=8).pack(pady=2)

        # 导入图片
        ttk.Radiobutton(
            cover_frame, text="导入图片", variable=self.cover_type,
            value="image", command=self._on_cover_type_change
        ).pack(anchor=tk.W)

        self.image_settings = ttk.Frame(cover_frame)
        self.image_settings.pack(fill=tk.X, padx=20, pady=2)

        self.image_entry = ttk.Entry(self.image_settings, textvariable=self.cover_image_path, width=30)
        self.image_entry.pack(side=tk.LEFT, padx=3)
        ttk.Button(self.image_settings, text="选择", command=self._select_cover_image).pack(side=tk.LEFT)

        # 封面时长
        duration_frame = ttk.Frame(cover_frame)
        duration_frame.pack(fill=tk.X, pady=5)
        ttk.Label(duration_frame, text="封面显示时长:").pack(side=tk.LEFT, padx=3)
        ttk.Spinbox(
            duration_frame, from_=0.1, to=10, width=6, increment=0.1,
            textvariable=self.cover_duration, format="%.1f"
        ).pack(side=tk.LEFT)
        ttk.Label(duration_frame, text="秒 (0.1-10)").pack(side=tk.LEFT)

        # 初始化封面设置状态
        self._on_cover_type_change()

    def _load_video_preview(self):
        """加载视频预览"""
        temp_dir = get_temp_dir()
        preview_path = os.path.join(temp_dir, "settings_preview.jpg")

        # 根据帧来源初始化时间滑块
        source = self.cover_frame_source.get()
        if source == "template" and self.template_video:
            source_video = self.template_video
        else:
            source_video = self.video_item.path

        # 获取封面来源视频的信息（用于时间滑块）
        source_info = get_video_info(source_video)
        if source_info:
            self.video_duration = source_info.get('duration', 0)
            self.time_scale.configure(to=max(1, self.video_duration))

        # 获取并显示当前列表视频的尺寸信息
        list_video_info = get_video_info(self.video_item.path)
        if list_video_info:
            width = list_video_info.get('width', 0)
            height = list_video_info.get('height', 0)
            duration = list_video_info.get('duration', 0)
            self.video_info_var.set(f"视频尺寸: {format_video_info(width, height, duration)}")
        else:
            self.video_info_var.set("无法获取视频信息")

        if extract_frame(self.video_item.path, preview_path):
            try:
                img = Image.open(preview_path)
                img.thumbnail((self.canvas_width, self.canvas_height), Image.Resampling.LANCZOS)
                self.preview_image = img
                self.preview_photo = ImageTk.PhotoImage(img)
                self._update_preview()
            except (IOError, OSError) as e:
                logger.warning(f"加载预览图片失败: {e}")
            except Exception as e:
                logger.warning(f"更新预览时发生错误: {e}")

    def _update_preview(self):
        """更新预览"""
        self.preview_canvas.delete("all")
        if self.preview_photo:
            x = (self.canvas_width - self.preview_image.width) // 2
            y = (self.canvas_height - self.preview_image.height) // 2
            self.preview_canvas.create_image(x, y, anchor=tk.NW, image=self.preview_photo)

            # 绘制分割线
            ratio = self.split_ratio.get()
            if self.split_mode == "horizontal":
                line_x = x + int(self.preview_image.width * ratio)
                self.preview_canvas.create_line(
                    line_x, y, line_x, y + self.preview_image.height,
                    fill='red', width=2, dash=(4, 2)
                )
                self.preview_canvas.create_text(
                    x + int(self.preview_image.width * ratio / 2), y + 12,
                    text="C", fill='white', font=('Arial', 12, 'bold')
                )
                self.preview_canvas.create_text(
                    x + int(self.preview_image.width * (1 + ratio) / 2), y + 12,
                    text="D", fill='white', font=('Arial', 12, 'bold')
                )
            else:
                line_y = y + int(self.preview_image.height * ratio)
                self.preview_canvas.create_line(
                    x, line_y, x + self.preview_image.width, line_y,
                    fill='red', width=2, dash=(4, 2)
                )
                self.preview_canvas.create_text(
                    x + self.preview_image.width // 2,
                    y + int(self.preview_image.height * ratio / 2),
                    text="C", fill='white', font=('Arial', 12, 'bold')
                )
                self.preview_canvas.create_text(
                    x + self.preview_image.width // 2,
                    y + int(self.preview_image.height * (1 + ratio) / 2),
                    text="D", fill='white', font=('Arial', 12, 'bold')
                )

        self.ratio_label.config(text=f"{int(self.split_ratio.get() * 100)}%")

    def _on_ratio_change(self, value):
        """滑块变化时的回调（带防抖）"""
        if self._preview_update_job:
            self.dialog.after_cancel(self._preview_update_job)
        self._update_split_line_only()
        self._preview_update_job = self.dialog.after(50, self._update_preview)

    def _update_split_line_only(self):
        """仅更新分割线位置（轻量操作）"""
        self.preview_canvas.delete("split_line")
        if self.preview_photo:
            x = (self.canvas_width - self.preview_image.width) // 2
            y = (self.canvas_height - self.preview_image.height) // 2
            ratio = self.split_ratio.get()
            if self.split_mode == "horizontal":
                line_x = x + int(self.preview_image.width * ratio)
                self.preview_canvas.create_line(
                    line_x, y, line_x, y + self.preview_image.height,
                    fill='red', width=2, dash=(4, 2), tags="split_line"
                )
            else:
                line_y = y + int(self.preview_image.height * ratio)
                self.preview_canvas.create_line(
                    x, line_y, x + self.preview_image.width, line_y,
                    fill='red', width=2, dash=(4, 2), tags="split_line"
                )
        self.ratio_label.config(text=f"{int(self.split_ratio.get() * 100)}%")

    def _on_canvas_click(self, event):
        """画布点击"""
        self._update_ratio_from_mouse(event)

    def _on_canvas_drag(self, event):
        """画布拖拽"""
        self._update_ratio_from_mouse(event)

    def _update_ratio_from_mouse(self, event):
        """从鼠标事件更新分割比例"""
        if self.preview_image:
            x = (self.canvas_width - self.preview_image.width) // 2
            y = (self.canvas_height - self.preview_image.height) // 2
            if self.split_mode == "horizontal":
                new_ratio = (event.x - x) / self.preview_image.width
            else:
                new_ratio = (event.y - y) / self.preview_image.height
            new_ratio = max(0.1, min(0.9, new_ratio))
            self.split_ratio.set(new_ratio)
            self._update_split_line_only()
            if self._preview_update_job:
                self.dialog.after_cancel(self._preview_update_job)
            self._preview_update_job = self.dialog.after(100, self._update_preview)

    def _on_cover_type_change(self):
        """封面类型改变"""
        cover_type = self.cover_type.get()
        state_frame = 'normal' if cover_type == 'frame' else 'disabled'
        state_image = 'normal' if cover_type == 'image' else 'disabled'

        def set_children_state(widget, state):
            for child in widget.winfo_children():
                try:
                    child.configure(state=state)
                except tk.TclError:
                    pass
                except Exception as e:
                    logger.warning(f"设置控件状态失败: {e}")
                set_children_state(child, state)

        set_children_state(self.frame_settings, state_frame)
        set_children_state(self.image_settings, state_image)

        if cover_type == 'frame':
            self._update_cover_preview()

    def _on_frame_source_change(self):
        """当帧来源改变时，更新时间滑块范围和预览"""
        source = self.cover_frame_source.get()
        if source == "template" and self.template_video:
            video_path = self.template_video
        elif source == "merged":
            video_path = self._generate_merged_preview()
            if not video_path:
                logger.warning("无法生成拼接预览，使用列表视频")
                video_path = self.video_item.path
        else:
            video_path = self.video_item.path

        info = get_video_info(video_path)
        if info:
            duration = info.get('duration', 0)
            self.time_scale.configure(to=max(1, duration))
            self.cover_frame_time.set(0)
            self.time_label.config(text="00:00")

        self._update_cover_preview()

    def _on_frame_time_change(self, value):
        """帧时间改变"""
        time_sec = float(value)
        mins = int(time_sec // 60)
        secs = int(time_sec % 60)
        self.time_label.config(text=f"{mins:02d}:{secs:02d}")

        if hasattr(self, '_preview_update_job') and self._preview_update_job:
            self.dialog.after_cancel(self._preview_update_job)
        self._preview_update_job = self.dialog.after(300, self._update_cover_preview)

    def _update_cover_preview(self):
        """更新封面帧预览"""
        if self.cover_type.get() != 'frame':
            return

        source = self.cover_frame_source.get()
        if source == "template" and self.template_video:
            video_path = self.template_video
        elif source == "merged":
            video_path = self._generate_merged_preview()
            if not video_path:
                self._show_cover_preview_error("拼接失败")
                return
        else:
            video_path = self.video_item.path

        time_pos = self.cover_frame_time.get()
        temp_dir = get_temp_dir()
        preview_path = os.path.join(temp_dir, "cover_preview.jpg")

        if extract_frame(video_path, preview_path, time_pos):
            try:
                img = Image.open(preview_path)
                img.thumbnail((240, 135), Image.Resampling.LANCZOS)
                self.cover_preview_photo = ImageTk.PhotoImage(img)

                self.cover_preview_canvas.delete("all")
                x = (240 - img.width) // 2
                y = (135 - img.height) // 2
                self.cover_preview_canvas.create_image(x, y, anchor=tk.NW, image=self.cover_preview_photo)
            except Exception as e:
                self._show_cover_preview_error("加载失败")
        else:
            self._show_cover_preview_error("提取失败")

    def _show_cover_preview_error(self, msg):
        """显示封面预览错误"""
        self.cover_preview_canvas.delete("all")
        self.cover_preview_canvas.create_text(120, 67, text=msg, fill='#888888', font=('Arial', 10))

    def _generate_merged_preview(self):
        """生成拼接后视频的快速预览（用于封面帧选择）"""
        if not self.template_video or not self.parent_app:
            logger.warning("无法生成拼接预览：缺少模板视频或主窗口引用")
            return None

        try:
            temp_dir = get_temp_dir()
            merged_preview_path = os.path.join(temp_dir, "merged_preview.mp4")

            if hasattr(self, '_cached_merged_preview') and os.path.exists(self._cached_merged_preview):
                logger.debug(f"使用缓存的拼接预览: {self._cached_merged_preview}")
                return self._cached_merged_preview

            self._show_cover_preview_error("正在生成预览...\n(首次需10-20秒)")
            self.dialog.update()

            combinations = self.parent_app._get_merge_combinations()
            if not combinations:
                logger.warning("无法获取拼接组合")
                return None
            merge_mode = combinations[0]
            logger.debug(f"生成拼接预览，merge_mode={merge_mode}")

            ffmpeg = get_ffmpeg_path()
            template_video = self.template_video
            target_video = self.video_item.path
            split_mode = self.split_mode
            split_ratio = self.split_ratio.get()

            template_info = get_video_info(template_video)
            if not template_info:
                return None

            out_width = template_info['width']
            out_height = template_info['height']

            if split_mode == "horizontal":
                template_part_a_width = int(out_width * split_ratio)
                template_part_b_width = out_width - template_part_a_width

                if merge_mode == "a+c":
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={template_part_a_width}:{out_height}:0:0[va];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={template_part_b_width}:{out_height}:{out_width}-{template_part_b_width}:0[vc];"
                        f"[va][vc]hstack=inputs=2[outv]"
                    )
                elif merge_mode == "a+d":
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={template_part_a_width}:{out_height}:0:0[va];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={template_part_b_width}:{out_height}:0:0[vd];"
                        f"[va][vd]hstack=inputs=2[outv]"
                    )
                elif merge_mode == "b+c":
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={template_part_b_width}:{out_height}:{template_part_a_width}:0[vb];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={template_part_a_width}:{out_height}:{out_width}-{template_part_a_width}:0[vc];"
                        f"[vb][vc]hstack=inputs=2[outv]"
                    )
                else:
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={template_part_b_width}:{out_height}:{template_part_a_width}:0[vb];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={template_part_a_width}:{out_height}:0:0[vd];"
                        f"[vb][vd]hstack=inputs=2[outv]"
                    )
            else:
                template_part_a_height = int(out_height * split_ratio)
                template_part_b_height = out_height - template_part_a_height

                if merge_mode == "a+c":
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={out_width}:{template_part_a_height}:0:0[va];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={out_width}:{template_part_b_height}:0:{out_height}-{template_part_b_height}[vc];"
                        f"[va][vc]vstack=inputs=2[outv]"
                    )
                elif merge_mode == "a+d":
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={out_width}:{template_part_a_height}:0:0[va];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={out_width}:{template_part_b_height}:0:0[vd];"
                        f"[va][vd]vstack=inputs=2[outv]"
                    )
                elif merge_mode == "b+c":
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={out_width}:{template_part_b_height}:0:{template_part_a_height}[vb];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={out_width}:{template_part_a_height}:0:{out_height}-{template_part_a_height}[vc];"
                        f"[vb][vc]vstack=inputs=2[outv]"
                    )
                else:
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={out_width}:{template_part_b_height}:0:{template_part_a_height}[vb];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
                        f"crop={out_width}:{template_part_a_height}:0:0[vd];"
                        f"[vb][vd]vstack=inputs=2[outv]"
                    )

            cmd = [
                ffmpeg, '-y',
                '-i', template_video,
                '-i', target_video,
                '-filter_complex', video_filter,
                '-map', '[outv]',
                '-t', '30',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '28',
                merged_preview_path
            ]

            logger.debug("执行FFmpeg命令生成拼接预览")
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            if result.returncode == 0 and os.path.exists(merged_preview_path):
                self._cached_merged_preview = merged_preview_path
                logger.info(f"拼接预览生成成功: {merged_preview_path}")
                return merged_preview_path
            else:
                logger.error(f"拼接预览生成失败 (returncode={result.returncode})")
                if result.stderr:
                    logger.error(f"FFmpeg错误: {result.stderr[-500:]}")
                return None

        except Exception as e:
            logger.error(f"生成拼接预览时发生异常: {str(e)}", exc_info=True)
            return None

    def _select_cover_image(self):
        """选择封面图片"""
        file_path = filedialog.askopenfilename(
            title="选择封面图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp"), ("所有文件", "*.*")]
        )
        if file_path:
            self.cover_image_path.set(file_path)

    def _on_ok(self):
        """确定按钮"""
        self.video_item.split_ratio = self.split_ratio.get()
        self.video_item.scale_percent = self.scale_percent.get()
        self.video_item.cover_type = self.cover_type.get()
        self.video_item.cover_frame_time = self.cover_frame_time.get()
        self.video_item.cover_image_path = self.cover_image_path.get() or None
        self.video_item.cover_duration = self.cover_duration.get()
        self.video_item.cover_frame_source = self.cover_frame_source.get()
        self.result = True
        self.dialog.destroy()

    def _on_cancel(self):
        """取消按钮"""
        self.result = False
        self.dialog.destroy()

    def show(self) -> Optional[bool]:
        """显示对话框并返回结果"""
        self.dialog.wait_window()
        return self.result
