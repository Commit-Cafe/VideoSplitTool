"""
对话框组件
包含视频设置对话框等
"""
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
from typing import Optional

from ..models.video_item import VideoItem
from ..core.ffmpeg_utils import FFmpegHelper
from ..utils.format_utils import format_duration


class VideoSettingsDialog:
    """视频设置对话框"""

    def __init__(
        self,
        parent,
        video_item: VideoItem,
        split_mode: str,
        template_video: str = None,
        parent_app=None
    ):
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

        # 按钮区域（先创建，pack到底部）
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        btn_inner = ttk.Frame(btn_frame)
        btn_inner.pack(anchor=tk.CENTER)

        ttk.Button(btn_inner, text="确定", command=self._on_ok, width=10).pack(
            side=tk.LEFT, padx=10
        )
        ttk.Button(btn_inner, text="取消", command=self._on_cancel, width=10).pack(
            side=tk.LEFT, padx=10
        )

        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(
            side=tk.BOTTOM, fill=tk.X, pady=5
        )

        # 分割设置
        self._create_split_settings(main_frame)

        # 缩放设置
        self._create_scale_settings(main_frame)

        # 封面设置
        self._create_cover_settings(main_frame)

    def _create_split_settings(self, parent):
        """创建分割设置区域"""
        split_mode_text = "左右分割" if self.split_mode == "horizontal" else "上下分割"
        split_frame = ttk.LabelFrame(parent, text=f"分割设置（当前: {split_mode_text}）", padding="5")
        split_frame.pack(fill=tk.X, pady=5)

        if self.split_mode == "horizontal":
            mode_hint = "拖拽红线调整左右分割位置 (C=左, D=右)"
        else:
            mode_hint = "拖拽红线调整上下分割位置 (C=上, D=下)"
        ttk.Label(split_frame, text=mode_hint, foreground='gray').pack(anchor=tk.W, padx=3)

        self.video_info_var = tk.StringVar(value="正在加载视频信息...")
        ttk.Label(
            split_frame, textvariable=self.video_info_var, foreground='#0066cc'
        ).pack(anchor=tk.W, padx=3, pady=(2, 5))

        self.preview_canvas = tk.Canvas(
            split_frame, width=self.canvas_width, height=self.canvas_height,
            bg='#333333', highlightthickness=1
        )
        self.preview_canvas.pack(pady=5)
        self.preview_canvas.bind('<Button-1>', self._on_canvas_click)
        self.preview_canvas.bind('<B1-Motion>', self._on_canvas_drag)

        ratio_frame = ttk.Frame(split_frame)
        ratio_frame.pack(fill=tk.X, pady=3)
        ttk.Label(ratio_frame, text="分割位置:").pack(side=tk.LEFT, padx=3)
        self.ratio_scale = ttk.Scale(
            ratio_frame, from_=0.1, to=0.9,
            variable=self.split_ratio, orient=tk.HORIZONTAL,
            command=self._on_ratio_change
        )
        self.ratio_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self.ratio_label = ttk.Label(
            ratio_frame, text=f"{int(self.split_ratio.get() * 100)}%", width=5
        )
        self.ratio_label.pack(side=tk.LEFT)

    def _create_scale_settings(self, parent):
        """创建缩放设置区域"""
        scale_frame = ttk.LabelFrame(parent, text="缩放设置", padding="5")
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

    def _create_cover_settings(self, parent):
        """创建封面设置区域"""
        cover_frame = ttk.LabelFrame(parent, text="封面首帧设置", padding="5")
        cover_frame.pack(fill=tk.X, pady=5)

        ttk.Radiobutton(
            cover_frame, text="无封面", variable=self.cover_type,
            value="none", command=self._on_cover_type_change
        ).pack(anchor=tk.W)

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

        # 时间滑块
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

        # 封面预览
        preview_row = ttk.Frame(self.frame_settings)
        preview_row.pack(fill=tk.X, pady=5)
        ttk.Label(preview_row, text="预览:").pack(side=tk.LEFT, anchor=tk.N)
        self.cover_preview_canvas = tk.Canvas(
            preview_row, width=240, height=135,
            bg='#333333', highlightthickness=1
        )
        self.cover_preview_canvas.pack(side=tk.LEFT, padx=5)
        self.cover_preview_photo = None

        # 图片封面选项
        ttk.Radiobutton(
            cover_frame, text="使用外部图片", variable=self.cover_type,
            value="image", command=self._on_cover_type_change
        ).pack(anchor=tk.W)

        self.image_settings = ttk.Frame(cover_frame)
        self.image_settings.pack(fill=tk.X, padx=20, pady=2)

        img_row = ttk.Frame(self.image_settings)
        img_row.pack(fill=tk.X, pady=2)
        self.image_path_entry = ttk.Entry(
            img_row, textvariable=self.cover_image_path, width=30
        )
        self.image_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(img_row, text="浏览", command=self._browse_image).pack(
            side=tk.LEFT, padx=5
        )

        # 封面时长
        duration_frame = ttk.Frame(cover_frame)
        duration_frame.pack(fill=tk.X, pady=5)
        ttk.Label(duration_frame, text="封面显示时长:").pack(side=tk.LEFT, padx=3)
        ttk.Spinbox(
            duration_frame, from_=0.5, to=10.0, increment=0.5, width=5,
            textvariable=self.cover_duration
        ).pack(side=tk.LEFT, padx=3)
        ttk.Label(duration_frame, text="秒").pack(side=tk.LEFT)

        self._on_cover_type_change()

    def _load_video_preview(self):
        """加载视频预览"""
        video_info = FFmpegHelper.get_video_info(self.video_item.path)
        if video_info:
            self.video_duration = video_info.duration
            self.time_scale.configure(to=self.video_duration)
            info_text = f"{video_info.width}x{video_info.height}, 时长: {format_duration(video_info.duration)}"
            self.video_info_var.set(info_text)

        self._update_split_preview()

    def _update_split_preview(self):
        """更新分割预览"""
        # 简化的预览更新
        pass

    def _on_ratio_change(self, value=None):
        """分割比例改变"""
        self.ratio_label.config(text=f"{int(self.split_ratio.get() * 100)}%")
        self._update_split_preview()

    def _on_canvas_click(self, event):
        """画布点击"""
        self._update_ratio_from_canvas(event)

    def _on_canvas_drag(self, event):
        """画布拖拽"""
        self._update_ratio_from_canvas(event)

    def _update_ratio_from_canvas(self, event):
        """从画布事件更新分割比例"""
        if self.split_mode == "horizontal":
            ratio = max(0.1, min(0.9, event.x / self.canvas_width))
        else:
            ratio = max(0.1, min(0.9, event.y / self.canvas_height))
        self.split_ratio.set(ratio)
        self._on_ratio_change()

    def _on_cover_type_change(self):
        """封面类型改变"""
        cover_type = self.cover_type.get()
        if cover_type == "frame":
            for child in self.frame_settings.winfo_children():
                child.pack_configure()
            for child in self.image_settings.winfo_children():
                child.pack_forget()
        elif cover_type == "image":
            for child in self.frame_settings.winfo_children():
                child.pack_forget()
            for child in self.image_settings.winfo_children():
                child.pack_configure()
        else:
            for child in self.frame_settings.winfo_children():
                child.pack_forget()
            for child in self.image_settings.winfo_children():
                child.pack_forget()

    def _on_frame_source_change(self):
        """帧来源改变"""
        pass

    def _on_frame_time_change(self, value=None):
        """帧时间改变"""
        time_val = self.cover_frame_time.get()
        self.time_label.config(text=format_duration(time_val))

    def _browse_image(self):
        """浏览图片"""
        file_path = filedialog.askopenfilename(
            title="选择封面图片",
            filetypes=[
                ("图片文件", "*.jpg;*.jpeg;*.png;*.bmp;*.gif"),
                ("所有文件", "*.*")
            ]
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
        self.result = self.video_item
        self.dialog.destroy()

    def _on_cancel(self):
        """取消按钮"""
        self.result = None
        self.dialog.destroy()

    def show(self) -> Optional[VideoItem]:
        """显示对话框并返回结果"""
        self.dialog.wait_window()
        return self.result
