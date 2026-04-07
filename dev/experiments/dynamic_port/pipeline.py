from dev.experiments.dynamic_port.config import (
    CONDITION_NAME,
    DEFAULT_MAX_SOLVER_RUNTIME_SECONDS,
    DEFAULT_NUM_OF_AGENTS,
    DEFAULT_SELECTED_MAP_NAME,
    LOOP_SEQUENCE_LENGTH,
    PORT_MAP_IMAGE_PATH,
    PORT_MAP_THRESHOLD,
    PREFERRED_DYNAMIC_GROUP_COUNT_RANGE,
    TARGET_DYNAMIC_OBSTACLE_DENSITY,
    TARGET_STATIC_OBSTACLE_DENSITY,
)
from dev.experiments.dynamic_port.dynamic_loop import build_dynamic_loop
from dev.experiments.dynamic_port.preprocessing import preprocess_static_obstacle_density
from dev.inputs.dynamic_port.loader import load_port_obstacle_matrix
from dev.inputs.dynamic_port.map_builder import obstacle_matrix_to_composite_base_map
from dev.mapf.agent_assignment import sample_agent_start_goal_pairs
from dev.mapf.time_expanded_runner import run_time_expanded_mapf_for_loop
from dev.maps.classical_mapper import apply_classical_mapping
from dev.maps.cyclic_mapper import apply_cyclic_mapping
from dev.paths import DYNAMIC_PORT_DIR, clear_output_dir


def matrix_to_static_free_frame(matrix):
    obstacle_matrix = [[1 if cell in (1, 2) else 0 for cell in row] for row in matrix]
    return obstacle_matrix_to_composite_base_map(obstacle_matrix)


def build_mapped_loop(base_dynamic_frames):
    unmapped_frames = {
        f"frame_{index:03d}": matrix_to_static_free_frame(frame)
        for index, frame in enumerate(base_dynamic_frames)
    }
    classical_frames_dict = apply_classical_mapping(unmapped_frames)
    cyclic_frames_dict = apply_cyclic_mapping(unmapped_frames)
    ordered_names = list(unmapped_frames.keys())
    classical_loop = [classical_frames_dict[name] for name in ordered_names]
    cyclic_loop = [cyclic_frames_dict[name] for name in ordered_names]
    return classical_loop, cyclic_loop


def get_shared_assignment_map(classical_loop):
    return classical_loop[0]


def summarize_dynamic_loop(dynamic_loop_frames):
    rows = len(dynamic_loop_frames[0])
    cols = len(dynamic_loop_frames[0][0])
    dynamic_counts = [sum(cell == 2 for row in frame for cell in row) for frame in dynamic_loop_frames]
    varying_frames = 0
    for index in range(1, len(dynamic_loop_frames)):
        if dynamic_loop_frames[index] != dynamic_loop_frames[index - 1]:
            varying_frames += 1
    print(f"Raw port-map dimensions: {rows}x{cols}")
    print(f"Dynamic obstacle cells per frame: {dynamic_counts[0]}")
    print(f"Frames that differ from previous frame: {varying_frames}/{max(0, len(dynamic_loop_frames)-1)}")


def run_dynamic_port_experiment(
    selected_map_name=DEFAULT_SELECTED_MAP_NAME,
    num_agents=DEFAULT_NUM_OF_AGENTS,
    max_solver_runtime_seconds=DEFAULT_MAX_SOLVER_RUNTIME_SECONDS,
):
    print(f"\n[Dynamic | Port map | {CONDITION_NAME}]")
    clear_output_dir(DYNAMIC_PORT_DIR)

    raw_obstacle_matrix = load_port_obstacle_matrix(
        image_path=PORT_MAP_IMAGE_PATH,
        threshold=PORT_MAP_THRESHOLD,
    )
    preprocessed_static_matrix = preprocess_static_obstacle_density(
        obstacle_matrix=raw_obstacle_matrix,
        target_density=TARGET_STATIC_OBSTACLE_DENSITY,
        seed=42,
    )
    dynamic_loop_frames = build_dynamic_loop(
        base_matrix=preprocessed_static_matrix,
        dynamic_density=TARGET_DYNAMIC_OBSTACLE_DENSITY,
        loop_length=LOOP_SEQUENCE_LENGTH,
        preferred_group_range=PREFERRED_DYNAMIC_GROUP_COUNT_RANGE,
        seed=42,
    )
    summarize_dynamic_loop(dynamic_loop_frames)
    classical_loop, cyclic_loop = build_mapped_loop(dynamic_loop_frames)

    shared_agents = sample_agent_start_goal_pairs(
        composite_map=get_shared_assignment_map(classical_loop),
        num_agents=num_agents,
    )

    cyclic_result = run_time_expanded_mapf_for_loop(
        map_name=selected_map_name,
        mapping_name="cyclic",
        mapped_loop=cyclic_loop,
        dynamic_matrix_loop=dynamic_loop_frames,
        agents=shared_agents,
        output_root=DYNAMIC_PORT_DIR,
        max_solver_runtime_seconds=max_solver_runtime_seconds,
    )

    print()

    classical_result = run_time_expanded_mapf_for_loop(
        map_name=selected_map_name,
        mapping_name="classical",
        mapped_loop=classical_loop,
        dynamic_matrix_loop=dynamic_loop_frames,
        agents=shared_agents,
        output_root=DYNAMIC_PORT_DIR,
        max_solver_runtime_seconds=max_solver_runtime_seconds,
    )

    return {
        "status": "completed" if cyclic_result is not None or classical_result is not None else "failed",
        "context": "dynamic_port",
        "condition": CONDITION_NAME,
        "selected_map_name": selected_map_name,
        "results": {"cyclic": cyclic_result, "classical": classical_result},
    }
