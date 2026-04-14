from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
INPUTS_ROOT = PACKAGE_ROOT / "inputs"


# One user-defined limit applies to all branches.
# If the current agent-number condition reaches this many consecutive jointly
# non-viable paired sampling attempts, that entire condition is discarded and
# the branch stops before higher agent numbers.
CONSECUTIVE_FAILED_PAIRED_SAMPLING_ATTEMPTS_LIMIT = 15


# Uncomment exactly one MAP_TYPE.
# MAP_TYPE = "static_artificial"
MAP_TYPE = "dynamic_port"
# MAP_TYPE = "dynamic_campus_area_1"
# MAP_TYPE = "dynamic_campus_area_2"


# All user-defined experiment values live in this file.
# Edit the branch dictionaries below when you want to change seeds, agent-number
# ranges, time limits, densities, image thresholds, or other branch-specific settings.
#
# dynamic_generation_cell_mode controls which raster cells participate in dynamic
# obstacle generation and free-space connectivity checks:
# - "all_free": every non-black source-image cell is traversable
# - "pure_white_only": only pure-white source-image cells are traversable
#
# agent_number_range = (start_agent_number, max_agent_number, step_size)
# Example: (8, 40, 4) -> [8, 12, 16, 20, 24, 28, 32, 36, 40]
# num_last_runs_to_visualize controls how many of the final successful paired run
# configurations at the highest reported agent number receive Pillow frame output.

STATIC_ARTIFICIAL_CONFIG = {
    "num_last_runs_to_visualize": 2,
    "time_limit_seconds": 15.0,
    "agent_number_range": (28, 36, 4),

    "seed": 101,
    "map_size": (25, 25),
    "static_obstacle_density": 0.40,
    "counted_runs_required": 5,
}

DYNAMIC_PORT_CONFIG = {
    "num_last_runs_to_visualize": 2,
    "time_limit_seconds": 15.0,
    "agent_number_range": (12, 100, 2),

    "seed": 201,
    "counted_runs_required": 5,
    "target_static_obstacle_density": 0.15,
    "target_dynamic_obstacle_density": 0.05,
    "loop_sequence_length": 20,
    "group_stay_durations": (3, 4, 5),
    "image_threshold": 127,
    "image_path": str(INPUTS_ROOT / "dynamic_port" / "port_map" / "port_map.png"),
    "image_resize_longest_side": 40,
    "dynamic_generation_cell_mode": "all_free",
}

DYNAMIC_CAMPUS_AREA_1_CONFIG = {
    "num_last_runs_to_visualize": 2,
    "time_limit_seconds": 15.0,
    "agent_number_range": (4, 100, 2),
    "target_dynamic_obstacle_density": 0.02,

    "seed": 301,
    "counted_runs_required": 5,
    # Campus Area 1 preserves the source-image static layout; this value is intentionally not applied.
    "target_static_obstacle_density": None,
    "loop_sequence_length": 20,
    "group_stay_durations": (3, 4, 5),
    "image_threshold": 127,
    "image_path": str(INPUTS_ROOT / "dynamic_campus_area_1" / "campus_area_1_x80.png"),
    "dynamic_generation_cell_mode": "all_free",
    "spawnable_cell_mode": "all_free",
}

DYNAMIC_CAMPUS_AREA_2_CONFIG = {
    "num_last_runs_to_visualize": 2,
    "time_limit_seconds": 15.0,
    "agent_number_range": (4, 100, 4),
    "target_dynamic_obstacle_density": 0.01,

    "seed": 401,
    "counted_runs_required": 5,
    # Campus Area 2 preserves the source-image static layout; this value is intentionally not applied.
    "target_static_obstacle_density": None,
    "loop_sequence_length": 20,
    "group_stay_durations": (3, 4, 5),
    "image_threshold": 127,
    "image_path": str(INPUTS_ROOT / "dynamic_campus_area_2" / "campus_area_2_x80.png"),
    # Campus Area 2 contains extra non-black but non-white raster regions.
    # To keep grouped dynamic-obstacle generation on the main contiguous playable area,
    # use only pure-white cells for dynamic generation, connectivity checks, and spawning.
    "dynamic_generation_cell_mode": "pure_white_only",
    # Only pure-white raster cells may be used as start/goal spawn cells.
    "spawnable_cell_mode": "pure_white_only",
}


BRANCH_USER_CONFIGS = {
    "static_artificial": STATIC_ARTIFICIAL_CONFIG,
    "dynamic_port": DYNAMIC_PORT_CONFIG,
    "dynamic_campus_area_1": DYNAMIC_CAMPUS_AREA_1_CONFIG,
    "dynamic_campus_area_2": DYNAMIC_CAMPUS_AREA_2_CONFIG,
}
