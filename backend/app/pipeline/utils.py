from __future__ import annotations

import json
import math
import re
import wave
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from PIL import Image, ImageDraw, ImageFont

from .state import ShortState

STOPWORDS = {
    "about",
    "an",
    "and",
    "are",
    "at",
    "for",
    "from",
    "into",
    "its",
    "that",
    "the",
    "this",
    "what",
    "with",
    "your",
}


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_runtime_dirs(state: ShortState) -> ShortState:
    assets_dir = ensure_dir(state.get("assets_dir", "data/assets"))
    output_dir = ensure_dir(state.get("output_dir", "data/output"))
    ensure_dir(assets_dir / "images")
    ensure_dir(assets_dir / "clips")
    ensure_dir(assets_dir / "audio")
    ensure_dir(assets_dir / "music")
    state["assets_dir"] = str(assets_dir)
    state["output_dir"] = str(output_dir)
    return state


def add_error(state: ShortState, message: str) -> None:
    errors = state.setdefault("errors", [])
    errors.append(message)


def bump_attempt(state: ShortState, key: str) -> int:
    attempts = state.setdefault("attempts", {})
    attempts[key] = attempts.get(key, 0) + 1
    return attempts[key]


def sanitize_filename(text: str, limit: int = 60) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", text).strip("_")
    return (cleaned or "file")[:limit]


def timestamp_name(prefix: str, suffix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}"


def split_sentences(text: str, max_sentences: int = 10) -> List[str]:
    chunks = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks = [c.strip() for c in chunks if c.strip()]
    return chunks[:max_sentences]


def script_to_search_terms(topic: str, script: str, max_terms: int = 6) -> list[str]:
    text = f"{topic} {script}".lower()
    tokens = re.findall(r"[a-zA-Z]{4,}", text)
    freq: dict[str, int] = {}
    for token in tokens:
        if token in STOPWORDS:
            continue
        freq[token] = freq.get(token, 0) + 1
    ranked = sorted(freq.items(), key=lambda x: (-x[1], -len(x[0]), x[0]))
    terms = [topic.strip()]
    for term, _ in ranked:
        if term not in terms:
            terms.append(term)
        if len(terms) >= max_terms:
            break
    return [t for t in terms if t]


def make_placeholder_image(path: Path, text: str, size: tuple[int, int] = (1080, 1920)) -> None:
    image = Image.new("RGB", size, color=(18, 22, 36))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("Arial.ttf", 54)
    except Exception:
        font = ImageFont.load_default()
    draw.multiline_text((80, 180), wrap_lines(text, 22), fill=(245, 245, 245), font=font, spacing=8)
    image.save(path)


def wrap_lines(text: str, width: int) -> str:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = (line + " " + word).strip()
        if len(candidate) <= width:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return "\n".join(lines)


def make_tone_wav(path: Path, duration_s: float, freq: float = 220.0, volume: float = 0.1) -> None:
    sample_rate = 44100
    amplitude = int(32767 * max(0.0, min(volume, 1.0)))
    samples = int(sample_rate * max(0.1, duration_s))
    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for i in range(samples):
            value = int(amplitude * math.sin(2 * math.pi * freq * (i / sample_rate)))
            wav_file.writeframesraw(value.to_bytes(2, byteorder="little", signed=True))


def estimate_narration_seconds(script: str) -> float:
    words = max(1, len(script.split()))
    return min(58.0, max(8.0, words / 2.6))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def unique_extend(target: list, values: Iterable[str]) -> None:
    for item in values:
        if item not in target:
            target.append(item)
