from dev.experiments.dynamic_port.pipeline import run_dynamic_port_experiment
from dev.experiments.static_artificial.pipeline import run_static_artificial_experiment


RUN_CONTEXT = "dynamic_port"  # "static_artificial" | "dynamic_port" | "both"

# Static artificial settings
STATIC_SELECTED_MAP_NAME = "map_1"
STATIC_COMPUTATION_DURATION_LIMIT = 30.0

STATIC_NUM_OF_AGENTS = 9
STATIC_TARGET_S_OBSTACLE_DENSITY = 0.40
STATIC_ARTIFICIAL_SEED = 13

# Dynamic port settings
DYNAMIC_COMPUTATION_DURATION_LIMIT = 30.0
DYNAMIC_LOOP_SEQUENCE_LENGTH = 30
DYNAMIC_GROUP_STAY_DURATIONS = (3, 4, 5)
DYNAMIC_SELECTED_MAP_NAME = "port_map"

DYNAMIC_NUM_OF_AGENTS = 16
DYNAMIC_TARGET_S_OBSTACLE_DENSITY = 0.15 # 0.20
DYNAMIC_TARGET_D_OBSTACLE_DENSITY = 0.05 # 0.06
DYNAMIC_PORT_SEED = 2


def main():
    if RUN_CONTEXT == "static_artificial":
        run_static_artificial_experiment(
            selected_map_name=STATIC_SELECTED_MAP_NAME,
            num_agents=STATIC_NUM_OF_AGENTS,
            obstacle_ratio=STATIC_TARGET_S_OBSTACLE_DENSITY,
            max_solver_runtime_seconds=STATIC_COMPUTATION_DURATION_LIMIT,
            seed=STATIC_ARTIFICIAL_SEED,
        )
    elif RUN_CONTEXT == "dynamic_port":
        run_dynamic_port_experiment(
            selected_map_name=DYNAMIC_SELECTED_MAP_NAME,
            num_agents=DYNAMIC_NUM_OF_AGENTS,
            target_static_obstacle_density=DYNAMIC_TARGET_S_OBSTACLE_DENSITY,
            target_dynamic_obstacle_density=DYNAMIC_TARGET_D_OBSTACLE_DENSITY,
            max_solver_runtime_seconds=DYNAMIC_COMPUTATION_DURATION_LIMIT,
            seed=DYNAMIC_PORT_SEED,
            loop_sequence_length=DYNAMIC_LOOP_SEQUENCE_LENGTH,
            group_stay_durations=DYNAMIC_GROUP_STAY_DURATIONS,
        )
    elif RUN_CONTEXT == "both":
        run_static_artificial_experiment(
            selected_map_name=STATIC_SELECTED_MAP_NAME,
            num_agents=STATIC_NUM_OF_AGENTS,
            obstacle_ratio=STATIC_TARGET_S_OBSTACLE_DENSITY,
            max_solver_runtime_seconds=STATIC_COMPUTATION_DURATION_LIMIT,
            seed=STATIC_ARTIFICIAL_SEED,
        )
        print("\n" + "=" * 72)
        run_dynamic_port_experiment(
            selected_map_name=DYNAMIC_SELECTED_MAP_NAME,
            num_agents=DYNAMIC_NUM_OF_AGENTS,
            target_static_obstacle_density=DYNAMIC_TARGET_S_OBSTACLE_DENSITY,
            target_dynamic_obstacle_density=DYNAMIC_TARGET_D_OBSTACLE_DENSITY,
            max_solver_runtime_seconds=DYNAMIC_COMPUTATION_DURATION_LIMIT,
            seed=DYNAMIC_PORT_SEED,
            loop_sequence_length=DYNAMIC_LOOP_SEQUENCE_LENGTH,
            group_stay_durations=DYNAMIC_GROUP_STAY_DURATIONS,
        )
    else:
        raise ValueError(
            "RUN_CONTEXT must be one of: "
            "'static_artificial', 'dynamic_port', or 'both'."
        )


if __name__ == "__main__":
    main()
