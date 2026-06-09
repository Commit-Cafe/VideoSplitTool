"""
验证 process_videos 接受新的 logo 参数
位置参数已重构：logo_x_percent / logo_y_percent（中心点百分比，0~100）
运行：python tests/test_process_videos_signature.py
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.video_processor import VideoProcessor

sig = inspect.signature(VideoProcessor.process_videos)
expected = [
    'logo_enabled', 'logo_path', 'logo_size_percent',
    'logo_x_percent', 'logo_y_percent',
    'logo_angle', 'logo_opacity',
]
params = list(sig.parameters.keys())
for p in expected:
    assert p in params, f"缺少参数: {p}"
    print(f"OK 参数存在: {p}")

# 同时验证旧的位置相关参数已被移除
removed_should_not_exist = ['logo_position', 'logo_margin_x', 'logo_margin_y']
for p in removed_should_not_exist:
    assert p not in params, f"旧参数 {p} 应已移除"
    print(f"OK 旧参数已移除: {p}")
print("ALL OK")
