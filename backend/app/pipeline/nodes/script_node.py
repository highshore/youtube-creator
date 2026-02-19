from __future__ import annotations

from loguru import logger

from ...config import SETTINGS
from ..state import ShortState
from ..utils import add_error, bump_attempt, ensure_runtime_dirs, split_sentences


def _default_script(topic: str, notes: str = "") -> str:
    note_line = f" Keep this review note in mind: {notes}" if notes else ""
    return (
        f"Let us break down {topic}. "
        "Here is the one reason people are paying attention now. "
        "Now we simplify the core idea in plain language. "
        "Next comes a surprising detail that most people miss. "
        "Then we connect it to a practical everyday example. "
        "Here is the key takeaway in one sentence. "
        "Before we end, try this quick action right away. "
        f"Follow for the next short deep dive.{note_line}"
    )


def _generate_script(topic: str, notes: str = "") -> str:
    if not SETTINGS.openai_api_key:
        return _default_script(topic, notes)
    try:
        from langchain_openai import ChatOpenAI
    except Exception:
        return _default_script(topic, notes)

    prompt = (
        "Write a YouTube Shorts voiceover script in 8-10 sentences.\n"
        "Rules:\n"
        "- Must fit under 60 seconds.\n"
        "- Sentence 1 should be a strong hook.\n"
        "- Keep wording concise and high energy.\n"
        "- No markdown and no bullet points.\n"
        f"Topic: {topic}\n"
    )
    if notes:
        prompt += f"Reviewer feedback to include: {notes}\n"

    llm = ChatOpenAI(
        api_key=SETTINGS.openai_api_key,
        model=SETTINGS.openai_model,
        temperature=0.7,
    )
    response = llm.invoke(prompt)
    raw_content = response.content
    if isinstance(raw_content, str):
        text = raw_content.strip()
    else:
        text = str(raw_content).strip()
    return text or _default_script(topic, notes)


def script_generator(state: ShortState) -> ShortState:
    state = dict(state)
    ensure_runtime_dirs(state)
    bump_attempt(state, "script_generator")

    topic = state.get("topic", "").strip()
    if not topic:
        add_error(state, "topic is required.")
        state["next_action"] = "failed"
        state["status"] = "failed:missing_topic"
        return state

    try:
        logger.info("Generating script for topic='{}'", topic)
        script = _generate_script(topic, state.get("review_notes", ""))
        state["script"] = " ".join(split_sentences(script, max_sentences=10))
        state["status"] = "script_ready"
        state["next_action"] = "find_assets"
        return state
    except Exception as exc:  # noqa: BLE001
        add_error(state, f"script_generator error: {exc}")
        state["status"] = "failed:script_generator"
        state["next_action"] = "needs_script_revision"
        return state
