from dev.master_config import DYNAMIC_PORT_CONFIG


DYNAMIC_PORT_CONDITION_NAME = "condition_beta"
PORT_MAP_NAME = "port_map"
TARGET_STATIC_OBSTACLE_DENSITY = float(DYNAMIC_PORT_CONFIG["target_static_obstacle_density"])
TARGET_DYNAMIC_OBSTACLE_DENSITY = float(DYNAMIC_PORT_CONFIG["target_dynamic_obstacle_density"])
LOOP_SEQUENCE_LENGTH = int(DYNAMIC_PORT_CONFIG["loop_sequence_length"])
GROUP_STAY_DURATIONS = tuple(DYNAMIC_PORT_CONFIG["group_stay_durations"])
PORT_MAP_THRESHOLD = int(DYNAMIC_PORT_CONFIG["image_threshold"])
PORT_MAP_IMAGE_PATH = DYNAMIC_PORT_CONFIG["image_path"]
