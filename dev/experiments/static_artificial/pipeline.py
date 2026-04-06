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
from dev.paths import STATIC_ARTIFICIAL_DIR


def run_static_artificial_experiment(
    selected_map_name=DEFAULT_SELECTED_MAP_NAME,
    num_agents=DEFAULT_NUM_OF_AGENTS,
    obstacle_ratio=DEFAULT_OBSTACLE_RATIO,
    max_solver_runtime_seconds=DEFAULT_MAX_SOLVER_RUNTIME_SECONDS,
):
    print(f"\n[Static | Artificial map | {CONDITION_NAME}]")

    base_maps = assemble_base_maps(MAP_SPECS, obstacle_ratio=obstacle_ratio)
    classical_maps = apply_classical_mapping(base_maps)
    cyclic_maps = apply_cyclic_mapping(base_maps)

    shared_agents = sample_agent_start_goal_pairs(
        composite_map=base_maps[selected_map_name],
        num_agents=num_agents,
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
    )

    if cyclic_result is None:
        return {"status": "failed", "context": "static_artificial"}

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
    )

    return {
        "status": "completed" if classical_result is not None else "failed",
        "context": "static_artificial",
        "condition": CONDITION_NAME,
        "selected_map_name": selected_map_name,
        "results": {
            "cyclic": cyclic_result,
            "classical": classical_result,
        },
    }
