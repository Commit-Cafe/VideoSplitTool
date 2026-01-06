# 桌面版 V2.2 优化方案

**优化日期**: 2026-01-05
**问题来源**: 用户反馈
**目标**: 优化16:9竖屏视频拼接体验

---

## 📋 用户反馈的问题

### 问题1: 竖屏视频拼接后变成长条

**现象**:
- 用户处理16:9竖屏视频（如手机竖屏拍摄）
- 左右拼接后输出变成很长的横条
- 上下拼接后输出变成很长的竖条

**原因**:
- 当前代码按照原视频尺寸进行拼接
- 没有提供输出尺寸的自定义选项
- 16:9竖屏(1080x1920) 左右拼接 → 2160x1920（超宽屏）

**示例**:
```
模板视频: 1080x1920 (竖屏)
列表视频: 1080x1920 (竖屏)

当前输出（左右拼接）: 2160x1920 ❌ 长条

期望输出: 1080x1920 ✅ 保持竖屏比例
```

### 问题2: 缺少视频尺寸信息

**现象**:
- 用户不知道视频的实际尺寸
- 不清楚拼接后的输出尺寸

**需求**:
- 显示模板视频尺寸
- 显示列表视频尺寸
- 显示预计输出尺寸

### 问题3: 位置顺序显示不友好

**现象**:
- 显示"A+C"、"B+D"等组合
- 用户看不懂什么是A、B、C、D
- 选择B+C拼接时，显示很奇怪

**需求**:
- 改为友好的文字描述
- "模板视频在左/上"
- "列表视频在左/上"

### 问题4: 缺少拼接效果预览

**现象**:
- 用户不知道拼接后的效果
- 需要处理完才能看到结果

**需求**:
- 添加可视化预览
- 显示拼接布局示意图

### 问题5: 封面帧显示问题

**现象**:
- 选择"拼接后视频"封面时显示不正确
- 封面时长默认3秒太长

**需求**:
- 修复拼接视频封面显示
- 默认封面时长改为1秒

---

## ✅ 优化方案

### 优化1: 修改封面默认时长 ✅ 已完成

**修改位置**: `main.py:29`

```python
# 修改前
self.cover_duration = 3.0       # 封面显示时长(秒)

# 修改后
self.cover_duration = 1.0       # 封面显示时长(秒)
```

---

### 优化2: 添加视频尺寸显示

**修改位置**: 主界面

**新增功能**:
1. 模板视频区域显示：`1920x1080 (横屏)` 或 `1080x1920 (竖屏)`
2. 列表视频编辑界面显示当前视频尺寸
3. 输出设置区域显示预计输出尺寸

**UI设计**:
```
┌─ 模板视频 ────────────────────────┐
│ 路径: D:\video.mp4              │
│ 尺寸: 1080x1920 (9:16 竖屏)     │ ← 新增
│ 时长: 00:30                      │
└──────────────────────────────────┘
```

**代码修改**:
```python
def _load_preview(self, video_path):
    # 获取视频信息
    info = get_video_info(video_path)
    if info:
        width = info['width']
        height = info['height']

        # 判断方向
        if width > height:
            orientation = "横屏"
            aspect_ratio = f"{width}:{height}"
        elif height > width:
            orientation = "竖屏"
            aspect_ratio = f"{width}:{height}"
        else:
            orientation = "正方形"
            aspect_ratio = "1:1"

        # 显示信息
        self.video_info_var.set(
            f"尺寸: {width}x{height} ({aspect_ratio} {orientation}), "
            f"时长: {format_duration(info['duration'])}"
        )
```

---

### 优化3: 优化位置顺序显示

**修改位置**: `main.py:898-959` (_on_merge_change方法)

**修改前**:
```
拼接方式: A+C (模板在前)
将生成 4 个视频: A+C, A+D, B+C, B+D (模板在前)
```

**修改后**:
```
拼接方式: 模板视频在左 + 列表视频在右
将生成 4 个视频 (模板视频在左):
  - 模板左侧 + 列表左侧
  - 模板左侧 + 列表右侧
  - 模板右侧 + 列表左侧
  - 模板右侧 + 列表右侧
```

**代码修改**:
```python
def _on_merge_change(self):
    """当拼接部分勾选变化时更新预览说明"""
    mode = self.split_mode.get()
    is_template_first = self.position_order.get() == "template_first"

    # 获取方向名称
    if mode == "horizontal":
        first_side = "左"
        second_side = "右"
    else:
        first_side = "上"
        second_side = "下"

    # 根据位置顺序确定文字
    if is_template_first:
        template_position = first_side
        list_position = second_side
    else:
        template_position = second_side
        list_position = first_side

    # 生成友好的描述
    desc = f"模板视频在{template_position}，列表视频在{list_position}"

    self.merge_preview_var.set(desc)
```

---

### 优化4: 添加输出尺寸配置

**新增功能**: 用户可以自定义输出视频尺寸

**UI设计**:
```
┌─ 输出设置 ────────────────────────┐
│ □ 自动尺寸（保持模板视频尺寸）    │
│ ☑ 自定义尺寸                      │
│   宽度: [1080] 像素               │
│   高度: [1920] 像素               │
│   预设: [竖屏1080p▼] [应用]       │
│                                    │
│ 预计输出: 1080x1920               │
└───────────────────────────────────┘
```

**预设选项**:
- 横屏1080p (1920x1080)
- 横屏720p (1280x720)
- 竖屏1080p (1080x1920)
- 竖屏720p (720x1280)
- 正方形1080 (1080x1080)
- 正方形720 (720x720)

**VideoItem扩展**:
```python
class VideoItem:
    def __init__(self, path):
        # ... 现有字段
        self.output_width = None   # None表示自动
        self.output_height = None  # None表示自动
```

**VideoSplitApp扩展**:
```python
class VideoSplitApp:
    def __init__(self, root):
        # ... 现有初始化
        self.use_custom_size = tk.BooleanVar(value=False)
        self.output_width = tk.IntVar(value=1920)
        self.output_height = tk.IntVar(value=1080)
```

---

### 优化5: 添加拼接效果可视化预览

**新增功能**: 在主界面显示拼接布局示意图

**UI设计**:
```
┌─ 拼接预览 ────────────────────────┐
│                                    │
│  ┌─────────┬──────────┐           │
│  │         │          │           │
│  │  模板   │   列表   │  ← 左右拼接│
│  │  视频   │   视频   │           │
│  │         │          │           │
│  └─────────┴──────────┘           │
│                                    │
│  拼接方式: 模板在左，列表在右      │
│  输出尺寸: 1920x1080              │
└────────────────────────────────────┘
```

**实现方式**:
使用Canvas绘制示意图

```python
def _draw_merge_preview(self):
    """绘制拼接效果示意图"""
    self.preview_canvas.delete("all")

    canvas_w = 300
    canvas_h = 200

    mode = self.split_mode.get()
    is_template_first = self.position_order.get() == "template_first"

    if mode == "horizontal":
        # 左右分割
        left_w = int(canvas_w * 0.5)

        if is_template_first:
            # 模板在左
            self.preview_canvas.create_rectangle(
                0, 0, left_w, canvas_h,
                fill="#E3F2FD", outline="#2196F3", width=2
            )
            self.preview_canvas.create_text(
                left_w//2, canvas_h//2,
                text="模板\n视频", font=("Arial", 12, "bold")
            )

            self.preview_canvas.create_rectangle(
                left_w, 0, canvas_w, canvas_h,
                fill="#FFF3E0", outline="#FF9800", width=2
            )
            self.preview_canvas.create_text(
                left_w + (canvas_w-left_w)//2, canvas_h//2,
                text="列表\n视频", font=("Arial", 12, "bold")
            )
        else:
            # 列表在左（相反）
            # ...
    else:
        # 上下分割
        # ...
```

---

### 优化6: 修复封面帧显示问题

**问题分析**:
当前代码在生成"拼接后视频"封面时，可能没有正确获取merge_mode参数。

**修改位置**: `main.py:430-510` (_generate_merged_preview方法)

**检查点**:
1. 确保merge_mode正确传递
2. 确保视频路径正确
3. 确保临时文件清理

**代码审查**:
```python
def _generate_merged_preview(self, template_path, list_path, time_pos):
    """生成拼接预览帧"""
    try:
        # 获取第一个拼接组合
        combinations = self._get_merge_combinations()
        if not combinations:
            return None

        merge_mode = combinations[0]  # 使用第一个组合

        # ⚠️ 确保这里的merge_mode传递正确
        logger.debug(f"生成拼接预览，merge_mode={merge_mode}")

        # ... 后续处理
```

**修复建议**:
添加更详细的日志和错误处理，确保封面生成过程可追踪。

---

## 🎯 实施计划

### Phase 1: 基础优化（立即实施）

**任务**:
- [x] 修改封面默认时长为1秒
- [ ] 添加视频尺寸显示
- [ ] 优化位置顺序显示文案

**时间**: 1-2小时
**风险**: 低

### Phase 2: 高级功能（后续实施）

**任务**:
- [ ] 添加输出尺寸配置
- [ ] 添加拼接效果预览
- [ ] 修复封面帧显示问题

**时间**: 3-4小时
**风险**: 中

---

## 📝 测试计划

### 测试场景1: 竖屏视频

**输入**:
- 模板视频: 1080x1920 (竖屏)
- 列表视频: 1080x1920 (竖屏)
- 拼接方式: 左右

**期望输出**:
- 自动模式: 2160x1920
- 自定义模式: 1080x1920 (保持竖屏)

### 测试场景2: 混合尺寸

**输入**:
- 模板视频: 1920x1080 (横屏)
- 列表视频: 1080x1920 (竖屏)

**期望**:
- 正确缩放适配
- 输出尺寸可控

---

## 🚀 下一步

1. **立即实施** Phase 1 优化
2. **测试验证** 基础功能
3. **用户反馈** 收集意见
4. **继续开发** Phase 2 功能

---

**准备开始优化了吗？** 🎬
