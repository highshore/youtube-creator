from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .nodes import (
    asset_finder,
    audio_narration,
    completion_node,
    human_review,
    music_selector,
    script_generator,
    video_assembler,
)
from .state import ShortState


def build_graph(checkpointer: MemorySaver | None = None):
    workflow = StateGraph(ShortState)
    workflow.add_node("script_generator", script_generator)
    workflow.add_node("asset_finder", asset_finder)
    workflow.add_node("audio_narration", audio_narration)
    workflow.add_node("music_selector", music_selector)
    workflow.add_node("video_assembler", video_assembler)
    workflow.add_node("human_review", human_review)
    workflow.add_node("complete", completion_node)

    workflow.set_entry_point("script_generator")

    workflow.add_conditional_edges(
        "script_generator",
        lambda s: s.get("next_action", "failed"),
        {
            "find_assets": "asset_finder",
            "needs_script_revision": "script_generator",
            "failed": END,
        },
    )
    workflow.add_conditional_edges(
        "asset_finder",
        lambda s: s.get("next_action", "failed"),
        {
            "generate_audio": "audio_narration",
            "refine_query": "asset_finder",
            "needs_script_revision": "script_generator",
            "failed": END,
        },
    )
    workflow.add_conditional_edges(
        "audio_narration",
        lambda s: s.get("next_action", "failed"),
        {
            "select_music": "music_selector",
            "needs_script_revision": "script_generator",
            "failed": END,
        },
    )
    workflow.add_conditional_edges(
        "music_selector",
        lambda s: s.get("next_action", "failed"),
        {"assemble_video": "video_assembler", "failed": END},
    )
    workflow.add_conditional_edges(
        "video_assembler",
        lambda s: s.get("next_action", "failed"),
        {
            "human_review": "human_review",
            "reassemble": "video_assembler",
            "failed": END,
        },
    )
    workflow.add_conditional_edges(
        "human_review",
        lambda s: s.get("next_action", "failed"),
        {
            "approved": "complete",
            "needs_script_revision": "script_generator",
            "find_more_assets": "asset_finder",
            "reassemble": "video_assembler",
            "failed": END,
        },
    )
    workflow.add_edge("complete", END)
    return workflow.compile(checkpointer=checkpointer or MemorySaver())
