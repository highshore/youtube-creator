from __future__ import annotations

from typing import Dict, List, Literal
from typing_extensions import TypedDict


NextAction = Literal[
    "find_assets",
    "refine_query",
    "generate_audio",
    "select_music",
    "assemble_video",
    "human_review",
    "approved",
    "needs_script_revision",
    "find_more_assets",
    "reassemble",
    "complete",
    "failed",
]


class AttributionItem(TypedDict, total=False):
    provider: str
    source_url: str
    local_path: str
    license: str


class ShortState(TypedDict, total=False):
    job_id: str
    topic: str
    script: str
    clips: List[str]
    images: List[str]
    audio_narration: str
    bg_music: str
    final_video: str
    status: str
    next_action: NextAction
    errors: List[str]
    attempts: Dict[str, int]
    asset_queries: List[str]
    attribution: List[AttributionItem]
    review_notes: str
    human_decision: Literal[
        "approved",
        "needs_script_revision",
        "find_more_assets",
        "reassemble",
    ]
    metadata_path: str
    output_dir: str
    assets_dir: str
    max_asset_attempts: int
