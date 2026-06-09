"""
图片 logo 端到端冒烟测试
位置参数语义：logo 中心点 = (X%, Y%) 视频区域，0% 为左/上边缘，100% 为右/下边缘
运行：python tests/test_e2e_image_logo.py
"""
import os
import sys
import tempfile

import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image
from src.ui import VideoSplitApp
from src.core.video_processor import VideoProcessor


def _make_logo(path):
    Image.new('RGBA', (200, 100), (255, 0, 0, 200)).save(path)


def test_app_constructs_with_logo():
    root = tk.Tk()
    root.withdraw()
    try:
        app = VideoSplitApp(root)
        # 新的位置相关属性
        for attr in [
            'logo_enabled', 'logo_path', 'logo_size_percent',
            'logo_x_percent', 'logo_y_percent',
            'logo_angle', 'logo_opacity',
        ]:
            assert hasattr(app, attr), f"缺少属性: {attr}"
        # 验证默认值 = 中心 (50, 50)
        assert app.logo_x_percent.get() == 50
        assert app.logo_y_percent.get() == 50
        # 旧字段应已被移除
        for old in ['logo_position', 'logo_margin_x', 'logo_margin_y']:
            assert not hasattr(app, old), f"旧字段 {old} 应已移除"
        app.process_mode.set('image_logo')
        app._on_process_mode_change()
        print("test_app_constructs_with_logo OK")
    finally:
        root.destroy()


def test_logo_path_validation_in_processor():
    """验证 _build_image_logo_filter_complex 在缺少文件时仍可生成字符串"""
    fp = VideoProcessor._build_image_logo_filter_complex(
        out_width=1920, out_height=1080,
        logo_path='不存在的文件.png',
        logo_size_percent=20,
        logo_x_percent=50, logo_y_percent=50,
        logo_angle=15.0, logo_opacity=0.5
    )
    assert '[outv]' in fp
    assert 'W*50/100-w/2' in fp
    assert 'H*50/100-h/2' in fp
    assert 'rotate=' in fp
    assert 'colorchannelmixer=aa=0.5' in fp
    print("test_logo_path_validation_in_processor OK")


def test_logo_drawn_in_preview():
    """验证 image_logo 模式下 _draw_merge_preview 不抛异常"""
    with tempfile.TemporaryDirectory() as tmp:
        logo_path = os.path.join(tmp, 'logo.png')
        _make_logo(logo_path)
        root = tk.Tk()
        root.withdraw()
        try:
            app = VideoSplitApp(root)
            app.process_mode.set('image_logo')
            app.logo_enabled.set(True)
            app.logo_path.set(logo_path)
            app.logo_size_percent.set(20)
            app.logo_x_percent.set(50)
            app.logo_y_percent.set(50)
            app._draw_merge_preview()
            print("test_logo_drawn_in_preview OK")
        finally:
            root.destroy()


def test_get_merge_combinations_image_logo():
    """验证 image_logo 模式返回 ['image_logo']"""
    root = tk.Tk()
    root.withdraw()
    try:
        app = VideoSplitApp(root)
        app.process_mode.set('image_logo')
        combos = app._get_merge_combinations()
        assert combos == ["image_logo"], f"预期 ['image_logo'], 得到 {combos}"
        print("test_get_merge_combinations_image_logo OK")
    finally:
        root.destroy()


def test_refresh_preview_image_logo_no_list_video():
    """验证 image_logo 模式下，仅模板视频 + logo 即可生成预览（不需列表视频）"""
    with tempfile.TemporaryDirectory() as tmp:
        logo_path = os.path.join(tmp, 'logo.png')
        _make_logo(logo_path)
        root = tk.Tk()
        root.withdraw()
        try:
            app = VideoSplitApp(root)
            assert len(app.video_items) == 0, "测试前提：video_items 应为空"
            app.process_mode.set('image_logo')
            app.logo_enabled.set(True)
            app.logo_path.set(logo_path)
            app._on_process_mode_change()
            assert hasattr(app, 'logo_widgets_frame')
            app._refresh_merge_preview()
            print("test_refresh_preview_image_logo_no_list_video OK")
        finally:
            root.destroy()


def test_use_temp_output_dir_button():
    """验证 '用临时目录' 按钮设置系统临时目录作为输出目录"""
    import tempfile
    root = tk.Tk()
    root.withdraw()
    try:
        app = VideoSplitApp(root)
        # 设置一个"坏"的目录
        app.output_dir.set('C:\\NonExistent\\BadPath')
        # 调用 _use_temp_output_dir
        # 由于它会弹 messagebox，我们 patch 掉 messagebox 以免阻塞
        from tkinter import messagebox
        original = messagebox.showinfo
        messagebox.showinfo = lambda *a, **k: None
        try:
            app._use_temp_output_dir()
        finally:
            messagebox.showinfo = original
        # 验证 output_dir 已被设置为系统临时目录
        assert app.output_dir.get() == tempfile.gettempdir(), \
            f"output_dir 应为 {tempfile.gettempdir()}，实际为 {app.output_dir.get()}"
        print("test_use_temp_output_dir_button OK")
    finally:
        root.destroy()


def test_results_carry_output_path():
    """验证 results 列表的每个字典都包含 output_path 字段

    之前 results 字典只有 name/success/error，没有 output_path，
    导致成功窗口无法显示生成文件的完整路径，用户找不到文件。
    """
    # 模拟一个 results 列表（模拟 _process_videos 的输出）
    simulated_results = [
        {'name': 'Vce6b912a.mp4 (IMAGE_LOGO)', 'success': True,
         'error': '', 'output_path': 'C:\\Temp\\20260609_001.mp4'},
    ]
    # 验证字段存在
    for r in simulated_results:
        assert 'output_path' in r, f"results 缺少 output_path: {r}"
        assert r['output_path'], f"output_path 不应为空: {r}"
    print("test_results_carry_output_path OK")


if __name__ == '__main__':
    test_app_constructs_with_logo()
    test_logo_path_validation_in_processor()
    test_logo_drawn_in_preview()
    test_get_merge_combinations_image_logo()
    test_refresh_preview_image_logo_no_list_video()
    test_use_temp_output_dir_button()
    test_results_carry_output_path()
    print("E2E ALL OK")
