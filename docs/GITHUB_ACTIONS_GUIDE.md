# GitHub Actions 自动打包指南

## 什么是 GitHub Actions？

GitHub Actions 是 GitHub 提供的免费 CI/CD 服务，可以自动在 Windows 和 macOS 虚拟机上构建应用程序。

## 优势

✅ **完全免费** - 公开仓库无限制使用
✅ **自动化** - 推送代码即可自动打包
✅ **多平台** - 同时生成 Windows 和 macOS 版本
✅ **可靠** - GitHub 官方提供的虚拟机环境

## 快速开始

### 步骤 1：创建 GitHub 仓库

1. 访问 https://github.com/new
2. 创建新仓库（可以是公开或私有）
3. 记下仓库地址，例如：`https://github.com/username/video_pin`

### 步骤 2：上传代码到 GitHub

**方法一：使用 Git 命令行**

```bash
# 在项目目录中初始化 Git
cd D:\mpower_project\video_pin
git init

# 添加所有文件
git add .

# 创建首次提交
git commit -m "Initial commit"

# 关联远程仓库（替换成你的仓库地址）
git remote add origin https://github.com/username/video_pin.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

**方法二：使用 GitHub Desktop**

1. 下载安装 GitHub Desktop：https://desktop.github.com/
2. 打开 GitHub Desktop
3. File → Add Local Repository → 选择项目目录
4. 点击 "Publish repository"

**方法三：直接上传文件**

1. 在 GitHub 仓库页面点击 "Add file" → "Upload files"
2. 拖拽所有项目文件到页面
3. 点击 "Commit changes"

### 步骤 3：触发自动打包

有两种触发方式：

#### 方式 A：手动触发（推荐，用于测试）

1. 进入 GitHub 仓库页面
2. 点击顶部 "Actions" 标签
3. 左侧选择 "Build and Release"
4. 点击右侧 "Run workflow" 按钮
5. 点击绿色的 "Run workflow" 确认

**等待 5-10 分钟**，构建完成后：
- 在 Actions 页面可以看到构建状态
- 点击构建任务查看详情
- 下载 Artifacts 中的 `windows-build` 和 `macos-build`

#### 方式 B：创建版本标签（自动发布到 Release）

```bash
# 创建版本标签
git tag v1.0.0

# 推送标签到 GitHub
git push origin v1.0.0
```

这会自动：
1. 在 Windows 和 macOS 上打包
2. 创建 GitHub Release
3. 上传两个平台的安装包

### 步骤 4：下载构建结果

#### 手动触发的结果：

1. Actions → 点击最新的构建任务
2. 滚动到底部找到 "Artifacts"
3. 下载：
   - `windows-build` - Windows 版本
   - `macos-build` - macOS 版本

#### 标签触发的结果：

1. 仓库页面右侧点击 "Releases"
2. 找到对应版本（如 v1.0.0）
3. 下载 Assets 中的文件：
   - `VideoSplitTool_Windows_20260104.zip`
   - `VideoSplitTool_macOS_20260104.zip`

## 详细说明

### 文件结构

上传到 GitHub 的项目需要包含：

```
video_pin/
├── .github/
│   └── workflows/
│       └── build.yml          # GitHub Actions 配置文件（已创建）
├── main.py                     # 主程序
├── video_processor.py          # 视频处理模块
├── utils.py                    # 工具函数
└── README.md                   # 项目说明（可选）
```

### 工作流程说明

**build.yml** 配置文件定义了三个任务：

1. **build-windows**
   - 在 Windows 虚拟机上运行
   - 安装 Python 和依赖
   - 使用 PyInstaller 打包
   - 自动下载 FFmpeg
   - 创建 ZIP 包

2. **build-macos**
   - 在 macOS 虚拟机上运行
   - 安装 Python 和依赖
   - 使用 PyInstaller 打包
   - 创建 ZIP 包（不包含 FFmpeg，用户需自行安装）

3. **create-release**
   - 仅在推送版本标签时运行
   - 创建 GitHub Release
   - 上传两个平台的安装包

### 触发条件

工作流在以下情况触发：

1. **手动触发**：Actions 页面点击 "Run workflow"
2. **版本标签**：推送 `v` 开头的标签（如 `v1.0.0`、`v2.1.3`）

### 构建时间

- Windows 构建：约 3-5 分钟
- macOS 构建：约 3-5 分钟
- 总时间：约 5-10 分钟（并行执行）

## 常见问题

### Q1: 如何查看构建日志？

1. Actions → 点击构建任务
2. 点击左侧的任务名（build-windows 或 build-macos）
3. 展开步骤查看详细日志

### Q2: 构建失败怎么办？

1. 检查日志中的错误信息
2. 常见问题：
   - **缺少依赖**：确保 `requirements.txt` 包含所有依赖
   - **语法错误**：在本地先测试代码
   - **路径问题**：使用相对路径而非绝对路径

### Q3: 如何修改配置？

编辑 `.github/workflows/build.yml` 文件，常见修改：

- **Python 版本**：修改 `python-version: '3.11'`
- **添加依赖**：在 `pip install` 行添加包名
- **修改文件名**：修改 `--name VideoSplitTool` 参数

### Q4: 私有仓库可以用吗？

可以，但有限制：
- **免费账户**：每月 2000 分钟
- **Pro 账户**：每月 3000 分钟
- **公开仓库**：无限制

### Q5: 如何添加版本号？

在代码中添加版本号：

```python
# main.py
VERSION = "2.0.0"
self.root.title(f"视频分割拼接工具 V{VERSION}")
```

推送标签时使用相同版本号：
```bash
git tag v2.0.0
git push origin v2.0.0
```

## 最佳实践

### 1. 使用语义化版本号

- `v1.0.0` - 主要版本（重大更新）
- `v1.1.0` - 次要版本（新功能）
- `v1.1.1` - 补丁版本（Bug 修复）

### 2. 编写 Release Notes

创建标签时添加说明：

```bash
git tag -a v1.0.0 -m "首次发布

新功能：
- 视频位置顺序配置
- 封面选帧实时预览
- 音频配置功能

修复：
- 封面拼接后音频丢失
"
git push origin v1.0.0
```

### 3. 本地测试后再推送

推送前确保：
```bash
# 测试主程序
python main.py

# 检查语法
python -m py_compile main.py video_processor.py utils.py
```

## 示例：完整发布流程

```bash
# 1. 修改代码，添加新功能
# ... 编辑代码 ...

# 2. 本地测试
python main.py

# 3. 提交代码
git add .
git commit -m "添加新功能：XXX"
git push

# 4. 创建版本标签
git tag v1.1.0
git push origin v1.1.0

# 5. 等待 GitHub Actions 完成（5-10分钟）

# 6. 在 GitHub Release 页面查看和下载
```

## 进阶配置

### 添加构建缓存（加速构建）

在 build.yml 中的 "Set up Python" 后添加：

```yaml
- name: Cache pip packages
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

### 添加自动测试

在打包前运行测试：

```yaml
- name: Run tests
  run: |
    pip install pytest
    pytest tests/
```

### 支持多个 Python 版本

```yaml
strategy:
  matrix:
    python-version: ['3.9', '3.10', '3.11']
```

## 获取帮助

- **GitHub Actions 文档**：https://docs.github.com/en/actions
- **PyInstaller 文档**：https://pyinstaller.org/
- **问题反馈**：在仓库中创建 Issue

## 总结

使用 GitHub Actions，您只需：
1. ✅ 上传代码到 GitHub
2. ✅ 点击 "Run workflow" 或推送标签
3. ✅ 等待 5-10 分钟
4. ✅ 下载 Windows 和 macOS 安装包

完全自动化，无需 Mac 电脑！
