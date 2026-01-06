"""
视频分割拼接工具 - 应用入口
"""
import tkinter as tk
import sys
import os

# 确保src目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ui.main_window import MainWindow
from src.utils.logger import logger


def main():
    """应用程序入口"""
    logger.info("=" * 50)
    logger.info("视频分割拼接工具启动")
    logger.info("=" * 50)

    try:
        root = tk.Tk()
        app = MainWindow(root)
        app.run()
    except Exception as e:
        logger.exception(f"程序异常退出: {e}")
        raise
    finally:
        logger.info("程序退出")


if __name__ == "__main__":
    main()
