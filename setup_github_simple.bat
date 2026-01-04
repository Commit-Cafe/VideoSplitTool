@echo off
echo =======================================
echo GitHub Repository Setup
echo =======================================
echo.

git --version >nul 2>&1
if errorlevel 1 (
    echo Error: Git not found
    echo Please install Git: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo Git installed
echo.

if exist ".git" (
    echo Git repository exists
) else (
    echo [1/4] Initializing Git...
    git init
    echo Done
    echo.
)

echo [2/4] Setup remote repository
echo.
echo Please create a new repository on GitHub: https://github.com/new
echo Then enter the repository URL (e.g., https://github.com/username/video_pin.git)
echo.
set /p REPO_URL="Repository URL: "

if "%REPO_URL%"=="" (
    echo Error: URL cannot be empty
    pause
    exit /b 1
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
    git remote add origin %REPO_URL%
    echo Added remote: %REPO_URL%
) else (
    git remote set-url origin %REPO_URL%
    echo Updated remote: %REPO_URL%
)
echo.

echo [3/4] Adding files...
git add .
echo Done
echo.

echo [4/4] Creating commit...
git commit -m "Initial commit: Video Split Tool V2.0"
if errorlevel 1 (
    echo No changes to commit
) else (
    echo Done
)
echo.

echo =======================================
echo Ready to push
echo =======================================
echo.
echo Repository: %REPO_URL%
echo Branch: main
echo.
set /p CONFIRM="Continue? (y/n): "

if /i "%CONFIRM%"=="y" (
    echo.
    echo Pushing to GitHub...
    git branch -M main
    git push -u origin main

    if errorlevel 1 (
        echo.
        echo Push failed
        echo.
        echo Possible reasons:
        echo 1. Need to login GitHub (login window will pop up)
        echo 2. Wrong repository URL
        echo 3. No push permission
        echo.
    ) else (
        echo.
        echo =======================================
        echo Success!
        echo =======================================
        echo.
        echo Next steps:
        echo 1. Visit your GitHub repository
        echo 2. Click "Actions" tab
        echo 3. Click "Run workflow" to trigger build
        echo.
        echo Or create a release tag:
        echo   git tag v1.0.0
        echo   git push origin v1.0.0
        echo.
    )
) else (
    echo.
    echo Cancelled
    echo.
    echo To push manually, run:
    echo   git push -u origin main
)

echo.
pause
