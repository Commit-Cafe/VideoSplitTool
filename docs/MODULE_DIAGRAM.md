# 模块依赖关系图

## 层级依赖

```
┌─────────────────────────────────────────────────────────────────────┐
│                           UI Layer (表现层)                          │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐ │
│  │      MainWindow         │    │        Dialogs                  │ │
│  │   - 主窗口管理          │    │   - VideoSettingsDialog         │ │
│  │   - 事件处理            │    │   - 视频设置对话框              │ │
│  │   - 进度显示            │    │                                 │ │
│  └───────────┬─────────────┘    └──────────────┬──────────────────┘ │
└──────────────│─────────────────────────────────│────────────────────┘
               │                                 │
               ▼                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Core Layer (业务层)                         │
│  ┌─────────────────────┐  ┌────────────────┐  ┌───────────────────┐ │
│  │   VideoProcessor    │  │  FFmpegHelper  │  │  ErrorHandler     │ │
│  │   - 视频处理        │  │  - FFmpeg封装  │  │  - 错误诊断       │ │
│  │   - 拼接逻辑        │  │  - 视频信息    │  │  - 输入验证       │ │
│  │   - 封面处理        │  │  - 帧提取      │  │  - 建议生成       │ │
│  └─────────┬───────────┘  └───────┬────────┘  └─────────┬─────────┘ │
└────────────│──────────────────────│─────────────────────│───────────┘
             │                      │                     │
             ▼                      ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Models Layer (数据层)                        │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐ │
│  │         VideoItem           │    │         AppConfig           │ │
│  │   - 视频文件路径            │    │   - 分割模式                │ │
│  │   - 分割比例                │    │   - 位置顺序                │ │
│  │   - 缩放百分比              │    │   - 音频来源                │ │
│  │   - 封面设置                │    │   - 输出配置                │ │
│  └─────────────────────────────┘    └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Utils Layer (工具层)                         │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────┐ ┌──────────────┐ │
│  │   Logger      │ │  TempManager  │ │ FileUtils │ │ FormatUtils  │ │
│  │   日志记录    │ │  临时文件管理 │ │ 文件操作  │ │ 格式化工具   │ │
│  └───────────────┘ └───────────────┘ └───────────┘ └──────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## 模块职责

### UI Layer (src/ui/)

| 模块 | 职责 | 依赖 |
|------|------|------|
| MainWindow | 主窗口、菜单、事件处理 | VideoProcessor, AppConfig, VideoItem |
| Dialogs | 视频设置对话框 | VideoItem, FFmpegHelper |

### Core Layer (src/core/)

| 模块 | 职责 | 依赖 |
|------|------|------|
| VideoProcessor | 视频处理协调、filter构建 | FFmpegHelper, ErrorHandler, TempManager |
| FFmpegHelper | FFmpeg/FFprobe命令封装 | Logger |
| ErrorHandler | 错误诊断、输入验证 | Logger, FileUtils |

### Models Layer (src/models/)

| 模块 | 职责 | 依赖 |
|------|------|------|
| VideoItem | 视频文件数据结构 | - |
| AppConfig | 应用配置数据结构 | - |

### Utils Layer (src/utils/)

| 模块 | 职责 | 依赖 |
|------|------|------|
| Logger | 日志记录、清理 | - |
| TempManager | 临时文件追踪与清理 | FileUtils, Logger |
| FileUtils | 文件操作、验证 | - |
| FormatUtils | 时间/大小格式化 | - |

## 数据流向

```
用户输入
    │
    ▼
┌──────────────┐
│  MainWindow  │ ─── 收集用户配置
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  AppConfig   │ ─── 存储配置
│  VideoItem   │ ─── 存储视频信息
└──────┬───────┘
       │
       ▼
┌───────────────┐
│VideoProcessor │ ─── 处理视频
└──────┬────────┘
       │
       ▼
┌──────────────┐
│ FFmpegHelper │ ─── 调用FFmpeg
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    FFmpeg    │ ─── 实际处理
└──────┬───────┘
       │
       ▼
   输出视频
```

## 事件处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        事件处理流程                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  用户操作 ──► MainWindow ──► 验证输入 ──► 创建处理线程         │
│                                    │                            │
│                                    ▼                            │
│                              VideoProcessor                     │
│                                    │                            │
│                    ┌───────────────┼───────────────┐            │
│                    ▼               ▼               ▼            │
│               获取信息         构建滤镜        处理封面         │
│                    │               │               │            │
│                    ▼               ▼               ▼            │
│              FFmpegHelper    FFmpegHelper    FFmpegHelper       │
│                    │               │               │            │
│                    └───────────────┴───────────────┘            │
│                                    │                            │
│                                    ▼                            │
│                              进度回调                           │
│                                    │                            │
│                                    ▼                            │
│                           MainWindow更新UI                      │
│                                    │                            │
│                                    ▼                            │
│                              处理完成                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 关键接口

### VideoProcessor.process_videos()

```python
def process_videos(
    template_video: str,      # 模板视频路径
    target_video: str,        # 目标视频路径
    output_path: str,         # 输出路径
    split_mode: str,          # 分割模式 (horizontal/vertical)
    merge_mode: str,          # 拼接模式 (a+c, a+d, b+c, b+d)
    split_ratio: float,       # 模板分割比例
    target_split_ratio: float,# 目标分割比例
    target_scale_percent: int,# 目标缩放百分比
    cover_type: str,          # 封面类型
    cover_frame_time: float,  # 封面帧时间
    cover_image_path: str,    # 封面图片路径
    cover_duration: float,    # 封面时长
    cover_frame_source: str,  # 封面帧来源
    position_order: str,      # 位置顺序
    audio_source: str,        # 音频来源
    custom_audio_path: str,   # 自定义音频路径
    output_width: int,        # 输出宽度
    output_height: int,       # 输出高度
    scale_mode: str           # 缩放模式
) -> ProcessResult
```

### FFmpegHelper.get_video_info()

```python
@staticmethod
def get_video_info(video_path: str) -> Optional[VideoInfo]:
    """
    获取视频信息

    Returns:
        VideoInfo(width, height, duration, has_audio)
    """
```
