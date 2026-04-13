from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
INPUTS_ROOT = PACKAGE_ROOT / "inputs"


# Uncomment exactly one MAP_TYPE.
MAP_TYPE = "static_artificial"
# MAP_TYPE = "dynamic_port"
# MAP_TYPE = "dynamic_campus_area_1"
# MAP_TYPE = "dynamic_campus_area_2"


# All user-defined experiment values live in this file.
# Edit the branch dictionaries below when you want to change seeds, agent lists,
# time limits, densities, image thresholds, or other branch-specific settings.

STATIC_ARTIFICIAL_CONFIG = {
    "seed": 101,
    "map_size": (25, 25),
    "static_obstacle_density": 0.40,
    "time_limit_seconds": 15.0,
    "counted_runs_required": 5,
    "agent_numbers": [12, 16, 20],
}

DYNAMIC_PORT_CONFIG = {
    "seed": 201,
    "time_limit_seconds": 30.0,
    "counted_runs_required": 5,
    "agent_numbers": [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
    "target_static_obstacle_density": 0.20,
    "target_dynamic_obstacle_density": 0.10,
    "loop_sequence_length": 30,
    "group_stay_durations": (3, 4, 5),
    "image_threshold": 127,
    "image_path": str(INPUTS_ROOT / "dynamic_port" / "port_map" / "port_map.png"),
    "image_resize_longest_side": 40,
}

DYNAMIC_CAMPUS_AREA_1_CONFIG = {
    "seed": 301,
    "time_limit_seconds": 30.0,
    "counted_runs_required": 5,
    "agent_numbers": [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
    "target_static_obstacle_density": 0.20,
    "target_dynamic_obstacle_density": 0.10,
    "loop_sequence_length": 30,
    "group_stay_durations": (3, 4, 5),
    "image_threshold": 127,
    "image_path": str(INPUTS_ROOT / "dynamic_campus_area_1" / "campus_area_1_x80.png"),
}

DYNAMIC_CAMPUS_AREA_2_CONFIG = {
    "seed": 401,
    "time_limit_seconds": 30.0,
    "counted_runs_required": 5,
    "agent_numbers": [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
    "target_static_obstacle_density": 0.20,
    "target_dynamic_obstacle_density": 0.10,
    "loop_sequence_length": 30,
    "group_stay_durations": (3, 4, 5),
    "image_threshold": 127,
    "image_path": str(INPUTS_ROOT / "dynamic_campus_area_2" / "campus_area_2_x80.png"),
}


BRANCH_USER_CONFIGS = {
    "static_artificial": STATIC_ARTIFICIAL_CONFIG,
    "dynamic_port": DYNAMIC_PORT_CONFIG,
    "dynamic_campus_area_1": DYNAMIC_CAMPUS_AREA_1_CONFIG,
    "dynamic_campus_area_2": DYNAMIC_CAMPUS_AREA_2_CONFIG,
}
