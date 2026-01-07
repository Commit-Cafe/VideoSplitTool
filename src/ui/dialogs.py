"""
对话框组件
包含视频设置对话框等
"""
import tkinter as tk
from tkinter import ttk
import os
from PIL import Image, ImageTk
from typing import Optional

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
        self.dialog.geometry("480x380")
        self.dialog.minsize(450, 350)
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 数据变量
        self.split_ratio = tk.DoubleVar(value=video_item.split_ratio)

        # 预览相关
        self.preview_image = None
        self.preview_photo = None
        self.canvas_width = 300
        self.canvas_height = 170
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

    def _load_video_preview(self):
        """加载视频预览"""
        temp_dir = get_temp_dir()
        preview_path = os.path.join(temp_dir, "settings_preview.jpg")

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

    def _on_ok(self):
        """确定按钮"""
        self.video_item.split_ratio = self.split_ratio.get()
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
