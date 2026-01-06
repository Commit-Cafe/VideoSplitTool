# 视频分割拼接工具 V2.2

一个基于 Python + Tkinter + FFmpeg 的视频分割拼接工具。

## 功能特性

### 核心功能
- **视频分割**: 支持水平（左右）和垂直（上下）分割
- **视频拼接**: 4种拼接模式（A+C, A+D, B+C, B+D）
- **批量处理**: 支持多个视频批量处理
- **独立设置**: 每个视频可单独设置分割比例和缩放

### 封面功能
- 从视频提取帧作为封面
- 使用外部图片作为封面
- 支持从模板/列表/拼接后视频提取帧
- 可调节封面显示时长

### 音频功能
- 使用模板视频音频
- 使用列表视频音频
- 混合两个音频
- 使用自定义音频
- 静音模式

### 输出设置
- 跟随模板视频尺寸
- 跟随列表视频尺寸（一对一）
- 自定义输出尺寸

## 安装

### 依赖
- Python 3.8+
- FFmpeg 4.x+
- Pillow 9.x+

### 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/your-repo/video_pin.git
cd video_pin
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 确保 FFmpeg 已安装
```bash
# Windows: 下载 ffmpeg 并添加到 PATH
# macOS: brew install ffmpeg
# Linux: apt install ffmpeg
```

## 使用方法

### 启动程序
```bash
# 方式1: 使用新入口
python -m src.app

# 方式2: 使用原入口
python main.py
```

### 基本流程

1. **选择模板视频**: 作为分割参考的视频
2. **添加列表视频**: 需要处理的视频列表
3. **配置设置**:
   - 选择分割模式（左右/上下）
   - 选择拼接方式
   - 配置音频来源
   - 设置输出尺寸
4. **处理视频**: 点击开始处理

### 视频设置

双击列表中的视频可打开设置对话框：
- **分割比例**: 调整分割线位置（10%-90%）
- **缩放比例**: 调整视频缩放（50%-200%）
- **封面设置**: 配置视频封面

## 项目结构

```
video_pin/
├── src/                    # 源代码
│   ├── models/            # 数据模型
│   ├── core/              # 核心业务
│   ├── ui/                # UI界面
│   └── utils/             # 工具函数
├── docs/                   # 文档
├── main.py                # 入口文件
└── requirements.txt       # 依赖
```

详细架构说明请参考 [ARCHITECTURE.md](./ARCHITECTURE.md)

## 构建发布

### Windows
```bash
pyinstaller --onedir --windowed --name "视频分割拼接工具" main.py
```

### macOS
```bash
pyinstaller --onedir --windowed --name "VideoPinTool" main.py
```

## 常见问题

### Q: 提示"FFmpeg未找到"
A: 请确保 FFmpeg 已安装并添加到系统 PATH，或将 ffmpeg 文件夹放在程序目录下。

### Q: 处理时提示音频错误
A: 如果视频没有音频轨道，请在音频设置中选择"静音"。

### Q: 输出视频没有声音
A: 检查源视频是否有音频，尝试选择其他音频来源。

## 更新日志

### V2.2 (当前版本)
- 重构项目架构，提升代码可维护性
- 优化UI交互体验
- 新增输出尺寸选项
- 改进错误诊断系统

### V2.1
- 添加封面首帧功能
- 支持自定义音频
- 优化预览显示

### V2.0
- 支持独立视频设置
- 添加批量处理
- 改进FFmpeg集成

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
