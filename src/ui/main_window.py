"""
主窗口组件
视频分割拼接工具的主界面
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import time
from datetime import datetime
from typing import List

# 配置文件路径
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".video_split_tool")
_instance_id = f"{int(time.time() * 1000) % 100000000}"
CONFIG_FILE = os.path.join(CONFIG_DIR, f"settings_{_instance_id}.json")

from ..models.video_item import VideoItem
from ..core.video_processor import VideoProcessor
from ..core.ffmpeg_utils import check_ffmpeg
from ..utils.logger import logger
from ..utils.file_utils import is_valid_video
from .dialogs import VideoSettingsDialog
from .widgets import ScrollableFrame

# 导入功能 Mixins
from .mixins import (
    DividerMixin,
    PreviewMixin,
    DiagramMixin,
    CoverMixin,
    AudioMixin,
    ProcessingMixin,
)


class VideoSplitApp(
    DividerMixin,
    PreviewMixin,
    DiagramMixin,
    CoverMixin,
    AudioMixin,
    ProcessingMixin
):
    """视频分割拼接应用 V2.5.3"""

    VERSION = "2.5.3"

    def __init__(self, root):
        self.root = root
        self.root.title(f"视频分割拼接工具 V{self.VERSION}")
        self.root.geometry("750x800")
        self.root.minsize(650, 700)

        # 数据
        self.template_video = tk.StringVar()
        self.video_items: List[VideoItem] = []
        self.split_mode = tk.StringVar(value="vertical")
        self.output_dir = tk.StringVar()
        self.split_ratio = tk.DoubleVar(value=0.5)
        self.naming_rule = tk.StringVar(value="time")
        self.custom_prefix = tk.StringVar(value="video")

        # 各文件选择对话框的独立初始目录
        self._template_initial_dir = ""  # 模板视频选择目录
        self._list_initial_dir = ""      # 列表视频选择目录
        self._output_initial_dir = ""    # 输出目录选择

        # 加载保存的目录设置
        self._load_dialog_dirs()

        # 处理模式
        self.process_mode = tk.StringVar(value="overlay")  # "split"=分割拼接, "overlay"=视频叠加

        # 拼接部分勾选
        self.use_part_a = tk.BooleanVar(value=False)
        self.use_part_b = tk.BooleanVar(value=True)
        self.use_part_c = tk.BooleanVar(value=True)
        self.use_part_d = tk.BooleanVar(value=False)

        # 位置顺序
        self.position_order = tk.StringVar(value="list_first")

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
        self.audio_source = tk.StringVar(value="list")
        self.custom_audio_path = tk.StringVar()

        # 音量控制 (0-200, 100=原音量)
        self.template_volume = tk.IntVar(value=100)
        self.list_volume = tk.IntVar(value=100)
        self.custom_volume = tk.IntVar(value=100)
        self._audio_player = None  # 音频播放进程

        # 分界线设置
        self.divider_enabled = tk.BooleanVar(value=False)  # 是否启用自定义分界线
        self.divider_color = tk.StringVar(value="#FFFFFF")  # 分界线颜色
        self.divider_width = tk.IntVar(value=2)  # 分界线宽度
        self.divider_curve_points = []  # 曲线控制点列表 [(x1,y1), (x2,y2), ...]
        self._divider_mask_path = None  # 生成的蒙版图片路径

        # 输出尺寸配置
        self.output_size_mode = tk.StringVar(value="list")
        self.output_width = tk.IntVar(value=1920)
        self.output_height = tk.IntVar(value=1080)
        self.scale_mode = tk.StringVar(value="fit")
        self.template_width = 0
        self.template_height = 0

        # 输出时长配置
        self.output_duration_mode = tk.StringVar(value="list")  # list/template

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

    def _load_dialog_dirs(self):
        """从配置文件加载对话框目录"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._template_initial_dir = data.get('template_dir', '')
                    self._list_initial_dir = data.get('list_dir', '')
                    self._output_initial_dir = data.get('output_dir', '')
        except Exception as e:
            logger.warning(f"加载目录配置失败: {e}")

    def _save_dialog_dirs(self):
        """保存对话框目录到配置文件"""
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            data = {
                'template_dir': self._template_initial_dir,
                'list_dir': self._list_initial_dir,
                'output_dir': self._output_initial_dir,
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存目录配置失败: {e}")

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
        self._on_process_mode_change()

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
            ratio_frame, from_=0.0, to=1.0, length=180,
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
        list_frame = ttk.LabelFrame(parent, text="", padding="5")
        list_frame.pack(fill=tk.X, pady=3)

        # 标题行（带数量显示）
        title_frame = ttk.Frame(list_frame)
        title_frame.pack(fill=tk.X, pady=(0, 3))
        self.list_count_label = ttk.Label(
            title_frame, text="视频列表 (C/D) - 已选 0 个 - 双击编辑设置",
            font=('Arial', 9, 'bold')
        )
        self.list_count_label.pack(side=tk.LEFT, padx=5)

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

        # 更新视频数量显示
        self._update_list_count()

    def _create_merge_section(self, parent):
        """创建拼接设置区域（左侧设置 + 右侧预览）"""
        merge_frame = ttk.LabelFrame(parent, text="拼接设置", padding="5")
        merge_frame.pack(fill=tk.X, pady=3)

        # 主容器
        main_container = ttk.Frame(merge_frame)
        main_container.pack(fill=tk.BOTH, expand=True)

        # ========== 左侧：设置区域 ==========
        left_frame = ttk.Frame(main_container)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # --- 处理模式选择 ---
        mode_frame = ttk.Frame(left_frame)
        mode_frame.pack(fill=tk.X, pady=2)
        ttk.Label(mode_frame, text="模式:").pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(
            mode_frame, text="分割拼接", variable=self.process_mode,
            value="split", command=self._on_process_mode_change
        ).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(
            mode_frame, text="视频叠加", variable=self.process_mode,
            value="overlay", command=self._on_process_mode_change
        ).pack(side=tk.LEFT, padx=2)

        # --- 拼接部分选择（分割拼接模式专用）---
        self.split_widgets_frame = ttk.Frame(left_frame)
        self.split_widgets_frame.pack(fill=tk.X, pady=2)
        merge_inner = ttk.Frame(self.split_widgets_frame)
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
        order_frame = ttk.Frame(self.split_widgets_frame)
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
        ratio_frame = ttk.Frame(self.split_widgets_frame)
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

        # --- 曲线分界线设置 ---
        divider_frame = ttk.Frame(self.split_widgets_frame)
        divider_frame.pack(fill=tk.X, pady=2)

        self.divider_check = ttk.Checkbutton(
            divider_frame, text="曲线分界线",
            variable=self.divider_enabled,
            command=self._on_divider_toggle
        )
        self.divider_check.pack(side=tk.LEFT, padx=3)

        self.divider_edit_btn = ttk.Button(
            divider_frame, text="编辑曲线", width=8,
            command=self._open_curve_editor, state='disabled'
        )
        self.divider_edit_btn.pack(side=tk.LEFT, padx=3)

        ttk.Label(divider_frame, text="宽度:").pack(side=tk.LEFT, padx=(8, 2))
        self.divider_width_spin = ttk.Spinbox(
            divider_frame, from_=0, to=20, width=4,
            textvariable=self.divider_width, state='disabled'
        )
        self.divider_width_spin.pack(side=tk.LEFT)

        self.divider_color_btn = ttk.Button(
            divider_frame, text="颜色", width=5,
            command=self._select_divider_color, state='disabled'
        )
        self.divider_color_btn.pack(side=tk.LEFT, padx=3)

        self.divider_sync_btn = ttk.Button(
            divider_frame, text="同步全部", width=7,
            command=self._sync_curve_to_all, state='disabled'
        )
        self.divider_sync_btn.pack(side=tk.LEFT, padx=3)

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
            size_mode_frame, text="跟随列表视频（一对一）", variable=self.output_size_mode,
            value="list", command=self._on_output_size_mode_change
        ).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(
            size_mode_frame, text="跟随模板视频", variable=self.output_size_mode,
            value="template", command=self._on_output_size_mode_change
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
            duration_mode_frame, text="跟随列表视频（一对一）", variable=self.output_duration_mode,
            value="list"
        ).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(
            duration_mode_frame, text="跟随模板视频", variable=self.output_duration_mode,
            value="template"
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
            audio_inner, text="列表音频", variable=self.audio_source, value="list"
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            audio_inner, text="模板音频", variable=self.audio_source, value="template"
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

        # 音量控制区域
        ttk.Separator(audio_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        volume_title_frame = ttk.Frame(audio_frame)
        volume_title_frame.pack(fill=tk.X, pady=2)
        ttk.Label(volume_title_frame, text="音量控制 (0-200%):").pack(side=tk.LEFT, padx=5)

        # 全局音量控制
        global_vol_frame = ttk.Frame(audio_frame)
        global_vol_frame.pack(fill=tk.X, pady=2)
        ttk.Label(global_vol_frame, text="全局音量:", width=10).pack(side=tk.LEFT, padx=5)
        self.global_volume = tk.IntVar(value=100)
        self.global_volume_scale = ttk.Scale(
            global_vol_frame, from_=0, to=200, variable=self.global_volume,
            orient=tk.HORIZONTAL, length=120, command=self._on_global_volume_change
        )
        self.global_volume_scale.pack(side=tk.LEFT, padx=3)
        self.global_volume_label = ttk.Label(global_vol_frame, text="100%", width=5)
        self.global_volume_label.pack(side=tk.LEFT)
        ttk.Button(
            global_vol_frame, text="应用到全部", width=10,
            command=self._apply_global_volume
        ).pack(side=tk.LEFT, padx=5)

        # 模板音频音量
        template_vol_frame = ttk.Frame(audio_frame)
        template_vol_frame.pack(fill=tk.X, pady=2)
        ttk.Label(template_vol_frame, text="模板音量:", width=10).pack(side=tk.LEFT, padx=5)
        self.template_volume_scale = ttk.Scale(
            template_vol_frame, from_=0, to=200, variable=self.template_volume,
            orient=tk.HORIZONTAL, length=120, command=lambda v: self._on_volume_change('template', v)
        )
        self.template_volume_scale.pack(side=tk.LEFT, padx=3)
        self.template_volume_label = ttk.Label(template_vol_frame, text="100%", width=5)
        self.template_volume_label.pack(side=tk.LEFT)
        ttk.Button(
            template_vol_frame, text="试听", width=6,
            command=lambda: self._preview_audio('template')
        ).pack(side=tk.LEFT, padx=3)
        ttk.Button(
            template_vol_frame, text="停止", width=6,
            command=self._stop_audio_preview
        ).pack(side=tk.LEFT)

        # 列表音频音量
        list_vol_frame = ttk.Frame(audio_frame)
        list_vol_frame.pack(fill=tk.X, pady=2)
        ttk.Label(list_vol_frame, text="列表音量:", width=10).pack(side=tk.LEFT, padx=5)
        self.list_volume_scale = ttk.Scale(
            list_vol_frame, from_=0, to=200, variable=self.list_volume,
            orient=tk.HORIZONTAL, length=120, command=lambda v: self._on_volume_change('list', v)
        )
        self.list_volume_scale.pack(side=tk.LEFT, padx=3)
        self.list_volume_label = ttk.Label(list_vol_frame, text="100%", width=5)
        self.list_volume_label.pack(side=tk.LEFT)
        ttk.Button(
            list_vol_frame, text="试听", width=6,
            command=lambda: self._preview_audio('list')
        ).pack(side=tk.LEFT, padx=3)

        # 自定义音频音量
        custom_vol_frame = ttk.Frame(audio_frame)
        custom_vol_frame.pack(fill=tk.X, pady=2)
        ttk.Label(custom_vol_frame, text="自定义音量:", width=10).pack(side=tk.LEFT, padx=5)
        self.custom_volume_scale = ttk.Scale(
            custom_vol_frame, from_=0, to=200, variable=self.custom_volume,
            orient=tk.HORIZONTAL, length=120, command=lambda v: self._on_volume_change('custom', v)
        )
        self.custom_volume_scale.pack(side=tk.LEFT, padx=3)
        self.custom_volume_label = ttk.Label(custom_vol_frame, text="100%", width=5)
        self.custom_volume_label.pack(side=tk.LEFT)
        ttk.Button(
            custom_vol_frame, text="试听", width=6,
            command=lambda: self._preview_audio('custom')
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

        # 更新视频数量显示
        self._update_list_count()

    def _update_list_count(self):
        """更新视频列表数量显示"""
        count = len(self.video_items)
        self.list_count_label.config(text=f"视频列表 (C/D) - 已选 {count} 个 - 双击编辑设置")

    def _on_process_mode_change(self):
        """处理模式切换"""
        is_split = self.process_mode.get() == "split"
        # 显示/隐藏分割拼接相关控件
        if is_split:
            self.split_widgets_frame.pack(fill=tk.X, pady=2, after=self.split_widgets_frame.master.winfo_children()[0])
        else:
            self.split_widgets_frame.pack_forget()
        self._on_merge_change()

    def _on_merge_change(self):
        """当拼接部分勾选变化时更新预览说明"""
        # 叠加模式显示固定提示
        if self.process_mode.get() == "overlay":
            self.merge_preview_var.set("叠加模式: 模板视频在前（前景），列表视频在后（背景）")
            self._draw_merge_preview()
            return
        # 如果分割模式改变且曲线分界线已启用，重置曲线控制点
        if self.divider_enabled.get() and self.divider_curve_points:
            mode = self.split_mode.get()
            # 检查当前曲线是否与模式匹配
            if mode == "horizontal":
                # 左右分割应该是竖线：所有点的y坐标不同
                if len(self.divider_curve_points) >= 2:
                    # 如果第一个和最后一个点的x坐标相同但y不同，说明是竖线，正确
                    first_y = self.divider_curve_points[0][1]
                    last_y = self.divider_curve_points[-1][1]
                    if abs(first_y - last_y) < 0.1:
                        # y坐标相近说明是横线，需要重置为竖线
                        self._init_default_curve_points()
                        self._divider_mask_path = None
            else:
                # 上下分割应该是横线：所有点的x坐标不同
                if len(self.divider_curve_points) >= 2:
                    first_x = self.divider_curve_points[0][0]
                    last_x = self.divider_curve_points[-1][0]
                    if abs(first_x - last_x) < 0.1:
                        # x坐标相近说明是竖线，需要重置为横线
                        self._init_default_curve_points()
                        self._divider_mask_path = None

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

    # 拼接预览相关方法已移至 PreviewMixin
    # 效果示意图相关方法已移至 DiagramMixin
    # 封面设置相关方法已移至 CoverMixin

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
        if self.process_mode.get() == "overlay":
            return ["overlay"]
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
            initialdir=self._template_initial_dir,
            filetypes=[
                ("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.template_video.set(file_path)
            self._template_initial_dir = os.path.dirname(file_path)  # 记住目录
            self._load_preview(file_path)
            if not self.output_dir.get():
                self.output_dir.set(os.path.dirname(file_path))

    # 预览加载和画布交互方法已移至 PreviewMixin

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

    # 曲线分界线相关方法已移至 DividerMixin

    def _add_videos(self):
        """添加视频"""
        files = filedialog.askopenfilenames(
            title="选择视频",
            initialdir=self._list_initial_dir,
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
                # 记住最后一个文件的目录
                self._list_initial_dir = os.path.dirname(f)
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
        dir_path = filedialog.askdirectory(
            title="选择输出目录",
            initialdir=self._output_initial_dir
        )
        if dir_path:
            self.output_dir.set(dir_path)
            self._output_initial_dir = dir_path  # 记住目录

    # 音频相关方法已移至 AudioMixin

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

    # 处理相关方法已移至 ProcessingMixin

    def run(self):
        """运行主循环"""
        self.root.mainloop()


# 为了兼容性，保留 MainWindow 别名
MainWindow = VideoSplitApp
