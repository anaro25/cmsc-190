import shutil
from pathlib import Path

from dev.mapf.mapf_logger_dynamic import (
    write_dynamic_mapf_frames,
    write_dynamic_setup_frame,
    write_dynamic_showcase_frame,
    write_dynamic_obstacle_only_frame,
)
from dev.mapf.metrics import summarize_mapf_result
from dev.mapf.time_expanded_cbs import solve_time_expanded_mapf_with_cbs


PROGRESS_LOG_INTERVAL_SECONDS = 5


def clear_previous_mapping_run(map_name, mapping_name, output_root):
    mapping_output_dir = Path(output_root) / mapping_name / map_name
    if mapping_output_dir.exists():
        shutil.rmtree(mapping_output_dir)
    mapping_output_dir.mkdir(parents=True, exist_ok=True)


def build_elapsed_time_reporter(interval_seconds=PROGRESS_LOG_INTERVAL_SECONDS):
    def report(elapsed_seconds):
        if elapsed_seconds > 0 and elapsed_seconds % interval_seconds == 0:
            print(f"{elapsed_seconds}...")
    return report


def format_path_length(value):
    if value is None:
        return "None"
    if isinstance(value, (int, float)) and float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def print_mapping_header(mapping_name, context_label):
    print(f"=== {mapping_name.upper()} | {context_label} ===")


def print_mapping_summary(summary):
    if not summary["solved"]:
        print("[Failed]")
        return
    print("[Success]")
    print(f"Number of conflicts detected: {summary['num_conflicts_detected']}")
    print(f"Average path length: {format_path_length(summary['average_path_length'])}")


def print_bad_setup_message(result):
    status = result["status"]
    if status == "bad_setup_timeout":
        print("[Failed: solver timeout reached]")
    elif status == "no_solution":
        print("[Failed: no feasible path for this assignment]")
    else:
        print("[Failed: assignment not solved]")
    print(f"Number of conflicts detected: {result['num_conflicts_detected']}")


def run_time_expanded_mapf_for_loop(
    map_name,
    mapping_name,
    mapped_loop,
    dynamic_matrix_loop,
    setup_composite_map,
    agents,
    output_root,
    max_solver_runtime_seconds=10.0,
    context_label=None,
):
    clear_previous_mapping_run(map_name=map_name, mapping_name=mapping_name, output_root=output_root)
    mapping_output_root = Path(output_root) / mapping_name

    write_dynamic_obstacle_only_frame(
        map_name=map_name,
        composite_map=setup_composite_map,
        output_root=mapping_output_root,
    )
    write_dynamic_showcase_frame(
        map_name=map_name,
        composite_map=setup_composite_map,
        output_root=mapping_output_root,
    )
    write_dynamic_setup_frame(
        map_name=map_name,
        composite_map=setup_composite_map,
        agents=agents,
        output_root=mapping_output_root,
    )

    print_mapping_header(mapping_name=mapping_name, context_label=context_label or map_name)
    print("0...")
    result = solve_time_expanded_mapf_with_cbs(
        mapped_loop=mapped_loop,
        agents=agents,
        max_runtime_seconds=max_solver_runtime_seconds,
        progress_callback=build_elapsed_time_reporter(),
    )

    if result["status"] != "solved":
        print_bad_setup_message(result)
        return None

    rendered_frame_paths = write_dynamic_mapf_frames(
        map_name=map_name,
        composite_loop=mapped_loop,
        dynamic_matrix_loop=dynamic_matrix_loop,
        agents=agents,
        paths_by_agent=result["paths_by_agent"],
        output_root=mapping_output_root,
    )

    run_result = {
        "agents": agents,
        "paths_by_agent": result["paths_by_agent"],
        "frames": rendered_frame_paths,
        "num_conflicts_detected": result["num_conflicts_detected"],
        "num_high_level_nodes_expanded": result["num_high_level_nodes_expanded"],
    }
    summary = summarize_mapf_result(run_result)
    print_mapping_summary(summary)
    return run_result
