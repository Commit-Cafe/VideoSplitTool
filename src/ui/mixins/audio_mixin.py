"""
音频设置功能 Mixin
处理音频源选择、音量调节、音频试听等
"""
import os
import subprocess
from tkinter import messagebox, filedialog


class AudioMixin:
    """音频设置功能混入类

    需要主类提供以下属性：
    - audio_source: tk.StringVar
    - custom_audio_path: tk.StringVar
    - template_volume: tk.IntVar
    - list_volume: tk.IntVar
    - custom_volume: tk.IntVar
    - global_volume: tk.IntVar
    - template_volume_label, list_volume_label, custom_volume_label: ttk.Label
    - global_volume_label: ttk.Label
    - template_video: tk.StringVar
    - video_items: list
    - preview_video_combo: ttk.Combobox
    - status_var: tk.StringVar
    - _audio_player: subprocess.Popen (需要在主类中初始化为 None)
    """

    def _select_custom_audio(self):
        """选择自定义音频文件"""
        # 热更新：从配置文件重新读取最新目录（支持多实例间同步）
        self._load_dialog_dirs()
        file_path = filedialog.askopenfilename(
            title="选择音频文件",
            initialdir=self._template_initial_dir,  # 使用模板目录作为初始目录
            filetypes=[
                ("音频文件", "*.mp3 *.wav *.aac *.m4a *.flac *.ogg"),
                ("视频文件", "*.mp4 *.avi *.mkv *.mov"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.custom_audio_path.set(file_path)
            self.audio_source.set("custom")

    def _on_global_volume_change(self, value):
        """全局音量滑块变化"""
        vol = int(float(value))
        self.global_volume_label.config(text=f"{vol}%")

    def _apply_global_volume(self):
        """将全局音量应用到所有音频源"""
        vol = self.global_volume.get()
        self.template_volume.set(vol)
        self.list_volume.set(vol)
        self.custom_volume.set(vol)
        self.template_volume_label.config(text=f"{vol}%")
        self.list_volume_label.config(text=f"{vol}%")
        self.custom_volume_label.config(text=f"{vol}%")
        self.status_var.set(f"已将音量 {vol}% 应用到所有音频源")

    def _on_volume_change(self, source, value):
        """单个音量滑块变化"""
        vol = int(float(value))
        if source == 'template':
            self.template_volume_label.config(text=f"{vol}%")
        elif source == 'list':
            self.list_volume_label.config(text=f"{vol}%")
        elif source == 'custom':
            self.custom_volume_label.config(text=f"{vol}%")

    def _preview_audio(self, source):
        """试听音频（带音量调节）"""
        # 停止之前的播放
        self._stop_audio_preview()

        # 确定音频源和音量
        if source == 'template':
            audio_path = self.template_video.get()
            volume = self.template_volume.get() / 100.0
            if not audio_path:
                messagebox.showinfo("提示", "请先选择模板视频")
                return
        elif source == 'list':
            if not self.video_items:
                messagebox.showinfo("提示", "请先添加列表视频")
                return
            idx = self.preview_video_combo.current()
            if idx < 0 or idx >= len(self.video_items):
                idx = 0
            audio_path = self.video_items[idx].path
            volume = self.list_volume.get() / 100.0
        elif source == 'custom':
            audio_path = self.custom_audio_path.get()
            volume = self.custom_volume.get() / 100.0
            if not audio_path:
                messagebox.showinfo("提示", "请先选择自定义音频文件")
                return
        else:
            return

        if not os.path.exists(audio_path):
            messagebox.showerror("错误", f"文件不存在: {audio_path}")
            return

        try:
            from ..core.ffmpeg_utils import get_ffmpeg_path
            ffmpeg_dir = os.path.dirname(get_ffmpeg_path())
            ffplay_path = os.path.join(ffmpeg_dir, 'ffplay.exe')

            # 如果ffplay不存在，使用ffmpeg播放
            if not os.path.exists(ffplay_path):
                ffplay_path = 'ffplay'

            # 使用ffplay播放音频，应用音量滤镜
            cmd = [
                ffplay_path,
                '-nodisp',  # 不显示视频窗口
                '-autoexit',  # 播放完自动退出
                '-t', '10',  # 最多播放10秒
                '-af', f'volume={volume}',  # 音量滤镜
                audio_path
            ]

            self._audio_player = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            self.status_var.set(f"正在试听音频 (音量: {int(volume * 100)}%)...")

        except FileNotFoundError:
            messagebox.showerror("错误", "未找到ffplay，无法试听音频")
        except Exception as e:
            messagebox.showerror("错误", f"播放音频失败: {e}")

    def _stop_audio_preview(self):
        """停止音频试听"""
        if self._audio_player:
            try:
                self._audio_player.terminate()
                self._audio_player.wait(timeout=1)
            except Exception:
                try:
                    self._audio_player.kill()
                except Exception:
                    pass
            self._audio_player = None
            self.status_var.set("已停止音频播放")
