import random

from agent_assignment import sample_agent_start_goal_pairs
from cbs_solver import solve_mapf_with_cbs
from mapf_frame_builder import build_all_frames
from mapf_logger import write_mapf_frames


def run_single_mapf_for_map(
    map_name,
    cyclic_map,
    num_agents=8,
    rng=None,
    max_assignment_attempts=200,
):
    if rng is None:
        rng = random.Random()

    for _ in range(max_assignment_attempts):
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
            continue

        frames = build_all_frames(
            cyclic_map=cyclic_map,
            agents=agents,
            paths_by_agent=paths_by_agent,
        )

        write_mapf_frames(
            map_name=map_name,
            frames=frames,
            output_root="mapf_runs",
        )

        return {
            "agents": agents,
            "paths_by_agent": paths_by_agent,
            "frames": frames,
        }

    raise RuntimeError(
        f"Could not find a solvable 8-agent MAPF assignment for {map_name} "
        f"after {max_assignment_attempts} attempts."
    )


def run_single_mapf_for_all_maps(cyclic_maps, num_agents=8, seed=None):
    rng = random.Random(seed)
    results = {}

    for map_name, cyclic_map in cyclic_maps.items():
        results[map_name] = run_single_mapf_for_map(
            map_name=map_name,
            cyclic_map=cyclic_map,
            num_agents=num_agents,
            rng=rng,
        )

    return results