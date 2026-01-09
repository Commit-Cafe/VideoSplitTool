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
                    text="C", fill='black', font=('Arial', 12, 'bold')
                )
                self.preview_canvas.create_text(
                    x + int(self.preview_image.width * (1 + ratio) / 2), y + 12,
                    text="D", fill='black', font=('Arial', 12, 'bold')
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
                    text="C", fill='black', font=('Arial', 12, 'bold')
                )
                self.preview_canvas.create_text(
                    x + self.preview_image.width // 2,
                    y + int(self.preview_image.height * (1 + ratio) / 2),
                    text="D", fill='black', font=('Arial', 12, 'bold')
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


class CurveEditorDialog:
    """曲线分界线编辑器对话框"""

    POINT_RADIUS = 8  # 控制点半径
    POINT_COLOR = '#FF4444'  # 控制点颜色
    POINT_HOVER_COLOR = '#FFAA00'  # 悬停时的颜色
    POINT_SELECTED_COLOR = '#00FFFF'  # 选中时的颜色
    CURVE_COLOR = '#00FF00'  # 曲线颜色
    CURVE_WIDTH = 3  # 曲线宽度
    GRID_COLOR = '#404040'  # 网格颜色

    def __init__(self, parent, curve_points: list, split_mode: str,
                 video_width: int, video_height: int,
                 divider_color: str = "#FFFFFF", divider_width: int = 2,
                 template_video: str = None, list_video: str = None):
        self.result = None
        self.curve_points = curve_points if curve_points else []
        self.split_mode = split_mode
        self.video_width = video_width
        self.video_height = video_height
        self.divider_color = divider_color
        self.divider_width = divider_width
        self.template_video = template_video
        self.list_video = list_video

        # 创建对话框 - 大尺寸以便专业剪辑师操作
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("曲线分界线编辑器")
        self.dialog.geometry("1200x900")
        self.dialog.minsize(900, 700)
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 画布尺寸 - 大尺寸高清预览
        self.canvas_width = 960
        self.canvas_height = 540  # 16:9 比例

        # 预览图片
        self.preview_image = None
        self.preview_photo = None
        self.img_x = 0  # 图片在画布上的x偏移
        self.img_y = 0  # 图片在画布上的y偏移
        self.img_scale = 1.0  # 图片缩放比例

        # 拖拽状态
        self.dragging_point_index = None
        self.hover_point_index = None
        self.selected_point_index = None  # 当前选中的控制点（用于键盘微调）
        self.show_grid = True  # 显示网格
        self.fine_tune_step = 0.01  # 微调步长（1%）

        self._create_widgets()
        self._load_preview()
        self._init_default_points()

        # 居中显示
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """创建对话框控件"""
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ===== 底部按钮区域（先pack，确保始终可见）=====
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 5))

        ttk.Separator(btn_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))

        btn_inner = ttk.Frame(btn_frame)
        btn_inner.pack(anchor=tk.CENTER)

        ttk.Button(btn_inner, text="确定", command=self._on_ok, width=12).pack(side=tk.LEFT, padx=15)
        ttk.Button(btn_inner, text="取消", command=self._on_cancel, width=12).pack(side=tk.LEFT, padx=15)

        # ===== 顶部内容区域 =====
        # 顶部提示
        hint_text = "左右分割: 拖动控制点调整曲线（从上到下）" if self.split_mode == "horizontal" else "上下分割: 拖动控制点调整曲线（从左到右）"
        ttk.Label(main_frame, text=hint_text, foreground='#0066cc').pack(anchor=tk.W, pady=(0, 5))

        # 画布区域
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            canvas_frame, width=self.canvas_width, height=self.canvas_height,
            bg='#2a2a2a', highlightthickness=1, highlightbackground='#666'
        )
        self.canvas.pack(pady=5)

        # 绑定鼠标事件
        self.canvas.bind('<Button-1>', self._on_canvas_click)
        self.canvas.bind('<B1-Motion>', self._on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_canvas_release)
        self.canvas.bind('<Motion>', self._on_canvas_motion)
        self.canvas.bind('<Double-Button-1>', self._on_canvas_double_click)
        self.canvas.bind('<Button-3>', self._on_canvas_right_click)

        # 绑定键盘事件（用于微调）
        self.dialog.bind('<Left>', lambda e: self._fine_tune_point(-1, 0))
        self.dialog.bind('<Right>', lambda e: self._fine_tune_point(1, 0))
        self.dialog.bind('<Up>', lambda e: self._fine_tune_point(0, -1))
        self.dialog.bind('<Down>', lambda e: self._fine_tune_point(0, 1))
        self.dialog.bind('<Shift-Left>', lambda e: self._fine_tune_point(-5, 0))
        self.dialog.bind('<Shift-Right>', lambda e: self._fine_tune_point(5, 0))
        self.dialog.bind('<Shift-Up>', lambda e: self._fine_tune_point(0, -5))
        self.dialog.bind('<Shift-Down>', lambda e: self._fine_tune_point(0, 5))
        self.dialog.bind('<Delete>', lambda e: self._delete_selected_point())
        self.dialog.bind('<Escape>', lambda e: self._deselect_point())

        # 控制按钮区域
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill=tk.X, pady=5)

        ttk.Button(ctrl_frame, text="添加控制点", command=self._add_point, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl_frame, text="删除选中点", command=self._remove_selected_point, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl_frame, text="重置直线", command=self._reset_to_line, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl_frame, text="细分平滑", command=self._smooth_curve, width=8).pack(side=tk.LEFT, padx=2)

        # 预设曲线形状
        preset_frame = ttk.Frame(main_frame)
        preset_frame.pack(fill=tk.X, pady=2)
        ttk.Label(preset_frame, text="预设:").pack(side=tk.LEFT, padx=3)
        ttk.Button(preset_frame, text="S曲线", command=lambda: self._apply_preset("s_curve"), width=7).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="波浪", command=lambda: self._apply_preset("wave"), width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="弧形内凹", command=lambda: self._apply_preset("arc_in"), width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="弧形外凸", command=lambda: self._apply_preset("arc_out"), width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="斜线", command=lambda: self._apply_preset("diagonal"), width=6).pack(side=tk.LEFT, padx=2)

        # 精确坐标控制区域
        coord_frame = ttk.Frame(main_frame)
        coord_frame.pack(fill=tk.X, pady=3)

        ttk.Label(coord_frame, text="选中点:").pack(side=tk.LEFT, padx=3)
        self.selected_point_var = tk.StringVar(value="无")
        ttk.Label(coord_frame, textvariable=self.selected_point_var, width=8, foreground='#0066cc').pack(side=tk.LEFT)

        ttk.Label(coord_frame, text="X:").pack(side=tk.LEFT, padx=(10, 2))
        self.coord_x_var = tk.StringVar(value="0.50")
        self.coord_x_entry = ttk.Entry(coord_frame, textvariable=self.coord_x_var, width=8)
        self.coord_x_entry.pack(side=tk.LEFT)
        self.coord_x_entry.bind('<Return>', self._apply_coord_input)

        ttk.Label(coord_frame, text="Y:").pack(side=tk.LEFT, padx=(10, 2))
        self.coord_y_var = tk.StringVar(value="0.50")
        self.coord_y_entry = ttk.Entry(coord_frame, textvariable=self.coord_y_var, width=8)
        self.coord_y_entry.pack(side=tk.LEFT)
        self.coord_y_entry.bind('<Return>', self._apply_coord_input)

        ttk.Button(coord_frame, text="应用", command=self._apply_coord_input, width=5).pack(side=tk.LEFT, padx=5)

        # 网格开关
        self.grid_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(coord_frame, text="网格", variable=self.grid_var,
                       command=self._toggle_grid).pack(side=tk.LEFT, padx=(15, 0))

        # 状态提示
        self.status_var = tk.StringVar(value="点击选中控制点，方向键微调，Shift加速")
        ttk.Label(main_frame, textvariable=self.status_var, foreground='#888').pack(anchor=tk.W, pady=2)

    def _load_preview(self):
        """加载预览图片"""
        video_path = self.template_video or self.list_video
        if not video_path:
            return

        temp_dir = get_temp_dir()
        preview_path = os.path.join(temp_dir, "curve_editor_preview.jpg")

        if extract_frame(video_path, preview_path):
            try:
                img = Image.open(preview_path)

                # 计算缩放比例以适应画布
                scale_w = self.canvas_width / img.width
                scale_h = self.canvas_height / img.height
                self.img_scale = min(scale_w, scale_h) * 0.95  # 留一些边距

                new_width = int(img.width * self.img_scale)
                new_height = int(img.height * self.img_scale)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                self.preview_image = img
                self.preview_photo = ImageTk.PhotoImage(img)

                # 计算图片在画布上的位置
                self.img_x = (self.canvas_width - new_width) // 2
                self.img_y = (self.canvas_height - new_height) // 2

            except Exception as e:
                logger.warning(f"加载曲线编辑器预览失败: {e}")

    def _init_default_points(self):
        """初始化默认控制点"""
        if not self.curve_points:
            if self.split_mode == "horizontal":
                # 水平分割：控制点从上到下排列，x表示分割位置
                self.curve_points = [
                    (0.5, 0.0),   # 顶部
                    (0.5, 0.5),   # 中间
                    (0.5, 1.0)    # 底部
                ]
            else:
                # 垂直分割：控制点从左到右排列，y表示分割位置
                self.curve_points = [
                    (0.0, 0.5),   # 左边
                    (0.5, 0.5),   # 中间
                    (1.0, 0.5)    # 右边
                ]
        self._update_coord_display()  # 初始化坐标显示状态
        self._update_canvas()

    def _update_canvas(self):
        """更新画布"""
        self.canvas.delete("all")

        # 绘制网格
        if self.show_grid and self.preview_image:
            self._draw_grid()

        # 绘制预览图片
        if self.preview_photo:
            self.canvas.create_image(self.img_x, self.img_y, anchor=tk.NW, image=self.preview_photo)

        # 计算曲线点的实际坐标
        canvas_points = self._get_canvas_points()

        if len(canvas_points) >= 2:
            # 绘制曲线
            smooth_points = self._get_smooth_curve_points(canvas_points)
            if len(smooth_points) >= 4:
                self.canvas.create_line(smooth_points, fill=self.CURVE_COLOR, width=self.CURVE_WIDTH, smooth=True)

        # 绘制控制点
        for i, (cx, cy) in enumerate(canvas_points):
            # 确定颜色：选中 > 悬停 > 默认
            if i == self.selected_point_index:
                color = self.POINT_SELECTED_COLOR
                outline = '#FFFFFF'
                width = 3
            elif i == self.hover_point_index:
                color = self.POINT_HOVER_COLOR
                outline = '#FFFFFF'
                width = 2
            else:
                color = self.POINT_COLOR
                outline = '#FFFFFF'
                width = 1

            # 绘制控制点
            self.canvas.create_oval(
                cx - self.POINT_RADIUS, cy - self.POINT_RADIUS,
                cx + self.POINT_RADIUS, cy + self.POINT_RADIUS,
                fill=color, outline=outline, width=width, tags=f"point_{i}"
            )

            # 显示点的序号和坐标
            if i == self.selected_point_index:
                px, py = self.curve_points[i]
                coord_text = f"{i+1}: ({px:.2f}, {py:.2f})"
                self.canvas.create_text(
                    cx, cy - self.POINT_RADIUS - 15,
                    text=coord_text, fill='#00FFFF', font=('Arial', 10, 'bold')
                )
            else:
                self.canvas.create_text(
                    cx, cy - self.POINT_RADIUS - 12,
                    text=str(i + 1), fill='white', font=('Arial', 10)
                )

    def _draw_grid(self):
        """绘制辅助网格"""
        if not self.preview_image:
            return

        img_w = self.preview_image.width
        img_h = self.preview_image.height

        # 绘制10%间隔的网格线
        for i in range(1, 10):
            # 垂直线
            x = self.img_x + int(img_w * i / 10)
            self.canvas.create_line(
                x, self.img_y, x, self.img_y + img_h,
                fill=self.GRID_COLOR, dash=(2, 4)
            )
            # 水平线
            y = self.img_y + int(img_h * i / 10)
            self.canvas.create_line(
                self.img_x, y, self.img_x + img_w, y,
                fill=self.GRID_COLOR, dash=(2, 4)
            )

        # 绘制50%中心线（更明显）
        center_x = self.img_x + img_w // 2
        center_y = self.img_y + img_h // 2
        self.canvas.create_line(
            center_x, self.img_y, center_x, self.img_y + img_h,
            fill='#606060', width=1
        )
        self.canvas.create_line(
            self.img_x, center_y, self.img_x + img_w, center_y,
            fill='#606060', width=1
        )

    def _get_canvas_points(self):
        """将归一化坐标转换为画布坐标"""
        if not self.preview_image:
            return []

        points = []
        for px, py in self.curve_points:
            cx = self.img_x + int(px * self.preview_image.width)
            cy = self.img_y + int(py * self.preview_image.height)
            points.append((cx, cy))
        return points

    def _canvas_to_normalized(self, cx, cy):
        """将画布坐标转换为归一化坐标"""
        if not self.preview_image:
            return 0.5, 0.5

        px = (cx - self.img_x) / self.preview_image.width
        py = (cy - self.img_y) / self.preview_image.height

        # 限制在0-1范围内
        px = max(0.0, min(1.0, px))
        py = max(0.0, min(1.0, py))

        return px, py

    def _get_smooth_curve_points(self, control_points):
        """使用Catmull-Rom样条生成平滑曲线点用于绘制"""
        if len(control_points) < 2:
            return []

        # 如果只有2个点，使用线性插值
        if len(control_points) == 2:
            smooth = []
            p0, p1 = control_points[0], control_points[1]
            for t in range(11):
                t_norm = t / 10.0
                x = p0[0] + (p1[0] - p0[0]) * t_norm
                y = p0[1] + (p1[1] - p0[1]) * t_norm
                smooth.extend([x, y])
            return smooth

        # 使用Catmull-Rom样条生成平滑曲线
        smooth = []

        # 扩展控制点列表（首尾各复制一个点以处理边界）
        extended = [control_points[0]] + list(control_points) + [control_points[-1]]

        segments_per_span = 15  # 每段的采样点数

        for i in range(1, len(extended) - 2):
            p0 = extended[i - 1]
            p1 = extended[i]
            p2 = extended[i + 1]
            p3 = extended[i + 2]

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

                smooth.extend([x, y])

        # 添加最后一个点
        smooth.extend([control_points[-1][0], control_points[-1][1]])

        return smooth

    def _find_point_at(self, x, y):
        """查找指定位置的控制点"""
        canvas_points = self._get_canvas_points()
        for i, (cx, cy) in enumerate(canvas_points):
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if dist <= self.POINT_RADIUS + 5:
                return i
        return None

    def _on_canvas_click(self, event):
        """画布点击"""
        point_idx = self._find_point_at(event.x, event.y)
        if point_idx is not None:
            self.dragging_point_index = point_idx
            self.selected_point_index = point_idx
            self._update_coord_display()
            self.status_var.set(f"选中控制点 {point_idx + 1}，方向键微调")
            self._update_canvas()
        else:
            # 点击空白处取消选中
            self.selected_point_index = None
            self._update_coord_display()
            self._update_canvas()

    def _on_canvas_drag(self, event):
        """画布拖拽"""
        if self.dragging_point_index is not None:
            px, py = self._canvas_to_normalized(event.x, event.y)

            # 允许自由移动（上下左右都可以）
            self.curve_points[self.dragging_point_index] = (px, py)

            self._update_coord_display()  # 实时更新坐标显示
            self._update_canvas()

    def _on_canvas_release(self, event):
        """释放鼠标"""
        self.dragging_point_index = None
        self._update_coord_display()
        self.status_var.set("双击添加控制点，右键删除控制点")

    def _on_canvas_motion(self, event):
        """鼠标移动"""
        old_hover = self.hover_point_index
        self.hover_point_index = self._find_point_at(event.x, event.y)
        if old_hover != self.hover_point_index:
            self._update_canvas()

    def _on_canvas_double_click(self, event):
        """双击添加控制点"""
        px, py = self._canvas_to_normalized(event.x, event.y)

        # 找到合适的插入位置
        insert_idx = self._find_insert_position(px, py)
        self.curve_points.insert(insert_idx, (px, py))

        self.selected_point_index = insert_idx  # 选中新添加的点
        self._update_coord_display()
        self.status_var.set(f"已添加控制点 {insert_idx + 1}")
        self._update_canvas()

    def _on_canvas_right_click(self, event):
        """右键删除控制点"""
        point_idx = self._find_point_at(event.x, event.y)
        if point_idx is not None and len(self.curve_points) > 2:
            # 如果删除的是选中的点，清除选中状态
            if self.selected_point_index == point_idx:
                self.selected_point_index = None
            elif self.selected_point_index is not None and self.selected_point_index > point_idx:
                # 如果删除的点在选中点之前，更新选中点索引
                self.selected_point_index -= 1
            del self.curve_points[point_idx]
            self._update_coord_display()
            self.status_var.set(f"已删除控制点")
            self._update_canvas()
        elif len(self.curve_points) <= 2:
            self.status_var.set("至少需要2个控制点")

    def _find_insert_position(self, px, py):
        """查找新点的插入位置"""
        if self.split_mode == "horizontal":
            # 根据y坐标排序
            for i, (_, cy) in enumerate(self.curve_points):
                if py < cy:
                    return i
            return len(self.curve_points)
        else:
            # 根据x坐标排序
            for i, (cx, _) in enumerate(self.curve_points):
                if px < cx:
                    return i
            return len(self.curve_points)

    def _add_point(self):
        """添加控制点（在中间位置）"""
        if len(self.curve_points) < 2:
            return

        # 在最长的线段中间添加点
        max_dist = 0
        insert_idx = 1
        mid_point = (0.5, 0.5)
        for i in range(len(self.curve_points) - 1):
            p0 = self.curve_points[i]
            p1 = self.curve_points[i + 1]
            dist = ((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2) ** 0.5
            if dist > max_dist:
                max_dist = dist
                insert_idx = i + 1
                mid_point = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)

        self.curve_points.insert(insert_idx, mid_point)
        self.selected_point_index = insert_idx  # 选中新添加的点
        self._update_coord_display()
        self.status_var.set(f"已添加控制点 {insert_idx + 1}")
        self._update_canvas()

    def _remove_selected_point(self):
        """删除悬停或选中的控制点"""
        # 优先使用选中的点，其次使用悬停的点
        target_idx = self.selected_point_index if self.selected_point_index is not None else self.hover_point_index

        if target_idx is not None and len(self.curve_points) > 2:
            del self.curve_points[target_idx]
            self.hover_point_index = None
            self.selected_point_index = None
            self._update_coord_display()
            self.status_var.set("已删除控制点")
            self._update_canvas()
        elif len(self.curve_points) <= 2:
            self.status_var.set("至少需要2个控制点")
        else:
            self.status_var.set("请先选中或悬停要删除的点")

    def _reset_to_line(self):
        """重置为直线"""
        if self.split_mode == "horizontal":
            # 获取第一个点的x位置作为直线位置
            x_pos = self.curve_points[0][0] if self.curve_points else 0.5
            self.curve_points = [
                (x_pos, 0.0),
                (x_pos, 0.5),
                (x_pos, 1.0)
            ]
        else:
            y_pos = self.curve_points[0][1] if self.curve_points else 0.5
            self.curve_points = [
                (0.0, y_pos),
                (0.5, y_pos),
                (1.0, y_pos)
            ]
        self.selected_point_index = None
        self._update_coord_display()
        self.status_var.set("已重置为直线")
        self._update_canvas()

    def _smooth_curve(self):
        """平滑曲线（增加中间控制点）"""
        if len(self.curve_points) < 2:
            return

        new_points = [self.curve_points[0]]
        for i in range(len(self.curve_points) - 1):
            p0 = self.curve_points[i]
            p1 = self.curve_points[i + 1]
            # 添加中点
            mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
            new_points.append(mid)
            new_points.append(p1)

        self.curve_points = new_points
        self.selected_point_index = None
        self._update_coord_display()
        self.status_var.set(f"曲线已平滑，当前 {len(self.curve_points)} 个控制点")
        self._update_canvas()

    def _apply_preset(self, preset_type):
        """应用预设曲线形状"""
        import math

        # 获取当前分割位置作为基准
        if self.curve_points:
            if self.split_mode == "horizontal":
                base_pos = self.curve_points[len(self.curve_points) // 2][0]
            else:
                base_pos = self.curve_points[len(self.curve_points) // 2][1]
        else:
            base_pos = 0.5

        # 曲线振幅（偏移量）
        amplitude = 0.15

        if self.split_mode == "horizontal":
            # 左右分割：竖向曲线，x可变，y从0到1
            if preset_type == "s_curve":
                # S形曲线
                self.curve_points = [
                    (base_pos - amplitude, 0.0),
                    (base_pos - amplitude, 0.25),
                    (base_pos + amplitude, 0.5),
                    (base_pos + amplitude, 0.75),
                    (base_pos - amplitude, 1.0)
                ]
            elif preset_type == "wave":
                # 波浪形
                self.curve_points = [
                    (base_pos, 0.0),
                    (base_pos + amplitude, 0.2),
                    (base_pos - amplitude, 0.4),
                    (base_pos + amplitude, 0.6),
                    (base_pos - amplitude, 0.8),
                    (base_pos, 1.0)
                ]
            elif preset_type == "arc_in":
                # 内凹弧形
                self.curve_points = [
                    (base_pos, 0.0),
                    (base_pos - amplitude * 1.5, 0.25),
                    (base_pos - amplitude * 2, 0.5),
                    (base_pos - amplitude * 1.5, 0.75),
                    (base_pos, 1.0)
                ]
            elif preset_type == "arc_out":
                # 外凸弧形
                self.curve_points = [
                    (base_pos, 0.0),
                    (base_pos + amplitude * 1.5, 0.25),
                    (base_pos + amplitude * 2, 0.5),
                    (base_pos + amplitude * 1.5, 0.75),
                    (base_pos, 1.0)
                ]
            elif preset_type == "diagonal":
                # 斜线
                self.curve_points = [
                    (base_pos - amplitude, 0.0),
                    (base_pos, 0.5),
                    (base_pos + amplitude, 1.0)
                ]
        else:
            # 上下分割：横向曲线，y可变，x从0到1
            if preset_type == "s_curve":
                self.curve_points = [
                    (0.0, base_pos - amplitude),
                    (0.25, base_pos - amplitude),
                    (0.5, base_pos + amplitude),
                    (0.75, base_pos + amplitude),
                    (1.0, base_pos - amplitude)
                ]
            elif preset_type == "wave":
                self.curve_points = [
                    (0.0, base_pos),
                    (0.2, base_pos + amplitude),
                    (0.4, base_pos - amplitude),
                    (0.6, base_pos + amplitude),
                    (0.8, base_pos - amplitude),
                    (1.0, base_pos)
                ]
            elif preset_type == "arc_in":
                self.curve_points = [
                    (0.0, base_pos),
                    (0.25, base_pos - amplitude * 1.5),
                    (0.5, base_pos - amplitude * 2),
                    (0.75, base_pos - amplitude * 1.5),
                    (1.0, base_pos)
                ]
            elif preset_type == "arc_out":
                self.curve_points = [
                    (0.0, base_pos),
                    (0.25, base_pos + amplitude * 1.5),
                    (0.5, base_pos + amplitude * 2),
                    (0.75, base_pos + amplitude * 1.5),
                    (1.0, base_pos)
                ]
            elif preset_type == "diagonal":
                self.curve_points = [
                    (0.0, base_pos - amplitude),
                    (0.5, base_pos),
                    (1.0, base_pos + amplitude)
                ]

        # 确保坐标在有效范围内
        self.curve_points = [
            (max(0.05, min(0.95, x)), max(0.0, min(1.0, y)))
            for x, y in self.curve_points
        ]

        preset_names = {
            "s_curve": "S曲线",
            "wave": "波浪",
            "arc_in": "内凹弧形",
            "arc_out": "外凸弧形",
            "diagonal": "斜线"
        }
        self.selected_point_index = None  # 重置选中状态
        self._update_coord_display()
        self.status_var.set(f"已应用预设: {preset_names.get(preset_type, preset_type)}")
        self._update_canvas()

    def _on_ok(self):
        """确定按钮"""
        # 排序控制点
        if self.split_mode == "horizontal":
            self.curve_points.sort(key=lambda p: p[1])
        else:
            self.curve_points.sort(key=lambda p: p[0])

        self.result = {'points': self.curve_points}
        self.dialog.destroy()

    def _on_cancel(self):
        """取消按钮"""
        self.result = None
        self.dialog.destroy()

    def _update_coord_display(self):
        """更新坐标显示"""
        if self.selected_point_index is not None and 0 <= self.selected_point_index < len(self.curve_points):
            px, py = self.curve_points[self.selected_point_index]
            self.selected_point_var.set(f"点 {self.selected_point_index + 1}")
            self.coord_x_var.set(f"{px:.3f}")
            self.coord_y_var.set(f"{py:.3f}")
            self.coord_x_entry.config(state='normal')
            self.coord_y_entry.config(state='normal')
        else:
            self.selected_point_var.set("无")
            self.coord_x_var.set("--")
            self.coord_y_var.set("--")
            self.coord_x_entry.config(state='disabled')
            self.coord_y_entry.config(state='disabled')

    def _apply_coord_input(self, event=None):
        """应用手动输入的坐标"""
        if self.selected_point_index is None:
            self.status_var.set("请先选中一个控制点")
            return

        try:
            new_x = float(self.coord_x_var.get())
            new_y = float(self.coord_y_var.get())

            # 限制范围
            new_x = max(0.0, min(1.0, new_x))
            new_y = max(0.0, min(1.0, new_y))

            # 允许自由移动（同时更新X和Y）
            self.curve_points[self.selected_point_index] = (new_x, new_y)

            self._update_coord_display()
            self._update_canvas()
            self.status_var.set(f"已更新控制点 {self.selected_point_index + 1} 的坐标")

        except ValueError:
            self.status_var.set("请输入有效的数字（0.0 - 1.0）")

    def _toggle_grid(self):
        """切换网格显示"""
        self.show_grid = self.grid_var.get()
        self._update_canvas()

    def _fine_tune_point(self, dx, dy):
        """微调选中的控制点位置"""
        if self.selected_point_index is None:
            self.status_var.set("请先选中一个控制点")
            return

        if 0 <= self.selected_point_index < len(self.curve_points):
            px, py = self.curve_points[self.selected_point_index]

            # 计算新位置（dx, dy 是步数，乘以步长）
            step = self.fine_tune_step
            new_x = px + dx * step
            new_y = py + dy * step

            # 限制范围
            new_x = max(0.0, min(1.0, new_x))
            new_y = max(0.0, min(1.0, new_y))

            # 允许自由移动（上下左右都可以）
            self.curve_points[self.selected_point_index] = (new_x, new_y)

            self._update_coord_display()
            self._update_canvas()

    def _delete_selected_point(self):
        """删除选中的控制点"""
        if self.selected_point_index is None:
            self.status_var.set("请先选中一个控制点")
            return

        if len(self.curve_points) <= 2:
            self.status_var.set("至少需要保留2个控制点")
            return

        if 0 <= self.selected_point_index < len(self.curve_points):
            del self.curve_points[self.selected_point_index]
            self.status_var.set(f"已删除控制点")
            self.selected_point_index = None
            self._update_coord_display()
            self._update_canvas()

    def _deselect_point(self):
        """取消选中控制点"""
        self.selected_point_index = None
        self._update_coord_display()
        self._update_canvas()
        self.status_var.set("已取消选中")

    def show(self):
        """显示对话框并返回结果"""
        self.dialog.wait_window()
        return self.result
