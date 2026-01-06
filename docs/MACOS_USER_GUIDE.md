# 视频分割拼接工具 - macOS 用户完整指南

**版本**: V2.1
**适用系统**: macOS 10.13 (High Sierra) 及更高版本

---

## 📋 目录

1. [系统要求](#系统要求)
2. [安装步骤](#安装步骤)
3. [首次运行](#首次运行)
4. [使用说明](#使用说明)
5. [常见问题](#常见问题)
6. [卸载方法](#卸载方法)

---

## 💻 系统要求

- **操作系统**: macOS 10.13 或更高版本
- **处理器**: Intel 或 Apple Silicon (M1/M2/M3)
- **内存**: 至少 4GB RAM（推荐 8GB）
- **磁盘空间**: 至少 500MB 可用空间
- **必需软件**: FFmpeg（安装步骤见下文）

---

## 🚀 安装步骤

### 步骤1：安装 FFmpeg

FFmpeg 是视频处理的核心组件，必须先安装。

#### 方法A：使用 Homebrew（推荐）

**1.1 检查是否已安装 Homebrew**

打开"终端"应用（在"应用程序" → "实用工具"中），输入：

```bash
brew --version
```

- 如果显示版本号，说明已安装，跳到步骤1.2
- 如果提示"command not found"，需要先安装 Homebrew

**安装 Homebrew：**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

安装过程可能需要5-10分钟，请耐心等待。

**1.2 使用 Homebrew 安装 FFmpeg**

```bash
brew install ffmpeg
```

**1.3 验证安装**

```bash
ffmpeg -version
```

如果显示版本信息，说明安装成功！

---

#### 方法B：手动下载安装

如果不想使用 Homebrew，可以手动安装：

**1.1 下载 FFmpeg**

访问：https://evermeet.cx/ffmpeg/

下载以下文件：
- `ffmpeg-*.7z`
- `ffprobe-*.7z`

**1.2 解压并安装**

1. 双击解压下载的文件
2. 打开"终端"，执行以下命令：

```bash
# 创建本地bin目录
mkdir -p ~/bin

# 移动ffmpeg可执行文件（替换实际的文件名）
mv ~/Downloads/ffmpeg ~/bin/
mv ~/Downloads/ffprobe ~/bin/

# 添加执行权限
chmod +x ~/bin/ffmpeg
chmod +x ~/bin/ffprobe

# 添加到PATH（如果使用bash）
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bash_profile
source ~/.bash_profile

# 如果使用zsh（macOS 10.15+默认）
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**1.3 验证安装**

```bash
ffmpeg -version
```

---

### 步骤2：下载视频分割拼接工具

**2.1 从GitHub下载**

访问项目Release页面：
```
https://github.com/yuheng-ctrl/video_pin/releases
```

**2.2 下载macOS版本**

点击下载：`VideoSplitTool_macOS_YYYYMMDD.zip`

**2.3 解压文件**

双击下载的zip文件，会自动解压到"下载"文件夹。

**2.4 移动到应用程序文件夹（可选）**

```bash
# 打开Finder，将 VideoSplitTool 拖动到"应用程序"文件夹
# 或者使用终端命令：
mv ~/Downloads/VideoSplitTool /Applications/
```

---

## 🎬 首次运行

### 步骤1：添加执行权限

**打开终端，执行：**

```bash
# 如果应用在"应用程序"文件夹
chmod +x /Applications/VideoSplitTool

# 如果应用在"下载"文件夹
chmod +x ~/Downloads/VideoSplitTool
```

---

### 步骤2：处理 macOS 安全提示

macOS 会阻止未签名的应用，这是正常的安全机制。

#### 方法A：通过"系统设置"允许

**2.1 首次尝试运行**

双击 `VideoSplitTool`，会弹出提示：

```
"VideoSplitTool" 无法打开，因为它来自身份不明的开发者。
```

点击"好"。

**2.2 打开系统设置**

- **macOS 13 Ventura 及更高版本**：
  1. 打开"系统设置"
  2. 点击左侧"隐私与安全性"
  3. 向下滚动到"安全性"部分
  4. 找到提示：`"VideoSplitTool" 已被阻止`
  5. 点击右侧的"仍要打开"按钮
  6. 在弹出的对话框中，点击"打开"

- **macOS 12 Monterey 及更低版本**：
  1. 打开"系统偏好设置"
  2. 点击"安全性与隐私"
  3. 在"通用"标签页
  4. 找到提示：`"VideoSplitTool" 已被阻止`
  5. 点击"仍要打开"
  6. 在弹出的对话框中，点击"打开"

---

#### 方法B：通过终端运行（更简单）

**直接在终端运行：**

```bash
# 如果应用在"应用程序"文件夹
/Applications/VideoSplitTool

# 如果应用在"下载"文件夹
~/Downloads/VideoSplitTool
```

首次运行时，会弹出对话框：

```
macOS 无法验证"VideoSplitTool"的开发者。您确定要打开它吗？
```

点击"打开"即可。

---

#### 方法C：移除隔离属性（高级用户）

如果上述方法都不行，可以移除 macOS 的隔离属性：

```bash
# 移除隔离属性
xattr -d com.apple.quarantine /Applications/VideoSplitTool

# 或者对整个下载文件夹操作
xattr -d com.apple.quarantine ~/Downloads/VideoSplitTool
```

然后再双击运行。

---

## 📖 使用说明

### 基本工作流程

**1. 准备视频文件**
- 支持格式：MP4, AVI, MOV, MKV 等常见格式
- 准备一个"模板视频"（将被分割）
- 准备一个或多个"列表视频"（将与模板拼接）

**2. 启动应用**

```bash
# 方式1：双击应用图标
# 方式2：终端运行
/Applications/VideoSplitTool
```

**3. 配置模板视频**
- 点击"选择模板视频"
- 选择分割方式：
  - 左右分割（默认）
  - 上下分割
- 设置分割比例（例如：0.5 表示均分）

**4. 添加视频列表**
- 点击"添加视频"
- 可以添加多个视频
- 支持批量处理

**5. 配置音频选项**
- 静音：输出无声视频
- 保留模板音频：使用模板视频的音频
- 保留列表音频：使用列表视频的音频
- 混合音频：两个视频的音频混合
- 自定义音频：选择外部音频文件

**6. 设置封面（可选）**
- 选择封面来源：
  - 从模板视频选择帧
  - 从列表视频选择帧
  - 从拼接后视频选择帧
- 拖动滑块选择时间点
- 实时预览封面效果

**7. 开始处理**
- 点击"开始处理"按钮
- 等待处理完成
- 默认输出到"桌面/视频输出"文件夹

---

### 快捷键

- `Cmd + O`：打开模板视频
- `Cmd + A`：添加列表视频
- `Cmd + S`：开始处理
- `Cmd + Q`：退出应用

---

## ❓ 常见问题

### Q1: 提示"找不到 ffmpeg 命令"

**原因**: FFmpeg 未正确安装或未添加到 PATH

**解决方法**:

```bash
# 检查 FFmpeg 是否安装
which ffmpeg

# 如果没有输出，重新安装 FFmpeg
brew install ffmpeg

# 或者手动添加到 PATH
export PATH="/usr/local/bin:$PATH"
```

---

### Q2: 应用无法打开，提示"已损坏"

**原因**: macOS 的安全机制阻止

**解决方法**:

```bash
# 移除隔离属性
xattr -cr /Applications/VideoSplitTool

# 然后再双击运行
```

---

### Q3: 处理视频时速度很慢

**原因**: 视频文件较大或分辨率较高

**优化建议**:
1. 使用较低分辨率的源视频
2. 关闭不必要的应用释放内存
3. 确保有足够的磁盘空间（至少是视频大小的3倍）

**性能参考**:
- 1080p 10分钟视频：约 2-5 分钟处理时间
- 4K 10分钟视频：约 10-20 分钟处理时间

---

### Q4: 输出视频没有声音

**原因**: 可能选择了"静音"选项，或者源视频本身没有音频

**解决方法**:
1. 检查音频设置，确保不是"静音"
2. 确认源视频有音频轨道
3. 尝试"混合音频"选项

---

### Q5: 应用在 Apple Silicon (M1/M2/M3) Mac 上运行很慢

**原因**: 应用可能使用 Rosetta 2 转译运行

**解决方法**:

```bash
# 检查架构
file /Applications/VideoSplitTool

# 如果显示 x86_64，说明是 Intel 版本
# 可以尝试在 Rosetta 模式下优化：
arch -x86_64 /Applications/VideoSplitTool
```

> 注意: V2.1 使用 Python 构建，性能在 Apple Silicon 上应该是原生的。

---

### Q6: 处理过程中应用崩溃

**可能原因**:
1. 内存不足
2. 磁盘空间不足
3. 视频文件损坏

**解决方法**:
1. 检查系统"活动监视器"中的内存使用
2. 检查磁盘可用空间（至少需要 2GB）
3. 尝试用其他播放器播放源视频，确认文件完整
4. 查看日志文件了解详情：`logs/video_tool_YYYYMMDD.log`

---

### Q7: 如何查看处理日志？

**日志位置**:

```bash
# 应用同目录下的 logs 文件夹
/Applications/logs/video_tool_20260104.log

# 或者在终端查看最新日志
tail -f /Applications/logs/video_tool_$(date +%Y%m%d).log
```

---

### Q8: 输出的视频质量变差了

**原因**: FFmpeg 默认编码参数可能压缩了视频

**解决方法**:

当前版本使用的编码设置已优化，但如果需要更高质量：
1. 确保源视频质量足够高
2. 联系开发者请求添加质量设置选项

---

### Q9: 可以处理多大的视频文件？

**理论上没有限制**，但实际受以下因素影响：

- **可用内存**: 建议源视频大小 < 可用内存的 50%
- **磁盘空间**: 需要至少是视频大小的 3 倍
- **处理时间**: 大文件需要更长时间

**推荐限制**:
- 单个视频 < 2GB
- 总处理时长 < 1小时

---

### Q10: 如何批量处理多个视频？

**当前版本**:
- 可以添加多个"列表视频"
- 每个列表视频都会与模板视频拼接
- 生成多个输出文件

**示例**:
- 模板视频：A.mp4
- 列表视频：B1.mp4, B2.mp4, B3.mp4
- 输出：A+B1.mp4, A+B2.mp4, A+B3.mp4

---

## 🗑️ 卸载方法

### 完全卸载

**1. 删除应用**

```bash
# 删除应用程序
rm -rf /Applications/VideoSplitTool

# 或者拖到废纸篓
```

**2. 清理临时文件**

```bash
# 清理临时文件
rm -rf /tmp/video_pin

# 清理日志（如果需要）
rm -rf /Applications/logs
```

**3. 卸载 FFmpeg（可选）**

如果不再需要 FFmpeg：

```bash
brew uninstall ffmpeg
```

---

## 📞 技术支持

### 获取帮助

1. **查看日志文件**:
   ```bash
   cat /Applications/logs/video_tool_$(date +%Y%m%d).log
   ```

2. **查看详细文档**:
   - `RELEASE_NOTES_V2.1.md` - 发布说明
   - `DEBUG_FFMPEG_ERROR.md` - 错误诊断指南

3. **提交问题**:
   - GitHub Issues: https://github.com/yuheng-ctrl/video_pin/issues
   - 提交时请附上日志文件和错误截图

---

## 🎯 性能优化建议

### 1. 系统优化

```bash
# 关闭不必要的后台应用
# 确保有足够的可用内存（建议 > 2GB）

# 检查可用内存
vm_stat

# 检查磁盘空间
df -h
```

### 2. 视频预处理

**如果源视频过大**:
1. 可以先用其他工具转换为较小的格式
2. 降低分辨率（如 4K → 1080p）
3. 降低码率

### 3. 最佳实践

- ✅ 使用 SSD 存储视频文件
- ✅ 保持系统和 FFmpeg 更新
- ✅ 定期清理临时文件
- ✅ 处理前先测试小文件
- ❌ 避免同时运行多个视频处理任务
- ❌ 避免在低电量时处理大文件

---

## 📊 系统要求详细说明

### 最低配置
- **CPU**: Intel Core i3 / Apple M1
- **内存**: 4GB RAM
- **磁盘**: 500MB 可用空间
- **系统**: macOS 10.13+

### 推荐配置
- **CPU**: Intel Core i5 / Apple M1 或更高
- **内存**: 8GB RAM
- **磁盘**: 2GB+ 可用空间（SSD）
- **系统**: macOS 11.0+

### 处理性能参考

**Intel Mac (i5, 8GB RAM)**:
- 1080p 10分钟视频: ~3分钟
- 4K 10分钟视频: ~15分钟

**Apple Silicon Mac (M1, 8GB RAM)**:
- 1080p 10分钟视频: ~2分钟
- 4K 10分钟视频: ~8分钟

---

## 🔄 更新说明

### V2.1 新特性

✅ **稳定性改进**
- 自动临时文件清理
- 完善的日志记录系统
- 智能错误诊断

✅ **用户体验优化**
- 友好的错误提示
- 输入验证
- 退出保护机制

详见: `RELEASE_NOTES_V2.1.md`

---

## 📝 许可证

MIT License - 免费使用，欢迎分享

---

## 🙏 致谢

感谢使用视频分割拼接工具！

如有问题或建议，欢迎通过 GitHub Issues 反馈。

---

**最后更新**: 2026-01-04
**版本**: V2.1
**项目地址**: https://github.com/yuheng-ctrl/video_pin

---

**祝您使用愉快！** 🎉
