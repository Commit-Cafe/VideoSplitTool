@echo off
chcp 65001 >nul
echo ========================================
echo Fix Git Large Files Issue
echo ========================================
echo.

echo Step 1: Remove FFmpeg from Git tracking
git rm -r --cached ffmpeg-8.0.1-full_build/
echo.

echo Step 2: Commit changes
git add .gitignore
git commit -m "Remove FFmpeg large files, will download in CI build"
echo.

echo ========================================
echo Done! Now run: git push
echo ========================================
pause
