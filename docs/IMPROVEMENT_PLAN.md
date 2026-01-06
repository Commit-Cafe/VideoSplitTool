# 视频分割拼接工具 - 改进计划

## 当前版本：V2.0
## 目标版本：V2.1（稳定性）→ V3.0（功能增强）

---

## 阶段1：稳定性修复（V2.1）⚡

### 1.1 资源管理优化
**优先级**：P0 - 严重

- [ ] **临时文件自动清理**
  - 程序启动时清理3天前的临时文件
  - 程序退出时清理当前会话的临时文件
  - 添加"清理临时文件"菜单选项

- [ ] **临时文件使用UUID命名**
  ```python
  # 当前
  preview_path = os.path.join(temp_dir, "preview.jpg")

  # 改进
  import uuid
  preview_path = os.path.join(temp_dir, f"preview_{uuid.uuid4().hex[:8]}.jpg")
  ```

- [ ] **追踪所有临时文件**
  ```python
  class TempFileManager:
      def __init__(self):
          self.temp_files = []

      def create_temp_file(self, suffix=".tmp"):
          path = os.path.join(get_temp_dir(), f"{uuid.uuid4().hex}{suffix}")
          self.temp_files.append(path)
          return path

      def cleanup_all(self):
          for path in self.temp_files:
              try:
                  if os.path.exists(path):
                      os.remove(path)
              except Exception as e:
                  logging.warning(f"Failed to delete {path}: {e}")
  ```

### 1.2 异常处理规范化
**优先级**：P0 - 严重

- [ ] **替换所有裸except**
  ```python
  # 当前
  except:
      pass

  # 改进
  except (OSError, IOError) as e:
      logging.error(f"File operation failed: {e}")
      return False
  except Exception as e:
      logging.exception(f"Unexpected error: {e}")
      raise
  ```

- [ ] **添加日志系统**
  ```python
  import logging

  # 配置日志
  logging.basicConfig(
      level=logging.INFO,
      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
      handlers=[
          logging.FileHandler('video_tool.log'),
          logging.StreamHandler()
      ]
  )
  ```

### 1.3 线程管理优化
**优先级**：P0 - 严重

- [ ] **非守护线程 + 优雅关闭**
  ```python
  class ProcessingThread(threading.Thread):
      def __init__(self):
          super().__init__()
          self.daemon = False  # ✓ 非守护线程
          self._stop_event = threading.Event()

      def stop(self):
          self._stop_event.set()

      def run(self):
          while not self._stop_event.is_set():
              # 处理逻辑
              pass
  ```

- [ ] **添加"停止处理"按钮**
  - 终止FFmpeg进程：`process.terminate()`
  - 清理未完成的输出文件
  - 更新UI状态

### 1.4 FFmpeg进程管理
**优先级**：P1 - 高

- [ ] **从subprocess.run改为Popen**
  ```python
  # 当前：subprocess.run缓冲所有输出
  result = subprocess.run(cmd, capture_output=True)

  # 改进：实时读取stderr，解析进度
  process = subprocess.Popen(
      cmd,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      creationflags=subprocess.CREATE_NO_WINDOW
  )

  # 解析FFmpeg的time=进度信息
  for line in iter(process.stderr.readline, b''):
      if b'time=' in line:
          # 提取当前时间，计算百分比
          progress = parse_ffmpeg_progress(line, total_duration)
          self._report_progress(progress, "处理中...")
  ```

- [ ] **支持取消FFmpeg任务**
  ```python
  def cancel_processing(self):
      if self.current_process:
          self.current_process.terminate()
          self.current_process.wait(timeout=5)
  ```

### 1.5 输入验证增强
**优先级**：P1 - 高

- [ ] **文件存在性和可读性检查**
  ```python
  def validate_video_file(path: str) -> tuple[bool, str]:
      if not os.path.exists(path):
          return False, "文件不存在"
      if not os.access(path, os.R_OK):
          return False, "文件无读取权限"
      if not is_valid_video(path):
          return False, "不是有效的视频格式"
      # 尝试获取视频信息验证完整性
      if not get_video_info(path):
          return False, "视频文件损坏或格式不支持"
      return True, ""
  ```

- [ ] **参数范围验证**
  ```python
  def validate_split_ratio(ratio: float) -> bool:
      return 0.1 <= ratio <= 0.9

  def validate_scale_percent(percent: int) -> bool:
      return 50 <= percent <= 200
  ```

---

## 阶段2：用户体验优化（V2.5）✨

### 2.1 进度反馈改进
**优先级**：P1 - 高

- [ ] **真实的FFmpeg进度条**
  - 解析`time=00:01:23.45`输出
  - 计算百分比：(current_time / total_duration) * 100
  - 更新进度条和剩余时间估算

- [ ] **详细的状态信息**
  ```
  正在处理: video1.mp4 (A+C)
  进度: 45% (01:23 / 03:05)
  速度: 1.2x
  预计剩余: 1分30秒
  ```

- [ ] **处理日志窗口**
  - 可选的"查看详细日志"按钮
  - 显示FFmpeg原始输出
  - 便于问题诊断

### 2.2 性能优化
**优先级**：P1 - 高

- [ ] **视频信息缓存**
  ```python
  class VideoInfoCache:
      def __init__(self):
          self._cache = {}  # {file_path: (mtime, info)}

      def get_info(self, path: str):
          mtime = os.path.getmtime(path)
          if path in self._cache:
              cached_mtime, info = self._cache[path]
              if cached_mtime == mtime:
                  return info

          info = get_video_info(path)
          self._cache[path] = (mtime, info)
          return info
  ```

- [ ] **封面预览优化**
  - 移除"拼接后视频"选项（性能太差）
  - 或改为：只提取单帧而不生成完整视频
  ```python
  # 使用FFmpeg的overlay滤镜生成单帧预览
  ffmpeg -i template.mp4 -i list.mp4 -filter_complex "..." -frames:v 1 preview.jpg
  ```

- [ ] **批量处理优化**
  - 如果多个视频使用相同设置，复用filter_complex
  - 预先验证所有输入文件，避免中途失败

### 2.3 UI改进
**优先级**：P2 - 中

- [ ] **拖放文件支持**
  ```python
  def on_drop(event):
      files = root.tk.splitlist(event.data)
      for file in files:
          if is_valid_video(file):
              add_video_to_list(file)
  ```

- [ ] **批量添加视频**
  - "添加文件夹"按钮，递归扫描所有视频
  - 支持多选文件

- [ ] **视频预览播放**
  - 使用opencv或tkVideoPlayer
  - 在设置对话框中播放视频片段
  - 帮助用户选择合适的分割位置

- [ ] **设置模板保存/加载**
  ```python
  # 保存常用配置为JSON
  {
    "split_mode": "horizontal",
    "split_ratio": 0.5,
    "merge_combinations": ["a+c"],
    "audio_source": "template",
    "cover_type": "none"
  }
  ```

### 2.4 错误处理用户友好化
**优先级**：P2 - 中

- [ ] **智能错误诊断**
  ```python
  def diagnose_ffmpeg_error(stderr: str, input_files: list) -> str:
      if "No such file" in stderr:
          return "视频文件路径无效或文件已被移动"
      if "Invalid data" in stderr:
          return "视频文件损坏，请使用其他工具修复或重新下载"
      if "matches no streams" in stderr:
          if "audio" in stderr:
              return "您选择了音频选项，但视频没有音频轨道，请选择'静音'或添加自定义音频"
      if "Conversion failed" in stderr:
          return "视频编码失败，可能是编码器不支持该分辨率或格式"
      return f"处理失败：{extract_key_error(stderr)}"
  ```

- [ ] **错误恢复建议**
  ```python
  def suggest_fix(error_type: str) -> list[str]:
      suggestions = {
          "no_audio": [
              "选择'静音'选项",
              "添加自定义音频文件",
              "使用有音频的视频"
          ],
          "file_not_found": [
              "检查文件是否被移动或删除",
              "重新选择视频文件"
          ]
      }
      return suggestions.get(error_type, ["查看详细日志"])
  ```

---

## 阶段3：功能增强（V3.0）🎯

### 3.1 新增核心功能
**优先级**：P2 - 中

- [ ] **批量模板应用**
  - 一次加载多个模板视频
  - 每个列表视频与所有模板视频配对
  - 生成N×M个输出视频

- [ ] **视频效果滤镜**
  - 亮度/对比度调整
  - 色彩滤镜（黑白、怀旧、冷暖色调）
  - 模糊/锐化
  ```python
  # FFmpeg滤镜示例
  -vf "eq=brightness=0.1:saturation=1.5,unsharp=5:5:1.0"
  ```

- [ ] **转场效果**
  - 在A+C拼接处添加过渡效果
  - 淡入淡出、滑动、溶解等
  ```python
  # FFmpeg xfade滤镜
  [0:v][1:v]xfade=transition=fade:duration=1:offset=5[outv]
  ```

- [ ] **画中画模式**
  - 将列表视频缩小后叠加在模板视频上
  - 可调整位置（左上、右上、左下、右下、中央）
  - 可调整尺寸和边框样式

- [ ] **水印添加**
  - 文字水印（可自定义字体、颜色、位置）
  - 图片水印（Logo、二维码等）
  - 时间戳水印

### 3.2 高级功能
**优先级**：P3 - 低

- [ ] **实时预览模式**
  - 使用opencv创建预览窗口
  - 实时显示拼接效果
  - 在预览窗口中调整分割线位置

- [ ] **视频剪辑**
  - 设置开始/结束时间
  - 只处理视频的某个时间段
  - 多段拼接

- [ ] **字幕添加**
  - 导入SRT/ASS字幕文件
  - 烧录到视频中
  - 可调整字幕样式

- [ ] **音频处理增强**
  - 音量调节（独立调整模板/列表音频）
  - 音频淡入淡出
  - 背景音乐混合（降低原音频音量）
  - 音频均衡器

- [ ] **GPU加速**
  - 检测NVIDIA/AMD GPU
  - 使用h264_nvenc/h264_amf编码器
  - 提升处理速度3-10倍
  ```python
  # 检测CUDA支持
  ffmpeg -hwaccels
  # 使用GPU编码
  -c:v h264_nvenc -preset fast
  ```

### 3.3 工作流优化
**优先级**：P3 - 低

- [ ] **项目文件保存**
  - 保存整个项目配置为.vproj文件
  - 包含所有视频路径、设置、输出目录
  - 下次打开直接加载，无需重新配置

- [ ] **历史记录**
  - 记录最近处理的视频和设置
  - 快速重复相同操作

- [ ] **预设管理**
  - 内置常用预设（抖音对比、B站双屏等）
  - 用户自定义预设
  - 导入/导出预设

- [ ] **命令行模式**
  ```bash
  VideoSplitTool.exe --template video1.mp4 --target video2.mp4 \
    --mode horizontal --merge a+c --output result.mp4
  ```

---

## 阶段4：企业级功能（V4.0）💼

### 4.1 多语言支持
- [ ] 英语界面
- [ ] 使用i18n框架
- [ ] 语言配置文件

### 4.2 云端集成
- [ ] 支持从云存储加载视频（OneDrive、Google Drive）
- [ ] 输出直接上传到云端
- [ ] 协作功能（共享配置）

### 4.3 API接口
- [ ] RESTful API
- [ ] 允许其他程序调用处理功能
- [ ] Webhook通知处理完成

### 4.4 性能监控
- [ ] 处理时间统计
- [ ] 成功率监控
- [ ] 资源使用情况（CPU、内存、磁盘）

---

## 代码质量改进（持续）

### 架构重构
- [ ] **分离UI和业务逻辑**
  ```
  video_pin/
  ├── ui/
  │   ├── main_window.py
  │   ├── settings_dialog.py
  │   └── widgets/
  ├── core/
  │   ├── processor.py
  │   ├── filter_builder.py
  │   └── ffmpeg_wrapper.py
  ├── utils/
  │   ├── file_manager.py
  │   ├── video_info.py
  │   └── temp_manager.py
  └── config/
      ├── presets.py
      └── constants.py
  ```

- [ ] **提取常量和配置**
  ```python
  # config/constants.py
  class VideoConfig:
      DEFAULT_PRESET = "medium"
      DEFAULT_CRF = 23
      PREVIEW_WIDTH = 320
      PREVIEW_HEIGHT = 180
      TEMP_VIDEO_DURATION = 15
  ```

- [ ] **单元测试**
  ```python
  # tests/test_filter_builder.py
  def test_horizontal_split_ac():
      builder = FilterBuilder()
      filter_str = builder.build_horizontal_split("a+c", 0.5, 1920, 1080)
      assert "[va][vc]hstack" in filter_str
  ```

### 文档完善
- [ ] **代码注释规范化**
  ```python
  def process_videos(
      self,
      template_video: str,  # 模板视频路径
      target_video: str,    # 目标视频路径
      # ...
  ) -> ProcessResult:
      """
      处理视频：分割并拼接

      Args:
          template_video: 模板视频路径（必须存在且可读）
          target_video: 目标视频路径（必须存在且可读）

      Returns:
          ProcessResult: 包含处理状态和错误信息

      Raises:
          ValueError: 参数无效时
          IOError: 文件访问失败时
      """
  ```

- [ ] **用户手册**
  - 安装指南
  - 功能说明（附截图）
  - 常见问题FAQ
  - 视频教程

- [ ] **开发者文档**
  - 架构设计图
  - 模块依赖关系
  - FFmpeg滤镜使用说明
  - 贡献指南

---

## 性能基准测试

### 测试场景
1. **小视频处理**
   - 输入：2个1分钟1080p视频
   - 操作：左右分割+拼接
   - 目标：<10秒

2. **大视频处理**
   - 输入：2个10分钟4K视频
   - 操作：上下分割+拼接+封面
   - 目标：<5分钟（GPU加速）

3. **批量处理**
   - 输入：10个视频
   - 操作：统一设置批量处理
   - 目标：CPU利用率>80%

### 优化目标
- [ ] 启动时间 < 2秒
- [ ] UI响应时间 < 100ms
- [ ] 内存占用 < 500MB（处理4K视频时）
- [ ] 临时文件自动清理率 > 99%

---

## 发布检查清单

### V2.1 发布前
- [ ] 所有P0问题已修复
- [ ] 所有P1问题已修复或记录为已知问题
- [ ] 在Windows 10/11上测试通过
- [ ] 在macOS上测试通过（如有条件）
- [ ] 更新README和CHANGELOG
- [ ] GitHub Actions构建成功
- [ ] 创建Release和安装包

### 测试用例
- [ ] 处理包含中文路径的视频
- [ ] 处理无音频视频
- [ ] 处理长时间视频（>1小时）
- [ ] 同时运行多个实例
- [ ] 处理中途取消
- [ ] 程序异常退出后重启

---

## 长期愿景

### 社区版 vs 专业版
**社区版（免费）**
- 基础分割拼接
- 封面设置
- 音频配置
- 最多同时处理5个视频

**专业版（付费）**
- 无限视频处理
- GPU加速
- 批量模板应用
- 高级滤镜
- 技术支持
- 云端存储

### 生态扩展
- [ ] 插件系统（允许第三方开发滤镜）
- [ ] 模板市场（分享/下载预设）
- [ ] 在线版本（WebAssembly + FFmpeg.js）

---

## 贡献者指南

如需参与开发，请：
1. Fork项目
2. 创建功能分支：`git checkout -b feature/new-feature`
3. 提交代码：`git commit -m "Add: new feature"`
4. 推送到分支：`git push origin feature/new-feature`
5. 创建Pull Request

### 代码规范
- 使用Black格式化代码
- 遵循PEP 8
- 所有公开函数必须有docstring
- 提交前运行`pylint`和`mypy`

---

**最后更新**: 2026-01-04
**维护者**: @developer
**问题反馈**: GitHub Issues
