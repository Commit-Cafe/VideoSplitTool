# Claude Code Review #1 - 视频处理滤镜失败问题

## 问题概述

用户报告 3 个视频文件处理时提示"视频滤镜处理失败"，所有视频状态均为失败。经过完整源代码审查，共发现 **6 个 Bug** 和 **2 个改进建议**。

---

## Bug #1【严重】`_make_even()` 会产生零值，导致 FFmpeg 滤镜参数无效

**文件**: `src/core/video_processor.py:25-27`

```python
def _make_even(n: int) -> int:
    """确保数值是偶数（libx264要求宽高必须是偶数）"""
    return n if n % 2 == 0 else n - 1
```

**问题**: 当输入 `n=1` 时返回 `0`，当输入 `n=0` 时返回 `0`。这些零值会作为裁剪滤镜的宽/高参数传给 FFmpeg，导致 `crop` 滤镜报错。

**触发条件**:
- 输出尺寸很小（如 100x100），分割比例很小（如 0.1）
  - `int(100 * 0.1)` = 10 → `_make_even(10)` = 10（正常）
  - `int(100 * 0.01)` → 这不应该发生（比例限制为 0.1）
- 但更隐蔽的场景：在 `_build_filter_complex` 中（line 912）:
  ```python
  template_part_a_width = _make_even(int(out_width * actual_output_ratio))
  ```
  若 `out_width=3`（极小视频）且 `actual_output_ratio=0.5`：
  - `int(3 * 0.5)` = 1 → `_make_even(1)` = **0** → FFmpeg 崩溃

**修复方案**:
```python
def _make_even(n: int) -> int:
    """确保数值是偶数（libx264要求宽高必须是偶数），最小值为2"""
    if n <= 1:
        return 2
    return n if n % 2 == 0 else n - 1
```

或者换一种方式，确保最小值为 2：
```python
def _make_even(n: int, min_value: int = 2) -> int:
    result = n if n % 2 == 0 else n - 1
    return max(result, min_value)
```

---

## Bug #2【严重】`crop` 滤镜的偏移量可能为负数

**文件**: `src/core/video_processor.py:1101`

```python
f"crop={part_d_width}:{target_height}:{target_width}-{part_d_width}:0,"
```

**问题**: 当 `part_d_width > target_width` 时，表达式 `{target_width}-{part_d_width}` 会产生负数，FFmpeg 无法处理负数的裁剪偏移量。

**触发条件**:
- 在 `_build_horizontal_filter` 中（line 916-917）:
  ```python
  target_part_c_width = _make_even(int(target_scaled_width * target_split_ratio))
  target_part_d_width = target_scaled_width - target_part_c_width
  ```
  当 `target_scaled_width=2`，`target_split_ratio=0.9`：
  - `target_part_c_width = _make_even(1)` = 假设修复后为 2（原版为 0）
  - `target_part_d_width = 2 - 2` = 0
  - 此时 `target_width - part_d_width` = `2 - 0` = 2（正常）
  
  但当修复 `_make_even` 为最小值 2 后，可能产生溢出问题。需要确保 `crop` 的 `x:y` 不为负。

**同样的问题出现在**:
- `video_processor.py:1158` - 水平滤镜
- `video_processor.py:1161` - 水平滤镜  
- `video_processor.py:1228` - 垂直滤镜
- `video_processor.py:1242` - 垂直滤镜
- `video_processor.py:1274` - 垂直滤镜
- `video_processor.py:1288` - 垂直滤镜

**修复方案**: 在 crop 使用前验证参数：
```python
crop_x = max(0, target_width - part_d_width)
crop_y = max(0, target_height - part_d_height)
```

---

## Bug #3【中等】`_build_horizontal_filter` / `_build_vertical_filter` 中双重缩放导致滤镜链冗余冲突

**文件**: `src/core/video_processor.py:1077-1095`

在两个子滤镜构建函数中，对模板视频的处理是先拉伸到全尺寸再裁剪，然后**再应用一次缩放模式**。例如：

```python
# 第一步：拉伸到输出全尺寸（disable aspect ratio）
f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=disable,"
# 第二步：裁剪出需要的部分
f"crop={part_a_width}:{out_height}:0:0,"
# 第三步：再应用缩放（可能是 fit/fill/stretch）
f"{t_scale_left}[va];"  # ← t_scale_left 内部可能又有 crop + pad
```

**问题**: 
1. 第三步的 `_build_scale_filter` 在 "fill" 模式下会执行 `scale(force_original_aspect_ratio=increase) + crop`，但此时视频已经被第一步拉伸变形了，aspect_ratio 已不可靠。
2. 当 `template_scale_mode="fill"` 时，第一步拉伸后的视频宽高比已经失真，第三步的 `force_original_aspect_ratio=increase` 可能基于错误的比例进行计算。

**修复方案**: 第一步的 scale 不应该使用 `force_original_aspect_ratio=disable`，应该保持原比例进行缩放：
```python
# 保持原比例的缩放（仅用于区域提取）
f"[0:v]scale={out_width}:{out_height}:force_original_aspect_ratio=increase,"
# 裁剪
f"crop={part_a_width}:{out_height}:(iw-{part_a_width})/2:(ih-{out_height})/2,"
# 最终缩放（这一步会应用用户的缩放模式）
f"{t_scale_left}[va];"
```

或者更简洁地：移除第一步 scale+crop 中的 scale，直接用 crop 从原始视频中提取区域（但需要从原始尺寸计算裁剪位置）。

---

## Bug #4【严重】FFmpeg stderr 错误信息丢失，用户看到的错误毫无帮助

**文件**: `src/core/video_processor.py:90-133` 和 `src/core/error_handler.py:109-117`

**问题链**:
1. `_run_ffmpeg` 只在 **DEBUG** 级别记录 FFmpeg stderr（line 115）
2. `ErrorDiagnostics.diagnose_ffmpeg_error()` 返回一个**通用错误描述**，完全丢弃了原始 FFmpeg 错误信息
3. 用户界面只显示 "视频滤镜处理失败"，没有具体原因

```python
# video_processor.py:114-116
if result.returncode != 0:
    logger.error(f"FFmpeg执行失败，返回码: {result.returncode}")
    logger.debug(f"FFmpeg stderr: {result.stderr}")  # ← DEBUG级别！故障排查时根本看不到

# error_handler.py:109-117
if "filter" in stderr_lower or "scale" in stderr_lower:
    return (
        "视频滤镜处理失败",  # ← 通用错误，丢弃了原始信息
        [
            "视频尺寸可能异常(0x0或过大)",
            "尝试调整分割比例",
            "检查视频文件是否完整"
        ]
    )
```

**问题**: 
- 用户无法根据"视频滤镜处理失败"定位具体原因。
- FFmpeg 的原始错误 stderr 包含了精确的失败位置和原因（如某个滤镜的参数错误），但被丢弃了。
- 由于 `logger.debug` 记录 stderr，而在日常使用中 DEBUG 日志很容易被忽略。

**修复方案**:
1. 将 stderr 记录级别从 DEBUG 提升到 **ERROR**：
```python
logger.error(f"FFmpeg stderr: {result.stderr}")
```

2. 在错误消息中保留 FFmpeg 关键错误信息：
```python
# error_handler.py 修改
error_desc, suggestions = ErrorDiagnostics.diagnose_ffmpeg_error(
    result.stderr,
    context
)
# 保留原始错误第一行用于诊断
first_error_line = ErrorDiagnostics._extract_key_error(result.stderr)
error_msg = format_error_message(error_desc, suggestions)
error_msg += f"\n\nFFmpeg原始错误:\n{first_error_line}"
```

---

## Bug #5【中等】错误诊断器 `"filter" / "scale"` 关键词匹配过于宽泛

**文件**: `src/core/error_handler.py:109-117`

```python
if "filter" in stderr_lower or "scale" in stderr_lower:
    return (
        "视频滤镜处理失败",
        [...]
    )
```

**问题**: 
- FFmpeg 的 stderr 输出中，"filter" 和 "scale" 是极其常见的词汇。例如：
  - `[libx264 @ ...]` 的输出中可能提到 "filter"
  - 输入流的元数据包含 `Stream #0:0: Video: ...` 包含 "scale" 在 codec 名字中
- 这个分支会匹配很多跟滤镜无关的错误（编码器问题、文件问题、内存问题等），导致诊断错误。
- 而且这个分支排在 "音频编码失败" 等分支的 **前面**，会截获真正的问题。

**修复方案**: 将通用匹配降为兜底分支（放在所有具体诊断之后），并增加更具体的匹配条件：
```python
# 移动到诊断函数的最后，作为兜底
# 添加更具体的 filter 错误模式匹配
if "filter_complex" in stderr_lower or "filtergraph" in stderr_lower or \
   "no such filter" in stderr_lower or "error while filtering" in stderr_lower:
    return (
        "视频滤镜处理失败",
        [...]
    )
```

---

## Bug #6【低】`_report_progress` 在滤镜构建阶段报告进度但命令实际未开始执行

**文件**: `src/core/video_processor.py:100`

```python
def _run_ffmpeg(self, cmd: list, description: str = "", context: dict = None) -> tuple:
    try:
        self._report_progress(0, f"正在{description}...")  # ← 进度 0%
        logger.info(f"执行FFmpeg命令: {description}")
        ...
```

在 `process_videos` 方法的调用链中：
```python
self._report_progress(0.1, "构建处理命令")  # ← line 261
# ... 构建 filter_complex ...
self._report_progress(0.2, "处理视频")  # ← line 415
success, error_msg = self._run_ffmpeg(cmd, "处理视频")  # ← 内部又 reset 到 0%
```

**问题**: `_run_ffmpeg` 将进度重置为 0%，导致 `processing_mixin.py` 中的全局进度计算混乱（line 137）：
```python
overall = ((task_index - 1 + progress) / total_tasks) * 100
```
当 `progress=0` 时，overall 进度会回退，UI 进度条看起来像卡住一样。

**修复方案**: 移除 `_run_ffmpeg` 中的 `_report_progress(0, ...)` 调用，或在 `_run_ffmpeg` 中增加 `start_progress` 参数避免总是从 0 开始。

---

## 改进建议 #1：增加滤镜参数生成后的验证

在 `process_videos()` 的 filter_complex 构建完成后、传给 FFmpeg 执行前，增加尺寸参数验证：

```python
def _validate_filter_params(self, out_width, out_height, split_ratio, target_split_ratio):
    """验证滤镜参数合法性"""
    errors = []
    if out_width < 2:
        errors.append(f"输出宽度过小({out_width}px)，需要至少2px")
    if out_height < 2:
        errors.append(f"输出高度过小({out_height}px)，需要至少2px")
    # 验证裁剪宽度
    part_width = int(out_width * split_ratio)
    if part_width < 1:
        errors.append(f"分割比例({split_ratio})导致裁剪宽度({part_width})为0")
    if errors:
        raise ValueError("; ".join(errors))
```

---

## 改进建议 #2：FFmpeg 命令执行增加超时保护

当前 FFmpeg 子进程没有超时限制 (`subprocess.run` 没有 timeout 参数)，如果视频损坏导致 FFmpeg 卡死，程序将永久挂起。

```python
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=600,  # 10分钟超时
    ...
)
```

---

## 总结

| 优先级 | 编号 | 问题 | 影响 |
|--------|------|------|------|
| P0 | Bug #1 | `_make_even` 返回 0 | 直接导致 FFmpeg 滤镜失败 |
| P0 | Bug #4 | FFmpeg stderr 丢失 | 无法定位真实错误原因 |
| P1 | Bug #2 | crop 偏移量为负数 | 特定组合下 FFmpeg 崩溃 |
| P1 | Bug #3 | 双重缩放导致 aspect_ratio 失真 | 非拉伸模式下输出变形 |
| P2 | Bug #5 | 错误诊断过度宽泛 | 误报问题原因 |
| P3 | Bug #6 | 进度回调被重置 | UI 进度条体验差 |

**根因分析**: 本次用户报错的"视频滤镜处理失败"最可能由 Bug #1 + Bug #4 组合导致：
1. 某些边界输入产生了 0 值的滤镜参数
2. FFmpeg 报错但具体原因被丢弃，用户只看到通用错误消息
3. 日志中没有记录 stderr（DEBUG 级别），无法事后回溯

**修复优先级建议**: 先修 Bug #1 和 Bug #4（加入 ERROR 级别日志），重新运行看 FFmpeg 的原始错误输出，再针对性修复。
