from __future__ import annotations

from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
INPUTS_ROOT = PACKAGE_ROOT / "inputs"


def _campus_area_image_path(*, area_number: int) -> str:
    if area_number not in {1, 2, 3}:
        raise ValueError(f"Unsupported campus area number: {area_number}")
    return str(INPUTS_ROOT / f"campus_area_{area_number}.png")


def _port_image_path() -> str:
    return str(INPUTS_ROOT / "dynamic_port" / "port_map.png")


def _with_shared_runtime(config: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
        "counted_runs_required": (
            TEMPORARY_INDIVIDUAL_CYCLIC_FASTER_RUNS_REQUIRED
            if TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER
            else SHARED_COUNTED_RUNS_REQUIRED
        ),
        "ECBS_suboptimality": SHARED_ECBS_SUBOPTIMALITY,
        "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
        "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,
        "filter_individual_runs_until_cyclic_faster": TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER,
        "filter_individual_runs_until_cyclic_faster_max_attempts": TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER_MAX_ATTEMPTS,
        "rerun_until_cyclic_faster": False,
        "rerun_until_cyclic_faster_max_batches": None,
        "num_last_runs_to_visualize_jointly_successful": 3,
        "num_last_runs_to_visualize_independently_successful": 3,
    }
    payload.update(config)
    if TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER:
        payload["counted_runs_required"] = TEMPORARY_INDIVIDUAL_CYCLIC_FASTER_RUNS_REQUIRED
        payload["filter_individual_runs_until_cyclic_faster"] = True
        payload["filter_individual_runs_until_cyclic_faster_max_attempts"] = (
            TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER_MAX_ATTEMPTS
        )
        payload["rerun_until_cyclic_faster"] = False
        payload["rerun_until_cyclic_faster_max_batches"] = None
    return payload


# If the current agent-number condition reaches this many consecutive jointly
# non-viable paired sampling attempts, that entire condition is discarded and
# the branch stops before higher agent numbers.
CONSECUTIVE_FAILED_PAIRED_SAMPLING_ATTEMPTS_LIMIT = 15

# shared constants
enhanced_CBS = True
compact_clustering = True
# Minimum Manhattan movement-step distance enforced between a clustered start set
# and a clustered goal set. Set to None or 0 to disable the separation rule.
PORT_CLUSTERED_START_GOAL_MIN_DISTANCE = 20

# Agent cohesion is enabled for campus branches and Dynamic Port only.
# Static Port remains a normal MAPF port branch without cohesion.
agent_cohesion: bool = True
cohesion_factor: float = 1.0
SHARED_TIME_LIMIT_SECONDS = 30.0
SHARED_ECBS_SUBOPTIMALITY = 3.0
SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE = True
SHARED_TIGHT_TIME_HORIZON = False
SHARED_COUNTED_RUNS_REQUIRED = 5
TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER = True
TEMPORARY_INDIVIDUAL_CYCLIC_FASTER_RUNS_REQUIRED = 3
TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER_MAX_ATTEMPTS = 15 # 20

# ===================================

recompute_MAPF = False

to_generate = "graphs_and_data"
# to_generate = "visualization"
# to_generate = "nothing"

# Traditional MAPF
MAP_TYPE = "static_artificial"
# MAP_TYPE = "static_port"
# MAP_TYPE = "dynamic_port"

# Campus Crowd Simulation
# MAP_TYPE = "static_campus_area_1"
# MAP_TYPE = "dynamic_campus_area_1"
# MAP_TYPE = "static_campus_area_2"
# MAP_TYPE = "dynamic_campus_area_2"

# MAP_TYPE = "static_campus_area_3"
# MAP_TYPE = "dynamic_campus_area_3"

# All 9 map-type configs are defined completely in this file.
# Edit the selected branch dictionary below, then set MAP_TYPE above.
STATIC_ARTIFICIAL_CONFIG = _with_shared_runtime(
    {
        # common frequently edited constants
        "seed": 101,
        "agent_number_range": (4, 100, 4), # goes beyond 100
        "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
        "num_last_runs_to_visualize_jointly_successful": 1,
        "num_last_runs_to_visualize_independently_successful": 1,
        "ECBS_suboptimality": 3.0,
        "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
        "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,

        # common permanent constants
        "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
        "start_distribution_mode": "dispersed",
        "goal_distribution_mode": "dispersed",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": False,
        "zone_relationship_mode": "none",
        "spawnable_cell_mode": "all_free",

        # image-map constants
        "image_threshold": 127,
        "image_path": None,
        "image_resize_longest_side": None,

        # dynamic-map constants
        "target_static_obstacle_density": None,
        "target_dynamic_obstacle_density": None,
        "loop_sequence_length": None,
        "group_stay_durations": None,
        "dynamic_generation_cell_mode": "all_free",

        # branch-specific constants
        "map_size": (32, 32),
        "static_obstacle_density": 0.40,
        "is_dynamic": False,
        "display_name": "Static Artificial",
        "map_family": "traditional_mapf",
    }
)

STATIC_PORT_CONFIG = _with_shared_runtime(
    {
        # common frequently edited constants
        "seed": 201,
        "agent_number_range": (2, 70, 2),
        "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
        "num_last_runs_to_visualize_jointly_successful": 0,
        "num_last_runs_to_visualize_independently_successful": 1,
        "ECBS_suboptimality": SHARED_ECBS_SUBOPTIMALITY,
        "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
        "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,

        # common permanent constants
        "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
        "start_distribution_mode": "dispersed",
        "goal_distribution_mode": "clustered",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": True,
        "zone_relationship_mode": "none",
        "spawnable_cell_mode": "all_free",

        # image-map constants
        "image_threshold": 127,
        "image_path": _port_image_path(),
        "image_resize_longest_side": 40,

        # dynamic-map constants
        "target_static_obstacle_density": 1.0,
        "target_dynamic_obstacle_density": None,
        "loop_sequence_length": None,
        "group_stay_durations": None,
        "dynamic_generation_cell_mode": "all_free",

        # branch-specific constants
        "map_size": None,
        "static_obstacle_density": 1.0,
        "is_dynamic": False,
        "display_name": "Static Port",
        "map_family": "traditional_mapf",
    }
)

DYNAMIC_PORT_CONFIG = _with_shared_runtime(
    {
        # common frequently edited constants
        "seed": 301,
        "agent_number_range": (2, 35, 1),
        "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
        "num_last_runs_to_visualize_jointly_successful": 0,
        "num_last_runs_to_visualize_independently_successful": 1,
        "ECBS_suboptimality": SHARED_ECBS_SUBOPTIMALITY,
        "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
        "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,

        # common permanent constants
        "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
        "start_distribution_mode": "clustered",
        "goal_distribution_mode": "clustered",
        "clustered_start_goal_min_distance": PORT_CLUSTERED_START_GOAL_MIN_DISTANCE,
        "require_individual_reachability": True,
        "zone_relationship_mode": "none",
        "spawnable_cell_mode": "all_free",

        # image-map constants
        "image_threshold": 127,
        "image_path": _port_image_path(),
        "image_resize_longest_side": 40,

        # dynamic-map constants
        "target_static_obstacle_density": 1.0,
        "target_dynamic_obstacle_density": 0.025,
        "loop_sequence_length": 250,
        "group_stay_durations": (11, 17, 29),
        "dynamic_generation_cell_mode": "all_free",

        # branch-specific constants
        "map_size": None,
        "static_obstacle_density": 0.8,
        "is_dynamic": True,
        "display_name": "Dynamic Port",
        "map_family": "traditional_mapf",
    }
)

# Campus Crowd Simulation
STATIC_CAMPUS_AREA_1_CONFIG = _with_shared_runtime(
    {
        # common frequently edited constants
        "seed": 401,
        "agent_number_range": (2, 200, 1),
        "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
        "num_last_runs_to_visualize_jointly_successful": 0,
        "num_last_runs_to_visualize_independently_successful": 1,
        "ECBS_suboptimality": SHARED_ECBS_SUBOPTIMALITY,
        "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
        "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,

        # common permanent constants
        "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
        "start_distribution_mode": "dispersed",
        "goal_distribution_mode": "single",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": True,
        "zone_relationship_mode": "distinct_campus_zones",
        "spawnable_cell_mode": "zone_colors_only",

        # image-map constants
        "image_threshold": 127,
        "image_path": _campus_area_image_path(area_number=1),
        "image_resize_longest_side": None,

        # dynamic-map constants
        "target_static_obstacle_density": None,
        "target_dynamic_obstacle_density": None,
        "loop_sequence_length": None,
        "group_stay_durations": None,
        "dynamic_generation_cell_mode": "zone_colors_only",

        # branch-specific constants
        "map_size": None,
        "static_obstacle_density": None,
        "is_dynamic": False,
        "display_name": "Static Campus Area 1",
        "map_family": "campus_crowd_simulation",
    }
)

DYNAMIC_CAMPUS_AREA_1_CONFIG = _with_shared_runtime(
    {
        # common frequently edited constants
        "seed": 501,
        "agent_number_range": (2, 200, 1),
        "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
        "num_last_runs_to_visualize_jointly_successful": 0,
        "num_last_runs_to_visualize_independently_successful": 1,
        "ECBS_suboptimality": SHARED_ECBS_SUBOPTIMALITY,
        "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
        "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,

        # common permanent constants
        "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
        "start_distribution_mode": "clustered",
        "goal_distribution_mode": "single",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": True,
        "zone_relationship_mode": "distinct_campus_zones",
        "spawnable_cell_mode": "zone_colors_only",

        # image-map constants
        "image_threshold": 127,
        "image_path": _campus_area_image_path(area_number=1),
        "image_resize_longest_side": None,

        # dynamic-map constants
        "target_static_obstacle_density": None,
        "target_dynamic_obstacle_density": 0.015,
        "loop_sequence_length": 250,
        "group_stay_durations": (17, 29, 37),
        "dynamic_generation_cell_mode": "all_free",

        # branch-specific constants
        "map_size": None,
        "static_obstacle_density": None,
        "is_dynamic": True,
        "display_name": "Dynamic Campus Area 1",
        "map_family": "campus_crowd_simulation",
    }
)

STATIC_CAMPUS_AREA_2_CONFIG = _with_shared_runtime(
    {
        # common frequently edited constants
        "seed": 601,
        "agent_number_range": (2, 200, 1),
        "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
        "num_last_runs_to_visualize_jointly_successful": 0,
        "num_last_runs_to_visualize_independently_successful": 1,
        "ECBS_suboptimality": SHARED_ECBS_SUBOPTIMALITY,
        "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
        "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,

        # common permanent constants
        "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
        "start_distribution_mode": "dispersed",
        "goal_distribution_mode": "single",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": True,
        "zone_relationship_mode": "distinct_campus_zones",
        "spawnable_cell_mode": "zone_colors_only",

        # image-map constants
        "image_threshold": 127,
        "image_path": _campus_area_image_path(area_number=2),
        "image_resize_longest_side": None,

        # dynamic-map constants
        "target_static_obstacle_density": None,
        "target_dynamic_obstacle_density": None,
        "loop_sequence_length": None,
        "group_stay_durations": None,
        "dynamic_generation_cell_mode": "zone_colors_only",

        # branch-specific constants
        "map_size": None,
        "static_obstacle_density": None,
        "is_dynamic": False,
        "display_name": "Static Campus Area 2",
        "map_family": "campus_crowd_simulation",
    }
)

DYNAMIC_CAMPUS_AREA_2_CONFIG = _with_shared_runtime(
    {
        # common frequently edited constants
        "seed": 701,
        "agent_number_range": (2, 200, 1),
        "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
        "num_last_runs_to_visualize_jointly_successful": 0,
        "num_last_runs_to_visualize_independently_successful": 1,
        "ECBS_suboptimality": SHARED_ECBS_SUBOPTIMALITY,
        "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
        "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,

        # common permanent constants
        "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
        "start_distribution_mode": "clustered",
        "goal_distribution_mode": "single",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": True,
        "zone_relationship_mode": "distinct_campus_zones",
        "spawnable_cell_mode": "zone_colors_only",

        # image-map constants
        "image_threshold": 127,
        "image_path": _campus_area_image_path(area_number=2),
        "image_resize_longest_side": None,

        # dynamic-map constants
        "target_static_obstacle_density": None,
        "target_dynamic_obstacle_density": 0.015,
        "loop_sequence_length": 250,
        "group_stay_durations": (17, 29, 37),
        "dynamic_generation_cell_mode": "all_free",

        # branch-specific constants
        "map_size": None,
        "static_obstacle_density": None,
        "is_dynamic": True,
        "display_name": "Dynamic Campus Area 2",
        "map_family": "campus_crowd_simulation",
    }
)

STATIC_CAMPUS_AREA_3_CONFIG = _with_shared_runtime(
    {
        # common frequently edited constants
        "seed": 801,
        "agent_number_range": (2, 200, 1),
        "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
        "num_last_runs_to_visualize_jointly_successful": 3,
        "num_last_runs_to_visualize_independently_successful": 3,
        "ECBS_suboptimality": SHARED_ECBS_SUBOPTIMALITY,
        "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
        "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,

        # common permanent constants
        "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
        "start_distribution_mode": "dispersed",
        "goal_distribution_mode": "single",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": True,
        "zone_relationship_mode": "distinct_campus_zones",
        "spawnable_cell_mode": "zone_colors_only",

        # image-map constants
        "image_threshold": 127,
        "image_path": _campus_area_image_path(area_number=3),
        "image_resize_longest_side": None,

        # dynamic-map constants
        "target_static_obstacle_density": None,
        "target_dynamic_obstacle_density": None,
        "loop_sequence_length": None,
        "group_stay_durations": None,
        "dynamic_generation_cell_mode": "zone_colors_only",

        # branch-specific constants
        "map_size": None,
        "static_obstacle_density": None,
        "is_dynamic": False,
        "display_name": "Static Campus Area 3",
        "map_family": "campus_crowd_simulation",
    }
)

DYNAMIC_CAMPUS_AREA_3_CONFIG = _with_shared_runtime(
    {
        # common frequently edited constants
        "seed": 901,
        "agent_number_range": (10, 10, 1),
        "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
        "num_last_runs_to_visualize_jointly_successful": 0,
        "num_last_runs_to_visualize_independently_successful": 1,
        "ECBS_suboptimality": SHARED_ECBS_SUBOPTIMALITY,
        "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
        "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,

        # common permanent constants
        "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
        "start_distribution_mode": "clustered",
        "goal_distribution_mode": "single",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": True,
        "zone_relationship_mode": "distinct_campus_zones",
        "spawnable_cell_mode": "zone_colors_only",

        # image-map constants
        "image_threshold": 127,
        "image_path": _campus_area_image_path(area_number=3),
        "image_resize_longest_side": None,

        # dynamic-map constants
        "target_static_obstacle_density": None,
        "target_dynamic_obstacle_density": 0.010,
        "loop_sequence_length": 250,
        "group_stay_durations": (17, 29, 37),
        "dynamic_generation_cell_mode": "all_free",

        # branch-specific constants
        "map_size": None,
        "static_obstacle_density": None,
        "is_dynamic": True,
        "display_name": "Dynamic Campus Area 3",
        "map_family": "campus_crowd_simulation",
    }
)

BRANCH_USER_CONFIGS = {
    "static_artificial": STATIC_ARTIFICIAL_CONFIG,
    "static_port": STATIC_PORT_CONFIG,
    "dynamic_port": DYNAMIC_PORT_CONFIG,
    "static_campus_area_1": STATIC_CAMPUS_AREA_1_CONFIG,
    "dynamic_campus_area_1": DYNAMIC_CAMPUS_AREA_1_CONFIG,
    "static_campus_area_2": STATIC_CAMPUS_AREA_2_CONFIG,
    "dynamic_campus_area_2": DYNAMIC_CAMPUS_AREA_2_CONFIG,
    "static_campus_area_3": STATIC_CAMPUS_AREA_3_CONFIG,
    "dynamic_campus_area_3": DYNAMIC_CAMPUS_AREA_3_CONFIG,
}
