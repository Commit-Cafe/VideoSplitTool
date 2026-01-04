"""
视频分割拼接工具 V2.0 - GUI界面
支持独立视频设置、封面首帧等功能
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import subprocess
import threading
import atexit
from datetime import datetime
from PIL import Image, ImageTk
from utils import check_ffmpeg, extract_frame, get_temp_dir, is_valid_video, get_video_info, format_duration
from video_processor import VideoProcessor, ProcessResult
from temp_manager import global_temp_manager, cleanup_on_exit
from logger import logger, cleanup_old_logs


class VideoItem:
    """视频列表项数据结构"""
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.split_ratio = 0.5          # 分割比例
        self.scale_percent = 100        # 缩放百分比
        self.cover_type = "none"        # 封面类型: none/frame/image
        self.cover_frame_time = 0.0     # 封面帧时间点(秒)
        self.cover_image_path = None    # 外部封面图片路径
        self.cover_duration = 3.0       # 封面显示时长(秒)
        self.cover_frame_source = "template"  # 封面帧来源: template/list

    def get_summary(self):
        """获取设置摘要"""
        cover_str = "无"
        if self.cover_type == "frame":
            cover_str = f"帧{self.cover_duration}s"
        elif self.cover_type == "image":
            cover_str = f"图{self.cover_duration}s"
        return f"{int(self.split_ratio*100)}%", f"{self.scale_percent}%", cover_str


class VideoSettingsDialog:
    """视频设置对话框"""
    def __init__(self, parent, video_item: VideoItem, split_mode: str, template_video: str = None, parent_app=None):
        self.result = None
        self.video_item = video_item
        self.split_mode = split_mode
        self.template_video = template_video  # 模板视频路径
        self.parent_app = parent_app  # 主窗口引用，用于获取merge_mode等参数

        # 创建对话框
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"视频设置 - {video_item.name}")
        self.dialog.geometry("520x750")
        self.dialog.minsize(480, 700)
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
        # 封面帧来源：template=模板视频, list=列表视频
        self.cover_frame_source = tk.StringVar(value=getattr(video_item, 'cover_frame_source', 'template'))

        # 预览相关
        self.preview_image = None
        self.preview_photo = None
        self.canvas_width = 300
        self.canvas_height = 170
        self.video_duration = 0
        self._preview_update_job = None  # 用于防抖的任务ID

        self._create_widgets()
        self._load_video_preview()

        # 居中显示
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ============ 分割设置 ============
        split_mode_text = "左右分割" if self.split_mode == "horizontal" else "上下分割"
        split_frame = ttk.LabelFrame(main_frame, text=f"分割设置（当前: {split_mode_text}）", padding="5")
        split_frame.pack(fill=tk.X, pady=5)

        # 分割模式提示
        if self.split_mode == "horizontal":
            mode_hint = "拖拽红线调整左右分割位置 (C=左, D=右)"
        else:
            mode_hint = "拖拽红线调整上下分割位置 (C=上, D=下)"
        ttk.Label(split_frame, text=mode_hint, foreground='gray').pack(anchor=tk.W, padx=3)

        # 预览画布
        self.preview_canvas = tk.Canvas(split_frame, width=self.canvas_width, height=self.canvas_height,
                                        bg='#333333', highlightthickness=1)
        self.preview_canvas.pack(pady=5)
        self.preview_canvas.bind('<Button-1>', self._on_canvas_click)
        self.preview_canvas.bind('<B1-Motion>', self._on_canvas_drag)

        # 分割比例滑块
        ratio_frame = ttk.Frame(split_frame)
        ratio_frame.pack(fill=tk.X, pady=3)
        ttk.Label(ratio_frame, text="分割位置:").pack(side=tk.LEFT, padx=3)
        self.ratio_scale = ttk.Scale(ratio_frame, from_=0.1, to=0.9,
                                     variable=self.split_ratio, orient=tk.HORIZONTAL,
                                     command=self._on_ratio_change)
        self.ratio_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self.ratio_label = ttk.Label(ratio_frame, text=f"{int(self.split_ratio.get()*100)}%", width=5)
        self.ratio_label.pack(side=tk.LEFT)

        # ============ 缩放设置 ============
        scale_frame = ttk.LabelFrame(main_frame, text="缩放设置", padding="5")
        scale_frame.pack(fill=tk.X, pady=5)

        scale_inner = ttk.Frame(scale_frame)
        scale_inner.pack(fill=tk.X)
        ttk.Label(scale_inner, text="缩放比例:").pack(side=tk.LEFT, padx=3)
        self.scale_spinbox = ttk.Spinbox(scale_inner, from_=50, to=200, width=5,
                                         textvariable=self.scale_percent)
        self.scale_spinbox.pack(side=tk.LEFT, padx=3)
        ttk.Label(scale_inner, text="% (50-200)").pack(side=tk.LEFT)

        # ============ 封面设置 ============
        cover_frame = ttk.LabelFrame(main_frame, text="封面首帧设置", padding="5")
        cover_frame.pack(fill=tk.X, pady=5)

        # 封面类型选择
        ttk.Radiobutton(cover_frame, text="无封面", variable=self.cover_type,
                        value="none", command=self._on_cover_type_change).pack(anchor=tk.W)

        # 从视频选择帧
        frame_radio = ttk.Radiobutton(cover_frame, text="从视频选择帧", variable=self.cover_type,
                                      value="frame", command=self._on_cover_type_change)
        frame_radio.pack(anchor=tk.W)

        self.frame_settings = ttk.Frame(cover_frame)
        self.frame_settings.pack(fill=tk.X, padx=20, pady=2)

        # 帧来源选择
        source_row = ttk.Frame(self.frame_settings)
        source_row.pack(fill=tk.X, pady=2)
        ttk.Label(source_row, text="帧来源:").pack(side=tk.LEFT)
        ttk.Radiobutton(source_row, text="模板视频", variable=self.cover_frame_source,
                        value="template", command=self._on_frame_source_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(source_row, text="列表视频", variable=self.cover_frame_source,
                        value="list", command=self._on_frame_source_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(source_row, text="拼接后视频", variable=self.cover_frame_source,
                        value="merged", command=self._on_frame_source_change).pack(side=tk.LEFT, padx=5)

        # 时间滑块行
        time_row = ttk.Frame(self.frame_settings)
        time_row.pack(fill=tk.X, pady=2)
        ttk.Label(time_row, text="时间点:").pack(side=tk.LEFT)
        self.time_scale = ttk.Scale(time_row, from_=0, to=100,
                                    variable=self.cover_frame_time, orient=tk.HORIZONTAL,
                                    command=self._on_frame_time_change)
        self.time_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self.time_label = ttk.Label(time_row, text="00:00", width=6)
        self.time_label.pack(side=tk.LEFT)

        # 封面帧预览
        preview_row = ttk.Frame(self.frame_settings)
        preview_row.pack(fill=tk.X, pady=5)
        ttk.Label(preview_row, text="预览:").pack(side=tk.LEFT, anchor=tk.N)
        self.cover_preview_canvas = tk.Canvas(preview_row, width=160, height=90,
                                               bg='#333333', highlightthickness=1)
        self.cover_preview_canvas.pack(side=tk.LEFT, padx=5)
        self.cover_preview_photo = None  # 保持引用防止被回收

        # 预览说明和手动刷新按钮
        preview_info = ttk.Frame(preview_row)
        preview_info.pack(side=tk.LEFT, padx=5)
        ttk.Label(preview_info, text="(自动更新)", foreground='gray', font=('Arial', 8)).pack()
        ttk.Button(preview_info, text="手动刷新", command=self._update_cover_preview, width=8).pack(pady=2)

        # 导入图片
        image_radio = ttk.Radiobutton(cover_frame, text="导入图片", variable=self.cover_type,
                                      value="image", command=self._on_cover_type_change)
        image_radio.pack(anchor=tk.W)

        self.image_settings = ttk.Frame(cover_frame)
        self.image_settings.pack(fill=tk.X, padx=20, pady=2)

        self.image_entry = ttk.Entry(self.image_settings, textvariable=self.cover_image_path, width=30)
        self.image_entry.pack(side=tk.LEFT, padx=3)
        ttk.Button(self.image_settings, text="选择", command=self._select_cover_image).pack(side=tk.LEFT)

        # 封面时长
        duration_frame = ttk.Frame(cover_frame)
        duration_frame.pack(fill=tk.X, pady=5)
        ttk.Label(duration_frame, text="封面显示时长:").pack(side=tk.LEFT, padx=3)
        ttk.Spinbox(duration_frame, from_=0.1, to=10, width=6, increment=0.1,
                    textvariable=self.cover_duration, format="%.1f").pack(side=tk.LEFT)
        ttk.Label(duration_frame, text="秒 (0.1-10)").pack(side=tk.LEFT)

        # 初始化封面设置状态
        self._on_cover_type_change()

        # ============ 按钮 ============
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=15)

        # 使用内部frame居中按钮
        btn_inner = ttk.Frame(btn_frame)
        btn_inner.pack(anchor=tk.CENTER)

        ttk.Button(btn_inner, text="确定", command=self._on_ok, width=10).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_inner, text="取消", command=self._on_cancel, width=10).pack(side=tk.LEFT, padx=10)

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

        # 获取视频信息
        info = get_video_info(source_video)
        if info:
            self.video_duration = info.get('duration', 0)
            self.time_scale.configure(to=max(1, self.video_duration))

        if extract_frame(self.video_item.path, preview_path):
            try:
                img = Image.open(preview_path)
                img.thumbnail((self.canvas_width, self.canvas_height), Image.Resampling.LANCZOS)
                self.preview_image = img
                self.preview_photo = ImageTk.PhotoImage(img)
                self._update_preview()
            except (IOError, OSError) as e:
                print(f"加载预览图片失败: {e}")
            except Exception as e:
                print(f"更新预览时发生错误: {e}")

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
                self.preview_canvas.create_line(line_x, y, line_x, y + self.preview_image.height,
                                               fill='red', width=3, dash=(5, 3))
                self.preview_canvas.create_text(x + int(self.preview_image.width * ratio / 2), y + 12,
                                               text="C", fill='white', font=('Arial', 12, 'bold'))
                self.preview_canvas.create_text(x + int(self.preview_image.width * (1 + ratio) / 2), y + 12,
                                               text="D", fill='white', font=('Arial', 12, 'bold'))
            else:
                line_y = y + int(self.preview_image.height * ratio)
                self.preview_canvas.create_line(x, line_y, x + self.preview_image.width, line_y,
                                               fill='red', width=3, dash=(5, 3))
                self.preview_canvas.create_text(x + self.preview_image.width // 2,
                                               y + int(self.preview_image.height * ratio / 2),
                                               text="C", fill='white', font=('Arial', 12, 'bold'))
                self.preview_canvas.create_text(x + self.preview_image.width // 2,
                                               y + int(self.preview_image.height * (1 + ratio) / 2),
                                               text="D", fill='white', font=('Arial', 12, 'bold'))

        self.ratio_label.config(text=f"{int(self.split_ratio.get() * 100)}%")

    def _on_ratio_change(self, value):
        self._update_preview()

    def _on_canvas_click(self, event):
        self._update_ratio_from_mouse(event)

    def _on_canvas_drag(self, event):
        self._update_ratio_from_mouse(event)

    def _update_ratio_from_mouse(self, event):
        if self.preview_image:
            x = (self.canvas_width - self.preview_image.width) // 2
            y = (self.canvas_height - self.preview_image.height) // 2
            if self.split_mode == "horizontal":
                new_ratio = (event.x - x) / self.preview_image.width
            else:
                new_ratio = (event.y - y) / self.preview_image.height
            new_ratio = max(0.1, min(0.9, new_ratio))
            self.split_ratio.set(new_ratio)
            self._update_preview()

    def _on_cover_type_change(self):
        cover_type = self.cover_type.get()
        # 启用/禁用相应设置
        state_frame = 'normal' if cover_type == 'frame' else 'disabled'
        state_image = 'normal' if cover_type == 'image' else 'disabled'

        # 递归设置子控件状态
        def set_children_state(widget, state):
            for child in widget.winfo_children():
                try:
                    child.configure(state=state)
                except tk.TclError:
                    # 某些控件不支持state配置，跳过
                    pass
                except Exception as e:
                    print(f"设置控件状态失败: {e}")
                set_children_state(child, state)

        set_children_state(self.frame_settings, state_frame)
        set_children_state(self.image_settings, state_image)

        # 如果选择了从视频选择帧，自动更新预览
        if cover_type == 'frame':
            self._update_cover_preview()

    def _on_frame_source_change(self):
        """当帧来源改变时，更新时间滑块范围和预览"""
        source = self.cover_frame_source.get()
        if source == "template" and self.template_video:
            video_path = self.template_video
        else:
            video_path = self.video_item.path

        # 更新时间滑块范围
        info = get_video_info(video_path)
        if info:
            duration = info.get('duration', 0)
            self.time_scale.configure(to=max(1, duration))
            # 重置时间点
            self.cover_frame_time.set(0)
            self.time_label.config(text="00:00")

        # 更新预览
        self._update_cover_preview()

    def _on_frame_time_change(self, value):
        time_sec = float(value)
        mins = int(time_sec // 60)
        secs = int(time_sec % 60)
        self.time_label.config(text=f"{mins:02d}:{secs:02d}")

        # 使用防抖机制更新预览，避免滑动时频繁更新
        if hasattr(self, '_preview_update_job') and self._preview_update_job:
            self.dialog.after_cancel(self._preview_update_job)
        # 延迟300ms后更新预览
        self._preview_update_job = self.dialog.after(300, self._update_cover_preview)

    def _update_cover_preview(self):
        """更新封面帧预览"""
        if self.cover_type.get() != 'frame':
            return

        # 根据帧来源选择视频
        source = self.cover_frame_source.get()
        if source == "template" and self.template_video:
            video_path = self.template_video
        elif source == "list":
            video_path = self.video_item.path
        elif source == "merged":
            # 拼接后视频：需要先生成快速拼接预览
            video_path = self._generate_merged_preview()
            if not video_path:
                self._show_cover_preview_error("拼接失败")
                return
        else:
            video_path = self.video_item.path

        time_pos = self.cover_frame_time.get()
        temp_dir = get_temp_dir()
        preview_path = os.path.join(temp_dir, "cover_preview.jpg")

        # 提取指定时间点的帧
        if extract_frame(video_path, preview_path, time_pos):
            try:
                img = Image.open(preview_path)
                # 缩放到预览尺寸
                img.thumbnail((160, 90), Image.Resampling.LANCZOS)
                self.cover_preview_photo = ImageTk.PhotoImage(img)

                # 更新画布
                self.cover_preview_canvas.delete("all")
                x = (160 - img.width) // 2
                y = (90 - img.height) // 2
                self.cover_preview_canvas.create_image(x, y, anchor=tk.NW, image=self.cover_preview_photo)
            except Exception as e:
                self._show_cover_preview_error("加载失败")
        else:
            self._show_cover_preview_error("提取失败")

    def _show_cover_preview_error(self, msg):
        """显示封面预览错误"""
        self.cover_preview_canvas.delete("all")
        self.cover_preview_canvas.create_text(80, 45, text=msg, fill='#888888', font=('Arial', 9))

    def _generate_merged_preview(self):
        """生成拼接后视频的快速预览（用于封面帧选择）"""
        if not self.template_video or not self.parent_app:
            return None

        try:
            from video_processor import VideoProcessor, get_ffmpeg_path
            import subprocess

            temp_dir = get_temp_dir()
            merged_preview_path = os.path.join(temp_dir, "merged_preview.mp4")

            # 检查缓存（避免重复生成）
            if hasattr(self, '_cached_merged_preview') and os.path.exists(self._cached_merged_preview):
                return self._cached_merged_preview

            # 显示提示信息
            self._show_cover_preview_error("正在生成预览...\n(首次需10-20秒)")
            self.dialog.update()

            # 获取主窗口的拼接组合（使用第一个有效组合）
            combinations = self.parent_app._get_merge_combinations()
            if not combinations:
                return None
            merge_mode = combinations[0]  # 使用第一个组合

            # 构建快速拼接命令（只拼接前15秒，使用最快参数）
            ffmpeg = get_ffmpeg_path()
            template_video = self.template_video
            target_video = self.video_item.path
            split_mode = "horizontal" if self.split_mode == "horizontal" else "vertical"
            split_ratio = self.split_ratio.get()

            # 获取视频信息
            from utils import get_video_info
            template_info = get_video_info(template_video)
            if not template_info:
                return None

            out_width = template_info['width']
            out_height = template_info['height']

            # 构建简化的filter（不处理音频，只处理视频，提高速度）
            if split_mode == "horizontal":
                # 左右分割
                template_part_a_width = int(out_width * split_ratio)
                template_part_b_width = out_width - template_part_a_width

                if merge_mode == "a+c":
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_a_width}:{out_height}:0:0[va];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_b_width}:{out_height}:{out_width}-{template_part_b_width}:0[vc];"
                        f"[va][vc]hstack=inputs=2[outv]"
                    )
                elif merge_mode == "a+d":
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_a_width}:{out_height}:0:0[va];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_b_width}:{out_height}:0:0[vd];"
                        f"[va][vd]hstack=inputs=2[outv]"
                    )
                elif merge_mode == "b+c":
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_b_width}:{out_height}:{template_part_a_width}:0[vb];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_a_width}:{out_height}:{out_width}-{template_part_a_width}:0[vc];"
                        f"[vb][vc]hstack=inputs=2[outv]"
                    )
                else:  # b+d
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_b_width}:{out_height}:{template_part_a_width}:0[vb];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={template_part_a_width}:{out_height}:0:0[vd];"
                        f"[vb][vd]hstack=inputs=2[outv]"
                    )
            else:
                # 上下分割
                template_part_a_height = int(out_height * split_ratio)
                template_part_b_height = out_height - template_part_a_height

                if merge_mode == "a+c":
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_a_height}:0:0[va];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_b_height}:0:{out_height}-{template_part_b_height}[vc];"
                        f"[va][vc]vstack=inputs=2[outv]"
                    )
                elif merge_mode == "a+d":
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_a_height}:0:0[va];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_b_height}:0:0[vd];"
                        f"[va][vd]vstack=inputs=2[outv]"
                    )
                elif merge_mode == "b+c":
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_b_height}:0:{template_part_a_height}[vb];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_a_height}:0:{out_height}-{template_part_a_height}[vc];"
                        f"[vb][vc]vstack=inputs=2[outv]"
                    )
                else:  # b+d
                    video_filter = (
                        f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_b_height}:0:{template_part_a_height}[vb];"
                        f"[1:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,crop={out_width}:{template_part_a_height}:0:0[vd];"
                        f"[vb][vd]vstack=inputs=2[outv]"
                    )

            # 快速拼接命令（只生成30秒，使用ultrafast预设）
            cmd = [
                ffmpeg, '-y',
                '-i', template_video,
                '-i', target_video,
                '-filter_complex', video_filter,
                '-map', '[outv]',
                '-t', '30',  # 生成30秒预览
                '-c:v', 'libx264',
                '-preset', 'ultrafast',  # 最快编码
                '-crf', '28',  # 降低质量以提高速度
                merged_preview_path
            ]

            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

            if result.returncode == 0 and os.path.exists(merged_preview_path):
                # 缓存结果
                self._cached_merged_preview = merged_preview_path
                return merged_preview_path
            else:
                return None

        except Exception as e:
            print(f"生成拼接预览失败: {str(e)}")
            return None

    def _select_cover_image(self):
        file_path = filedialog.askopenfilename(
            title="选择封面图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp"), ("所有文件", "*.*")]
        )
        if file_path:
            self.cover_image_path.set(file_path)

    def _on_ok(self):
        # 保存设置
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
        self.result = False
        self.dialog.destroy()

    def show(self):
        self.dialog.wait_window()
        return self.result


class ScrollableFrame(ttk.Frame):
    """可滚动的Frame容器"""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)


class VideoSplitApp:
    """视频分割拼接应用 V2.0"""

    def __init__(self, root):
        self.root = root
        self.root.title("视频分割拼接工具 V2.0")
        self.root.geometry("750x800")
        self.root.minsize(650, 700)

        # 数据
        self.template_video = tk.StringVar()
        self.video_items = []  # VideoItem列表
        self.split_mode = tk.StringVar(value="horizontal")
        self.output_dir = tk.StringVar()
        self.split_ratio = tk.DoubleVar(value=0.5)
        self.naming_rule = tk.StringVar(value="time")
        self.custom_prefix = tk.StringVar(value="video")

        # 拼接部分勾选
        self.use_part_a = tk.BooleanVar(value=True)   # 模板A部分
        self.use_part_b = tk.BooleanVar(value=False)  # 模板B部分
        self.use_part_c = tk.BooleanVar(value=True)   # 列表C部分
        self.use_part_d = tk.BooleanVar(value=False)  # 列表D部分

        # 位置顺序（模板在前还是列表在前）
        self.position_order = tk.StringVar(value="template_first")  # template_first 或 list_first

        # 音频配置
        self.audio_source = tk.StringVar(value="template")  # template/list/mix/custom/none
        self.custom_audio_path = tk.StringVar()

        # 预览相关
        self.preview_image = None
        self.preview_photo = None
        self.canvas_width = 320
        self.canvas_height = 180
        self.dragging = False

        # 处理器
        self.processor = VideoProcessor()

        if not check_ffmpeg():
            messagebox.showerror("错误", "未检测到FFmpeg，请确保FFmpeg已安装并添加到系统PATH中")

        self._create_widgets()

    def _create_widgets(self):
        scroll_container = ScrollableFrame(self.root)
        scroll_container.pack(fill=tk.BOTH, expand=True)

        main_frame = ttk.Frame(scroll_container.scrollable_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ============ 1. 模板视频选择 ============
        template_frame = ttk.LabelFrame(main_frame, text="模板视频 (A/B)", padding="5")
        template_frame.pack(fill=tk.X, pady=3)

        entry_frame = ttk.Frame(template_frame)
        entry_frame.pack(fill=tk.X)
        ttk.Entry(entry_frame, textvariable=self.template_video).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(entry_frame, text="选择", command=self._select_template, width=8).pack(side=tk.LEFT, padx=5)

        # ============ 2. 分割方式 ============
        split_frame = ttk.LabelFrame(main_frame, text="分割方式", padding="5")
        split_frame.pack(fill=tk.X, pady=3)

        ttk.Radiobutton(split_frame, text="左右分割", variable=self.split_mode,
                        value="horizontal", command=self._update_preview).pack(side=tk.LEFT, padx=15)
        ttk.Radiobutton(split_frame, text="上下分割", variable=self.split_mode,
                        value="vertical", command=self._update_preview).pack(side=tk.LEFT, padx=15)

        # ============ 3. 模板分割预览 ============
        preview_frame = ttk.LabelFrame(main_frame, text="模板分割预览（拖拽调整）", padding="5")
        preview_frame.pack(fill=tk.X, pady=3)

        self.preview_canvas = tk.Canvas(preview_frame, width=self.canvas_width, height=self.canvas_height,
                                        bg='#333333', highlightthickness=1, highlightbackground='#666666')
        self.preview_canvas.pack(pady=3)

        self.preview_canvas.bind('<Button-1>', self._on_canvas_click)
        self.preview_canvas.bind('<B1-Motion>', self._on_canvas_drag)
        self.preview_canvas.bind('<ButtonRelease-1>', self._on_canvas_release)

        ratio_frame = ttk.Frame(preview_frame)
        ratio_frame.pack(fill=tk.X, pady=3)
        ttk.Label(ratio_frame, text="分割位置:").pack(side=tk.LEFT, padx=3)
        self.ratio_scale = ttk.Scale(ratio_frame, from_=0.1, to=0.9,
                                     variable=self.split_ratio, orient=tk.HORIZONTAL,
                                     command=self._on_ratio_change)
        self.ratio_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        self.ratio_label = ttk.Label(ratio_frame, text="50%", width=5)
        self.ratio_label.pack(side=tk.LEFT, padx=3)

        # ============ 4. 视频列表 ============
        list_frame = ttk.LabelFrame(main_frame, text="视频列表 (C/D) - 双击编辑设置", padding="5")
        list_frame.pack(fill=tk.X, pady=3)

        # Treeview容器
        tree_container = ttk.Frame(list_frame)
        tree_container.pack(fill=tk.X, pady=3)

        # 使用Treeview
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

        # 双击编辑
        self.tree.bind('<Double-1>', self._on_tree_double_click)

        # 按钮行1
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="添加", command=self._add_videos, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="编辑", command=self._edit_selected, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="删除", command=self._remove_selected, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="清空", command=self._clear_list, width=8).pack(side=tk.LEFT, padx=2)

        # 按钮行2
        btn_frame2 = ttk.Frame(list_frame)
        btn_frame2.pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame2, text="同步模板分割", command=self._sync_template_ratio, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame2, text="应用到全部", command=self._apply_to_all, width=12).pack(side=tk.LEFT, padx=2)

        # ============ 5. 拼接方式（勾选） ============
        merge_frame = ttk.LabelFrame(main_frame, text="拼接设置", padding="5")
        merge_frame.pack(fill=tk.X, pady=3)

        # 使用grid布局让选项更紧凑
        merge_inner = ttk.Frame(merge_frame)
        merge_inner.pack(fill=tk.X, pady=2)

        ttk.Label(merge_inner, text="模板:").grid(row=0, column=0, padx=3, sticky='w')
        self.check_a = ttk.Checkbutton(merge_inner, text="A(左/上)", variable=self.use_part_a,
                                        command=self._on_merge_change)
        self.check_a.grid(row=0, column=1, padx=5)
        self.check_b = ttk.Checkbutton(merge_inner, text="B(右/下)", variable=self.use_part_b,
                                        command=self._on_merge_change)
        self.check_b.grid(row=0, column=2, padx=5)

        ttk.Label(merge_inner, text="列表:").grid(row=0, column=3, padx=(15,3), sticky='w')
        self.check_c = ttk.Checkbutton(merge_inner, text="C(左/上)", variable=self.use_part_c,
                                        command=self._on_merge_change)
        self.check_c.grid(row=0, column=4, padx=5)
        self.check_d = ttk.Checkbutton(merge_inner, text="D(右/下)", variable=self.use_part_d,
                                        command=self._on_merge_change)
        self.check_d.grid(row=0, column=5, padx=5)

        # 位置顺序
        order_frame = ttk.Frame(merge_frame)
        order_frame.pack(fill=tk.X, pady=2)
        ttk.Label(order_frame, text="位置顺序:").pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(order_frame, text="模板在前 (A+C)", variable=self.position_order,
                        value="template_first", command=self._on_merge_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(order_frame, text="列表在前 (C+A)", variable=self.position_order,
                        value="list_first", command=self._on_merge_change).pack(side=tk.LEFT, padx=5)

        # 拼接预览说明
        self.merge_preview_var = tk.StringVar(value="拼接: A+C")
        ttk.Label(merge_frame, textvariable=self.merge_preview_var, foreground='blue').pack(anchor=tk.W, padx=5, pady=2)

        self.split_mode.trace_add('write', lambda *args: self._on_merge_change())

        # ============ 6. 音频设置 ============
        audio_frame = ttk.LabelFrame(main_frame, text="音频设置", padding="5")
        audio_frame.pack(fill=tk.X, pady=3)

        audio_inner = ttk.Frame(audio_frame)
        audio_inner.pack(fill=tk.X, pady=2)

        ttk.Radiobutton(audio_inner, text="模板音频", variable=self.audio_source,
                        value="template").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(audio_inner, text="列表音频", variable=self.audio_source,
                        value="list").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(audio_inner, text="混合音频", variable=self.audio_source,
                        value="mix").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(audio_inner, text="静音", variable=self.audio_source,
                        value="none").pack(side=tk.LEFT, padx=5)

        # 自定义音频
        custom_audio_frame = ttk.Frame(audio_frame)
        custom_audio_frame.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(custom_audio_frame, text="自定义音频:", variable=self.audio_source,
                        value="custom").pack(side=tk.LEFT, padx=5)
        ttk.Entry(custom_audio_frame, textvariable=self.custom_audio_path, width=30).pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)
        ttk.Button(custom_audio_frame, text="选择", command=self._select_custom_audio, width=6).pack(side=tk.LEFT, padx=3)

        # ============ 输出设置 ============
        output_frame = ttk.LabelFrame(main_frame, text="输出设置", padding="5")
        output_frame.pack(fill=tk.X, pady=3)

        dir_frame = ttk.Frame(output_frame)
        dir_frame.pack(fill=tk.X, pady=2)
        ttk.Label(dir_frame, text="输出目录:").pack(side=tk.LEFT, padx=3)
        ttk.Entry(dir_frame, textvariable=self.output_dir, width=40).pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)
        ttk.Button(dir_frame, text="选择", command=self._select_output_dir).pack(side=tk.LEFT, padx=3)

        naming_frame = ttk.Frame(output_frame)
        naming_frame.pack(fill=tk.X, pady=2)
        ttk.Label(naming_frame, text="命名规则:").pack(side=tk.LEFT, padx=3)

        self.naming_combo = ttk.Combobox(naming_frame, textvariable=self.naming_rule, state="readonly", width=15)
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
        ttk.Label(output_frame, textvariable=self.naming_preview_var, foreground='gray').pack(anchor=tk.W, padx=5, pady=2)
        self._update_naming_preview()

        # ============ 进度条 ============
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=8)
        self.start_btn = ttk.Button(progress_frame, text="开始处理", command=self._start_processing)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.progress = ttk.Progressbar(progress_frame, mode='determinate', length=200)
        self.progress.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        # 处理状态标记
        self.is_processing = False

        # ============ 状态栏 ============
        self.status_var = tk.StringVar(value="准备就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=3)

        self._draw_placeholder()
        self._on_merge_change()  # 初始化拼接预览

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

        # 传递模板视频路径用于封面帧选择
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
                    item.cover_frame_source = source_item.cover_frame_source  # 复制帧来源
                    item.cover_frame_time = source_item.cover_frame_time  # 复制帧时间点
                    # 封面图片路径不复制（每个视频可能需要不同的图片）
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

        parts = []
        if a:
            parts.append(f"A({a_name})")
        if b:
            parts.append(f"B({b_name})")
        if c:
            parts.append(f"C({a_name})")
        if d:
            parts.append(f"D({b_name})")

        if not parts:
            self.merge_preview_var.set("请至少勾选一个部分")
            return

        # 计算输出数量
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

        # 获取位置顺序
        is_template_first = self.position_order.get() == "template_first"
        order_hint = "模板在前" if is_template_first else "列表在前"

        if len(template_parts) == 0 or len(list_parts) == 0:
            if len(template_parts) == 0 and len(list_parts) > 0:
                self.merge_preview_var.set(f"仅使用列表视频: {'+'.join(list_parts)}")
            elif len(list_parts) == 0 and len(template_parts) > 0:
                self.merge_preview_var.set(f"仅使用模板视频: {'+'.join(template_parts)}")
            else:
                self.merge_preview_var.set("请勾选要使用的部分")
        else:
            # 计算组合数
            combinations = len(template_parts) * len(list_parts)
            # 根据位置顺序调整显示
            if is_template_first:
                combo_list = [f"{t}+{l}" for t in template_parts for l in list_parts]
            else:
                combo_list = [f"{l}+{t}" for t in template_parts for l in list_parts]

            if combinations == 1:
                self.merge_preview_var.set(f"拼接方式: {combo_list[0]} ({order_hint})")
            else:
                self.merge_preview_var.set(f"将生成 {combinations} 个视频: {', '.join(combo_list)} ({order_hint})")

    def _sync_template_ratio(self):
        """将模板分割比例同步到所有列表视频"""
        if not self.video_items:
            messagebox.showinfo("提示", "视频列表为空")
            return

        template_ratio = self.split_ratio.get()
        result = messagebox.askyesno("确认",
            f"将模板分割比例 {int(template_ratio*100)}% 同步到所有 {len(self.video_items)} 个列表视频？")

        if result:
            for item in self.video_items:
                item.split_ratio = template_ratio
            self._refresh_tree()
            messagebox.showinfo("完成", f"已将分割比例 {int(template_ratio*100)}% 同步到所有视频")

    def _get_merge_combinations(self):
        """获取所有拼接组合，返回 (内部组合, 显示用组合)"""
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

        # 生成所有组合（内部使用模板+列表的顺序）
        combinations = []
        for t in template_parts:
            for l in list_parts:
                combinations.append(f"{t}+{l}")

        return combinations

    def _select_template(self):
        file_path = filedialog.askopenfilename(
            title="选择模板视频",
            filetypes=[("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"), ("所有文件", "*.*")]
        )
        if file_path:
            self.template_video.set(file_path)
            self._load_preview(file_path)
            if not self.output_dir.get():
                self.output_dir.set(os.path.dirname(file_path))

    def _load_preview(self, video_path):
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
                    self.status_var.set(f"模板视频: {info['width']}x{info['height']}, 时长: {format_duration(info['duration'])}")
            except Exception as e:
                self._draw_placeholder()
        else:
            self._draw_placeholder()

    def _draw_placeholder(self):
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(self.canvas_width // 2, self.canvas_height // 2,
            text="请选择模板视频以预览分割效果", fill='#888888', font=('Arial', 10))

    def _update_preview(self, *args):
        self.preview_canvas.delete("all")
        if self.preview_photo:
            x = (self.canvas_width - self.preview_image.width) // 2
            y = (self.canvas_height - self.preview_image.height) // 2
            self.preview_canvas.create_image(x, y, anchor=tk.NW, image=self.preview_photo)

            ratio = self.split_ratio.get()
            if self.split_mode.get() == "horizontal":
                line_x = x + int(self.preview_image.width * ratio)
                self.preview_canvas.create_line(line_x, y, line_x, y + self.preview_image.height,
                    fill='red', width=3, dash=(5, 3))
                self.preview_canvas.create_text(x + int(self.preview_image.width * ratio / 2), y + 12,
                    text="A", fill='white', font=('Arial', 12, 'bold'))
                self.preview_canvas.create_text(x + int(self.preview_image.width * (1 + ratio) / 2), y + 12,
                    text="B", fill='white', font=('Arial', 12, 'bold'))
            else:
                line_y = y + int(self.preview_image.height * ratio)
                self.preview_canvas.create_line(x, line_y, x + self.preview_image.width, line_y,
                    fill='red', width=3, dash=(5, 3))
                self.preview_canvas.create_text(x + self.preview_image.width // 2,
                    y + int(self.preview_image.height * ratio / 2), text="A", fill='white', font=('Arial', 12, 'bold'))
                self.preview_canvas.create_text(x + self.preview_image.width // 2,
                    y + int(self.preview_image.height * (1 + ratio) / 2), text="B", fill='white', font=('Arial', 12, 'bold'))
        else:
            self._draw_placeholder()

        self.ratio_label.config(text=f"{int(self.split_ratio.get() * 100)}%")

    def _on_ratio_change(self, value):
        self._update_preview()

    def _on_canvas_click(self, event):
        if self.preview_image:
            self.dragging = True

    def _on_canvas_drag(self, event):
        if self.dragging and self.preview_image:
            x = (self.canvas_width - self.preview_image.width) // 2
            y = (self.canvas_height - self.preview_image.height) // 2
            if self.split_mode.get() == "horizontal":
                new_ratio = (event.x - x) / self.preview_image.width
            else:
                new_ratio = (event.y - y) / self.preview_image.height
            new_ratio = max(0.1, min(0.9, new_ratio))
            self.split_ratio.set(new_ratio)
            self._update_preview()

    def _on_canvas_release(self, event):
        self.dragging = False

    def _add_videos(self):
        files = filedialog.askopenfilenames(
            title="选择视频",
            filetypes=[("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"), ("所有文件", "*.*")]
        )
        for f in files:
            if is_valid_video(f) and not any(v.path == f for v in self.video_items):
                video_item = VideoItem(f)
                video_item.split_ratio = self.split_ratio.get()  # 默认使用当前分割比例
                self.video_items.append(video_item)
        self._refresh_tree()

    def _remove_selected(self):
        selection = self.tree.selection()
        for item_id in reversed(selection):
            index = self.tree.index(item_id)
            del self.video_items[index]
        self._refresh_tree()

    def _clear_list(self):
        self.video_items.clear()
        self._refresh_tree()

    def _select_output_dir(self):
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
            self.audio_source.set("custom")  # 自动选择自定义音频选项

    def _on_naming_change(self, event=None):
        rule = self.naming_combo.get()
        self.prefix_entry.config(state='normal' if rule == "自定义前缀_序号" else 'disabled')
        self._update_naming_preview()

    def _update_naming_preview(self):
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
        from error_handler import InputValidator

        # 防止重复点击
        if self.is_processing:
            messagebox.showinfo("提示", "正在处理中，请等待完成")
            return

        # 验证模板视频
        template_path = self.template_video.get()
        if not template_path:
            messagebox.showwarning("警告", "请选择模板视频")
            return

        is_valid, error_msg = InputValidator.validate_video_file(template_path)
        if not is_valid:
            messagebox.showerror("模板视频错误", f"模板视频无效:\n{error_msg}")
            return

        # 验证列表视频
        if not self.video_items:
            messagebox.showwarning("警告", "请添加要处理的视频")
            return

        for i, video_item in enumerate(self.video_items, 1):
            is_valid, error_msg = InputValidator.validate_video_file(video_item.path)
            if not is_valid:
                messagebox.showerror("列表视频错误",
                    f"第{i}个视频 '{video_item.name}' 无效:\n{error_msg}")
                return

        # 验证输出目录
        output_path = self.output_dir.get()
        if not output_path:
            messagebox.showwarning("警告", "请选择输出目录")
            return

        is_valid, error_msg = InputValidator.validate_output_directory(output_path)
        if not is_valid:
            messagebox.showerror("输出目录错误", f"输出目录无效:\n{error_msg}")
            return

        # 获取拼接组合
        combinations = self._get_merge_combinations()
        if not combinations:
            messagebox.showwarning("警告", "请至少勾选模板和列表各一个部分")
            return

        # 设置处理状态
        self.is_processing = True
        self.start_btn.config(state='disabled', text="处理中...")
        self.progress.configure(value=0)

        # 使用非守护线程，确保处理完成
        thread = threading.Thread(target=self._process_videos, args=(combinations,))
        thread.daemon = False  # 非守护线程，程序退出时会等待线程完成
        thread.start()
        logger.info(f"启动处理线程，共 {len(self.video_items)} 个视频，{len(combinations)} 种组合")

    def _process_videos(self, merge_combinations):
        total_tasks = len(self.video_items) * len(merge_combinations)
        success_count = 0
        results = []
        task_index = 0

        for i, video_item in enumerate(self.video_items):
            for merge_mode in merge_combinations:
                task_index += 1
                task_desc = f"{video_item.name} ({merge_mode.upper()})"
                self.root.after(0, lambda v=task_desc: self.status_var.set(f"正在处理: {v}"))
                self.root.after(0, lambda p=(task_index / total_tasks) * 100: self.progress.configure(value=p))

                base_name = os.path.splitext(video_item.name)[0]
                # 如果有多个组合，在文件名中添加组合标识
                if len(merge_combinations) > 1:
                    output_filename = self._generate_output_filename(f"{base_name}_{merge_mode}", task_index)
                else:
                    output_filename = self._generate_output_filename(base_name, i + 1)
                output_path = os.path.join(self.output_dir.get(), output_filename)

                def progress_callback(progress, message):
                    overall = ((task_index - 1 + progress) / total_tasks) * 100
                    self.root.after(0, lambda p=overall: self.progress.configure(value=p))
                    self.root.after(0, lambda m=message: self.status_var.set(m))

                self.processor.set_progress_callback(progress_callback)

                # 处理视频 - 传入VideoItem的设置
                # 获取音频配置
                audio_source = self.audio_source.get()
                custom_audio = self.custom_audio_path.get() if audio_source == "custom" else None

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
                    custom_audio_path=custom_audio
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
        # 重置处理状态
        self.is_processing = False
        self.start_btn.config(state='normal', text="开始处理")

        # 显示结果
        self._show_results(results, success_count, total_tasks)

    def _show_results(self, results: list, success_count: int, total: int):
        result_window = tk.Toplevel(self.root)
        result_window.title("处理结果")
        result_window.geometry("500x400")
        result_window.transient(self.root)

        title_text = f"处理完成: 成功 {success_count}/{total}"
        color = 'green' if success_count == total else 'orange'
        ttk.Label(result_window, text=title_text, font=('Arial', 12, 'bold'), foreground=color).pack(pady=10)

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
            text.insert(tk.END, f"{i+1}. {result['name']}\n", 'filename')
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
        output_dir = self.output_dir.get()
        if output_dir and os.path.exists(output_dir):
            if os.name == 'nt':
                os.startfile(output_dir)
            else:
                subprocess.run(['xdg-open', output_dir])


def main():
    # 清理旧的日志和临时文件
    logger.info("=" * 50)
    logger.info("程序启动")
    logger.info("=" * 50)

    cleanup_old_logs(days=7)
    global_temp_manager.cleanup_old_temp_files(days=3)

    # 注册退出清理函数
    atexit.register(cleanup_on_exit)

    # 创建主窗口
    root = tk.Tk()
    app = VideoSplitApp(root)

    # 窗口关闭事件处理
    def on_closing():
        if app.is_processing:
            if messagebox.askokcancel("退出确认",
                "正在处理视频，强制退出可能导致输出文件损坏。\n\n确定要退出吗？"):
                logger.warning("用户强制退出程序（处理进行中）")
                root.destroy()
        else:
            logger.info("用户正常退出程序")
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # 启动主循环
    root.mainloop()
    logger.info("程序已关闭")


if __name__ == "__main__":
    main()
