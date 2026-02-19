from __future__ import annotations

from pathlib import Path

from ..state import ShortState
from ..utils import add_error, bump_attempt, ensure_runtime_dirs, timestamp_name, write_json


def completion_node(state: ShortState) -> ShortState:
    state = dict(state)
    ensure_runtime_dirs(state)
    bump_attempt(state, "completion_node")
    try:
        output_dir = Path(state["output_dir"])
        metadata_path = output_dir / timestamp_name("short_metadata", ".json")
        payload = {
            "job_id": state.get("job_id", ""),
            "topic": state.get("topic", ""),
            "script": state.get("script", ""),
            "final_video": state.get("final_video", ""),
            "audio_narration": state.get("audio_narration", ""),
            "bg_music": state.get("bg_music", ""),
            "clips": state.get("clips", []),
            "images": state.get("images", []),
            "attribution": state.get("attribution", []),
            "review_notes": state.get("review_notes", ""),
            "compliance_note": (
                "Use royalty-free or licensed assets only, add attribution when required, "
                "and verify YouTube policy compliance before publishing."
            ),
        }
        write_json(metadata_path, payload)
        state["metadata_path"] = str(metadata_path)
        state["status"] = "completed"
        state["next_action"] = "complete"
        return state
    except Exception as exc:  # noqa: BLE001
        add_error(state, f"completion_node error: {exc}")
        state["status"] = "failed:completion"
        state["next_action"] = "failed"
        return state
