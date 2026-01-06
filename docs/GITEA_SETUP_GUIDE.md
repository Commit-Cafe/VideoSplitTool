# 推送项目到 Gitea 完整指南

**更新日期**: 2026-01-05
**场景**: 项目已在GitHub，现在需要同时推送到Gitea

---

## 📋 目录

1. [在Gitea创建仓库](#步骤1在gitea创建仓库)
2. [添加Gitea远程仓库](#步骤2添加gitea远程仓库)
3. [推送到Gitea](#步骤3推送到gitea)
4. [配置多远程同步](#步骤4配置多远程同步可选)
5. [常用命令](#常用命令参考)

---

## 🎯 步骤1：在Gitea创建仓库

### 1.1 登录Gitea

访问你的Gitea服务器地址，例如：
```
https://gitea.example.com
或
http://192.168.1.100:3000
```

### 1.2 创建新仓库

1. 点击右上角 **"+"** → **"新建仓库"**
2. 填写仓库信息：
   - **仓库名称**: `video_pin`（与GitHub保持一致）
   - **可见性**: 私有/公开（根据需求选择）
   - **描述**: `视频分割拼接工具 V2.1`
   - **⚠️ 不要勾选** "使用 README 初始化仓库"
   - **⚠️ 不要选择** .gitignore 和 License
3. 点击 **"创建仓库"**

### 1.3 获取Gitea仓库地址

创建后会显示仓库地址，例如：
```
HTTPS: https://gitea.example.com/username/video_pin.git
SSH:   git@gitea.example.com:username/video_pin.git
```

**记录这个地址，后面会用到！**

---

## 🔗 步骤2：添加Gitea远程仓库

### 2.1 查看现有远程仓库

在PyCharm终端执行：

```bash
git remote -v
```

应该会看到：
```
origin  https://github.com/yuheng-ctrl/video_pin.git (fetch)
origin  https://github.com/yuheng-ctrl/video_pin.git (push)
```

### 2.2 添加Gitea作为第二个远程仓库

**方法A：添加为新的远程仓库（推荐）**

```bash
# 添加Gitea远程仓库，命名为 gitea
git remote add gitea https://gitea.example.com/username/video_pin.git

# 或者如果使用SSH
git remote add gitea git@gitea.example.com:username/video_pin.git
```

**验证添加成功**:
```bash
git remote -v
```

现在应该看到：
```
origin  https://github.com/yuheng-ctrl/video_pin.git (fetch)
origin  https://github.com/yuheng-ctrl/video_pin.git (push)
gitea   https://gitea.example.com/username/video_pin.git (fetch)
gitea   https://gitea.example.com/username/video_pin.git (push)
```

---

## 🚀 步骤3：推送到Gitea

### 3.1 推送所有分支

```bash
# 推送main分支到Gitea
git push gitea main

# 如果有其他分支也想推送
git push gitea --all

# 推送所有标签（如果有）
git push gitea --tags
```

### 3.2 设置上游分支（可选）

如果想让Gitea的main分支也作为上游分支：

```bash
git push -u gitea main
```

### 3.3 验证推送成功

访问Gitea仓库页面，应该能看到所有代码已经上传成功。

---

## ⚙️ 步骤4：配置多远程同步（可选）

如果你希望一次推送同时更新GitHub和Gitea，有两种方法：

### 方法A：配置origin推送到多个URL（推荐）

```bash
# 为origin添加第二个push URL
git remote set-url --add --push origin https://gitea.example.com/username/video_pin.git

# 再添加回GitHub的URL（因为上面的命令会覆盖原有的）
git remote set-url --add --push origin https://github.com/yuheng-ctrl/video_pin.git
```

**验证配置**:
```bash
git remote -v
```

应该看到：
```
origin  https://github.com/yuheng-ctrl/video_pin.git (fetch)
origin  https://github.com/yuheng-ctrl/video_pin.git (push)
origin  https://gitea.example.com/username/video_pin.git (push)
gitea   https://gitea.example.com/username/video_pin.git (fetch)
gitea   https://gitea.example.com/username/video_pin.git (push)
```

**现在执行 `git push` 会同时推送到GitHub和Gitea！**

### 方法B：创建推送脚本

创建一个批处理脚本自动推送到两个仓库。

**Windows (`push_all.bat`)**:
```batch
@echo off
echo Pushing to GitHub...
git push origin main
if %errorlevel% neq 0 (
    echo GitHub push failed!
    pause
    exit /b 1
)

echo.
echo Pushing to Gitea...
git push gitea main
if %errorlevel% neq 0 (
    echo Gitea push failed!
    pause
    exit /b 1
)

echo.
echo All pushes successful!
pause
```

**使用**:
```bash
push_all.bat
```

---

## 📚 常用命令参考

### 查看远程仓库

```bash
# 查看所有远程仓库
git remote -v

# 查看远程仓库详细信息
git remote show origin
git remote show gitea
```

### 推送操作

```bash
# 推送到GitHub
git push origin main

# 推送到Gitea
git push gitea main

# 同时推送到所有远程仓库（如果配置了方法A）
git push

# 强制推送（谨慎使用）
git push gitea main --force
```

### 拉取操作

```bash
# 从GitHub拉取
git pull origin main

# 从Gitea拉取
git pull gitea main
```

### 管理远程仓库

```bash
# 重命名远程仓库
git remote rename gitea my-gitea

# 删除远程仓库
git remote remove gitea

# 修改远程仓库URL
git remote set-url gitea https://new-gitea.example.com/username/video_pin.git
```

### 标签操作

```bash
# 推送单个标签到Gitea
git push gitea v2.1.0

# 推送所有标签到Gitea
git push gitea --tags

# 删除远程标签
git push gitea :refs/tags/v2.1.0
```

---

## 🔧 常见问题

### Q1: 推送时提示认证失败

**问题**:
```
remote: HTTP Basic: Access denied
fatal: Authentication failed
```

**解决方法**:

**HTTPS方式** - 使用访问令牌：

1. 在Gitea生成访问令牌：
   - 设置 → 应用 → 管理访问令牌
   - 点击"生成新令牌"
   - 选择权限（至少需要 `repo`）
   - 复制生成的令牌

2. 使用令牌推送：
```bash
# 方式1：在URL中包含令牌
git remote set-url gitea https://username:TOKEN@gitea.example.com/username/video_pin.git

# 方式2：推送时输入用户名和令牌
git push gitea main
# Username: 你的用户名
# Password: 粘贴访问令牌（不是密码）
```

**SSH方式** - 配置SSH密钥：

1. 生成SSH密钥（如果没有）：
```bash
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
```

2. 复制公钥：
```bash
cat ~/.ssh/id_rsa.pub
```

3. 在Gitea添加SSH密钥：
   - 设置 → SSH/GPG 密钥 → 添加密钥
   - 粘贴公钥内容

4. 修改远程URL为SSH：
```bash
git remote set-url gitea git@gitea.example.com:username/video_pin.git
```

---

### Q2: 推送失败，提示 "non-fast-forward"

**问题**:
```
! [rejected]        main -> main (non-fast-forward)
error: failed to push some refs
```

**原因**: Gitea仓库有你本地没有的提交（例如在创建时添加了README）

**解决方法**:

**方法1：拉取后再推送**
```bash
git pull gitea main --allow-unrelated-histories
git push gitea main
```

**方法2：强制推送（会覆盖Gitea上的内容）**
```bash
git push gitea main --force
```

---

### Q3: 如何只同步到Gitea，不同步GitHub Actions配置？

**问题**: GitHub Actions的`.github/workflows/`目录可能在Gitea上不需要

**解决方法**:

**方法1：推送时排除某些文件（不推荐，无法实现）**

**方法2：在Gitea上手动删除**
```bash
# 克隆Gitea仓库
git clone https://gitea.example.com/username/video_pin.git video_pin_gitea
cd video_pin_gitea

# 删除不需要的文件
git rm -r .github/
git commit -m "Remove GitHub Actions config"
git push
```

**方法3：维护两个分支**
- `main` - 包含所有内容（推送到GitHub）
- `main-gitea` - 不包含GitHub特定内容（推送到Gitea）

---

### Q4: 推送大文件报错

**问题**:
```
error: RPC failed; HTTP 413 curl 22 The requested URL returned error: 413
```

**原因**: Gitea服务器配置了文件大小限制

**解决方法**:

1. 增加Git缓冲区：
```bash
git config http.postBuffer 524288000  # 500MB
```

2. 确认文件已在`.gitignore`中：
```bash
# 查看哪些大文件被追踪
git ls-files | xargs ls -lh | sort -k5 -hr | head -20

# 如果FFmpeg文件还在，移除它们
git rm -r --cached ffmpeg-8.0.1-full_build/
git commit -m "Remove large files"
```

3. 联系Gitea管理员增加上传限制（如果是自建）

---

### Q5: 如何在两个远程仓库间同步？

**场景**: GitHub上有新的提交，想同步到Gitea

**操作**:
```bash
# 从GitHub拉取最新代码
git pull origin main

# 推送到Gitea
git push gitea main
```

**或者一次性操作**:
```bash
# 拉取GitHub
git fetch origin

# 直接推送到Gitea
git push gitea origin/main:main
```

---

## 🎯 推荐工作流程

### 日常开发流程

**如果配置了方法A（一次推送到多个远程）**:

```bash
# 1. 修改代码
# ...

# 2. 提交
git add .
git commit -m "Update: 新功能"

# 3. 推送（自动推送到GitHub和Gitea）
git push
```

**如果没有配置多远程推送**:

```bash
# 1. 修改代码
# ...

# 2. 提交
git add .
git commit -m "Update: 新功能"

# 3. 推送到GitHub
git push origin main

# 4. 推送到Gitea
git push gitea main
```

### 发布新版本流程

```bash
# 1. 创建标签
git tag v2.1.0
git tag -a v2.1.1 -m "Release V2.1.1"

# 2. 推送标签到GitHub（触发Actions构建）
git push origin v2.1.1

# 3. 推送标签到Gitea（备份）
git push gitea v2.1.1

# 或者一次性推送所有标签
git push --tags origin
git push --tags gitea
```

---

## 📊 不同场景的推荐配置

### 场景1: GitHub为主，Gitea备份

```bash
# 保持独立的远程仓库
git remote add gitea <gitea-url>

# 日常推送到GitHub
git push origin main

# 定期同步到Gitea
git push gitea main
```

### 场景2: 同时维护两个仓库

```bash
# 配置一次推送到多个远程
git remote set-url --add --push origin <gitea-url>
git remote set-url --add --push origin <github-url>

# 一次推送更新所有
git push
```

### 场景3: 不同分支推送到不同远程

```bash
# main分支推送到GitHub
git push origin main

# develop分支推送到Gitea（内部开发）
git push gitea develop
```

---

## 🔒 安全建议

1. **使用SSH而非HTTPS** - 更安全，无需每次输入密码
2. **访问令牌权限最小化** - 只授予必要的权限
3. **定期轮换访问令牌** - 建议每3-6个月更换
4. **不要在代码中硬编码凭证** - 使用Git凭证管理器
5. **私有仓库敏感信息** - 确保`.env`等文件在`.gitignore`中

---

## 📝 总结

**完整操作流程**:

```bash
# 1. 在Gitea创建仓库（Web界面）

# 2. 添加Gitea远程仓库
git remote add gitea https://gitea.example.com/username/video_pin.git

# 3. 推送代码
git push gitea main

# 4. 推送标签（如果有）
git push gitea --tags

# 5. （可选）配置多远程推送
git remote set-url --add --push origin https://gitea.example.com/username/video_pin.git
git remote set-url --add --push origin https://github.com/yuheng-ctrl/video_pin.git
```

**后续维护**:
```bash
# 日常推送（如果配置了多远程）
git push

# 或者分别推送
git push origin main
git push gitea main
```

---

**完成！现在你的代码同时在GitHub和Gitea上维护了！** 🎉
