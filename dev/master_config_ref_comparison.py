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

# Multi-agent reference comparison capacity-search controls.
# Each 50x50 reference port map searches only the classical capacity. A tested
# agent number passes when classical solves and cyclic also solves with both
# lower halted time and fewer conflicts on the exact same deterministic setup.
REFERENCE_CAPACITY_AGENT_UPPER_BOUND = 255
REFERENCE_CAPACITY_BINARY_SEARCH_MAX_DOWNWARD_MOVES = 3
REFERENCE_CAPACITY_ATTEMPTS_PER_AGENT_NUMBER = 1
REFERENCE_CAPACITY_PASS_CRITERION = "temp_pairwise"

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
# do not use the older repeated-sampling filter. Multi-agent capacity search now
# applies the stricter pairwise criterion directly to each tested agent number.
TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER = False
TEMPORARY_INDIVIDUAL_CYCLIC_FASTER_RUNS_REQUIRED = 3
TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER_MAX_ATTEMPTS = 20

# ---------------------------------------------------------------------------
# Program workflow, intentionally parallel to the main experiment.
# ---------------------------------------------------------------------------

# Select exactly one program mode.
# to_generate = "raw_data"       # recompute and save raw reference-comparison data
to_generate = "graphs"          # regenerate graphs/data from saved raw data
# to_generate = "visualization"  # regenerate Pillow visualizations from saved frame_by_frame packages

# Select exactly one reference-comparison execution target.
# SELECTED_PORT_EXPERIMENT = "single_agent"
SELECTED_PORT_EXPERIMENT = "multi_agent"

# Kept for backward compatibility. The current raw-data phase saves exactly one
# designated frame-by-frame run for every map/mapping pair, so visualization
# generation no longer selects from a larger raw-data candidate pool.
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
        "capacity_search_enabled": True,
        "capacity_agent_upper_bound": REFERENCE_CAPACITY_AGENT_UPPER_BOUND,
        "capacity_binary_search_max_downward_moves": REFERENCE_CAPACITY_BINARY_SEARCH_MAX_DOWNWARD_MOVES,
        "capacity_attempts_per_agent_number": REFERENCE_CAPACITY_ATTEMPTS_PER_AGENT_NUMBER,
        "capacity_pass_criterion": REFERENCE_CAPACITY_PASS_CRITERION,
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
