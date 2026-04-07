import os
import random

from dev.experiments.static_artificial.config import (
    CONDITION_NAME,
    DEFAULT_MAX_SOLVER_RUNTIME_SECONDS,
    DEFAULT_NUM_OF_AGENTS,
    DEFAULT_OBSTACLE_RATIO,
    DEFAULT_SELECTED_MAP_NAME,
    MAP_SPECS,
)
from dev.mapf.agent_assignment import sample_agent_start_goal_pairs
from dev.mapf.mapf_runner import run_single_mapf_for_selected_map
from dev.maps.base_map_factory import assemble_base_maps
from dev.maps.classical_mapper import apply_classical_mapping
from dev.maps.cyclic_mapper import apply_cyclic_mapping
from dev.paths import STATIC_ARTIFICIAL_DIR, clear_output_dir


def _clear_terminal_screen():
    if os.name == "nt":
        os.system("cls")
    elif os.getenv("TERM"):
        os.system("clear")
    else:
        print("\n" * 100, end="")


def _get_map_dimensions(selected_map_name):
    for spec in MAP_SPECS:
        if spec["name"] == selected_map_name:
            return spec["base_rows"], spec["base_cols"]
    raise ValueError(f"Unknown static artificial map: {selected_map_name}")


def _print_context_block(selected_map_name, num_agents, obstacle_ratio, max_solver_runtime_seconds, seed=None):
    rows, cols = _get_map_dimensions(selected_map_name)
    print("[Static | Artificial]")
    print(f"Number of agents: {num_agents}")
    print(f"Map dimensions: {rows}x{cols}")
    print(f"Target S-obstacle density: {obstacle_ratio:.2f}")
    print(f"Seed: {seed}")


def run_static_artificial_experiment(
    selected_map_name=DEFAULT_SELECTED_MAP_NAME,
    num_agents=DEFAULT_NUM_OF_AGENTS,
    obstacle_ratio=DEFAULT_OBSTACLE_RATIO,
    max_solver_runtime_seconds=DEFAULT_MAX_SOLVER_RUNTIME_SECONDS,
    seed=None,
):
    clear_output_dir(STATIC_ARTIFICIAL_DIR)

    rng = random.Random(seed)
    base_maps = assemble_base_maps(MAP_SPECS, obstacle_ratio=obstacle_ratio, rng=rng)
    classical_maps = apply_classical_mapping(base_maps)
    cyclic_maps = apply_cyclic_mapping(base_maps)

    _clear_terminal_screen()
    _print_context_block(
        selected_map_name=selected_map_name,
        num_agents=num_agents,
        obstacle_ratio=obstacle_ratio,
        max_solver_runtime_seconds=max_solver_runtime_seconds,
        seed=seed,
    )
    shared_agents = sample_agent_start_goal_pairs(
        composite_map=base_maps[selected_map_name],
        num_agents=num_agents,
        rng=rng,
    )

    cyclic_result = run_single_mapf_for_selected_map(
        mapping_name="cyclic",
        mapped_grids=cyclic_maps,
        selected_map_name=selected_map_name,
        num_agents=num_agents,
        seed=None,
        max_solver_runtime_seconds=max_solver_runtime_seconds,
        agents=shared_agents,
        output_root=STATIC_ARTIFICIAL_DIR,
        context_label="[Static | Artificial]",
    )

    if cyclic_result is None:
        return {
            "status": "failed",
            "context": "static_artificial",
            "condition": CONDITION_NAME,
            "selected_map_name": selected_map_name,
            "seed": seed,
            "results": {
                "cyclic": None,
                "classical": None,
            },
        }

    print()
    classical_result = run_single_mapf_for_selected_map(
        mapping_name="classical",
        mapped_grids=classical_maps,
        selected_map_name=selected_map_name,
        num_agents=num_agents,
        seed=None,
        max_solver_runtime_seconds=max_solver_runtime_seconds,
        agents=shared_agents,
        output_root=STATIC_ARTIFICIAL_DIR,
        context_label="[Static | Artificial]",
    )
    return {
        "status": "completed" if classical_result is not None else "failed",
        "context": "static_artificial",
        "condition": CONDITION_NAME,
        "selected_map_name": selected_map_name,
        "seed": seed,
        "results": {
            "cyclic": cyclic_result,
            "classical": classical_result,
        },
    }
