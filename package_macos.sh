#!/bin/bash
# macOS 打包脚本
# 在 macOS 系统上运行此脚本打包应用

set -e

echo "=== 开始打包 macOS 版本 ==="

# 检查 Python 和 PyInstaller
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "安装 PyInstaller..."
    pip3 install pyinstaller
fi

# 检查依赖
echo "检查依赖..."
pip3 install pillow

# 清理旧的构建文件
echo "清理旧文件..."
rm -rf build dist *.spec

# 打包应用
echo "打包应用..."
pyinstaller --onefile --windowed \
    --name VideoSplitTool \
    --add-data "utils.py:." \
    --add-data "video_processor.py:." \
    main.py

# 检查 FFmpeg
echo "检查 FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "警告: 系统未安装 FFmpeg"
    echo "请使用 Homebrew 安装: brew install ffmpeg"
else
    echo "FFmpeg 已安装"
fi

# 创建发布目录
RELEASE_DIR="release"
mkdir -p "$RELEASE_DIR"

# 创建应用包目录结构
APP_NAME="VideoSplitTool"
APP_DIR="dist/${APP_NAME}.app"
TIMESTAMP=$(date +%Y%m%d)
ZIP_NAME="${APP_NAME}_macOS_${TIMESTAMP}.zip"

echo "创建分发包..."

# 如果生成的是 .app 文件
if [ -d "$APP_DIR" ]; then
    cd dist
    zip -r "../${RELEASE_DIR}/${ZIP_NAME}" "${APP_NAME}.app"
    cd ..
# 如果生成的是可执行文件
elif [ -f "dist/${APP_NAME}" ]; then
    # 创建临时目录结构
    TEMP_DIR="dist/${APP_NAME}_Package"
    mkdir -p "$TEMP_DIR"

    cp "dist/${APP_NAME}" "$TEMP_DIR/"

    # 创建说明文件
    cat > "$TEMP_DIR/README.txt" << 'EOF'
视频分割拼接工具 macOS 版

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
- 视频位置顺序配置
- 封面选帧实时预览
- 音频配置功能
- 封面帧来源选择
- 界面优化
EOF

    # 打包
    cd dist
    zip -r "../${RELEASE_DIR}/${ZIP_NAME}" "${APP_NAME}_Package"
    cd ..

    # 清理
    rm -rf "$TEMP_DIR"
fi

# 显示结果
if [ -f "${RELEASE_DIR}/${ZIP_NAME}" ]; then
    FILE_SIZE=$(du -h "${RELEASE_DIR}/${ZIP_NAME}" | cut -f1)
    echo ""
    echo "=== 打包完成 ==="
    echo "文件: ${RELEASE_DIR}/${ZIP_NAME}"
    echo "大小: ${FILE_SIZE}"
    echo ""
    echo "注意事项："
    echo "1. 用户需要安装 FFmpeg: brew install ffmpeg"
    echo "2. 首次运行可能需要在安全设置中允许"
else
    echo "错误: 打包失败"
    exit 1
fi
