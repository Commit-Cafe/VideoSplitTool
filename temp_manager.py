"""
临时文件管理器模块
"""
import os
import uuid
import glob
from datetime import datetime
from typing import List
from utils import get_temp_dir
from logger import logger


class TempFileManager:
    """临时文件管理器，用于追踪和清理临时文件"""

    def __init__(self):
        """初始化临时文件管理器"""
        self.temp_files: List[str] = []
        self.temp_dir = get_temp_dir()

    def create_temp_file(self, suffix: str = ".tmp", prefix: str = "") -> str:
        """
        创建临时文件路径并追踪

        Args:
            suffix: 文件后缀，如 ".jpg", ".mp4"
            prefix: 文件前缀

        Returns:
            str: 临时文件的完整路径
        """
        filename = f"{prefix}{uuid.uuid4().hex[:8]}{suffix}"
        file_path = os.path.join(self.temp_dir, filename)
        self.temp_files.append(file_path)
        logger.debug(f"创建临时文件追踪: {file_path}")
        return file_path

    def cleanup_tracked_files(self):
        """清理所有追踪的临时文件"""
        cleaned = 0
        failed = 0

        for file_path in self.temp_files[:]:  # 使用副本遍历
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    cleaned += 1
                    logger.debug(f"删除临时文件: {file_path}")
                self.temp_files.remove(file_path)
            except OSError as e:
                failed += 1
                logger.warning(f"无法删除临时文件 {file_path}: {e}")
            except Exception as e:
                failed += 1
                logger.error(f"删除临时文件时发生异常 {file_path}: {e}")

        if cleaned > 0:
            logger.info(f"清理了 {cleaned} 个临时文件" + (f"，{failed} 个失败" if failed > 0 else ""))

    def cleanup_old_temp_files(self, days: int = 3):
        """
        清理旧的临时文件（所有文件，不仅仅是追踪的）

        Args:
            days: 清理几天前的文件，默认3天
        """
        try:
            if not os.path.exists(self.temp_dir):
                return

            current_time = datetime.now().timestamp()
            cutoff_time = current_time - (days * 24 * 3600)
            cleaned = 0

            # 清理所有旧文件
            for file_path in glob.glob(os.path.join(self.temp_dir, "*")):
                try:
                    if os.path.isfile(file_path):
                        file_time = os.path.getmtime(file_path)
                        if file_time < cutoff_time:
                            os.remove(file_path)
                            cleaned += 1
                            logger.debug(f"清理旧临时文件: {file_path}")
                except OSError as e:
                    logger.warning(f"无法删除旧临时文件 {file_path}: {e}")

            if cleaned > 0:
                logger.info(f"清理了 {cleaned} 个旧临时文件（{days}天前）")

        except Exception as e:
            logger.error(f"清理旧临时文件失败: {e}")

    def cleanup_all(self):
        """清理所有临时文件（追踪的+旧的）"""
        self.cleanup_tracked_files()
        self.cleanup_old_temp_files()

    def get_tracked_count(self) -> int:
        """获取当前追踪的临时文件数量"""
        return len(self.temp_files)

    def get_temp_dir_size(self) -> int:
        """
        获取临时目录总大小（字节）

        Returns:
            int: 目录大小（字节）
        """
        total_size = 0
        try:
            for file_path in glob.glob(os.path.join(self.temp_dir, "*")):
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
        except Exception as e:
            logger.error(f"计算临时目录大小失败: {e}")
        return total_size


# 全局临时文件管理器实例
global_temp_manager = TempFileManager()


def cleanup_on_exit():
    """程序退出时的清理函数"""
    logger.info("程序退出，开始清理临时文件...")
    global_temp_manager.cleanup_all()
    logger.info("临时文件清理完成")
