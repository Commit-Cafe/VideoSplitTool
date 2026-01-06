# Create-Release 失败问题修复

## 问题诊断

### 情况 A：任务被跳过（⚠️ 黄色感叹号）

**原因**: 手动触发 workflow 时，`create-release` 任务会被跳过，因为它只在推送标签时运行。

**这是正常的！** 不影响使用。

**解决方法**: 直接下载 Artifacts

1. 点击构建任务
2. 滚动到页面底部
3. 找到 **Artifacts** 区域
4. 下载：
   - `windows-build` - Windows 版本
   - `macos-build` - macOS 版本

---

### 情况 B：真的失败了（❌ 红色叉号）

点击查看错误信息，常见错误：

#### 错误 1: Resource not accessible by integration

```
Error: Resource not accessible by integration
```

**原因**: 仓库权限设置问题

**修复步骤**:

1. 进入仓库页面
2. Settings → Actions → General
3. 滚动到 **Workflow permissions**
4. 选择 **"Read and write permissions"**
5. ✅ 勾选 **"Allow GitHub Actions to create and approve pull requests"**
6. 点击 **Save**
7. 重新运行 workflow

#### 错误 2: Unable to create release

```
Error: Unable to create release: Bad credentials
```

**原因**: GITHUB_TOKEN 权限不足

**修复方法**: 使用个人访问令牌 (PAT)

1. **创建 Personal Access Token**:
   - 访问 https://github.com/settings/tokens/new
   - Note: `VideoSplitTool Release`
   - Expiration: `90 days` 或更长
   - 勾选权限:
     - ✅ `repo` (所有子项)
     - ✅ `workflow`
   - 点击 **Generate token**
   - **复制** token（只显示一次！）

2. **添加到仓库 Secrets**:
   - 仓库页面 → Settings → Secrets and variables → Actions
   - 点击 **New repository secret**
   - Name: `RELEASE_TOKEN`
   - Secret: 粘贴刚才复制的 token
   - 点击 **Add secret**

3. **修改 build.yml**:

   找到 `create-release` 任务的最后几行：

   ```yaml
   env:
     GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
   ```

   改为：

   ```yaml
   env:
     GITHUB_TOKEN: ${{ secrets.RELEASE_TOKEN }}
   ```

#### 错误 3: Tag already exists

```
Error: Release tag already exists
```

**原因**: 版本标签重复

**修复方法**: 使用新的版本号

```bash
# 删除本地和远程标签
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0

# 创建新标签
git tag v1.0.1
git push origin v1.0.1
```

---

## 推荐方案

### 方案 1: 手动触发 + 下载 Artifacts（推荐新手）

使用新创建的 `build-manual.yml` 工作流：

1. Actions → **"Build (Manual Download)"**
2. Run workflow
3. 等待完成后下载 Artifacts

**优点**:
- ✅ 不需要配置权限
- ✅ 不会创建 Release
- ✅ 简单可靠

### 方案 2: 推送标签 + 自动创建 Release（适合正式发布）

1. **首次配置** (只需一次):
   - 修改仓库权限（Settings → Actions → Workflow permissions → Read and write）

2. **每次发布**:
   ```bash
   # 创建标签
   git tag v1.0.0

   # 推送标签
   git push origin v1.0.0
   ```

3. **等待构建完成**，在 Releases 页面查看

**优点**:
- ✅ 自动创建 Release 页面
- ✅ 用户可以直接下载
- ✅ 有版本管理

---

## 快速测试

### 测试方案 1（不需要标签）

```bash
# 1. 上传新的 build-manual.yml
git add .github/workflows/build-manual.yml
git commit -m "Add manual build workflow"
git push

# 2. GitHub → Actions → Build (Manual Download) → Run workflow

# 3. 下载 Artifacts
```

### 测试方案 2（自动 Release）

```bash
# 1. 修改仓库权限
# Settings → Actions → General → Workflow permissions → Read and write

# 2. 创建标签
git tag v1.0.0
git push origin v1.0.0

# 3. 等待完成，检查 Releases 页面
```

---

## 文件清单

现在有两个工作流文件：

1. **`.github/workflows/build.yml`**
   - 触发: 推送标签（如 v1.0.0）
   - 结果: 创建 GitHub Release
   - 适合: 正式版本发布

2. **`.github/workflows/build-manual.yml`** (新增)
   - 触发: 手动点击 Run workflow
   - 结果: 生成 Artifacts
   - 适合: 日常测试、开发版本

---

## 常见问题

**Q: 我应该使用哪个工作流？**

A:
- 测试/开发 → `Build (Manual Download)`
- 正式发布 → `Build and Release` (推送标签)

**Q: Artifacts 保留多久？**

A: 默认 7 天，可在工作流中修改 `retention-days`

**Q: 如何删除错误的 Release？**

A:
1. Releases 页面 → 找到对应版本
2. 点击右侧 "Delete"
3. 删除对应的标签:
   ```bash
   git tag -d v1.0.0
   git push origin :refs/tags/v1.0.0
   ```

**Q: 可以同时使用两个工作流吗？**

A: 可以！它们互不影响

---

## 推荐流程

```
日常开发/测试
    ↓
Build (Manual Download)
    ↓
下载 Artifacts 测试
    ↓
确认无误
    ↓
git tag v1.0.0
git push origin v1.0.0
    ↓
Build and Release (自动)
    ↓
Release 页面发布
```

---

如果还有问题，请提供错误截图或完整错误信息！
