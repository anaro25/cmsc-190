import math
import random

from cyclic_test.navigation.cyclic_grid_navigation import get_all_free_vertices


AGENT_LABEL_POOL = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + list("ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ")
GOAL_LABEL_POOL = list("abcdefghijklmnopqrstuvwxyz") + list("αβγδεζηθικλμνξοπρστυφχψω")


def build_agent_labels(num_agents=8):
    if num_agents > len(AGENT_LABEL_POOL) or num_agents > len(GOAL_LABEL_POOL):
        raise ValueError(
            "Not enough single-character labels for the requested number of agents. "
            f"Requested={num_agents}, supported={min(len(AGENT_LABEL_POOL), len(GOAL_LABEL_POOL))}."
        )

    labels = []
    for agent_id in range(num_agents):
        labels.append(
            {
                "id": agent_id,
                "label": AGENT_LABEL_POOL[agent_id],
                "goal_label": GOAL_LABEL_POOL[agent_id],
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


def sample_agent_start_goal_pairs(composite_map, num_agents=8, rng=None):
    """
    Randomly assigns start and goal vertices for each agent.

    Rules:
        * starts and goals must be free vertices
        * each start must be unique
        * each goal must be unique
        * start != goal for each agent
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
