"""TestRunner - 顶层测试运行器"""
from typing import Optional
from schema.step import Scenario
from runtime.context import ExecutionContext
from runtime.bus import EventBus
from runtime.dispatcher import ActionDispatcher
from runtime.executor import StepExecutor
from plugins.base import Plugin


class TestRunner:
    """测试运行器顶层入口"""

    def __init__(self):
        self.event_bus = EventBus()
        self.dispatcher = ActionDispatcher()
        self.executor = StepExecutor(self.event_bus, self.dispatcher)
        self.plugins: list[Plugin] = []

    def add_plugin(self, plugin: Plugin):
        """注册插件"""
        self.plugins.append(plugin)
        self.event_bus.subscribe(plugin.on_event)

    def run(self, scenario: Scenario, variables: Optional[dict] = None) -> ExecutionContext:
        """运行场景，返回执行上下文"""
        # 初始化上下文
        context = ExecutionContext(
            scenario_name=scenario.name,
            variables={**scenario.variables, **(variables or {})},
        )

        # 触发插件 start 钩子
        for plugin in self.plugins:
            plugin.on_start()

        # 执行场景
        self.executor.execute_scenario(scenario, context)

        # 触发插件 end 钩子
        for plugin in self.plugins:
            plugin.on_end()

        return context

    def run_file(self, file_path: str, variables: Optional[dict] = None) -> ExecutionContext:
        """从 YAML 文件运行场景"""
        from loader.yaml_loader import YamlLoader

        scenario = YamlLoader.load(file_path)
        return self.run(scenario, variables)
