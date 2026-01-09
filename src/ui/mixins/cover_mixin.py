"""
封面设置功能 Mixin
处理视频封面的类型选择、帧时间设置、图片选择等
"""
import os
import tkinter as tk
from tkinter import messagebox, filedialog

from ...core.ffmpeg_utils import FFmpegHelper


def get_video_info(video_path):
    """获取视频信息的辅助函数"""
    info = FFmpegHelper.get_video_info(video_path)
    if info:
        return info.to_dict()
    return None


class CoverMixin:
    """封面设置功能混入类

    需要主类提供以下属性：
    - global_cover_type: tk.StringVar
    - global_cover_duration: tk.DoubleVar
    - global_cover_image_path: tk.StringVar
    - global_cover_frame_time: tk.DoubleVar
    - cover_time_frame: ttk.Frame
    - cover_type_frame_ref: ttk.Frame
    - cover_time_scale: ttk.Scale
    - cover_time_label: ttk.Label
    - cover_image_btn: ttk.Button
    - template_video: tk.StringVar
    - video_items: list
    - preview_video_combo: ttk.Combobox
    - status_var: tk.StringVar

    需要主类提供以下方法：
    - _refresh_merge_preview(): 刷新预览
    - _refresh_tree(): 刷新列表显示
    """

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
            elif cover_type in ("template", "list", "merged"):
                # 使用全局帧时间，确保预览和导出一致
                video_item.cover_frame_time = self.global_cover_frame_time.get()

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
