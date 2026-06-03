# Graph Report - D:\trae_Dproject\VideoSplitTool  (2026-06-03)

## Corpus Check
- Corpus is ~21,136 words - fits in a single context window. You may not need a graph.

## Summary
- 400 nodes · 816 edges · 23 communities (17 shown, 6 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 32 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_FFmpeg Utils & UI Mixins|FFmpeg Utils & UI Mixins]]
- [[_COMMUNITY_Error Diagnostics & Validation|Error Diagnostics & Validation]]
- [[_COMMUNITY_Audio Configuration|Audio Configuration]]
- [[_COMMUNITY_Main Window UI Builder|Main Window UI Builder]]
- [[_COMMUNITY_Config & Data Models|Config & Data Models]]
- [[_COMMUNITY_Curve Editor Dialog|Curve Editor Dialog]]
- [[_COMMUNITY_Video Processing Core|Video Processing Core]]
- [[_COMMUNITY_Preview Rendering|Preview Rendering]]
- [[_COMMUNITY_Video Settings Dialog|Video Settings Dialog]]
- [[_COMMUNITY_Detection Metadata|Detection Metadata]]
- [[_COMMUNITY_Temp File Management|Temp File Management]]
- [[_COMMUNITY_Curve Divider Mixin|Curve Divider Mixin]]
- [[_COMMUNITY_Batch Processing Control|Batch Processing Control]]
- [[_COMMUNITY_FFmpeg Filter Bugs|FFmpeg Filter Bugs]]
- [[_COMMUNITY_CI Build Pipelines|CI Build Pipelines]]
- [[_COMMUNITY_Claude Settings|Claude Settings]]
- [[_COMMUNITY_Architecture Design|Architecture Design]]
- [[_COMMUNITY_Curve Rendering|Curve Rendering]]
- [[_COMMUNITY_Error Reporting Bugs|Error Reporting Bugs]]
- [[_COMMUNITY_Package Metadata|Package Metadata]]
- [[_COMMUNITY_Progress Tracking Bug|Progress Tracking Bug]]

## God Nodes (most connected - your core abstractions)
1. `VideoSplitApp` - 48 edges
2. `CurveEditorDialog` - 34 edges
3. `FFmpegHelper` - 27 edges
4. `PreviewMixin` - 26 edges
5. `VideoProcessor` - 21 edges
6. `VideoSettingsDialog` - 19 edges
7. `get_temp_dir()` - 18 edges
8. `str` - 16 edges
9. `CoverMixin` - 14 edges
10. `int` - 13 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `VideoSplitApp`  [EXTRACTED]
  main.py → src/ui/main_window.py
- `main()` --calls--> `cleanup_old_logs()`  [EXTRACTED]
  main.py → src/utils/logger.py
- `VideoProcessor` --uses--> `ErrorDiagnostics`  [INFERRED]
  src/core/video_processor.py → src/core/error_handler.py
- `bool` --uses--> `ErrorDiagnostics`  [INFERRED]
  src/core/video_processor.py → src/core/error_handler.py
- `float` --uses--> `ErrorDiagnostics`  [INFERRED]
  src/core/video_processor.py → src/core/error_handler.py

## Hyperedges (group relationships)
- **FFmpeg Filter Chain Bugs** — review1_make_even_bug, review1_crop_negative_offset, review1_double_scale, review1_stderr_lost, review1_broad_error_match [INFERRED 0.80]

## Communities (23 total, 6 thin omitted)

### Community 0 - "FFmpeg Utils & UI Mixins"
Cohesion: 0.08
Nodes (40): FFmpeg 工具类 封装所有 FFmpeg 相关操作, Logger, 曲线分界线功能 Mixin 处理曲线分界线的编辑、生成和同步, 预览渲染功能 Mixin 处理模板视频预览、拼接预览、分割线绘制等, bool, str, float, int (+32 more)

### Community 1 - "Error Diagnostics & Validation"
Cohesion: 0.10
Nodes (27): Any, ErrorDiagnostics, format_error_message(), InputValidator, 诊断FFmpeg错误并提供修复建议          Args:             stderr: FFmpeg的错误输出, 验证视频文件          Args:             file_path: 视频文件路径          Returns:, 格式化错误消息（带建议）      Args:         error_desc: 错误描述         suggestions: 修复建议列表, check_ffmpeg() (+19 more)

### Community 2 - "Audio Configuration"
Cohesion: 0.06
Nodes (15): AudioMixin, 音频设置功能 Mixin 处理音频源选择、音量调节、音频试听等, 音频设置功能混入类      需要主类提供以下属性：     - audio_source: tk.StringVar     - custom_aud, CoverMixin, get_video_info(), 封面设置功能 Mixin 处理视频封面的类型选择、帧时间设置、图片选择等, 封面设置功能混入类      需要主类提供以下属性：     - global_cover_type: tk.StringVar     - globa, 将当前帧时间设置为当前预览视频的独立帧时间 (+7 more)

### Community 4 - "Config & Data Models"
Cohesion: 0.09
Nodes (21): Enum, AppConfig, AudioSource, DialogDirsConfig, MergeConfig, OutputConfig, OutputSizeMode, PositionOrder (+13 more)

### Community 5 - "Curve Editor Dialog"
Cohesion: 0.14
Nodes (3): int, CurveEditorDialog, 使用Catmull-Rom样条生成平滑曲线点用于绘制

### Community 6 - "Video Processing Core"
Cohesion: 0.19
Nodes (15): _build_scale_filter(), _make_even(), 处理视频：分割并拼接          Args:             template_video: 模板视频路径             tar, 确保数值是偶数（libx264要求宽高必须是偶数），最小值为2, 根据缩放模式构建FFmpeg scale滤镜字符串      Args:         width: 目标宽度         height: 目标高, 构建视频叠加滤镜 - 前景视频（模板）居中叠加在背景视频（列表）上          Args:             out_width: 输出宽度, 构建支持透明通道的filter_complex字符串         使用overlay滤镜将模板视频叠加到列表视频上，透明部分显示列表视频内容, 构建FFmpeg filter_complex字符串          Args:             output_ratio: 输出比例 - 上/ (+7 more)

### Community 7 - "Preview Rendering"
Cohesion: 0.12
Nodes (8): get_video_info(), PreviewMixin, 根据缩放模式缩放图片          Args:             img: PIL Image对象             target_w:, 预览渲染功能混入类      需要主类提供以下属性：     - template_video: tk.StringVar     - video_it, 模拟拼接效果（用PIL实现，支持缩放模式和曲线分界线）, 模拟叠加效果 - 前景视频（模板）居中叠加在背景视频（列表）上, 使用曲线蒙版模拟拼接效果（带边缘平滑处理）, 拼接预览画布滚轮事件 - 调整输出比例（仅在启用时生效）

### Community 8 - "Video Settings Dialog"
Cohesion: 0.12
Nodes (7): bool, str, int, str, VideoSettingsDialog, 生成输出文件名（支持多实例并发，避免文件名冲突）, ScrollableFrame

### Community 9 - "Detection Metadata"
Cohesion: 0.14
Nodes (13): files, code, document, image, paper, video, graphifyignore_patterns, needs_graph (+5 more)

### Community 10 - "Temp File Management"
Cohesion: 0.21
Nodes (6): int, str, 获取临时目录总大小（字节）          Returns:             int: 目录大小（字节）, 创建临时文件路径并追踪          Args:             suffix: 文件后缀，如 ".jpg", ".mp4", 清理旧的临时文件（所有文件，不仅仅是追踪的）          Args:             days: 清理几天前的文件，默认3天, TempFileManager

### Community 11 - "Curve Divider Mixin"
Cohesion: 0.24
Nodes (4): DividerMixin, 生成曲线分界线蒙版图片          Args:             curve_points: 曲线控制点列表，如果为None则使用全局设置, 曲线分界线功能混入类      需要主类提供以下属性：     - divider_enabled: tk.BooleanVar     - divid, 使用Catmull-Rom样条计算平滑曲线上的点          Args:             control_points: 归一化坐标的控制点

### Community 12 - "Batch Processing Control"
Cohesion: 0.25
Nodes (4): get_video_info(), ProcessingMixin, 视频处理功能混入类      需要主类提供以下属性：     - is_processing: bool     - processing_stoppe, int

### Community 13 - "FFmpeg Filter Bugs"
Cohesion: 0.50
Nodes (4): Even Width/Height Constraint, Bug: crop negative offset, Bug: double scaling filter conflict, Bug: _make_even zero value

### Community 14 - "CI Build Pipelines"
Cohesion: 1.00
Nodes (3): CI Manual Build Pipeline, CI Build and Release Pipeline, Pillow dependency

### Community 16 - "Architecture Design"
Cohesion: 0.67
Nodes (3): Four-Layer Architecture, Mixin Composition Pattern, VideoSplitTool V2.6.2

## Knowledge Gaps
- **29 isolated node(s):** `code`, `document`, `paper`, `image`, `video` (+24 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `VideoSplitApp` connect `Main Window UI Builder` to `FFmpeg Utils & UI Mixins`, `Audio Configuration`, `Preview Rendering`, `Video Settings Dialog`, `Curve Divider Mixin`, `Batch Processing Control`?**
  _High betweenness centrality (0.183) - this node is a cross-community bridge._
- **Why does `CurveEditorDialog` connect `Curve Editor Dialog` to `FFmpeg Utils & UI Mixins`, `Curve Divider Mixin`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Why does `PreviewMixin` connect `Preview Rendering` to `FFmpeg Utils & UI Mixins`, `Audio Configuration`, `Main Window UI Builder`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `VideoSplitApp` (e.g. with `VideoSettingsDialog` and `ScrollableFrame`) actually correct?**
  _`VideoSplitApp` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `FFmpegHelper` (e.g. with `ErrorDiagnostics` and `InputValidator`) actually correct?**
  _`FFmpegHelper` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `VideoProcessor` (e.g. with `ErrorDiagnostics` and `FFmpegHelper`) actually correct?**
  _`VideoProcessor` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `code`, `document`, `paper` to the rest of the system?**
  _101 weakly-connected nodes found - possible documentation gaps or missing edges._