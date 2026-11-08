from __future__ import annotations

import os
from dataclasses import dataclass


def parse_api_keys(value: str) -> tuple[tuple[str, str], ...]:
    """Parse secret:owner pairs without logging the secret value."""
    pairs: list[tuple[str, str]] = []
    for entry in value.split(","):
        entry = entry.strip()
        if not entry:
            continue
        secret, separator, owner = entry.partition(":")
        if not separator or not secret or not owner:
            raise ValueError("NEUROFAST_API_KEYS entries must use secret:owner format")
        pairs.append((secret, owner))
    return tuple(pairs)


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
    api_keys: tuple[tuple[str, str], ...] = parse_api_keys(os.getenv("NEUROFAST_API_KEYS", ""))
    request_max_bytes: int = int(os.getenv("NEUROFAST_REQUEST_MAX_BYTES", "1048576"))
    rate_limit_per_minute: int = int(os.getenv("NEUROFAST_RATE_LIMIT_PER_MINUTE", "60"))


settings = Settings()
