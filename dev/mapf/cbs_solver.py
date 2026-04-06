import heapq
import itertools
import time

from dev.mapf.mapf_low_level_astar import find_path_for_agent


def get_path_position(path, time_step):
    """
    Disappearing-agent model:
        return None after the agent's path ends.
    """
    if time_step < len(path):
        return path[time_step]
    return None


def compute_solution_cost(paths_by_agent):
    return sum(len(path) - 1 for path in paths_by_agent.values())


def detect_first_conflict(paths_by_agent):
    """
    Detects the first conflict in time order.

    Conflict types:
        * vertex conflict
        * edge conflict (swap)

    Disappearing-agent model:
        agents do not occupy any vertex after their final timestep.
    """
    if not paths_by_agent:
        return None

    agent_ids = sorted(paths_by_agent.keys())
    max_time = max(len(path) for path in paths_by_agent.values())

    for time_step in range(max_time):
        occupied_positions = {}

        for agent_id in agent_ids:
            position = get_path_position(paths_by_agent[agent_id], time_step)

            if position is None:
                continue

            if position in occupied_positions:
                other_agent_id = occupied_positions[position]
                return {
                    "type": "vertex",
                    "time": time_step,
                    "position": position,
                    "agents": (other_agent_id, agent_id),
                }

            occupied_positions[position] = agent_id

        if time_step == 0:
            continue

        transitions = {}

        for agent_id in agent_ids:
            prev_position = get_path_position(paths_by_agent[agent_id], time_step - 1)
            current_position = get_path_position(paths_by_agent[agent_id], time_step)

            if prev_position is None or current_position is None:
                continue

            edge = (prev_position, current_position)
            reverse_edge = (current_position, prev_position)

            if reverse_edge in transitions:
                other_agent_id = transitions[reverse_edge]

                # Ignore both agents waiting in place.
                if prev_position != current_position:
                    return {
                        "type": "edge",
                        "time": time_step,
                        "from_to": edge,
                        "agents": (other_agent_id, agent_id),
                    }

            transitions[edge] = agent_id

    return None


def split_conflict_into_constraints(conflict):
    agent_a, agent_b = conflict["agents"]

    if conflict["type"] == "vertex":
        position = conflict["position"]
        time_step = conflict["time"]

        return [
            {
                "agent": agent_a,
                "type": "vertex",
                "position": position,
                "time": time_step,
            },
            {
                "agent": agent_b,
                "type": "vertex",
                "position": position,
                "time": time_step,
            },
        ]

    from_a, to_a = conflict["from_to"]
    time_step = conflict["time"]

    return [
        {
            "agent": agent_a,
            "type": "edge",
            "from": from_a,
            "to": to_a,
            "time": time_step,
        },
        {
            "agent": agent_b,
            "type": "edge",
            "from": to_a,
            "to": from_a,
            "time": time_step,
        },
    ]



def make_constraint_signature(constraints):
    normalized = []

    for constraint in constraints:
        if constraint["type"] == "vertex":
            normalized.append((
                constraint["agent"],
                "vertex",
                constraint["position"],
                constraint["time"],
            ))
        else:
            normalized.append((
                constraint["agent"],
                "edge",
                constraint["from"],
                constraint["to"],
                constraint["time"],
            ))

    return tuple(sorted(normalized))


def make_cbs_node(constraints, paths_by_agent):
    return {
        "constraints": constraints,
        "paths": paths_by_agent,
        "cost": compute_solution_cost(paths_by_agent),
    }


def build_cbs_failure(reason, num_conflicts_detected, num_high_level_nodes_expanded):
    return {
        "status": reason,
        "paths_by_agent": None,
        "num_conflicts_detected": num_conflicts_detected,
        "num_high_level_nodes_expanded": num_high_level_nodes_expanded,
    }


def maybe_report_elapsed_time(start_time, next_report_seconds, progress_callback):
    if progress_callback is None:
        return next_report_seconds

    elapsed_seconds = time.perf_counter() - start_time

    while elapsed_seconds >= next_report_seconds:
        progress_callback(next_report_seconds)
        next_report_seconds += 5

    return next_report_seconds


def solve_mapf_with_cbs(
    composite_map,
    agents,
    max_runtime_seconds=10.0,
    progress_callback=None,
):
    """
    Vanilla CBS for disappearing agents, with practical bad-setup detection.

    A setup is treated as bad when CBS keeps expanding for too long without
    finishing. In that case, return a non-solved status so the caller can skip
    the setup and resample a new assignment.
    """
    start_time = time.perf_counter()
    next_report_seconds = 5
    root_constraints = []
    root_paths = {}

    if progress_callback is not None:
        progress_callback(0)

    for agent in agents:
        next_report_seconds = maybe_report_elapsed_time(
            start_time=start_time,
            next_report_seconds=next_report_seconds,
            progress_callback=progress_callback,
        )

        if time.perf_counter() - start_time > max_runtime_seconds:
            return build_cbs_failure(
                reason="bad_setup_timeout",
                num_conflicts_detected=0,
                num_high_level_nodes_expanded=0,
            )

        path = find_path_for_agent(
            cyclic_map=composite_map,
            agent_id=agent["id"],
            start=agent["start"],
            goal=agent["goal"],
            constraints=root_constraints,
        )

        if path is None:
            return build_cbs_failure(
                reason="no_solution",
                num_conflicts_detected=0,
                num_high_level_nodes_expanded=0,
            )

        root_paths[agent["id"]] = path

    root_node = make_cbs_node(root_constraints, root_paths)
    num_conflicts_detected = 0
    num_high_level_nodes_expanded = 0

    open_heap = []
    counter = itertools.count()
    visited_constraint_sets = {make_constraint_signature(root_constraints)}
    heapq.heappush(open_heap, (root_node["cost"], next(counter), root_node))

    while open_heap:
        next_report_seconds = maybe_report_elapsed_time(
            start_time=start_time,
            next_report_seconds=next_report_seconds,
            progress_callback=progress_callback,
        )

        elapsed_seconds = time.perf_counter() - start_time
        if elapsed_seconds > max_runtime_seconds:
            return build_cbs_failure(
                reason="bad_setup_timeout",
                num_conflicts_detected=num_conflicts_detected,
                num_high_level_nodes_expanded=num_high_level_nodes_expanded,
            )

        _, _, current_node = heapq.heappop(open_heap)
        num_high_level_nodes_expanded += 1

        conflict = detect_first_conflict(current_node["paths"])

        if conflict is None:
            return {
                "status": "solved",
                "paths_by_agent": current_node["paths"],
                "num_conflicts_detected": num_conflicts_detected,
                "num_high_level_nodes_expanded": num_high_level_nodes_expanded,
            }

        num_conflicts_detected += 1

        new_constraints = split_conflict_into_constraints(conflict)

        for added_constraint in new_constraints:
            next_report_seconds = maybe_report_elapsed_time(
                start_time=start_time,
                next_report_seconds=next_report_seconds,
                progress_callback=progress_callback,
            )

            if time.perf_counter() - start_time > max_runtime_seconds:
                return build_cbs_failure(
                    reason="bad_setup_timeout",
                    num_conflicts_detected=num_conflicts_detected,
                    num_high_level_nodes_expanded=num_high_level_nodes_expanded,
                )

            child_constraints = list(current_node["constraints"])
            child_constraints.append(added_constraint)

            child_paths = dict(current_node["paths"])
            constrained_agent_id = added_constraint["agent"]

            agent = next(agent for agent in agents if agent["id"] == constrained_agent_id)

            new_path = find_path_for_agent(
                cyclic_map=composite_map,
                agent_id=agent["id"],
                start=agent["start"],
                goal=agent["goal"],
                constraints=child_constraints,
            )

            if new_path is None:
                continue

            child_signature = make_constraint_signature(child_constraints)
            if child_signature in visited_constraint_sets:
                continue

            visited_constraint_sets.add(child_signature)
            child_paths[constrained_agent_id] = new_path
            child_node = make_cbs_node(child_constraints, child_paths)

            heapq.heappush(
                open_heap,
                (child_node["cost"], next(counter), child_node),
            )

    return build_cbs_failure(
        reason="no_solution",
        num_conflicts_detected=num_conflicts_detected,
        num_high_level_nodes_expanded=num_high_level_nodes_expanded,
    )
