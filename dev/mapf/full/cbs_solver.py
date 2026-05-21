import heapq
import itertools
import time
from typing import Any

from dev.mapf.full.mapf_low_level_astar import find_path_for_agent


DEFAULT_ECBS_SUBOPTIMALITY_FACTOR = 1.5
PROGRESS_REPORT_INTERVAL_SECONDS = 5


# ---------------------------------------------------------------------------
# Small helper functions
# ---------------------------------------------------------------------------


def _resolve_ecbs_suboptimality_factor(suboptimality_factor: float | None) -> float:
    value = DEFAULT_ECBS_SUBOPTIMALITY_FACTOR if suboptimality_factor is None else float(suboptimality_factor)
    if value < 1.0:
        raise ValueError("ECBS suboptimality factor must be greater than or equal to 1.0")
    return value



def get_path_position(path, time_step):
    """
    Return the agent's position at a certain timestep.

    This project uses the disappearing-agent model. This means that after an
    agent reaches the end of its path, it no longer occupies any cell.
    """
    if time_step < len(path):
        return path[time_step]
    return None



def compute_solution_cost(paths_by_agent):
    """
    The cost of one CBS node is the total length of all its current paths.

    Since a path with 4 positions has 3 moves, each path contributes
    len(path) - 1 to the total cost.
    """
    return sum(len(path) - 1 for path in paths_by_agent.values())



def _count_vertex_conflicts_at_time(paths_by_agent, agent_ids, time_step):
    occupied_positions = {}
    num_conflicts = 0

    for agent_id in agent_ids:
        position = get_path_position(paths_by_agent[agent_id], time_step)
        if position is None:
            continue
        occupied_positions.setdefault(position, []).append(agent_id)

    for agents_in_same_position in occupied_positions.values():
        if len(agents_in_same_position) >= 2:
            num_conflicts += len(agents_in_same_position) - 1

    return num_conflicts



def _count_edge_conflicts_at_time(paths_by_agent, agent_ids, time_step):
    moves_seen = {}
    num_conflicts = 0

    for agent_id in agent_ids:
        previous_position = get_path_position(paths_by_agent[agent_id], time_step - 1)
        current_position = get_path_position(paths_by_agent[agent_id], time_step)

        if previous_position is None or current_position is None:
            continue

        current_move = (previous_position, current_position)
        reverse_move = (current_position, previous_position)

        # A swap conflict happens when one agent moves A -> B while another
        # agent moves B -> A during the same timestep.
        if previous_position != current_position and reverse_move in moves_seen:
            num_conflicts += 1

        moves_seen[current_move] = agent_id

    return num_conflicts



def count_all_conflicts(paths_by_agent):
    """
    Count all conflicts in a set of paths.

    Vanilla CBS only needs the first conflict. ECBS additionally uses this
    number as a rough guide: among acceptable nodes, prefer the one that still
    has fewer visible conflicts.
    """
    if not paths_by_agent:
        return 0

    agent_ids = sorted(paths_by_agent.keys())
    max_time = max(len(path) for path in paths_by_agent.values())
    total_conflicts = 0

    for time_step in range(max_time):
        total_conflicts += _count_vertex_conflicts_at_time(paths_by_agent, agent_ids, time_step)

        if time_step > 0:
            total_conflicts += _count_edge_conflicts_at_time(paths_by_agent, agent_ids, time_step)

    return total_conflicts


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


def detect_first_conflict(paths_by_agent):
    """
    Find the first conflict in the current solution.

    This follows the simple CBS explanation:
        If position(agent i, t) == position(agent j, t), there is a conflict.

    This function also checks swap conflicts, where two agents exchange
    positions during the same timestep.
    """
    if not paths_by_agent:
        return None

    agent_ids = sorted(paths_by_agent.keys())
    max_time = max(len(path) for path in paths_by_agent.values())

    for time_step in range(max_time):
        # Check vertex conflicts first.
        # Example: position(A, t=1) == position(B, t=1)
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

        # At t = 0, nobody has moved yet, so no edge/swap conflict can happen.
        if time_step == 0:
            continue

        # Check edge conflicts.
        # Example: A moves X -> Y while B moves Y -> X.
        moves_seen = {}

        for agent_id in agent_ids:
            previous_position = get_path_position(paths_by_agent[agent_id], time_step - 1)
            current_position = get_path_position(paths_by_agent[agent_id], time_step)

            if previous_position is None or current_position is None:
                continue

            current_move = (previous_position, current_position)
            reverse_move = (current_position, previous_position)

            if previous_position != current_position and reverse_move in moves_seen:
                other_agent_id = moves_seen[reverse_move]
                return {
                    "type": "edge",
                    "time": time_step,
                    "agents": (other_agent_id, agent_id),
                    "from_to": current_move,
                    "moves": {
                        other_agent_id: reverse_move,
                        agent_id: current_move,
                    },
                }

            moves_seen[current_move] = agent_id

    return None



def split_conflict_into_constraints(conflict):
    """
    Split one conflict into two possible child constraints.

    In the explanation, this is the part where we split reality into two:
        Child node 1: constrain agent i.
        Child node 2: constrain agent j.
    """
    agent_a, agent_b = conflict["agents"]
    time_step = conflict["time"]

    if conflict["type"] == "vertex":
        position = conflict["position"]
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

    move_a_from, move_a_to = conflict["moves"][agent_a]
    move_b_from, move_b_to = conflict["moves"][agent_b]

    return [
        {
            "agent": agent_a,
            "type": "edge",
            "from": move_a_from,
            "to": move_a_to,
            "time": time_step,
        },
        {
            "agent": agent_b,
            "type": "edge",
            "from": move_b_from,
            "to": move_b_to,
            "time": time_step,
        },
    ]


# ---------------------------------------------------------------------------
# Constraint Tree node handling
# ---------------------------------------------------------------------------


def make_constraint_signature(constraints):
    """
    Convert constraints into a sortable signature.

    This is only used to avoid adding the exact same CT node twice.
    """
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
    """
    Create one node in the Constraint Tree.

    A node stores:
        constraints = rules that some agents must follow
        paths       = current path of every agent under those constraints
        cost        = total path cost, used to choose the next CT leaf
    """
    return {
        "constraints": constraints,
        "paths": paths_by_agent,
        "cost": compute_solution_cost(paths_by_agent),
        "secondary_key": count_all_conflicts(paths_by_agent),
    }



def _agent_lookup(agents):
    return {agent["id"]: agent for agent in agents}



def _replan_static_agent(
    composite_map,
    agent,
    constraints,
    *,
    heuristic_weight,
    true_static_shortest_path_distance=False,
    tight_time_horizon=False,
    agent_cohesion_enabled=False,
    cohesion_reference_paths=None,
):
    """Run the low-level A* search for one agent."""
    return find_path_for_agent(
        cyclic_map=composite_map,
        agent_id=agent["id"],
        start=agent["start"],
        goal=agent["goal"],
        constraints=constraints,
        heuristic_weight=heuristic_weight,
        true_static_shortest_path_distance=true_static_shortest_path_distance,
        tight_time_horizon=tight_time_horizon,
        agent_cohesion_enabled=agent_cohesion_enabled,
        cohesion_reference_paths=cohesion_reference_paths,
    )



def _build_solver_success(
    paths_by_agent,
    num_conflicts_detected,
    num_high_level_nodes_expanded,
    *,
    solver_name,
    solver_suboptimality_factor=None,
    agent_cohesion_enabled=False,
):
    return {
        "status": "solved",
        "paths_by_agent": paths_by_agent,
        "num_conflicts_detected": num_conflicts_detected,
        "num_high_level_nodes_expanded": num_high_level_nodes_expanded,
        "solver_name": solver_name,
        "solver_suboptimality_factor": None if solver_name == "CBS" else solver_suboptimality_factor,
        "agent_cohesion_enabled": bool(agent_cohesion_enabled),
    }



def build_cbs_failure(
    reason,
    num_conflicts_detected,
    num_high_level_nodes_expanded,
    *,
    solver_name,
    solver_suboptimality_factor=None,
    agent_cohesion_enabled=False,
):
    return {
        "status": reason,
        "paths_by_agent": None,
        "num_conflicts_detected": num_conflicts_detected,
        "num_high_level_nodes_expanded": num_high_level_nodes_expanded,
        "solver_name": solver_name,
        "solver_suboptimality_factor": None if solver_name == "CBS" else solver_suboptimality_factor,
        "agent_cohesion_enabled": bool(agent_cohesion_enabled),
    }



def maybe_report_elapsed_time(start_time, next_report_seconds, progress_callback):
    if progress_callback is None:
        return next_report_seconds

    elapsed_seconds = time.perf_counter() - start_time

    while elapsed_seconds >= next_report_seconds:
        progress_callback(next_report_seconds)
        next_report_seconds += PROGRESS_REPORT_INTERVAL_SECONDS

    return next_report_seconds



def _has_reached_runtime_limit(start_time, max_runtime_seconds):
    return time.perf_counter() - start_time > max_runtime_seconds


# ---------------------------------------------------------------------------
# Choosing the next leaf of the Constraint Tree
# ---------------------------------------------------------------------------


def _add_vanilla_leaf_to_OPEN(OPEN, insertion_counter, node):
    """
    In normal CBS, OPEN stores the CT leaves that still need to be checked.
    The next leaf is the one with the least total path cost.
    """
    heapq.heappush(OPEN, (node["cost"], next(insertion_counter), node))



def _select_vanilla_leaf_from_OPEN(OPEN):
    _, _, selected_node = heapq.heappop(OPEN)
    return selected_node



def _clean_ecbs_OPEN(OPEN, active_leaf_nodes):
    """
    ECBS keeps a heap for the best cost, but some nodes may already have been
    removed from the active set. This removes those old heap entries.
    """
    while OPEN and OPEN[0][2] not in active_leaf_nodes:
        heapq.heappop(OPEN)



def _select_ecbs_leaf(active_leaf_nodes: dict[int, dict[str, Any]], best_cost: float, *, suboptimality_factor: float):
    """
    ECBS is like CBS, but it is allowed to choose a node whose cost is within
    a given bound of the current best cost.

    Among those allowed nodes, this implementation chooses the one with fewer
    remaining conflicts. This is the secondary_key of the CBS node.
    """
    cost_bound = suboptimality_factor * best_cost

    eligible_nodes = [
        (node["secondary_key"], node["cost"], node_id, node)
        for node_id, node in active_leaf_nodes.items()
        if node["cost"] <= cost_bound
    ]

    if not eligible_nodes:
        return None, None

    _, _, selected_node_id, selected_node = min(eligible_nodes)
    return selected_node_id, selected_node


# ---------------------------------------------------------------------------
# Main CBS search
# ---------------------------------------------------------------------------


def _solve_mapf_with_cbs_style(
    composite_map,
    agents,
    *,
    max_runtime_seconds,
    progress_callback,
    solver_name,
    heuristic_weight,
    suboptimality_factor=None,
    true_static_shortest_path_distance=False,
    tight_time_horizon=False,
    agent_cohesion_enabled=False,
):
    """
    Run the high-level CBS search.

    The structure intentionally follows the hand explanation:

    1. Create the root node of the Constraint Tree.
       Its constraints are empty, so each agent is planned independently.

    2. Choose a CT leaf and check its paths for a conflict.

    3. If there is a conflict between agents i and j, create two child nodes:
       one constraining i and one constraining j.

    4. Add the valid children back to OPEN and repeat until a conflict-free
       node is selected.
    """
    start_time = time.perf_counter()
    next_report_seconds = PROGRESS_REPORT_INTERVAL_SECONDS
    agents_by_id = _agent_lookup(agents)

    if progress_callback is not None:
        progress_callback(0)

    # Step 1: create Solution 0, the root node of the Constraint Tree.
    root_constraints = []
    root_paths = {}

    for agent in agents:
        next_report_seconds = maybe_report_elapsed_time(
            start_time,
            next_report_seconds,
            progress_callback,
        )

        if _has_reached_runtime_limit(start_time, max_runtime_seconds):
            return build_cbs_failure(
                "bad_setup_timeout",
                0,
                0,
                solver_name=solver_name,
                solver_suboptimality_factor=suboptimality_factor,
                agent_cohesion_enabled=agent_cohesion_enabled,
            )

        path = _replan_static_agent(
            composite_map,
            agent,
            root_constraints,
            heuristic_weight=heuristic_weight,
            true_static_shortest_path_distance=true_static_shortest_path_distance,
            tight_time_horizon=tight_time_horizon,
            agent_cohesion_enabled=agent_cohesion_enabled,
            cohesion_reference_paths=root_paths,
        )

        if path is None:
            return build_cbs_failure(
                "no_solution",
                0,
                0,
                solver_name=solver_name,
                solver_suboptimality_factor=suboptimality_factor,
                agent_cohesion_enabled=agent_cohesion_enabled,
            )

        root_paths[agent["id"]] = path

    root_node = make_cbs_node(root_constraints, root_paths)

    num_conflicts_detected = 0
    num_high_level_nodes_expanded = 0
    visited_constraint_sets = {make_constraint_signature(root_constraints)}

    # In the notes, this is the list of CT leaves waiting to be evaluated.
    OPEN = []
    insertion_counter = itertools.count()

    # ECBS needs a separate active set so that it can choose from a focal list.
    active_leaf_nodes = {}
    ecbs_node_id_counter = itertools.count()

    if solver_name == "ECBS":
        root_node_id = next(ecbs_node_id_counter)
        active_leaf_nodes[root_node_id] = root_node
        heapq.heappush(OPEN, (root_node["cost"], root_node["secondary_key"], root_node_id))
    else:
        _add_vanilla_leaf_to_OPEN(OPEN, insertion_counter, root_node)

    while True:
        if solver_name == "CBS" and not OPEN:
            break
        if solver_name == "ECBS" and not active_leaf_nodes:
            break

        next_report_seconds = maybe_report_elapsed_time(
            start_time,
            next_report_seconds,
            progress_callback,
        )

        if _has_reached_runtime_limit(start_time, max_runtime_seconds):
            return build_cbs_failure(
                "bad_setup_timeout",
                num_conflicts_detected,
                num_high_level_nodes_expanded,
                solver_name=solver_name,
                solver_suboptimality_factor=suboptimality_factor,
                agent_cohesion_enabled=agent_cohesion_enabled,
            )

        # Step 3 in the user's pseudocode:
        # In the Constraint Tree, select the leaf node to evaluate next.
        if solver_name == "ECBS":
            _clean_ecbs_OPEN(OPEN, active_leaf_nodes)
            if not OPEN:
                break

            best_cost = OPEN[0][0]
            selected_node_id, current_node = _select_ecbs_leaf(
                active_leaf_nodes,
                best_cost,
                suboptimality_factor=suboptimality_factor,
            )
            if current_node is None:
                break
            del active_leaf_nodes[selected_node_id]
        else:
            current_node = _select_vanilla_leaf_from_OPEN(OPEN)

        num_high_level_nodes_expanded += 1

        # Step 2 / Step 4: check whether this selected solution has a conflict.
        conflict = detect_first_conflict(current_node["paths"])

        if conflict is None:
            # No conflict means the selected CT node is the answer.
            return _build_solver_success(
                current_node["paths"],
                num_conflicts_detected,
                num_high_level_nodes_expanded,
                solver_name=solver_name,
                solver_suboptimality_factor=suboptimality_factor,
                agent_cohesion_enabled=agent_cohesion_enabled,
            )

        num_conflicts_detected += 1

        # Step 2: split the conflict by creating two child nodes.
        for added_constraint in split_conflict_into_constraints(conflict):
            next_report_seconds = maybe_report_elapsed_time(
                start_time,
                next_report_seconds,
                progress_callback,
            )

            if _has_reached_runtime_limit(start_time, max_runtime_seconds):
                return build_cbs_failure(
                    "bad_setup_timeout",
                    num_conflicts_detected,
                    num_high_level_nodes_expanded,
                    solver_name=solver_name,
                    solver_suboptimality_factor=suboptimality_factor,
                    agent_cohesion_enabled=agent_cohesion_enabled,
                )

            child_constraints = list(current_node["constraints"]) + [added_constraint]
            child_signature = make_constraint_signature(child_constraints)

            if child_signature in visited_constraint_sets:
                continue

            constrained_agent_id = added_constraint["agent"]
            constrained_agent = agents_by_id[constrained_agent_id]

            # Only the newly constrained agent has to replan. The other paths
            # are copied from the parent node.
            new_path = _replan_static_agent(
                composite_map,
                constrained_agent,
                child_constraints,
                heuristic_weight=heuristic_weight,
                true_static_shortest_path_distance=true_static_shortest_path_distance,
                tight_time_horizon=tight_time_horizon,
                agent_cohesion_enabled=agent_cohesion_enabled,
                cohesion_reference_paths=current_node["paths"],
            )

            if new_path is None:
                # This child represents an impossible branch, so skip it.
                continue

            visited_constraint_sets.add(child_signature)
            child_paths = dict(current_node["paths"])
            child_paths[constrained_agent_id] = new_path
            child_node = make_cbs_node(child_constraints, child_paths)

            if solver_name == "ECBS":
                child_node_id = next(ecbs_node_id_counter)
                active_leaf_nodes[child_node_id] = child_node
                heapq.heappush(OPEN, (child_node["cost"], child_node["secondary_key"], child_node_id))
            else:
                _add_vanilla_leaf_to_OPEN(OPEN, insertion_counter, child_node)

    return build_cbs_failure(
        "no_solution",
        num_conflicts_detected,
        num_high_level_nodes_expanded,
        solver_name=solver_name,
        solver_suboptimality_factor=suboptimality_factor,
        agent_cohesion_enabled=agent_cohesion_enabled,
    )



def _solve_mapf_with_vanilla_cbs(
    composite_map,
    agents,
    max_runtime_seconds=10.0,
    progress_callback=None,
    true_static_shortest_path_distance=False,
    tight_time_horizon=False,
    agent_cohesion_enabled=False,
):
    return _solve_mapf_with_cbs_style(
        composite_map,
        agents,
        max_runtime_seconds=max_runtime_seconds,
        progress_callback=progress_callback,
        solver_name="CBS",
        heuristic_weight=1.0,
        true_static_shortest_path_distance=true_static_shortest_path_distance,
        tight_time_horizon=tight_time_horizon,
        agent_cohesion_enabled=agent_cohesion_enabled,
    )



def _solve_mapf_with_ecbs(
    composite_map,
    agents,
    max_runtime_seconds=10.0,
    progress_callback=None,
    suboptimality_factor: float = DEFAULT_ECBS_SUBOPTIMALITY_FACTOR,
    true_static_shortest_path_distance=False,
    tight_time_horizon=False,
    agent_cohesion_enabled=False,
):
    return _solve_mapf_with_cbs_style(
        composite_map,
        agents,
        max_runtime_seconds=max_runtime_seconds,
        progress_callback=progress_callback,
        solver_name="ECBS",
        heuristic_weight=suboptimality_factor,
        suboptimality_factor=suboptimality_factor,
        true_static_shortest_path_distance=true_static_shortest_path_distance,
        tight_time_horizon=tight_time_horizon,
        agent_cohesion_enabled=agent_cohesion_enabled,
    )



def solve_mapf_with_cbs(
    composite_map,
    agents,
    max_runtime_seconds=10.0,
    progress_callback=None,
    use_ecbs=False,
    ecbs_suboptimality_factor: float | None = None,
    true_static_shortest_path_distance=False,
    tight_time_horizon=False,
    agent_cohesion_enabled=False,
):
    """
    Static MAPF entry point.

    use_ecbs=False: run normal CBS.
    use_ecbs=True: run ECBS, which is allowed to choose a near-best CT leaf
    instead of strictly choosing the cheapest one.
    """
    if use_ecbs:
        return _solve_mapf_with_ecbs(
            composite_map=composite_map,
            agents=agents,
            max_runtime_seconds=max_runtime_seconds,
            progress_callback=progress_callback,
            suboptimality_factor=_resolve_ecbs_suboptimality_factor(ecbs_suboptimality_factor),
            true_static_shortest_path_distance=true_static_shortest_path_distance,
            tight_time_horizon=tight_time_horizon,
            agent_cohesion_enabled=agent_cohesion_enabled,
        )

    return _solve_mapf_with_vanilla_cbs(
        composite_map=composite_map,
        agents=agents,
        max_runtime_seconds=max_runtime_seconds,
        progress_callback=progress_callback,
        true_static_shortest_path_distance=true_static_shortest_path_distance,
        tight_time_horizon=tight_time_horizon,
        agent_cohesion_enabled=agent_cohesion_enabled,
    )
