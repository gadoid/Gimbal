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

    # Set in model_post_init — True when the corresponding secret was
    # freshly generated because env/.env didn't provide one.  Not part of
    # the serialized settings; read-only diagnostics for the startup
    # warning in main.lifespan.
    JWT_SECRET_EPHEMERAL: bool = False
    FERNET_KEY_EPHEMERAL: bool = False

    def model_post_init(self, __context) -> None:
        # Ephemeral-key flags: True when the secret was freshly generated
        # because the env/.env didn't provide one.  A restart then rotates
        # the key (all JWT sessions invalidated / all Fernet ciphertexts
        # undecryptable) — the app logs a loud warning at startup (see
        # main.lifespan) so operators notice instead of debugging phantom
        # "401 every morning" incidents.
        self.JWT_SECRET_EPHEMERAL = not self.JWT_SECRET
        self.FERNET_KEY_EPHEMERAL = not self.FERNET_KEY
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
        for p in (
            self.DATA_DIR,
            self.PUBLIC_CASES_DIR,
            self.USERS_CASES_DIR,
            self.DATA_DIR / "tmp",
            self.DATA_DIR / "reports",
        ):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
