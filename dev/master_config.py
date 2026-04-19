from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
INPUTS_ROOT = PACKAGE_ROOT / "inputs"


def _campus_lane_variant_image_path(*, area_number: int, narrow_lanes: bool) -> str:
    lane_variant = "narrow_lanes" if narrow_lanes else "wide_lanes"
    return str(
        INPUTS_ROOT
        / f"dynamic_campus_area_{area_number}"
        / f"campus_area_{area_number}_{lane_variant}.png"
    )


# One user-defined limit applies to all branches.
# If the current agent-number condition reaches this many consecutive jointly
# non-viable paired sampling attempts, that entire condition is discarded and
# the branch stops before higher agent numbers.
CONSECUTIVE_FAILED_PAIRED_SAMPLING_ATTEMPTS_LIMIT = 15

# Global solver toggle for the whole project.
# False -> vanilla CBS
# True  -> Enhanced CBS (ECBS)
enhanced_CBS = True

# Global clustered-placement toggle for the whole project.
# True  -> clustered sets are compact directly adjacent groups.
# False -> clustered sets are spaced groups whose members keep one empty cell
#          of separation in all 8 directions while remaining one cluster.
compact_clustering = True

# Uncomment exactly one MAP_TYPE.
# MAP_TYPE = "static_artificial"
MAP_TYPE = "static_campus_area_1"
# MAP_TYPE = "dynamic_port"
# MAP_TYPE = "dynamic_campus_area_2"

# shared constants
SHARED_TIME_LIMIT_SECONDS = 30.0
SHARED_ECBS_SUBOPTIMALITY = 2.0 # helps so set to 2.0
SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE = True # helps so set to True
SHARED_NARROW_LANES = True # doesn't help so set to True
SHARED_TIGHT_TIME_HORIZON = False # doesn't help so set to False
SHARED_COUNTED_RUNS_REQUIRED = 5

STATIC_ARTIFICIAL_CONFIG = {
    # common frequently edited constants
    "seed": 101,
    "agent_number_range": (80, 200, 5),
    "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
    "num_last_runs_to_visualize": 1,
    "require_jointly_successful_mappings": False,
    "ECBS_suboptimality": 1.0, # vanilla CBS
    "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
    "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,
    
    # common permanent constants
    "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
    "start_distribution_mode": "dispersed",
    "goal_distribution_mode": "dispersed",
    "require_individual_reachability": False,
    "zone_relationship_mode": "none",

    # branch-specific constants
    "map_size": (32, 32),
    "static_obstacle_density": 0.40,
}

STATIC_CAMPUS_AREA_1_CONFIG = {
    # common frequently edited constants
    "seed": 201,
    "agent_number_range": (10, 100, 2),
    "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
    "num_last_runs_to_visualize": 1,
    "require_jointly_successful_mappings": False,
    "ECBS_suboptimality": SHARED_ECBS_SUBOPTIMALITY,
    "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
    "narrow_lanes": SHARED_NARROW_LANES,
    "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,

    # common permanent constants
    "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
    "start_distribution_mode": "dispersed",
    "goal_distribution_mode": "clustered",
    "require_individual_reachability": True,
    "zone_relationship_mode": "distinct_campus_zones",

    # branch-exclusive constants
    "spawnable_cell_mode": "zone_colors_only",
    "image_threshold": 127,
    "image_path": None,
    "dynamic_generation_cell_mode": "zone_colors_only",
}
STATIC_CAMPUS_AREA_1_CONFIG["image_path"] = _campus_lane_variant_image_path(
    area_number=1,
    narrow_lanes=bool(STATIC_CAMPUS_AREA_1_CONFIG["narrow_lanes"]),
)

DYNAMIC_PORT_CONFIG = {
    # common frequently edited constants
    "seed": 301,
    "agent_number_range": (8, 100, 2),
    "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
    "num_last_runs_to_visualize": 1,
    "require_jointly_successful_mappings": False,
    "ECBS_suboptimality": SHARED_ECBS_SUBOPTIMALITY,
    "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
    "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,

    # common permanent constants
    "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
    "start_distribution_mode": "clustered",
    "goal_distribution_mode": "dispersed",
    "require_individual_reachability": True,
    "zone_relationship_mode": "none",

    # branch-exclusive constants
    "target_static_obstacle_density": 0.15,
    "target_dynamic_obstacle_density": 0.05,
    "loop_sequence_length": 100,
    "group_stay_durations": (7, 9, 11),
    "image_threshold": 127,
    "image_path": str(INPUTS_ROOT / "dynamic_port" / "port_map" / "port_map.png"),
    "image_resize_longest_side": 40,
    "dynamic_generation_cell_mode": "all_free",
}

DYNAMIC_CAMPUS_AREA_2_CONFIG = {
    # common frequently edited constants
    "seed": 401,
    "agent_number_range": (16, 100, 2),
    "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
    "num_last_runs_to_visualize": 1,
    "require_jointly_successful_mappings": False,
    "ECBS_suboptimality": SHARED_ECBS_SUBOPTIMALITY,
    "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
    "narrow_lanes": SHARED_NARROW_LANES,
    "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,

    # common permanent constants
    "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
    "start_distribution_mode": "clustered",
    "goal_distribution_mode": "clustered",
    "require_individual_reachability": True,
    "zone_relationship_mode": "distinct_campus_zones",

    # branch-exclusive constants
    #   Campus Area 2 preserves the source-image static layout; this value is intentionally not applied.
    "target_static_obstacle_density": None,
    "target_dynamic_obstacle_density": 0.015,
    "loop_sequence_length": 100,
    "group_stay_durations": (7, 9, 11),
    "image_threshold": 127,
    "image_path": None,
    "dynamic_generation_cell_mode": "zone_colors_only",
    "spawnable_cell_mode": "zone_colors_only",
}


DYNAMIC_CAMPUS_AREA_2_CONFIG["image_path"] = _campus_lane_variant_image_path(
    area_number=2,
    narrow_lanes=bool(DYNAMIC_CAMPUS_AREA_2_CONFIG["narrow_lanes"]),
)


BRANCH_USER_CONFIGS = {
    "static_artificial": STATIC_ARTIFICIAL_CONFIG,
    "static_campus_area_1": STATIC_CAMPUS_AREA_1_CONFIG,
    "dynamic_port": DYNAMIC_PORT_CONFIG,
    "dynamic_campus_area_2": DYNAMIC_CAMPUS_AREA_2_CONFIG,
}
