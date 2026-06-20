from __future__ import annotations

from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent
INPUTS_ROOT = PACKAGE_ROOT / "inputs"
REFERENCE_PORT_MAPS_ROOT = INPUTS_ROOT / "reference_port_maps"


def _reference_port_image_path(size_label: str) -> str:
    return str(REFERENCE_PORT_MAPS_ROOT / f"port_map_{size_label}.png")


# ---------------------------------------------------------------------------
# Shared constants for the supplementary Tang-inspired reference comparison.
# The main experiment remains configured in master_config.py.
# ---------------------------------------------------------------------------

CONSECUTIVE_FAILED_PAIRED_SAMPLING_ATTEMPTS_LIMIT = 15
enhanced_CBS = True
compact_clustering = True
agent_cohesion: bool = True
cohesion_factor: float = 1.0
SHARED_TIME_LIMIT_SECONDS = 30.0
SHARED_ECBS_SUBOPTIMALITY = 3.0
SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE = True
SHARED_TIGHT_TIME_HORIZON = False
SHARED_COUNTED_RUNS_REQUIRED = 5

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

# For this supplementary reference comparison, the temporary setup means only
# the individual cyclic-faster filter. It does not use the older retry-on-third-
# cyclic-failure rule.
TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER = True
TEMPORARY_INDIVIDUAL_CYCLIC_FASTER_RUNS_REQUIRED = 3
TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER_MAX_ATTEMPTS = 20

# ---------------------------------------------------------------------------
# Program workflow, intentionally parallel to the main experiment.
# ---------------------------------------------------------------------------

recompute_MAPF = True

to_generate = "graphs_and_data"
# to_generate = "visualization"
# to_generate = "nothing"

# Select exactly one reference-comparison execution target.
# SELECTED_PORT_EXPERIMENT = "single_agent_x20"
SELECTED_PORT_EXPERIMENT = "single_agent_x50"
# SELECTED_PORT_EXPERIMENT = "multi_agent_x20"
# SELECTED_PORT_EXPERIMENT = "multi_agent_x50"

# Visualization can be regenerated from saved raw data. Keeping this small
# avoids generating unnecessarily large frame sets.
NUM_LAST_SUCCESSFUL_RUNS_TO_VISUALIZE_PER_MAPPING = 1


REFERENCE_COMPARISON_CASES: dict[str, dict[str, Any]] = {
    "single_agent_x20": {
        "case_id": "single_agent_x20",
        "experiment_mode": "single_agent",
        "display_name": "Reference Comparison: Single Agent x20",
        "size_label": "x20",
        "map_size": 20,
        "agent_number": 1,
        "counted_runs_required": 1,
        "filter_individual_runs_until_cyclic_faster": False,
        "image_path": _reference_port_image_path("x20"),
    },
    "single_agent_x50": {
        "case_id": "single_agent_x50",
        "experiment_mode": "single_agent",
        "display_name": "Reference Comparison: Single Agent x50",
        "size_label": "x50",
        "map_size": 50,
        "agent_number": 1,
        "counted_runs_required": 1,
        "filter_individual_runs_until_cyclic_faster": False,
        "image_path": _reference_port_image_path("x50"),
    },
    "multi_agent_x20": {
        "case_id": "multi_agent_x20",
        "experiment_mode": "multi_agent",
        "display_name": "Reference Comparison: Multi Agent x20",
        "size_label": "x20",
        "map_size": 20,
        "agent_number": 15,
        "counted_runs_required": TEMPORARY_INDIVIDUAL_CYCLIC_FASTER_RUNS_REQUIRED,
        "filter_individual_runs_until_cyclic_faster": TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER,
        "image_path": _reference_port_image_path("x20"),
    },
    "multi_agent_x50": {
        "case_id": "multi_agent_x50",
        "experiment_mode": "multi_agent",
        "display_name": "Reference Comparison: Multi Agent x50",
        "size_label": "x50",
        "map_size": 50,
        "agent_number": 15,
        "counted_runs_required": TEMPORARY_INDIVIDUAL_CYCLIC_FASTER_RUNS_REQUIRED,
        "filter_individual_runs_until_cyclic_faster": TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER,
        "image_path": _reference_port_image_path("x50"),
    },
}


SELECTED_PORT_EXPERIMENT_CASES: dict[str, list[str]] = {
    "single_agent_x20": ["single_agent_x20"],
    "single_agent_x50": ["single_agent_x50"],
    "multi_agent_x20": ["multi_agent_x20"],
    "multi_agent_x50": ["multi_agent_x50"],
}
