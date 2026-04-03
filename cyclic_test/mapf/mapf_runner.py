import random
import shutil
from pathlib import Path

from cyclic_test.mapf.agent_assignment import sample_agent_start_goal_pairs
from cyclic_test.mapf.cbs_solver import solve_mapf_with_cbs
from cyclic_test.mapf.mapf_frame_builder import build_all_frames
from cyclic_test.mapf.mapf_logger import write_mapf_frames


def clear_previous_map_run(map_name, output_root="outputs/mapf_runs"):
    map_output_dir = Path(output_root) / map_name

    if map_output_dir.exists():
        shutil.rmtree(map_output_dir)

    map_output_dir.mkdir(parents=True, exist_ok=True)


def run_single_mapf_for_map(
    map_name,
    cyclic_map,
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

    clear_previous_map_run(map_name)

    for attempt_index in range(1, max_assignment_attempts + 1):
        print(f"[{map_name}] assignment attempt {attempt_index}/{max_assignment_attempts}")

        agents = sample_agent_start_goal_pairs(
            composite_map=cyclic_map,
            num_agents=num_agents,
            rng=rng,
        )

        paths_by_agent = solve_mapf_with_cbs(
            cyclic_map=cyclic_map,
            agents=agents,
        )

        if paths_by_agent is None:
            print(f"[{map_name}] sampled assignment not solved, resampling")
            continue

        frames = build_all_frames(
            cyclic_map=cyclic_map,
            agents=agents,
            paths_by_agent=paths_by_agent,
        )

        write_mapf_frames(
            map_name=map_name,
            frames=frames,
            output_root="outputs/mapf_runs",
        )

        print(f"[{map_name}] solved successfully with {len(frames)} frames")

        return {
            "agents": agents,
            "paths_by_agent": paths_by_agent,
            "frames": frames,
        }

    raise RuntimeError(
        f"Could not find a solvable {num_agents}-agent MAPF assignment for {map_name} "
        f"after {max_assignment_attempts} attempts."
    )


def run_single_mapf_for_selected_map(cyclic_maps, selected_map_name="map_1", num_agents=8, seed=None):
    if selected_map_name not in cyclic_maps:
        raise ValueError(f"Map '{selected_map_name}' not found in cyclic_maps.")

    rng = random.Random(seed)

    print(f"\n=== Running MAPF for {selected_map_name} only ===")

    return run_single_mapf_for_map(
        map_name=selected_map_name,
        cyclic_map=cyclic_maps[selected_map_name],
        num_agents=num_agents,
        rng=rng,
    )