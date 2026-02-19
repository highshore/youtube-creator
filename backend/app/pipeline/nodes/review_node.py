from __future__ import annotations

from langgraph.types import interrupt

from ..state import ShortState
from ..utils import add_error, bump_attempt, ensure_runtime_dirs

ALLOWED = {"approved", "needs_script_revision", "find_more_assets", "reassemble"}


def human_review(state: ShortState) -> ShortState:
    state = dict(state)
    ensure_runtime_dirs(state)
    bump_attempt(state, "human_review")

    decision = state.get("human_decision", "")
    notes = state.get("review_notes", "")

    if decision not in ALLOWED:
        payload = {
            "message": "Review required",
            "script": state.get("script", ""),
            "clips": state.get("clips", []),
            "images": state.get("images", []),
            "final_video": state.get("final_video", ""),
            "options": sorted(ALLOWED),
        }
        feedback = interrupt(payload)
        if isinstance(feedback, dict):
            decision = str(feedback.get("human_decision", "")).strip()
            notes = str(feedback.get("review_notes", "")).strip()
        elif isinstance(feedback, str):
            decision = feedback.strip()

    if decision not in ALLOWED:
        add_error(state, "Invalid review decision. Defaulted to needs_script_revision.")
        decision = "needs_script_revision"

    state["human_decision"] = decision  # type: ignore[assignment]
    state["review_notes"] = notes
    state["status"] = f"reviewed:{decision}"
    state["next_action"] = decision  # type: ignore[assignment]
    return state
