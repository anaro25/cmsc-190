import random

from dev.maps.connectivity_postprocessor import are_mutually_reachable, is_free_vertex
from dev.utils.log_symbols import AGENT_LOG_SYMBOL, TARGET_LOG_SYMBOL


MAX_ASSIGNMENT_ATTEMPTS = 200


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


def sample_agent_start_goal_pairs(
    composite_map,
    num_agents,
    rng=None,
    require_individual_reachability=False,
    allowed_spawn_vertices=None,
    allowed_start_vertices=None,
    allowed_goal_vertices=None,
    shared_goal=False,
):
    """
    Randomly assigns start and goal vertices for each agent.

    Constraints:
        * starts must be free vertices
        * goals must be free vertices
        * when shared_goal=False, goals are unique and one-to-one
        * when shared_goal=True, all agents share a single goal vertex
        * start != goal for each agent
        * when require_individual_reachability=True, each assigned start-goal pair must be reachable
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
        if len(start_vertices) < num_agents:
            raise ValueError(
                f"Not enough free start vertices for {num_agents} unique starts in shared-goal mode."
            )
        if not goal_vertices:
            raise ValueError("No free goal vertices are available in shared-goal mode.")
        return _sample_shared_goal_pairs(
            composite_map=composite_map,
            num_agents=num_agents,
            labels=labels,
            start_vertices=start_vertices,
            goal_vertices=goal_vertices,
            rng=rng,
            require_individual_reachability=require_individual_reachability,
        )

    if len(start_vertices) < num_agents or len(goal_vertices) < num_agents:
        raise ValueError(
            f"Not enough free vertices for {num_agents} unique starts and goals."
        )

    if require_individual_reachability:
        return _sample_reachable_pairs(
            composite_map=composite_map,
            num_agents=num_agents,
            labels=labels,
            start_vertices=start_vertices,
            goal_vertices=goal_vertices,
            rng=rng,
        )

    return _sample_without_reachability(
        num_agents=num_agents,
        labels=labels,
        start_vertices=start_vertices,
        goal_vertices=goal_vertices,
        rng=rng,
    )


def _sample_without_reachability(num_agents, labels, start_vertices, goal_vertices, rng):
    if len(start_vertices) < num_agents:
        raise ValueError(f"Not enough start vertices for {num_agents} agents.")

    for _ in range(MAX_ASSIGNMENT_ATTEMPTS):
        starts = rng.sample(start_vertices, num_agents)
        remaining_goals = [vertex for vertex in goal_vertices if vertex not in set(starts)]
        if len(remaining_goals) < num_agents:
            continue
        goals = rng.sample(remaining_goals, num_agents)

        valid = True
        for start, goal in zip(starts, goals):
            if start == goal:
                valid = False
                break
        if not valid:
            continue

        return _build_agents_from_assignment(labels, starts, goals)

    raise ValueError(
        f"Could not sample valid start-goal pairs for {num_agents} agents."
    )


def _sample_reachable_pairs(composite_map, num_agents, labels, start_vertices, goal_vertices, rng):
    if len(start_vertices) < num_agents:
        raise ValueError(f"Not enough start vertices for {num_agents} agents.")

    for _ in range(MAX_ASSIGNMENT_ATTEMPTS):
        starts = rng.sample(start_vertices, num_agents)
        used_goals = set(starts)
        goals = []

        for start in starts:
            candidate_goals = [
                vertex
                for vertex in goal_vertices
                if vertex not in used_goals
                and vertex != start
                and are_mutually_reachable(composite_map, start, vertex)
            ]
            if not candidate_goals:
                break
            goal = rng.choice(candidate_goals)
            goals.append(goal)
            used_goals.add(goal)

        if len(goals) != num_agents:
            continue

        return _build_agents_from_assignment(labels, starts, goals)

    raise ValueError(
        f"Could not sample reachable start-goal pairs for {num_agents} agents."
    )


def _sample_shared_goal_pairs(
    composite_map,
    num_agents,
    labels,
    start_vertices,
    goal_vertices,
    rng,
    require_individual_reachability,
):
    shuffled_goals = goal_vertices[:]
    rng.shuffle(shuffled_goals)

    for goal in shuffled_goals:
        eligible_starts = [vertex for vertex in start_vertices if vertex != goal]
        if require_individual_reachability:
            eligible_starts = [
                vertex
                for vertex in eligible_starts
                if are_mutually_reachable(composite_map, vertex, goal)
            ]
        if len(eligible_starts) < num_agents:
            continue

        for _ in range(MAX_ASSIGNMENT_ATTEMPTS):
            starts = rng.sample(eligible_starts, num_agents)
            return _build_agents_from_assignment(labels, starts, [goal] * num_agents)

    raise ValueError(
        f"Could not sample a valid shared goal with {num_agents} reachable unique starts."
    )
