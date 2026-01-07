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
        preview_frame = ttk.LabelFrame(parent, text="预览", padding="5")
        preview_frame.pack(fill=tk.X, pady=3)

        # 分割方式选项
        split_option_frame = ttk.Frame(preview_frame)
        split_option_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(split_option_frame, text="分割方式:").pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(
            split_option_frame, text="左右分割", variable=self.split_mode,
            value="horizontal", command=self._update_preview
        ).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(
            split_option_frame, text="上下分割", variable=self.split_mode,
            value="vertical", command=self._update_preview
        ).pack(side=tk.LEFT, padx=10)

        # 预览画布区域
        canvas_container = ttk.Frame(preview_frame)
        canvas_container.pack(fill=tk.BOTH, expand=True, pady=3)

        # 左侧：模板分割预览
        left_preview = ttk.Frame(canvas_container)
        left_preview.pack(side=tk.LEFT, padx=(10, 30))
        ttk.Label(left_preview, text="模板分割（拖拽调整）", font=('Arial', 9)).pack()
        self.preview_canvas = tk.Canvas(
            left_preview, width=self.canvas_width, height=self.canvas_height,
            bg='#333333', highlightthickness=1, highlightbackground='#666666'
        )
        self.preview_canvas.pack(pady=3)
        self.preview_canvas.bind('<Button-1>', self._on_canvas_click)
        self.preview_canvas.bind('<B1-Motion>', self._on_canvas_drag)
        self.preview_canvas.bind('<ButtonRelease-1>', self._on_canvas_release)

        # 右侧：拼接效果预览
        right_preview = ttk.Frame(canvas_container)
        right_preview.pack(side=tk.LEFT, padx=(30, 10), expand=True)
        ttk.Label(right_preview, text="拼接效果示意", font=('Arial', 9)).pack()
        self.merge_preview_canvas = tk.Canvas(
            right_preview, width=220, height=self.canvas_height,
            highlightthickness=1, highlightbackground='#cccccc'
        )
        self.merge_preview_canvas.pack(pady=3)

        # 分割位置滑块
        ratio_frame = ttk.Frame(preview_frame)
        ratio_frame.pack(fill=tk.X, pady=3)
        ttk.Label(ratio_frame, text="分割位置:").pack(side=tk.LEFT, padx=3)
        self.ratio_scale = ttk.Scale(
            ratio_frame, from_=0.1, to=0.9,
            variable=self.split_ratio, orient=tk.HORIZONTAL,
            command=self._on_ratio_change
        )
        self.ratio_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self.ratio_label = ttk.Label(ratio_frame, text="50%", width=5)
        self.ratio_label.pack(side=tk.LEFT, padx=3)

    def _create_list_section(self, parent):
        """创建视频列表区域"""
        list_frame = ttk.LabelFrame(parent, text="视频列表 (C/D) - 双击编辑设置", padding="5")
        list_frame.pack(fill=tk.X, pady=3)

        tree_container = ttk.Frame(list_frame)
        tree_container.pack(fill=tk.X, pady=3)

        columns = ('name', 'split', 'scale', 'cover')
        self.tree = ttk.Treeview(tree_container, columns=columns, show='headings', height=5)
        self.tree.heading('name', text='文件名')
        self.tree.heading('split', text='分割')
        self.tree.heading('scale', text='缩放')
        self.tree.heading('cover', text='封面')

        self.tree.column('name', width=280, minwidth=150)
        self.tree.column('split', width=50, anchor='center', minwidth=50)
        self.tree.column('scale', width=50, anchor='center', minwidth=50)
        self.tree.column('cover', width=60, anchor='center', minwidth=50)

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
        """创建拼接设置区域"""
        merge_frame = ttk.LabelFrame(parent, text="拼接设置", padding="5")
        merge_frame.pack(fill=tk.X, pady=3)

        merge_inner = ttk.Frame(merge_frame)
        merge_inner.pack(fill=tk.X, pady=2)

        ttk.Label(merge_inner, text="模板:").grid(row=0, column=0, padx=3, sticky='w')
        self.check_a = ttk.Checkbutton(
            merge_inner, text="A(左/上)", variable=self.use_part_a,
            command=self._on_merge_change
        )
        self.check_a.grid(row=0, column=1, padx=5)
        self.check_b = ttk.Checkbutton(
            merge_inner, text="B(右/下)", variable=self.use_part_b,
            command=self._on_merge_change
        )
        self.check_b.grid(row=0, column=2, padx=5)

        ttk.Label(merge_inner, text="列表:").grid(row=0, column=3, padx=(15, 3), sticky='w')
        self.check_c = ttk.Checkbutton(
            merge_inner, text="C(左/上)", variable=self.use_part_c,
            command=self._on_merge_change
        )
        self.check_c.grid(row=0, column=4, padx=5)
        self.check_d = ttk.Checkbutton(
            merge_inner, text="D(右/下)", variable=self.use_part_d,
            command=self._on_merge_change
        )
        self.check_d.grid(row=0, column=5, padx=5)

        # 位置顺序
        order_frame = ttk.Frame(merge_frame)
        order_frame.pack(fill=tk.X, pady=2)
        ttk.Label(order_frame, text="位置顺序:").pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(
            order_frame, text="模板视频在左/上", variable=self.position_order,
            value="template_first", command=self._on_merge_change
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            order_frame, text="列表视频在左/上", variable=self.position_order,
            value="list_first", command=self._on_merge_change
        ).pack(side=tk.LEFT, padx=5)

        self.merge_preview_var = tk.StringVar(value="")
        ttk.Label(merge_frame, textvariable=self.merge_preview_var, foreground='blue').pack(
            anchor=tk.W, padx=5, pady=2
        )

        self.split_mode.trace_add('write', lambda *args: self._on_merge_change())

    def _create_output_size_section(self, parent):
        """创建输出尺寸设置区域"""
        output_size_frame = ttk.LabelFrame(parent, text="输出尺寸", padding="5")
        output_size_frame.pack(fill=tk.X, pady=3)

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
            split_str, scale_str, cover_str = video_item.get_summary()
            self.tree.insert('', tk.END, values=(video_item.name, split_str, scale_str, cover_str))

    def _on_merge_change(self):
        """当拼接部分勾选变化时更新预览说明"""
        a = self.use_part_a.get()
        b = self.use_part_b.get()
        c = self.use_part_c.get()
        d = self.use_part_d.get()

        mode = self.split_mode.get()
        a_name = "左" if mode == "horizontal" else "上"
        b_name = "右" if mode == "horizontal" else "下"

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
        """绘制拼接效果示意图"""
        canvas = self.merge_preview_canvas
        canvas.delete("all")

        w = 200
        h = self.canvas_height

        mode = self.split_mode.get()
        is_template_first = self.position_order.get() == "template_first"

        template_color = "#4A90D9"
        list_color = "#E8A838"
        template_text = "模板"
        list_text = "列表"

        padding = 10
        preview_w = w - 2 * padding
        preview_h = h - 2 * padding

        if mode == "horizontal":
            half_w = preview_w // 2
            if is_template_first:
                canvas.create_rectangle(
                    padding, padding, padding + half_w, padding + preview_h,
                    fill=template_color, outline="#333"
                )
                canvas.create_text(
                    padding + half_w // 2, padding + preview_h // 2,
                    text=template_text, fill="white", font=('Arial', 10, 'bold')
                )
                canvas.create_rectangle(
                    padding + half_w, padding, padding + preview_w, padding + preview_h,
                    fill=list_color, outline="#333"
                )
                canvas.create_text(
                    padding + half_w + half_w // 2, padding + preview_h // 2,
                    text=list_text, fill="white", font=('Arial', 10, 'bold')
                )
            else:
                canvas.create_rectangle(
                    padding, padding, padding + half_w, padding + preview_h,
                    fill=list_color, outline="#333"
                )
                canvas.create_text(
                    padding + half_w // 2, padding + preview_h // 2,
                    text=list_text, fill="white", font=('Arial', 10, 'bold')
                )
                canvas.create_rectangle(
                    padding + half_w, padding, padding + preview_w, padding + preview_h,
                    fill=template_color, outline="#333"
                )
                canvas.create_text(
                    padding + half_w + half_w // 2, padding + preview_h // 2,
                    text=template_text, fill="white", font=('Arial', 10, 'bold')
                )
        else:
            half_h = preview_h // 2
            if is_template_first:
                canvas.create_rectangle(
                    padding, padding, padding + preview_w, padding + half_h,
                    fill=template_color, outline="#333"
                )
                canvas.create_text(
                    padding + preview_w // 2, padding + half_h // 2,
                    text=template_text, fill="white", font=('Arial', 10, 'bold')
                )
                canvas.create_rectangle(
                    padding, padding + half_h, padding + preview_w, padding + preview_h,
                    fill=list_color, outline="#333"
                )
                canvas.create_text(
                    padding + preview_w // 2, padding + half_h + half_h // 2,
                    text=list_text, fill="white", font=('Arial', 10, 'bold')
                )
            else:
                canvas.create_rectangle(
                    padding, padding, padding + preview_w, padding + half_h,
                    fill=list_color, outline="#333"
                )
                canvas.create_text(
                    padding + preview_w // 2, padding + half_h // 2,
                    text=list_text, fill="white", font=('Arial', 10, 'bold')
                )
                canvas.create_rectangle(
                    padding, padding + half_h, padding + preview_w, padding + preview_h,
                    fill=template_color, outline="#333"
                )
                canvas.create_text(
                    padding + preview_w // 2, padding + half_h + half_h // 2,
                    text=template_text, fill="white", font=('Arial', 10, 'bold')
                )

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

        self.is_processing = True
        self.start_btn.config(state='disabled', text="处理中...")
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
                    if video_info:
                        out_width = video_info.get('width', 0)
                        out_height = video_info.get('height', 0)
                    else:
                        out_width = None
                        out_height = None
                    scale_mode = "fit"
                else:
                    out_width = None
                    out_height = None
                    scale_mode = None

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
                    scale_mode=scale_mode
                )

                result_name = f"{video_item.name} ({merge_mode.upper()})"
                results.append({'name': result_name, 'success': result.success, 'error': result.error})
                if result.success:
                    success_count += 1

        self.root.after(0, lambda: self.progress.configure(value=100))
        self.root.after(0, lambda: self.status_var.set(f"处理完成: 成功 {success_count}/{total_tasks}"))
        self.root.after(0, lambda: self._on_processing_complete(results, success_count, total_tasks))

    def _on_processing_complete(self, results, success_count, total_tasks):
        """处理完成后的回调"""
        self.is_processing = False
        self.start_btn.config(state='normal', text="开始处理")
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
