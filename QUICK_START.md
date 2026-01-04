# 快速开始 - GitHub Actions 自动打包

## 最简单的方法（3 步完成）

### 步骤 1: 创建 GitHub 仓库

1. 访问 https://github.com/new
2. 填写仓库名称（如 `video_pin`）
3. 选择 Public（公开）或 Private（私有）
4. 点击 "Create repository"
5. **复制**仓库地址（如 `https://github.com/username/video_pin.git`）

### 步骤 2: 上传代码

**方法 A：使用自动化脚本（推荐）**

1. 双击运行 `setup_github.bat`
2. 粘贴仓库地址
3. 按提示操作

**方法 B：手动上传（适合不熟悉 Git 的用户）**

1. 在 GitHub 仓库页面点击 "uploading an existing file"
2. 拖拽以下文件到页面：
   ```
   main.py
   video_processor.py
   utils.py
   .github/workflows/build.yml
   ```
3. 点击 "Commit changes"

### 步骤 3: 触发自动打包

1. 进入 GitHub 仓库
2. 点击顶部 **"Actions"** 标签
3. 左侧选择 **"Build and Release"**
4. 右侧点击 **"Run workflow"** → **"Run workflow"**
5. 等待 5-10 分钟
6. 完成后点击构建任务，下载底部的 **Artifacts**

## 下载构建结果

### 位置
```
仓库页面 → Actions → 最新构建任务 → 滚动到底部 → Artifacts
```

### 文件
- **windows-build** - Windows 版本（含 FFmpeg）
- **macos-build** - macOS 版本

## 创建正式发布版本

如果想在 Releases 页面显示：

```bash
# 在项目目录打开命令行/终端
git tag v1.0.0
git push origin v1.0.0
```

然后自动在 Releases 页面创建下载链接。

## 常见问题

### ❌ Actions 标签不显示？

**原因**: 没有上传 `.github/workflows/build.yml` 文件

**解决**:
1. 确保文件路径正确：`.github/workflows/build.yml`
2. 重新上传此文件
3. 刷新 GitHub 页面

### ❌ 构建失败？

**检查步骤**:
1. Actions → 点击失败的任务
2. 点击左侧 "build-windows" 或 "build-macos"
3. 查看红色 ❌ 的步骤
4. 检查错误信息

**常见错误**:
- `No module named 'xxx'` → 缺少依赖，在 build.yml 的 `pip install` 行添加
- `SyntaxError` → 代码语法错误，本地先测试

### ❌ 无法下载 Artifacts？

**原因**: Artifacts 有 90 天过期时间

**解决**:
1. 重新运行 workflow
2. 或使用 git tag 创建 Release（永久保存）

### ❓ 如何更新版本？

```bash
# 1. 修改代码
# 2. 提交更改
git add .
git commit -m "更新功能"
git push

# 3. 手动触发 Actions
# 或创建新标签
git tag v1.1.0
git push origin v1.1.0
```

## 完整工作流

```
修改代码
   ↓
git add .
git commit -m "..."
git push
   ↓
GitHub Actions 触发（手动或标签）
   ↓
Windows + macOS 并行构建（5-10分钟）
   ↓
下载 Artifacts 或 Release
   ↓
发给用户使用
```

## 费用说明

- ✅ **公开仓库**: 完全免费，无限制
- ⚠️ **私有仓库**: 免费账户每月 2000 分钟
  - 每次构建约 10 分钟 = 可运行 200 次/月
  - 绝对够用

## 获取帮助

- 详细文档：`GITHUB_ACTIONS_GUIDE.md`
- GitHub Actions 状态：https://www.githubstatus.com/
- 提问：在仓库创建 Issue

---

**就这么简单！3 步完成自动化打包** 🎉
