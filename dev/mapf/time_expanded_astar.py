import heapq
import itertools

from dev.navigation.cyclic_grid_navigation import get_outgoing_neighbors


REMOVED = object()


def manhattan_vertex_distance(a, b):
    return (abs(a[0] - b[0]) + abs(a[1] - b[1])) // 2


def get_agent_constraints(constraints, agent_id):
    return [constraint for constraint in constraints if constraint["agent"] == agent_id]


def violates_vertex_constraint(agent_constraints, position, time_step):
    for constraint in agent_constraints:
        if constraint["type"] == "vertex" and constraint["position"] == position and constraint["time"] == time_step:
            return True
    return False


def violates_edge_constraint(agent_constraints, from_position, to_position, time_step):
    for constraint in agent_constraints:
        if constraint["type"] != "edge":
            continue
        if constraint["from"] == from_position and constraint["to"] == to_position and constraint["time"] == time_step:
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


def is_vertex_free_at_time(mapped_loop, position, time_step):
    frame = mapped_loop[time_step % len(mapped_loop)]
    i, j = position
    return frame[i][j].name == "FREE_SPACE"


def get_neighbors_at_time(mapped_loop, position, time_step):
    frame = mapped_loop[time_step % len(mapped_loop)]
    return get_outgoing_neighbors(frame, position)


def find_time_expanded_path_for_agent(mapped_loop, agent_id, start, goal, constraints, heuristic_weight=1.0):
    heuristic_weight = max(1.0, float(heuristic_weight))
    agent_constraints = get_agent_constraints(constraints, agent_id)

    if violates_vertex_constraint(agent_constraints, start, 0):
        return None
    if not is_vertex_free_at_time(mapped_loop, start, 0):
        return None

    latest_constraint_time = get_latest_constraint_time(agent_constraints)
    free_vertices = sum(1 for row in mapped_loop[0] for cell in row if getattr(cell, 'name', None) == 'FREE_SPACE')
    max_time_horizon = max(20, latest_constraint_time + (2 * max(1, free_vertices // 4)))

    start_state = (start, 0)
    open_heap = []
    counter = itertools.count()
    heapq.heappush(open_heap, (manhattan_vertex_distance(start, goal) * heuristic_weight, 0, next(counter), start_state))
    came_from = {start_state: None}
    g_score = {start_state: 0}

    while open_heap:
        _, current_g, _, current_state = heapq.heappop(open_heap)
        current_position, current_time = current_state

        if current_g != g_score.get(current_state):
            continue

        if current_position == goal and current_time >= latest_constraint_time:
            return reconstruct_path(came_from, current_state)

        if current_time >= max_time_horizon:
            continue

        next_time = current_time + 1
        candidate_positions = list(get_neighbors_at_time(mapped_loop, current_position, current_time))
        candidate_positions.append(current_position)

        for next_position in candidate_positions:
            if not is_vertex_free_at_time(mapped_loop, next_position, next_time):
                continue
            if violates_vertex_constraint(agent_constraints, next_position, next_time):
                continue
            if violates_edge_constraint(agent_constraints, current_position, next_position, next_time):
                continue

            next_state = (next_position, next_time)
            tentative_g = current_g + 1
            if tentative_g >= g_score.get(next_state, float('inf')):
                continue

            came_from[next_state] = current_state
            g_score[next_state] = tentative_g
            f_score = tentative_g + (heuristic_weight * manhattan_vertex_distance(next_position, goal))
            heapq.heappush(open_heap, (f_score, tentative_g, next(counter), next_state))

    return None
