import random

from dev.maps.connectivity_postprocessor import are_mutually_reachable, is_free_vertex
from dev.utils.log_symbols import AGENT_LOG_SYMBOL, TARGET_LOG_SYMBOL


MAX_ASSIGNMENT_ATTEMPTS = 200
VERTEX_ADJACENCY_CLEARANCE = 2


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


def _subset_respects_clearance(vertices):
    for index, vertex in enumerate(vertices):
        for other in vertices[index + 1 :]:
            if _vertices_conflict_under_clearance(vertex, other):
                return False
    return True


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

    centers = vertices[:]
    rng.shuffle(centers)
    for center in centers[: min(len(centers), MAX_ASSIGNMENT_ATTEMPTS)]:
        ordered_candidates = sorted(
            vertices,
            key=lambda vertex: (
                (vertex[0] - center[0]) ** 2 + (vertex[1] - center[1]) ** 2,
                rng.random(),
            ),
        )
        chosen = _greedy_clearance_subset(ordered_candidates, num_vertices)
        if chosen is not None:
            return chosen

    raise ValueError(
        f"Could not sample {num_vertices} clustered vertices with 8-neighbor clearance."
    )


def _sample_vertex_subset(vertices, num_vertices, rng, distribution_mode):
    if distribution_mode not in {"dispersed", "clustered"}:
        raise ValueError(f"Unsupported distribution_mode '{distribution_mode}'.")
    if len(vertices) < num_vertices:
        raise ValueError(
            f"Not enough candidate vertices for {num_vertices} positions under distribution_mode={distribution_mode}."
        )

    if distribution_mode == "clustered":
        return _sample_clustered_vertices(vertices, num_vertices, rng)
    return _sample_dispersed_vertices(vertices, num_vertices, rng)


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
        * starts and goals remain unique one-to-one positions when shared_goal=False
        * start != goal for each agent
        * when require_individual_reachability=True, each assigned start-goal pair must be reachable
        * starts respect 8-neighbor clearance among themselves
        * goals respect 8-neighbor clearance among themselves
        * clustered/dispersed controls only how each set is positioned, not assignment cardinality
    """
    if rng is None:
        rng = random.Random()

    if allowed_start_vertices is None:
        allowed_start_vertices = allowed_spawn_vertices
    if allowed_goal_vertices is None:
        allowed_goal_vertices = allowed_spawn_vertices

    labels = _build_label_info(num_agents)
    start_vertices = _filter_allowed_vertices(composite_map, allowed_start_vertices)
    goal_vertices = _filter_allowed_vertices(composite_map, allowed_goal_vertices)

    if shared_goal:
        raise ValueError("shared_goal mode is no longer supported in the current project configuration.")

    if len(start_vertices) < num_agents or len(goal_vertices) < num_agents:
        raise ValueError(
            f"Not enough free vertices for {num_agents} unique starts and goals."
        )

    for _ in range(MAX_ASSIGNMENT_ATTEMPTS):
        starts = _sample_vertex_subset(start_vertices, num_agents, rng, start_distribution_mode)
        if not _subset_respects_clearance(starts):
            continue

        remaining_goal_vertices = [vertex for vertex in goal_vertices if vertex not in set(starts)]
        if len(remaining_goal_vertices) < num_agents:
            continue

        goals = _sample_vertex_subset(remaining_goal_vertices, num_agents, rng, goal_distribution_mode)
        if not _subset_respects_clearance(goals):
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
