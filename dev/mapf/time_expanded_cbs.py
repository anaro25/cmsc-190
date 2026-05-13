import heapq
import itertools
import time
from typing import Any

from dev.mapf.time_expanded_astar import find_time_expanded_path_for_agent


DEFAULT_ECBS_SUBOPTIMALITY_FACTOR = 1.5


def _resolve_ecbs_suboptimality_factor(suboptimality_factor: float | None) -> float:
    value = DEFAULT_ECBS_SUBOPTIMALITY_FACTOR if suboptimality_factor is None else float(suboptimality_factor)
    if value < 1.0:
        raise ValueError("ECBS suboptimality factor must be greater than or equal to 1.0")
    return value


def get_path_position(path, time_step):
    if time_step < len(path):
        return path[time_step]
    return None


def compute_solution_cost(paths_by_agent):
    return sum(len(path) - 1 for path in paths_by_agent.values())


def detect_first_conflict(paths_by_agent):
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

    return None


def count_all_conflicts(paths_by_agent):
    if not paths_by_agent:
        return 0

    agent_ids = sorted(paths_by_agent.keys())
    max_time = max(len(path) for path in paths_by_agent.values())
    total_conflicts = 0

    for time_step in range(max_time):
        occupied_positions = {}
        for agent_id in agent_ids:
            position = get_path_position(paths_by_agent[agent_id], time_step)
            if position is None:
                continue
            occupied_positions.setdefault(position, []).append(agent_id)

        for occupants in occupied_positions.values():
            if len(occupants) >= 2:
                total_conflicts += len(occupants) - 1

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
            if reverse_edge in transitions and prev_position != current_position:
                total_conflicts += 1
            transitions[edge] = agent_id

    return total_conflicts


def split_conflict_into_constraints(conflict):
    agent_a, agent_b = conflict["agents"]
    if conflict["type"] == "vertex":
        position = conflict["position"]
        time_step = conflict["time"]
        return [
            {"agent": agent_a, "type": "vertex", "position": position, "time": time_step},
            {"agent": agent_b, "type": "vertex", "position": position, "time": time_step},
        ]

    from_a, to_a = conflict["from_to"]
    time_step = conflict["time"]
    return [
        {"agent": agent_a, "type": "edge", "from": from_a, "to": to_a, "time": time_step},
        {"agent": agent_b, "type": "edge", "from": to_a, "to": from_a, "time": time_step},
    ]


def make_constraint_signature(constraints):
    normalized = []
    for constraint in constraints:
        if constraint["type"] == "vertex":
            normalized.append((constraint["agent"], "vertex", constraint["position"], constraint["time"]))
        else:
            normalized.append((constraint["agent"], "edge", constraint["from"], constraint["to"], constraint["time"]))
    return tuple(sorted(normalized))


def make_cbs_node(constraints, paths_by_agent):
    return {
        "constraints": constraints,
        "paths": paths_by_agent,
        "cost": compute_solution_cost(paths_by_agent),
        "secondary_key": count_all_conflicts(paths_by_agent),
    }


def build_failure(reason, num_conflicts_detected, num_high_level_nodes_expanded, *, solver_name, solver_suboptimality_factor=None):
    return {
        "status": reason,
        "paths_by_agent": None,
        "num_conflicts_detected": num_conflicts_detected,
        "num_high_level_nodes_expanded": num_high_level_nodes_expanded,
        "solver_name": solver_name,
        "solver_suboptimality_factor": None if solver_name == "CBS" else solver_suboptimality_factor,
    }


def maybe_report_elapsed_time(start_time, next_report_seconds, progress_callback):
    if progress_callback is None:
        return next_report_seconds
    elapsed_seconds = time.perf_counter() - start_time
    while elapsed_seconds >= next_report_seconds:
        progress_callback(next_report_seconds)
        next_report_seconds += 5
    return next_report_seconds


def _build_solver_success(paths_by_agent, num_conflicts_detected, num_high_level_nodes_expanded, *, solver_name, solver_suboptimality_factor=None):
    return {
        "status": "solved",
        "paths_by_agent": paths_by_agent,
        "num_conflicts_detected": num_conflicts_detected,
        "num_high_level_nodes_expanded": num_high_level_nodes_expanded,
        "solver_name": solver_name,
        "solver_suboptimality_factor": None if solver_name == "CBS" else solver_suboptimality_factor,
    }


def _replan_dynamic_agent(
    mapped_loop,
    agent,
    constraints,
    *,
    heuristic_weight,
    true_static_shortest_path_distance=False,
    tight_time_horizon=False,
):
    return find_time_expanded_path_for_agent(
        mapped_loop=mapped_loop,
        agent_id=agent["id"],
        start=agent["start"],
        goal=agent["goal"],
        constraints=constraints,
        heuristic_weight=heuristic_weight,
        true_static_shortest_path_distance=true_static_shortest_path_distance,
        tight_time_horizon=tight_time_horizon,
    )


def _solve_time_expanded_with_vanilla_cbs(
    mapped_loop,
    agents,
    max_runtime_seconds=10.0,
    progress_callback=None,
    true_static_shortest_path_distance=False,
    tight_time_horizon=False,
):
    start_time = time.perf_counter()
    next_report_seconds = 5
    root_constraints = []
    root_paths = {}
    agents_by_id = {agent["id"]: agent for agent in agents}

    if progress_callback is not None:
        progress_callback(0)

    for agent in agents:
        next_report_seconds = maybe_report_elapsed_time(start_time, next_report_seconds, progress_callback)
        if time.perf_counter() - start_time > max_runtime_seconds:
            return build_failure("bad_setup_timeout", 0, 0, solver_name="CBS")

        path = _replan_dynamic_agent(
            mapped_loop,
            agent,
            root_constraints,
            heuristic_weight=1.0,
            true_static_shortest_path_distance=true_static_shortest_path_distance,
            tight_time_horizon=tight_time_horizon,
        )
        if path is None:
            return build_failure("no_solution", 0, 0, solver_name="CBS")
        root_paths[agent["id"]] = path

    open_heap = []
    counter = itertools.count()
    root = make_cbs_node(root_constraints, root_paths)
    heapq.heappush(open_heap, (root["cost"], next(counter), root))
    visited = {make_constraint_signature(root_constraints)}
    num_conflicts_detected = 0
    num_high_level_nodes_expanded = 0

    while open_heap:
        next_report_seconds = maybe_report_elapsed_time(start_time, next_report_seconds, progress_callback)
        if time.perf_counter() - start_time > max_runtime_seconds:
            return build_failure("bad_setup_timeout", num_conflicts_detected, num_high_level_nodes_expanded, solver_name="CBS")

        _, _, node = heapq.heappop(open_heap)
        num_high_level_nodes_expanded += 1

        conflict = detect_first_conflict(node["paths"])
        if conflict is None:
            return _build_solver_success(node["paths"], num_conflicts_detected, num_high_level_nodes_expanded, solver_name="CBS")

        num_conflicts_detected += 1
        for new_constraint in split_conflict_into_constraints(conflict):
            child_constraints = list(node["constraints"]) + [new_constraint]
            signature = make_constraint_signature(child_constraints)
            if signature in visited:
                continue

            child_paths = dict(node["paths"])
            agent_id = new_constraint["agent"]
            replanned_path = _replan_dynamic_agent(
                mapped_loop,
                agents_by_id[agent_id],
                child_constraints,
                heuristic_weight=1.0,
                true_static_shortest_path_distance=true_static_shortest_path_distance,
                tight_time_horizon=tight_time_horizon,
            )
            if replanned_path is None:
                continue
            visited.add(signature)
            child_paths[agent_id] = replanned_path
            child = make_cbs_node(child_constraints, child_paths)
            heapq.heappush(open_heap, (child["cost"], next(counter), child))

    return build_failure("no_solution", num_conflicts_detected, num_high_level_nodes_expanded, solver_name="CBS")


def _clean_open_heap(open_heap, active_nodes):
    while open_heap and open_heap[0][2] not in active_nodes:
        heapq.heappop(open_heap)


def _select_focal_node(active_nodes: dict[int, dict[str, Any]], best_cost: float, *, suboptimality_factor: float):
    cost_bound = suboptimality_factor * best_cost
    eligible = [
        (node["secondary_key"], node["cost"], node_id, node)
        for node_id, node in active_nodes.items()
        if node["cost"] <= cost_bound
    ]
    if not eligible:
        return None, None
    _, _, node_id, node = min(eligible)
    return node_id, node


def _solve_time_expanded_with_ecbs(
    mapped_loop,
    agents,
    max_runtime_seconds=10.0,
    progress_callback=None,
    suboptimality_factor: float = DEFAULT_ECBS_SUBOPTIMALITY_FACTOR,
    true_static_shortest_path_distance=False,
    tight_time_horizon=False,
):
    start_time = time.perf_counter()
    next_report_seconds = 5
    root_constraints = []
    root_paths = {}
    agents_by_id = {agent["id"]: agent for agent in agents}

    if progress_callback is not None:
        progress_callback(0)

    for agent in agents:
        next_report_seconds = maybe_report_elapsed_time(start_time, next_report_seconds, progress_callback)
        if time.perf_counter() - start_time > max_runtime_seconds:
            return build_failure("bad_setup_timeout", 0, 0, solver_name="ECBS", solver_suboptimality_factor=suboptimality_factor)

        path = _replan_dynamic_agent(
            mapped_loop,
            agent,
            root_constraints,
            heuristic_weight=suboptimality_factor,
            true_static_shortest_path_distance=true_static_shortest_path_distance,
            tight_time_horizon=tight_time_horizon,
        )
        if path is None:
            return build_failure("no_solution", 0, 0, solver_name="ECBS", solver_suboptimality_factor=suboptimality_factor)
        root_paths[agent["id"]] = path

    root = make_cbs_node(root_constraints, root_paths)
    open_heap = []
    active_nodes = {}
    node_id_counter = itertools.count()
    visited = {make_constraint_signature(root_constraints)}
    num_conflicts_detected = 0
    num_high_level_nodes_expanded = 0

    root_node_id = next(node_id_counter)
    active_nodes[root_node_id] = root
    heapq.heappush(open_heap, (root["cost"], root["secondary_key"], root_node_id))

    while active_nodes:
        next_report_seconds = maybe_report_elapsed_time(start_time, next_report_seconds, progress_callback)
        if time.perf_counter() - start_time > max_runtime_seconds:
            return build_failure("bad_setup_timeout", num_conflicts_detected, num_high_level_nodes_expanded, solver_name="ECBS", solver_suboptimality_factor=suboptimality_factor)

        _clean_open_heap(open_heap, active_nodes)
        if not open_heap:
            break

        best_cost = open_heap[0][0]
        selected_node_id, node = _select_focal_node(active_nodes, best_cost, suboptimality_factor=suboptimality_factor)
        if node is None:
            break
        del active_nodes[selected_node_id]
        num_high_level_nodes_expanded += 1

        conflict = detect_first_conflict(node["paths"])
        if conflict is None:
            return _build_solver_success(node["paths"], num_conflicts_detected, num_high_level_nodes_expanded, solver_name="ECBS", solver_suboptimality_factor=suboptimality_factor)

        num_conflicts_detected += 1
        for new_constraint in split_conflict_into_constraints(conflict):
            next_report_seconds = maybe_report_elapsed_time(start_time, next_report_seconds, progress_callback)
            if time.perf_counter() - start_time > max_runtime_seconds:
                return build_failure("bad_setup_timeout", num_conflicts_detected, num_high_level_nodes_expanded, solver_name="ECBS", solver_suboptimality_factor=suboptimality_factor)

            child_constraints = list(node["constraints"]) + [new_constraint]
            signature = make_constraint_signature(child_constraints)
            if signature in visited:
                continue

            child_paths = dict(node["paths"])
            agent_id = new_constraint["agent"]
            replanned_path = _replan_dynamic_agent(
                mapped_loop,
                agents_by_id[agent_id],
                child_constraints,
                heuristic_weight=suboptimality_factor,
                true_static_shortest_path_distance=true_static_shortest_path_distance,
                tight_time_horizon=tight_time_horizon,
            )
            if replanned_path is None:
                continue
            visited.add(signature)
            child_paths[agent_id] = replanned_path
            child = make_cbs_node(child_constraints, child_paths)
            child_node_id = next(node_id_counter)
            active_nodes[child_node_id] = child
            heapq.heappush(open_heap, (child["cost"], child["secondary_key"], child_node_id))

    return build_failure("no_solution", num_conflicts_detected, num_high_level_nodes_expanded, solver_name="ECBS", solver_suboptimality_factor=suboptimality_factor)


def solve_time_expanded_mapf_with_cbs(
    mapped_loop,
    agents,
    max_runtime_seconds=10.0,
    progress_callback=None,
    use_ecbs=False,
    ecbs_suboptimality_factor: float | None = None,
    true_static_shortest_path_distance=False,
    tight_time_horizon=False,
):
    if use_ecbs:
        return _solve_time_expanded_with_ecbs(
            mapped_loop=mapped_loop,
            agents=agents,
            max_runtime_seconds=max_runtime_seconds,
            progress_callback=progress_callback,
            suboptimality_factor=_resolve_ecbs_suboptimality_factor(ecbs_suboptimality_factor),
            true_static_shortest_path_distance=true_static_shortest_path_distance,
            tight_time_horizon=tight_time_horizon,
        )
    return _solve_time_expanded_with_vanilla_cbs(
        mapped_loop=mapped_loop,
        agents=agents,
        max_runtime_seconds=max_runtime_seconds,
        progress_callback=progress_callback,
        true_static_shortest_path_distance=true_static_shortest_path_distance,
        tight_time_horizon=tight_time_horizon,
    )
