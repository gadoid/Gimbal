"""运行入口 - CLI"""
import sys
from runner import TestRunner
from plugins.response_time import ResponseTimePlugin


def main():
    """CLI 入口"""
    if len(sys.argv) < 2:
        print("Usage: python run.py <scenario.yaml>")
        sys.exit(1)

    file_path = sys.argv[1]

    # 初始化运行器
    runner = TestRunner()

    # 注册插件
    response_time_plugin = ResponseTimePlugin(threshold_ms=2000)
    runner.add_plugin(response_time_plugin)

    # 运行场景
    print(f"Running scenario from: {file_path}")
    context = runner.run_file(file_path)

    # 输出结果
    print(f"\nScenario: {context.scenario_name}")
    print(f"Total steps: {len(context.assertions) + len(context.failures)}")
    print(f"Passed: {len([a for a in context.assertions if a['passed']])}")
    print(f"Failed: {len(context.failures)}")
    print(f"Assertions: {len(context.assertions)}")

    if context.failures:
        print("\nFailures:")
        for failure in context.failures:
            print(f"  - {failure.step_name}: {failure.error_message}")

    sys.exit(0 if not context.failures else 1)


if __name__ == "__main__":
    main()
