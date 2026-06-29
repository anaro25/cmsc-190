from __future__ import annotations

from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent
INPUTS_ROOT = PACKAGE_ROOT / "inputs"
REFERENCE_PORT_MAPS_ROOT = INPUTS_ROOT / "reference_port_maps"
REFERENCE_PORT_MAP_NUMBERS = (1, 2, 3)


def _reference_port_image_path(map_number: int) -> str:
    return str(REFERENCE_PORT_MAPS_ROOT / f"port_map_{int(map_number)}.png")


def _reference_port_image_paths() -> list[str]:
    return [_reference_port_image_path(map_number) for map_number in REFERENCE_PORT_MAP_NUMBERS]


# ---------------------------------------------------------------------------
# Shared constants for the supplementary Tang-inspired reference comparison.
# The main experiment remains configured in master_config.py.
# ---------------------------------------------------------------------------

CONSECUTIVE_FAILED_PAIRED_SAMPLING_ATTEMPTS_LIMIT = 15
enhanced_CBS = True
compact_clustering = True
agent_cohesion: bool = True
cohesion_factor: float = 1.0
SHARED_TIME_LIMIT_SECONDS = 60.0
SHARED_ECBS_SUBOPTIMALITY = 3.0
SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE = True
SHARED_TIGHT_TIME_HORIZON = False
SHARED_COUNTED_RUNS_REQUIRED = 5
SINGLE_AGENT_TIMING_REPETITIONS = 5
MULTI_AGENT_TIMING_REPETITIONS = 3

# Multi-agent reference comparison agent counts per 50x50 port map.
# Edit these values to choose how many agents are used for each map.
# Keys correspond to inputs/reference_port_maps/port_map_<number>.png.
MULTI_AGENT_REFERENCE_PORT_MAP_AGENT_NUMBERS: dict[int, int] = {
    1: 17, # max good 17
    2: 24, # max good 24 (max 40)
    3: 11, # max good 11
}

# Controls the final cyclic-map cleanup step only for the reference comparison.
# True preserves the full cyclic-mapping behavior used by the main experiment.
# False skips only the redundant-transition elimination step. Required
# connectivity restoration is still applied so generated maps remain usable.
REMOVE_EXTRA_TRANSITIONS = False

# Optional final cyclic-map step only for the reference comparison.
# True forces every adjacent pair of free cells to have a bidirectional
# transition after the normal cyclic-mapping cleanup steps. This can be used
# to test a much less restrictive version of the cyclic map when the standard
# transition reduction produces impractical routes.
ADD_TRANSITIONS_BETWEEN_FREE_SPACES = False

# Legacy cyclic-faster filter controls. The current reference-comparison cases
# disable this filter because both single-agent and multi-agent cases use fixed
# maps with repeated timing samples.
TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER = False
TEMPORARY_INDIVIDUAL_CYCLIC_FASTER_RUNS_REQUIRED = 3
TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER_MAX_ATTEMPTS = 20

# ---------------------------------------------------------------------------
# Program workflow, intentionally parallel to the main experiment.
# ---------------------------------------------------------------------------

# Select exactly one program mode.
# to_generate = "raw_data"       # recompute and save raw reference-comparison data
to_generate = "graphs"          # regenerate graphs/data from saved raw data
# to_generate = "visualization"  # regenerate visualizations from saved raw data

# Select exactly one reference-comparison execution target.
# SELECTED_PORT_EXPERIMENT = "single_agent"
SELECTED_PORT_EXPERIMENT = "multi_agent"

# Visualization can be regenerated from saved raw data. Keeping this small
# avoids generating unnecessarily large frame sets.
NUM_LAST_SUCCESSFUL_RUNS_TO_VISUALIZE_PER_MAPPING = 1


REFERENCE_COMPARISON_CASES: dict[str, dict[str, Any]] = {
    "single_agent": {
        "case_id": "single_agent",
        "experiment_mode": "single_agent",
        "display_name": "Reference Comparison: Single Agent",
        "size_label": "x50",
        "map_size": 50,
        "agent_number": 1,
        "counted_runs_required": 1,
        "single_agent_timing_repetitions": SINGLE_AGENT_TIMING_REPETITIONS,
        "filter_individual_runs_until_cyclic_faster": False,
        "image_path": _reference_port_image_path(1),
        "map_image_paths": _reference_port_image_paths(),
    },
    "multi_agent": {
        "case_id": "multi_agent",
        "experiment_mode": "multi_agent",
        "display_name": "Reference Comparison: Multi Agent",
        "size_label": "x50",
        "map_size": 50,
        # Fallback/default value used for legacy summaries. The actual multi-agent
        # run for each port map uses the matching value in map_agent_numbers below.
        "agent_number": MULTI_AGENT_REFERENCE_PORT_MAP_AGENT_NUMBERS.get(1, 10),
        "map_agent_numbers": MULTI_AGENT_REFERENCE_PORT_MAP_AGENT_NUMBERS,
        "counted_runs_required": 1,
        "multi_agent_timing_repetitions": MULTI_AGENT_TIMING_REPETITIONS,
        "filter_individual_runs_until_cyclic_faster": False,
        "image_path": _reference_port_image_path(1),
        "map_image_paths": _reference_port_image_paths(),
    },
}


SELECTED_PORT_EXPERIMENT_CASES: dict[str, list[str]] = {
    "single_agent": ["single_agent"],
    "multi_agent": ["multi_agent"],
    # Backward-compatible aliases for older config values. The reference
    # comparison now uses only 50x50 port_map_1..port_map_3 for both modes.
    "single_agent_x20": ["single_agent"],
    "single_agent_x50": ["single_agent"],
    "multi_agent_x20": ["multi_agent"],
    "multi_agent_x50": ["multi_agent"],
}
