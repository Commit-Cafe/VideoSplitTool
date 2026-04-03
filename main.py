"""
视频分割拼接工具 V2.2 - 主入口
"""
import tkinter as tk
from tkinter import messagebox
import atexit

from src.ui import VideoSplitApp
from src.utils import global_temp_manager, cleanup_on_exit, logger, cleanup_old_logs


def main():
    """程序主入口"""
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
                # 保存目录配置
                app._save_dialog_dirs()
                root.destroy()
        else:
            # 保存目录配置
            app._save_dialog_dirs()
            logger.info("用户正常退出程序")
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # 启动主循环
    root.mainloop()
    logger.info("程序已关闭")


if __name__ == "__main__":
    main()
