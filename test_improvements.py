"""
V2.1改进功能测试脚本
用于验证所有新增的稳定性和用户体验改进
"""
import os
import sys
import time


def print_section(title):
    """打印分隔符"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_logger():
    """测试日志系统"""
    print_section("测试1: 日志系统")

    try:
        from logger import logger, cleanup_old_logs

        # 测试各种日志级别
        logger.debug("这是DEBUG级别日志")
        logger.info("这是INFO级别日志")
        logger.warning("这是WARNING级别日志")
        logger.error("这是ERROR级别日志")

        # 检查日志文件是否创建
        from utils import get_base_path
        log_dir = os.path.join(get_base_path(), 'logs')

        if os.path.exists(log_dir):
            log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
            print(f"✅ 日志系统正常工作")
            print(f"   日志目录: {log_dir}")
            print(f"   日志文件数: {len(log_files)}")
            if log_files:
                print(f"   最新日志: {log_files[-1]}")
            return True
        else:
            print("❌ 日志目录未创建")
            return False

    except Exception as e:
        print(f"❌ 日志系统测试失败: {e}")
        return False


def test_temp_manager():
    """测试临时文件管理器"""
    print_section("测试2: 临时文件管理器")

    try:
        from temp_manager import TempFileManager

        # 创建测试管理器
        manager = TempFileManager()

        # 创建几个临时文件
        temp_files = []
        for i in range(3):
            temp_path = manager.create_temp_file(suffix=f".test{i}", prefix="test_")
            temp_files.append(temp_path)
            # 实际创建文件
            with open(temp_path, 'w') as f:
                f.write(f"Test file {i}")

        print(f"✅ 创建了 {len(temp_files)} 个临时文件")
        print(f"   追踪文件数: {manager.get_tracked_count()}")

        # 测试清理
        manager.cleanup_tracked_files()

        # 验证文件是否被删除
        remaining = sum(1 for f in temp_files if os.path.exists(f))
        if remaining == 0:
            print(f"✅ 所有临时文件已清理")
            return True
        else:
            print(f"⚠️  还有 {remaining} 个文件未清理")
            return False

    except Exception as e:
        print(f"❌ 临时文件管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_diagnostics():
    """测试智能错误诊断"""
    print_section("测试3: 智能错误诊断")

    try:
        from error_handler import ErrorDiagnostics, format_error_message

        # 测试各种错误模式
        test_cases = [
            ("No such file or directory", "文件不存在"),
            ("matches no streams", "音频流匹配"),
            ("Invalid data found", "文件损坏"),
            ("Permission denied", "权限不足"),
        ]

        success_count = 0
        for stderr_sample, expected_keyword in test_cases:
            error_desc, suggestions = ErrorDiagnostics.diagnose_ffmpeg_error(stderr_sample)
            if expected_keyword in error_desc or any(expected_keyword in s for s in suggestions):
                success_count += 1
                print(f"✅ 识别错误: {expected_keyword}")
            else:
                print(f"⚠️  可能未正确识别: {expected_keyword}")

        if success_count == len(test_cases):
            print(f"\n✅ 所有错误诊断测试通过 ({success_count}/{len(test_cases)})")
            return True
        else:
            print(f"\n⚠️  部分测试通过 ({success_count}/{len(test_cases)})")
            return success_count > 0

    except Exception as e:
        print(f"❌ 错误诊断测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_input_validator():
    """测试输入验证"""
    print_section("测试4: 输入验证")

    try:
        from error_handler import InputValidator

        # 测试分割比例验证
        test_ratios = [
            (0.5, True),   # 有效
            (0.1, True),   # 边界值
            (0.9, True),   # 边界值
            (0.05, False), # 太小
            (1.0, False),  # 太大
        ]

        ratio_ok = 0
        for ratio, expected in test_ratios:
            is_valid, _ = InputValidator.validate_split_ratio(ratio)
            if is_valid == expected:
                ratio_ok += 1

        print(f"分割比例验证: {ratio_ok}/{len(test_ratios)} 通过")

        # 测试缩放百分比验证
        test_scales = [
            (100, True),  # 有效
            (50, True),   # 边界值
            (200, True),  # 边界值
            (30, False),  # 太小
            (300, False), # 太大
        ]

        scale_ok = 0
        for scale, expected in test_scales:
            is_valid, _ = InputValidator.validate_scale_percent(scale)
            if is_valid == expected:
                scale_ok += 1

        print(f"缩放百分比验证: {scale_ok}/{len(test_scales)} 通过")

        total_ok = ratio_ok + scale_ok
        total_tests = len(test_ratios) + len(test_scales)

        if total_ok == total_tests:
            print(f"\n✅ 所有输入验证测试通过")
            return True
        else:
            print(f"\n⚠️  部分测试通过 ({total_ok}/{total_tests})")
            return False

    except Exception as e:
        print(f"❌ 输入验证测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_exception_handling():
    """测试异常处理改进"""
    print_section("测试5: 异常处理")

    try:
        # 检查utils.py中的异常处理
        print("检查代码中的异常处理...")

        issues = []

        # 读取关键文件检查裸except
        files_to_check = ['utils.py', 'main.py', 'video_processor.py']

        for filename in files_to_check:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 检查是否还有裸except
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        stripped = line.strip()
                        if stripped == "except:" or stripped.startswith("except:"):
                            issues.append(f"{filename}:{i} - 发现裸except")

        if not issues:
            print("✅ 未发现裸except语句")
            return True
        else:
            print(f"⚠️  发现 {len(issues)} 个潜在问题:")
            for issue in issues[:5]:  # 只显示前5个
                print(f"   {issue}")
            return False

    except Exception as e:
        print(f"❌ 异常处理检查失败: {e}")
        return False


def test_imports():
    """测试所有模块导入"""
    print_section("测试6: 模块导入")

    modules = [
        'logger',
        'temp_manager',
        'error_handler',
        'utils',
        'video_processor',
    ]

    success_count = 0
    for module_name in modules:
        try:
            __import__(module_name)
            print(f"✅ {module_name}")
            success_count += 1
        except Exception as e:
            print(f"❌ {module_name}: {e}")

    if success_count == len(modules):
        print(f"\n✅ 所有模块导入成功")
        return True
    else:
        print(f"\n⚠️  {success_count}/{len(modules)} 模块导入成功")
        return False


def test_file_structure():
    """测试文件结构"""
    print_section("测试7: 文件结构")

    required_files = [
        'logger.py',
        'temp_manager.py',
        'error_handler.py',
        'utils.py',
        'video_processor.py',
        'main.py',
        'IMPROVEMENT_PLAN.md',
        'CHANGELOG_V2.1.md',
    ]

    missing = []
    for filename in required_files:
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"✅ {filename} ({size} bytes)")
        else:
            print(f"❌ {filename} - 缺失")
            missing.append(filename)

    if not missing:
        print(f"\n✅ 所有必需文件存在")
        return True
    else:
        print(f"\n⚠️  缺失 {len(missing)} 个文件")
        return False


def main():
    """运行所有测试"""
    print("\n" + "+" * 60)
    print("  视频分割拼接工具 V2.1 - 改进功能测试")
    print("+" * 60)

    tests = [
        ("模块导入", test_imports),
        ("文件结构", test_file_structure),
        ("日志系统", test_logger),
        ("临时文件管理", test_temp_manager),
        ("错误诊断", test_error_diagnostics),
        ("输入验证", test_input_validator),
        ("异常处理", test_exception_handling),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ 测试 '{test_name}' 执行失败: {e}")
            results.append((test_name, False))

        time.sleep(0.5)  # 稍微延迟，便于查看输出

    # 打印总结
    print_section("测试总结")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {test_name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！V2.1改进功能正常工作。")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，请检查上述输出。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
