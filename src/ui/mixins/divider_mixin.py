"""
曲线分界线功能 Mixin
处理曲线分界线的编辑、生成和同步
"""
import os
from tkinter import messagebox

from ...utils.logger import logger
from ...utils.file_utils import get_temp_dir


class DividerMixin:
    """曲线分界线功能混入类

    需要主类提供以下属性：
    - divider_enabled: tk.BooleanVar
    - divider_curve_points: list
    - divider_color: tk.StringVar
    - divider_width: tk.IntVar
    - divider_edit_btn, divider_width_spin, divider_color_btn, divider_sync_btn: UI控件
    - split_mode: tk.StringVar
    - template_width, template_height: int
    - template_video: tk.StringVar
    - video_items: list
    - video_list: list (alias for video_items)
    - _divider_mask_path: str
    - root: tk.Tk

    需要主类提供以下方法：
    - _draw_merge_preview(): 刷新预览
    """

    def _on_divider_toggle(self):
        """切换曲线分界线启用状态"""
        enabled = self.divider_enabled.get()
        state = 'normal' if enabled else 'disabled'
        self.divider_edit_btn.config(state=state)
        self.divider_width_spin.config(state=state)
        self.divider_color_btn.config(state=state)
        self.divider_sync_btn.config(state=state)

        if enabled and not self.divider_curve_points:
            # 初始化默认控制点（直线）
            self._init_default_curve_points()

        self._draw_merge_preview()

    def _init_default_curve_points(self):
        """初始化默认曲线控制点（直线）"""
        mode = self.split_mode.get()
        if mode == "horizontal":
            # 左右分割：竖线，从上到下排列，控制点可左右移动
            self.divider_curve_points = [
                (0.5, 0.0),   # 顶部
                (0.5, 0.5),   # 中间
                (0.5, 1.0)    # 底部
            ]
        else:
            # 上下分割：横线，从左到右排列，控制点可上下移动
            self.divider_curve_points = [
                (0.0, 0.5),   # 左边
                (0.5, 0.5),   # 中间
                (1.0, 0.5)    # 右边
            ]

    def _open_curve_editor(self):
        """打开曲线编辑器对话框"""
        from ..dialogs import CurveEditorDialog

        # 获取当前视频尺寸用于预览
        video_width = self.template_width or 1920
        video_height = self.template_height or 1080

        dialog = CurveEditorDialog(
            self.root,
            curve_points=self.divider_curve_points.copy(),
            split_mode=self.split_mode.get(),
            video_width=video_width,
            video_height=video_height,
            divider_color=self.divider_color.get(),
            divider_width=self.divider_width.get(),
            template_video=self.template_video.get(),
            list_video=self.video_items[0].path if self.video_items else None
        )

        result = dialog.show()
        if result:
            self.divider_curve_points = result['points']
            self._generate_divider_mask()
            self._draw_merge_preview()

    def _select_divider_color(self):
        """选择分界线颜色"""
        from tkinter import colorchooser
        color = colorchooser.askcolor(
            initialcolor=self.divider_color.get(),
            title="选择分界线颜色"
        )
        if color[1]:
            self.divider_color.set(color[1])
            self._draw_merge_preview()

    def _sync_curve_to_all(self):
        """将当前曲线设置同步到所有视频"""
        if not self.divider_curve_points:
            messagebox.showwarning("提示", "请先设置曲线分界线")
            return

        if not self.video_items:
            messagebox.showwarning("提示", "视频列表为空")
            return

        # 复制当前曲线点到所有视频
        curve_copy = [tuple(p) for p in self.divider_curve_points]
        count = 0
        for item in self.video_items:
            item.curve_points = curve_copy.copy()
            count += 1

        messagebox.showinfo("同步完成", f"已将曲线设置同步到 {count} 个视频")
        logger.info(f"曲线设置已同步到 {count} 个视频")

    def _generate_divider_mask(self, curve_points=None, suffix="", edge_blur=3):
        """生成曲线分界线蒙版图片

        Args:
            curve_points: 曲线控制点列表，如果为None则使用全局设置
            suffix: 文件名后缀，用于区分不同视频的蒙版
            edge_blur: 边缘模糊半径（像素），用于消除硬边缘，默认3

        Returns:
            str: 蒙版图片路径，失败返回None
        """
        # 使用传入的曲线点或全局曲线点
        points = curve_points if curve_points is not None else self.divider_curve_points
        if not points:
            return None

        try:
            from PIL import Image, ImageDraw, ImageFilter

            # 使用模板视频尺寸
            width = self.template_width or 1920
            height = self.template_height or 1080

            # 使用超采样抗锯齿：先创建2倍大小的图像，绘制后缩小
            scale_factor = 2
            large_width = width * scale_factor
            large_height = height * scale_factor

            # 创建大尺寸蒙版图片
            mask_large = Image.new('L', (large_width, large_height), 0)
            draw = ImageDraw.Draw(mask_large)

            mode = self.split_mode.get()

            # 计算放大后的曲线点
            bezier_points = self._calculate_bezier_curve(points, large_width, large_height, mode)

            if mode == "horizontal":
                # 水平分割：曲线左侧为白色
                polygon_points = [(0, 0)]  # 左上角
                polygon_points.extend(bezier_points)
                polygon_points.append((0, large_height))  # 左下角
                draw.polygon(polygon_points, fill=255)
            else:
                # 垂直分割：曲线上方为白色
                polygon_points = [(0, 0)]  # 左上角
                polygon_points.extend(bezier_points)
                polygon_points.append((large_width, 0))  # 右上角
                draw.polygon(polygon_points, fill=255)

            # 缩小到目标尺寸（自带抗锯齿效果）
            mask = mask_large.resize((width, height), Image.Resampling.LANCZOS)

            # 应用边缘模糊以消除硬边缘（创建平滑过渡）
            if edge_blur > 0:
                mask = mask.filter(ImageFilter.GaussianBlur(radius=edge_blur))

            # 保存蒙版
            temp_dir = get_temp_dir()
            filename = f"divider_mask{suffix}.png" if suffix else "divider_mask.png"
            mask_path = os.path.join(temp_dir, filename)
            mask.save(mask_path)

            # 如果是全局蒙版（没有传入curve_points），更新缓存路径
            if curve_points is None:
                self._divider_mask_path = mask_path

            logger.info(f"生成分界线蒙版: {mask_path} (边缘模糊: {edge_blur}px)")
            return mask_path

        except Exception as e:
            logger.error(f"生成分界线蒙版失败: {e}")
            return None

    def _calculate_bezier_curve(self, control_points, width, height, mode, num_segments=100):
        """使用Catmull-Rom样条计算平滑曲线上的点

        Args:
            control_points: 归一化坐标的控制点列表 [(x, y), ...]
            width: 输出宽度
            height: 输出高度
            mode: 分割模式 (horizontal/vertical)
            num_segments: 采样点数量

        Returns:
            list: 实际坐标的曲线点列表 [(x, y), ...]
        """
        if len(control_points) < 2:
            return []

        # 将归一化坐标转换为实际坐标
        actual_points = []
        for px, py in control_points:
            x = int(px * width)
            y = int(py * height)
            actual_points.append((x, y))

        # 如果只有2个点，使用线性插值
        if len(actual_points) == 2:
            curve_points = []
            p0, p1 = actual_points[0], actual_points[1]
            for t in range(num_segments + 1):
                t_norm = t / num_segments
                x = int(p0[0] + (p1[0] - p0[0]) * t_norm)
                y = int(p0[1] + (p1[1] - p0[1]) * t_norm)
                curve_points.append((x, y))
            return curve_points

        # 使用Catmull-Rom样条生成平滑曲线
        curve_points = []

        # 扩展控制点列表（首尾各复制一个点以处理边界）
        extended_points = [actual_points[0]] + actual_points + [actual_points[-1]]

        # 每段的采样点数
        segments_per_span = max(10, num_segments // (len(actual_points) - 1))

        for i in range(1, len(extended_points) - 2):
            p0 = extended_points[i - 1]
            p1 = extended_points[i]
            p2 = extended_points[i + 1]
            p3 = extended_points[i + 2]

            for t in range(segments_per_span):
                t_norm = t / segments_per_span

                # Catmull-Rom 样条公式
                t2 = t_norm * t_norm
                t3 = t2 * t_norm

                x = 0.5 * ((2 * p1[0]) +
                          (-p0[0] + p2[0]) * t_norm +
                          (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                          (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)

                y = 0.5 * ((2 * p1[1]) +
                          (-p0[1] + p2[1]) * t_norm +
                          (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                          (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)

                curve_points.append((int(x), int(y)))

        # 添加最后一个点
        curve_points.append(actual_points[-1])

        return curve_points
