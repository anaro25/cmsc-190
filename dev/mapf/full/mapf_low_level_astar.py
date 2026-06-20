
import heapq
import itertools
from collections.abc import Mapping

from dev.mapf.agent_cohesion import cohesion_penalty
from dev.mapf.low_level_guidance import get_true_static_distances_for_static_map
from dev.navigation.cyclic_grid_navigation import get_all_free_vertices, get_outgoing_neighbors


_STATIC_TIGHT_HORIZON_MAX_SLACK = 64


def manhattan_vertex_distance(a, b):
    """
    h(n) = horizontal distance + vertical distance to the target

    Composite-map vertices are spaced by 2 cells in the stored grid, so we
    divide by 2 to express the distance in movement steps.
    """
    horizontal_distance = abs(a[0] - b[0]) // 2
    vertical_distance = abs(a[1] - b[1]) // 2
    return horizontal_distance + vertical_distance


def get_agent_constraints(constraints, agent_id):
    """Keep only the CBS constraints that apply to this specific agent."""
    return [constraint for constraint in constraints if constraint["agent"] == agent_id]


def violates_vertex_constraint(agent_constraints, position, time_step):
    """
    A vertex constraint says:
        this agent cannot be at this position at this time.
    """
    for constraint in agent_constraints:
        if constraint["type"] != "vertex":
            continue
        if constraint["position"] == position and constraint["time"] == time_step:
            return True
    return False


def violates_edge_constraint(agent_constraints, from_position, to_position, time_step):
    """
    An edge constraint says:
        this agent cannot move from one position to another at this time.

    Here, time_step is the arrival time of the move.
    """
    for constraint in agent_constraints:
        if constraint["type"] != "edge":
            continue
        if (
            constraint["from"] == from_position
            and constraint["to"] == to_position
            and constraint["time"] == time_step
        ):
            return True
    return False


def get_latest_constraint_time(agent_constraints, *, spawn_time=0):
    """
    The disappearing-agent model lets the agent disappear after reaching its goal.
    However, it should not disappear before its own later constraints matter.

    Reference-comparison runs may release an agent after t=0. Constraints before
    the release time are irrelevant because the agent is not yet on the map.
    """
    relevant_constraint_times = [
        int(constraint["time"])
        for constraint in agent_constraints
        if int(constraint["time"]) >= int(spawn_time)
    ]
    if not relevant_constraint_times:
        return int(spawn_time)
    return max([int(spawn_time)] + relevant_constraint_times)


def reconstruct_path(parent_of_node, target_node, *, spawn_time=0):
    """
    Rebuild the path by walking backward from the target node to the start node.

    If ``spawn_time`` is greater than zero, prefix the path with ``None`` so
    list indices remain global timesteps. Conflict detection already treats
    ``None`` as no occupying agent.
    """
    path = []
    current_node = target_node

    while current_node is not None:
        position, _ = current_node
        path.append(position)
        current_node = parent_of_node[current_node]

    path.reverse()
    if spawn_time > 0:
        return [None for _ in range(int(spawn_time))] + path
    return path


def _static_distance_lookup(cyclic_map, goal):
    return get_true_static_distances_for_static_map(cyclic_map, goal)


def _cell_is_free_space(cell):
    return getattr(cell, "name", None) == "FREE_SPACE"


def count_adjacent_free_vertices(cyclic_map, position):
    """Count nearby free vertices without changing directed transition rules."""
    i, j = position
    count = 0
    for di, dj in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        ni = i + di
        nj = j + dj
        if ni < 0 or ni >= len(cyclic_map):
            continue
        if nj < 0 or nj >= len(cyclic_map[ni]):
            continue
        if _cell_is_free_space(cyclic_map[ni][nj]):
            count += 1
    return count


def _find_h_value(position, goal, *, true_static_shortest_path_distance, static_distance_lookup):
    """
    Find h(n), the estimated remaining distance to the goal.

    By default, this is the Manhattan distance. Some experiments can instead
    use the true shortest static distance as a stronger heuristic.
    """
    if true_static_shortest_path_distance:
        return static_distance_lookup.get(position, float("inf"))
    return manhattan_vertex_distance(position, goal)


def _find_f_value(g_value, h_value, heuristic_weight):
    """
    Standard A*:          f(n) = g(n) + h(n)
    Weighted A* / ECBS:   f(n) = g(n) + weight * h(n)

    When heuristic_weight is 1.0, this is the ordinary A* formula.
    """
    return g_value + (heuristic_weight * h_value)


def _add_node_to_OPEN(
    OPEN,
    insertion_counter,
    node,
    g_value,
    h_value,
    heuristic_weight,
    *,
    soft_cohesion_penalty=0.0,
):
    """
    Add a discovered node to OPEN.

    OPEN is implemented as a heap so that Python can quickly get the node with
    the smallest f(n).

    Tie-breaking rule:
        If two nodes have the same f(n), choose the one with the smaller h(n),
        meaning the one that looks closer to the target. If there is still a
        tie, choose the one that entered OPEN earlier.
    """
    f_value = _find_f_value(g_value, h_value, heuristic_weight)
    priority_value = f_value + float(soft_cohesion_penalty)
    heapq.heappush(OPEN, (priority_value, soft_cohesion_penalty, h_value, next(insertion_counter), node))


def _resolve_time_horizon(
    *,
    cyclic_map,
    latest_constraint_time,
    base_goal_distance,
    tight_time_horizon,
):
    """
    A wait action means time can keep increasing forever.
    To keep the search finite, we stop expanding nodes beyond a time limit.
    """
    num_free_vertices = len(get_all_free_vertices(cyclic_map))
    if not tight_time_horizon:
        return max(
            latest_constraint_time,
            (num_free_vertices * 4) + latest_constraint_time + 4,
        )

    slack = max(8, min(_STATIC_TIGHT_HORIZON_MAX_SLACK, max(1, num_free_vertices // 6)))
    return max(20, latest_constraint_time + base_goal_distance + slack)


def find_path_for_agent(
    cyclic_map,
    agent_id,
    start,
    goal,
    constraints,
    heuristic_weight=1.0,
    true_static_shortest_path_distance=False,
    tight_time_horizon=False,
    agent_cohesion_enabled=False,
    cohesion_reference_paths: Mapping[int, list[tuple[int, int]]] | None = None,
    spawn_time: int = 0,
    return_diagnostics: bool = False,
):
    """
    Find one agent's path using A* while respecting CBS constraints.

    The names below intentionally match the A* explanation:
        OPEN          = discovered but unexplored nodes
        CLOSED        = explored nodes
        selected_node = the node chosen from OPEN because it has the least f(n)
        g_score       = recorded distance from the start to a node
        h_value       = estimated distance from a node to the target
        f_value       = g(n) + h(n), or g(n) + weight * h(n)
    """
    heuristic_weight = max(1.0, float(heuristic_weight))
    spawn_time = max(0, int(spawn_time or 0))
    agent_constraints = get_agent_constraints(constraints, agent_id)

    # If the start itself is forbidden at the release/spawn time, no path is possible.
    # If the start itself is forbidden at the release/spawn time, no path is possible.
    if violates_vertex_constraint(agent_constraints, start, spawn_time):
        if return_diagnostics:
            return {"path": None, "num_expanded_nodes": 0}
        return None


    latest_constraint_time = get_latest_constraint_time(agent_constraints, spawn_time=spawn_time)

    # Some experiment settings use a precomputed true distance table.
    static_distance_lookup = {}
    if true_static_shortest_path_distance or tight_time_horizon:
        static_distance_lookup = _static_distance_lookup(cyclic_map, goal)
        start_goal_distance = static_distance_lookup.get(start)
        if start_goal_distance is None:
            if return_diagnostics:
                return {"path": None, "num_expanded_nodes": 0}
            return None
    else:
        start_goal_distance = manhattan_vertex_distance(start, goal)

    max_time_horizon = _resolve_time_horizon(
        cyclic_map=cyclic_map,
        latest_constraint_time=latest_constraint_time,
        base_goal_distance=start_goal_distance,
        tight_time_horizon=tight_time_horizon,
    )

    # Iteration 0 in the hand solution:
    # OPEN initially contains the agent's node, while CLOSED is empty.
    OPEN = []
    CLOSED = set()
    insertion_counter = itertools.count()

    start_node = (start, spawn_time)
    parent_of_node = {start_node: None}
    g_score = {start_node: 0}

    start_h = _find_h_value(
        start,
        goal,
        true_static_shortest_path_distance=true_static_shortest_path_distance,
        static_distance_lookup=static_distance_lookup,
    )
    if start_h == float("inf"):
        if return_diagnostics:
            return {"path": None, "num_expanded_nodes": 0}
        return None

    _add_node_to_OPEN(
        OPEN,
        insertion_counter,
        start_node,
        g_value=0,
        h_value=start_h,
        heuristic_weight=heuristic_weight,
        soft_cohesion_penalty=cohesion_penalty(
            start,
            0,
            reference_paths=cohesion_reference_paths,
            excluded_agent_id=agent_id,
            enabled=agent_cohesion_enabled,
            previous_position=None,
            goal=goal,
            local_free_neighbor_count=count_adjacent_free_vertices(cyclic_map, start),
        ),
    )

    while OPEN:
        # From OPEN, select the node with the least f(n).
        _, _, _, _, selected_node = heapq.heappop(OPEN)

        # The same node can enter OPEN more than once if a better parent is found.
        # If it was already explored, skip the duplicate entry.
        if selected_node in CLOSED:
            continue

        selected_position, selected_time = selected_node
        selected_g = g_score[selected_node]

        # Move the selected node to CLOSED.
        CLOSED.add(selected_node)

        # In A*, we check whether the selected node is the target node.
        # We stop only when the target is selected from OPEN, not merely seen.
        if selected_position == goal and selected_time >= latest_constraint_time:
            final_path = reconstruct_path(parent_of_node, selected_node, spawn_time=spawn_time)
            if return_diagnostics:
                return {"path": final_path, "num_expanded_nodes": len(CLOSED)}
            return final_path

        # Do not keep expanding forever in time.
        if selected_time >= max_time_horizon:
            continue

        next_time = selected_time + 1

        # Add neighbors of the selected node to OPEN.
        # The wait action means the agent may stay on the same position for one timestep.
        neighboring_positions = list(get_outgoing_neighbors(cyclic_map, selected_position))
        neighboring_positions.append(selected_position)

        for neighbor_position in neighboring_positions:
            if violates_vertex_constraint(agent_constraints, neighbor_position, next_time):
                continue

            if violates_edge_constraint(
                agent_constraints,
                selected_position,
                neighbor_position,
                next_time,
            ):
                continue

            # If a true-distance table exists, positions missing from the table
            # cannot reach the goal under the static movement rules.
            if static_distance_lookup:
                static_distance = static_distance_lookup.get(neighbor_position)
                if static_distance is None:
                    continue
            else:
                static_distance = None

            neighbor_node = (neighbor_position, next_time)
            if neighbor_node in CLOSED:
                continue

            # Moving to a neighbor costs 1 timestep.
            tentative_g = selected_g + 1

            # If we already know an equal or better way to reach this node,
            # there is no need to update it.
            if tentative_g >= g_score.get(neighbor_node, float("inf")):
                continue

            parent_of_node[neighbor_node] = selected_node
            g_score[neighbor_node] = tentative_g

            neighbor_h = (
                static_distance
                if true_static_shortest_path_distance and static_distance is not None
                else manhattan_vertex_distance(neighbor_position, goal)
            )

            _add_node_to_OPEN(
                OPEN,
                insertion_counter,
                neighbor_node,
                g_value=tentative_g,
                h_value=neighbor_h,
                heuristic_weight=heuristic_weight,
                soft_cohesion_penalty=cohesion_penalty(
                    neighbor_position,
                    next_time,
                    reference_paths=cohesion_reference_paths,
                    excluded_agent_id=agent_id,
                    enabled=agent_cohesion_enabled,
                    previous_position=selected_position,
                    goal=goal,
                    local_free_neighbor_count=count_adjacent_free_vertices(cyclic_map, neighbor_position),
                ),
            )

    # OPEN became empty, so all reachable possibilities were exhausted.
    if return_diagnostics:
        return {"path": None, "num_expanded_nodes": len(CLOSED)}
    return None