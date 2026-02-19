from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _load_env_files() -> None:
    root = Path(__file__).resolve().parents[2]
    candidates = [
        root / ".env",
        root / ".env.local",
        root / "frontend" / ".env.local",
    ]
    for path in candidates:
        if path.exists():
            load_dotenv(path, override=False)


_load_env_files()


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_root: Path
    assets_root: Path
    output_root: Path
    logs_root: Path
    openai_api_key: str
    openai_model: str
    pexels_api_key: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    elevenlabs_model_id: str
    gtts_lang: str
    cors_origins: list[str]

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(__file__).resolve().parents[2]
        data_root = root / "data"
        assets_root = data_root / "assets"
        output_root = data_root / "output"
        logs_root = root / "logs"
        data_root.mkdir(parents=True, exist_ok=True)
        assets_root.mkdir(parents=True, exist_ok=True)
        output_root.mkdir(parents=True, exist_ok=True)
        logs_root.mkdir(parents=True, exist_ok=True)
        origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
        cors_origins = [o.strip() for o in origins.split(",") if o.strip()]
        return cls(
            project_root=root,
            data_root=data_root,
            assets_root=assets_root,
            output_root=output_root,
            logs_root=logs_root,
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            pexels_api_key=os.getenv("PEXELS_API_KEY", ""),
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
            elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL"),
            elevenlabs_model_id=os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
            gtts_lang=os.getenv("GTTS_LANG", "en"),
            cors_origins=cors_origins,
        )


SETTINGS = Settings.from_env()
