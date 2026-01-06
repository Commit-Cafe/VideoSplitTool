# GitHub 自动打包完整指南

本指南将手把手教您如何使用GitHub Actions自动打包Windows和macOS版本。

---

## 📋 前提条件

- ✅ 您已有GitHub账号
- ✅ 代码已经在本地准备好（就是当前的video_pin目录）
- ✅ 已安装Git（检查方法：打开cmd输入 `git --version`）

---

## 🚀 步骤1：初始化Git仓库并推送到GitHub

### 方法A：使用命令行（推荐）

#### 1.1 打开命令提示符
```bash
# 按 Win + R，输入 cmd，回车
# 进入项目目录
cd D:\mpower_project\video_pin
```

#### 1.2 初始化Git（如果还没有）
```bash
# 检查是否已经是Git仓库
git status

# 如果提示"不是 git 仓库"，执行：
git init
```

#### 1.3 配置Git用户信息（首次使用需要）
```bash
git config --global user.name "你的GitHub用户名"
git config --global user.email "你的GitHub邮箱"
```

#### 1.4 添加所有文件
```bash
git add .
```

#### 1.5 创建第一次提交
```bash
git commit -m "V2.1 稳定性改进版本"
```

#### 1.6 在GitHub创建仓库

1. 打开浏览器访问: https://github.com/new
2. **Repository name**: `video-split-tool` （或您喜欢的名称）
3. **Description**: `视频分割拼接工具 - 专业的视频处理软件`
4. **Public** 或 **Private**（选择私有如果不想公开）
5. **不要勾选** "Initialize this repository with a README"
6. 点击 **Create repository**

#### 1.7 关联远程仓库并推送
```bash
# 复制GitHub显示的仓库URL，例如：
# https://github.com/你的用户名/video-split-tool.git

# 添加远程仓库
git remote add origin https://github.com/你的用户名/video-split-tool.git

# 推送代码
git branch -M main
git push -u origin main
```

如果提示需要登录：
- 输入GitHub用户名
- 密码需要使用**Personal Access Token**（见下方）

---

### 创建GitHub Personal Access Token（如果需要）

如果推送时提示需要密码，需要创建Token：

1. 访问: https://github.com/settings/tokens
2. 点击 **Generate new token** → **Generate new token (classic)**
3. Note: `video-split-tool-upload`
4. Expiration: `90 days` （或更长）
5. 勾选权限：
   - ✅ `repo` (所有子项)
   - ✅ `workflow`
6. 点击 **Generate token**
7. **复制Token**（只显示一次，一定要保存！）
8. 在命令行输入密码时，粘贴这个Token

---

### 方法B：使用GitHub Desktop（图形化界面）

#### 2.1 下载安装
https://desktop.github.com/

#### 2.2 登录GitHub账号

#### 2.3 添加本地仓库
1. File → Add Local Repository
2. 选择 `D:\mpower_project\video_pin`
3. 如果提示"not a git repository"，点击 "Create a repository"

#### 2.4 发布到GitHub
1. 点击 **Publish repository**
2. Name: `video-split-tool`
3. Description: `视频分割拼接工具`
4. 取消勾选 "Keep this code private"（如果想公开）
5. 点击 **Publish repository**

#### 2.5 提交更改
1. 左侧会显示所有更改的文件
2. 在Summary输入: `V2.1 稳定性改进版本`
3. 点击 **Commit to main**
4. 点击 **Push origin**

---

## 🔧 步骤2：配置GitHub Actions权限

### 2.1 进入仓库设置
访问: `https://github.com/你的用户名/video-split-tool/settings`

### 2.2 配置Workflow权限
1. 左侧菜单点击 **Actions** → **General**
2. 滚动到 **Workflow permissions**
3. 选择 **Read and write permissions**
4. ✅ 勾选 **Allow GitHub Actions to create and approve pull requests**
5. 点击 **Save**

---

## 📦 步骤3：触发自动打包

现在有两种方式打包：

### 方式1: 手动触发（测试用）

这种方式适合测试，不会创建正式Release。

#### 3.1 访问Actions页面
`https://github.com/你的用户名/video-split-tool/actions`

#### 3.2 触发构建
1. 左侧点击 **Build (Manual Download)**
2. 右侧点击 **Run workflow**
3. Branch选择 **main**
4. 点击绿色的 **Run workflow** 按钮

#### 3.3 等待构建完成
- 构建时间：约5-10分钟
- Windows构建：约3-5分钟
- macOS构建：约3-5分钟

#### 3.4 下载构建文件
1. 等待构建完成（绿色✓）
2. 点击构建任务
3. 滚动到页面底部
4. 在 **Artifacts** 区域下载：
   - `windows-build` - Windows版本
   - `macos-build` - macOS版本

**注意**: Artifacts保留7天后会自动删除。

---

### 方式2: 创建标签（正式发布）

这种方式会自动创建Release页面，用户可以直接下载。

#### 4.1 确保代码已推送
```bash
git status  # 确保没有未提交的更改
```

#### 4.2 创建版本标签
```bash
# 创建v2.1.0标签
git tag v2.1.0

# 推送标签到GitHub
git push origin v2.1.0
```

#### 4.3 自动构建
推送标签后，GitHub Actions会自动：
1. 构建Windows版本
2. 构建macOS版本
3. 创建GitHub Release
4. 上传安装包到Release

#### 4.4 查看Release
访问: `https://github.com/你的用户名/video-split-tool/releases`

您会看到自动创建的 **v2.1.0** Release，包含：
- `VideoSplitTool_Windows_YYYYMMDD.zip`
- `VideoSplitTool_macOS_YYYYMMDD.zip`

---

## 🎯 步骤4：分享给用户

### 4.1 获取下载链接
```
Windows版本:
https://github.com/你的用户名/video-split-tool/releases/download/v2.1.0/VideoSplitTool_Windows_YYYYMMDD.zip

macOS版本:
https://github.com/你的用户名/video-split-tool/releases/download/v2.1.0/VideoSplitTool_macOS_YYYYMMDD.zip
```

### 4.2 或者提供Release页面
```
https://github.com/你的用户名/video-split-tool/releases/latest
```

---

## 🔄 步骤5：更新版本（后续）

当您修改代码后，想发布新版本：

### 5.1 提交代码更改
```bash
git add .
git commit -m "修复bug：xxx"
git push
```

### 5.2 创建新标签
```bash
# 创建v2.1.1标签
git tag v2.1.1

# 推送标签
git push origin v2.1.1
```

### 5.3 自动构建
GitHub Actions会自动构建并创建新的Release。

---

## ❓ 常见问题

### Q1: 推送代码时提示权限错误
**A**: 确保使用Personal Access Token作为密码，而不是GitHub账号密码。

### Q2: Actions构建失败
**A**:
1. 点击失败的任务查看详细日志
2. 检查是否配置了 "Read and write permissions"
3. 参考 `FIX_RELEASE_ERROR.md` 排查

### Q3: 创建Release失败
**A**:
1. 确保配置了Workflow权限
2. 检查标签格式是否正确（如v2.1.0）
3. 不要重复使用相同的标签

### Q4: Artifacts下载后是zip套zip
**A**: 这是正常的，解压两次即可：
```
windows-build.zip
  └─ VideoSplitTool_Windows_20260104.zip
       └─ VideoSplitTool.exe
       └─ ffmpeg/
```

### Q5: 构建很慢
**A**:
- Windows构建：3-5分钟（正常）
- macOS构建：3-5分钟（正常）
- 总共：6-10分钟（正常）

如果超过15分钟，可能是GitHub服务器繁忙。

---

## 📊 两种打包方式对比

| 特性 | 手动触发 | 标签触发 |
|------|---------|---------|
| 触发方式 | 点击Run workflow | 推送标签 |
| 创建Release | ❌ 否 | ✅ 是 |
| 下载方式 | Artifacts（7天有效） | Release（永久） |
| 适用场景 | 测试、开发 | 正式发布 |
| 推荐用途 | 内部测试 | 用户下载 |

---

## 🎓 快速命令参考

```bash
# === 首次推送 ===
cd D:\mpower_project\video_pin
git init
git add .
git commit -m "V2.1 稳定性改进版本"
git remote add origin https://github.com/你的用户名/video-split-tool.git
git branch -M main
git push -u origin main

# === 更新代码 ===
git add .
git commit -m "更新说明"
git push

# === 创建Release ===
git tag v2.1.0
git push origin v2.1.0

# === 删除错误的标签 ===
git tag -d v2.1.0                    # 删除本地标签
git push origin :refs/tags/v2.1.0    # 删除远程标签

# === 查看状态 ===
git status                           # 查看当前状态
git log --oneline                    # 查看提交历史
git remote -v                        # 查看远程仓库
```

---

## 🛠️ 故障排除

### 场景1: create-release任务失败

**症状**:
- build-windows ✅
- build-macos ✅
- create-release ❌

**解决方法**: 参考 `FIX_RELEASE_ERROR.md`

---

### 场景2: 手动触发时create-release被跳过

**症状**: create-release显示 ⚠️（黄色感叹号）

**原因**: 正常现象，手动触发不会创建Release

**解决方法**: 使用Artifacts下载，或使用标签触发

---

### 场景3: FFmpeg下载失败

**症状**: Windows构建失败，提示下载FFmpeg错误

**解决方法**: 重新运行构建（GitHub Actions右上角 "Re-run all jobs"）

---

## 📞 需要帮助？

如果遇到问题：

1. **查看日志**: Actions页面 → 点击失败的任务 → 查看详细日志
2. **查看文档**:
   - `FIX_RELEASE_ERROR.md` - Release错误修复
   - `GITHUB_ACTIONS_GUIDE.md` - GitHub Actions详细指南
3. **提交Issue**: 在仓库中创建Issue描述问题

---

## ✅ 检查清单

在推送到GitHub之前，确保：

- [ ] 所有代码已提交
- [ ] 测试通过（运行 `python test_improvements.py`）
- [ ] 版本号已更新
- [ ] CHANGELOG已更新
- [ ] README已更新
- [ ] 没有敏感信息（密码、Token等）

在创建Release之前，确保：

- [ ] 代码已推送到GitHub
- [ ] Workflow权限已配置
- [ ] 标签格式正确（如v2.1.0）
- [ ] 标签未重复使用

---

**祝您打包顺利！** 🎉

如有问题，请参考本指南的故障排除章节。
