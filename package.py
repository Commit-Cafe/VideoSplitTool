"""
打包分发脚本 - 将exe和ffmpeg打包成zip文件
"""
import os
import zipfile
import shutil
from datetime import datetime


def create_distribution_package():
    """创建分发包"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(base_dir, 'dist')

    # 检查必要文件
    exe_path = os.path.join(dist_dir, 'VideoSplitTool.exe')
    ffmpeg_dir = os.path.join(dist_dir, 'ffmpeg')

    if not os.path.exists(exe_path):
        print("错误: VideoSplitTool.exe 不存在，请先运行打包")
        return False

    if not os.path.exists(ffmpeg_dir):
        print("错误: ffmpeg 目录不存在")
        return False

    # 创建发布目录
    release_dir = os.path.join(base_dir, 'release')
    os.makedirs(release_dir, exist_ok=True)

    # 生成zip文件名
    timestamp = datetime.now().strftime("%Y%m%d")
    zip_name = f"VideoSplitTool_{timestamp}.zip"
    zip_path = os.path.join(release_dir, zip_name)

    print(f"正在创建分发包: {zip_name}")

    # 创建zip文件
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 添加exe
        print("  添加 VideoSplitTool.exe...")
        zipf.write(exe_path, 'VideoSplitTool/VideoSplitTool.exe')

        # 添加ffmpeg (只添加bin目录下的必要文件)
        ffmpeg_bin = os.path.join(ffmpeg_dir, 'bin')
        for file in ['ffmpeg.exe', 'ffprobe.exe']:
            file_path = os.path.join(ffmpeg_bin, file)
            if os.path.exists(file_path):
                print(f"  添加 ffmpeg/bin/{file}...")
                zipf.write(file_path, f'VideoSplitTool/ffmpeg/bin/{file}')

        # 添加使用说明
        readme_content = """# 视频分割拼接工具 使用说明

## 使用方法
1. 解压本压缩包到任意目录
2. 双击运行 VideoSplitTool.exe
3. 按照界面提示操作

## 目录结构（请勿改动）
VideoSplitTool/
├── VideoSplitTool.exe    <- 主程序
└── ffmpeg/               <- 依赖文件（必须保留）
    └── bin/
        ├── ffmpeg.exe
        └── ffprobe.exe

## 注意事项
- ffmpeg文件夹必须和exe放在同一目录下
- 请勿删除或移动ffmpeg文件夹

## 功能说明
- 支持视频画面分割（左右/上下）
- 支持自定义分割位置（可拖拽调整）
- 支持多种拼接方式
- 支持批量处理
- 自动处理视频长度和画面对齐
"""
        zipf.writestr('VideoSplitTool/使用说明.txt', readme_content.encode('utf-8'))

    # 获取文件大小
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)

    print(f"\n打包完成!")
    print(f"输出文件: {zip_path}")
    print(f"文件大小: {size_mb:.1f} MB")
    print(f"\n请将此zip文件发送给同事，解压后即可使用")

    return True


if __name__ == '__main__':
    create_distribution_package()
    input("\n按回车键退出...")
