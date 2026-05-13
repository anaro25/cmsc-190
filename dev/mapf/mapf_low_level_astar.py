import heapq
import itertools

from dev.mapf.low_level_guidance import get_true_static_distances_for_static_map
from dev.navigation.cyclic_grid_navigation import get_all_free_vertices, get_outgoing_neighbors


_STATIC_TIGHT_HORIZON_MAX_SLACK = 64


class AStarNode:
    def __init__(self, position, time_step, g=0, h=0.0, parent=None):
        self.position = position
        self.time_step = time_step
        self.g = g
        self.h = h
        self.f = g + h
        self.parent = parent

    @property
    def state(self):
        return (self.position, self.time_step)


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


def reconstruct_path(end_node: AStarNode):
    path = []
    current = end_node
    while current is not None:
        path.append(current.position)
        current = current.parent

    path.reverse()
    return path


def _static_distance_lookup(cyclic_map, goal):
    return get_true_static_distances_for_static_map(cyclic_map, goal)


def _heuristic_value(position, goal, *, true_static_shortest_path_distance, static_distance_lookup):
    if true_static_shortest_path_distance:
        return static_distance_lookup.get(position, float("inf"))
    return manhattan_vertex_distance(position, goal)


def _resolve_time_horizon(
    *,
    cyclic_map,
    latest_constraint_time,
    base_goal_distance,
    tight_time_horizon,
):
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
):
    """
    Low-level A* for CBS / ECBS.

    State:
        (vertex_position, time_step)

    Actions:
        * move to reachable directed neighbor
        * wait in place

    Disappearing-agent model:
        Once the agent reaches its goal and satisfies all of its own
        time-indexed constraints up to that point, the path ends there.
        The agent is considered absent afterward.

    Important practical bound:
        Because a wait action exists, unbounded time would create infinitely
        many distinct states at the same vertex. We therefore cap the search
        horizon to a conservative finite value based on map size plus the
        latest relevant constraint time, or to a tighter distance-aware bound
        when tight_time_horizon=True.
    """
    heuristic_weight = max(1.0, float(heuristic_weight))
    agent_constraints = get_agent_constraints(constraints, agent_id)

    if violates_vertex_constraint(agent_constraints, start, 0):
        return None

    latest_constraint_time = get_latest_constraint_time(agent_constraints)
    static_distance_lookup = {}
    if true_static_shortest_path_distance or tight_time_horizon:
        static_distance_lookup = _static_distance_lookup(cyclic_map, goal)
        start_goal_distance = static_distance_lookup.get(start)
        if start_goal_distance is None:
            return None
    else:
        start_goal_distance = manhattan_vertex_distance(start, goal)

    max_time_horizon = _resolve_time_horizon(
        cyclic_map=cyclic_map,
        latest_constraint_time=latest_constraint_time,
        base_goal_distance=start_goal_distance,
        tight_time_horizon=tight_time_horizon,
    )

    open_heap = []
    counter = itertools.count()
    closed_states = set()
    best_g = {}
    start_h = _heuristic_value(
        start,
        goal,
        true_static_shortest_path_distance=true_static_shortest_path_distance,
        static_distance_lookup=static_distance_lookup,
    )
    if start_h == float("inf"):
        return None
    start_node = AStarNode(
        position=start,
        time_step=0,
        g=0,
        h=(heuristic_weight * start_h),
        parent=None,
    )
    best_g[start_node.state] = 0
    heapq.heappush(open_heap, (start_node.f, next(counter), start_node))

    while open_heap:
        _, _, current_node = heapq.heappop(open_heap)
        current_state = current_node.state
        current_position, current_time = current_state
        current_g = current_node.g

        if current_g != best_g.get(current_state):
            continue
        if current_state in closed_states:
            continue
        closed_states.add(current_state)

        if current_position == goal and current_time >= latest_constraint_time:
            return reconstruct_path(current_node)

        if current_time >= max_time_horizon:
            continue

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

            if static_distance_lookup:
                static_distance = static_distance_lookup.get(next_position)
                if static_distance is None:
                    continue
            else:
                static_distance = None

            next_state = (next_position, next_time)
            tentative_g = current_g + 1

            if tentative_g >= best_g.get(next_state, float("inf")):
                continue

            best_g[next_state] = tentative_g
            h_value = (
                static_distance
                if true_static_shortest_path_distance and static_distance is not None
                else manhattan_vertex_distance(next_position, goal)
            )
            next_node = AStarNode(
                position=next_position,
                time_step=next_time,
                g=tentative_g,
                h=(heuristic_weight * h_value),
                parent=current_node,
            )

            heapq.heappush(
                open_heap,
                (next_node.f, next(counter), next_node),
            )

    return None
