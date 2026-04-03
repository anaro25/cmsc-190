import heapq
import itertools

from cyclic_test.navigation.cyclic_grid_navigation import get_outgoing_neighbors


def manhattan_vertex_distance(a, b):
    """
    Composite-map vertices are spaced by 2 cells.
    Divide by 2 so the heuristic is in timestep units.
    """
    return (abs(a[0] - b[0]) + abs(a[1] - b[1])) // 2


def get_agent_constraints(constraints, agent_id):
    return [constraint for constraint in constraints if constraint["agent"] == agent_id]


def violates_vertex_constraint(agent_constraints, position, time_step):
    for constraint in agent_constraints:
        if constraint["type"] != "vertex":
            continue
        if constraint["position"] == position and constraint["time"] == time_step:
            return True
    return False


def violates_edge_constraint(agent_constraints, from_position, to_position, time_step):
    """
    time_step is the arrival time of the move.
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


def get_latest_constraint_time(agent_constraints):
    if not agent_constraints:
        return 0
    return max(constraint["time"] for constraint in agent_constraints)


def reconstruct_path(came_from, end_state):
    path = []
    current_state = end_state

    while current_state is not None:
        position, _ = current_state
        path.append(position)
        current_state = came_from[current_state]

    path.reverse()
    return path


def find_path_for_agent(cyclic_map, agent_id, start, goal, constraints):
    """
    Low-level A* for CBS.

    State:
        (vertex_position, time_step)

    Actions:
        * move to reachable directed neighbor
        * wait in place

    Disappearing-agent model:
        Once the agent reaches its goal and satisfies all of its own
        time-indexed constraints up to that point, the path ends there.
        The agent is considered absent afterward.
    """
    agent_constraints = get_agent_constraints(constraints, agent_id)

    if violates_vertex_constraint(agent_constraints, start, 0):
        return None

    latest_constraint_time = get_latest_constraint_time(agent_constraints)

    open_heap = []
    counter = itertools.count()

    start_state = (start, 0)
    came_from = {start_state: None}
    best_g = {start_state: 0}

    start_f = manhattan_vertex_distance(start, goal)
    heapq.heappush(open_heap, (start_f, 0, next(counter), start_state))

    while open_heap:
        _, current_g, _, current_state = heapq.heappop(open_heap)
        current_position, current_time = current_state

        if current_position == goal and current_time >= latest_constraint_time:
            return reconstruct_path(came_from, current_state)

        next_time = current_time + 1

        candidate_positions = list(get_outgoing_neighbors(cyclic_map, current_position))
        candidate_positions.append(current_position)  # wait action

        for next_position in candidate_positions:
            if violates_vertex_constraint(agent_constraints, next_position, next_time):
                continue

            if violates_edge_constraint(
                agent_constraints,
                current_position,
                next_position,
                next_time,
            ):
                continue

            next_state = (next_position, next_time)
            tentative_g = current_g + 1

            if tentative_g >= best_g.get(next_state, float("inf")):
                continue

            best_g[next_state] = tentative_g
            came_from[next_state] = current_state

            h_value = manhattan_vertex_distance(next_position, goal)
            f_value = tentative_g + h_value

            heapq.heappush(
                open_heap,
                (f_value, tentative_g, next(counter), next_state),
            )

    return None