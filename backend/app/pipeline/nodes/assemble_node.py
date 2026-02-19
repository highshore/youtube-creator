from __future__ import annotations

import re
import sys
from pathlib import Path

from loguru import logger
from tqdm import tqdm

from ..state import ShortState
from ..utils import (
    add_error,
    bump_attempt,
    ensure_runtime_dirs,
    estimate_narration_seconds,
    split_sentences,
    timestamp_name,
)


def _fit_vertical(clip):
    target_w, target_h = 1080, 1920
    clip_ratio = clip.w / clip.h
    target_ratio = target_w / target_h
    if clip_ratio > target_ratio:
        resized = clip.resize(height=target_h)
    else:
        resized = clip.resize(width=target_w)
    from moviepy.video.fx.all import crop

    return crop(
        resized,
        x_center=resized.w / 2,
        y_center=resized.h / 2,
        width=target_w,
        height=target_h,
    )


def _build_caption_layers(script: str, duration: float):
    from moviepy.editor import TextClip

    sentences = split_sentences(script, max_sentences=6)
    if not sentences:
        return []
    seg_duration = max(1.8, duration / len(sentences))
    layers = []
    for idx, sentence in enumerate(sentences):
        text = re.sub(r"\s+", " ", sentence).strip()
        if not text:
            continue
        clip = (
            TextClip(text, fontsize=52, color="white", method="caption", size=(980, None))
            .set_position(("center", 1580))
            .set_start(idx * seg_duration)
            .set_duration(seg_duration)
        )
        layers.append(clip)
    return layers


def video_assembler(state: ShortState) -> ShortState:
    state = dict(state)
    ensure_runtime_dirs(state)
    attempt = bump_attempt(state, "video_assembler")
    try:
        from moviepy.audio.fx.all import audio_loop
        from moviepy.editor import (
            AudioFileClip,
            ColorClip,
            CompositeAudioClip,
            CompositeVideoClip,
            ImageClip,
            VideoFileClip,
            concatenate_videoclips,
        )

        output_dir = Path(state["output_dir"])
        final_video_path = output_dir / timestamp_name("short_final", ".mp4")

        narration_clip = None
        narration_path = state.get("audio_narration")
        if narration_path and Path(narration_path).exists():
            narration_clip = AudioFileClip(narration_path)

        target_duration = min(
            59.0,
            narration_clip.duration if narration_clip else estimate_narration_seconds(state.get("script", "")),
        )
        if target_duration <= 0:
            target_duration = 18.0

        media_paths = list(state.get("clips", [])) + list(state.get("images", []))
        each_duration = max(2.0, target_duration / max(1, len(media_paths)))
        visual_clips = []

        pbar = tqdm(
            total=max(1, len(media_paths)),
            desc=f"job-{state.get('job_id', 'na')}:assemble",
            unit="clip",
            disable=not sys.stderr.isatty(),
        )
        for media_path in media_paths:
            p = Path(media_path)
            if not p.exists():
                pbar.update(1)
                continue
            if p.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}:
                clip = VideoFileClip(str(p)).without_audio()
                clip = _fit_vertical(clip)
                clip = clip.subclip(0, min(clip.duration, each_duration)).set_duration(each_duration)
                visual_clips.append(clip)
            else:
                clip = ImageClip(str(p)).set_duration(each_duration)
                visual_clips.append(_fit_vertical(clip))
            pbar.update(1)
        pbar.close()

        if not visual_clips:
            visual_clips = [ColorClip(size=(1080, 1920), color=(20, 24, 35), duration=target_duration)]

        timeline = concatenate_videoclips(visual_clips, method="compose")
        if timeline.duration > target_duration:
            timeline = timeline.subclip(0, target_duration)
        else:
            timeline = timeline.set_duration(target_duration)

        layers = [timeline]
        try:
            layers.extend(_build_caption_layers(state.get("script", ""), target_duration))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Caption layer skipped due to error: {}", exc)

        composed = CompositeVideoClip(layers, size=(1080, 1920)).set_duration(target_duration)
        audio_tracks = []
        if narration_clip:
            audio_tracks.append(narration_clip.volumex(1.0))
        bg_path = state.get("bg_music")
        if bg_path and Path(bg_path).exists():
            bg_track = audio_loop(AudioFileClip(bg_path), duration=target_duration).volumex(0.18)
            audio_tracks.append(bg_track)
        if audio_tracks:
            composed = composed.set_audio(CompositeAudioClip(audio_tracks).set_duration(target_duration))

        composed.write_videofile(
            str(final_video_path),
            fps=30,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            logger=None,
        )

        state["final_video"] = str(final_video_path)
        state["status"] = "video_ready"
        state["next_action"] = "human_review"
        return state
    except Exception as exc:  # noqa: BLE001
        add_error(state, f"video_assembler error: {exc}")
        state["status"] = "failed:video_assembler"
        state["next_action"] = "reassemble" if attempt < 3 else "failed"
        return state
