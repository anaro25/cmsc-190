import random

from dev.maps.connectivity_postprocessor import are_mutually_reachable, is_free_vertex
from dev.master_config import compact_clustering
from dev.utils.log_symbols import AGENT_LOG_SYMBOL, TARGET_LOG_SYMBOL


MAX_ASSIGNMENT_ATTEMPTS = 200
VERTEX_ADJACENCY_CLEARANCE = 2
CLUSTER_GAP_ONE_STEP = 4
START_DISTRIBUTION_MODES = {"dispersed", "clustered"}
GOAL_DISTRIBUTION_MODES = {"dispersed", "clustered", "single"}


def _build_label_info(num_agents):
    return [
        {
            "id": agent_id,
            "label": AGENT_LOG_SYMBOL,
            "goal_label": TARGET_LOG_SYMBOL,
        }
        for agent_id in range(num_agents)
    ]


def _iter_free_vertices(composite_map):
    rows = len(composite_map)
    cols = len(composite_map[0]) if rows else 0
    for row_index in range(0, rows, 2):
        for column_index in range(0, cols, 2):
            if is_free_vertex(composite_map, row_index, column_index):
                yield (row_index, column_index)


def _filter_allowed_vertices(composite_map, allowed_vertices):
    free_vertices = set(_iter_free_vertices(composite_map))
    if allowed_vertices is None:
        return list(free_vertices)
    return [vertex for vertex in allowed_vertices if vertex in free_vertices]


def _build_agents_from_assignment(labels, starts, goals):
    agents = []
    for label_info, start, goal in zip(labels, starts, goals):
        agents.append(
            {
                "id": label_info["id"],
                "label": label_info["label"],
                "goal_label": label_info["goal_label"],
                "start": start,
                "goal": goal,
            }
        )
    return agents


def _vertices_conflict_under_clearance(vertex_a, vertex_b):
    row_delta = abs(vertex_a[0] - vertex_b[0])
    col_delta = abs(vertex_a[1] - vertex_b[1])
    return row_delta <= VERTEX_ADJACENCY_CLEARANCE and col_delta <= VERTEX_ADJACENCY_CLEARANCE


def _vertices_are_direct_neighbors(vertex_a, vertex_b):
    row_delta = abs(vertex_a[0] - vertex_b[0])
    col_delta = abs(vertex_a[1] - vertex_b[1])
    return (row_delta != 0 or col_delta != 0) and row_delta <= 2 and col_delta <= 2


def _vertices_are_gap_one_neighbors(vertex_a, vertex_b):
    row_delta = abs(vertex_a[0] - vertex_b[0])
    col_delta = abs(vertex_a[1] - vertex_b[1])
    return (row_delta, col_delta) in {
        (0, CLUSTER_GAP_ONE_STEP),
        (CLUSTER_GAP_ONE_STEP, 0),
        (CLUSTER_GAP_ONE_STEP, CLUSTER_GAP_ONE_STEP),
    }


def _vertices_are_cluster_neighbors(vertex_a, vertex_b):
    if compact_clustering:
        return _vertices_are_direct_neighbors(vertex_a, vertex_b)
    return _vertices_are_gap_one_neighbors(vertex_a, vertex_b)


def _subset_respects_clearance(vertices):
    for index, vertex in enumerate(vertices):
        for other in vertices[index + 1 :]:
            if _vertices_conflict_under_clearance(vertex, other):
                return False
    return True


def _subset_is_connected_cluster(vertices):
    if not vertices:
        return False
    if len(vertices) == 1:
        return True
    if not compact_clustering and not _subset_respects_clearance(vertices):
        return False

    remaining = set(vertices)
    stack = [remaining.pop()]
    visited = {stack[0]}
    while stack:
        current = stack.pop()
        newly_reached = {
            other
            for other in tuple(remaining)
            if _vertices_are_cluster_neighbors(current, other)
        }
        if newly_reached:
            remaining -= newly_reached
            visited |= newly_reached
            stack.extend(newly_reached)
    return len(visited) == len(vertices)


def _greedy_clearance_subset(candidates, num_vertices):
    chosen = []
    for vertex in candidates:
        if all(not _vertices_conflict_under_clearance(vertex, existing) for existing in chosen):
            chosen.append(vertex)
            if len(chosen) == num_vertices:
                return chosen
    return None


def _sample_dispersed_vertices(vertices, num_vertices, rng):
    for _ in range(MAX_ASSIGNMENT_ATTEMPTS):
        shuffled = vertices[:]
        rng.shuffle(shuffled)
        chosen = _greedy_clearance_subset(shuffled, num_vertices)
        if chosen is not None:
            return chosen
    raise ValueError(
        f"Could not sample {num_vertices} dispersed vertices with 8-neighbor clearance."
    )


def _sample_clustered_vertices(vertices, num_vertices, rng):
    if not vertices:
        raise ValueError("No candidate vertices are available for clustered sampling.")

    if num_vertices == 1:
        return [rng.choice(vertices)]

    vertex_set = set(vertices)
    centers = vertices[:]
    rng.shuffle(centers)
    for center in centers[: min(len(centers), MAX_ASSIGNMENT_ATTEMPTS)]:
        chosen = [center]
        chosen_set = {center}

        while len(chosen) < num_vertices:
            frontier = []
            for candidate in vertex_set - chosen_set:
                if not compact_clustering and any(
                    _vertices_conflict_under_clearance(candidate, existing) for existing in chosen
                ):
                    continue
                touching_vertices = sum(
                    1 for existing in chosen if _vertices_are_cluster_neighbors(candidate, existing)
                )
                if touching_vertices == 0:
                    continue
                distance_sq = (candidate[0] - center[0]) ** 2 + (candidate[1] - center[1]) ** 2
                frontier.append((distance_sq, -touching_vertices, rng.random(), candidate))

            if not frontier:
                break

            frontier.sort()
            next_vertex = frontier[0][3]
            chosen.append(next_vertex)
            chosen_set.add(next_vertex)

        if len(chosen) == num_vertices and _subset_is_connected_cluster(chosen):
            return chosen

    cluster_description = (
        "one compact directly adjacent component"
        if compact_clustering
        else "one spaced one-cell-gap component"
    )
    raise ValueError(
        f"Could not sample {num_vertices} clustered vertices as {cluster_description}."
    )


def _sample_vertex_subset(vertices, num_vertices, rng, distribution_mode):
    if distribution_mode not in START_DISTRIBUTION_MODES:
        raise ValueError(f"Unsupported distribution_mode '{distribution_mode}'.")
    if len(vertices) < num_vertices:
        raise ValueError(
            f"Not enough candidate vertices for {num_vertices} positions under distribution_mode={distribution_mode}."
        )

    if distribution_mode == "clustered":
        return _sample_clustered_vertices(vertices, num_vertices, rng)
    return _sample_dispersed_vertices(vertices, num_vertices, rng)


def _resolve_single_goal(composite_map, starts, candidate_goals, rng, require_individual_reachability):
    possible_goals = [goal for goal in candidate_goals if goal not in set(starts)]
    rng.shuffle(possible_goals)

    for goal in possible_goals:
        if not require_individual_reachability:
            return goal
        if all(are_mutually_reachable(composite_map, start, goal) for start in starts):
            return goal

    return None


def _build_reachability_adjacency(composite_map, starts, goals):
    adjacency = [[] for _ in starts]
    for start_index, start in enumerate(starts):
        for goal_index, goal in enumerate(goals):
            if start == goal:
                continue
            if are_mutually_reachable(composite_map, start, goal):
                adjacency[start_index].append(goal_index)
    return adjacency


def _find_bipartite_matching(adjacency, num_goals, rng):
    goal_to_start = [-1] * num_goals

    def try_assign(start_index, visited_goals):
        candidate_goals = adjacency[start_index][:]
        rng.shuffle(candidate_goals)
        for goal_index in candidate_goals:
            if goal_index in visited_goals:
                continue
            visited_goals.add(goal_index)
            assigned_start = goal_to_start[goal_index]
            if assigned_start == -1 or try_assign(assigned_start, visited_goals):
                goal_to_start[goal_index] = start_index
                return True
        return False

    start_indices = list(range(len(adjacency)))
    rng.shuffle(start_indices)
    for start_index in start_indices:
        if not try_assign(start_index, set()):
            return None

    start_to_goal = [-1] * len(adjacency)
    for goal_index, start_index in enumerate(goal_to_start):
        if start_index != -1:
            start_to_goal[start_index] = goal_index
    if any(goal_index == -1 for goal_index in start_to_goal):
        return None
    return start_to_goal


def _pair_starts_and_goals(composite_map, starts, goals, rng, require_individual_reachability):
    if require_individual_reachability:
        adjacency = _build_reachability_adjacency(composite_map, starts, goals)
        if any(not goal_indices for goal_indices in adjacency):
            return None
        start_to_goal = _find_bipartite_matching(adjacency, len(goals), rng)
        if start_to_goal is None:
            return None
        return [goals[goal_index] for goal_index in start_to_goal]

    shuffled_goals = goals[:]
    rng.shuffle(shuffled_goals)
    return shuffled_goals


def sample_agent_start_goal_pairs(
    composite_map,
    num_agents,
    rng=None,
    require_individual_reachability=False,
    allowed_spawn_vertices=None,
    allowed_start_vertices=None,
    allowed_goal_vertices=None,
    shared_goal=False,
    start_distribution_mode="dispersed",
    goal_distribution_mode="dispersed",
):
    """
    Randomly assigns start and goal vertices for each agent.

    Constraints:
        * starts must be free vertices
        * goals must be free vertices
        * starts remain unique positions
        * goals remain unique one-to-one positions for dispersed and clustered target modes
        * goal_distribution_mode="single" gives all agents the same literal target cell
        * start != goal for each agent
        * when require_individual_reachability=True, each assigned start-goal pair must be reachable
        * dispersed sets respect 8-neighbor clearance internally
        * clustered sets form one connected cluster whose spacing is controlled by compact_clustering
        * "single" is valid only for goal_distribution_mode, not start_distribution_mode
    """
    if rng is None:
        rng = random.Random()

    if allowed_start_vertices is None:
        allowed_start_vertices = allowed_spawn_vertices
    if allowed_goal_vertices is None:
        allowed_goal_vertices = allowed_spawn_vertices

    if shared_goal:
        goal_distribution_mode = "single"

    if start_distribution_mode not in START_DISTRIBUTION_MODES:
        raise ValueError(
            f"Unsupported start_distribution_mode '{start_distribution_mode}'. "
            f"Valid start modes are: {sorted(START_DISTRIBUTION_MODES)}. "
            "The 'single' mode can only be used for targets/goals."
        )
    if goal_distribution_mode not in GOAL_DISTRIBUTION_MODES:
        raise ValueError(
            f"Unsupported goal_distribution_mode '{goal_distribution_mode}'. "
            f"Valid goal modes are: {sorted(GOAL_DISTRIBUTION_MODES)}."
        )

    labels = _build_label_info(num_agents)
    start_vertices = _filter_allowed_vertices(composite_map, allowed_start_vertices)
    goal_vertices = _filter_allowed_vertices(composite_map, allowed_goal_vertices)

    minimum_goal_vertices = 1 if goal_distribution_mode == "single" else num_agents
    if len(start_vertices) < num_agents or len(goal_vertices) < minimum_goal_vertices:
        raise ValueError(
            f"Not enough free vertices for {num_agents} starts and goal_distribution_mode={goal_distribution_mode}."
        )

    for _ in range(MAX_ASSIGNMENT_ATTEMPTS):
        starts = _sample_vertex_subset(start_vertices, num_agents, rng, start_distribution_mode)
        if start_distribution_mode == "dispersed" and not _subset_respects_clearance(starts):
            continue
        if start_distribution_mode == "clustered" and not _subset_is_connected_cluster(starts):
            continue

        remaining_goal_vertices = [vertex for vertex in goal_vertices if vertex not in set(starts)]

        if goal_distribution_mode == "single":
            shared_target = _resolve_single_goal(
                composite_map=composite_map,
                starts=starts,
                candidate_goals=remaining_goal_vertices,
                rng=rng,
                require_individual_reachability=require_individual_reachability,
            )
            if shared_target is None:
                continue
            paired_goals = [shared_target for _ in starts]
            return _build_agents_from_assignment(labels, starts, paired_goals)

        if len(remaining_goal_vertices) < num_agents:
            continue

        goals = _sample_vertex_subset(remaining_goal_vertices, num_agents, rng, goal_distribution_mode)
        if goal_distribution_mode == "dispersed" and not _subset_respects_clearance(goals):
            continue
        if goal_distribution_mode == "clustered" and not _subset_is_connected_cluster(goals):
            continue

        paired_goals = _pair_starts_and_goals(
            composite_map=composite_map,
            starts=starts,
            goals=goals,
            rng=rng,
            require_individual_reachability=require_individual_reachability,
        )
        if paired_goals is None:
            continue

        return _build_agents_from_assignment(labels, starts, paired_goals)

    raise ValueError(
        f"Could not sample valid start-goal pairs for {num_agents} agents with start_distribution_mode={start_distribution_mode} "
        f"and goal_distribution_mode={goal_distribution_mode}."
    )
