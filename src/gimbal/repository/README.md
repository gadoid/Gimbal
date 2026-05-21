# Repository 模块

资产仓库模块，负责测试资产的存储、检索和管理。

## 设计理念

### 1. Repository 架构

```
Asset Reference (e.g., suite:id, scenario:path)
         │
         ▼
┌─────────────────┐
│     Router      │  引用路由
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ AssetRepository │  资产仓库抽象
└────────┬────────┘
         │
         ├── FileSystemBackend ──▶ 本地文件系统
         ├── MySQLBackend ───────▶ MySQL 数据库
         └── PythonModuleBackend ▶ Python 模块
```

### 2. 资产引用格式

| 类型 | 格式 | 示例 |
|------|------|------|
| Suite | `suite:<id>` | `suite:customs-declare` |
| Scenario | `scenario:<path>` | `scenario:tests/login.yaml` |
| 远程 | `<source>:<id>` | `remote:customs:v1.2` |

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `base.py` | `AssetRepository` 抽象基类 |
| `router.py` | `AssetRouter` 引用路由实现 |
| `exceptions.py` | 资产相关异常 |
| `backends/` | 存储后端实现 |
| `backends/filesystem.py` | 文件系统后端 |
| `backends/mysql.py` | MySQL 后端（预留） |
| `backends/python_module.py` | Python 模块后端（预留） |

---

## AssetRepository

```python
class AssetRepository(ABC):
    """资产仓库抽象基类。"""

    @abstractmethod
    def get_scenario(self, ref: str) -> Scenario:
        """获取 Scenario 资产。"""
        pass

    @abstractmethod
    def get_suite(self, ref: str) -> Suite:
        """获取 Suite 资产。"""
        pass

    @abstractmethod
    def list_assets(self, asset_type: str) -> list[AssetRef]:
        """列出资产。"""
        pass
```

---

## AssetRouter

```python
class AssetRouter:
    """资产引用路由。"""

    def resolve(self, ref: str) -> tuple[str, AssetRepository]:
        """解析引用，返回 (backend_type, repository)。"""
        pass

    def register_backend(self, scheme: str, backend: AssetRepository) -> None:
        """注册后端。"""
        pass
```

---

## 异常类

```python
class AssetNotFoundError(Exception):
    """资产未找到。"""

class AssetResolveError(Exception):
    """资产解析失败。"""
```

---

## 内置后端

### FileSystemBackend

本地文件系统后端。

```python
class FileSystemBackend(AssetRepository):
    """文件系统资产后端。"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
```

### MySQLBackend

MySQL 数据库后端（预留）。

```python
class MySQLBackend(AssetRepository):
    """MySQL 资产后端。"""
    pass
```

### PythonModuleBackend

Python 模块后端（预留）。

```python
class PythonModuleBackend(AssetRepository):
    """Python 模块资产后端。"""
    pass
```

---

## 使用示例

```python
from gimbal.repository import AssetRouter, FileSystemBackend

# 创建路由
router = AssetRouter()

# 注册后端
router.register_backend("file", FileSystemBackend(Path("./assets")))

# 解析资产引用
backend, ref = router.resolve("file:scenario/login.yaml")
scenario = backend.get_scenario(ref)
```

---

## 运行测试

```bash
python -m gimbal.repository
```
