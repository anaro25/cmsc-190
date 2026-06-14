from __future__ import annotations

from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
INPUTS_ROOT = PACKAGE_ROOT / "inputs"
OUTPUT_ADDITIONAL_EXP_ROOT = PACKAGE_ROOT / "output_additional_exp"


def _reference_map_path() -> str:
    return str(INPUTS_ROOT / "reference_map" / "reference_map.png")


def _port_image_path() -> str:
    return str(INPUTS_ROOT / "dynamic_port" / "port_map.png")


# Toggle these the same way as the main experiment config.
recompute_MAPF = True

to_generate = "graphs_and_data"
# to_generate = "nothing"

# Main version or temporary retry version.
ADDITIONAL_EXPERIMENT_USE_TEMPORARY_TESTING = True

# The additional experiment keeps agent count fixed and varies ECBS weight.
# Edit the upper bound rather than manually changing the range length.
# We test from the upper bound downward, then work toward the lower bound.
ADDITIONAL_EXPERIMENT_WEIGHT_LOWER_BOUND = 1.1 # skip 1.0 (vanilla)
ADDITIONAL_EXPERIMENT_WEIGHT_UPPER_BOUND = 2.3
ADDITIONAL_EXPERIMENT_WEIGHT_STEP = 0.1


def _build_weight_range(*, lower_bound: float, upper_bound: float, step: float) -> list[float]:
    if step <= 0:
        raise ValueError("ADDITIONAL_EXPERIMENT_WEIGHT_STEP must be positive.")
    if upper_bound < lower_bound:
        raise ValueError("ADDITIONAL_EXPERIMENT_WEIGHT_UPPER_BOUND must be >= lower bound.")
    weights: list[float] = []
    value = float(upper_bound)
    epsilon = float(step) / 1000.0
    while value >= float(lower_bound) - epsilon:
        weights.append(round(value, 1))
        value -= float(step)
    return weights


ADDITIONAL_EXPERIMENT_WEIGHTS = _build_weight_range(
    lower_bound=ADDITIONAL_EXPERIMENT_WEIGHT_LOWER_BOUND,
    upper_bound=ADDITIONAL_EXPERIMENT_WEIGHT_UPPER_BOUND,
    step=ADDITIONAL_EXPERIMENT_WEIGHT_STEP,
)
ADDITIONAL_EXPERIMENT_RUNS_PER_WEIGHT = 5
ADDITIONAL_EXPERIMENT_TIME_LIMIT_SECONDS = 30.0
ADDITIONAL_EXPERIMENT_TEMPORARY_EXTRA_ATTEMPTS = 3

# Extra guard to prevent unbounded setup retries when sampling itself fails.
ADDITIONAL_EXPERIMENT_MAX_TOTAL_ATTEMPTS_PER_WEIGHT = 100

# Use one deterministic run-context cache per map. This preserves the same
# initial condition for the same run_index across all ECBS weights. In the
# temporary testing version, extra attempts use later run_index values from the
# same deterministic cache.
ADDITIONAL_EXPERIMENT_REUSE_INITIAL_CONDITIONS_ACROSS_WEIGHTS = True

# Only these two metrics are plotted. Average path length is still recorded in
# raw records and aggregates, but intentionally not plotted for this experiment.
ADDITIONAL_EXPERIMENT_PLOTTED_METRICS = [
    "computation_time_halted",
    "num_conflicts",
]

# Choose exactly one additional-experiment map by uncommenting one line.
# MAP_TYPE_ADDITIONAL_EXP = "reference_map"
MAP_TYPE_ADDITIONAL_EXP = "artificial_map"
# MAP_TYPE_ADDITIONAL_EXP = "port_map"

# Agent counts are tentative and deliberately editable here, not hardcoded in
# the runner.
ADDITIONAL_EXPERIMENT_MAP_CONFIGS: dict[str, dict[str, Any]] = {
    "reference_map": {
        "map_type": "reference_rahman_32x32",
        "display_name": "Reference 32x32 Map",
        "seed": 1101,
        "agent_count": 20,
        "map_size": None,
        "static_obstacle_density": 1.0,
        "image_path": _reference_map_path(),
        "image_threshold": 127,
        "image_resize_longest_side": None,
        "require_individual_reachability": True,
    },
    "artificial_map": {
        "map_type": "static_artificial_weight_sweep",
        "display_name": "Static Artificial",
        "seed": 1201,
        "agent_count": 100,
        "map_size": (32, 32),
        "static_obstacle_density": 0.40,
        "image_path": None,
        "image_threshold": 127,
        "image_resize_longest_side": None,
        "require_individual_reachability": False,
    },
    "port_map": {
        "map_type": "static_port_weight_sweep",
        "display_name": "Static Port",
        "seed": 1301,
        "agent_count": 50,
        "map_size": None,
        "static_obstacle_density": 1.0,
        "image_path": _port_image_path(),
        "image_threshold": 127,
        "image_resize_longest_side": 40,
        "require_individual_reachability": True,
    },
}


def _selected_additional_experiment_maps() -> list[dict[str, Any]]:
    if MAP_TYPE_ADDITIONAL_EXP not in ADDITIONAL_EXPERIMENT_MAP_CONFIGS:
        valid_options = ", ".join(sorted(ADDITIONAL_EXPERIMENT_MAP_CONFIGS))
        raise ValueError(
            "MAP_TYPE_ADDITIONAL_EXP must be one of: "
            f"{valid_options}. Got {MAP_TYPE_ADDITIONAL_EXP!r}."
        )
    selected = dict(ADDITIONAL_EXPERIMENT_MAP_CONFIGS[MAP_TYPE_ADDITIONAL_EXP])
    selected["map_selection_key"] = MAP_TYPE_ADDITIONAL_EXP
    return [selected]


ADDITIONAL_EXPERIMENT_MAPS: list[dict[str, Any]] = _selected_additional_experiment_maps()
