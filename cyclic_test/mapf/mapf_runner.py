import random
import shutil
from pathlib import Path

from cyclic_test.mapf.agent_assignment import sample_agent_start_goal_pairs
from cyclic_test.mapf.cbs_solver import solve_mapf_with_cbs
from cyclic_test.mapf.mapf_frame_builder import build_all_frames
from cyclic_test.mapf.mapf_logger import write_mapf_frames
from cyclic_test.mapf.metrics import summarize_mapf_result


def clear_previous_mapping_run(map_name, mapping_name, output_root="outputs/mapf_runs"):
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

    print(f"Number of conflicts detected: {summary['num_conflicts_detected']}")
    print(f"Total path length: {summary['total_path_length']}")


def build_run_result(agents, solved_result, frames):
    return {
        "agents": agents,
        "paths_by_agent": solved_result["paths_by_agent"],
        "frames": frames,
        "num_conflicts_detected": solved_result["num_conflicts_detected"],
    }


def solve_single_mapf_instance(composite_map, agents):
    return solve_mapf_with_cbs(
        composite_map=composite_map,
        agents=agents,
    )


def run_single_mapf_for_map(
    map_name,
    mapping_name,
    composite_map,
    num_agents=8,
    rng=None,
    max_assignment_attempts=200,
):
    """
    Repeatedly samples random assignments until one solvable MAPF instance is found.
    CBS itself remains vanilla and unbudgeted.
    """
    if rng is None:
        rng = random.Random()

    clear_previous_mapping_run(map_name=map_name, mapping_name=mapping_name)

    for attempt_index in range(1, max_assignment_attempts + 1):
        print(
            f"[{mapping_name} | {map_name}] assignment attempt "
            f"{attempt_index}/{max_assignment_attempts}"
        )

        agents = sample_agent_start_goal_pairs(
            composite_map=composite_map,
            num_agents=num_agents,
            rng=rng,
        )

        result = solve_single_mapf_instance(
            composite_map=composite_map,
            agents=agents,
        )

        if result is None:
            print(f"[{mapping_name} | {map_name}] sampled assignment not solved, resampling")
            continue

        frames = build_all_frames(
            cyclic_map=composite_map,
            agents=agents,
            paths_by_agent=result["paths_by_agent"],
        )

        write_mapf_frames(
            map_name=map_name,
            frames=frames,
            output_root=f"outputs/mapf_runs/{mapping_name}",
        )

        run_result = build_run_result(agents=agents, solved_result=result, frames=frames)
        summary = summarize_mapf_result(run_result)
        print_mapping_summary(mapping_name=mapping_name, map_name=map_name, summary=summary)

        return run_result

    raise RuntimeError(
        f"Could not find a solvable {num_agents}-agent MAPF assignment for "
        f"{mapping_name}/{map_name} after {max_assignment_attempts} attempts."
    )


def run_single_mapf_for_selected_map(mapping_name, mapped_grids, selected_map_name="map_1", num_agents=8, seed=None):
    if selected_map_name not in mapped_grids:
        raise ValueError(f"Map '{selected_map_name}' not found in mapped_grids.")

    rng = random.Random(seed)

    return run_single_mapf_for_map(
        map_name=selected_map_name,
        mapping_name=mapping_name,
        composite_map=mapped_grids[selected_map_name],
        num_agents=num_agents,
        rng=rng,
    )
