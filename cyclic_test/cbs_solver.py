import heapq
import itertools

from mapf_low_level_astar import find_path_for_agent


def get_path_position(path, time_step):
    """
    Disappearing-agent model:
        return None after the agent's path ends.
    """
    if time_step < len(path):
        return path[time_step]
    return None


def compute_solution_cost(paths_by_agent):
    return sum(len(path) - 1 for path in paths_by_agent.values())


def detect_first_conflict(paths_by_agent):
    """
    Detects the first conflict in time order.

    Conflict types:
        * vertex conflict
        * edge conflict (swap)

    Disappearing-agent model:
        agents do not occupy any vertex after their final timestep.
    """
    if not paths_by_agent:
        return None

    agent_ids = sorted(paths_by_agent.keys())
    max_time = max(len(path) for path in paths_by_agent.values())

    for time_step in range(max_time):
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

        if time_step == 0:
            continue

        transitions = {}

        for agent_id in agent_ids:
            prev_position = get_path_position(paths_by_agent[agent_id], time_step - 1)
            current_position = get_path_position(paths_by_agent[agent_id], time_step)

            if prev_position is None or current_position is None:
                continue

            edge = (prev_position, current_position)
            reverse_edge = (current_position, prev_position)

            if reverse_edge in transitions:
                other_agent_id = transitions[reverse_edge]

                # Ignore both agents waiting in place.
                if prev_position != current_position:
                    return {
                        "type": "edge",
                        "time": time_step,
                        "from_to": edge,
                        "agents": (other_agent_id, agent_id),
                    }

            transitions[edge] = agent_id

    return None


def split_conflict_into_constraints(conflict):
    agent_a, agent_b = conflict["agents"]

    if conflict["type"] == "vertex":
        position = conflict["position"]
        time_step = conflict["time"]

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

    from_a, to_a = conflict["from_to"]
    time_step = conflict["time"]

    return [
        {
            "agent": agent_a,
            "type": "edge",
            "from": from_a,
            "to": to_a,
            "time": time_step,
        },
        {
            "agent": agent_b,
            "type": "edge",
            "from": to_a,
            "to": from_a,
            "time": time_step,
        },
    ]


def make_cbs_node(constraints, paths_by_agent):
    return {
        "constraints": constraints,
        "paths": paths_by_agent,
        "cost": compute_solution_cost(paths_by_agent),
    }


def solve_mapf_with_cbs(cyclic_map, agents):
    """
    Vanilla CBS for disappearing agents.

    High-level node:
        * constraints
        * paths
        * cost
    """
    root_constraints = []
    root_paths = {}

    for agent in agents:
        path = find_path_for_agent(
            cyclic_map=cyclic_map,
            agent_id=agent["id"],
            start=agent["start"],
            goal=agent["goal"],
            constraints=root_constraints,
        )

        if path is None:
            return None

        root_paths[agent["id"]] = path

    root_node = make_cbs_node(root_constraints, root_paths)

    open_heap = []
    counter = itertools.count()
    heapq.heappush(open_heap, (root_node["cost"], next(counter), root_node))

    while open_heap:
        _, _, current_node = heapq.heappop(open_heap)

        conflict = detect_first_conflict(current_node["paths"])

        if conflict is None:
            return current_node["paths"]

        new_constraints = split_conflict_into_constraints(conflict)

        for added_constraint in new_constraints:
            child_constraints = list(current_node["constraints"])
            child_constraints.append(added_constraint)

            child_paths = dict(current_node["paths"])
            constrained_agent_id = added_constraint["agent"]

            agent = next(agent for agent in agents if agent["id"] == constrained_agent_id)

            new_path = find_path_for_agent(
                cyclic_map=cyclic_map,
                agent_id=agent["id"],
                start=agent["start"],
                goal=agent["goal"],
                constraints=child_constraints,
            )

            if new_path is None:
                continue

            child_paths[constrained_agent_id] = new_path
            child_node = make_cbs_node(child_constraints, child_paths)

            heapq.heappush(
                open_heap,
                (child_node["cost"], next(counter), child_node),
            )

    return None