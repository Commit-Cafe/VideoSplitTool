@echo off
echo ========================================
echo GitHub 仓库初始化脚本
echo ========================================
echo.

REM 检查是否已安装 Git
git --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Git
    echo 请先安装 Git: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo [OK] Git 已安装
echo.

REM 检查是否已初始化 Git
if exist ".git" (
    echo [提示] Git 仓库已存在
) else (
    echo [1/4] 初始化 Git 仓库...
    git init
    echo [OK] 完成
    echo.
)

REM 询问 GitHub 仓库地址
echo [2/4] 配置远程仓库
echo.
echo 请先在 GitHub 创建一个新仓库（https://github.com/new）
echo 然后输入仓库地址（例如: https://github.com/username/video_pin.git）
echo.
set /p REPO_URL="输入仓库地址: "

if "%REPO_URL%"=="" (
    echo [错误] 仓库地址不能为空
    pause
    exit /b 1
)

REM 检查是否已添加远程仓库
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    git remote add origin %REPO_URL%
    echo [OK] 已添加远程仓库: %REPO_URL%
) else (
    git remote set-url origin %REPO_URL%
    echo [OK] 已更新远程仓库: %REPO_URL%
)
echo.

REM 添加文件
echo [3/4] 添加文件到 Git...
git add .
echo [OK] 完成
echo.

REM 提交
echo [4/4] 创建提交...
git commit -m "Initial commit: Video Split Tool V2.0"
if errorlevel 1 (
    echo [提示] 没有新的更改需要提交
) else (
    echo [OK] 完成
)
echo.

REM 推送到 GitHub
echo ========================================
echo 准备推送到 GitHub
echo ========================================
echo.
echo 请确认：
echo - 远程仓库: %REPO_URL%
echo - 分支: main
echo.
set /p CONFIRM="是否继续推送? (y/n): "

if /i "%CONFIRM%"=="y" (
    echo.
    echo 正在推送到 GitHub...
    git branch -M main
    git push -u origin main

    if errorlevel 1 (
        echo.
        echo [错误] 推送失败
        echo.
        echo 可能的原因：
        echo 1. 需要登录 GitHub（会弹出登录窗口）
        echo 2. 仓库地址错误
        echo 3. 没有推送权限
        echo.
        echo 请检查后重新运行此脚本
    ) else (
        echo.
        echo ========================================
        echo [OK] 推送成功！
        echo ========================================
        echo.
        echo 下一步：
        echo 1. 访问你的 GitHub 仓库
        echo 2. 点击 Actions 标签
        echo 3. 点击 Run workflow 手动触发构建
        echo.
        echo 或者创建版本标签自动发布：
        echo   git tag v1.0.0
        echo   git push origin v1.0.0
        echo.
        echo 详细说明请查看: GITHUB_ACTIONS_GUIDE.md
    )
) else (
    echo.
    echo [取消] 已取消推送
    echo.
    echo 如需手动推送，请运行：
    echo   git push -u origin main
)

echo.
pause
