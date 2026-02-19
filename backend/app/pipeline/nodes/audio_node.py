from __future__ import annotations

from pathlib import Path

import requests
from loguru import logger

from ...config import SETTINGS
from ..retry import retry_call
from ..state import ShortState
from ..utils import (
    add_error,
    bump_attempt,
    ensure_runtime_dirs,
    estimate_narration_seconds,
    make_tone_wav,
    timestamp_name,
)


def _tts_elevenlabs(script: str, output_path: Path) -> bool:
    if not SETTINGS.elevenlabs_api_key:
        return False

    def _call() -> bool:
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{SETTINGS.elevenlabs_voice_id}",
            headers={
                "xi-api-key": SETTINGS.elevenlabs_api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": script,
                "model_id": SETTINGS.elevenlabs_model_id,
                "voice_settings": {"stability": 0.4, "similarity_boost": 0.75},
            },
            timeout=60,
        )
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return True

    try:
        return retry_call("tts_elevenlabs", _call, max_attempts=3)
    except Exception:  # noqa: BLE001
        return False


def _tts_gtts(script: str, output_path: Path) -> bool:
    try:
        from gtts import gTTS
    except Exception:
        return False
    try:
        gTTS(text=script, lang=SETTINGS.gtts_lang).save(str(output_path))
        return True
    except Exception:  # noqa: BLE001
        return False


def audio_narration(state: ShortState) -> ShortState:
    state = dict(state)
    ensure_runtime_dirs(state)
    bump_attempt(state, "audio_narration")

    script = state.get("script", "").strip()
    if not script:
        add_error(state, "audio_narration requires script.")
        state["status"] = "failed:missing_script"
        state["next_action"] = "needs_script_revision"
        return state

    try:
        audio_dir = Path(state["assets_dir"]) / "audio"
        mp3_path = audio_dir / timestamp_name("narration", ".mp3")
        wav_path = audio_dir / timestamp_name("narration_fallback", ".wav")

        generated = _tts_elevenlabs(script, mp3_path)
        if not generated:
            generated = _tts_gtts(script, mp3_path)

        if generated:
            state["audio_narration"] = str(mp3_path)
            logger.info("Narration generated: {}", mp3_path)
        else:
            make_tone_wav(wav_path, estimate_narration_seconds(script), freq=250.0, volume=0.1)
            state["audio_narration"] = str(wav_path)
            add_error(state, "TTS unavailable. Fallback tone narration was generated.")

        state["status"] = "audio_ready"
        state["next_action"] = "select_music"
        return state
    except Exception as exc:  # noqa: BLE001
        add_error(state, f"audio_narration error: {exc}")
        state["status"] = "failed:audio_narration"
        state["next_action"] = "select_music"
        return state
