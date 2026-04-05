import random
import shutil
from pathlib import Path

from cyclic_test.mapf.agent_assignment import sample_agent_start_goal_pairs
from cyclic_test.mapf.cbs_solver import solve_mapf_with_cbs
from cyclic_test.mapf.mapf_frame_builder import build_all_frames
from cyclic_test.mapf.mapf_logger import write_mapf_frames
from cyclic_test.mapf.metrics import summarize_mapf_result
from cyclic_test.paths import MAPF_RUNS_DIR


PROGRESS_LOG_INTERVAL_SECONDS = 5


def clear_previous_mapping_run(map_name, mapping_name, output_root=MAPF_RUNS_DIR):
    mapping_output_dir = Path(output_root) / mapping_name / map_name

    if mapping_output_dir.exists():
        shutil.rmtree(mapping_output_dir)

    mapping_output_dir.mkdir(parents=True, exist_ok=True)


def format_path_length(value):
    if value is None:
        return "None"

    if isinstance(value, (int, float)) and float(value).is_integer():
        return str(int(value))

    return f"{value:.2f}"


def print_mapping_header(mapping_name, map_name, num_agents):
    title = f"{mapping_name.upper()} | {map_name}"
    print(f"=== {title} ===")
    print(f"Number of agents: {num_agents}")


def print_mapping_summary(summary):
    if not summary["solved"]:
        print("[Failed]")
        return

    print("[Success]")
    print(f"Number of conflicts detected: {summary['num_conflicts_detected']}")
    print(f"Average path length: {format_path_length(summary['average_path_length'])}")


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
    progress_callback=None,
):
    return solve_mapf_with_cbs(
        composite_map=composite_map,
        agents=agents,
        max_runtime_seconds=max_solver_runtime_seconds,
        progress_callback=progress_callback,
    )


def build_elapsed_time_reporter(interval_seconds=PROGRESS_LOG_INTERVAL_SECONDS):
    def report(elapsed_seconds):
        if elapsed_seconds % interval_seconds == 0:
            print(f"{elapsed_seconds}...")

    return report


def print_bad_setup_message(result):
    status = result["status"]

    if status == "bad_setup_timeout":
        print("[Failed: solver timeout reached]")
    else:
        print("[Failed: assignment not solved]")

    print(f"Number of conflicts detected: {result['num_conflicts_detected']}")


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

    if num_agents is None:
        if agent_density is not None:
            raise ValueError(
                "Agent density is no longer supported. Please provide num_agents instead."
            )
        raise ValueError("num_agents must be provided.")

    clear_previous_mapping_run(map_name=map_name, mapping_name=mapping_name)

    agents = sample_agent_start_goal_pairs(
        composite_map=composite_map,
        num_agents=num_agents,
        rng=rng,
    )

    print_mapping_header(
        mapping_name=mapping_name,
        map_name=map_name,
        num_agents=num_agents,
    )

    result = solve_single_mapf_instance(
        composite_map=composite_map,
        agents=agents,
        max_solver_runtime_seconds=max_solver_runtime_seconds,
        progress_callback=build_elapsed_time_reporter(),
    )

    if result["status"] != "solved":
        print_bad_setup_message(result=result)
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
    print_mapping_summary(summary=summary)

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
