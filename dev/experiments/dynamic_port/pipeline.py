import os
import random

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


def _clear_terminal_screen():
    if os.name == "nt":
        os.system("cls")
    elif os.getenv("TERM"):
        os.system("clear")
    else:
        print("\n" * 100, end="")


def matrix_to_obstacle_frame(matrix, treat_dynamic_as_obstacle=True):
    obstacle_values = (1, 2) if treat_dynamic_as_obstacle else (1,)
    obstacle_matrix = [[1 if cell in obstacle_values else 0 for cell in row] for row in matrix]
    return obstacle_matrix_to_composite_base_map(obstacle_matrix)


def build_mapped_loop(base_dynamic_frames):
    unmapped_frames = {
        f"frame_{index:03d}": matrix_to_obstacle_frame(frame, treat_dynamic_as_obstacle=True)
        for index, frame in enumerate(base_dynamic_frames)
    }
    classical_frames_dict = apply_classical_mapping(unmapped_frames)
    cyclic_frames_dict = apply_cyclic_mapping(unmapped_frames)
    ordered_names = list(unmapped_frames.keys())
    classical_loop = [classical_frames_dict[name] for name in ordered_names]
    cyclic_loop = [cyclic_frames_dict[name] for name in ordered_names]
    return classical_loop, cyclic_loop


def build_static_only_setup_maps(static_matrix):
    static_base = matrix_to_obstacle_frame(static_matrix, treat_dynamic_as_obstacle=False)
    classical_setup = apply_classical_mapping({"setup": static_base})["setup"]
    cyclic_setup = apply_cyclic_mapping({"setup": static_base})["setup"]
    return classical_setup, cyclic_setup


def get_shared_assignment_map(classical_loop):
    return classical_loop[0]


def summarize_dynamic_loop(raw_obstacle_matrix, static_matrix, dynamic_loop_frames, num_agents, target_static_obstacle_density, target_dynamic_obstacle_density, seed=None):
    rows = len(dynamic_loop_frames[0])
    cols = len(dynamic_loop_frames[0][0])
    total_cells = rows * cols
    raw_static_count = sum(cell == 1 for row in raw_obstacle_matrix for cell in row)
    static_count = sum(cell == 1 for row in static_matrix for cell in row)
    dynamic_counts = [sum(cell == 2 for row in frame for cell in row) for frame in dynamic_loop_frames]

    print("[Dynamic | Port Map]")
    print(f"Number of agents: {num_agents}")
    print(f"Map dimensions: {rows}x{cols}")
    print(f"Raw S-obstacle density: {raw_static_count / total_cells:.2f}")
    print(f"Target S-obstacle density: {target_static_obstacle_density:.2f}")
    print(f"Target D-obstacle density: {target_dynamic_obstacle_density:.2f}")
    print(f"S-obstacle cells per frame: {static_count}")
    print(f"D-obstacle cells per frame: {dynamic_counts[0] if dynamic_counts else 0}")
    print(f"Loop sequence length: {len(dynamic_loop_frames)}")
    print(f"Seed: {seed}")


def run_dynamic_port_experiment(
    selected_map_name=DEFAULT_SELECTED_MAP_NAME,
    num_agents=DEFAULT_NUM_OF_AGENTS,
    target_static_obstacle_density=TARGET_STATIC_OBSTACLE_DENSITY,
    target_dynamic_obstacle_density=TARGET_DYNAMIC_OBSTACLE_DENSITY,
    max_solver_runtime_seconds=DEFAULT_MAX_SOLVER_RUNTIME_SECONDS,
    seed=None,
):
    clear_output_dir(DYNAMIC_PORT_DIR)

    raw_obstacle_matrix = load_port_obstacle_matrix(
        image_path=PORT_MAP_IMAGE_PATH,
        threshold=PORT_MAP_THRESHOLD,
    )
    preprocessed_static_matrix = preprocess_static_obstacle_density(
        obstacle_matrix=raw_obstacle_matrix,
        target_density=target_static_obstacle_density,
        seed=seed,
    )
    dynamic_loop_frames = build_dynamic_loop(
        base_matrix=preprocessed_static_matrix,
        dynamic_density=target_dynamic_obstacle_density,
        loop_length=LOOP_SEQUENCE_LENGTH,
        preferred_group_range=PREFERRED_DYNAMIC_GROUP_COUNT_RANGE,
        seed=seed,
    )
    classical_loop, cyclic_loop = build_mapped_loop(dynamic_loop_frames)
    classical_setup_map, cyclic_setup_map = build_static_only_setup_maps(preprocessed_static_matrix)

    rng = random.Random(seed)

    _clear_terminal_screen()
    summarize_dynamic_loop(
        raw_obstacle_matrix=raw_obstacle_matrix,
        static_matrix=preprocessed_static_matrix,
        dynamic_loop_frames=dynamic_loop_frames,
        num_agents=num_agents,
        target_static_obstacle_density=target_static_obstacle_density,
        target_dynamic_obstacle_density=target_dynamic_obstacle_density,
        seed=seed,
    )
    print()
    shared_agents = sample_agent_start_goal_pairs(
        composite_map=get_shared_assignment_map(classical_loop),
        num_agents=num_agents,
        rng=rng,
    )

    cyclic_result = run_time_expanded_mapf_for_loop(
        map_name=selected_map_name,
        mapping_name="cyclic",
        mapped_loop=cyclic_loop,
        dynamic_matrix_loop=dynamic_loop_frames,
        setup_composite_map=cyclic_setup_map,
        agents=shared_agents,
        output_root=DYNAMIC_PORT_DIR,
        max_solver_runtime_seconds=max_solver_runtime_seconds,
        context_label="[Dynamic | Port Map]",
    )

    if cyclic_result is None:
        return {
            "status": "failed",
            "context": "dynamic_port",
            "condition": CONDITION_NAME,
            "selected_map_name": selected_map_name,
            "seed": seed,
            "agents": shared_agents,
            "results": {"cyclic": None, "classical": None},
        }

    print()
    classical_result = run_time_expanded_mapf_for_loop(
        map_name=selected_map_name,
        mapping_name="classical",
        mapped_loop=classical_loop,
        dynamic_matrix_loop=dynamic_loop_frames,
        setup_composite_map=classical_setup_map,
        agents=shared_agents,
        output_root=DYNAMIC_PORT_DIR,
        max_solver_runtime_seconds=max_solver_runtime_seconds,
        context_label="[Dynamic | Port Map]",
    )
    return {
        "status": "completed" if classical_result is not None else "failed",
        "context": "dynamic_port",
        "condition": CONDITION_NAME,
        "selected_map_name": selected_map_name,
        "seed": seed,
        "agents": shared_agents,
        "results": {"cyclic": cyclic_result, "classical": classical_result},
    }
