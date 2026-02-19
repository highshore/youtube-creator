from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
from loguru import logger
from tqdm import tqdm

from ...config import SETTINGS
from ..retry import retry_call
from ..state import ShortState
from ..utils import (
    add_error,
    bump_attempt,
    ensure_runtime_dirs,
    make_placeholder_image,
    sanitize_filename,
    script_to_search_terms,
    timestamp_name,
)


def _search_pexels_images(query: str, per_page: int = 6) -> list[dict[str, str]]:
    if not SETTINGS.pexels_api_key:
        return []

    def _call() -> list[dict[str, str]]:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": SETTINGS.pexels_api_key},
            params={"query": query, "per_page": per_page},
            timeout=20,
        )
        r.raise_for_status()
        photos = r.json().get("photos", [])
        out: list[dict[str, str]] = []
        for photo in photos:
            src = photo.get("src", {})
            url = src.get("large2x") or src.get("large") or src.get("original")
            if not url:
                continue
            out.append(
                {
                    "url": url,
                    "provider": "pexels",
                    "source_url": photo.get("url", ""),
                    "license": "Pexels License",
                    "kind": "image",
                }
            )
        return out

    return retry_call(f"pexels_images:{query}", _call, max_attempts=3)


def _search_pexels_videos(query: str, per_page: int = 5) -> list[dict[str, str]]:
    if not SETTINGS.pexels_api_key:
        return []

    def _call() -> list[dict[str, str]]:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": SETTINGS.pexels_api_key},
            params={"query": query, "per_page": per_page},
            timeout=20,
        )
        r.raise_for_status()
        videos = r.json().get("videos", [])
        out: list[dict[str, str]] = []
        for item in videos:
            files = sorted(item.get("video_files", []), key=lambda x: x.get("width", 0))
            candidate = None
            for file_item in files:
                if file_item.get("quality") == "hd":
                    candidate = file_item
                    break
            if not candidate and files:
                candidate = files[-1]
            if not candidate or not candidate.get("link"):
                continue
            out.append(
                {
                    "url": candidate["link"],
                    "provider": "pexels",
                    "source_url": item.get("url", ""),
                    "license": "Pexels License",
                    "kind": "video",
                }
            )
        return out

    return retry_call(f"pexels_videos:{query}", _call, max_attempts=3)


def _download_file(url: str, dest: Path) -> bool:
    def _call() -> bool:
        r = requests.get(url, stream=True, timeout=40)
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        return True

    try:
        return retry_call(f"download:{dest.name}", _call, max_attempts=3)
    except Exception:  # noqa: BLE001
        return False


def asset_finder(state: ShortState) -> ShortState:
    state = dict(state)
    ensure_runtime_dirs(state)
    attempt = bump_attempt(state, "asset_finder")
    max_attempts = state.get("max_asset_attempts", 3)

    try:
        topic = state.get("topic", "")
        script = state.get("script", "")
        terms = script_to_search_terms(topic, script)
        state["asset_queries"] = terms

        images_dir = Path(state["assets_dir"]) / "images"
        clips_dir = Path(state["assets_dir"]) / "clips"
        existing_images = list(state.get("images", []))
        existing_clips = list(state.get("clips", []))
        attribution = list(state.get("attribution", []))

        query_subset = terms[:3]
        logger.info(
            "Asset search started for {} queries (single session, threaded workers).",
            len(query_subset),
        )

        image_candidates: list[dict[str, str]] = []
        video_candidates: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=6, thread_name_prefix="asset-search") as executor:
            future_map = {}
            for query in query_subset:
                future_map[executor.submit(_search_pexels_images, query)] = ("image", query)
                future_map[executor.submit(_search_pexels_videos, query)] = ("video", query)

            for future in as_completed(future_map):
                kind, query = future_map[future]
                try:
                    results = future.result()
                    logger.debug("Search {} '{}' -> {} hits", kind, query, len(results))
                    if kind == "image":
                        image_candidates.extend(results)
                    else:
                        video_candidates.extend(results)
                except Exception as exc:  # noqa: BLE001
                    add_error(state, f"asset search error ({kind}:{query}): {exc}")

        image_plan = image_candidates[:6]
        video_plan = video_candidates[:4]
        plan = image_plan + video_plan

        pbar = tqdm(
            total=len(plan),
            desc=f"job-{state.get('job_id', 'na')}:asset-download",
            unit="file",
            disable=not sys.stderr.isatty(),
        )

        with ThreadPoolExecutor(max_workers=6, thread_name_prefix="asset-download") as executor:
            downloads = {}
            for idx, item in enumerate(plan):
                query_hint = query_subset[idx % max(1, len(query_subset))]
                suffix = ".jpg" if item["kind"] == "image" else ".mp4"
                folder = images_dir if item["kind"] == "image" else clips_dir
                stem = sanitize_filename(f"{query_hint}_{item['kind']}_{attempt}_{idx}")
                dest = folder / f"{stem}{suffix}"
                downloads[executor.submit(_download_file, item["url"], dest)] = (item, dest)

            for future in as_completed(downloads):
                item, dest = downloads[future]
                ok = future.result()
                if ok:
                    if item["kind"] == "image":
                        existing_images.append(str(dest))
                    else:
                        existing_clips.append(str(dest))
                    attribution.append(
                        {
                            "provider": item["provider"],
                            "source_url": item["source_url"],
                            "license": item["license"],
                            "local_path": str(dest),
                        }
                    )
                pbar.update(1)
        pbar.close()

        min_total_assets = 3
        placeholder_idx = 0
        while len(existing_images) + len(existing_clips) < min_total_assets:
            placeholder_idx += 1
            placeholder = images_dir / f"{timestamp_name('placeholder', '')}_{attempt}_{placeholder_idx}.jpg"
            make_placeholder_image(placeholder, topic or "YouTube Shorts")
            existing_images.append(str(placeholder))
            attribution.append(
                {
                    "provider": "local-placeholder",
                    "source_url": "",
                    "license": "generated",
                    "local_path": str(placeholder),
                }
            )

        state["images"] = sorted(set(existing_images))
        state["clips"] = sorted(set(existing_clips))
        state["attribution"] = attribution

        enough_assets = len(state["images"]) + len(state["clips"]) >= min_total_assets
        if enough_assets:
            state["status"] = "assets_ready"
            state["next_action"] = "generate_audio"
        elif attempt < max_attempts:
            state["status"] = "assets_insufficient_retrying"
            state["next_action"] = "refine_query"
        else:
            state["status"] = "assets_insufficient_script_revision"
            state["next_action"] = "needs_script_revision"
        return state
    except Exception as exc:  # noqa: BLE001
        add_error(state, f"asset_finder error: {exc}")
        state["status"] = "failed:asset_finder"
        state["next_action"] = "refine_query"
        return state
