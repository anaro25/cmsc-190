import random
import shutil
from pathlib import Path

from dev.master_config import BRANCH_USER_CONFIGS, MAP_TYPE, agent_cohesion, enhanced_CBS
from dev.mapf.agent_assignment import sample_agent_start_goal_pairs
from dev.mapf.full.cbs_solver import solve_mapf_with_cbs
from dev.mapf.mapf_logger import (
    write_empty_map_config_frame,
    write_mapf_frames,
    write_setup_frame,
    write_showcase_frame,
)
from dev.mapf.metrics import summarize_mapf_result


PROGRESS_LOG_INTERVAL_SECONDS = 5


def current_ecbs_suboptimality_factor():
    return float(BRANCH_USER_CONFIGS[MAP_TYPE].get("ECBS_suboptimality", 1.5))


def current_true_static_shortest_path_distance_enabled():
    return bool(BRANCH_USER_CONFIGS[MAP_TYPE].get("true_static_shortest_path_distance", False))


def current_tight_time_horizon_enabled():
    return bool(BRANCH_USER_CONFIGS[MAP_TYPE].get("tight_time_horizon", False))


def current_agent_cohesion_enabled():
    return bool(agent_cohesion) and MAP_TYPE in {"static_campus_area_1", "dynamic_campus_area_2"}


def clear_previous_mapping_run(map_name, mapping_name, output_root):
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


def print_mapping_header(mapping_name, context_label):
    title = f"{mapping_name.upper()} | {context_label}"
    print(f"=== {title} ===")


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
    use_ecbs=None,
    ecbs_suboptimality_factor=None,
    true_static_shortest_path_distance=None,
    tight_time_horizon=None,
    agent_cohesion_enabled=None,
):
    return solve_mapf_with_cbs(
        composite_map=composite_map,
        agents=agents,
        max_runtime_seconds=max_solver_runtime_seconds,
        progress_callback=progress_callback,
        use_ecbs=bool(enhanced_CBS) if use_ecbs is None else bool(use_ecbs),
        ecbs_suboptimality_factor=(current_ecbs_suboptimality_factor() if ecbs_suboptimality_factor is None else ecbs_suboptimality_factor),
        true_static_shortest_path_distance=(current_true_static_shortest_path_distance_enabled() if true_static_shortest_path_distance is None else bool(true_static_shortest_path_distance)),
        tight_time_horizon=(current_tight_time_horizon_enabled() if tight_time_horizon is None else bool(tight_time_horizon)),
        agent_cohesion_enabled=(current_agent_cohesion_enabled() if agent_cohesion_enabled is None else bool(agent_cohesion_enabled)),
    )


def build_elapsed_time_reporter(interval_seconds=PROGRESS_LOG_INTERVAL_SECONDS):
    def report(elapsed_seconds):
        if elapsed_seconds > 0 and elapsed_seconds % interval_seconds == 0:
            print(f"{elapsed_seconds}...")

    return report


def print_bad_setup_message(result):
    status = result["status"]

    if status == "bad_setup_timeout":
        print("[Failed: solver timeout reached]")
    elif status == "no_solution":
        print("[Failed: no feasible path for this assignment]")
    else:
        print("[Failed: assignment not solved]")

    print(f"Number of conflicts detected: {result['num_conflicts_detected']}")


def run_single_mapf_for_map(
    map_name,
    mapping_name,
    composite_map,
    output_root,
    num_agents=None,
    agent_density=None,
    rng=None,
    max_solver_runtime_seconds=10.0,
    agents=None,
    context_label=None,
):
    if rng is None:
        rng = random.Random()

    if num_agents is None:
        if agent_density is not None:
            raise ValueError(
                "Agent density is no longer supported. Please provide num_agents instead."
            )
        raise ValueError("num_agents must be provided.")

    clear_previous_mapping_run(
        map_name=map_name,
        mapping_name=mapping_name,
        output_root=output_root,
    )

    mapping_output_root = Path(output_root) / mapping_name

    write_empty_map_config_frame(
        map_name=map_name,
        composite_map=composite_map,
        output_root=mapping_output_root,
    )

    write_showcase_frame(
        map_name=map_name,
        composite_map=composite_map,
        output_root=mapping_output_root,
    )

    if agents is None:
        agents = sample_agent_start_goal_pairs(
            composite_map=composite_map,
            num_agents=num_agents,
            rng=rng,
        )

    write_setup_frame(
        map_name=map_name,
        composite_map=composite_map,
        agents=agents,
        output_root=mapping_output_root,
    )

    print_mapping_header(
        mapping_name=mapping_name,
        context_label=context_label or map_name,
    )
    print("0...")

    result = solve_single_mapf_instance(
        composite_map=composite_map,
        agents=agents,
        max_solver_runtime_seconds=max_solver_runtime_seconds,
        progress_callback=build_elapsed_time_reporter(),
        use_ecbs=bool(enhanced_CBS),
        ecbs_suboptimality_factor=current_ecbs_suboptimality_factor(),
        true_static_shortest_path_distance=current_true_static_shortest_path_distance_enabled(),
        tight_time_horizon=current_tight_time_horizon_enabled(),
        agent_cohesion_enabled=current_agent_cohesion_enabled(),
    )

    if result["status"] != "solved":
        print_bad_setup_message(result=result)
        return None

    rendered_frame_paths = write_mapf_frames(
        map_name=map_name,
        composite_map=composite_map,
        agents=agents,
        paths_by_agent=result["paths_by_agent"],
        output_root=mapping_output_root,
    )

    run_result = build_run_result(
        agents=agents,
        solved_result=result,
        frames=rendered_frame_paths,
    )
    summary = summarize_mapf_result(run_result)
    print_mapping_summary(summary=summary)

    return run_result


def run_single_mapf_for_selected_map(
    mapping_name,
    mapped_grids,
    output_root,
    selected_map_name="map_1",
    num_agents=None,
    agent_density=None,
    seed=None,
    max_solver_runtime_seconds=10.0,
    agents=None,
    context_label=None,
):
    if selected_map_name not in mapped_grids:
        raise ValueError(f"Map '{selected_map_name}' not found in mapped_grids.")

    rng = random.Random(seed)

    return run_single_mapf_for_map(
        map_name=selected_map_name,
        mapping_name=mapping_name,
        composite_map=mapped_grids[selected_map_name],
        output_root=output_root,
        num_agents=num_agents,
        agent_density=agent_density,
        rng=rng,
        max_solver_runtime_seconds=max_solver_runtime_seconds,
        agents=agents,
        context_label=context_label,
    )
