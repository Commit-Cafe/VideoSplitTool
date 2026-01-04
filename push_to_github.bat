@echo off
chcp 65001 >nul
echo ========================================
echo GitHub Code Push Helper
echo ========================================
echo.

REM Check git status
echo Checking git status...
git status

echo.
echo Please confirm the above file changes are correct
pause

echo.
echo Adding files...
git add .

echo.
set /p commit_msg=Enter commit message (e.g., Update V2.1):
git commit -m "%commit_msg%"

echo.
echo Pushing to GitHub...
git push

echo.
echo ========================================
echo Code push completed!
echo ========================================
echo.
echo Next steps:
echo 1. For testing: Go to GitHub - Actions - Build (Manual Download) - Run workflow
echo 2. For release: Create and push a tag
echo.
echo Example tag commands:
echo   git tag v2.1.0
echo   git push origin v2.1.0
echo.
pause
