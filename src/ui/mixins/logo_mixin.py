"""
图片 logo 叠加设置功能 Mixin
处理 logo 文件选择、位置/大小/角度/不透明度调整事件

需要主类提供以下属性:
- logo_enabled: tk.BooleanVar
- logo_path: tk.StringVar
- logo_size_percent: tk.IntVar
- logo_size_label: ttk.Label
- logo_position: tk.StringVar
- logo_position_combo: ttk.Combobox
- logo_margin_x: tk.IntVar
- logo_margin_y: tk.IntVar
- logo_angle: tk.DoubleVar
- logo_opacity: tk.DoubleVar
- logo_opacity_label: ttk.Label
- status_var: tk.StringVar
- _template_initial_dir: str

需要主类提供以下方法:
- _load_dialog_dirs(): 加载目录配置
- _save_dialog_dirs(): 保存目录配置
- _refresh_merge_preview(): 刷新预览
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox

from ...core.image_utils import get_image_info
from ...utils.logger import logger


class LogoMixin:
    """图片 logo 设置功能混入类"""

    def _on_logo_toggle(self):
        """启用/禁用 logo 叠加"""
        enabled = self.logo_enabled.get()
        logger.info(f"图片 logo 叠加 {'启用' if enabled else '禁用'}")
        if enabled and not self.logo_path.get():
            messagebox.showinfo("提示", "请先选择 logo 图片")
            self.logo_enabled.set(False)
            return
        if enabled:
            info = get_image_info(self.logo_path.get())
            if not info:
                messagebox.showerror("错误", f"无法读取 logo 图片: {self.logo_path.get()}")
                self.logo_enabled.set(False)
                return
        self._refresh_merge_preview()

    def _select_logo_image(self):
        """选择 logo 图片"""
        self._load_dialog_dirs()
        file_path = filedialog.askopenfilename(
            title="选择 logo 图片",
            initialdir=self._template_initial_dir,
            filetypes=[
                ("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                ("PNG 文件", "*.png"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.logo_path.set(file_path)
            self._template_initial_dir = os.path.dirname(file_path)
            self._save_dialog_dirs()
            info = get_image_info(file_path)
            if info:
                self.status_var.set(
                    f"已选择 logo: {os.path.basename(file_path)} "
                    f"({info.width}x{info.height}{', 含透明通道' if info.has_alpha else ''})"
                )
            self.logo_enabled.set(True)
            self._refresh_merge_preview()

    def _on_logo_size_change(self, value):
        """大小滑块变化"""
        try:
            v = int(float(value))
            self.logo_size_label.config(text=f"{v}%")
        except (ValueError, tk.TclError):
            pass

    def _on_logo_x_change(self, value):
        """X 中心百分比滑块变化"""
        try:
            v = int(float(value))
            if hasattr(self, 'logo_x_label'):
                self.logo_x_label.config(text=f"{v}%")
        except (ValueError, tk.TclError):
            pass

    def _on_logo_y_change(self, value):
        """Y 中心百分比滑块变化"""
        try:
            v = int(float(value))
            if hasattr(self, 'logo_y_label'):
                self.logo_y_label.config(text=f"{v}%")
        except (ValueError, tk.TclError):
            pass

    def _on_logo_opacity_change(self, value):
        """不透明度滑块变化"""
        try:
            v = int(float(value))
            self.logo_opacity_label.config(text=f"{v}%")
        except (ValueError, tk.TclError):
            pass

    def _on_logo_change(self, *_args):
        """任何 logo 参数变化时刷新预览"""
        try:
            self._refresh_merge_preview()
        except Exception:
            pass
