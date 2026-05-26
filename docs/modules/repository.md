# Repository 模块

> 资源仓库模块，管理测试资产（Scenario/Suite）的存储和访问

## 目录结构

```
gimbal/repository/
├── __init__.py
├── base.py        # Repository 基类
├── router.py      # 引用路由
├── exceptions.py  # 仓库异常
└── backends/     # 存储后端
    ├── __init__.py
    ├── filesystem.py  # 文件系统后端
    ├── mysql.py       # MySQL 后端
    └── python_module.py # Python 模块后端
```

## 核心组件

### Repository 基类

```python
class Repository(ABC):
    """资源仓库抽象基类"""

    @abstractmethod
    def get(self, id: str) -> Scenario | Suite:
        """根据 ID 获取资产"""
        raise NotImplementedError

    @abstractmethod
    def list(self, namespace: str = None) -> list[Asset]:
        """列出资产"""
        raise NotImplementedError

    @abstractmethod
    def save(self, asset: Asset) -> None:
        """保存资产"""
        raise NotImplementedError

    @abstractmethod
    def delete(self, id: str) -> None:
        """删除资产"""
        raise NotImplementedError
```

### Asset

资产定义：

```python
class Asset:
    """测试资产"""
    id: str
    name: str
    namespace: str
    kind: AssetKind  # scenario / suite
    content: str | dict
    version: str
    created_at: datetime
    updated_at: datetime
    metadata: dict
```

### AssetKind

资产类型枚举：

```python
class AssetKind(Enum):
    SCENARIO = "scenario"
    SUITE = "suite"
```

### Router

引用路由：

```python
class Router:
    """引用路由"""

    def resolve(self, ref: str) -> Asset:
        """解析引用获取资产"""
        ...

    def match(self, pattern: str) -> list[Asset]:
        """模式匹配资产"""
        # 支持通配符
        # 支持命名空间
        ...
```

## 存储后端

### FilesystemBackend

文件系统后端：

```python
class FilesystemBackend(Repository):
    """文件系统后端"""

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir

    def get(self, id: str) -> Scenario | Suite:
        # 从 base_dir/{namespace}/{id}.yaml 读取
        ...
```

### MySQLBackend

MySQL 后端：

```python
class MySQLBackend(Repository):
    """MySQL 后端"""

    def __init__(self, uri: str):
        self._uri = uri
        self._conn = connect(uri)
```

### PythonModuleBackend

Python 模块后端：

```python
class PythonModuleBackend(Repository):
    """Python 模块后端"""
    # 从 Python 模块导入资产
```

## 使用示例

```python
from gimbal.repository.backends.filesystem import FilesystemBackend

# 创建仓库
repo = FilesystemBackend(base_dir="./assets")

# 获取资产
scenario = repo.get("payment/sc-001")

# 列出资产
assets = repo.list(namespace="payment")

# 模式匹配
matched = repo.match("payment/sc-*")
```

## 设计原则

1. **接口统一**: 所有后端实现统一 Repository 接口
2. **后端可插拔**: 支持多种存储后端按需切换
3. **命名空间**: 支持资产命名空间管理
4. **版本支持**: 资产支持版本控制