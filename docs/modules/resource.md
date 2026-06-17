# Resource 模块

> 资源管理模块：测试所需的资源（Mock、Fixture、File、DB Snapshot 等）的管理与供给。

## 状态

**当前为预留桩模块**。所有源文件都仅含 docstring，**未实现**具体类与方法：

```
gimbal/resource/
├── __init__.py           # """Resource manager module."""
├── handle.py             # """ResourceHandle definition."""
├── manager.py            # """ResourceManager main class."""
├── provider_base.py      # """ResourceProvider abstract."""
└── providers/
    ├── __init__.py                  # """Resource provider implementations."""
    ├── mock_provider.py             # """MockProvider implementation."""
    ├── fixture_provider.py          # """FixtureProvider implementation."""
    ├── file_provider.py             # """FileProvider implementation."""
    └── db_snapshot_provider.py      # """DbSnapshotProvider implementation."""
```

后续填充计划（来自 `resource/README.md` 与目录命名）：

| 文件 | 计划内容 |
| --- | --- |
| `manager.py` | `ResourceManager` —— 资源管理器 |
| `handle.py` | `ResourceHandle` —— 资源句柄 |
| `provider_base.py` | `ResourceProvider` —— 资源提供者抽象基类 |
| `providers/mock_provider.py` | `MockProvider` —— 启动 Mock 容器 |
| `providers/fixture_provider.py` | `FixtureProvider` —— 准备测试数据 |
| `providers/file_provider.py` | `FileProvider` —— 准备测试文件 |
| `providers/db_snapshot_provider.py` | `DbSnapshotProvider` —— 恢复数据库快照 |

## 设计原则（预期）

1. **供给/销毁生命周期**: 资源有明确的供给和销毁流程
2. **健康检查**: 支持资源就绪检查
3. **批量操作**: 支持批量设置和清理
4. **Provider 可扩展**: 可注册自定义资源提供者

## 计划中的核心接口（仅作占位说明）

### ResourceManager（计划）

```python
class ResourceManager:
    """资源管理器（占位）"""

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

### ResourceHandle（计划）

```python
class ResourceHandle:
    """资源句柄（占位）"""

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

### Provider 基类（计划）

```python
class ResourceProvider(ABC):
    """资源提供者抽象基类（占位）"""

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

### 资源类型（计划）

```python
class MockProvider(ResourceProvider):
    """Mock 服务提供者（占位）"""
    # 启动 Mock 容器 → 返回访问地址

class FixtureProvider(ResourceProvider):
    """Fixture 提供者（占位）"""
    # 准备测试数据

class FileProvider(ResourceProvider):
    """文件提供者（占位）"""
    # 准备测试文件

class DbSnapshotProvider(ResourceProvider):
    """数据库快照提供者（占位）"""
    # 恢复数据库快照
```

## 计划中的使用示例（占位）

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

> 上方所有代码块仅展示预期接口签名，**当前未实现**。调用方不应直接依赖 `gimbal.resource.*`。
