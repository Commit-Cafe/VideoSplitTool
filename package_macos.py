#!/usr/bin/env python3
"""
macOS 打包脚本
在 macOS 系统上运行此脚本打包应用
运行方式: python3 package_macos.py
"""

import os
import sys
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path


def run_command(cmd, description):
    """运行命令"""
    print(f"\n{description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"错误: {e}")
        print(f"输出: {e.output}")
        return False


def check_dependencies():
    """检查依赖"""
    print("=== 检查依赖 ===")

    # 检查 Python
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print(f"错误: Python 版本过低 ({sys.version}), 需要 Python 3.8+")
        return False
    print(f"✓ Python {sys.version}")

    # 检查 PyInstaller
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("安装 PyInstaller...")
        if not run_command("pip3 install pyinstaller", "安装 PyInstaller"):
            return False

    # 检查 Pillow
    try:
        import PIL
        print(f"✓ Pillow {PIL.__version__}")
    except ImportError:
        print("安装 Pillow...")
        if not run_command("pip3 install pillow", "安装 Pillow"):
            return False

    # 检查 FFmpeg
    ffmpeg_installed = run_command("which ffmpeg", "检查 FFmpeg")
    if not ffmpeg_installed:
        print("警告: 系统未安装 FFmpeg")
        print("建议安装: brew install ffmpeg")
    else:
        print("✓ FFmpeg 已安装")

    return True


def clean_build():
    """清理旧的构建文件"""
    print("\n=== 清理旧文件 ===")
    dirs_to_remove = ['build', 'dist', '__pycache__']
    files_to_remove = [f for f in os.listdir('.') if f.endswith('.spec')]

    for d in dirs_to_remove:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"删除目录: {d}")

    for f in files_to_remove:
        os.remove(f)
        print(f"删除文件: {f}")


def build_app():
    """打包应用"""
    print("\n=== 打包应用 ===")

    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name", "VideoSplitTool",
        "main.py"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("打包失败:")
        print(result.stderr)
        return False

    print("✓ 打包完成")
    return True


def create_package():
    """创建分发包"""
    print("\n=== 创建分发包 ===")

    # 创建 release 目录
    release_dir = Path("release")
    release_dir.mkdir(exist_ok=True)

    # 确定打包文件
    dist_dir = Path("dist")
    app_name = "VideoSplitTool"
    timestamp = datetime.now().strftime("%Y%m%d")
    zip_name = f"{app_name}_macOS_{timestamp}.zip"
    zip_path = release_dir / zip_name

    # 查找可执行文件
    app_path = dist_dir / f"{app_name}.app"
    exe_path = dist_dir / app_name

    if app_path.exists():
        # 打包 .app 文件
        print(f"打包 {app_name}.app...")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(app_path):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(dist_dir)
                    zipf.write(file_path, arcname)

    elif exe_path.exists():
        # 打包可执行文件
        print(f"打包 {app_name} 可执行文件...")

        # 创建临时目录
        temp_dir = dist_dir / f"{app_name}_Package"
        temp_dir.mkdir(exist_ok=True)

        # 复制可执行文件
        shutil.copy(exe_path, temp_dir / app_name)

        # 创建 README
        readme_content = """视频分割拼接工具 macOS 版

使用说明：
1. 确保已安装 FFmpeg
   安装命令: brew install ffmpeg

2. 双击运行 VideoSplitTool
   如果提示"无法打开"，请在终端执行:
   chmod +x VideoSplitTool
   ./VideoSplitTool

3. 如果遇到安全提示：
   系统偏好设置 -> 安全性与隐私 -> 通用 -> 点击"仍要打开"

更新内容：
- 视频位置顺序配置（模板在前/列表在前）
- 封面选帧实时预览（自动更新）
- 音频配置功能（模板音频/列表音频/混合/静音/自定义）
- 封面帧来源选择（模板视频/列表视频）
- 修复封面拼接后音频丢失问题
- 界面优化
"""
        with open(temp_dir / "README.txt", 'w', encoding='utf-8') as f:
            f.write(readme_content)

        # 打包
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(dist_dir)
                    zipf.write(file_path, arcname)

        # 清理临时目录
        shutil.rmtree(temp_dir)

    else:
        print("错误: 未找到可执行文件")
        return False

    # 显示结果
    if zip_path.exists():
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"\n=== 打包完成 ===")
        print(f"文件: {zip_path}")
        print(f"大小: {size_mb:.1f} MB")
        print(f"\n注意事项：")
        print(f"1. 用户需要安装 FFmpeg: brew install ffmpeg")
        print(f"2. 首次运行可能需要在安全设置中允许")
        return True

    return False


def main():
    """主函数"""
    print("=== macOS 打包脚本 ===\n")

    # 检查平台
    if sys.platform != "darwin":
        print(f"警告: 当前平台是 {sys.platform}, 不是 macOS (darwin)")
        response = input("是否继续打包? (y/n): ").lower()
        if response != 'y':
            return

    # 检查依赖
    if not check_dependencies():
        print("\n依赖检查失败，请先安装所需依赖")
        return

    # 清理旧文件
    clean_build()

    # 打包应用
    if not build_app():
        print("\n打包失败")
        return

    # 创建分发包
    if not create_package():
        print("\n创建分发包失败")
        return

    print("\n所有步骤完成!")


if __name__ == "__main__":
    main()
