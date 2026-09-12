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



CONSECUTIVE_FAILED_PAIRED_SAMPLING_ATTEMPTS_LIMIT = 15
enhanced_CBS = True
compact_clustering = True
SHARED_TIME_LIMIT_SECONDS = 60.0
SHARED_ECBS_SUBOPTIMALITY = 3.0
SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE = False
SHARED_TIGHT_TIME_HORIZON = False
SHARED_COUNTED_RUNS_REQUIRED = 5
SINGLE_AGENT_TIMING_REPETITIONS = 5
MULTI_AGENT_TIMING_REPETITIONS = 3

# Use the same fixed agent count for both mappings on each map.
MULTI_AGENT_AGENT_NUMBERS_BY_MAP = {
    1: 17,
    2: 24,
    3: 11,
}

# Match the cyclic post-processing used by the main experiment.
REMOVE_EXTRA_TRANSITIONS = True
ADD_TRANSITIONS_BETWEEN_FREE_SPACES = False

# Old filter settings kept for compatibility.
TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER = False
TEMPORARY_INDIVIDUAL_CYCLIC_FASTER_RUNS_REQUIRED = 3
TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER_MAX_ATTEMPTS = 20

# Program mode.
# to_generate = "raw_data"
to_generate = "graphs"
# to_generate = "visualization"

# Reference experiment to run.
# SELECTED_PORT_EXPERIMENT = "single_agent"
SELECTED_PORT_EXPERIMENT = "multi_agent"

# Kept for older code that still reads this setting.
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
        "capacity_search_enabled": False,
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
    # Older config names still accepted.
    "single_agent_x20": ["single_agent"],
    "single_agent_x50": ["single_agent"],
    "multi_agent_x20": ["multi_agent"],
    "multi_agent_x50": ["multi_agent"],
}
