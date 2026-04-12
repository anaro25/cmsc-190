import math
import random
from collections import deque

from dev.navigation.cyclic_grid_navigation import get_all_free_vertices, get_outgoing_neighbors
from dev.utils.log_symbols import AGENT_LOG_SYMBOL, TARGET_LOG_SYMBOL


def build_agent_labels(num_agents=8):
    labels = []
    for agent_id in range(num_agents):
        labels.append(
            {
                "id": agent_id,
                "label": AGENT_LOG_SYMBOL,
                "goal_label": TARGET_LOG_SYMBOL,
            }
        )

    return labels


def collect_free_vertices(composite_map):
    return get_all_free_vertices(composite_map)


def compute_num_agents_from_density(composite_map, density):
    if density < 0.0 or density > 1.0:
        raise ValueError(f"Density must be between 0.0 and 1.0. Got {density}.")

    num_free_vertices = len(collect_free_vertices(composite_map))
    num_agents = math.floor(density * num_free_vertices)

    if density > 0.0 and num_free_vertices > 0:
        num_agents = max(1, num_agents)

    return num_agents


def _collect_reachable_vertices(composite_map, start_vertex):
    queue = deque([start_vertex])
    visited = {start_vertex}

    while queue:
        current = queue.popleft()
        for neighbor in get_outgoing_neighbors(composite_map, current):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append(neighbor)

    return visited


def sample_agent_start_goal_pairs(
    composite_map,
    num_agents=8,
    rng=None,
    require_individual_reachability=False,
):
    """
    Randomly assigns start and goal vertices for each agent.

    Rules:
        * starts and goals must be free vertices
        * each start must be unique
        * each goal must be unique
        * start != goal for each agent
        * when require_individual_reachability=True, each agent's goal must be reachable
          from its start in the provided composite map
    """
    if rng is None:
        rng = random

    free_vertices = collect_free_vertices(composite_map)

    if len(free_vertices) < num_agents * 2:
        raise ValueError(
            f"Not enough free vertices for {num_agents} unique starts and goals."
        )

    labels = build_agent_labels(num_agents=num_agents)

    max_attempts = 1000

    if not require_individual_reachability:
        for _ in range(max_attempts):
            starts = rng.sample(free_vertices, num_agents)
            goals = rng.sample(free_vertices, num_agents)

            valid = True

            for start, goal in zip(starts, goals):
                if start == goal:
                    valid = False
                    break

            if not valid:
                continue

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

        raise ValueError(
            f"Could not sample valid start-goal pairs for {num_agents} agents."
        )

    for _ in range(max_attempts):
        starts = rng.sample(free_vertices, num_agents)
        used_goals = set(starts)
        goals = []
        valid = True

        for start in starts:
            reachable_vertices = _collect_reachable_vertices(composite_map, start)
            candidate_goals = [
                vertex for vertex in reachable_vertices if vertex not in used_goals and vertex != start
            ]
            if not candidate_goals:
                valid = False
                break
            goal = rng.choice(candidate_goals)
            goals.append(goal)
            used_goals.add(goal)

        if not valid:
            continue

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

    raise ValueError(
        f"Could not sample reachable start-goal pairs for {num_agents} agents."
    )
