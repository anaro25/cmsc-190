import random
import shutil
from pathlib import Path

from cyclic_test.mapf.agent_assignment import (
    compute_num_agents_from_density,
    sample_agent_start_goal_pairs,
)
from cyclic_test.mapf.cbs_solver import solve_mapf_with_cbs
from cyclic_test.mapf.mapf_frame_builder import build_all_frames
from cyclic_test.mapf.mapf_logger import write_mapf_frames
from cyclic_test.mapf.metrics import summarize_mapf_result
from cyclic_test.paths import MAPF_RUNS_DIR


def clear_previous_mapping_run(map_name, mapping_name, output_root=MAPF_RUNS_DIR):
    mapping_output_dir = Path(output_root) / mapping_name / map_name

    if mapping_output_dir.exists():
        shutil.rmtree(mapping_output_dir)

    mapping_output_dir.mkdir(parents=True, exist_ok=True)


def print_mapping_summary(mapping_name, map_name, summary):
    title = f"{mapping_name.upper()} | {map_name}"
    print(f"\n=== {title} ===")

    if not summary["solved"]:
        print("Status: not solved")
        return

    print(f"Number of agents: {summary['num_agents']}")
    print(f"Number of conflicts detected: {summary['num_conflicts_detected']}")
    print(f"Total path length: {summary['total_path_length']}")


def build_run_result(agents, solved_result, frames):
    return {
        "agents": agents,
        "paths_by_agent": solved_result["paths_by_agent"],
        "frames": frames,
        "num_conflicts_detected": solved_result["num_conflicts_detected"],
        "num_high_level_nodes_expanded": solved_result["num_high_level_nodes_expanded"],
    }


def solve_single_mapf_instance(
    composite_map,
    agents,
    max_solver_runtime_seconds=10.0,
):
    return solve_mapf_with_cbs(
        composite_map=composite_map,
        agents=agents,
        max_runtime_seconds=max_solver_runtime_seconds,
    )


def print_bad_setup_message(mapping_name, map_name, result):
    status = result["status"]
    conflicts = result["num_conflicts_detected"]
    expanded = result["num_high_level_nodes_expanded"]

    if status == "bad_setup_timeout":
        reason_text = "solver timeout has been reached"
    else:
        reason_text = "assignment not solved"

    print(
        f"[{mapping_name} | {map_name}] {reason_text} "
        f"| conflicts_seen={conflicts} | high_level_nodes={expanded}"
    )


def run_single_mapf_for_map(
    map_name,
    mapping_name,
    composite_map,
    num_agents=None,
    agent_density=None,
    rng=None,
    max_solver_runtime_seconds=10.0,
):
    """
    Samples one random assignment and attempts one CBS solve.

    If the solver times out or fails, the program reports it and stops for this
    mapping run. The user can manually restart the whole program for another
    random setup.
    """
    if rng is None:
        rng = random.Random()

    if agent_density is not None:
        num_agents = compute_num_agents_from_density(
            composite_map=composite_map,
            density=agent_density,
        )
    elif num_agents is None:
        raise ValueError("Either num_agents or agent_density must be provided.")

    clear_previous_mapping_run(map_name=map_name, mapping_name=mapping_name)

    agents = sample_agent_start_goal_pairs(
        composite_map=composite_map,
        num_agents=num_agents,
        rng=rng,
    )

    result = solve_single_mapf_instance(
        composite_map=composite_map,
        agents=agents,
        max_solver_runtime_seconds=max_solver_runtime_seconds,
    )

    if result["status"] != "solved":
        print_bad_setup_message(
            mapping_name=mapping_name,
            map_name=map_name,
            result=result,
        )
        return None

    frames = build_all_frames(
        cyclic_map=composite_map,
        agents=agents,
        paths_by_agent=result["paths_by_agent"],
    )

    write_mapf_frames(
        map_name=map_name,
        frames=frames,
        output_root=MAPF_RUNS_DIR / mapping_name,
    )

    run_result = build_run_result(agents=agents, solved_result=result, frames=frames)
    summary = summarize_mapf_result(run_result)
    print_mapping_summary(mapping_name=mapping_name, map_name=map_name, summary=summary)

    return run_result


def run_single_mapf_for_selected_map(
    mapping_name,
    mapped_grids,
    selected_map_name="map_1",
    num_agents=None,
    agent_density=None,
    seed=None,
    max_solver_runtime_seconds=10.0,
):
    if selected_map_name not in mapped_grids:
        raise ValueError(f"Map '{selected_map_name}' not found in mapped_grids.")

    rng = random.Random(seed)

    return run_single_mapf_for_map(
        map_name=selected_map_name,
        mapping_name=mapping_name,
        composite_map=mapped_grids[selected_map_name],
        num_agents=num_agents,
        agent_density=agent_density,
        rng=rng,
        max_solver_runtime_seconds=max_solver_runtime_seconds,
    )
