from __future__ import annotations

from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
INPUTS_ROOT = PACKAGE_ROOT / "inputs"


def _campus_area_image_path(*, area_number: int) -> str:
    if area_number not in {1, 2}:
        raise ValueError(f"Unsupported campus area number: {area_number}")
    return str(INPUTS_ROOT / f"campus_area_{area_number}.png")


def _port_image_path() -> str:
    return str(INPUTS_ROOT / "dynamic_port" / "port_map.png")


def _with_shared_runtime(config: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "time_limit_seconds": SHARED_TIME_LIMIT_SECONDS,
        "counted_runs_required": SHARED_COUNTED_RUNS_REQUIRED,
        "capacity_successful_runs_required": CAPACITY_SUCCESSFUL_RUNS_REQUIRED,
        "capacity_attempts_per_agent_number": CAPACITY_ATTEMPTS_PER_AGENT_NUMBER,
        "capacity_agent_upper_bound": CAPACITY_AGENT_UPPER_BOUND,
        "capacity_binary_search_max_downward_moves": CAPACITY_BINARY_SEARCH_MAX_DOWNWARD_MOVES,
        "capacity_pass_criterion": CAPACITY_PASS_CRITERION,
        "setup_generation_attempt_cap_per_solver_attempt": SETUP_GENERATION_ATTEMPT_CAP_PER_SOLVER_ATTEMPT,
        "prompt_before_next_map_config": PROMPT_BEFORE_NEXT_MAP_CONFIG,
        "ECBS_suboptimality": SHARED_ECBS_SUBOPTIMALITY,
        "true_static_shortest_path_distance": SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
        "tight_time_horizon": SHARED_TIGHT_TIME_HORIZON,
        "num_last_runs_to_visualize_jointly_successful": 3,
        "num_last_runs_to_visualize_independently_successful": 3,
    }
    payload.update(config)
    return payload


# Shared constants for the updated main experiment.
enhanced_CBS = True
compact_clustering = True
PORT_CLUSTERED_START_GOAL_MIN_DISTANCE = 20

# Agent cohesion is enabled for campus branches and Dynamic Port only.
# Static Port and artificial branches remain normal MAPF branches without cohesion.
agent_cohesion: bool = True
cohesion_factor: float = 1.0

SHARED_TIME_LIMIT_SECONDS = 30.0
SHARED_ECBS_SUBOPTIMALITY = 3.0
SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE = True
SHARED_TIGHT_TIME_HORIZON = False

# Capacity-search protocol constants.
# Valid values:
#   "solver_success"       -> each mapping passes if it solves within the time limit.
#   "temp_cyclic"    -> classical uses solver capacity, while cyclic passes only
#                             when it solves and beats classical on the same setup in
#                             time computation halted and conflicts at halt.
#   "temp_pairwise"  -> both capacity searches use the temp criterion:
#                             classical passes only when classical solves and cyclic
#                             beats it on the same setup; cyclic passes only when cyclic
#                             solves and beats classical on the same setup.
CAPACITY_PASS_CRITERION = "temp_pairwise"

SHARED_COUNTED_RUNS_REQUIRED = 1
CAPACITY_ATTEMPTS_PER_AGENT_NUMBER = 5
CAPACITY_SUCCESSFUL_RUNS_REQUIRED = 1
CAPACITY_AGENT_UPPER_BOUND = 255
CAPACITY_BINARY_SEARCH_MAX_DOWNWARD_MOVES = 3
SETUP_GENERATION_ATTEMPT_CAP_PER_SOLVER_ATTEMPT = 5

# When multiple map configurations are selected, ask after each completed
# configuration whether to continue. Enter 1 to continue or 0 to terminate
# early.
PROMPT_BEFORE_NEXT_MAP_CONFIG = True

# ===================================

# Select exactly one program mode.
to_generate = "raw_data"        # compute binary-search capacity data and text logs
# to_generate = "graphs"        # generate graphs for the selected map configs from saved raw data
# to_generate = "visualization" # generate visualizations for the selected map configs from saved raw data

# Select one or more exact main-experiment map configurations. Uncomment only
# the configurations that should be processed by the active to_generate mode.
SELECTED_MAP_CONFIGS = [
    # "static_artificial_dispersed_dispersed",
    # "static_artificial_dispersed_clustered",
    # "static_artificial_clustered_dispersed",
    # "static_artificial_clustered_clustered",
    # "dynamic_artificial_dispersed_dispersed",
    # "dynamic_artificial_dispersed_clustered",
    # "dynamic_artificial_clustered_dispersed",
    # "dynamic_artificial_clustered_clustered",

    # "static_port_dispersed_dispersed",
    # "static_port_dispersed_clustered",
    # "static_port_clustered_dispersed",
    # "static_port_clustered_clustered",
    # "dynamic_port_dispersed_dispersed",
    # "dynamic_port_dispersed_clustered",
    # "dynamic_port_clustered_dispersed",
    # "dynamic_port_clustered_clustered",

    # "static_campus_area_1_dispersed_dispersed",
    # "static_campus_area_1_dispersed_single",
    # "static_campus_area_1_single_dispersed",
    # "static_campus_area_1_single_single",
    # "dynamic_campus_area_1_dispersed_dispersed",
    # "dynamic_campus_area_1_dispersed_single",
    # "dynamic_campus_area_1_single_dispersed",
    # "dynamic_campus_area_1_single_single",

    # "static_campus_area_2_dispersed_dispersed",
    # "static_campus_area_2_dispersed_single",
    # "static_campus_area_2_single_dispersed",
    # "static_campus_area_2_single_single",
    # "dynamic_campus_area_2_dispersed_dispersed",
    # "dynamic_campus_area_2_dispersed_single",
    # "dynamic_campus_area_2_single_dispersed",
    # "dynamic_campus_area_2_single_single",
]

STATIC_ARTIFICIAL_CONFIG = _with_shared_runtime(
    {
        "seed": 101,
        "agent_number_range": (1, CAPACITY_AGENT_UPPER_BOUND, 1),
        "start_distribution_mode": "dispersed",
        "goal_distribution_mode": "dispersed",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": False,
        "zone_relationship_mode": "none",
        "spawnable_cell_mode": "all_free",
        "image_threshold": 127,
        "image_path": None,
        "image_resize_longest_side": None,
        "target_static_obstacle_density": None,
        "target_dynamic_obstacle_density": None,
        "loop_sequence_length": None,
        "group_stay_durations": None,
        "dynamic_generation_cell_mode": "all_free",
        "map_size": (32, 32),
        "static_obstacle_density": 0.40,
        "is_dynamic": False,
        "display_name": "Static Artificial",
        "map_family": "traditional_mapf",
        "category_index": 1,
    }
)

DYNAMIC_ARTIFICIAL_CONFIG = _with_shared_runtime(
    {
        "seed": 151,
        "agent_number_range": (1, CAPACITY_AGENT_UPPER_BOUND, 1),
        "start_distribution_mode": "dispersed",
        "goal_distribution_mode": "dispersed",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": False,
        "zone_relationship_mode": "none",
        "spawnable_cell_mode": "all_free",
        "image_threshold": 127,
        "image_path": None,
        "image_resize_longest_side": None,
        "target_static_obstacle_density": None,
        "target_dynamic_obstacle_density": 0.05,
        "loop_sequence_length": 250,
        "group_stay_durations": (7, 11, 17),
        "dynamic_generation_cell_mode": "all_free",
        "map_size": (32, 32),
        "static_obstacle_density": 0.35,
        "is_dynamic": True,
        "display_name": "Dynamic Artificial",
        "map_family": "traditional_mapf",
        "category_index": 2,
    }
)

STATIC_PORT_CONFIG = _with_shared_runtime(
    {
        "seed": 201,
        "agent_number_range": (1, CAPACITY_AGENT_UPPER_BOUND, 1),
        "start_distribution_mode": "dispersed",
        "goal_distribution_mode": "dispersed",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": True,
        "zone_relationship_mode": "none",
        "spawnable_cell_mode": "all_free",
        "image_threshold": 127,
        "image_path": _port_image_path(),
        "image_resize_longest_side": 40,
        "target_static_obstacle_density": 1.0,
        "target_dynamic_obstacle_density": None,
        "loop_sequence_length": None,
        "group_stay_durations": None,
        "dynamic_generation_cell_mode": "all_free",
        "map_size": None,
        "static_obstacle_density": 1.0,
        "is_dynamic": False,
        "display_name": "Static Port",
        "map_family": "traditional_mapf",
        "category_index": 3,
    }
)

DYNAMIC_PORT_CONFIG = _with_shared_runtime(
    {
        "seed": 301,
        "agent_number_range": (1, CAPACITY_AGENT_UPPER_BOUND, 1),
        "start_distribution_mode": "dispersed",
        "goal_distribution_mode": "dispersed",
        "clustered_start_goal_min_distance": PORT_CLUSTERED_START_GOAL_MIN_DISTANCE,
        "require_individual_reachability": True,
        "zone_relationship_mode": "none",
        "spawnable_cell_mode": "all_free",
        "image_threshold": 127,
        "image_path": _port_image_path(),
        "image_resize_longest_side": 40,
        "target_static_obstacle_density": 1.0,
        "target_dynamic_obstacle_density": 0.025,
        "loop_sequence_length": 250,
        "group_stay_durations": (11, 17, 29),
        "dynamic_generation_cell_mode": "all_free",
        "map_size": None,
        "static_obstacle_density": 0.8,
        "is_dynamic": True,
        "display_name": "Dynamic Port",
        "map_family": "traditional_mapf",
        "category_index": 4,
    }
)

STATIC_CAMPUS_AREA_1_CONFIG = _with_shared_runtime(
    {
        "seed": 401,
        "agent_number_range": (1, CAPACITY_AGENT_UPPER_BOUND, 1),
        "start_distribution_mode": "dispersed",
        "goal_distribution_mode": "dispersed",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": True,
        "zone_relationship_mode": "distinct_campus_zones",
        "spawnable_cell_mode": "zone_colors_only",
        "image_threshold": 127,
        "image_path": _campus_area_image_path(area_number=1),
        "image_resize_longest_side": None,
        "target_static_obstacle_density": None,
        "target_dynamic_obstacle_density": None,
        "loop_sequence_length": None,
        "group_stay_durations": None,
        "dynamic_generation_cell_mode": "zone_colors_only",
        "map_size": None,
        "static_obstacle_density": None,
        "is_dynamic": False,
        "display_name": "Static Campus Area 1",
        "map_family": "campus_crowd_simulation",
        "category_index": 5,
    }
)

DYNAMIC_CAMPUS_AREA_1_CONFIG = _with_shared_runtime(
    {
        "seed": 501,
        "agent_number_range": (1, CAPACITY_AGENT_UPPER_BOUND, 1),
        "start_distribution_mode": "dispersed",
        "goal_distribution_mode": "dispersed",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": True,
        "zone_relationship_mode": "distinct_campus_zones",
        "spawnable_cell_mode": "zone_colors_only",
        "image_threshold": 127,
        "image_path": _campus_area_image_path(area_number=1),
        "image_resize_longest_side": None,
        "target_static_obstacle_density": None,
        "target_dynamic_obstacle_density": 0.015,
        "loop_sequence_length": 250,
        "group_stay_durations": (17, 29, 37),
        "dynamic_generation_cell_mode": "all_free",
        "map_size": None,
        "static_obstacle_density": None,
        "is_dynamic": True,
        "display_name": "Dynamic Campus Area 1",
        "map_family": "campus_crowd_simulation",
        "category_index": 6,
    }
)

STATIC_CAMPUS_AREA_2_CONFIG = _with_shared_runtime(
    {
        "seed": 601,
        "agent_number_range": (1, CAPACITY_AGENT_UPPER_BOUND, 1),
        "start_distribution_mode": "dispersed",
        "goal_distribution_mode": "dispersed",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": True,
        "zone_relationship_mode": "distinct_campus_zones",
        "spawnable_cell_mode": "zone_colors_only",
        "image_threshold": 127,
        "image_path": _campus_area_image_path(area_number=2),
        "image_resize_longest_side": None,
        "target_static_obstacle_density": None,
        "target_dynamic_obstacle_density": None,
        "loop_sequence_length": None,
        "group_stay_durations": None,
        "dynamic_generation_cell_mode": "zone_colors_only",
        "map_size": None,
        "static_obstacle_density": None,
        "is_dynamic": False,
        "display_name": "Static Campus Area 2",
        "map_family": "campus_crowd_simulation",
        "category_index": 7,
    }
)

DYNAMIC_CAMPUS_AREA_2_CONFIG = _with_shared_runtime(
    {
        "seed": 701,
        "agent_number_range": (1, CAPACITY_AGENT_UPPER_BOUND, 1),
        "start_distribution_mode": "dispersed",
        "goal_distribution_mode": "dispersed",
        "clustered_start_goal_min_distance": None,
        "require_individual_reachability": True,
        "zone_relationship_mode": "distinct_campus_zones",
        "spawnable_cell_mode": "zone_colors_only",
        "image_threshold": 127,
        "image_path": _campus_area_image_path(area_number=2),
        "image_resize_longest_side": None,
        "target_static_obstacle_density": None,
        "target_dynamic_obstacle_density": 0.015,
        "loop_sequence_length": 250,
        "group_stay_durations": (17, 29, 37),
        "dynamic_generation_cell_mode": "all_free",
        "map_size": None,
        "static_obstacle_density": None,
        "is_dynamic": True,
        "display_name": "Dynamic Campus Area 2",
        "map_family": "campus_crowd_simulation",
        "category_index": 8,
    }
)

BRANCH_USER_CONFIGS = {
    "static_artificial": STATIC_ARTIFICIAL_CONFIG,
    "dynamic_artificial": DYNAMIC_ARTIFICIAL_CONFIG,
    "static_port": STATIC_PORT_CONFIG,
    "dynamic_port": DYNAMIC_PORT_CONFIG,
    "static_campus_area_1": STATIC_CAMPUS_AREA_1_CONFIG,
    "dynamic_campus_area_1": DYNAMIC_CAMPUS_AREA_1_CONFIG,
    "static_campus_area_2": STATIC_CAMPUS_AREA_2_CONFIG,
    "dynamic_campus_area_2": DYNAMIC_CAMPUS_AREA_2_CONFIG,
}
