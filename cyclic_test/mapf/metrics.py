from cyclic_test.mapf.cbs_solver import compute_solution_cost


def summarize_mapf_result(result):
    if result is None:
        return {
            "solved": False,
            "num_conflicts_detected": None,
            "total_path_length": None,
            "num_agents": None,
            "num_frames": None,
        }

    return {
        "solved": True,
        "num_conflicts_detected": result["num_conflicts_detected"],
        "total_path_length": compute_solution_cost(result["paths_by_agent"]),
        "num_agents": len(result["agents"]),
        "num_frames": len(result["frames"]),
    }
