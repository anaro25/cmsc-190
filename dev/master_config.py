from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
INPUTS_ROOT = PACKAGE_ROOT / "inputs"


# One user-defined limit applies to all branches.
# If the current agent-number condition reaches this many consecutive jointly
# non-viable paired sampling attempts, that entire condition is discarded and
# the branch stops before higher agent numbers.
CONSECUTIVE_FAILED_PAIRED_SAMPLING_ATTEMPTS_LIMIT = 15

# Global solver toggle for the whole project.
# False -> vanilla CBS
# True  -> Enhanced CBS (ECBS)
enhanced_CBS = True

# Uncomment exactly one MAP_TYPE.
MAP_TYPE = "static_artificial"
# MAP_TYPE = "static_campus_area_1"
# MAP_TYPE = "dynamic_port"
# MAP_TYPE = "dynamic_campus_area_2"

STATIC_ARTIFICIAL_CONFIG = {
    # common frequently edited constants
    "agent_number_range": (105, 200, 5), # max 120
    "time_limit_seconds": 30.0,
    "ECBS_suboptimality": 1.5,
    "num_last_runs_to_visualize": 1,
    "require_jointly_successful_mappings": False,
    "seed": 101,
    
    # common permanent constants
    "counted_runs_required": 5,
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
    "agent_number_range": (10, 10, 2),
    "time_limit_seconds": 5.0,
    "ECBS_suboptimality": 100.0,
    "num_last_runs_to_visualize": 1,
    "require_jointly_successful_mappings": False,
    "seed": 201,

    # common permanent constants
    "counted_runs_required": 5,
    "start_distribution_mode": "dispersed",
    "goal_distribution_mode": "clustered",
    "require_individual_reachability": True,
    "zone_relationship_mode": "distinct_campus_zones",
    
    # branch-specific constants
    "spawnable_cell_mode": "zone_colors_only",
    "image_threshold": 127,
    "image_path": str(INPUTS_ROOT / "dynamic_campus_area_1" / "campus_area_1_x64_colored.png"),
    "dynamic_generation_cell_mode": "zone_colors_only",
}

DYNAMIC_PORT_CONFIG = {
    # common frequently edited constants
    "agent_number_range": (8, 100, 2),
    "time_limit_seconds": 5.0,
    "ECBS_suboptimality": 100.0,
    "num_last_runs_to_visualize": 1,
    "require_jointly_successful_mappings": False,
    "seed": 301,    

    # common permanent constants
    "counted_runs_required": 5,
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
    "agent_number_range": (10, 100, 2),
    "time_limit_seconds": 30.0,
    "ECBS_suboptimality": 100.0,
    "num_last_runs_to_visualize": 1,
    "require_jointly_successful_mappings": False,
    "seed": 401,
    
    # common permanent constants
    "counted_runs_required": 5,
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
    "image_path": str(INPUTS_ROOT / "dynamic_campus_area_2" / "campus_area_2_x64_colored.png"),
    "dynamic_generation_cell_mode": "zone_colors_only",
    "spawnable_cell_mode": "zone_colors_only",
}


BRANCH_USER_CONFIGS = {
    "static_artificial": STATIC_ARTIFICIAL_CONFIG,
    "static_campus_area_1": STATIC_CAMPUS_AREA_1_CONFIG,
    "dynamic_port": DYNAMIC_PORT_CONFIG,
    "dynamic_campus_area_2": DYNAMIC_CAMPUS_AREA_2_CONFIG,
}
