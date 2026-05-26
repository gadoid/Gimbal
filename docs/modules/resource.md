# Resource 模块

> 资源管理模块，提供测试所需的资源（Mock、Fixture、File 等）的管理和供给

## 目录结构

```
gimbal/resource/
├── __init__.py
├── manager.py       # ResourceManager
├── handle.py        # ResourceHandle
├── provider_base.py # Provider 基类
└── providers/       # 资源提供者
    ├── __init__.py
    ├── mock_provider.py    # Mock 服务提供者
    ├── fixture_provider.py # Fixture 提供者
    ├── file_provider.py    # 文件提供者
    └── db_snapshot_provider.py # 数据库快照提供者
```

## 核心组件

### ResourceManager

资源管理器：

```python
class ResourceManager:
    """资源管理器"""

    def __init__(self, config: BootstrapConfig):
        self._providers: dict[str, ResourceProvider] = {}

    def register_provider(self, name: str, provider: ResourceProvider) -> None:
        """注册资源提供者"""
        self._providers[name] = provider

    def acquire(self, resource: Resource) -> ResourceHandle:
        """获取资源"""
        ...

    def release(self, handle: ResourceHandle) -> None:
        """释放资源"""
        ...

    def setup(self, resources: list[Resource]) -> None:
        """批量设置资源"""
        ...

    def teardown(self, handles: list[ResourceHandle]) -> None:
        """批量清理资源"""
        ...
```

### ResourceHandle

资源句柄：

```python
class ResourceHandle:
    """资源句柄"""

    resource_id: str
    provider_name: str
    endpoint: str | None
    metadata: dict

    def is_ready(self) -> bool:
        """资源是否就绪"""
        ...

    def wait_until_ready(self, timeout: float = 30) -> None:
        """等待资源就绪"""
        ...

    def release(self) -> None:
        """释放资源"""
        ...
```

### Provider 基类

```python
class ResourceProvider(ABC):
    """资源提供者抽象基类"""

    @property
    def name(self) -> str:
        """提供者名称"""
        ...

    @abstractmethod
    def provision(self, resource: Resource) -> ResourceHandle:
        """供给资源"""
        raise NotImplementedError

    @abstractmethod
    def destroy(self, handle: ResourceHandle) -> None:
        """销毁资源"""
        raise NotImplementedError

    def health_check(self, handle: ResourceHandle) -> bool:
        """健康检查"""
        ...
```

## 资源类型

### MockProvider

Mock 服务提供者：

```python
class MockProvider(ResourceProvider):
    """Mock 服务提供者"""

    def provision(self, resource: Resource) -> ResourceHandle:
        # 启动 Mock 容器
        # 返回访问地址
        ...
```

### FixtureProvider

Fixture 提供者：

```python
class FixtureProvider(ResourceProvider):
    """Fixture 提供者"""

    def provision(self, resource: Resource) -> ResourceHandle:
        # 准备测试数据
        ...
```

### FileProvider

文件提供者：

```python
class FileProvider(ResourceProvider):
    """文件提供者"""

    def provision(self, resource: Resource) -> ResourceHandle:
        # 准备测试文件
        ...
```

### DBSnapshotProvider

数据库快照提供者：

```python
class DBSnapshotProvider(ResourceProvider):
    """数据库快照提供者"""

    def provision(self, resource: Resource) -> ResourceHandle:
        # 恢复数据库快照
        ...
```

## 使用示例

```python
from gimbal.resource.manager import ResourceManager
from gimbal.schema.resource import Mock, File

# 创建资源管理器
manager = ResourceManager(config)

# 注册提供者
manager.register_provider("mock", MockProvider())
manager.register_provider("file", FileProvider())

# 设置资源
handles = manager.setup([
    Mock(name="user-mock", port=8080),
    File(name="test-data", path="/data/users.json"),
])

# 等待就绪
for handle in handles:
    handle.wait_until_ready()

# 执行测试...

# 清理资源
manager.teardown(handles)
```

## 设计原则

1. **供给/销毁生命周期**: 资源有明确的供给和销毁流程
2. **健康检查**: 支持资源就绪检查
3. **批量操作**: 支持批量设置和清理
4. **Provider 可扩展**: 可注册自定义资源提供者