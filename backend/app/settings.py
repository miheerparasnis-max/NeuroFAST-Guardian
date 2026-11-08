from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_path: str = os.getenv("NEUROFAST_DATABASE_PATH", "./neurofast.db")
    demo_mode: bool = os.getenv("NEUROFAST_DEMO_MODE", "true").lower() == "true"
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "NEUROFAST_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
        ).split(",")
        if origin.strip()
    )


settings = Settings()
