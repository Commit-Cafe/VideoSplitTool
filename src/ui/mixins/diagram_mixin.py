"""
效果示意图功能 Mixin
处理可拖拽效果示意图的显示和交互
"""
import tkinter as tk
from tkinter import ttk

from ...core.ffmpeg_utils import FFmpegHelper


def get_video_info(video_path):
    """获取视频信息的辅助函数"""
    info = FFmpegHelper.get_video_info(video_path)
    if info:
        return info.to_dict()
    return None


class DiagramMixin:
    """效果示意图功能混入类

    需要主类提供以下属性：
    - root: tk.Tk
    - template_video: tk.StringVar
    - split_mode: tk.StringVar
    - position_order: tk.StringVar
    - output_ratio: tk.DoubleVar
    - output_ratio_enabled: tk.BooleanVar
    - template_scale_mode, list_scale_mode: tk.StringVar
    - status_var: tk.StringVar

    需要主类提供以下方法：
    - _on_output_ratio_toggle(): 输出比例切换
    - _refresh_merge_preview(): 刷新预览
    """

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
