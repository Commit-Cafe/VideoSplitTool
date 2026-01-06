"""
日志系统模块
"""
import logging
import os
import sys
from datetime import datetime
from typing import Optional


def get_base_path() -> str:
    """获取程序基础路径（支持PyInstaller打包）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        # 开发环境：返回项目根目录
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_logger(name: str = "VideoSplitTool") -> logging.Logger:
    """
    配置日志系统

    Args:
        name: 日志记录器名称

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    log = logging.getLogger(name)

    # 避免重复添加handler
    if log.handlers:
        return log

    log.setLevel(logging.DEBUG)

    # 创建日志目录
    base_path = get_base_path()
    log_dir = os.path.join(base_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # 日志文件路径（按日期命名）
    log_file = os.path.join(log_dir, f'video_tool_{datetime.now().strftime("%Y%m%d")}.log')

    # 文件处理器（记录所有级别）
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_formatter)

    # 控制台处理器（仅显示警告及以上）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)

    log.addHandler(file_handler)
    log.addHandler(console_handler)

    return log


def cleanup_old_logs(days: int = 7):
    """
    清理旧的日志文件

    Args:
        days: 保留最近几天的日志，默认7天
    """
    try:
        base_path = get_base_path()
        log_dir = os.path.join(base_path, 'logs')

        if not os.path.exists(log_dir):
            return

        current_time = datetime.now().timestamp()
        cutoff_time = current_time - (days * 24 * 3600)

        for filename in os.listdir(log_dir):
            if filename.endswith('.log'):
                file_path = os.path.join(log_dir, filename)
                try:
                    file_time = os.path.getmtime(file_path)
                    if file_time < cutoff_time:
                        os.remove(file_path)
                except OSError as e:
                    logging.warning(f"无法删除旧日志文件 {filename}: {e}")
    except Exception as e:
        logging.error(f"清理旧日志失败: {e}")


# 全局日志记录器
logger = setup_logger()
