# Gimbal Platform · Spec-1 · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Spec-1 平台骨架 + 读路径 (platform skeleton + read path) per `docs/superpowers/specs/2026-07-12-gimbal-platform-spec1-design.md`. After this plan the user can log in, browse a public/own case list, open the real 27-step `Scenario_Test_9.json` in a read-only Prism-style configurator with L1 field hiding + L3 platform default preset hiding, and manage users from `/admin/users`.

**Architecture:**
- Single repo at `D:/Gimbal/gimbal-platform/` with `backend/` (FastAPI + SQLAlchemy async + SQLite + JWT + Fernet) and `frontend/` (Vite + Vue 3 + TS + Pinia + Vue Router + Element Plus + Prism theme tokens).
- 用例磁盘扫描器 (`CaseLoader`) reads `data/public/` + `data/users/<u>/cases/` on every request, caches `case_id → summary`, invalidates on `os.path.getmtime` delta.
- 形态 X (Disk-scan-on-request) + T1 (cases 表先建空着等 Spec-2 写). Spec-1 不消费 `cases` 表的真实写,只在模块声明里注册模型以便 Alembic 迁移时有锚点。
- 用例配置页 A3 深度: read-only Prism 4-tab layout + L1 👁 in-memory hide toggle + L3 平台默认预设隐藏 `sec-*` / `Sec-*` / `meta.requirementRef`.
- Spec-1 字段隐藏不写 yaml、不入 DB。

**Tech Stack:**
- **Backend:** Python 3.11+, FastAPI 0.115+, SQLAlchemy 2.x async, aiosqlite, pydantic 2.x, pydantic-settings, python-jose[cryptography], passlib[bcrypt], cryptography (Fernet), PyYAML, httpx, loguru.
- **Frontend:** Vite 5, Vue 3, TypeScript 5, Vue Router 4, Pinia 2, Element Plus 2.x, axios, @vueuse/core.
- **测试:** pytest (backend ≥1 functional); 手动 AC-* walkthrough (无前端 unit test,Spec-1).
- **部署:** Windows 11 + bash; `gimbal` already installed at `D:/Capture/Scripts/gimbal.exe`.

---

## Global Constraints

| 项 | 值 |
|---|---|
| 工作目录 | `D:/Gimbal/gimbal-platform/` |
| 后端 Python | `D:/Capture/Scripts/python.exe` (3.11+) |
| Backend 端口 | `http://127.0.0.1:8000` |
| Frontend 端口 | `http://localhost:5173` (Vite default) |
| CORS | 仅 `http://localhost:5173` + `http://127.0.0.1:5173` |
| 数据库 | SQLite at `data/app.db` |
| 默认种子账号 | 首个注册用户自动 is_admin=true；spec-1 不消费 is_admin 字段做 admin-only 路由 |
| 写路径 | Spec-1 范围内只允许：`/api/auth/*` (register/login/refresh/me), `/api/users/*`, `/api/cases/{id}/favorite` / `/api/cases/{id}/copy` |
| 读路径 | `/api/cases/mine` (返回空), `/api/cases/public`, `/api/cases/{id}` |
| Spec-1 后续不接受的写 | `/api/cases/upload`, `/api/cases/{id}/save-as`, `/api/cases/{id}` PATCH (yaml 修改) — 这些都推迟到 Spec-2 |
| No-op endpoint | `POST /api/cases/{id}/favorite` 是 stub 实现 (不报 501，返回 200 让 UI 流转) |
| JWT secret 默认值 | 启动时若 `.env` 无 `JWT_SECRET` 自动生成 48 字节 random url-safe string |
| Fernet 默认值 | 启动时若 `.env` 无 `FERNET_KEY` 自动 `Fernet.generate_key()` — 仅 spec-1 不消费 Fernet (auths 表不写),但生成并保存以便后续 spec 直接复用 |
| 数据落地 | `data/`、`*.db`、`*.tmp.yaml` 全部 `.gitignore` (data/ 永远不进版本控制) |
| Spec-1 必须做的事 | 跑通 AC-1 ~ AC-15 (见 §5 of spec) |

---

## File Structure (locked here)

```
gimbal-platform/
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI app + lifespan + uvicorn entry
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py                 # Settings (pydantic-settings)
│   │   │   ├── db.py                     # engine + SessionLocal + init_db
│   │   │   ├── security.py               # hash/jwt/fernet
│   │   │   └── deps.py                   # get_current_user
│   │   ├── models/
│   │   │   ├── __init__.py               # export all
│   │   │   ├── user.py                   # User
│   │   │   └── case.py                   # Case + CaseFavorite
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                   # LoginIn / RegisterIn / TokenOut / MeOut
│   │   │   ├── user.py                   # UserOut / UserCreateIn / UserPatchIn
│   │   │   └── case.py                   # CaseSummaryOut / CaseDetailOut / CaseListOut
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                   # /api/auth/*
│   │   │   ├── users.py                  # /api/users/*
│   │   │   └── cases.py                  # /api/cases/* + /api/cases/public
│   │   └── services/
│   │       ├── __init__.py
│   │       └── case_loader.py            # CaseLoader class + scan/read
│   ├── data/                              # gitignored
│   │   ├── app.db
│   │   ├── public/sc_e2e应收核销.json     # seed (copy from D:/Gimbal/Gimbal/gimbal-tmp/Scenario_Test_9.json)
│   │   └── users/.gitkeep
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_auth.py                  # register/admin/first/wrong-pw/refresh
│   └── README.md
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── main.ts
│       ├── App.vue
│       ├── router/index.ts
│       ├── stores/
│       │   ├── auth.ts                    # Pinia: tokens + currentUser
│       │   ├── cases.ts                   # Pinia: mine / public list cache
│       │   ├── users.ts                   # Pinia: admin users list cache
│       │   └── hide.ts                    # Pinia: L1 in-memory hide + L3 defaults
│       ├── api/
│       │   ├── http.ts                    # axios instance + interceptors
│       │   ├── auth.ts
│       │   ├── users.ts
│       │   └── cases.ts
│       ├── views/
│       │   ├── Login.vue
│       │   ├── Register.vue
│       │   ├── CasesMine.vue
│       │   ├── CasesPublic.vue
│       │   ├── CaseConfigReadonly.vue
│       │   └── UsersAdmin.vue
│       ├── components/
│       │   ├── TopNav.vue
│       │   ├── TabRow.vue
│       │   ├── CardStack.vue
│       │   ├── StepCard.vue
│       │   ├── FieldRow.vue
│       │   ├── TagPill.vue
│       │   ├── MethodPill.vue
│       │   ├── JsonPreview.vue
│       │   └── DropdownMenu.vue            # reusable ⋯ dropdown for CasesPublic
│       └── styles/
│           ├── theme.css                   # Prism tokens (--accent #4338ca etc.)
│           └── override.css                # Element Plus primary color override
├── docs/
│   ├── PLATFORM_REQUIREMENTS.md
│   └── superpowers/
│       ├── specs/2026-07-12-gimbal-platform-spec1-design.md
│       └── plans/2026-07-12-gimbal-platform-spec1.md
└── .gitignore                              # data/ ; *.db; *.tmp.yaml; node_modules; .venv; .superpowers
```

注：`.superpowers/brainstorm/` 已经存在（wireframe + state），写到 `.gitignore` 排除（mockup 文件不入版本控制）。

---

## Task 1: Backend project boot + Settings + DB engine

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/db.py`
- Create: `backend/.gitignore` (root-level .gitignore for backend)
- Create: `data/.gitkeep` (gitignore will exclude; we add keep for dir)
- Create: `.gitignore` (project root)

**Interfaces:**
- Consumes: nothing
- Produces:
  - `from app.core.config import settings: Settings`
  - `from app.core.db import engine, SessionLocal, get_db, init_db, Base`

- [ ] **Step 1.1: Create project root `.gitignore`**

Path: `D:/Gimbal/gimbal-platform/.gitignore`

```gitignore
# Backend
backend/data/
*.db
*.sqlite
*.tmp.yaml
.venv/
__pycache__/
*.pyc

# Frontend
frontend/node_modules/
frontend/dist/
frontend/.vite/

# Spec / Mockup artifacts (NOT business artifacts)
.superpowers/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 1.2: Create `backend/pyproject.toml`**

Path: `backend/pyproject.toml`

```toml
[project]
name = "gimbal-platform-backend"
version = "0.1.0"
description = "Gimbal Platform backend (FastAPI)"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy>=2.0",
    "pydantic>=2.6",
    "pydantic-settings>=2.0",
    "PyYAML>=6.0",
    "cryptography>=42.0",
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7",
    "python-multipart>=0.0.9",
    "aiosqlite>=0.20",
    "python-dotenv>=1.0",
    "loguru>=0.7",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["app"]
```

- [ ] **Step 1.3: Create `backend/.env.example`**

Path: `backend/.env.example`

```ini
# 平台后端配置 — 拷贝为 .env
# 留空则启动时自动生成 (dev only, prod 必须显式配置)
JWT_SECRET=
JWT_ALGO=HS256
ACCESS_TOKEN_EXPIRE_MIN=60
REFRESH_TOKEN_EXPIRE_DAYS=14
FERNET_KEY=

DATABASE_URL=sqlite+aiosqlite:///./data/app.db
DATA_DIR=./data
PUBLIC_CASES_DIR=./data/public
USERS_CASES_DIR=./data/users

# Gimbal 可执行文件位置 (Spec-1 不消费)
GIMBAL_BIN=gimbal

# CORS
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

- [ ] **Step 1.4: Create `backend/app/__init__.py`**

Path: `backend/app/__init__.py`

```python
"""Gimbal Platform backend."""
```

- [ ] **Step 1.5: Create `backend/app/core/__init__.py`**

Path: `backend/app/core/__init__.py`

```python
"""Core utilities."""
```

- [ ] **Step 1.6: Create `backend/app/core/config.py`**

Path: `backend/app/core/config.py`

```python
"""Application configuration via pydantic-settings."""
from __future__ import annotations

import secrets
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict


def _generate_fernet_key() -> str:
    return Fernet.generate_key().decode()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── JWT ───────────────────────────────────────────────
    JWT_SECRET: str = ""
    JWT_ALGO: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MIN: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # ── Fernet ────────────────────────────────────────────
    FERNET_KEY: str = ""

    # ── DB ────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/app.db"

    # ── Data dir ──────────────────────────────────────────
    DATA_DIR: Path = Path("./data")
    PUBLIC_CASES_DIR: Path = Path("./data/public")
    USERS_CASES_DIR: Path = Path("./data/users")

    # ── Gimbal runner ─────────────────────────────────────
    GIMBAL_BIN: str = "gimbal"

    # ── CORS ──────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    def model_post_init(self, __context) -> None:
        if not self.JWT_SECRET:
            self.JWT_SECRET = secrets.token_urlsafe(48)
        if not self.FERNET_KEY:
            self.FERNET_KEY = _generate_fernet_key()
        for p in (
            self.DATA_DIR,
            self.PUBLIC_CASES_DIR,
            self.USERS_CASES_DIR,
            self.DATA_DIR / "tmp",
            self.DATA_DIR / "reports",
        ):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
```

- [ ] **Step 1.7: Create `backend/app/core/db.py`**

Path: `backend/app/core/db.py`

```python
"""SQLAlchemy async engine + session factory."""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from .config import settings  # noqa: E402

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Create tables; idempotent."""
    from .. import models  # noqa: F401  注册所有模型

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 1.8: Install backend deps**

Bash:
```bash
cd D:/Gimbal/gimbal-platform/backend
D:/Capture/Scripts/pip.exe install -e .
```
Expected: `Successfully installed gimbal-platform-backend-0.1.0 ...`

If `gimbal` import conflict, also run:
```bash
D:/Capture/Scripts/pip.exe install -e D:/Gimbal/Gimbal
```

- [ ] **Step 1.9: Smoke import**

Bash:
```bash
cd D:/Gimbal/gimbal-platform/backend
D:/Capture/Scripts/python.exe -c "from app.core.config import settings; from app.core.db import engine, Base; print('settings.JWT_SECRET len:', len(settings.JWT_SECRET)); print('settings.FERNET_KEY len:', len(settings.FERNET_KEY)); print('engine:', engine)"
```
Expected: prints 3 lines, no ImportError. Engine URL: `sqlite+aiosqlite:///./data/app.db`.

- [ ] **Step 1.10: Commit**

Bash:
```bash
cd D:/Gimbal/gimbal-platform
git add .gitignore backend/pyproject.toml backend/.env.example backend/app/
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-1: backend skeleton (settings + db engine)"
```

---

## Task 2: User model + security primitives (pwd hash / JWT / Fernet)

**Files (relative to `backend/`):**
- Create: `app/models/user.py`
- Create: `app/models/__init__.py`
- Create: `app/core/security.py`
- Create: `tests/__init__.py` (空)

**Step 2.1 — `app/models/user.py`:**
定义 `User` SQLAlchemy model，字段：`id PK / username UNIQUE index / display_name / password_hash / is_admin bool default False / is_active bool default True / created_at server_default=func.now() / updated_at onupdate=func.now()`。继承 `from ..core.db import Base`。

**Step 2.2 — `app/models/__init__.py`:** `from .user import User; __all__ = ["User"]`

**Step 2.3 — `app/core/security.py`:** 模块导入 `CryptContext(schemes=["bcrypt"])`, `Fernet(settings.FERNET_KEY.encode())`, `jwt` (python-jose)。导出函数：
- `hash_password(plain) -> str`
- `verify_password(plain, hashed) -> bool` (try/except 都返 False)
- `_now()` timezone-aware UTC
- `create_access_token(*, subject, **claims)` payload: `{"sub": str(subject), "exp": now+ACCESS_TOKEN_EXPIRE_MIN, "iat": now, "type": "access", **claims}`
- `create_refresh_token(*, subject)` payload: `{"sub": ..., "type": "refresh"}` with REFRESH_TOKEN_EXPIRE_DAYS
- `decode_token(token) -> dict` raises `ValueError` on JWTError
- `fernet_encrypt(plain) -> str` `_fernet.encrypt(plain.encode()).decode()`
- `fernet_decrypt(enc) -> str` raises `ValueError` on InvalidToken

**Step 2.4 — `tests/__init__.py`:** 空文件。

**Step 2.5 — Smoke import:**
```bash
cd D:/Gimbal/gimbal-platform/backend
D:/Capture/Scripts/python.exe -c "from app.models.user import User; from app.core.security import hash_password, create_access_token, decode_token, fernet_encrypt, fernet_decrypt; u = User(username='x', password_hash=hash_password('p')); t = create_access_token(subject=1); print('user:', u.username); print('token len:', len(t)); print('payload:', decode_token(t)['type']); print('round-trip:', fernet_decrypt(fernet_encrypt('hello')))"
```
期望输出 4 行，无异常。

**Step 2.6 — Commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add backend/app/models/ backend/app/core/security.py backend/tests/__init__.py
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-2: User model + security primitives"
```

---

## Task 3: Auth router (register/login/refresh/me) + dependency

**Files (relative to `backend/`):**
- Create: `app/schemas/__init__.py` (空)
- Create: `app/schemas/auth.py`
- Create: `app/core/deps.py`
- Create: `app/routers/__init__.py` (空)
- Create: `app/routers/auth.py`
- Create: `tests/test_auth.py`

**Step 3.1 — `app/schemas/auth.py`:**
Pydantic models:
- `RegisterIn`: `username: str Field(pattern=r"^[A-Za-z0-9_]+$", min_length=3, max_length=32)`; `password: str Field(min_length=8, max_length=128)`; `display_name: str Field(default="", max_length=128)`; field_validator on `password` 校验 must have letter + digit。
- `LoginIn`: `username: str`, `password: str`
- `RefreshIn`: `refresh_token: str`
- `UserPublic(BaseModel)` 含 `from_attributes=True`: `id / username / display_name / is_admin / is_active / created_at: str` (把 datetime 转 isoformat)
- `TokenOut`: `access_token / refresh_token / token_type="bearer" / user: UserPublic`
- `MeOut`: `user: UserPublic`

**Step 3.2 — `app/core/deps.py`:**
`oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")`。
`async def get_current_user(token=Depends(oauth2_scheme), db=Depends(get_db))`: decode_token → 必须 type=access，否则 401；按 sub 查 user；user 不存在或非 active 返 401。导出 `CurrentUser = Annotated[User, Depends(get_current_user)]`。

**Step 3.3 — `app/routers/auth.py`:**
`router = APIRouter(prefix="/auth", tags=["auth"])`。
辅助：`_user_public(u) → UserPublic` (created_at isoformat), `_token_out(u) → TokenOut` (生成两个 token)。

Endpoints:
- `POST /register` → 409 if username 重复 (code=4003); 检查 `User` 表 count，0 → is_admin=True 首位；返回 TokenOut (201)。
- `POST /login` → 401 if not user OR !verify_password (code=4004); 403 if !user.is_active (code=4005)。
- `POST /refresh` → decode refresh_token; 401 if type!=refresh; user 不存在/inactive 401; 返回新 TokenOut。
- `GET /me` → 当前用户。

**Step 3.4 — `tests/test_auth.py`:**
5 个 pytest async 测试 (用 `pytest-asyncio`):
1. `test_first_register_becomes_admin` — 注册 alice 后 is_admin=True。
2. `test_second_register_is_member` — 注册 alice 后注册 bob，bob is_admin=False。
3. `test_login_wrong_password_401` — 错密码返 401。
4. `test_refresh_token_round_trip` — refresh 返新 access_token。
5. `test_register_duplicate_username_409` — 同名返 409。
注意：测试 import `from app.main import create_app` —— 该 create_app 在 Task 5 才出现，本 task 内 pytest 不能跑；属预期，Task 5 完成后才执行。

**Step 3.5 — Commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add backend/app/schemas backend/app/core/deps.py backend/app/routers/auth.py backend/tests/test_auth.py
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-3: auth router + deps + schemas"
```

---

## Task 4: Case models + CaseFavorite + CaseLoader disk scanner

**Files (relative to `backend/`):**
- Create: `app/models/case.py`
- Modify: `app/models/__init__.py` (re-export)
- Create: `app/services/__init__.py` (空)
- Create: `app/services/case_loader.py`
- Create: `data/public/sc_e2e应收核销.json` (复制种子)

**Step 4.1 — 复制种子:**
```bash
mkdir -p D:/Gimbal/gimbal-platform/backend/data/public
cp "D:/Gimbal/Gimbal/gimbal-tmp/Scenario_Test_9.json" D:/Gimbal/gimbal-platform/backend/data/public/sc_e2e应收核销.json
ls -la D:/Gimbal/gimbal-platform/backend/data/public/
```
期望 1 个 ~30KB 文件。

**Step 4.2 — `app/models/case.py`:** 定义 `Case` 与 `CaseFavorite` 两个 model（详见 spec §3.1 数据模型小节）。`Case` 表 spec-1 不写，只为 Alembic 锚点。

**Step 4.3 — `app/models/__init__.py`:** `from .user import User; from .case import Case, CaseFavorite; __all__ = ["User","Case","CaseFavorite"]`

**Step 4.4 — `app/services/__init__.py`:** 空文件。

**Step 4.5 — `app/services/case_loader.py`:** 
- `@dataclass CaseSummary`: case_id/name/module/description/visibility/owner_id/audited/file_path:Path/updated_at:float/tags:list
- `@dataclass _CacheEntry`: summary/payload:dict/mtime:float
- `class CaseLoader`:
  - `__init__`: `_cache={}, _last_full_scan=0.0`
  - `scan(*, owner_id=None) → list[CaseSummary]`: call `_full_scan_if_needed`, 过滤 visibility=='public' (owner_id=None) 或 owner_id 匹配 private。sorted by updated_at desc。
  - `read(case_id) → dict`: 抛 KeyError if not found；否则若 file_path.stat().st_mtime 不等于 entry.mtime 即重 parse。
- 模块私有：
  - `_iter_yaml_files() → Iterable[(path, visibility, owner_id, audited)]`: scan `settings.PUBLIC_CASES_DIR` (visibility=public, audited=True) and `settings.USERS_CASES_DIR/<int_user>/` (visibility=private, audited=False); 仅匹配 `*.y*ml` 和 `*.json`。
  - `_parse_file(path) → dict`: suffix `.json` 用 `json.loads`, 否则 `yaml.safe_load` (空文件返 {}).
  - `_full_scan_if_needed()`: 节流（≤1s）；valid_ids ∩ cache；mtime 不变的 entry skip；删除 stale。
- 模块级 singleton `loader = CaseLoader()`。
- logger.warning 跳过解析失败的文件不抛。
- 详细代码逻辑见本计划已写 Task 1 风格的格式（spec-1 不重抄完整实现，工程实现期直接抄）。

**Step 4.6 — Smoke scan:**
```bash
cd D:/Gimbal/gimbal-platform/backend
D:/Capture/Scripts/python.exe -c "from app.services.case_loader import loader; s = loader.scan(owner_id=None); print('public count:', len(s)); print('first.case_id:', s[0].case_id); print('first.module:', loader.read(s[0].case_id)['meta']['module'])"
```
期望：public count ≥ 1；case_id = "e2e订单到应收核销"；module = "settlement"。

**Step 4.7 — Commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add backend/data/ backend/app/models/case.py backend/app/models/__init__.py backend/app/services/
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-4: case models + CaseLoader disk scanner + seed"
```

---

## Task 5: Cases router (mine/public/get/favorite/copy) + FastAPI main + CORS

**Files (relative to `backend/`):**
- Create: `app/schemas/case.py`
- Create: `app/routers/cases.py`
- Create: `app/main.py`

**Step 5.1 — `app/schemas/case.py`:** 
- `CaseSummaryOut`: 序列化 CaseSummary（case_id/owner_id/audited→bool/updated_at→datetime→isoformat/file_path→str/tags→list）
- `CaseListOut`: items: list[CaseSummaryOut]; total: int
- `CaseDetailOut`: payload: dict (= loader.read(case_id) 返回)；summary: CaseSummaryOut

**Step 5.2 — `app/routers/cases.py`:**
- `router = APIRouter(prefix="/cases", tags=["cases"])`
- 内部 helper `_summary_out(s: CaseSummary) → CaseSummaryOut`
- `GET /mine` (auth)：扫描 loader.scan(owner_id=user.id)；返回 `CaseListOut(items=[], total=0)` (spec-1 形态 X 不写 cases 表，私有扫描是空)；同时返回已收藏公共 case (即扫公共并查 case_favorites DB)。返回 `{"items": [...], "total": N}`
- `GET /public` (auth)：扫 public 全部，**对每个 item 标 favorited_by_me/copied_by_me 两个 bool**（查 favorites DB）。
- `GET /{case_id}` (auth)：loader.read(case_id) 抛 KeyError → 404。
- `POST /{id}/favorite` (auth)：用 favorites DB；spec-1 行为 — insert 一条 user_id+case_id 记录（cases 表此时是空，case_id 直接当 favorite.case_id varchar 不强 FK）。当前 spec-1 简化为"返回 200"，记录到 audit_logs (暂省略)。
- `DELETE /{id}/favorite` (auth)：delete 记录返 204。
- `POST /{id}/copy` (auth)：public 时把 yaml 写到 `settings.USERS_CASES_DIR/<user_id>/<case_id>-copy-<N>.<ext>`，N 是该用户该 case_id 已存在的最大 -copy-N +1；返回 `{"case_id": new_id, "path": str}`。spec-1 不写 favorites 表。

**Step 5.3 — `app/main.py`:**
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.db import init_db
from .routers import auth, users, cases


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Gimbal Platform", version="0.1.0", lifespan=lifespan)
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(cases.router, prefix="/api")
    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
```

**Step 5.4 — Smoke run:**
```bash
cd D:/Gimbal/gimbal-platform/backend
D:/Capture/Scripts/python.exe -m app.main &
SERVER_PID=$!
sleep 3
curl -s http://127.0.0.1:8000/api/health
kill $SERVER_PID 2>/dev/null
```
期望：`{"status":"ok"}`，再 kill。

**Step 5.5 — Run auth tests (Task 3 已经准备好的)：**
```bash
cd D:/Gimbal/gimbal-platform/backend
D:/Capture/Scripts/pip.exe install pytest pytest-asyncio
D:/Capture/Scripts/python.exe -m pytest tests/test_auth.py -v
```
期望 5 个测试全 PASS。如果失败，定位修复后重跑。

**Step 5.6 — Commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add backend/app/schemas/case.py backend/app/routers/cases.py backend/app/main.py
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-5: cases router + FastAPI main + CORS"
```

---

## Task 6: Users router (list/create/patch/delete/reset-password)

**Files (relative to `backend/`):**
- Create: `app/schemas/user.py`
- Create: `app/routers/users.py`

**Step 6.1 — `app/schemas/user.py`:** 
- `UserCreateIn`: `username / password(min_length=8) / display_name / is_admin default=False`
- `UserPatchIn`: `display_name? / is_admin? / is_active? / new_password?` (Optional fields)
- `UserOut`: 用户公开信息（同 spec auth.UserPublic，独立定义；复用字段定义）

**Step 6.2 — `app/routers/users.py`:**
- `router = APIRouter(prefix="/users", tags=["users"])`
- 所有路由都 `Depends(get_current_user)` —— spec-1 不引入 `require_admin`。
- 业务约束（后端硬限制）：
  - 不能删除自己（user.id != target_user.id，else 409 code=4091）。
  - 不能降级最后一个 admin（PATCH is_admin=False 必须查 total_admin > 1，else 409 code=4092）。
  - 状态/角色切换允许任何 caller 调用（spec-1 简化）。
- 路由：
  - `GET /` → `list[UserOut]` 全部用户
  - `POST /` (admin 模式：自动 member，除非 admin 显式开 is_admin)：201 + UserOut + 临时密码回写？spec-1 简化：admin 通过 create_user 默认 not admin；后续 admin 想批量创建 admin 走直接 DB。
  - `PATCH /{user_id}`: 改 display_name / is_active / is_admin / new_password。
  - `POST /{user_id}/reset-password`: 返新随机 12 位密码（明文返一次）。
  - `DELETE /{user_id}`: 不能 self / 不能是最后 admin；成功后级联删该用户的 favorites (但 spec-1 favorites 表空)。
- 写完后 routes 全员可调，但业务限制保护规则生效。

**Step 6.3 — Smoke:**
启 backend 后 curl 测一遍 (Task 5 启服务方式)，用第一个注册用户 admin 创建第二个用户 wang_p / Test2026!，然后 patch 它，删除时确认无法删自己。

**Step 6.4 — Commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add backend/app/schemas/user.py backend/app/routers/users.py
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-6: users router (list/create/patch/delete/reset-password)"
```

---

## Task 7: Frontend project boot (Vite + Vue 3 + TS + Pinia + Router + EP)

**Files (relative to `frontend/`):**
- Create: `package.json`
- Create: `tsconfig.json`, `tsconfig.node.json`
- Create: `vite.config.ts`
- Create: `index.html`
- Create: `src/main.ts`, `src/App.vue`

**Step 7.1 — `package.json`:** Vue 3.5 / Vite 5 / TS 5 / Pinia 2 / Vue Router 4 / Element Plus 2 / axios 1.7 / @vueuse/core / typescript / @vitejs/plugin-vue。scripts: `dev / build / preview`。

**Step 7.2 — `tsconfig.json`:** target=ES2022, strict=true, baseUrl=src, paths: `@/*`，types: ["vite/client"]。`tsconfig.node.json` for vite.config.ts。

**Step 7.3 — `vite.config.ts`:** plugins: [vue()], server: { port:5173, host:'localhost', proxy: {'/api': { target:'http://127.0.0.1:8000', changeOrigin:true }}}。alias `@` → `src/`。

**Step 7.4 — `index.html`:** `<div id="app"></div>`, `<script type="module" src="/src/main.ts"></script>"。

**Step 7.5 — `src/main.ts`:** createApp + use pinia + use router + use Element Plus (按需)。`import 'element-plus/dist/index.css'` + `'./styles/theme.css'` + `'./styles/override.css'`。

**Step 7.6 — `src/App.vue`:** `<router-view />` only。先空 router/index.ts (Task 8 加)。

**Step 7.7 — `npm install`:**
```bash
cd D:/Gimbal/gimbal-platform/frontend
npm install
```

**Step 7.8 — Smoke build:**
```bash
cd D:/Gimbal/gimbal-platform/frontend
npx vite build 2>&1 | tail -10
```
期望：build 成功；输出在 `dist/`。如有错误，定位修复。

**Step 7.9 — Commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add frontend/package.json frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts frontend/index.html frontend/src/main.ts frontend/src/App.vue
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-7: frontend project boot (vite+vue+ts+pinia+router+EP)"
```

---

## Task 8: Theme CSS + Pinia stores (auth/cases/users/hide) + axios http + router

**Files (relative to `frontend/src/`):**
- Create: `styles/theme.css`
- Create: `styles/override.css`
- Create: `api/http.ts`
- Create: `api/auth.ts`
- Create: `api/users.ts`
- Create: `api/cases.ts`
- Create: `stores/auth.ts`
- Create: `stores/cases.ts`
- Create: `stores/users.ts`
- Create: `stores/hide.ts`
- Create: `router/index.ts`

**Step 8.1 — `styles/theme.css`:**
Prism 风格 tokens: `--color-bg-primary: #ffffff; --color-bg-secondary: #f5f3ee; --color-text-primary: #1f2933; --color-text-secondary: #64748b; --color-text-tertiary: #94a3b8; --color-border-tertiary: #e2e8f0; --color-border-secondary: #cbd5e1; --font-mono: ui-monospace, "Cascadia Mono", "JetBrains Mono", Menlo, monospace; --accent: #4338ca; --accent-hover: #3730a3; --accent-soft: #eef2ff; --accent-soft-border: #c7d2fe; --red: #e24b4a; --green: #22c55e; --amber: #f59e0b;`。Body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif; font-size: 13px; color: var(--color-text-primary); background: var(--color-bg-secondary); }

**Step 8.2 — `styles/override.css`:** Element Plus primary 改成 `--el-color-primary: var(--accent);` + `--el-color-primary-light-3..9` 各自映射。

**Step 8.3 — `api/http.ts`:** axios.create({ baseURL: '/api', timeout: 30_000 })。请求拦截：用 `useAuthStore` 注入 `Authorization: Bearer <accessToken>`。响应拦截：401 试 refresh 一次，新 token 重试原请求；refresh 失败跳 /login 并清 token。错误统一 `{code, msg}` 透传给 UI（不弹 toast 这一层让 UI 自己处理）。

**Step 8.4 — `api/auth.ts`:** 导出 `register(body)`, `login(body)`, `refresh(refreshToken)`, `me()` 四个函数，调用 http POST/GET。

**Step 8.5 — `api/users.ts`:** `list()`, `create(body)`, `patch(id, body)`, `resetPassword(id)`, `remove(id)`。

**Step 8.6 — `api/cases.ts`:** `mine()`, `public()`, `get(caseId)`, `favorite(id)`, `unfavorite(id)`, `copy(id)`, `payloadId` 提取顶层 scenarioId。

**Step 8.7 — `stores/auth.ts`:** state: `accessToken / refreshToken / currentUser`；actions: `login / register / refreshAccess / logout / fetchMe`；`this` 持久化到 localStorage key `gimbal-auth`。getter `isAuthenticated = !!accessToken`。

**Step 8.8 — `stores/cases.ts`:** state: `mine.favorites: CaseSummary[] / mine.uploads: CaseSummary[] / publicLibrary: CaseSummary[]`。actions: `fetchMine / fetchPublic / fetchOne(id) / toggleFavorite(id)`。Memoize：5s 内不重复 fetch。

**Step 8.9 — `stores/users.ts`:** state: `list: UserOut[] / summary: {total,active,admin,recent}`。actions: `fetchAll / createUser / patchUser / deleteUser / resetPassword`。

**Step 8.10 — `stores/hide.ts`:** state: `hiddenPaths: Set<string>`；L3 defaults 常量:
```ts
const L3_DEFAULTS = [
  'api.headers["sec-ch-ua-platform"]',
  'api.headers["sec-ch-ua"]',
  'api.headers["sec-ch-ua-mobile"]',
  'api.headers["Sec-Fetch-Site"]',
  'api.headers["Sec-Fetch-Mode"]',
  'api.headers["Sec-Fetch-Dest"]',
  'meta.requirementRef',
]
```
初始化时 `hiddenPaths = new Set(L3_DEFAULTS)`。actions: `toggleL1(path)` / `setShowHidden(bool)` / `recompute(path)`。Getter `isHidden(path)` / `shouldRender(path, showAll)`。

**Step 8.11 — `router/index.ts`:** 路由表（spec §4.1）。`beforeEach` 守卫：未登录访问受保护路由跳 /login (带 ?redirect=)；已登录访问 /login 或 /register 跳 /cases/mine。

**Step 8.12 — Commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add frontend/src/styles frontend/src/api frontend/src/stores frontend/src/router
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-8: theme + api + stores + router"
```

---

## Task 9: Login + Register views

**Files (relative to `frontend/src/views/`):**
- Create: `Login.vue`
- Create: `Register.vue`

**Step 9.1 — `Login.vue`:** 严格按 wireframe 2 设计：380px 居中卡片 / 浅紫渐变背景 / 品牌头 / 错误条 / 用户名 + 密码（密码右侧👁切换可见） / 30 天保持登录 / 忘记密码占位 / 主按钮 / 立即注册链接 / 开发模式提示（首次 db 空时显示）。使用 Element Plus `el-card / el-input / el-form / el-button`。调 `useAuthStore().login(...)`；成功后 router.push 到 ?redirect 或 /cases/mine。

**Step 9.2 — `Register.vue`:** 严格按 wireframe 3 设计：420px 居中卡片 / 双列用户名+昵称 / 密码+ 4 段强度条 / 4 条规则勾 / 确认密码实时一致 / 隐私勾选 / 主按钮 / 已有账号去登录。密码强度算法：长度 (≥8 -> +1, ≥12 -> +1), 含字母 -> +1, 含数字 -> +1, 含特殊字符 -> +1; 总分 0-2=WEAK, 3=OK, 4=STRONG（暂不强求特殊字符）。

**Step 9.3 — Smoke dev server:**
```bash
cd D:/Gimbal/gimbal-platform/frontend
npx vite &
VITE_PID=$!
sleep 5
curl -s -I http://localhost:5173/ | head -3
echo "---"
curl -s http://localhost:5173/ | head -5
kill $VITE_PID 2>/dev/null
```
期望：HTTP/1.1 200 OK；HTML 含 `<div id="app">`。

**Step 9.4 — Commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add frontend/src/views/Login.vue frontend/src/views/Register.vue
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-9: Login + Register views"
```

---

## Task 10: TopNav component + Layout shell + App router-view 包裹

**Files (relative to `frontend/src/`):**
- Create: `components/TopNav.vue`
- Create: `views/_Layout.vue` (受保护路由的 layout)

**Step 10.1 — `components/TopNav.vue`:** 顶部固定栏 48px 高 (#1f2933)，左侧 status dot + "platform"；中部 4 nav entries（cases/mine, cases/public, admin/users — "auths" 占位但路由不实现）；右侧用户徽章（admin/member badge）+ 登出按钮。受 props 控制当前激活项。

**Step 10.2 — `views/_Layout.vue`:** 包含 TopNav + `<router-view />`。router 配置里把受保护路由的 component 设为 `_Layout.vue`，并使用 `<router-view />` 子嵌套渲染页面（通过 `<router-view v-slot="{ Component }">` + `<keep-alive>` 可选 —— spec-1 不必持久，简化为单 `<router-view />`）。

实际方案：把 TopNav 提到 App.vue，统一渲染；所有路由 component 是 page view。**简化方案**：
- 不引入 `_Layout.vue`。
- App.vue 直接渲染 `<TopNav v-if="authStore.isAuthenticated" />` + `<router-view />`。
- 登录/注册页 authStore.isAuthenticated=false → 不渲染 TopNav。

**Step 10.3 — Smoke:** 同 Task 9.3。

**Step 10.4 — Commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add frontend/src/components/TopNav.vue frontend/src/App.vue
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-10: TopNav + App layout"
```

---

## Task 11: CasesMine.vue + helper components (TabRow/TagPill/MethodPill/FieldRow)

**Files (relative to `frontend/src/`):**
- Create: `views/CasesMine.vue`
- Create: `components/TagPill.vue`
- Create: `components/MethodPill.vue`
- Create: `components/FieldRow.vue`

**Step 11.1 — `components/TagPill.vue`:** props `tags: string[]`, emit `update:order` (拖拽)。Element Plus 的 `el-tag` 派系，紫底浅紫字，小圆角 12px。spec-1 简化：spec-1 不真正拖 tag，spec-2 才需要；先静态渲染。

**Step 11.2 — `components/MethodPill.vue`:** props `method: 'GET'|'POST'|'PUT'|'DELETE'|'PATCH'`。按 Prism 风格着色：GET = 绿、POST = 紫、PUT = 黄、DELETE = 红、PATCH = 青。

**Step 11.3 — `components/FieldRow.vue`:** props `label: string`, `value: any`, `mono?: boolean`, `eye?: boolean` (右上👁), `hidden?: boolean`。emit `toggle-eye`。label 宽度 130px，背景用 #f8fafc。单列 grid。

**Step 11.4 — `views/CasesMine.vue`:** 严格按 wireframe 4。TopNav 在 App.vue 已渲染，本 view 内不需要再放。
- Page header: 标题 + 元信息 (调用 casesStore 总数=4 / 1 收藏) + 搜索 + 高级过滤 + 上传按钮 disabled。
- Tabs: 我的上传 (3) / ⭐ 我的收藏 (1)。
- Element Plus `el-table` 渲染 8 列。spec-1 简化：表格行只展示当前 users 数据；任何 row 名字 click 跳 `/cases/:caseId/config`；⭐ row 调 favorite toggle。

**Step 11.5 — Dev smoke:**
启动前后端，访问 /cases/mine，能看到 e2e应收核销 行（来自公共种子）。表格渲染 OK。

**Step 11.6 — Commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add frontend/src/components/TagPill.vue frontend/src/components/MethodPill.vue frontend/src/components/FieldRow.vue frontend/src/views/CasesMine.vue
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-11: CasesMine + helpers"
```

---

## Task 12: CasesPublic.vue + DropdownMenu component (v2 layout)

**Files:**
- Create: `views/CasesPublic.vue`
- Create: `components/DropdownMenu.vue`

**Step 12.1 — `components/DropdownMenu.vue`:** props `trigger: '⋯' | string`；slot 默认菜单 items。Element Plus `el-dropdown`，trigger: click。spec-1 仅展示 3 项：👁 查看 / ★ 收藏（动态切换为"取消收藏"当已收藏）/ 📋 复制到我的 / 分隔 / ⤴ 打开源 yaml（暂无 href 只是占位 toast）。

**Step 12.2 — `views/CasesPublic.vue`:** 严格按 wireframe 5/v2 设计。无审核 tab；表格行内 audit 列（绿/米 tag）。操作列 ⋯ dropdown。

注意：v2 设计里说"无审核 tab"，但 column audit 列展示同色 tag —— 简化实施：tsc tags 列展示简化 1 个 ✓已审核 或 ⏳待审（spec-1 数据全 visible=public。

**Step 12.3 — Author popover:** 点击作者名 → 用 Element Plus `el-popover` 显示小卡片（avatar 圆 + 上传数 + 案例数）。spec-1 简化版本：仅显示头像 + 用户名 + "TA 上传的公共用例 N 条"。

**Step 12.4 — Dev smoke:** 访问 /cases/public 看到种子用例出现在表格。

**Step 12.5 — Commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add frontend/src/components/DropdownMenu.vue frontend/src/views/CasesPublic.vue
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-12: CasesPublic v2 (no-audit-tab + ⋯ dropdown + author popover)"
```

---

## Task 13: CaseConfigReadonly.vue + StepCard + JsonPreview + L1/L3 hide wiring

**Files (relative to `frontend/src/`):**
- Create: `views/CaseConfigReadonly.vue`
- Create: `components/StepCard.vue`
- Create: `components/JsonPreview.vue`

**Step 13.1 — `components/JsonPreview.vue`:** props `data: any`。Element Plus 的 `el-input` (type=textarea, autosize) 默认显示 compact 模式（key 单行 ellipsis）。spec-1 用只读 textarea + monospace 字体；显示 JSON.stringify 缩进 2。value 受控。如果 >200 行默认折叠。

**Step 13.2 — `components/StepCard.vue`:** props `step: any`, `idx: number`, `hiddenDefault: boolean` (L3 应用)。事件 `toggle`。内部 sub-tab: description/api/request/strategy。当前 sub-tab=request 时渲染 Headers key-value 表（FieldRow）。

L1 👁 toggle: 调用 `hideStore.toggleL1(path)`。
L3 默认隐藏: 计算 `hideStore.isHidden(path)` 自动应用；展开时若有 L3 隐藏字段显示顶部 "本步骤隐藏了 6 个浏览器嗅探 header" 蓝色提示卡 + "👁 显示隐藏"按钮。

**Step 13.3 — `views/CaseConfigReadonly.vue`:** Prism 4 tab 折叠面板 + 顶部固定栏 + 👁 toggle 按钮（top fixed bar 右侧 toggle "👁 显示隐藏"）。
- Tabs: 01 meta / 02 config / 03 resource / 04 steps。spec-1 只 active steps (简化)
- Card stack: 渲染所有 step；step 默认折叠。点开渲染 StepCard。
- 调用 casesStore.fetchOne(caseId) → loader.read 返回的 yaml dict 解析后传入 StepCard。
- L3 hints 蓝条只在当前 step headers 含 sec-*/Sec-* 时显示。

**Step 13.4 — Dev smoke:** 登录后访问 `/cases/sc_e2e订单到应收核销/config` (或类似 ids), 看到 27 step 卡片；展开 #2 看到 Headers 默认只显示 Authorization + Content-Type (L3 隐藏生效)；👁 单字段切换；👁 toggle 显示隐藏生效。

**Step 13.5 — Commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add frontend/src/components/StepCard.vue frontend/src/components/JsonPreview.vue frontend/src/views/CaseConfigReadonly.vue
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-13: CaseConfigReadonly (L1/L3 hide wiring)"
```

---

## Task 14: UsersAdmin.vue + CreateUserModal + ConfirmDialog

**Files (relative to `frontend/src/`):**
- Create: `views/UsersAdmin.vue`
- Create: `components/CreateUserModal.vue`
- Create: `components/ConfirmDialog.vue`

**Step 14.1 — `components/ConfirmDialog.vue`:** Element Plus `el-dialog` props: `open, title, content, danger?`。slot actions: 默认 [取消, 确认]；emit `confirm`。spec-1 用于"删除用户"—— 内容需要输入 username 才允许 confirm（pinia / 父子 store 间 local state 控制）。

**Step 14.2 — `components/CreateUserModal.vue`:** 表单: username / display_name / password (with 🎲 random) / is_admin radio。emit `submit(body)`, `cancel`。

**Step 14.3 — `views/UsersAdmin.vue`:** 严格按 wireframe 6。TopNav 在 App.vue 已渲染。
- Page header: 12 用户 / 10 启用 / 2 停用 / 3 admin / 7 天 5 人登录（spec-1 简化默认 footer）。
- Element Plus `el-table` 8 列；行 ⋯ dropdown menu: 编辑昵称 / 修改角色 / 重置密码 / 停用·启用 / 删除。
- "— 自助 —" 处理自己行。
- 删除二次 confirm dialog。
- 创建 modal。

**Step 14.4 — Dev smoke:** 登录首个 admin（alice），访问 /admin/users，看到表 + 自己行 + "你"紫牌 + — 自助 —。点 + 创建 wang_p，列表多一行。点删除 wang_p，弹出 confirm 输入 wang_p 才能确认。

**Step 14.5 — Commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add frontend/src/components/CreateUserModal.vue frontend/src/components/ConfirmDialog.vue frontend/src/views/UsersAdmin.vue
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-14: UsersAdmin + modals"
```

---

## Task 15: Manual AC-* walkthrough + final verify + Spec-1 sign-off

**Goal:** walk through AC-1 ~ AC-15 from spec §5 with real browser + backend.

**Step 15.1 — Backend live:**
```bash
cd D:/Gimbal/gimbal-platform/backend
D:/Capture/Scripts/python.exe -m app.main &
SERVER_PID=$!
sleep 4
echo "server pid: $SERVER_PID"
curl -s http://127.0.0.1:8000/api/health
```
期望 `{"status":"ok"}`。记录 $SERVER_PID 后续用。

**Step 15.2 — Frontend live (separate terminal):**
```bash
cd D:/Gimbal/gimbal-platform/frontend
npx vite &
VITE_PID=$!
sleep 5
echo "vite pid: $VITE_PID"
```
访问 http://localhost:5173。

**Step 15.3 — Run AC-1:** 浏览器打开 http://localhost:5173 → 跳 /login → 显示"开发模式提示: admin/admin 黄色条"。
(First-time dev 提示：当前账号 db 空，应该提示.)
**AC-1 ✓**

**Step 15.4 — Register alice & login:** /register → 注册 alice / Hello2026! → 绿色成功条 + 跳 /cases/mine → 跳回 alice (member)。等下，先重新 login admin/admin 会发现 alice 是 admin（首位注册），admin flag 已自动。

Actually AC-2 期望"liuyu / Hello2026!"为非首位注册人。先 token 拿到 alice 的 refresh，admin 界面恢复后再注册 liuyu。具体 run order:
1. 浏览器注册 alice (首位→ admin)
2. 退出
3. 注册 liuyu
4. /cases/mine 是空
**AC-2 ~ AC-3 ✓**

**Step 15.5 — Public/mine CRUD walk:** 登录 alice → /cases/public → 看到 e2e应收核销。/cases/mine → 我的上传 (0) + 我的收藏 (0)。

点 ⋯ → 收藏 → 切到我的收藏 tab，出现该用例。**AC-4 ~ AC-6 ✓**

**Step 15.6 — Config page:** 点行名或 ⋯ → 查看 → 进 /cases/sc_e2e订单到应收核销/config。
- 默认激活 steps tab。
- 默认折叠所有 step。
- 展开 #2 → sub-tab=request → headers 表只显示 Authorization + Content-Type（L3 隐藏生效）。
**AC-7 ~ AC-8 ✓**

**Step 15.7 — L1 切换:** 在 #2 Headers 行点任一 👁 按钮 → 该行变灰 strike；再点 🔓 切换回来。**AC-9 ✓**

**Step 15.8 — Display toggle:** 顶部 👁 「显示隐藏」开启 → L1 + L3 所有隐藏行浮现 (灰 strike)。关闭 toggle → 隐藏行重新消失。**AC-10 ✓**

**Step 15.9 — UsersAdmin:** /admin/users → 看到 2 行 (alice 你, liuyu)；alice 行操作列 "— 自助 —"；liuyu ⋯ 菜单可选 删除。**AC-11 ✓**

**Step 15.10 — Create user:** 点 + 创建用户 → wang_p / Test2026! / 角色 成员 → 列表 +1 行 wang_p。**AC-12 ✓**

**Step 15.11 — Delete confirm:** 选中 wang_p ⋯ → 删除 → 弹 dialog → 要求输入 wang_p 才能 confirm。**AC-13 ✓**

**Step 15.12 — Logout/login:** 登出 alice → 重新登录 → token 重新发放；in-memory hide 状态被清空（L1 L3 reset）。**AC-14 ✓**

**Step 15.13 — Copy public case:** /cases/public 选中 e2e应收核销 ⋯ → 复制到我的 → 后端 clone 成功 → 切到 /cases/mine 看到新私有副本。**AC-15 ✓**

**Step 15.14 — Run pytest (Task 5.5 已就位):**
```bash
cd D:/Gimbal/gimbal-platform/backend
D:/Capture/Scripts/python.exe -m pytest tests/test_auth.py -v
```
期望：5 passed。

**Step 15.15 — Stop services:**
```bash
kill $SERVER_PID $VITE_PID 2>/dev/null
```

**Step 15.16 — Spec-1 sign-off commit:**
```bash
cd D:/Gimbal/gimbal-platform
git add docs/
git -c user.email=spec@local -c user.name="gimbal-spec" commit -m "task-15: AC-* verified; spec-1 sign-off" || echo "no doc changes"
```

**Acceptance:** AC-1~AC-15 全 PASS。Spec-1 完成。下一步：用户回归确认 → Spec-2 启动。

---

## 自审 (Self-Review of the plan)

| 项 | 状态 |
|---|---|
| Spec coverage | AC-1~AC-15 全映射到 task (3 / 8 / 9 / 11 / 12 / 13 / 14 / 15 各自的实现) |
| Placeholder scan | 无 TBD/TODO；代码块完整或附"详见 spec-1"指引 |
| Type/method consistency | `User` / `Case` / `CaseFavorite` / `CaseLoader.loader` / `CaseSummary` 一致；HTTP `/api/{prefix}` 一致；store 名一致 |
| 已知不阻断问题 | ⚠ Task 5 测试 import `from app.main import create_app` — Task 5 自带 create_app，立即解 |
| Filesystem 与 spec-1 §2 一致 | ✅ |
| Global Constraints 锁定所有 spec 不变量 | ✅ |

