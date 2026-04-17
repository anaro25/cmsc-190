from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
INPUTS_ROOT = PACKAGE_ROOT / "inputs"


# All user-defined experiment values live in this file.
# Edit the branch dictionaries below when you want to change seeds, agent-number
# ranges, time limits, densities, thresholds, loop settings, or other branch-specific settings.
#
# dynamic_generation_cell_mode controls which raster cells participate in dynamic
# obstacle generation and free-space connectivity checks:
# - "all_free": every non-black source-image cell is traversable
# - "pure_white_only": only pure-white source-image cells are traversable
# - "zone_colors_only": only designated campus zone-color cells are eligible
#   for spawning or dynamic-obstacle generation; white walkways remain traversable
#   but non-spawnable, and gray areas remain non-traversable.
#
# start_distribution_mode / goal_distribution_mode:
# - "dispersed": unique one-to-one positions sampled across the allowed set
# - "clustered": unique one-to-one positions concentrated in one general area
#
# zone_relationship_mode:
# - "none": starts and goals may be sampled from the same allowed pool
# - "distinct_campus_zones": starts and goals must come from different campus zones
#
# agent_number_range = (start_agent_number, max_agent_number, step_size)
# Example: (8, 40, 4) -> [8, 12, 16, 20, 24, 28, 32, 36, 40]
# num_last_runs_to_visualize controls how many successful runs receive Pillow
# frame output at the end of the branch.
#
# require_jointly_successful_mappings = True
#   Select the last n run configurations for which both classical and cyclic
#   are successful on the same paired instance.
# require_jointly_successful_mappings = False
#   Select the last n successful classical runs and the last n successful cyclic
#   runs independently, even when they come from different paired instances.


# One user-defined limit applies to all branches.
# If the current agent-number condition reaches this many consecutive jointly
# non-viable paired sampling attempts, that entire condition is discarded and
# the branch stops before higher agent numbers.
CONSECUTIVE_FAILED_PAIRED_SAMPLING_ATTEMPTS_LIMIT = 15

# Uncomment exactly one MAP_TYPE.
MAP_TYPE = "static_artificial"
# MAP_TYPE = "static_campus_area_2"
# MAP_TYPE = "dynamic_port"
# MAP_TYPE = "dynamic_campus_area_1"

STATIC_ARTIFICIAL_CONFIG = {
    "num_last_runs_to_visualize": 3,
    "require_jointly_successful_mappings": True,
    "time_limit_seconds": 15.0,
    "agent_number_range": (10, 14, 2), # (2, 100, 2)
    "start_distribution_mode": "dispersed",
    "goal_distribution_mode": "dispersed",
    "require_individual_reachability": False,
    "zone_relationship_mode": "none",

    "seed": 101,
    "map_size": (25, 25),
    "static_obstacle_density": 0.40,
    "counted_runs_required": 5,
}

STATIC_CAMPUS_AREA_2_CONFIG = {
    "num_last_runs_to_visualize": 2,
    "require_jointly_successful_mappings": False,
    "time_limit_seconds": 15.0,
    "agent_number_range": (10, 10, 4),
    "start_distribution_mode": "dispersed",
    "goal_distribution_mode": "clustered",
    "require_individual_reachability": True,
    "zone_relationship_mode": "distinct_campus_zones",

    "seed": 401,
    "counted_runs_required": 5,
    "image_threshold": 127,
    "image_path": str(INPUTS_ROOT / "dynamic_campus_area_2" / "campus_area_2_x80.png"),
    "dynamic_generation_cell_mode": "zone_colors_only",
    "spawnable_cell_mode": "zone_colors_only",
}

DYNAMIC_PORT_CONFIG = {
    "num_last_runs_to_visualize": 3,
    "require_jointly_successful_mappings": False,
    "time_limit_seconds": 15.0,
    "agent_number_range": (2, 100, 1),
    "start_distribution_mode": "clustered",
    "goal_distribution_mode": "dispersed",
    "require_individual_reachability": True,
    "zone_relationship_mode": "none",

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
    "require_jointly_successful_mappings": False,
    "time_limit_seconds": 15.0,
    "agent_number_range": (6, 100, 2),
    "start_distribution_mode": "clustered",
    "goal_distribution_mode": "clustered",
    "require_individual_reachability": True,
    "zone_relationship_mode": "distinct_campus_zones",
    "target_dynamic_obstacle_density": 0.015,

    "seed": 301,
    "counted_runs_required": 5,
    # Campus Area 1 preserves the source-image static layout; this value is intentionally not applied.
    "target_static_obstacle_density": None,
    "loop_sequence_length": 20,
    "group_stay_durations": (3, 4, 5),
    "image_threshold": 127,
    "image_path": str(INPUTS_ROOT / "dynamic_campus_area_1" / "campus_area_1_x80.png"),
    "dynamic_generation_cell_mode": "zone_colors_only",
    "spawnable_cell_mode": "zone_colors_only",
}


BRANCH_USER_CONFIGS = {
    "static_artificial": STATIC_ARTIFICIAL_CONFIG,
    "static_campus_area_2": STATIC_CAMPUS_AREA_2_CONFIG,
    "dynamic_port": DYNAMIC_PORT_CONFIG,
    "dynamic_campus_area_1": DYNAMIC_CAMPUS_AREA_1_CONFIG,
}
