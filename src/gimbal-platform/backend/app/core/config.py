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
    # Resolved to absolute at startup so subprocess argv / DB log paths
    # never land as relative ``./data\...`` which then shows up in the
    # admin "command preview" as e.g. ``data\tmp\exec_17_1.yaml``.
    DATA_DIR: Path = Path("./data").resolve()
    PUBLIC_CASES_DIR: Path = (Path("./data") / "public").resolve()
    USERS_CASES_DIR: Path = (Path("./data") / "users").resolve()

    # ── Gimbal runner ─────────────────────────────────────
    GIMBAL_BIN: str = "gimbal"
    # Project root for the gimbal CLI subprocess.  After the directory
    # reshuffle ``gimbal-platform`` lives at
    # ``<gimbal>/src/gimbal-platform``, so the gimbal CLI's
    # ``ConfigLoader._find_base_dir()`` (which walks upward from cwd
    # looking for ``pyproject.toml``) must be launched with cwd =
    # gimbal's own root — otherwise it stops at gimbal-platform's own
    # pyproject.toml and fails to load ``src/gimbal/config/*.yml``.
    # Default is derived from this file's location assuming the layout
    #   <gimbal>/src/gimbal-platform/backend/app/core/config.py
    # i.e. parents[5] == gimbal root.  Override via env GIMBAL_PROJECT_ROOT.
    GIMBAL_PROJECT_ROOT: Path | None = None
    # ── Gimbal runner HTTP service (#4 run 最小链路) ──────
    # ``gimbal run server`` 默认监听 127.0.0.1:8766(8765 被 plate 实占)。
    # run dispatcher 每行 convert 成功后 POST /run 到这里执行。
    GIMBAL_BASE_URL: str = "http://127.0.0.1:8766"
    GIMBAL_TIMEOUT_SEC: float = 300.0

    # ── LogHub retention ──────────────────────────────────
    # Channels in DONE state older than this are evicted by the
    # background sweeper in main.lifespan.  Set to 0 to disable
    # eviction (channels kept until process exit).
    LOG_HUB_TTL_HOURS: int = 24
    LOG_HUB_SWEEP_INTERVAL_MIN: int = 60

    # ── CORS ──────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ── Plate integration (V3 scenario composer) ──────────
    # Base URL of the gimbal-plate FastAPI service.  Default port 8765 to
    # stay out of Platform's 8000 + Vite's 5173 footprint.
    PLATE_BASE_URL: str = "http://127.0.0.1:8765"
    PLATE_TIMEOUT_SEC: float = 30.0

    def model_post_init(self, __context) -> None:
        if not self.JWT_SECRET:
            self.JWT_SECRET = secrets.token_urlsafe(48)
        if not self.FERNET_KEY:
            self.FERNET_KEY = _generate_fernet_key()
        # Force-absolute.  pydantic-settings re-coerces from env vars which
        # may hand us back a relative ``./data``; normalize again here so
        # every downstream consumer (subprocess argv, DB log paths, UI
        # preview) sees e.g. ``D:\Gimbal\Gimbal\gimbal-platform\data\tmp\...``.
        self.DATA_DIR = self.DATA_DIR.resolve()
        self.PUBLIC_CASES_DIR = self.PUBLIC_CASES_DIR.resolve()
        self.USERS_CASES_DIR = self.USERS_CASES_DIR.resolve()
        # Resolve the gimbal project root: prefer env override, else
        # compute from this file's location (assumes
        #   gimbal/src/gimbal-platform/backend/app/core/config.py
        # → parents[5] is the gimbal root).
        if self.GIMBAL_PROJECT_ROOT is None:
            self.GIMBAL_PROJECT_ROOT = Path(__file__).resolve().parents[5]
        else:
            self.GIMBAL_PROJECT_ROOT = Path(self.GIMBAL_PROJECT_ROOT).resolve()
        for p in (
            self.DATA_DIR,
            self.PUBLIC_CASES_DIR,
            self.USERS_CASES_DIR,
            self.DATA_DIR / "tmp",
            self.DATA_DIR / "reports",
        ):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
