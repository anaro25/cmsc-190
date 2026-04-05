from cyclic_test.mapf.cbs_solver import compute_solution_cost


def summarize_mapf_result(result):
    if result is None:
        return {
            "solved": False,
            "num_conflicts_detected": None,
            "average_path_length": None,
            "num_agents": None,
            "num_frames": None,
        }

    num_agents = len(result["agents"])
    total_path_length = compute_solution_cost(result["paths_by_agent"])
    average_path_length = 0 if num_agents == 0 else total_path_length / num_agents

    return {
        "solved": True,
        "num_conflicts_detected": result["num_conflicts_detected"],
        "average_path_length": average_path_length,
        "num_agents": num_agents,
        "num_frames": len(result["frames"]),
    }
