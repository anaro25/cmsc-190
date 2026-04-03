from copy import deepcopy


def get_path_position(path, time_step):
    """
    Disappearing-agent model:
        return None after the agent's path ends.
    """
    if time_step < len(path):
        return path[time_step]
    return None


def get_makespan(paths_by_agent):
    if not paths_by_agent:
        return 0
    return max(len(path) for path in paths_by_agent.values()) - 1


def build_frame_for_time(cyclic_map, agents, paths_by_agent, time_step):
    """
    Builds one composite-map frame for a single timestep.

    Overlay priority:
        1. target letters (lowercase)
        2. agent letters (uppercase) overwrite targets if occupying same cell

    Since agents disappear after reaching their targets, an agent is shown
    only while its path still has a position at this timestep.
    """
    frame = deepcopy(cyclic_map)

    for agent in agents:
        goal_i, goal_j = agent["goal"]
        frame[goal_i][goal_j] = agent["goal_label"]

    for agent in agents:
        path = paths_by_agent[agent["id"]]
        current_position = get_path_position(path, time_step)

        if current_position is None:
            continue

        current_i, current_j = current_position
        frame[current_i][current_j] = agent["label"]

    return frame


def build_all_frames(cyclic_map, agents, paths_by_agent):
    frames = []
    makespan = get_makespan(paths_by_agent)

    for time_step in range(makespan + 1):
        frame = build_frame_for_time(cyclic_map, agents, paths_by_agent, time_step)
        frames.append(frame)

    return frames