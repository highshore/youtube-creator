from __future__ import annotations

import random
from pathlib import Path

from ..state import ShortState
from ..utils import add_error, bump_attempt, ensure_runtime_dirs, estimate_narration_seconds, make_tone_wav, timestamp_name


def music_selector(state: ShortState) -> ShortState:
    state = dict(state)
    ensure_runtime_dirs(state)
    bump_attempt(state, "music_selector")

    try:
        music_dir = Path(state["assets_dir"]) / "music"
        tracks = [
            p
            for p in music_dir.glob("*")
            if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
        ]
        if tracks:
            state["bg_music"] = str(random.choice(tracks))
        else:
            fallback = music_dir / timestamp_name("bg_music", ".wav")
            make_tone_wav(
                fallback,
                duration_s=max(12.0, estimate_narration_seconds(state.get("script", ""))),
                freq=112.0,
                volume=0.05,
            )
            state["bg_music"] = str(fallback)
            add_error(state, "No local royalty-free music found. Generated fallback tone music.")
        state["status"] = "music_ready"
        state["next_action"] = "assemble_video"
        return state
    except Exception as exc:  # noqa: BLE001
        add_error(state, f"music_selector error: {exc}")
        state["status"] = "failed:music_selector"
        state["next_action"] = "assemble_video"
        return state
