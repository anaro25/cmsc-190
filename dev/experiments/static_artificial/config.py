from dev.master_config import STATIC_ARTIFICIAL_CONFIG


STATIC_ARTIFICIAL_MAP_SPEC = {
    "name": "map_1",
    "base_rows": int(STATIC_ARTIFICIAL_CONFIG["map_size"][0]),
    "base_cols": int(STATIC_ARTIFICIAL_CONFIG["map_size"][1]),
}

STATIC_ARTIFICIAL_OBSTACLE_RATIO = float(STATIC_ARTIFICIAL_CONFIG["static_obstacle_density"])
STATIC_ARTIFICIAL_CONDITION_NAME = "condition_alpha"
