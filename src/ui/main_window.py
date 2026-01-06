"""
主窗口组件
视频分割拼接工具的主界面
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
import atexit
from datetime import datetime
from typing import List, Optional

from ..models.video_item import VideoItem
from ..models.config import AppConfig
from ..core.video_processor import VideoProcessor, ProcessResult
from ..core.ffmpeg_utils import FFmpegHelper, check_ffmpeg
from ..utils.logger import logger, cleanup_old_logs
from ..utils.temp_manager import global_temp_manager, cleanup_on_exit
from ..utils.file_utils import is_valid_video
from ..utils.format_utils import format_duration, format_video_info
from .dialogs import VideoSettingsDialog


class MainWindow:
    """主窗口类"""

    VERSION = "2.2"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"视频分割拼接工具 V{self.VERSION}")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)

        # 数据
        self.video_list: List[VideoItem] = []
        self.template_video: Optional[str] = None
        self.output_dir: Optional[str] = None
        self.config = AppConfig()

        # 视频处理器
        self.processor = VideoProcessor()

        # 处理状态
        self.is_processing = False
        self.processing_thread = None

        # 检查FFmpeg
        if not check_ffmpeg():
            messagebox.showerror("错误", "未检测到FFmpeg，请确保已安装FFmpeg并添加到系统PATH")

        # 清理旧日志
        cleanup_old_logs()

        # 注册退出清理
        atexit.register(cleanup_on_exit)

        # 创建UI
        self._create_menu()
        self._create_widgets()
        self._bind_events()

        logger.info(f"程序启动 - V{self.VERSION}")

    def _create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="选择模板视频", command=self._select_template)
        file_menu.add_command(label="添加视频", command=self._add_videos)
        file_menu.add_command(label="选择输出目录", command=self._select_output_dir)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)

        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self._show_about)

    def _create_widgets(self):
        """创建主界面控件"""
        # 主容器
        main_container = ttk.Frame(self.root, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)

        # 顶部：模板视频区域
        self._create_template_section(main_container)

        # 中部：视频列表和预览
        self._create_middle_section(main_container)

        # 底部：设置和操作按钮
        self._create_bottom_section(main_container)

    def _create_template_section(self, parent):
        """创建模板视频区域"""
        frame = ttk.LabelFrame(parent, text="模板视频", padding="5")
        frame.pack(fill=tk.X, pady=(0, 10))

        self.template_var = tk.StringVar(value="未选择模板视频")
        ttk.Label(frame, textvariable=self.template_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(frame, text="选择", command=self._select_template).pack(side=tk.RIGHT)

    def _create_middle_section(self, parent):
        """创建中间区域"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 左侧：视频列表
        left_frame = ttk.LabelFrame(frame, text="视频列表", padding="5")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # 列表工具栏
        toolbar = ttk.Frame(left_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(toolbar, text="添加", command=self._add_videos).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="移除", command=self._remove_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="清空", command=self._clear_list).pack(side=tk.LEFT, padx=2)

        # 视频列表
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('name', 'split', 'scale', 'cover')
        self.video_tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        self.video_tree.heading('name', text='文件名')
        self.video_tree.heading('split', text='分割')
        self.video_tree.heading('scale', text='缩放')
        self.video_tree.heading('cover', text='封面')

        self.video_tree.column('name', width=200)
        self.video_tree.column('split', width=60)
        self.video_tree.column('scale', width=60)
        self.video_tree.column('cover', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.video_tree.yview)
        self.video_tree.configure(yscrollcommand=scrollbar.set)

        self.video_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.video_tree.bind('<Double-1>', self._on_video_double_click)

        # 右侧：预览区域
        right_frame = ttk.LabelFrame(frame, text="预览", padding="5")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, ipadx=20)

        self.preview_canvas = tk.Canvas(right_frame, width=300, height=200, bg='#f0f0f0')
        self.preview_canvas.pack(pady=10)

    def _create_bottom_section(self, parent):
        """创建底部区域"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X)

        # 设置区域
        settings_frame = ttk.LabelFrame(frame, text="设置", padding="5")
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        # 分割模式
        mode_frame = ttk.Frame(settings_frame)
        mode_frame.pack(fill=tk.X, pady=2)
        ttk.Label(mode_frame, text="分割模式:").pack(side=tk.LEFT)
        self.split_mode = tk.StringVar(value="horizontal")
        ttk.Radiobutton(mode_frame, text="左右分割", variable=self.split_mode,
                       value="horizontal").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="上下分割", variable=self.split_mode,
                       value="vertical").pack(side=tk.LEFT, padx=10)

        # 输出目录
        output_frame = ttk.Frame(settings_frame)
        output_frame.pack(fill=tk.X, pady=2)
        ttk.Label(output_frame, text="输出目录:").pack(side=tk.LEFT)
        self.output_var = tk.StringVar(value="未选择")
        ttk.Label(output_frame, textvariable=self.output_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(output_frame, text="选择", command=self._select_output_dir).pack(side=tk.RIGHT)

        # 操作按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)

        self.process_btn = ttk.Button(btn_frame, text="开始处理", command=self._start_processing)
        self.process_btn.pack(side=tk.RIGHT, padx=5)

        ttk.Button(btn_frame, text="应用到全部", command=self._apply_to_all).pack(side=tk.RIGHT, padx=5)

        # 进度条
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(btn_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(btn_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=5)

    def _bind_events(self):
        """绑定事件"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _select_template(self):
        """选择模板视频"""
        file_path = filedialog.askopenfilename(
            title="选择模板视频",
            filetypes=[("视频文件", "*.mp4;*.avi;*.mkv;*.mov;*.wmv")]
        )
        if file_path and is_valid_video(file_path):
            self.template_video = file_path
            self.template_var.set(os.path.basename(file_path))
            logger.info(f"选择模板视频: {file_path}")

    def _add_videos(self):
        """添加视频"""
        files = filedialog.askopenfilenames(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4;*.avi;*.mkv;*.mov;*.wmv")]
        )
        for file_path in files:
            if is_valid_video(file_path):
                video_item = VideoItem(path=file_path)
                self.video_list.append(video_item)
                self._update_video_tree()
        logger.info(f"添加了 {len(files)} 个视频")

    def _remove_selected(self):
        """移除选中的视频"""
        selected = self.video_tree.selection()
        if selected:
            indices = [self.video_tree.index(item) for item in selected]
            for index in sorted(indices, reverse=True):
                if 0 <= index < len(self.video_list):
                    del self.video_list[index]
            self._update_video_tree()

    def _clear_list(self):
        """清空列表"""
        if messagebox.askyesno("确认", "确定要清空视频列表吗？"):
            self.video_list.clear()
            self._update_video_tree()

    def _update_video_tree(self):
        """更新视频列表显示"""
        for item in self.video_tree.get_children():
            self.video_tree.delete(item)

        for video in self.video_list:
            split, scale, cover = video.get_summary()
            self.video_tree.insert('', 'end', values=(video.name, split, scale, cover))

    def _on_video_double_click(self, event):
        """双击视频项"""
        selected = self.video_tree.selection()
        if selected:
            index = self.video_tree.index(selected[0])
            if 0 <= index < len(self.video_list):
                video_item = self.video_list[index]
                dialog = VideoSettingsDialog(
                    self.root, video_item,
                    self.split_mode.get(),
                    self.template_video,
                    self
                )
                result = dialog.show()
                if result:
                    self.video_list[index] = result
                    self._update_video_tree()

    def _select_output_dir(self):
        """选择输出目录"""
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.output_dir = dir_path
            self.output_var.set(dir_path)
            logger.info(f"选择输出目录: {dir_path}")

    def _apply_to_all(self):
        """应用设置到所有视频"""
        if not self.video_list:
            return

        selected = self.video_tree.selection()
        if selected:
            index = self.video_tree.index(selected[0])
            if 0 <= index < len(self.video_list):
                source = self.video_list[index]
                for i, video in enumerate(self.video_list):
                    if i != index:
                        video.split_ratio = source.split_ratio
                        video.scale_percent = source.scale_percent
                        video.cover_type = source.cover_type
                        video.cover_duration = source.cover_duration
                self._update_video_tree()
                messagebox.showinfo("成功", "已应用设置到所有视频")

    def _start_processing(self):
        """开始处理"""
        if self.is_processing:
            return

        # 验证
        if not self.template_video:
            messagebox.showerror("错误", "请先选择模板视频")
            return
        if not self.video_list:
            messagebox.showerror("错误", "请添加要处理的视频")
            return
        if not self.output_dir:
            messagebox.showerror("错误", "请选择输出目录")
            return

        self.is_processing = True
        self.process_btn.config(state='disabled')
        self.status_var.set("处理中...")

        # 在后台线程处理
        self.processing_thread = threading.Thread(target=self._process_videos)
        self.processing_thread.daemon = True
        self.processing_thread.start()

    def _process_videos(self):
        """处理视频（后台线程）"""
        total = len(self.video_list)
        success_count = 0
        fail_count = 0

        for i, video_item in enumerate(self.video_list):
            if not self.is_processing:
                break

            self.root.after(0, lambda idx=i: self.status_var.set(f"处理 {idx + 1}/{total}: {video_item.name}"))

            # 生成输出文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"{os.path.splitext(video_item.name)[0]}_{timestamp}.mp4"
            output_path = os.path.join(self.output_dir, output_name)

            # 处理视频
            result = self.processor.process_videos(
                template_video=self.template_video,
                target_video=video_item.path,
                output_path=output_path,
                split_mode=self.split_mode.get(),
                merge_mode="a+c",
                split_ratio=0.5,
                target_split_ratio=video_item.split_ratio,
                target_scale_percent=video_item.scale_percent,
                cover_type=video_item.cover_type,
                cover_frame_time=video_item.cover_frame_time,
                cover_image_path=video_item.cover_image_path,
                cover_duration=video_item.cover_duration,
                cover_frame_source=video_item.cover_frame_source
            )

            if result.success:
                success_count += 1
            else:
                fail_count += 1
                logger.error(f"处理失败 {video_item.name}: {result.error}")

            progress = (i + 1) / total * 100
            self.root.after(0, lambda p=progress: self.progress_var.set(p))

        # 完成
        self.root.after(0, self._processing_complete, success_count, fail_count)

    def _processing_complete(self, success: int, fail: int):
        """处理完成"""
        self.is_processing = False
        self.process_btn.config(state='normal')
        self.progress_var.set(0)

        total = success + fail
        self.status_var.set(f"完成: {success}/{total} 成功")

        if fail == 0:
            messagebox.showinfo("完成", f"所有 {total} 个视频处理完成！")
        else:
            messagebox.showwarning("完成", f"处理完成：{success} 个成功，{fail} 个失败")

        logger.info(f"处理完成: {success}/{total} 成功")

    def _show_about(self):
        """显示关于对话框"""
        messagebox.showinfo(
            "关于",
            f"视频分割拼接工具 V{self.VERSION}\n\n"
            "一个简单的视频分割拼接工具\n"
            "使用FFmpeg进行视频处理"
        )

    def _on_closing(self):
        """窗口关闭"""
        if self.is_processing:
            if not messagebox.askyesno("确认", "正在处理视频，确定要退出吗？"):
                return
            self.is_processing = False

        cleanup_on_exit()
        self.root.destroy()

    def run(self):
        """运行主循环"""
        self.root.mainloop()
