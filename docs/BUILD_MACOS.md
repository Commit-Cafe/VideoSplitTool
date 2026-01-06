# macOS 打包说明

## 前置条件

1. **macOS 系统**（需要在 macOS 上才能打包 macOS 版本）
2. **Python 3.8+**
3. **FFmpeg**（可选，但建议安装）

## 安装依赖

### 1. 安装 Homebrew（如果还没有）
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. 安装 FFmpeg（可选）
```bash
brew install ffmpeg
```

### 3. 安装 Python 依赖
```bash
pip3 install pyinstaller pillow
```

## 打包方法

### 方法一：使用 Python 脚本（推荐）

```bash
# 进入项目目录
cd /path/to/video_pin

# 运行打包脚本
python3 package_macos.py
```

### 方法二：使用 Shell 脚本

```bash
# 进入项目目录
cd /path/to/video_pin

# 添加执行权限
chmod +x package_macos.sh

# 运行打包脚本
./package_macos.sh
```

### 方法三：手动打包

```bash
# 1. 清理旧文件
rm -rf build dist *.spec

# 2. 打包
pyinstaller --onefile --windowed --name VideoSplitTool main.py

# 3. 查看生成的文件
ls -lh dist/
```

## 打包结果

打包成功后，会在 `release/` 目录下生成：
```
VideoSplitTool_macOS_20260104.zip
```

解压后包含：
- `VideoSplitTool` - 可执行文件或 `.app` 文件
- `README.txt` - 使用说明

## 分发给用户

用户使用步骤：

1. **安装 FFmpeg**
   ```bash
   brew install ffmpeg
   ```

2. **解压并运行**
   - 双击 `VideoSplitTool` 或 `VideoSplitTool.app`
   - 如果提示"无法打开"，在终端执行：
     ```bash
     chmod +x VideoSplitTool
     ./VideoSplitTool
     ```

3. **安全设置**
   - 如果遇到安全提示："无法打开，因为它来自身份不明的开发者"
   - 解决方法：
     - 系统偏好设置 → 安全性与隐私 → 通用
     - 点击"仍要打开"

## 常见问题

### Q: 打包失败，提示找不到模块
A: 确保已安装所有依赖：
```bash
pip3 install pyinstaller pillow
```

### Q: 生成的文件太大
A: macOS 版本通常比 Windows 版本小，因为不需要打包 FFmpeg

### Q: 用户无法运行
A: 提醒用户：
1. 安装 FFmpeg
2. 添加执行权限：`chmod +x VideoSplitTool`
3. 在安全设置中允许运行

## 注意事项

1. **FFmpeg**: macOS 版本不包含 FFmpeg，需要用户自行安装
2. **代码签名**: 如果需要发布到 App Store 或避免安全警告，需要 Apple Developer 账号进行代码签名
3. **通知权限**: 应用可能需要用户授予文件访问权限

## 开发者签名（可选）

如果有 Apple Developer 账号，可以签名应用：

```bash
# 查看可用的签名身份
security find-identity -v -p codesigning

# 签名应用
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/VideoSplitTool.app

# 验证签名
codesign --verify --deep --strict --verbose=2 dist/VideoSplitTool.app
spctl -a -t exec -vv dist/VideoSplitTool.app
```

## 创建 DMG 安装包（可选）

如果想创建更专业的安装包：

```bash
# 安装 create-dmg
brew install create-dmg

# 创建 DMG
create-dmg \
  --volname "VideoSplitTool" \
  --window-pos 200 120 \
  --window-size 800 400 \
  --icon-size 100 \
  --app-drop-link 600 185 \
  "release/VideoSplitTool_macOS.dmg" \
  "dist/VideoSplitTool.app"
```
