from pathlib import Path

DEFAULT_NUM_OF_AGENTS = 9
DEFAULT_MAX_SOLVER_RUNTIME_SECONDS = 30.0
DEFAULT_SELECTED_MAP_NAME = "port_map"
CONDITION_NAME = "condition_beta"

TARGET_STATIC_OBSTACLE_DENSITY = 0.20
TARGET_DYNAMIC_OBSTACLE_DENSITY = 0.10
LOOP_SEQUENCE_LENGTH = 30
GROUP_STAY_DURATIONS = (3, 4, 5)
PORT_MAP_THRESHOLD = 127

PORT_MAP_IMAGE_PATH = (
    Path(__file__).resolve().parents[2]
    / "inputs"
    / "dynamic_port"
    / "port_map"
    / "port_map.png"
)

