# Resource 模块

资源管理模块，负责测试执行过程中所需资源的获取、释放和管理。

## 设计理念

### 1. Resource 架构

```
Resource Request
        │
        ▼
┌─────────────────┐
│ ResourceManager │  资源管理器
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ResourceProvider│  资源提供器
└────────┬────────┘
         │
         ├── FixtureProvider ──▶ Fixture 资源
         ├── FileProvider ─────▶ 文件资源
         ├── DbSnapshotProvider ▶ 数据库快照
         └── MockProvider ──────▶ Mock 服务
```

### 2. 资源生命周期

```
acquire() ──▶ 使用 ──▶ release()
    │
    └─▶ 自动清理（context manager）
```

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `manager.py` | `ResourceManager` 资源管理器 |
| `handle.py` | `ResourceHandle` 资源句柄 |
| `provider_base.py` | `ResourceProvider` 资源提供器基类 |
| `providers/` | 资源提供器实现 |
| `providers/fixture_provider.py` | Fixture 资源提供器 |
| `providers/file_provider.py` | 文件资源提供器 |
| `providers/db_snapshot_provider.py` | 数据库快照提供器 |
| `providers/mock_provider.py` | Mock 服务提供器 |

---

## ResourceManager

```python
class ResourceManager:
    """资源管理器。"""

    def acquire(self, resource_type: str, **kwargs) -> ResourceHandle:
        """获取资源。"""
        pass

    def release(self, handle: ResourceHandle) -> None:
        """释放资源。"""
        pass

    def register_provider(self, provider: ResourceProvider) -> None:
        """注册资源提供器。"""
        pass
```

---

## ResourceHandle

```python
@dataclass
class ResourceHandle:
    """资源句柄。"""

    resource_id: str           # 资源唯一标识
    resource_type: str         # 资源类型
    provider: ResourceProvider # 提供器
    data: Any                  # 资源数据
    acquired_at: datetime      # 获取时间

    def release(self) -> None:
        """释放资源。"""
        pass
```

---

## ResourceProvider

```python
class ResourceProvider(ABC):
    """资源提供器抽象基类。"""

    @property
    @abstractmethod
    def resource_type(self) -> str:
        """资源类型。"""
        pass

    @abstractmethod
    def acquire(self, **kwargs) -> ResourceHandle:
        """获取资源。"""
        pass

    @abstractmethod
    def release(self, handle: ResourceHandle) -> None:
        """释放资源。"""
        pass
```

---

## 内置 Providers

### FixtureProvider

提供测试 Fixture 资源。

```python
class FixtureProvider(ResourceProvider):
    """Fixture 资源提供器。"""

    resource_type = "fixture"
```

### FileProvider

提供文件资源。

```python
class FileProvider(ResourceProvider):
    """文件资源提供器。"""

    resource_type = "file"
```

### DbSnapshotProvider

提供数据库快照资源。

```python
class DbSnapshotProvider(ResourceProvider):
    """数据库快照提供器。"""

    resource_type = "db_snapshot"
```

### MockProvider

提供 Mock 服务资源。

```python
class MockProvider(ResourceProvider):
    """Mock 服务提供器。"""

    resource_type = "mock"
```

---

## 使用示例

```python
from gimbal.resource import ResourceManager, ResourceHandle

manager = ResourceManager()

# 注册提供器
manager.register_provider(FixtureProvider())
manager.register_provider(FileProvider())

# 获取资源
handle = manager.acquire("fixture", name="test_user")
print(f"Resource: {handle.data}")

# 释放资源
handle.release()

# 使用 context manager
with manager.acquire("fixture", name="test_user") as handle:
    print(f"Resource: {handle.data}")
```

---

## 运行测试

```bash
python -m gimbal.resource
```
