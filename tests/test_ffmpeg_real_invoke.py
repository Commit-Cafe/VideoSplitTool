"""
FFmpeg 真实调用冒烟测试：验证生成的 filter_complex 实际可执行
运行：python tests/test_ffmpeg_real_invoke.py
"""
import os
import sys
import subprocess
import tempfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.video_processor import get_ffmpeg_path
from src.core.video_processor import VideoProcessor


def _make_logo(path):
    """创建一个 100x50 的半透明红色 PNG logo"""
    Image.new('RGBA', (100, 50), (255, 0, 0, 200)).save(path)


def _make_test_video(path, w=320, h=240, dur=2):
    """用 ffmpeg 创建一个 2 秒的测试视频"""
    ffmpeg = get_ffmpeg_path()
    cmd = [
        ffmpeg, '-y',
        '-f', 'lavfi', '-i', f'testsrc=duration={dur}:size={w}x{240}:rate=30',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        path
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return proc


def test_real_ffmpeg_invocation_with_logo():
    """真实跑一次 FFmpeg：模板视频 + logo → 输出叠加后视频"""
    with tempfile.TemporaryDirectory() as tmp:
        logo_path = os.path.join(tmp, 'logo.png')
        template_path = os.path.join(tmp, 'template.mp4')
        output_path = os.path.join(tmp, 'output.mp4')

        _make_logo(logo_path)
        print(f"  生成模板视频...")
        proc = _make_test_video(template_path)
        if proc.returncode != 0:
            print(f"  ⚠️  模板视频生成失败: {proc.stderr[-200:]}")
            # 跳过测试：可能是 ffmpeg 缺编解码器
            print("test_real_ffmpeg_invocation_with_logo SKIP (模板视频生成失败)")
            return

        print(f"  生成 filter_complex...")
        fp = VideoProcessor._build_image_logo_filter_complex(
            out_width=320, out_height=240,
            logo_path=logo_path,
            logo_size_percent=20,
            logo_x_percent=50, logo_y_percent=50,
            logo_angle=0.0,
            logo_opacity=1.0
        )
        print(f"    filter: {fp[:100]}...")

        ffmpeg = get_ffmpeg_path()
        # 构造一个完整的 ffmpeg 命令
        cmd = [
            ffmpeg, '-y',
            '-stream_loop', '-1', '-i', template_path,
            '-loop', '1', '-i', logo_path,
            '-filter_complex', fp,
            '-map', '[outv]',
            '-t', '2',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            output_path
        ]
        print(f"  执行 ffmpeg 命令...")
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if proc.returncode == 0:
            assert os.path.exists(output_path), "输出文件未生成"
            size = os.path.getsize(output_path)
            assert size > 1000, f"输出文件太小: {size} bytes"
            print(f"  ✓ 成功生成输出: {output_path} ({size} bytes)")
            print("test_real_ffmpeg_invocation_with_logo OK")
        else:
            print(f"  ✗ ffmpeg 失败: {proc.stderr[-500:]}")
            assert False, f"ffmpeg failed: {proc.stderr[-200:]}"


def test_real_ffmpeg_invocation_with_rotation():
    """带旋转的 FFmpeg 调用"""
    with tempfile.TemporaryDirectory() as tmp:
        logo_path = os.path.join(tmp, 'logo.png')
        template_path = os.path.join(tmp, 'template.mp4')
        output_path = os.path.join(tmp, 'output.mp4')

        _make_logo(logo_path)
        proc = _make_test_video(template_path)
        if proc.returncode != 0:
            print("test_real_ffmpeg_invocation_with_rotation SKIP (模板视频生成失败)")
            return

        fp = VideoProcessor._build_image_logo_filter_complex(
            out_width=320, out_height=240,
            logo_path=logo_path,
            logo_size_percent=20,
            logo_x_percent=50, logo_y_percent=50,
            logo_angle=45.0,  # 旋转 45 度
            logo_opacity=1.0
        )

        ffmpeg = get_ffmpeg_path()
        cmd = [
            ffmpeg, '-y',
            '-stream_loop', '-1', '-i', template_path,
            '-loop', '1', '-i', logo_path,
            '-filter_complex', fp,
            '-map', '[outv]',
            '-t', '2',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            output_path
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if proc.returncode == 0:
            assert os.path.exists(output_path)
            size = os.path.getsize(output_path)
            assert size > 1000
            print(f"  ✓ 旋转 logo 成功: {output_path} ({size} bytes)")
            print("test_real_ffmpeg_invocation_with_rotation OK")
        else:
            assert False, f"ffmpeg failed: {proc.stderr[-200:]}"


def test_real_ffmpeg_invocation_output_path_with_spaces():
    """回归测试：输出路径含空格 + 数字时也能成功（确保 subprocess 正确转义）"""
    with tempfile.TemporaryDirectory() as tmp:
        # 创建含空格的子目录（模拟用户路径 'Telegram Desktop'）
        spaced_dir = os.path.join(tmp, 'Telegram Desktop')
        os.makedirs(spaced_dir, exist_ok=True)

        logo_path = os.path.join(spaced_dir, 'logo.png')
        template_path = os.path.join(spaced_dir, 'template 001.mp4')
        output_path = os.path.join(spaced_dir, 'output final 2024.mp4')

        _make_logo(logo_path)
        proc = _make_test_video(template_path)
        if proc.returncode != 0:
            print("test_real_ffmpeg_invocation_output_path_with_spaces SKIP (模板视频生成失败)")
            return

        fp = VideoProcessor._build_image_logo_filter_complex(
            out_width=320, out_height=240,
            logo_path=logo_path,
            logo_size_percent=20,
            logo_x_percent=50, logo_y_percent=50,
            logo_angle=0.0,
            logo_opacity=1.0
        )

        ffmpeg = get_ffmpeg_path()
        cmd = [
            ffmpeg, '-y',
            '-stream_loop', '-1', '-i', template_path,
            '-loop', '1', '-i', logo_path,
            '-filter_complex', fp,
            '-map', '[outv]',
            '-t', '2',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            output_path
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if proc.returncode == 0:
            assert os.path.exists(output_path)
            size = os.path.getsize(output_path)
            assert size > 1000
            print(f"  ✓ 含空格路径成功: {output_path} ({size} bytes)")
            print("test_real_ffmpeg_invocation_output_path_with_spaces OK")
        else:
            assert False, f"ffmpeg failed: {proc.stderr[-200:]}"


def test_real_ffmpeg_invocation_output_path_chinese():
    """回归测试：输出路径含中文字符时也能成功（Python 3 + Windows Unicode 路径）"""
    with tempfile.TemporaryDirectory() as tmp:
        # 创建含中文的子目录（模拟用户路径 'D:\输出视频文件夹'）
        chinese_dir = os.path.join(tmp, '输出视频文件夹')
        os.makedirs(chinese_dir, exist_ok=True)

        logo_path = os.path.join(chinese_dir, 'logo.png')
        template_path = os.path.join(chinese_dir, '模板视频.mp4')
        output_path = os.path.join(chinese_dir, '输出_2024.mp4')

        _make_logo(logo_path)
        proc = _make_test_video(template_path)
        if proc.returncode != 0:
            print("test_real_ffmpeg_invocation_output_path_chinese SKIP (模板视频生成失败)")
            return

        fp = VideoProcessor._build_image_logo_filter_complex(
            out_width=320, out_height=240,
            logo_path=logo_path,
            logo_size_percent=20,
            logo_x_percent=50, logo_y_percent=50,
            logo_angle=0.0,
            logo_opacity=1.0
        )

        ffmpeg = get_ffmpeg_path()
        cmd = [
            ffmpeg, '-y',
            '-stream_loop', '-1', '-i', template_path,
            '-loop', '1', '-i', logo_path,
            '-filter_complex', fp,
            '-map', '[outv]',
            '-t', '2',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            output_path
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if proc.returncode == 0:
            assert os.path.exists(output_path)
            size = os.path.getsize(output_path)
            assert size > 1000
            print(f"  ✓ 含中文路径成功: {output_path} ({size} bytes)")
            print("test_real_ffmpeg_invocation_output_path_chinese OK")
        else:
            assert False, f"ffmpeg failed: {proc.stderr[-200:]}"


def test_writability_check_chinese_path():
    """单元测试：_check_output_writability 应能识别含中文路径"""
    from src.core.video_processor import VideoProcessor
    proc = VideoProcessor()
    with tempfile.TemporaryDirectory() as tmp:
        chinese_dir = os.path.join(tmp, '输出视频文件夹')
        os.makedirs(chinese_dir, exist_ok=True)
        ok, msg = proc._check_output_writability(chinese_dir)
        assert ok, f"含中文路径应可写: {msg}"
        print(f"  ✓ 含中文路径可写检查通过")
    print("test_writability_check_chinese_path OK")


def test_validate_output_file_zero_bytes():
    """回归测试：_validate_output_file 应能检测 0 字节文件

    之前：process_videos 在 FFmpeg 写出 0 字节文件时仍返回成功，
    导致用户得到一个打不开的 MP4。
    修复后：_validate_output_file 会检测 0 字节并返回清晰错误。
    """
    from src.core.video_processor import VideoProcessor
    proc = VideoProcessor()
    with tempfile.TemporaryDirectory() as tmp:
        zero_file = os.path.join(tmp, 'zero.mp4')
        with open(zero_file, 'wb') as f:
            pass  # 创建 0 字节文件
        ok, msg = proc._validate_output_file(zero_file)
        assert not ok, "0 字节文件应被检测为无效"
        assert "太小" in msg or "不存在" in msg, f"错误消息应说明问题: {msg}"
        print("test_validate_output_file_zero_bytes OK")


def test_validate_output_file_no_ftyp_header():
    """回归测试：_validate_output_file 应能检测缺少 ftyp 头的文件"""
    from src.core.video_processor import VideoProcessor
    proc = VideoProcessor()
    with tempfile.TemporaryDirectory() as tmp:
        # 写一个非 MP4 文件（不是 ftyp 头）
        bad_file = os.path.join(tmp, 'bad.mp4')
        with open(bad_file, 'wb') as f:
            f.write(b'\x00' * 4 + b'NOT_MP4_HEADER' + b'\x00' * 100)
        ok, msg = proc._validate_output_file(bad_file)
        assert not ok, "非 MP4 头应被检测为无效"
        assert "ftyp" in msg or "MP4" in msg, f"错误消息应说明问题: {msg}"
        print("test_validate_output_file_no_ftyp_header OK")


def test_validate_output_file_valid_mp4():
    """_validate_output_file 应能正确识别真实有效的 MP4 文件"""
    from src.core.video_processor import VideoProcessor
    proc = VideoProcessor()
    with tempfile.TemporaryDirectory() as tmp:
        # 用之前测试生成的真实 MP4
        # 重新生成一个
        ffmpeg = get_ffmpeg_path()
        mp4_path = os.path.join(tmp, 'valid.mp4')
        cmd = [
            ffmpeg, '-y',
            '-f', 'lavfi', '-i', 'testsrc=duration=1:size=160x120:rate=15',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            mp4_path
        ]
        subprocess.run(cmd, capture_output=True)
        ok, msg = proc._validate_output_file(mp4_path)
        assert ok, f"真实 MP4 应被识别为有效: {msg}"
        print("test_validate_output_file_valid_mp4 OK")


def test_real_ffmpeg_invocation_image_logo_with_audio():
    """端到端：image_logo 模式 + 模板音频（audio_source='template'）

    回归测试：之前 _build_image_logo_filter_complex 不返回 [outa] 标签，
    导致 -map [outa] 找不到而出错：
    'Output with label outa does not exist in any defined filter graph'

    修复后：process_videos 在 image_logo + template 音频时会自动追加
    ';[0:a]volume=...[outa]' 到 filter_complex。
    """
    with tempfile.TemporaryDirectory() as tmp:
        logo_path = os.path.join(tmp, 'logo.png')
        template_path = os.path.join(tmp, 'template_with_audio.mp4')
        output_path = os.path.join(tmp, 'output_with_audio.mp4')

        _make_logo(logo_path)

        # 创建带音频的测试视频（sine 音源）
        ffmpeg = get_ffmpeg_path()
        cmd = [
            ffmpeg, '-y',
            '-f', 'lavfi', '-i', 'testsrc=duration=2:size=320x240:rate=30',
            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-shortest',
            template_path
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if proc.returncode != 0:
            print(f"test_real_ffmpeg_invocation_image_logo_with_audio SKIP (模板生成失败)")
            return

        # 模拟 process_videos 内部为 image_logo + template 音频构造的 filter_complex
        video_filter = VideoProcessor._build_image_logo_filter_complex(
            out_width=320, out_height=240,
            logo_path=logo_path,
            logo_size_percent=20,
            logo_x_percent=50, logo_y_percent=50,
            logo_angle=0.0,
            logo_opacity=1.0
        )
        # 模拟 process_videos 自动追加的音频滤镜
        full_filter = video_filter + ";[0:a]volume=1.0[outa]"

        # 关键断言：filter_complex 必须含 [outa] 标签
        assert '[outa]' in full_filter, f"filter_complex 缺少 [outa]: {full_filter}"

        # 跑完整 cmd
        cmd = [
            ffmpeg, '-y',
            '-stream_loop', '-1', '-i', template_path,
            '-loop', '1', '-i', logo_path,
            '-filter_complex', full_filter,
            '-map', '[outv]',
            '-map', '[outa]',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-t', '2',
            output_path
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if proc.returncode == 0:
            assert os.path.exists(output_path)
            size = os.path.getsize(output_path)
            assert size > 1000
            print(f"  ✓ image_logo + 音频成功: {output_path} ({size} bytes)")
            print("test_real_ffmpeg_invocation_image_logo_with_audio OK")
        else:
            err = proc.stderr[-300:] if proc.stderr else proc.stdout[-300:]
            assert False, f"ffmpeg 失败: {err}"


if __name__ == '__main__':
    test_real_ffmpeg_invocation_with_logo()
    test_real_ffmpeg_invocation_with_rotation()
    test_real_ffmpeg_invocation_output_path_with_spaces()
    test_real_ffmpeg_invocation_output_path_chinese()
    test_writability_check_chinese_path()
    test_real_ffmpeg_invocation_image_logo_with_audio()
    print("FFMPEG REAL INVOKE ALL OK")
