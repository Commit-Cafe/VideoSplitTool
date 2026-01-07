"""
主窗口组件
视频分割拼接工具的主界面
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import subprocess
import threading
from datetime import datetime
from PIL import Image, ImageTk
from typing import List

from ..models.video_item import VideoItem
from ..core.video_processor import VideoProcessor
from ..core.ffmpeg_utils import FFmpegHelper, check_ffmpeg
from ..core.error_handler import InputValidator
from ..utils.logger import logger, cleanup_old_logs
from ..utils.temp_manager import global_temp_manager, cleanup_on_exit
from ..utils.file_utils import get_temp_dir, is_valid_video
from ..utils.format_utils import format_video_info
from .dialogs import VideoSettingsDialog
from .widgets import ScrollableFrame
from .compat import get_video_info, extract_frame


class VideoSplitApp:
    """视频分割拼接应用 V2.2"""

    VERSION = "2.2"

    def __init__(self, root):
        self.root = root
        self.root.title(f"视频分割拼接工具 V{self.VERSION}")
        self.root.geometry("750x800")
        self.root.minsize(650, 700)

        # 数据
        self.template_video = tk.StringVar()
        self.video_items: List[VideoItem] = []
        self.split_mode = tk.StringVar(value="horizontal")
        self.output_dir = tk.StringVar()
        self.split_ratio = tk.DoubleVar(value=0.5)
        self.naming_rule = tk.StringVar(value="time")
        self.custom_prefix = tk.StringVar(value="video")

        # 拼接部分勾选
        self.use_part_a = tk.BooleanVar(value=True)
        self.use_part_b = tk.BooleanVar(value=False)
        self.use_part_c = tk.BooleanVar(value=True)
        self.use_part_d = tk.BooleanVar(value=False)

        # 位置顺序
        self.position_order = tk.StringVar(value="template_first")

        # 输出比例（独立于分割比例，控制输出视频中各部分的大小）
        self.output_ratio = tk.DoubleVar(value=0.5)
        self.output_ratio_enabled = tk.BooleanVar(value=False)  # 是否启用独立输出比例

        # 各部分视频的缩放模式和百分比
        self.template_scale_mode = tk.StringVar(value="fit")  # fit/fill/stretch/custom
        self.list_scale_mode = tk.StringVar(value="fit")
        self.template_scale_percent = tk.IntVar(value=100)  # 自定义缩放百分比
        self.list_scale_percent = tk.IntVar(value=100)

        # 全局封面设置
        self.global_cover_type = tk.StringVar(value="none")  # none/template/list/merged/image
        self.global_cover_frame_time = tk.DoubleVar(value=0.0)
        self.global_cover_duration = tk.DoubleVar(value=1.0)
        self.global_cover_image_path = tk.StringVar()

        # 预览相关
        self.merge_preview_image = None  # PIL Image对象
        self.merge_preview_photo = None  # PhotoImage对象

        # 音频配置
        self.audio_source = tk.StringVar(value="template")
        self.custom_audio_path = tk.StringVar()

        # 输出尺寸配置
        self.output_size_mode = tk.StringVar(value="template")
        self.output_width = tk.IntVar(value=1920)
        self.output_height = tk.IntVar(value=1080)
        self.scale_mode = tk.StringVar(value="fit")
        self.template_width = 0
        self.template_height = 0

        # 输出时长配置
        self.output_duration_mode = tk.StringVar(value="template")  # template/list

        # 预览相关
        self.preview_image = None
        self.preview_photo = None
        self._preview_update_job = None
        self.canvas_width = 320
        self.canvas_height = 180
        self.dragging = False

        # 处理器
        self.processor = VideoProcessor()

        # 处理状态
        self.is_processing = False
        self.processing_stopped = False

        if not check_ffmpeg():
            messagebox.showerror("错误", "未检测到FFmpeg，请确保FFmpeg已安装并添加到系统PATH中")

        self._create_widgets()
        logger.info(f"程序启动 - V{self.VERSION}")

    def _create_widgets(self):
        """创建主界面控件"""
        scroll_container = ScrollableFrame(self.root)
        scroll_container.pack(fill=tk.BOTH, expand=True)

        main_frame = ttk.Frame(scroll_container.scrollable_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 模板视频选择
        self._create_template_section(main_frame)

        # 预览区域
        self._create_preview_section(main_frame)

        # 视频列表
        self._create_list_section(main_frame)

        # 拼接设置
        self._create_merge_section(main_frame)

        # 输出尺寸设置
        self._create_output_size_section(main_frame)

        # 音频设置
        self._create_audio_section(main_frame)

        # 输出设置
        self._create_output_section(main_frame)

        # 进度条和状态栏
        self._create_progress_section(main_frame)

        self._draw_placeholder()
        self._on_merge_change()

    def _create_template_section(self, parent):
        """创建模板视频选择区域"""
        template_frame = ttk.LabelFrame(parent, text="模板视频 (A/B)", padding="5")
        template_frame.pack(fill=tk.X, pady=3)

        entry_frame = ttk.Frame(template_frame)
        entry_frame.pack(fill=tk.X)
        ttk.Entry(entry_frame, textvariable=self.template_video).pack(
            side=tk.LEFT, padx=5, expand=True, fill=tk.X
        )
        ttk.Button(entry_frame, text="选择", command=self._select_template, width=8).pack(
            side=tk.LEFT, padx=5
        )

        self.template_info_var = tk.StringVar(value="")
        ttk.Label(
            template_frame, textvariable=self.template_info_var,
            foreground='#0066cc', font=('Arial', 9)
        ).pack(anchor=tk.W, padx=5, pady=(3, 0))

    def _create_preview_section(self, parent):
        """创建预览区域"""
        preview_frame = ttk.LabelFrame(parent, text="分割预览", padding="5")
        preview_frame.pack(fill=tk.X, pady=3)

        # 主容器：左侧控制 + 右侧预览
        main_container = ttk.Frame(preview_frame)
        main_container.pack(fill=tk.X, pady=2)

        # 左侧：控制区域
        left_frame = ttk.Frame(main_container)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 分割方式标签
        ttk.Label(left_frame, text="分割方式:").pack(anchor=tk.W, padx=3, pady=(0, 3))

        # 分割方式选项（另起一行）
        split_option_frame = ttk.Frame(left_frame)
        split_option_frame.pack(fill=tk.X, pady=(0, 8), padx=10)
        ttk.Radiobutton(
            split_option_frame, text="左右分割", variable=self.split_mode,
            value="horizontal", command=self._update_preview
        ).pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(
            split_option_frame, text="上下分割", variable=self.split_mode,
            value="vertical", command=self._update_preview
        ).pack(side=tk.LEFT)

        # 分割位置标签
        ttk.Label(left_frame, text="分割位置:").pack(anchor=tk.W, padx=3, pady=(5, 3))

        # 分割位置滑块（另起一行）
        ratio_frame = ttk.Frame(left_frame)
        ratio_frame.pack(fill=tk.X, pady=3, padx=10)
        self.ratio_scale = ttk.Scale(
            ratio_frame, from_=0.1, to=0.9, length=180,
            variable=self.split_ratio, orient=tk.HORIZONTAL,
            command=self._on_ratio_change
        )
        self.ratio_scale.pack(side=tk.LEFT, padx=3)
        self.ratio_label = ttk.Label(ratio_frame, text="50%", width=5)
        self.ratio_label.pack(side=tk.LEFT, padx=3)

        # 右侧：预览画布
        right_frame = ttk.Frame(main_container)
        right_frame.pack(side=tk.RIGHT, padx=(15, 5))

        preview_label = ttk.Label(right_frame, text="模板预览 (拖拽调整)", font=('Arial', 9))
        preview_label.pack()
        self.preview_canvas = tk.Canvas(
            right_frame, width=self.canvas_width, height=self.canvas_height,
            bg='#333333', highlightthickness=1, highlightbackground='#666666'
        )
        self.preview_canvas.pack(pady=3)
        self.preview_canvas.bind('<Button-1>', self._on_canvas_click)
        self.preview_canvas.bind('<B1-Motion>', self._on_canvas_drag)
        self.preview_canvas.bind('<ButtonRelease-1>', self._on_canvas_release)

    def _create_list_section(self, parent):
        """创建视频列表区域"""
        list_frame = ttk.LabelFrame(parent, text="视频列表 (C/D) - 双击编辑设置", padding="5")
        list_frame.pack(fill=tk.X, pady=3)

        tree_container = ttk.Frame(list_frame)
        tree_container.pack(fill=tk.X, pady=3)

        columns = ('name', 'split', 'frame_time')
        self.tree = ttk.Treeview(tree_container, columns=columns, show='headings', height=5)
        self.tree.heading('name', text='文件名')
        self.tree.heading('split', text='分割比例')
        self.tree.heading('frame_time', text='封面帧时间')

        self.tree.column('name', width=280, minwidth=180)
        self.tree.column('split', width=80, anchor='center', minwidth=60)
        self.tree.column('frame_time', width=90, anchor='center', minwidth=70)

        tree_scroll = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind('<Double-1>', self._on_tree_double_click)

        # 按钮行
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, pady=3)
        ttk.Button(btn_frame, text="添加", command=self._add_videos, width=7).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="编辑", command=self._edit_selected, width=7).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="删除", command=self._remove_selected, width=7).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="清空", command=self._clear_list, width=7).pack(side=tk.LEFT, padx=4)
        ttk.Separator(btn_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(btn_frame, text="应用到全部", command=self._apply_to_all, width=10).pack(side=tk.LEFT, padx=4)

    def _create_merge_section(self, parent):
        """创建拼接设置区域（左侧设置 + 右侧预览）"""
        merge_frame = ttk.LabelFrame(parent, text="拼接设置", padding="5")
        merge_frame.pack(fill=tk.X, pady=3)

        # 主容器
        main_container = ttk.Frame(merge_frame)
        main_container.pack(fill=tk.BOTH, expand=True)

        # ========== 左侧：设置区域 ==========
        left_frame = ttk.Frame(main_container, width=340)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.pack_propagate(False)

        # --- 拼接部分选择 ---
        merge_inner = ttk.Frame(left_frame)
        merge_inner.pack(fill=tk.X, pady=2)

        ttk.Label(merge_inner, text="模板:").grid(row=0, column=0, padx=3, sticky='w')
        self.check_a = ttk.Checkbutton(
            merge_inner, text="A(左/上)", variable=self.use_part_a,
            command=self._on_merge_change
        )
        self.check_a.grid(row=0, column=1, padx=2)
        self.check_b = ttk.Checkbutton(
            merge_inner, text="B(右/下)", variable=self.use_part_b,
            command=self._on_merge_change
        )
        self.check_b.grid(row=0, column=2, padx=2)

        ttk.Label(merge_inner, text="列表:").grid(row=0, column=3, padx=(8, 3), sticky='w')
        self.check_c = ttk.Checkbutton(
            merge_inner, text="C(左/上)", variable=self.use_part_c,
            command=self._on_merge_change
        )
        self.check_c.grid(row=0, column=4, padx=2)
        self.check_d = ttk.Checkbutton(
            merge_inner, text="D(右/下)", variable=self.use_part_d,
            command=self._on_merge_change
        )
        self.check_d.grid(row=0, column=5, padx=2)

        # --- 位置顺序 ---
        order_frame = ttk.Frame(left_frame)
        order_frame.pack(fill=tk.X, pady=2)
        ttk.Label(order_frame, text="位置:").pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(
            order_frame, text="模板在左/上", variable=self.position_order,
            value="template_first", command=self._on_merge_change
        ).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(
            order_frame, text="列表在左/上", variable=self.position_order,
            value="list_first", command=self._on_merge_change
        ).pack(side=tk.LEFT, padx=2)

        # --- 输出比例 ---
        ratio_frame = ttk.Frame(left_frame)
        ratio_frame.pack(fill=tk.X, pady=2)
        self.output_ratio_check = ttk.Checkbutton(
            ratio_frame, text="自定义比例",
            variable=self.output_ratio_enabled,
            command=self._on_output_ratio_toggle
        )
        self.output_ratio_check.pack(side=tk.LEFT, padx=3)
        self.output_ratio_scale = ttk.Scale(
            ratio_frame, from_=0.1, to=0.9, length=120,
            variable=self.output_ratio, orient=tk.HORIZONTAL,
            command=self._on_output_ratio_change, state='disabled'
        )
        self.output_ratio_scale.pack(side=tk.LEFT, padx=3)
        self.output_ratio_label = ttk.Label(ratio_frame, text="50%", width=4, foreground='blue')
        self.output_ratio_label.pack(side=tk.LEFT)
        # 效果示意按钮
        self.effect_diagram_btn = ttk.Button(
            ratio_frame, text="效果示意", width=8,
            command=self._show_effect_diagram
        )
        self.effect_diagram_btn.pack(side=tk.LEFT, padx=(8, 0))

        # --- 分隔线 ---
        ttk.Separator(left_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        # --- 封面设置 ---
        cover_label = ttk.Label(left_frame, text="封面设置:", font=('Arial', 9, 'bold'))
        cover_label.pack(anchor=tk.W, padx=3)

        # 封面类型选择
        self.cover_type_frame_ref = ttk.Frame(left_frame)
        self.cover_type_frame_ref.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(
            self.cover_type_frame_ref, text="无", variable=self.global_cover_type,
            value="none", command=self._on_cover_type_change
        ).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(
            self.cover_type_frame_ref, text="模板帧", variable=self.global_cover_type,
            value="template", command=self._on_cover_type_change
        ).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(
            self.cover_type_frame_ref, text="列表帧", variable=self.global_cover_type,
            value="list", command=self._on_cover_type_change
        ).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(
            self.cover_type_frame_ref, text="拼接帧", variable=self.global_cover_type,
            value="merged", command=self._on_cover_type_change
        ).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(
            self.cover_type_frame_ref, text="图片", variable=self.global_cover_type,
            value="image", command=self._on_cover_type_change
        ).pack(side=tk.LEFT, padx=2)

        # 帧时间滑块（仅用于模板帧/列表帧/拼接帧，默认隐藏）
        self.cover_time_frame = ttk.Frame(left_frame)
        # 默认不显示（因为默认封面类型是"none"）

        # 帧时间滑块和按钮在同一行
        ttk.Label(self.cover_time_frame, text="帧时间:").pack(side=tk.LEFT, padx=3)
        self.cover_time_scale = ttk.Scale(
            self.cover_time_frame, from_=0, to=100, length=100,
            variable=self.global_cover_frame_time, orient=tk.HORIZONTAL,
            command=self._on_cover_time_change
        )
        self.cover_time_scale.pack(side=tk.LEFT, padx=2)
        self.cover_time_label = ttk.Label(self.cover_time_frame, text="00:00", width=5)
        self.cover_time_label.pack(side=tk.LEFT)
        # 独立帧设置按钮 - 记录当前预览视频的帧时间
        ttk.Button(
            self.cover_time_frame, text="设为独立", width=7,
            command=self._set_current_video_frame_time
        ).pack(side=tk.LEFT, padx=2)
        # 同步按钮 - 将当前帧时间应用到所有列表视频
        ttk.Button(
            self.cover_time_frame, text="同步全部", width=7,
            command=self._sync_cover_time_to_all
        ).pack(side=tk.LEFT)

        # 封面时长和图片选择
        cover_param_frame = ttk.Frame(left_frame)
        cover_param_frame.pack(fill=tk.X, pady=2)
        ttk.Label(cover_param_frame, text="时长:").pack(side=tk.LEFT, padx=3)
        self.cover_duration_spin = ttk.Spinbox(
            cover_param_frame, from_=0.5, to=10, width=4,
            textvariable=self.global_cover_duration, increment=0.5
        )
        self.cover_duration_spin.pack(side=tk.LEFT)
        ttk.Label(cover_param_frame, text="秒").pack(side=tk.LEFT, padx=(0, 8))

        # 图片选择按钮
        self.cover_image_btn = ttk.Button(
            cover_param_frame, text="选择图片", width=8,
            command=self._select_cover_image, state='disabled'
        )
        self.cover_image_btn.pack(side=tk.LEFT, padx=(8, 0))

        # 状态文字
        self.merge_preview_var = tk.StringVar(value="")
        ttk.Label(left_frame, textvariable=self.merge_preview_var, foreground='#666').pack(
            anchor=tk.W, padx=3, pady=(5, 0)
        )

        # ========== 右侧：预览区域 ==========
        right_frame = ttk.Frame(main_container)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 预览画布（更大）
        self.merge_preview_canvas = tk.Canvas(
            right_frame, width=280, height=180,
            highlightthickness=1, highlightbackground='#999', bg='#2a2a2a'
        )
        self.merge_preview_canvas.pack(pady=(0, 5))

        # 预览控制栏
        preview_ctrl_frame = ttk.Frame(right_frame)
        preview_ctrl_frame.pack(fill=tk.X)

        ttk.Label(preview_ctrl_frame, text="预览:").pack(side=tk.LEFT, padx=3)
        self.preview_video_combo = ttk.Combobox(
            preview_ctrl_frame, width=18, state="readonly",
            values=["(请添加列表视频)"]
        )
        self.preview_video_combo.pack(side=tk.LEFT, padx=3)
        self.preview_video_combo.current(0)
        self.preview_video_combo.bind('<<ComboboxSelected>>', self._on_preview_video_change)

        ttk.Button(
            preview_ctrl_frame, text="刷新", width=5,
            command=self._refresh_merge_preview
        ).pack(side=tk.LEFT, padx=3)

        # 绑定事件（滚轮调整比例，双击放大预览）
        self.merge_preview_canvas.bind('<MouseWheel>', self._on_merge_preview_wheel)
        self.merge_preview_canvas.bind('<Button-4>', self._on_merge_preview_wheel)
        self.merge_preview_canvas.bind('<Button-5>', self._on_merge_preview_wheel)
        self.merge_preview_canvas.bind('<Double-Button-1>', self._on_preview_double_click)

        self.split_mode.trace_add('write', lambda *args: self._on_merge_change())

    def _create_output_size_section(self, parent):
        """创建输出设置区域"""
        output_size_frame = ttk.LabelFrame(parent, text="输出设置", padding="5")
        output_size_frame.pack(fill=tk.X, pady=3)

        # 输出尺寸选择
        ttk.Label(output_size_frame, text="输出尺寸:", font=('Arial', 9)).pack(anchor=tk.W, padx=3)
        size_mode_frame = ttk.Frame(output_size_frame)
        size_mode_frame.pack(fill=tk.X, pady=2)

        ttk.Radiobutton(
            size_mode_frame, text="跟随模板视频", variable=self.output_size_mode,
            value="template", command=self._on_output_size_mode_change
        ).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(
            size_mode_frame, text="跟随列表视频（一对一）", variable=self.output_size_mode,
            value="list", command=self._on_output_size_mode_change
        ).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(
            size_mode_frame, text="自定义尺寸", variable=self.output_size_mode,
            value="custom", command=self._on_output_size_mode_change
        ).pack(side=tk.LEFT, padx=8)

        # 自定义尺寸输入
        self.custom_size_frame = ttk.Frame(output_size_frame)
        self.custom_size_frame.pack(fill=tk.X, pady=2)

        ttk.Label(self.custom_size_frame, text="宽度:").pack(side=tk.LEFT, padx=3)
        self.width_spinbox = ttk.Spinbox(
            self.custom_size_frame, from_=100, to=7680, width=6,
            textvariable=self.output_width
        )
        self.width_spinbox.pack(side=tk.LEFT, padx=2)

        ttk.Label(self.custom_size_frame, text="高度:").pack(side=tk.LEFT, padx=3)
        self.height_spinbox = ttk.Spinbox(
            self.custom_size_frame, from_=100, to=4320, width=6,
            textvariable=self.output_height
        )
        self.height_spinbox.pack(side=tk.LEFT, padx=2)

        ttk.Label(self.custom_size_frame, text="预设:").pack(side=tk.LEFT, padx=(10, 3))
        self.preset_combo = ttk.Combobox(
            self.custom_size_frame, width=15, state="readonly",
            values=[
                "竖屏1080p (1080x1920)",
                "竖屏720p (720x1280)",
                "横屏1080p (1920x1080)",
                "横屏720p (1280x720)",
                "正方形1080 (1080x1080)",
                "正方形720 (720x720)"
            ]
        )
        self.preset_combo.pack(side=tk.LEFT, padx=2)
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)

        # 缩放模式
        self.scale_mode_frame = ttk.Frame(output_size_frame)
        self.scale_mode_frame.pack(fill=tk.X, pady=2)
        ttk.Label(self.scale_mode_frame, text="缩放模式:").pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(
            self.scale_mode_frame, text="适应(留黑边)", variable=self.scale_mode, value="fit"
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            self.scale_mode_frame, text="填充(裁剪)", variable=self.scale_mode, value="fill"
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            self.scale_mode_frame, text="拉伸", variable=self.scale_mode, value="stretch"
        ).pack(side=tk.LEFT, padx=5)

        self.output_size_info = tk.StringVar(value="输出: 等待选择模板视频")
        ttk.Label(
            output_size_frame, textvariable=self.output_size_info, foreground='#666666'
        ).pack(anchor=tk.W, padx=5, pady=2)

        # 分隔线
        ttk.Separator(output_size_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        # 输出时长选择
        ttk.Label(output_size_frame, text="输出时长:", font=('Arial', 9)).pack(anchor=tk.W, padx=3)
        duration_mode_frame = ttk.Frame(output_size_frame)
        duration_mode_frame.pack(fill=tk.X, pady=2)

        ttk.Radiobutton(
            duration_mode_frame, text="跟随模板视频", variable=self.output_duration_mode,
            value="template"
        ).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(
            duration_mode_frame, text="跟随列表视频（一对一）", variable=self.output_duration_mode,
            value="list"
        ).pack(side=tk.LEFT, padx=8)

        # 时长说明
        ttk.Label(
            output_size_frame,
            text="(较短视频自动循环，较长视频自动截断)",
            foreground='#888888', font=('Arial', 8)
        ).pack(anchor=tk.W, padx=8, pady=(0, 2))

        self._on_output_size_mode_change()

    def _create_audio_section(self, parent):
        """创建音频设置区域"""
        audio_frame = ttk.LabelFrame(parent, text="音频设置", padding="5")
        audio_frame.pack(fill=tk.X, pady=3)

        audio_inner = ttk.Frame(audio_frame)
        audio_inner.pack(fill=tk.X, pady=2)

        ttk.Radiobutton(
            audio_inner, text="模板音频", variable=self.audio_source, value="template"
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            audio_inner, text="列表音频", variable=self.audio_source, value="list"
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            audio_inner, text="混合音频", variable=self.audio_source, value="mix"
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            audio_inner, text="静音", variable=self.audio_source, value="none"
        ).pack(side=tk.LEFT, padx=5)

        custom_audio_frame = ttk.Frame(audio_frame)
        custom_audio_frame.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(
            custom_audio_frame, text="自定义音频:", variable=self.audio_source, value="custom"
        ).pack(side=tk.LEFT, padx=5)
        ttk.Entry(custom_audio_frame, textvariable=self.custom_audio_path, width=30).pack(
            side=tk.LEFT, padx=3, expand=True, fill=tk.X
        )
        ttk.Button(
            custom_audio_frame, text="选择", command=self._select_custom_audio, width=6
        ).pack(side=tk.LEFT, padx=3)

    def _create_output_section(self, parent):
        """创建输出设置区域"""
        output_frame = ttk.LabelFrame(parent, text="输出设置", padding="5")
        output_frame.pack(fill=tk.X, pady=3)

        dir_frame = ttk.Frame(output_frame)
        dir_frame.pack(fill=tk.X, pady=2)
        ttk.Label(dir_frame, text="输出目录:").pack(side=tk.LEFT, padx=3)
        ttk.Entry(dir_frame, textvariable=self.output_dir, width=40).pack(
            side=tk.LEFT, padx=3, expand=True, fill=tk.X
        )
        ttk.Button(dir_frame, text="选择", command=self._select_output_dir).pack(side=tk.LEFT, padx=3)

        naming_frame = ttk.Frame(output_frame)
        naming_frame.pack(fill=tk.X, pady=2)
        ttk.Label(naming_frame, text="命名规则:").pack(side=tk.LEFT, padx=3)

        self.naming_combo = ttk.Combobox(
            naming_frame, textvariable=self.naming_rule, state="readonly", width=15
        )
        self.naming_combo['values'] = ["时间戳", "原文件名_merged", "自定义前缀_序号", "原文件名_时间戳"]
        self.naming_combo.current(0)
        self.naming_combo.pack(side=tk.LEFT, padx=3)
        self.naming_combo.bind('<<ComboboxSelected>>', self._on_naming_change)

        ttk.Label(naming_frame, text="前缀:").pack(side=tk.LEFT, padx=3)
        self.prefix_entry = ttk.Entry(naming_frame, textvariable=self.custom_prefix, width=12)
        self.prefix_entry.pack(side=tk.LEFT, padx=3)
        self.prefix_entry.config(state='disabled')

        self.custom_prefix.trace_add('write', lambda *args: self._update_naming_preview())
        self.naming_preview_var = tk.StringVar(value="示例: 20251230_143052_001.mp4")
        ttk.Label(
            output_frame, textvariable=self.naming_preview_var, foreground='gray'
        ).pack(anchor=tk.W, padx=5, pady=2)
        self._update_naming_preview()

    def _create_progress_section(self, parent):
        """创建进度条和状态栏区域"""
        progress_frame = ttk.Frame(parent)
        progress_frame.pack(fill=tk.X, pady=8)
        self.start_btn = ttk.Button(progress_frame, text="开始处理", command=self._start_processing)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(progress_frame, text="停止", command=self._stop_processing, state='disabled')
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        self.progress = ttk.Progressbar(progress_frame, mode='determinate', length=200)
        self.progress.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        self.status_var = tk.StringVar(value="准备就绪")
        status_bar = ttk.Label(parent, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=3)

    # ==================== 事件处理方法 ====================

    def _on_tree_double_click(self, event):
        """双击编辑视频设置"""
        self._edit_selected()

    def _edit_selected(self):
        """编辑选中的视频设置"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一个视频")
            return

        item_id = selection[0]
        index = self.tree.index(item_id)
        video_item = self.video_items[index]

        template_video = self.template_video.get() if self.template_video.get() else None
        dialog = VideoSettingsDialog(self.root, video_item, self.split_mode.get(), template_video, self)
        if dialog.show():
            self._refresh_tree()

    def _apply_to_all(self):
        """将选中视频的设置应用到所有视频"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一个视频作为设置模板")
            return

        if len(self.video_items) < 2:
            return

        item_id = selection[0]
        index = self.tree.index(item_id)
        source_item = self.video_items[index]

        result = messagebox.askyesno("确认", f"将 {source_item.name} 的设置应用到所有视频？")
        if result:
            for item in self.video_items:
                if item != source_item:
                    item.split_ratio = source_item.split_ratio
                    item.scale_percent = source_item.scale_percent
                    item.cover_type = source_item.cover_type
                    item.cover_duration = source_item.cover_duration
                    item.cover_frame_source = source_item.cover_frame_source
                    item.cover_frame_time = source_item.cover_frame_time
            self._refresh_tree()
            messagebox.showinfo("完成", "设置已应用到所有视频")

    def _refresh_tree(self):
        """刷新列表显示"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        for video_item in self.video_items:
            split_str = f"{int(video_item.split_ratio * 100)}%"
            frame_time_str = f"{video_item.cover_frame_time:.1f}s"
            self.tree.insert('', tk.END, values=(video_item.name, split_str, frame_time_str))

        # 更新预览视频下拉列表
        self._update_preview_combo()

    def _on_merge_change(self):
        """当拼接部分勾选变化时更新预览说明"""
        a = self.use_part_a.get()
        b = self.use_part_b.get()
        c = self.use_part_c.get()
        d = self.use_part_d.get()

        template_parts = []
        list_parts = []
        if a:
            template_parts.append("A")
        if b:
            template_parts.append("B")
        if c:
            list_parts.append("C")
        if d:
            list_parts.append("D")

        is_template_first = self.position_order.get() == "template_first"
        mode = self.split_mode.get()

        if mode == "horizontal":
            first_side = "左"
            second_side = "右"
        else:
            first_side = "上"
            second_side = "下"

        if is_template_first:
            template_pos = first_side
            list_pos = second_side
        else:
            template_pos = second_side
            list_pos = first_side

        if len(template_parts) == 0 or len(list_parts) == 0:
            if len(template_parts) == 0 and len(list_parts) > 0:
                self.merge_preview_var.set("仅使用列表视频")
            elif len(list_parts) == 0 and len(template_parts) > 0:
                self.merge_preview_var.set("仅使用模板视频")
            else:
                self.merge_preview_var.set("请勾选要使用的部分")
        else:
            combinations = len(template_parts) * len(list_parts)
            if combinations == 1:
                self.merge_preview_var.set(f"拼接方式: 模板视频在{template_pos}，列表视频在{list_pos}")
            else:
                template_parts_desc = "、".join([
                    f"模板{first_side if p == 'A' else second_side}侧" for p in template_parts
                ])
                list_parts_desc = "、".join([
                    f"列表{first_side if p == 'C' else second_side}侧" for p in list_parts
                ])
                self.merge_preview_var.set(
                    f"将生成 {combinations} 个视频\n"
                    f"模板: {template_parts_desc} | 列表: {list_parts_desc}\n"
                    f"位置: 模板在{template_pos}，列表在{list_pos}"
                )

        self._draw_merge_preview()

    def _draw_merge_preview(self):
        """绘制拼接预览（显示实际视频帧或占位符）"""
        canvas = self.merge_preview_canvas
        canvas.delete("all")

        w = 280
        h = 180

        # 如果没有模板视频，显示占位符
        if not self.template_video.get():
            canvas.create_text(
                w // 2, h // 2,
                text="请选择模板视频", fill='#888', font=('Arial', 11)
            )
            return

        # 如果有缓存的预览图像，直接显示
        if self.merge_preview_photo:
            canvas.create_image(w // 2, h // 2, image=self.merge_preview_photo)
        else:
            # 显示提示
            canvas.create_text(
                w // 2, h // 2 - 10,
                text="点击[刷新]生成预览", fill='#aaa', font=('Arial', 10)
            )
            canvas.create_text(
                w // 2, h // 2 + 10,
                text="或添加列表视频", fill='#777', font=('Arial', 9)
            )

    def _refresh_merge_preview(self):
        """刷新拼接预览（根据封面类型显示不同内容）"""
        canvas = self.merge_preview_canvas
        canvas_w, canvas_h = 280, 180

        template_path = self.template_video.get()
        if not template_path:
            self._draw_merge_preview()
            return

        # 获取当前选中的列表视频
        list_video_path = None
        if self.video_items:
            idx = self.preview_video_combo.current()
            if 0 <= idx < len(self.video_items):
                list_video_path = self.video_items[idx].path

        # 获取当前封面类型
        cover_type = self.global_cover_type.get()

        try:
            temp_dir = get_temp_dir()
            frame_time = self.global_cover_frame_time.get()

            # 根据封面类型决定显示内容
            if cover_type == "template":
                # 模板帧 - 只显示模板视频
                template_frame_path = os.path.join(temp_dir, "preview_template.jpg")
                if not extract_frame(template_path, template_frame_path, frame_time):
                    raise Exception("无法提取模板帧")
                preview_img = Image.open(template_frame_path)
                preview_img.thumbnail((canvas_w - 20, canvas_h - 20), Image.Resampling.LANCZOS)
                self.merge_preview_image = preview_img
                self.merge_preview_photo = ImageTk.PhotoImage(preview_img)
                self._draw_merge_preview()
                self.merge_preview_var.set("预览: 模板视频帧")
                return

            elif cover_type == "list":
                # 列表帧 - 只显示列表视频
                if not list_video_path:
                    canvas.delete("all")
                    canvas.create_text(
                        canvas_w // 2, canvas_h // 2,
                        text="请添加列表视频", fill='#f66', font=('Arial', 10)
                    )
                    return
                list_frame_path = os.path.join(temp_dir, "preview_list.jpg")
                if not extract_frame(list_video_path, list_frame_path, frame_time):
                    raise Exception("无法提取列表帧")
                preview_img = Image.open(list_frame_path)
                preview_img.thumbnail((canvas_w - 20, canvas_h - 20), Image.Resampling.LANCZOS)
                self.merge_preview_image = preview_img
                self.merge_preview_photo = ImageTk.PhotoImage(preview_img)
                self._draw_merge_preview()
                self.merge_preview_var.set("预览: 列表视频帧")
                return

            # 其他情况（merged、none、image等）显示拼接预览
            # 提取模板帧
            template_frame_path = os.path.join(temp_dir, "preview_template.jpg")
            if not extract_frame(template_path, template_frame_path, frame_time):
                raise Exception("无法提取模板帧")
            template_img = Image.open(template_frame_path)

            # 如果没有列表视频，只显示模板
            if not list_video_path:
                template_img.thumbnail((canvas_w - 20, canvas_h - 20), Image.Resampling.LANCZOS)
                self.merge_preview_image = template_img
                self.merge_preview_photo = ImageTk.PhotoImage(template_img)
                self._draw_merge_preview()
                self.merge_preview_var.set("预览: 模板视频")
                return

            # 提取列表帧
            list_frame_path = os.path.join(temp_dir, "preview_list.jpg")
            if not extract_frame(list_video_path, list_frame_path, frame_time):
                raise Exception("无法提取列表帧")
            list_img = Image.open(list_frame_path)

            # 模拟拼接
            merged_img = self._simulate_merge(template_img, list_img)

            # 缩放到画布大小
            merged_img.thumbnail((canvas_w - 10, canvas_h - 10), Image.Resampling.LANCZOS)

            self.merge_preview_image = merged_img
            self.merge_preview_photo = ImageTk.PhotoImage(merged_img)
            self._draw_merge_preview()
            self.merge_preview_var.set("预览: 拼接效果")

        except Exception as e:
            logger.warning(f"生成预览失败: {e}")
            canvas.delete("all")
            canvas.create_text(
                canvas_w // 2, canvas_h // 2,
                text=f"预览生成失败", fill='#f66', font=('Arial', 10)
            )

    def _scale_image_with_mode(self, img, target_w, target_h, mode="stretch"):
        """
        根据缩放模式缩放图片

        Args:
            img: PIL Image对象
            target_w: 目标宽度
            target_h: 目标高度
            mode: 缩放模式 (stretch/fill/fit)

        Returns:
            缩放后的PIL Image
        """
        if mode == "fill":
            # 填充模式：放大到覆盖目标区域，然后居中裁剪
            img_ratio = img.width / img.height
            target_ratio = target_w / target_h
            if img_ratio > target_ratio:
                # 图片更宽，按高度缩放后裁剪宽度
                new_h = target_h
                new_w = int(new_h * img_ratio)
            else:
                # 图片更高，按宽度缩放后裁剪高度
                new_w = target_w
                new_h = int(new_w / img_ratio)
            scaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            # 居中裁剪
            left = (new_w - target_w) // 2
            top = (new_h - target_h) // 2
            return scaled.crop((left, top, left + target_w, top + target_h))

        elif mode == "fit":
            # 适应模式：缩小到适应目标区域，添加黑边
            img_ratio = img.width / img.height
            target_ratio = target_w / target_h
            if img_ratio > target_ratio:
                # 图片更宽，按宽度缩放
                new_w = target_w
                new_h = int(new_w / img_ratio)
            else:
                # 图片更高，按高度缩放
                new_h = target_h
                new_w = int(new_h * img_ratio)
            scaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            # 创建黑色背景并居中粘贴
            result = Image.new('RGB', (target_w, target_h), (0, 0, 0))
            paste_x = (target_w - new_w) // 2
            paste_y = (target_h - new_h) // 2
            result.paste(scaled, (paste_x, paste_y))
            return result

        else:
            # 拉伸模式（默认）：直接缩放到目标尺寸
            return img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    def _simulate_merge(self, template_img, list_img):
        """模拟拼接效果（用PIL实现，支持缩放模式）"""
        split_ratio = self.split_ratio.get()
        output_ratio = self.output_ratio.get() if self.output_ratio_enabled.get() else 0.5
        is_horizontal = self.split_mode.get() == "horizontal"
        is_template_first = self.position_order.get() == "template_first"

        # 获取缩放模式
        template_scale_mode = self.template_scale_mode.get()
        list_scale_mode = self.list_scale_mode.get()

        # 目标尺寸（使用模板尺寸）
        out_w, out_h = template_img.size

        # 裁剪模板
        if is_horizontal:
            t_crop_w = int(template_img.width * split_ratio)
            template_part = template_img.crop((0, 0, t_crop_w, template_img.height))
            l_crop_w = int(list_img.width * split_ratio)
            list_part = list_img.crop((0, 0, l_crop_w, list_img.height))
        else:
            t_crop_h = int(template_img.height * split_ratio)
            template_part = template_img.crop((0, 0, template_img.width, t_crop_h))
            l_crop_h = int(list_img.height * split_ratio)
            list_part = list_img.crop((0, 0, list_img.width, l_crop_h))

        # 计算输出各部分大小并应用缩放模式
        if is_horizontal:
            first_w = int(out_w * output_ratio)
            second_w = out_w - first_w
            if is_template_first:
                first_part = self._scale_image_with_mode(template_part, first_w, out_h, template_scale_mode)
                second_part = self._scale_image_with_mode(list_part, second_w, out_h, list_scale_mode)
            else:
                first_part = self._scale_image_with_mode(list_part, first_w, out_h, list_scale_mode)
                second_part = self._scale_image_with_mode(template_part, second_w, out_h, template_scale_mode)
            merged = Image.new('RGB', (out_w, out_h))
            merged.paste(first_part, (0, 0))
            merged.paste(second_part, (first_w, 0))
        else:
            first_h = int(out_h * output_ratio)
            second_h = out_h - first_h
            if is_template_first:
                first_part = self._scale_image_with_mode(template_part, out_w, first_h, template_scale_mode)
                second_part = self._scale_image_with_mode(list_part, out_w, second_h, list_scale_mode)
            else:
                first_part = self._scale_image_with_mode(list_part, out_w, first_h, list_scale_mode)
                second_part = self._scale_image_with_mode(template_part, out_w, second_h, template_scale_mode)
            merged = Image.new('RGB', (out_w, out_h))
            merged.paste(first_part, (0, 0))
            merged.paste(second_part, (0, first_h))

        return merged

    def _show_effect_diagram(self):
        """显示效果示意图弹窗 - 支持自由拖拽调整区块大小"""
        dialog = tk.Toplevel(self.root)
        dialog.title("拼接效果示意")
        dialog.geometry("400x520")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        # 居中
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 520) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # 获取模板视频尺寸，用于计算画布比例
        template_path = self.template_video.get()
        video_w, video_h = 1920, 1080  # 默认16:9
        if template_path:
            info = get_video_info(template_path)
            if info and info.get('width', 0) > 0 and info.get('height', 0) > 0:
                video_w = info['width']
                video_h = info['height']

        # 根据视频比例计算画布尺寸（最大360x200，保持比例）
        max_canvas_w, max_canvas_h = 360, 200
        video_ratio = video_w / video_h
        if video_ratio > max_canvas_w / max_canvas_h:
            # 视频更宽，以宽度为准
            canvas_w = max_canvas_w
            canvas_h = int(canvas_w / video_ratio)
        else:
            # 视频更高，以高度为准
            canvas_h = max_canvas_h
            canvas_w = int(canvas_h * video_ratio)

        # 确保最小尺寸
        canvas_w = max(200, canvas_w)
        canvas_h = max(120, canvas_h)

        # 提示文字
        video_info_text = f"视频尺寸: {video_w}x{video_h} | 拖拽手柄调整区块"
        ttk.Label(
            frame, text=video_info_text,
            foreground='#666', font=('Arial', 9)
        ).pack(anchor=tk.W)

        # 画布 - 根据视频比例
        canvas = tk.Canvas(frame, width=canvas_w, height=canvas_h, bg='#333', highlightthickness=1)
        canvas.pack(pady=(5, 8))

        # 存储拖拽状态
        self._diagram_canvas = canvas
        self._diagram_dialog = dialog
        self._diagram_drag_target = None  # 当前拖拽目标
        self._diagram_drag_edge = None    # 拖拽的边缘

        # 初始化区块数据 (相对于画布的位置和大小)
        padding = 10
        mode = self.split_mode.get()
        is_template_first = self.position_order.get() == "template_first"
        output_ratio = self.output_ratio.get() if self.output_ratio_enabled.get() else 0.5

        inner_w = canvas_w - 2 * padding
        inner_h = canvas_h - 2 * padding

        if mode == "horizontal":
            # 左右布局
            first_w = int(inner_w * output_ratio)
            self._diagram_blocks = {
                'first': {'x': padding, 'y': padding, 'w': first_w, 'h': inner_h},
                'second': {'x': padding + first_w, 'y': padding, 'w': inner_w - first_w, 'h': inner_h}
            }
        else:
            # 上下布局
            first_h = int(inner_h * output_ratio)
            self._diagram_blocks = {
                'first': {'x': padding, 'y': padding, 'w': inner_w, 'h': first_h},
                'second': {'x': padding, 'y': padding + first_h, 'w': inner_w, 'h': inner_h - first_h}
            }

        self._diagram_is_template_first = is_template_first
        self._diagram_mode = mode
        self._diagram_padding = padding
        self._diagram_inner_w = inner_w
        self._diagram_inner_h = inner_h
        self._diagram_video_size = (video_w, video_h)  # 保存视频尺寸用于显示

        # 绘制初始状态
        self._draw_draggable_diagram()

        # 绑定鼠标事件
        canvas.bind('<Button-1>', self._on_diagram_mouse_down)
        canvas.bind('<B1-Motion>', self._on_diagram_mouse_move)
        canvas.bind('<ButtonRelease-1>', self._on_diagram_mouse_up)
        canvas.bind('<Motion>', self._on_diagram_hover)

        # 尺寸信息显示
        self._diagram_info_var = tk.StringVar(value="拖拽边缘调整区块大小")
        ttk.Label(frame, textvariable=self._diagram_info_var, foreground='#0066cc').pack(anchor=tk.W, pady=2)

        # 缩放模式设置
        scale_frame = ttk.LabelFrame(frame, text="缩放模式 (视频如何填充区块)", padding="5")
        scale_frame.pack(fill=tk.X, pady=(0, 5))

        # 模板视频缩放模式
        template_row = ttk.Frame(scale_frame)
        template_row.pack(fill=tk.X, pady=2)
        ttk.Label(template_row, text="模板视频:", width=10).pack(side=tk.LEFT)
        for mode_val, text in [("fit", "适应"), ("fill", "填充"), ("stretch", "拉伸")]:
            ttk.Radiobutton(
                template_row, text=text, variable=self.template_scale_mode,
                value=mode_val
            ).pack(side=tk.LEFT, padx=5)

        # 列表视频缩放模式
        list_row = ttk.Frame(scale_frame)
        list_row.pack(fill=tk.X, pady=2)
        ttk.Label(list_row, text="列表视频:", width=10).pack(side=tk.LEFT)
        for mode_val, text in [("fit", "适应"), ("fill", "填充"), ("stretch", "拉伸")]:
            ttk.Radiobutton(
                list_row, text=text, variable=self.list_scale_mode,
                value=mode_val
            ).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            scale_frame,
            text="适应=留黑边  填充=裁切  拉伸=变形填满",
            foreground='#888', font=('Arial', 8)
        ).pack(anchor=tk.W)

        # 按钮区域
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        def apply_and_close():
            # 计算并应用比例
            mode = self._diagram_mode
            first = self._diagram_blocks['first']
            second = self._diagram_blocks['second']

            if mode == "horizontal":
                total_w = first['w'] + second['w']
                new_ratio = first['w'] / total_w if total_w > 0 else 0.5
            else:
                total_h = first['h'] + second['h']
                new_ratio = first['h'] / total_h if total_h > 0 else 0.5

            self.output_ratio_enabled.set(True)
            self.output_ratio.set(new_ratio)
            self._on_output_ratio_toggle()
            self._refresh_merge_preview()
            self.status_var.set(f"已应用拼接设置 (比例: {round(new_ratio*100)}%:{round((1-new_ratio)*100)}%)")
            dialog.destroy()

        def reset_blocks():
            # 重置为默认50:50
            if self._diagram_mode == "horizontal":
                half_w = self._diagram_inner_w // 2
                self._diagram_blocks['first'] = {
                    'x': self._diagram_padding, 'y': self._diagram_padding,
                    'w': half_w, 'h': self._diagram_inner_h
                }
                self._diagram_blocks['second'] = {
                    'x': self._diagram_padding + half_w, 'y': self._diagram_padding,
                    'w': self._diagram_inner_w - half_w, 'h': self._diagram_inner_h
                }
            else:
                half_h = self._diagram_inner_h // 2
                self._diagram_blocks['first'] = {
                    'x': self._diagram_padding, 'y': self._diagram_padding,
                    'w': self._diagram_inner_w, 'h': half_h
                }
                self._diagram_blocks['second'] = {
                    'x': self._diagram_padding, 'y': self._diagram_padding + half_h,
                    'w': self._diagram_inner_w, 'h': self._diagram_inner_h - half_h
                }
            self._draw_draggable_diagram()
            self._diagram_info_var.set("已重置为50:50")

        ttk.Button(btn_frame, text="应用", command=apply_and_close, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="重置", command=reset_blocks, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy, width=8).pack(side=tk.LEFT, padx=5)

    def _draw_draggable_diagram(self):
        """绘制可拖拽的效果示意图"""
        canvas = self._diagram_canvas
        canvas.delete("all")

        first = self._diagram_blocks['first']
        second = self._diagram_blocks['second']
        is_template_first = self._diagram_is_template_first

        template_color = "#4A90D9"
        list_color = "#E8A838"
        handle_color = "#ffffff"

        # 确定颜色
        first_color = template_color if is_template_first else list_color
        second_color = list_color if is_template_first else template_color
        first_label = "模板" if is_template_first else "列表"
        second_label = "列表" if is_template_first else "模板"

        # 获取画布尺寸（使用存储的内部尺寸）
        padding = self._diagram_padding
        inner_w = self._diagram_inner_w
        inner_h = self._diagram_inner_h

        # 计算画布到视频的缩放比例
        video_w, video_h = getattr(self, '_diagram_video_size', (1920, 1080))
        scale_x = video_w / inner_w
        scale_y = video_h / inner_h

        # 计算实际像素尺寸
        first_real_w = int(first['w'] * scale_x)
        first_real_h = int(first['h'] * scale_y)
        second_real_w = int(second['w'] * scale_x)
        second_real_h = int(second['h'] * scale_y)

        # 绘制画布背景区域（显示输出区域）
        canvas.create_rectangle(
            padding, padding,
            padding + inner_w, padding + inner_h,
            fill='#222', outline='#555', width=1
        )

        # 绘制第一个区块
        canvas.create_rectangle(
            first['x'], first['y'],
            first['x'] + first['w'], first['y'] + first['h'],
            fill=first_color, outline="#fff", width=2, tags="block_first"
        )
        # 区块标签和尺寸（显示实际像素）
        canvas.create_text(
            first['x'] + first['w'] // 2, first['y'] + first['h'] // 2 - 10,
            text=first_label, fill="white", font=('Arial', 11, 'bold')
        )
        canvas.create_text(
            first['x'] + first['w'] // 2, first['y'] + first['h'] // 2 + 10,
            text=f"{first_real_w}x{first_real_h}", fill="white", font=('Arial', 9)
        )

        # 绘制第二个区块
        canvas.create_rectangle(
            second['x'], second['y'],
            second['x'] + second['w'], second['y'] + second['h'],
            fill=second_color, outline="#fff", width=2, tags="block_second"
        )
        canvas.create_text(
            second['x'] + second['w'] // 2, second['y'] + second['h'] // 2 - 10,
            text=second_label, fill="white", font=('Arial', 11, 'bold')
        )
        canvas.create_text(
            second['x'] + second['w'] // 2, second['y'] + second['h'] // 2 + 10,
            text=f"{second_real_w}x{second_real_h}", fill="white", font=('Arial', 9)
        )

        # 绘制拖拽手柄（四个角落的小方块）
        handle_size = 6
        for block in [first, second]:
            bx, by, bw, bh = block['x'], block['y'], block['w'], block['h']
            corners = [
                (bx, by),  # 左上
                (bx + bw, by),  # 右上
                (bx, by + bh),  # 左下
                (bx + bw, by + bh),  # 右下
            ]
            for cx, cy in corners:
                canvas.create_rectangle(
                    cx - handle_size // 2, cy - handle_size // 2,
                    cx + handle_size // 2, cy + handle_size // 2,
                    fill=handle_color, outline='#666'
                )

            # 边缘中心手柄
            edge_handles = [
                (bx + bw // 2, by),  # 上
                (bx + bw // 2, by + bh),  # 下
                (bx, by + bh // 2),  # 左
                (bx + bw, by + bh // 2),  # 右
            ]
            for ex, ey in edge_handles:
                canvas.create_rectangle(
                    ex - handle_size // 2, ey - handle_size // 2,
                    ex + handle_size // 2, ey + handle_size // 2,
                    fill=handle_color, outline='#666'
                )

    def _on_diagram_hover(self, event):
        """鼠标悬停 - 改变光标"""
        canvas = self._diagram_canvas
        edge = self._detect_drag_edge(event.x, event.y)

        if edge in ("first_left", "first_right", "second_left", "second_right"):
            canvas.config(cursor="sb_h_double_arrow")
        elif edge in ("first_top", "first_bottom", "second_top", "second_bottom"):
            canvas.config(cursor="sb_v_double_arrow")
        elif edge in ("first_corner_br", "second_corner_br", "first_corner_tl", "second_corner_tl"):
            canvas.config(cursor="sizing")
        elif edge in ("first_corner_bl", "second_corner_bl", "first_corner_tr", "second_corner_tr"):
            canvas.config(cursor="sizing")
        else:
            canvas.config(cursor="")

    def _detect_drag_edge(self, x, y):
        """检测鼠标位置对应的拖拽边缘 - 支持所有边缘和角落"""
        threshold = 8  # 边缘检测范围
        corner_threshold = 12  # 角落检测范围

        for block_name in ['first', 'second']:
            block = self._diagram_blocks[block_name]
            bx, by, bw, bh = block['x'], block['y'], block['w'], block['h']

            # 检测四个角落（优先级最高）
            # 右下角
            if abs(x - (bx + bw)) < corner_threshold and abs(y - (by + bh)) < corner_threshold:
                return f"{block_name}_corner_br"
            # 左上角
            if abs(x - bx) < corner_threshold and abs(y - by) < corner_threshold:
                return f"{block_name}_corner_tl"
            # 右上角
            if abs(x - (bx + bw)) < corner_threshold and abs(y - by) < corner_threshold:
                return f"{block_name}_corner_tr"
            # 左下角
            if abs(x - bx) < corner_threshold and abs(y - (by + bh)) < corner_threshold:
                return f"{block_name}_corner_bl"

            # 检测四个边缘
            # 右边缘
            if abs(x - (bx + bw)) < threshold and by < y < by + bh:
                return f"{block_name}_right"
            # 左边缘
            if abs(x - bx) < threshold and by < y < by + bh:
                return f"{block_name}_left"
            # 下边缘
            if abs(y - (by + bh)) < threshold and bx < x < bx + bw:
                return f"{block_name}_bottom"
            # 上边缘
            if abs(y - by) < threshold and bx < x < bx + bw:
                return f"{block_name}_top"

        return None

    def _on_diagram_mouse_down(self, event):
        """鼠标按下"""
        edge = self._detect_drag_edge(event.x, event.y)
        self._diagram_drag_edge = edge
        self._diagram_drag_start = (event.x, event.y)

    def _on_diagram_mouse_move(self, event):
        """鼠标移动 - 拖拽调整"""
        if not self._diagram_drag_edge:
            return

        padding = self._diagram_padding
        inner_w = self._diagram_inner_w
        inner_h = self._diagram_inner_h
        min_size = 30  # 最小尺寸

        edge = self._diagram_drag_edge
        block_name = edge.split('_')[0]  # 'first' or 'second'
        block = self._diagram_blocks[block_name]

        # 边界限制
        min_x, min_y = padding, padding
        max_x = padding + inner_w
        max_y = padding + inner_h

        if '_corner_' in edge:
            # 角落拖拽 - 同时调整宽高
            corner_type = edge.split('_corner_')[1]
            if corner_type == 'br':  # 右下角
                new_w = max(min_size, event.x - block['x'])
                new_h = max(min_size, event.y - block['y'])
                block['w'] = min(new_w, max_x - block['x'])
                block['h'] = min(new_h, max_y - block['y'])
            elif corner_type == 'tl':  # 左上角
                new_x = max(min_x, min(event.x, block['x'] + block['w'] - min_size))
                new_y = max(min_y, min(event.y, block['y'] + block['h'] - min_size))
                block['w'] = block['x'] + block['w'] - new_x
                block['h'] = block['y'] + block['h'] - new_y
                block['x'] = new_x
                block['y'] = new_y
            elif corner_type == 'tr':  # 右上角
                new_w = max(min_size, event.x - block['x'])
                new_y = max(min_y, min(event.y, block['y'] + block['h'] - min_size))
                block['w'] = min(new_w, max_x - block['x'])
                old_bottom = block['y'] + block['h']
                block['y'] = new_y
                block['h'] = old_bottom - new_y
            elif corner_type == 'bl':  # 左下角
                new_x = max(min_x, min(event.x, block['x'] + block['w'] - min_size))
                new_h = max(min_size, event.y - block['y'])
                old_right = block['x'] + block['w']
                block['x'] = new_x
                block['w'] = old_right - new_x
                block['h'] = min(new_h, max_y - block['y'])
        elif '_right' in edge:
            # 右边缘
            new_w = max(min_size, event.x - block['x'])
            block['w'] = min(new_w, max_x - block['x'])
        elif '_left' in edge:
            # 左边缘
            new_x = max(min_x, min(event.x, block['x'] + block['w'] - min_size))
            block['w'] = block['x'] + block['w'] - new_x
            block['x'] = new_x
        elif '_bottom' in edge:
            # 下边缘
            new_h = max(min_size, event.y - block['y'])
            block['h'] = min(new_h, max_y - block['y'])
        elif '_top' in edge:
            # 上边缘
            new_y = max(min_y, min(event.y, block['y'] + block['h'] - min_size))
            block['h'] = block['y'] + block['h'] - new_y
            block['y'] = new_y

        self._draw_draggable_diagram()

        # 更新信息显示（使用实际像素尺寸）
        first = self._diagram_blocks['first']
        second = self._diagram_blocks['second']
        is_template_first = self._diagram_is_template_first

        # 计算实际像素尺寸
        video_w, video_h = getattr(self, '_diagram_video_size', (1920, 1080))
        inner_w = self._diagram_inner_w
        inner_h = self._diagram_inner_h
        scale_x = video_w / inner_w
        scale_y = video_h / inner_h

        first_real_w = int(first['w'] * scale_x)
        first_real_h = int(first['h'] * scale_y)
        second_real_w = int(second['w'] * scale_x)
        second_real_h = int(second['h'] * scale_y)

        if is_template_first:
            self._diagram_info_var.set(
                f"模板: {first_real_w}x{first_real_h}  列表: {second_real_w}x{second_real_h}"
            )
        else:
            self._diagram_info_var.set(
                f"列表: {first_real_w}x{first_real_h}  模板: {second_real_w}x{second_real_h}"
            )

    def _on_diagram_mouse_up(self, event):
        """鼠标释放"""
        self._diagram_drag_edge = None
        self._diagram_canvas.config(cursor="")

    def _on_cover_type_change(self):
        """封面类型改变"""
        cover_type = self.global_cover_type.get()

        # 控制帧时间滑块显示（仅template/list/merged显示）
        if cover_type in ("template", "list", "merged"):
            self.cover_time_frame.pack(fill=tk.X, pady=2, after=self.cover_type_frame_ref)
            # 根据封面类型设置滑块范围
            self._update_cover_time_scale_range(cover_type)
        else:
            self.cover_time_frame.pack_forget()

        # 图片选择按钮状态
        if cover_type == "image":
            self.cover_image_btn.config(state='normal')
        else:
            self.cover_image_btn.config(state='disabled')

        # 刷新预览
        self._refresh_merge_preview()

    def _update_cover_time_scale_range(self, cover_type):
        """根据封面类型更新帧时间滑块范围"""
        max_duration = 100  # 默认值
        if cover_type == "template" and self.template_video.get():
            info = get_video_info(self.template_video.get())
            if info:
                max_duration = info.get('duration', 100)
        elif cover_type == "list" and self.video_items:
            idx = self.preview_video_combo.current()
            if 0 <= idx < len(self.video_items):
                info = get_video_info(self.video_items[idx].path)
                if info:
                    max_duration = info.get('duration', 100)
        elif cover_type == "merged":
            # 对于拼接帧，使用较短的那个视频时长
            max_duration = 100
            if self.template_video.get():
                info = get_video_info(self.template_video.get())
                if info:
                    max_duration = info.get('duration', 100)

        self.cover_time_scale.configure(to=max(1, max_duration))

    def _on_cover_time_change(self, value):
        """帧时间滑块变化"""
        time_sec = float(value)
        mins = int(time_sec // 60)
        secs = int(time_sec % 60)
        self.cover_time_label.config(text=f"{mins:02d}:{secs:02d}")

    def _set_current_video_frame_time(self):
        """将当前帧时间设置为当前预览视频的独立帧时间"""
        if not self.video_items:
            messagebox.showinfo("提示", "列表中没有视频")
            return

        idx = self.preview_video_combo.current()
        if idx < 0 or idx >= len(self.video_items):
            messagebox.showinfo("提示", "请先选择要设置的视频")
            return

        current_time = self.global_cover_frame_time.get()
        video_item = self.video_items[idx]
        video_item.cover_frame_time = current_time

        self.status_var.set(f"已设置 {video_item.name} 的封面帧时间为 {current_time:.1f}s")
        self._refresh_tree()

    def _sync_cover_time_to_all(self):
        """将当前帧时间同步到所有列表视频"""
        if not self.video_items:
            messagebox.showinfo("提示", "列表中没有视频")
            return

        current_time = self.global_cover_frame_time.get()
        count = 0
        for video_item in self.video_items:
            video_item.cover_frame_time = current_time
            count += 1

        self.status_var.set(f"已将帧时间 {current_time:.1f}s 同步到 {count} 个视频")
        self._refresh_tree()

    def _apply_global_cover_settings(self):
        """将全局封面设置应用到各视频项"""
        cover_type = self.global_cover_type.get()
        cover_duration = self.global_cover_duration.get()
        cover_image_path = self.global_cover_image_path.get()

        for video_item in self.video_items:
            video_item.cover_type = cover_type
            video_item.cover_duration = cover_duration
            video_item.cover_frame_source = cover_type  # template/list/merged

            if cover_type == "image":
                video_item.cover_image_path = cover_image_path
            elif cover_type == "template":
                # 模板帧使用全局帧时间（因为模板视频是同一个）
                video_item.cover_frame_time = self.global_cover_frame_time.get()
            # 对于 "list" 和 "merged"，保留各视频独立的 cover_frame_time

    def _select_cover_image(self):
        """选择封面图片"""
        file_path = filedialog.askopenfilename(
            title="选择封面图片",
            filetypes=[
                ("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.global_cover_image_path.set(file_path)
            self.status_var.set(f"已选择封面图片: {os.path.basename(file_path)}")

    def _on_preview_video_change(self, event=None):
        """预览视频选择改变"""
        self._refresh_merge_preview()

    def _update_preview_combo(self):
        """更新预览视频下拉列表"""
        if self.video_items:
            values = [f"{i+1}. {item.name[:20]}" for i, item in enumerate(self.video_items)]
            self.preview_video_combo['values'] = values
            if self.preview_video_combo.current() < 0 or self.preview_video_combo.current() >= len(values):
                self.preview_video_combo.current(0)
        else:
            self.preview_video_combo['values'] = ["(请添加列表视频)"]
            self.preview_video_combo.current(0)

    def _on_output_size_mode_change(self):
        """当输出尺寸模式改变时"""
        mode = self.output_size_mode.get()

        if mode == "template":
            self.width_spinbox.config(state="disabled")
            self.height_spinbox.config(state="disabled")
            self.preset_combo.config(state="disabled")
            for child in self.scale_mode_frame.winfo_children():
                if isinstance(child, ttk.Radiobutton):
                    child.config(state="disabled")
            if self.template_width > 0 and self.template_height > 0:
                self.output_size_info.set(f"输出: {self.template_width}x{self.template_height} (跟随模板)")
            else:
                self.output_size_info.set("输出: 等待选择模板视频")
        elif mode == "list":
            self.width_spinbox.config(state="disabled")
            self.height_spinbox.config(state="disabled")
            self.preset_combo.config(state="disabled")
            for child in self.scale_mode_frame.winfo_children():
                if isinstance(child, ttk.Radiobutton):
                    child.config(state="disabled")
            if self.video_items:
                self.output_size_info.set("输出: 每个视频使用自己的尺寸（一对一）")
            else:
                self.output_size_info.set("输出: 等待添加列表视频")
        else:
            self.width_spinbox.config(state="normal")
            self.height_spinbox.config(state="normal")
            self.preset_combo.config(state="readonly")
            for child in self.scale_mode_frame.winfo_children():
                if isinstance(child, ttk.Radiobutton):
                    child.config(state="normal")
            self._update_output_size_info()

    def _on_preset_selected(self, event):
        """当选择预设尺寸时"""
        preset = self.preset_combo.get()
        presets = {
            "竖屏1080p (1080x1920)": (1080, 1920),
            "竖屏720p (720x1280)": (720, 1280),
            "横屏1080p (1920x1080)": (1920, 1080),
            "横屏720p (1280x720)": (1280, 720),
            "正方形1080 (1080x1080)": (1080, 1080),
            "正方形720 (720x720)": (720, 720),
        }
        if preset in presets:
            w, h = presets[preset]
            self.output_width.set(w)
            self.output_height.set(h)
            self._update_output_size_info()

    def _update_output_size_info(self):
        """更新输出尺寸信息显示"""
        w = self.output_width.get()
        h = self.output_height.get()
        if w > h:
            orientation = "横屏"
        elif h > w:
            orientation = "竖屏"
        else:
            orientation = "正方形"
        self.output_size_info.set(f"输出: {w}x{h} ({orientation})")

    def _update_output_size_from_template(self):
        """根据模板视频更新输出尺寸默认值"""
        if self.template_width > 0 and self.template_height > 0:
            self.output_width.set(self.template_width)
            self.output_height.set(self.template_height)
            if self.output_size_mode.get() == "template":
                self.output_size_info.set(f"输出: {self.template_width}x{self.template_height} (跟随模板)")

    def _update_list_video_info(self):
        """更新列表视频相关显示"""
        if self.output_size_mode.get() == "list":
            self._on_output_size_mode_change()

    def _get_merge_combinations(self):
        """获取所有拼接组合"""
        template_parts = []
        list_parts = []

        if self.use_part_a.get():
            template_parts.append("a")
        if self.use_part_b.get():
            template_parts.append("b")
        if self.use_part_c.get():
            list_parts.append("c")
        if self.use_part_d.get():
            list_parts.append("d")

        combinations = []
        for t in template_parts:
            for l in list_parts:
                combinations.append(f"{t}+{l}")

        return combinations

    def _select_template(self):
        """选择模板视频"""
        file_path = filedialog.askopenfilename(
            title="选择模板视频",
            filetypes=[
                ("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.template_video.set(file_path)
            self._load_preview(file_path)
            if not self.output_dir.get():
                self.output_dir.set(os.path.dirname(file_path))

    def _load_preview(self, video_path):
        """加载预览"""
        temp_dir = get_temp_dir()
        preview_path = os.path.join(temp_dir, "preview.jpg")

        if extract_frame(video_path, preview_path):
            try:
                img = Image.open(preview_path)
                img.thumbnail((self.canvas_width, self.canvas_height), Image.Resampling.LANCZOS)
                self.preview_image = img
                self.preview_photo = ImageTk.PhotoImage(img)
                self._update_preview()

                info = get_video_info(video_path)
                if info:
                    width = info.get('width', 0)
                    height = info.get('height', 0)
                    duration = info.get('duration', 0)
                    self.template_width = width
                    self.template_height = height
                    self.template_info_var.set(f"尺寸: {format_video_info(width, height, duration)}")
                    self.status_var.set("已加载模板视频")
                    self._update_output_size_from_template()
            except Exception as e:
                logger.warning(f"加载预览失败: {e}")
                self._draw_placeholder()
        else:
            self._draw_placeholder()

    def _draw_placeholder(self):
        """绘制占位符"""
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(
            self.canvas_width // 2, self.canvas_height // 2,
            text="请选择模板视频以预览分割效果", fill='#888888', font=('Arial', 10)
        )

    def _update_preview(self, *args):
        """更新预览"""
        self.preview_canvas.delete("all")
        if self.preview_photo:
            x = (self.canvas_width - self.preview_image.width) // 2
            y = (self.canvas_height - self.preview_image.height) // 2
            self.preview_canvas.create_image(x, y, anchor=tk.NW, image=self.preview_photo)

            ratio = self.split_ratio.get()
            if self.split_mode.get() == "horizontal":
                line_x = x + int(self.preview_image.width * ratio)
                self.preview_canvas.create_line(
                    line_x, y, line_x, y + self.preview_image.height,
                    fill='red', width=2, dash=(4, 2)
                )
                self.preview_canvas.create_text(
                    x + int(self.preview_image.width * ratio / 2), y + 12,
                    text="A", fill='white', font=('Arial', 12, 'bold')
                )
                self.preview_canvas.create_text(
                    x + int(self.preview_image.width * (1 + ratio) / 2), y + 12,
                    text="B", fill='white', font=('Arial', 12, 'bold')
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
                    text="A", fill='white', font=('Arial', 12, 'bold')
                )
                self.preview_canvas.create_text(
                    x + self.preview_image.width // 2,
                    y + int(self.preview_image.height * (1 + ratio) / 2),
                    text="B", fill='white', font=('Arial', 12, 'bold')
                )
        else:
            self._draw_placeholder()

        self.ratio_label.config(text=f"{int(self.split_ratio.get() * 100)}%")
        self._draw_merge_preview()

    def _on_ratio_change(self, value):
        """滑块变化时的回调（带防抖）"""
        if self._preview_update_job:
            self.root.after_cancel(self._preview_update_job)
        self._update_split_line_only()
        self._preview_update_job = self.root.after(50, self._full_preview_update)

    def _update_split_line_only(self):
        """仅更新分割线位置（轻量操作）"""
        self.preview_canvas.delete("split_line")
        if self.preview_photo:
            x = (self.canvas_width - self.preview_image.width) // 2
            y = (self.canvas_height - self.preview_image.height) // 2
            ratio = self.split_ratio.get()
            if self.split_mode.get() == "horizontal":
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

    def _full_preview_update(self):
        """完整预览更新"""
        self._update_preview()

    def _on_canvas_click(self, event):
        """画布点击"""
        if self.preview_image:
            self.dragging = True

    def _on_canvas_drag(self, event):
        """画布拖拽"""
        if self.dragging and self.preview_image:
            x = (self.canvas_width - self.preview_image.width) // 2
            y = (self.canvas_height - self.preview_image.height) // 2
            if self.split_mode.get() == "horizontal":
                new_ratio = (event.x - x) / self.preview_image.width
            else:
                new_ratio = (event.y - y) / self.preview_image.height
            new_ratio = max(0.1, min(0.9, new_ratio))
            self.split_ratio.set(new_ratio)
            self._update_split_line_only()
            if self._preview_update_job:
                self.root.after_cancel(self._preview_update_job)
            self._preview_update_job = self.root.after(100, self._full_preview_update)

    def _on_canvas_release(self, event):
        """画布释放"""
        self.dragging = False

    def _on_merge_preview_wheel(self, event):
        """拼接预览画布滚轮事件 - 调整输出比例"""
        # 自动启用输出比例调整
        if not self.output_ratio_enabled.get():
            self.output_ratio_enabled.set(True)
            self.output_ratio.set(self.split_ratio.get())  # 初始化为当前分割比例
            self._on_output_ratio_toggle()

        # 计算滚动方向和步长
        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            # 向上滚动 - 增加比例
            delta = 0.02
        elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
            # 向下滚动 - 减少比例
            delta = -0.02
        else:
            return

        # 更新输出比例
        new_ratio = self.output_ratio.get() + delta
        new_ratio = max(0.1, min(0.9, new_ratio))
        self.output_ratio.set(new_ratio)
        self._on_output_ratio_change(new_ratio)

    def _on_preview_double_click(self, event):
        """双击预览画布 - 显示高清放大预览窗口"""
        template_path = self.template_video.get()
        if not template_path:
            return

        # 创建放大预览窗口
        dialog = tk.Toplevel(self.root)
        dialog.title("高清预览")
        dialog.transient(self.root)
        dialog.grab_set()

        # 获取屏幕尺寸
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        max_w = int(screen_w * 0.85)
        max_h = int(screen_h * 0.85)

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # 显示加载提示
        loading_label = ttk.Label(frame, text="正在生成高清预览...", font=('Arial', 11))
        loading_label.pack(pady=50)
        dialog.update()

        try:
            # 重新提取高分辨率帧
            temp_dir = get_temp_dir()
            frame_time = self.global_cover_frame_time.get()

            template_frame_path = os.path.join(temp_dir, "hd_preview_template.jpg")
            if not extract_frame(template_path, template_frame_path, frame_time):
                raise Exception("无法提取模板帧")
            template_img = Image.open(template_frame_path)

            # 获取列表视频
            list_video_path = None
            if self.video_items:
                idx = self.preview_video_combo.current()
                if 0 <= idx < len(self.video_items):
                    list_video_path = self.video_items[idx].path

            if list_video_path:
                list_frame_path = os.path.join(temp_dir, "hd_preview_list.jpg")
                if not extract_frame(list_video_path, list_frame_path, frame_time):
                    raise Exception("无法提取列表帧")
                list_img = Image.open(list_frame_path)

                # 高清拼接
                hd_img = self._simulate_merge(template_img, list_img)
            else:
                hd_img = template_img

            # 计算显示尺寸（适应屏幕，保持纵横比）
            orig_w, orig_h = hd_img.size
            scale = min(max_w / orig_w, max_h / orig_h, 1.0)  # 不放大，只缩小
            display_w = int(orig_w * scale)
            display_h = int(orig_h * scale)

            # 移除加载提示
            loading_label.destroy()

            # 设置窗口尺寸
            dialog.geometry(f"{display_w + 20}x{display_h + 80}")

            # 居中显示
            dialog.update_idletasks()
            x = (screen_w - dialog.winfo_width()) // 2
            y = (screen_h - dialog.winfo_height()) // 2
            dialog.geometry(f"+{x}+{y}")

            # 缩放到显示尺寸
            display_img = hd_img.resize((display_w, display_h), Image.Resampling.LANCZOS)
            display_photo = ImageTk.PhotoImage(display_img)

            # 显示图片
            canvas = tk.Canvas(frame, width=display_w, height=display_h, highlightthickness=1)
            canvas.pack()
            canvas.create_image(display_w // 2, display_h // 2, image=display_photo)
            canvas.image = display_photo

            # 显示分辨率信息
            ttk.Label(
                frame, text=f"原始分辨率: {orig_w}x{orig_h}  |  双击或按ESC关闭",
                foreground='#666'
            ).pack(pady=(5, 0))

        except Exception as e:
            loading_label.config(text=f"生成高清预览失败: {e}")
            logger.warning(f"生成高清预览失败: {e}")

        # 绑定关闭事件
        dialog.bind('<Double-Button-1>', lambda e: dialog.destroy())
        dialog.bind('<Escape>', lambda e: dialog.destroy())

    def _on_merge_preview_double_click(self, event):
        """双击预览区域 - 调整对应视频的缩放模式"""
        x, y = event.x, event.y

        # 检测点击的区域
        clicked_area = None
        if hasattr(self, '_merge_preview_areas'):
            for area_name, (x1, y1, x2, y2) in self._merge_preview_areas.items():
                if x1 <= x <= x2 and y1 <= y <= y2:
                    clicked_area = area_name
                    break

        if clicked_area:
            self._show_scale_mode_menu(event, clicked_area)
        else:
            # 点击空白区域，重置输出比例
            self.output_ratio_enabled.set(False)
            self.output_ratio.set(self.split_ratio.get())
            self._on_output_ratio_toggle()
            self.status_var.set("输出比例已重置")

    def _show_scale_mode_menu(self, event, area_type):
        """显示缩放模式选择菜单"""
        menu = tk.Menu(self.root, tearoff=0)

        if area_type == "template":
            current_mode = self.template_scale_mode.get()
            current_percent = self.template_scale_percent.get()
            title = "模板视频缩放"
        else:
            current_mode = self.list_scale_mode.get()
            current_percent = self.list_scale_percent.get()
            title = "列表视频缩放"

        menu.add_command(label=f"== {title} ==", state='disabled')
        menu.add_separator()

        modes = [
            ("fit", "适应 (保持比例，留黑边)"),
            ("fill", "填充 (保持比例，裁剪)"),
            ("stretch", "拉伸 (变形填满)")
        ]

        for mode_value, mode_label in modes:
            prefix = "✓ " if current_mode == mode_value else "   "
            menu.add_command(
                label=f"{prefix}{mode_label}",
                command=lambda v=mode_value, t=area_type: self._set_scale_mode(t, v)
            )

        menu.add_separator()

        # 自定义缩放选项
        custom_prefix = "✓ " if current_mode == "custom" else "   "
        custom_label = f"自定义缩放 ({current_percent}%)" if current_mode == "custom" else "自定义缩放..."
        menu.add_command(
            label=f"{custom_prefix}{custom_label}",
            command=lambda t=area_type: self._show_custom_scale_dialog(t)
        )

        # 在鼠标位置显示菜单
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_custom_scale_dialog(self, area_type):
        """显示自定义缩放对话框"""
        if area_type == "template":
            current_percent = self.template_scale_percent.get()
            title = "模板视频自定义缩放"
        else:
            current_percent = self.list_scale_percent.get()
            title = "列表视频自定义缩放"

        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 300) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 150) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dialog, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="设置缩放百分比 (50% - 200%):", font=('Arial', 10)).pack(pady=(0, 10))

        # 滑块和数值显示
        slider_frame = ttk.Frame(frame)
        slider_frame.pack(fill=tk.X, pady=5)

        scale_var = tk.IntVar(value=current_percent)
        scale_label = ttk.Label(slider_frame, text=f"{current_percent}%", width=6, font=('Arial', 11, 'bold'))
        scale_label.pack(side=tk.RIGHT, padx=5)

        def on_scale_change(val):
            scale_label.config(text=f"{int(float(val))}%")

        scale = ttk.Scale(
            slider_frame, from_=50, to=200, variable=scale_var,
            orient=tk.HORIZONTAL, command=on_scale_change
        )
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 快捷按钮
        quick_frame = ttk.Frame(frame)
        quick_frame.pack(fill=tk.X, pady=8)
        for percent in [50, 75, 100, 125, 150, 200]:
            ttk.Button(
                quick_frame, text=f"{percent}%", width=5,
                command=lambda p=percent: (scale_var.set(p), scale_label.config(text=f"{p}%"))
            ).pack(side=tk.LEFT, padx=2)

        # 确定/取消按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        def on_confirm():
            self._set_scale_mode(area_type, "custom", scale_var.get())
            dialog.destroy()

        ttk.Button(btn_frame, text="确定", command=on_confirm, width=10).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy, width=10).pack(side=tk.RIGHT)

    def _set_scale_mode(self, area_type, mode, percent=100):
        """设置缩放模式"""
        if area_type == "template":
            self.template_scale_mode.set(mode)
            if mode == "custom":
                self.template_scale_percent.set(percent)
            area_name = "模板"
        else:
            self.list_scale_mode.set(mode)
            if mode == "custom":
                self.list_scale_percent.set(percent)
            area_name = "列表"

        if mode == "custom":
            status_text = f"{area_name}视频缩放已设置为: 自定义 {percent}%"
        else:
            mode_names = {"fit": "适应", "fill": "填充", "stretch": "拉伸"}
            status_text = f"{area_name}视频缩放模式已设置为: {mode_names.get(mode, mode)}"

        self.status_var.set(status_text)
        self._draw_merge_preview()

    def _on_output_ratio_toggle(self):
        """切换输出比例启用状态"""
        if self.output_ratio_enabled.get():
            self.output_ratio_scale.config(state='normal')
            # 如果刚启用，设置为当前分割比例
            if abs(self.output_ratio.get() - 0.5) < 0.01:
                self.output_ratio.set(self.split_ratio.get())
        else:
            self.output_ratio_scale.config(state='disabled')

        self._on_output_ratio_change(self.output_ratio.get())
        self._draw_merge_preview()

    def _on_output_ratio_change(self, value):
        """输出比例变化回调"""
        ratio = float(value) if isinstance(value, str) else value
        self.output_ratio_label.config(text=f"{int(ratio * 100)}%")
        self._draw_merge_preview()

    def _add_videos(self):
        """添加视频"""
        files = filedialog.askopenfilenames(
            title="选择视频",
            filetypes=[
                ("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"),
                ("所有文件", "*.*")
            ]
        )
        for f in files:
            if is_valid_video(f) and not any(v.path == f for v in self.video_items):
                video_item = VideoItem(f)
                video_item.split_ratio = self.split_ratio.get()
                self.video_items.append(video_item)
        self._refresh_tree()
        self._update_list_video_info()

    def _remove_selected(self):
        """删除选中"""
        selection = self.tree.selection()
        for item_id in reversed(selection):
            index = self.tree.index(item_id)
            del self.video_items[index]
        self._refresh_tree()
        self._update_list_video_info()

    def _clear_list(self):
        """清空列表"""
        self.video_items.clear()
        self._refresh_tree()
        self._update_list_video_info()

    def _select_output_dir(self):
        """选择输出目录"""
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.output_dir.set(dir_path)

    def _select_custom_audio(self):
        """选择自定义音频文件"""
        file_path = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=[
                ("音频文件", "*.mp3 *.wav *.aac *.m4a *.flac *.ogg"),
                ("视频文件", "*.mp4 *.avi *.mkv *.mov"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.custom_audio_path.set(file_path)
            self.audio_source.set("custom")

    def _on_naming_change(self, event=None):
        """命名规则改变"""
        rule = self.naming_combo.get()
        self.prefix_entry.config(state='normal' if rule == "自定义前缀_序号" else 'disabled')
        self._update_naming_preview()

    def _update_naming_preview(self):
        """更新命名预览"""
        rule = self.naming_combo.get()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if rule == "时间戳":
            preview = f"{timestamp}_001.mp4"
        elif rule == "原文件名_merged":
            preview = "example_merged.mp4"
        elif rule == "自定义前缀_序号":
            prefix = self.custom_prefix.get() or "video"
            preview = f"{prefix}_001.mp4"
        else:
            preview = f"example_{timestamp}.mp4"
        self.naming_preview_var.set(f"示例: {preview}")

    def _generate_output_filename(self, original_name: str, index: int) -> str:
        """生成输出文件名"""
        rule = self.naming_combo.get()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if rule == "时间戳":
            return f"{timestamp}_{index:03d}.mp4"
        elif rule == "原文件名_merged":
            return f"{original_name}_merged.mp4"
        elif rule == "自定义前缀_序号":
            prefix = self.custom_prefix.get() or "video"
            return f"{prefix}_{index:03d}.mp4"
        else:
            return f"{original_name}_{timestamp}.mp4"

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
                    list_scale_mode=self.list_scale_mode.get()
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

    def _on_processing_complete(self, results, success_count, total_tasks, stopped=False):
        """处理完成后的回调"""
        self.is_processing = False
        self.processing_stopped = False
        self.start_btn.config(state='normal', text="开始处理")
        self.stop_btn.config(state='disabled')
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

    def run(self):
        """运行主循环"""
        self.root.mainloop()


# 为了兼容性，保留 MainWindow 别名
MainWindow = VideoSplitApp
