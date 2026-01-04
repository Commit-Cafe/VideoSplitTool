@echo off
chcp 65001 >nul
echo ========================================
echo    视频分割拼接工具 - 打包脚本
echo ========================================
echo.

:: 激活虚拟环境
call .venv\Scripts\activate.bat

:: 清理旧的打包文件
echo [1/3] 清理旧文件...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

:: 执行打包
echo [2/3] 正在打包...
pyinstaller --noconfirm --onefile --windowed --name "VideoSplitTool" main.py

:: 复制ffmpeg到dist目录
echo [3/3] 复制ffmpeg依赖...
if exist "dist\VideoSplitTool.exe" (
    xcopy /E /I /Y "ffmpeg-8.0.1-full_build" "dist\ffmpeg" >nul
    echo.
    echo ========================================
    echo    打包完成！
    echo    输出目录: dist\
    echo    - VideoSplitTool.exe
    echo    - ffmpeg\ (依赖文件夹)
    echo ========================================
    echo.
    echo 请将 dist 文件夹整体发送给同事使用
) else (
    echo.
    echo 打包失败，请检查错误信息
)

pause
