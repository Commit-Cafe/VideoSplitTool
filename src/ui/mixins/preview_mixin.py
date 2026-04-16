"""
预览渲染功能 Mixin
处理模板视频预览、拼接预览、分割线绘制等
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageTk, ImageDraw

from ...utils.logger import logger
from ...utils.file_utils import get_temp_dir
from ...core.ffmpeg_utils import FFmpegHelper


def get_video_info(video_path):
    """获取视频信息的辅助函数"""
    info = FFmpegHelper.get_video_info(video_path)
    if info:
        return info.to_dict()
    return None


class PreviewMixin:
    """预览渲染功能混入类

    需要主类提供以下属性：
    - template_video: tk.StringVar
    - video_items: list
    - preview_video_combo: ttk.Combobox
    - global_cover_type: tk.StringVar
    - global_cover_frame_time: tk.DoubleVar
    - merge_preview_canvas: tk.Canvas
    - merge_preview_photo: ImageTk.PhotoImage
    - merge_preview_image: PIL.Image
    - merge_preview_var: tk.StringVar
    - preview_canvas: tk.Canvas
    - preview_image, preview_photo: PIL.Image / ImageTk.PhotoImage
    - canvas_width, canvas_height: int
    - split_ratio: tk.DoubleVar
    - split_mode: tk.StringVar
    - output_ratio: tk.DoubleVar
    - output_ratio_enabled: tk.BooleanVar
    - position_order: tk.StringVar
    - template_scale_mode, list_scale_mode: tk.StringVar
    - template_scale_percent, list_scale_percent: tk.IntVar
    - divider_enabled: tk.BooleanVar
    - divider_curve_points: list
    - divider_width: tk.IntVar
    - divider_color: tk.StringVar
    - ratio_label: ttk.Label
    - dragging: bool
    - _preview_update_job: int (after job id)
    - root: tk.Tk

    需要主类提供以下方法：
    - _calculate_bezier_curve(): 计算贝塞尔曲线
    - _on_output_ratio_toggle(): 输出比例切换
    - _on_output_ratio_change(): 输出比例变化
    """

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

        # 获取当前封面类型和处理模式
        cover_type = self.global_cover_type.get()
        is_overlay_mode = hasattr(self, 'process_mode') and self.process_mode.get() == "overlay"

        try:
            temp_dir = get_temp_dir()
            frame_time = self.global_cover_frame_time.get()

            # 如果没有列表视频，显示提示
            if not list_video_path:
                canvas.delete("all")
                canvas.create_text(
                    canvas_w // 2, canvas_h // 2,
                    text="请添加列表视频", fill='#f66', font=('Arial', 10)
                )
                return

            # 提取模板帧
            template_frame_path = os.path.join(temp_dir, "preview_template.jpg")
            if not FFmpegHelper.extract_frame(template_path, template_frame_path, frame_time):
                raise Exception("无法提取模板帧")
            template_img = Image.open(template_frame_path)

            # 提取列表帧
            list_frame_path = os.path.join(temp_dir, "preview_list.jpg")
            if not FFmpegHelper.extract_frame(list_video_path, list_frame_path, frame_time):
                raise Exception("无法提取列表帧")
            list_img = Image.open(list_frame_path)

            # 叠加模式下，始终显示叠加预览效果
            if is_overlay_mode:
                # 叠加模式：模拟叠加效果
                merged_img = self._simulate_merge(template_img, list_img)
                merged_img.thumbnail((canvas_w - 10, canvas_h - 10), Image.Resampling.LANCZOS)
                self.merge_preview_image = merged_img
                self.merge_preview_photo = ImageTk.PhotoImage(merged_img)
                self._draw_merge_preview()
                self.merge_preview_var.set("预览: 叠加效果")
                return

            # 分割拼接模式下，根据封面类型决定显示内容
            if cover_type == "template":
                # 模板帧 - 显示模板视频
                template_img.thumbnail((canvas_w - 20, canvas_h - 20), Image.Resampling.LANCZOS)
                self.merge_preview_image = template_img
                self.merge_preview_photo = ImageTk.PhotoImage(template_img)
                self._draw_merge_preview()
                self.merge_preview_var.set("预览: 模板视频帧")
                return

            elif cover_type == "list":
                # 列表帧 - 显示列表视频
                list_img.thumbnail((canvas_w - 20, canvas_h - 20), Image.Resampling.LANCZOS)
                self.merge_preview_image = list_img
                self.merge_preview_photo = ImageTk.PhotoImage(list_img)
                self._draw_merge_preview()
                self.merge_preview_var.set("预览: 列表视频帧")
                return

            # 其他情况（merged、none、image等）显示拼接预览
            # 提取模板帧
            template_frame_path = os.path.join(temp_dir, "preview_template.jpg")
            if not FFmpegHelper.extract_frame(template_path, template_frame_path, frame_time):
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
            if not FFmpegHelper.extract_frame(list_video_path, list_frame_path, frame_time):
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
        """模拟拼接效果（用PIL实现，支持缩放模式和曲线分界线）"""
        # 叠加模式：前景居中叠加在背景上
        if hasattr(self, 'process_mode') and self.process_mode.get() == "overlay":
            return self._simulate_overlay(template_img, list_img)
        split_ratio = self.split_ratio.get()
        output_ratio = self.output_ratio.get() if self.output_ratio_enabled.get() else 0.5
        is_horizontal = self.split_mode.get() == "horizontal"
        is_template_first = self.position_order.get() == "template_first"

        # 获取缩放模式
        template_scale_mode = self.template_scale_mode.get()
        list_scale_mode = self.list_scale_mode.get()

        # 目标尺寸（使用模板尺寸）
        out_w, out_h = template_img.size

        # 如果启用了曲线分界线，使用蒙版混合
        if self.divider_enabled.get() and self.divider_curve_points:
            return self._simulate_merge_with_curve(template_img, list_img, out_w, out_h,
                                                    template_scale_mode, list_scale_mode,
                                                    is_template_first)

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

    def _simulate_overlay(self, template_img, list_img):
        """模拟叠加效果 - 前景视频（模板）居中叠加在背景视频（列表）上"""
        template_scale_mode = self.template_scale_mode.get()
        list_scale_mode = self.list_scale_mode.get()

        out_w, out_h = list_img.size

        # 缩放背景（列表视频）
        bg = self._scale_image_with_mode(list_img, out_w, out_h, list_scale_mode)
        # 缩放前景（模板视频）
        fg = self._scale_image_with_mode(template_img, out_w, out_h, template_scale_mode)

        # 如果前景有透明通道，使用 alpha composite
        if fg.mode == 'RGBA':
            bg_rgba = bg.convert('RGBA')
            merged = Image.alpha_composite(bg_rgba, fg)
            return merged.convert('RGB')
        else:
            # 无透明通道，直接居中粘贴
            merged = bg.copy()
            paste_x = (out_w - fg.width) // 2
            paste_y = (out_h - fg.height) // 2
            merged.paste(fg, (paste_x, paste_y))
            return merged

    def _simulate_merge_with_curve(self, template_img, list_img, out_w, out_h,
                                    template_scale_mode, list_scale_mode, is_template_first):
        """使用曲线蒙版模拟拼接效果（带边缘平滑处理）"""
        from PIL import ImageFilter

        # 缩放两个图片到输出尺寸
        template_scaled = self._scale_image_with_mode(template_img, out_w, out_h, template_scale_mode)
        list_scaled = self._scale_image_with_mode(list_img, out_w, out_h, list_scale_mode)

        mode = self.split_mode.get()
        points = self.divider_curve_points

        # 使用超采样抗锯齿：先创建2倍大小的蒙版
        scale_factor = 2
        large_w = out_w * scale_factor
        large_h = out_h * scale_factor

        mask_large = Image.new('L', (large_w, large_h), 0)
        draw = ImageDraw.Draw(mask_large)

        # 计算放大后的曲线点
        bezier_points_large = self._calculate_bezier_curve(points, large_w, large_h, mode)

        if mode == "horizontal":
            # 水平分割：曲线左侧为白色
            polygon_points = [(0, 0)]
            polygon_points.extend(bezier_points_large)
            polygon_points.append((0, large_h))
            draw.polygon(polygon_points, fill=255)
        else:
            # 垂直分割：曲线上方为白色
            polygon_points = [(0, 0)]
            polygon_points.extend(bezier_points_large)
            polygon_points.append((large_w, 0))
            draw.polygon(polygon_points, fill=255)

        # 缩小到目标尺寸（自带抗锯齿效果）
        mask = mask_large.resize((out_w, out_h), Image.Resampling.LANCZOS)

        # 应用边缘模糊以消除硬边缘（与导出一致）
        edge_blur = 3
        mask = mask.filter(ImageFilter.GaussianBlur(radius=edge_blur))

        # 确定前景和背景
        if is_template_first:
            fg_img = template_scaled
            bg_img = list_scaled
        else:
            fg_img = list_scaled
            bg_img = template_scaled

        # 使用蒙版混合图像
        merged = Image.composite(fg_img, bg_img, mask)

        # 绘制分界线（如果宽度>0）
        if self.divider_width.get() > 0:
            # 计算正常尺寸的曲线点用于绘制分界线
            bezier_points = self._calculate_bezier_curve(points, out_w, out_h, mode)
            draw = ImageDraw.Draw(merged)
            line_points = list(bezier_points)
            if len(line_points) >= 2:
                draw.line(line_points, fill=self.divider_color.get(), width=self.divider_width.get())

        return merged

    def _load_preview(self, video_path):
        """加载预览"""
        from ...utils.format_utils import format_video_info

        temp_dir = get_temp_dir()
        preview_path = os.path.join(temp_dir, "preview.jpg")

        if FFmpegHelper.extract_frame(video_path, preview_path):
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
                    text="A", fill='black', font=('Arial', 12, 'bold')
                )
                self.preview_canvas.create_text(
                    x + int(self.preview_image.width * (1 + ratio) / 2), y + 12,
                    text="B", fill='black', font=('Arial', 12, 'bold')
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
                    text="A", fill='black', font=('Arial', 12, 'bold')
                )
                self.preview_canvas.create_text(
                    x + self.preview_image.width // 2,
                    y + int(self.preview_image.height * (1 + ratio) / 2),
                    text="B", fill='black', font=('Arial', 12, 'bold')
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
        """拼接预览画布滚轮事件 - 调整输出比例（仅在启用时生效）"""
        # 只有在自定义比例已启用时才响应滚轮
        if not self.output_ratio_enabled.get():
            return

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
            if not FFmpegHelper.extract_frame(template_path, template_frame_path, frame_time):
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
                if not FFmpegHelper.extract_frame(list_video_path, list_frame_path, frame_time):
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

        ttk.Label(frame, text="请输入缩放百分比 (50-200):").pack(pady=(0, 10))

        percent_var = tk.IntVar(value=current_percent)
        percent_entry = ttk.Entry(frame, textvariable=percent_var, width=10)
        percent_entry.pack()

        def apply():
            try:
                value = percent_var.get()
                if 50 <= value <= 200:
                    if area_type == "template":
                        self.template_scale_mode.set("custom")
                        self.template_scale_percent.set(value)
                    else:
                        self.list_scale_mode.set("custom")
                        self.list_scale_percent.set(value)
                    self._refresh_merge_preview()
                    dialog.destroy()
                else:
                    messagebox.showwarning("警告", "请输入50-200之间的数值")
            except Exception:
                messagebox.showwarning("警告", "请输入有效的数字")

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="确定", command=apply).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _set_scale_mode(self, area_type, mode):
        """设置缩放模式"""
        if area_type == "template":
            self.template_scale_mode.set(mode)
        else:
            self.list_scale_mode.set(mode)
        self._refresh_merge_preview()
        self.status_var.set(f"已设置{area_type}缩放模式为: {mode}")
