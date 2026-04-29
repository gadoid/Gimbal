"""Plugin 协议定义"""
from abc import ABC, abstractmethod
from runtime.events import Event


class Plugin(ABC):
    """插件抽象基类"""

    @abstractmethod
    def on_event(self, event: Event):
        """接收事件回调"""
        pass

    @abstractmethod
    def on_start(self):
        """场景开始前的钩子"""
        pass

    @abstractmethod
    def on_end(self):
        """场景结束后的钩子"""
        pass
