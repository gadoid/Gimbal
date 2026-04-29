"""StepExecutor - 步骤执行器状态机"""
from schema.step import Step, Scenario
from schema.states import StepState
from runtime.context import ExecutionContext
from runtime.events import Event, EventType
from runtime.bus import EventBus
from runtime.dispatcher import ActionDispatcher


class StepExecutor:
    """步骤执行器状态机"""

    def __init__(self, event_bus: EventBus, dispatcher: ActionDispatcher):
        self.event_bus = event_bus
        self.dispatcher = dispatcher

    def execute_step(self, step: Step, context: ExecutionContext) -> Step:
        """执行单个步骤"""
        step.state = StepState.RUNNING
        self.event_bus.publish(
            Event(type=EventType.STEP_STARTED, data={"step_name": step.name})
        )

        try:
            result = self.dispatcher.dispatch(step.action, context)
            step.state = StepState.PASSED
            self.event_bus.publish(
                Event(type=EventType.STEP_COMPLETED, data={"step_name": step.name, "result": result})
            )
        except Exception as e:
            step.state = StepState.FAILED
            step.error = str(e)
            context.add_failure(step.name, step.action.type, str(e))
            self.event_bus.publish(
                Event(type=EventType.STEP_FAILED, data={"step_name": step.name, "error": str(e)})
            )

        return step

    def execute_scenario(self, scenario: Scenario, context: ExecutionContext) -> Scenario:
        """执行整个场景"""
        self.event_bus.publish(
            Event(type=EventType.SCENARIO_STARTED, data={"scenario_name": scenario.name})
        )

        for step in scenario.steps:
            if step.state == StepState.SKIPPED:
                continue
            self.execute_step(step, context)

        self.event_bus.publish(
            Event(type=EventType.SCENARIO_COMPLETED, data={"scenario_name": scenario.name})
        )

        return scenario
