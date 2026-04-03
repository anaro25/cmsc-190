from copy import deepcopy


def get_path_position(path, time_step):
    if time_step < len(path):
        return path[time_step]
    return path[-1]


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
    """
    frame = deepcopy(cyclic_map)

    for agent in agents:
        goal_i, goal_j = agent["goal"]
        frame[goal_i][goal_j] = agent["goal_label"]

    for agent in agents:
        path = paths_by_agent[agent["id"]]
        current_i, current_j = get_path_position(path, time_step)
        frame[current_i][current_j] = agent["label"]

    return frame


def build_all_frames(cyclic_map, agents, paths_by_agent):
    frames = []
    makespan = get_makespan(paths_by_agent)

    for time_step in range(makespan + 1):
        frame = build_frame_for_time(cyclic_map, agents, paths_by_agent, time_step)
        frames.append(frame)

    return frames