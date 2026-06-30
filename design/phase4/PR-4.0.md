# PR-4.0  P0 安全止血：明文凭证清理与 AuthSession 字段加固

> Phase 4 / PR 0 of 9
> 优先级: 🔴 P0 (阻塞 PR-4.5)
> 估计工作量: 0.5 PD
> 阻塞: PR-4.1 / PR-4.5

## 一句话目标

**消除 framework 内任何形式的明文凭证(用户名/密码/token)写入源码或被 git 历史记录**,并把 `AuthSession` 的敏感字段改造成可 secret-aware 容器,确保后续 PR 不退回。

---

## 背景与动机

### 现状 finding (HIGHEST SEVERITY)

`src/gimbal/auth/authenticators/wl.py:67-74` 的 `__main__` 块写入真实凭据:

```python
if __name__ == "__main__":
    auth = AuthSession(
        url="https://fin-tidb.21eflag.com/",
        username="18180789650",
        password="yhd123456!",
        expires_in=7200
    )
    WLAuthenticator().authenticate(auth=auth, tag="test")
    print(auth)
```

观察:

1. `__name__ == "__main__"` 块在 `from gimbal.auth.authenticators.wl import *` 时不被执行, 但在 `python -m gimbal.auth.authenticators.wl` 或文档示例误执行时仍会触发实际 HTTP 登录
2. 历史 git blame / git log 仍可检索到生产域名 `fin-tidb.21eflag.com`
3. CI 在某些 job 下若错误地拉这个文件会触发真实登录
4. 没有 `.gitignore` 包含 `*.secret`, secrets 缺乏标准化管理路径

### 同源问题面

- `src/gimbal/schema/auth.py` 的 `AuthSession` 字段 `password` / `access_token` / `refresh_token` **明文 Pydantic 字段** —— 内置 test / log / repr 时全部打印
- `src/gimbal/auth/manager.py:_refresh` 把 `auth.refresh_token` 写到 `httpx.post(json=...)` 的 body, 无任何 sanitize
- `src/gimbal/auth/authenticators/wl.py` 的 `code: 0000` 字段为 Python int 0, 但服务端语义应为 str `"0000"` —— 既不属 PR-4.0 scope, **标注后置**

## 范围与非目标

**In scope**:

- 删除 `wl.py:67-74` 的 `__main__` 块所有内容(替换为 docstring demo)
- 引入 `gimbal/secrets/` 子包,封装 secret load/compare 工具
- 把 `AuthSession.password / access_token / refresh_token` 改成 `SecretStr` 或自定义 `SecretField`
- 添加 `pyproject.toml` + `.gitignore` 防 secret 类文件入库
- 添加 `git-secrets` / `pre-commit` 钩子配置(可选, 由 reviewer 决议)

**Out of scope**:

- HTTPSAuthenticator / HTTPAuthenticator / GitHubAuthenticator 的语义改造(独立 PR)
- `AuthManager._refresh` 的逻辑重写
- secrets-provider 实际后端实现(只定接口)

---

## 设计

### 1. secrets/ 子包骨架

新增 `src/gimbal/secrets/`:

```
secrets/
  __init__.py        # public API: SecretStr, secret_compare, mask_secret
  types.py           # SecretStr Pydantic-compatible type
  provider.py        # SecretProvider Protocol
  defaults.py        # EnvSecretProvider (从 env / file 读)
```

```python
# types.py —— SecretStr
class SecretStr:
    """不可打印的 secret 容器, repr() 输出 '<SecretStr:7chars>', __eq__ 做 constant-time."""
    __slots__ = ("_value",)
    def __init__(self, value: str): ...
    def __repr__(self) -> str: ...
    def __str__(self) -> str: ...
    def reveal(self) -> str: ...
    def __eq__(self, other) -> bool:  # hmac.compare_digest
```

### 2. AuthSession 字段迁移

| 字段 | 旧类型 | 新类型 | 备注 |
|---|---|---|---|
| `password` | `str` | `SecretStr \| None` | Pydantic 兼容; 明文访问需 `.reveal()` |
| `access_token` | `str \| None` | `SecretStr \| None` | 同上 |
| `refresh_token` | `str \| None` | `SecretStr \| None` | 同上 |

兼容性策略:
- 提供 `apply_token(plaintext: str, expires_in: int | None)` 方法,内部包成 `SecretStr`
- 提供 `auth_header` property 直接输出 `Bearer xxxxx`(原作者已用该 property, 不破坏)
- 反序列化(Pydantic v2): `secrets={"password": "abc123"}` 仍可, 自动包装

### 3. wl.py cleanup

```python
"""WLAuthenticator - 物流系统 (fin-tidb) 专用认证器

[危险 demo 移除] 原 __main__ 块已删除, 详见 PR-4.0.

用法示例(勿在源码中写真凭据):
    from gimbal.secrets import EnvSecretProvider
    pw = EnvSecretProvider("WL_USER_PASSWORD").reveal()
    auth = AuthSession(
        url="https://fin-tidb.21eflag.com/",
        username=os.environ["WL_USERNAME"],
        password=pw,
    )
"""
# 业务代码不变
```

### 4. .gitignore / pre-commit

- `.gitignore`: 增加 `*.secret`, `.secrets/`, `secrets.local.yaml`
- `.pre-commit-config.yaml`(可选): 引入 `git-secrets --register --add-provider` + 自定义 regex `(?i)(password|token|api[_-]?key)\s*=\s*['"][^'"]+['"]`
- 文档 `docs/security.md`: 补充"如何管理 credentials"

### 5. 升级路径

为避免破坏现有 scenario.json, 增加 Pydantic validator:

```python
@field_validator("password", "access_token", "refresh_token", mode="before")
@classmethod
def _wrap_secret(cls, v: Any) -> Any:
    """dict 反序列化时, 接受明文 str 后包装为 SecretStr (向后兼容)."""
    if v is None or isinstance(v, SecretStr):
        return v
    return SecretStr(v)
```

测试侧: 打印 `repr(auth)` 不再包含明文 token.

---

## 验收 (DoD)

### 必须

- [ ] `auth/authenticators/wl.py` 无 `__name__ == "__main__"` 块, 无真实 URL/用户名/密码
- [ ] `git grep -nE 'yhd[0-9]+|fin-tidb\.21eflag' src/` 无结果
- [ ] `git grep -nE 'password\s*=\s*"[^"]+"' src/` 无结果(测试 fixture 与 dev-only 例外)
- [ ] `tests/unit/test_auth_secret.py` 新增 6 个用例: round-trip / repr 掩码 / eq constant-time / Pydantic 反序列化
- [ ] `tests/unit/test_auth_session_field.py` 测试 `AuthSession.password` 拒明文 log: `logger.info("%s", auth)` 不输出明文
- [ ] `pyproject.toml` 与 `.gitignore` 反映 `.secret` 模式
- [ ] CHANGELOG / DECISIONS (D28) 记录

### 应有

- [ ] docs/security.md 写出"如何本地管理 credentials"流程
- [ ] pre-commit / git-secrets 配置存盘(reviewer 决定是否合并)

### Nice to have

- [ ] CI 跑 `detect-secrets` 或 `trufflehog` 扫描历史提交(只告警, 不阻断)
- [ ] 现存用户场景文件(scenario.json 等)如有明文 password, 给 migration 提示

---

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| AuthSession 字段强类型破坏外部调用 | SecretStr 自动 wrap 旧 JSON; 加 release note | 暂时保留 `password_str` 兼容字段 |
| .gitignore 过严, 误排除 CI 必要文件 | CI cache 文件不进 secret 目录 | 单独列出白名单 |
| SecretStr 的 `__eq__` 与 dict 比较差异 | 自定义 `__hash__` 与 `__eq__` 同步 | 暂时禁用 SecretStr, 仅 docstring 提示 |

---

## 任务清单

- [ ] T1 创建 `src/gimbal/secrets/{__init__.py, types.py, provider.py, defaults.py}` 并加单测
- [ ] T2 修改 `src/gimbal/schema/auth.py` 字段类型 + 加 validator
- [ ] T3 修改 `src/gimbal/auth/authenticators/wl.py` 删除 `__main__` 块
- [ ] T4 更新 `src/gimbal/auth/manager.py:_refresh`, 使用 `auth.refresh_token.reveal()`
- [ ] T5 pyproject.toml + .gitignore + docs/security.md
- [ ] T6 tests/unit/test_auth_secret.py + tests/unit/test_auth_session_field.py
- [ ] T7 DECISIONS.md D28 登记
- [ ] T8 上 PR, @security-reviewer

---

## 依赖与并行

- **依赖**: 无(本 PR 是 Phase 4 第一步)
- **被依赖**: PR-4.5(auth 测试), PR-4.7(docs)
- **可并行**: 无
