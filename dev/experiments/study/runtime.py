from __future__ import annotations

import time
from typing import Any, Callable

from dev.experiments.study.io_utils import ExperimentLogger
from dev.experiments.study.models import MappingRunRecord, RunConfiguration
from dev.master_config import enhanced_CBS
from dev.mapf.full.cbs_solver import compute_solution_cost as compute_static_solution_cost
from dev.mapf.full.cbs_solver import solve_mapf_with_cbs
from dev.mapf.time_expanded_cbs import compute_solution_cost as compute_dynamic_solution_cost
from dev.mapf.time_expanded_cbs import solve_time_expanded_mapf_with_cbs


COUNTED_RESULT_CATEGORIES = {"successful", "unfinished"}


def build_progress_callback(logger: ExperimentLogger, label: str) -> Callable[[int], None]:
    def callback(elapsed_seconds: int) -> None:
        logger.log(f"    {label} progress: {max(0, elapsed_seconds):.2f}s")

    return callback


def compute_average_path_length(
    paths_by_agent: dict[int, list[tuple[int, int]]], *, dynamic: bool
) -> float:
    if not paths_by_agent:
        return 0.0
    total_cost = (
        compute_dynamic_solution_cost(paths_by_agent)
        if dynamic
        else compute_static_solution_cost(paths_by_agent)
    )
    return total_cost / len(paths_by_agent)


def seed_for(*parts: Any) -> int:
    text = "|".join(str(part) for part in parts)
    total = 0
    for index, character in enumerate(text, start=1):
        total = (total + index * ord(character)) % (2**31 - 1)
    return total or 1


def categorize_solver_status(solver_status: str | None) -> tuple[str, bool, bool]:
    if solver_status == "solved":
        return "successful", True, True
    if solver_status == "bad_setup_timeout":
        return "unfinished", True, False
    if solver_status == "no_solution":
        return "unsolvable", False, False
    if solver_status and solver_status.startswith("setup_failed"):
        return "setup_failed", False, False
    if solver_status and solver_status.startswith("exception"):
        return "setup_failed", False, False
    return "setup_failed", False, False


def build_mapping_record(
    *,
    run_configuration: RunConfiguration,
    mapping_name: str,
    comparison_case: str,
    runtime_limit_seconds: float,
    solver_name: str,
    enhanced_cbs_enabled: bool,
    solver_suboptimality_factor: float | None,
    solver_result: dict[str, Any] | None,
    elapsed_seconds: float,
    solver_status: str | None,
    paired_run: bool,
    dynamic: bool,
) -> MappingRunRecord:
    average_path_length = None
    num_conflicts_detected_at_halt = None
    resolved_solver_status = solver_status or "unknown_failure"

    if solver_result is not None:
        resolved_solver_status = solver_result.get("status", resolved_solver_status)
        num_conflicts_detected_at_halt = solver_result.get("num_conflicts_detected")
        if num_conflicts_detected_at_halt is None:
            num_conflicts_detected_at_halt = solver_result.get("num_conflicts_detected_at_halt")
        if solver_result.get("paths_by_agent"):
            average_path_length = compute_average_path_length(
                solver_result["paths_by_agent"],
                dynamic=dynamic,
            )
        num_high_level_nodes_expanded = solver_result.get("num_high_level_nodes_expanded")
    else:
        num_high_level_nodes_expanded = None

    result_category, counted_run, solved_run = categorize_solver_status(resolved_solver_status)
    halted_time = runtime_limit_seconds if result_category == "unfinished" else elapsed_seconds

    mapping_index = 0 if mapping_name == "classical" else 1
    return MappingRunRecord(
        branch_id=run_configuration.branch_id,
        branch_decimal=run_configuration.branch_decimal,
        map_type=run_configuration.map_type,
        map_obstacle_type=run_configuration.map_obstacle_type,
        target_type=run_configuration.target_type,
        agent_number=run_configuration.agent_number,
        agent_number_index=run_configuration.agent_number_index,
        run_index=run_configuration.run_index,
        run_config_id=run_configuration.run_config_id,
        mapping_name=mapping_name,
        mapping_index=mapping_index,
        mapping_record_id=(
            f"mapping[{run_configuration.branch_decimal}."
            f"{run_configuration.agent_number_index}.{run_configuration.run_index}.{mapping_index}]"
        ),
        comparison_case=comparison_case,
        solver_name=solver_name,
        enhanced_cbs_enabled=enhanced_cbs_enabled,
        solver_suboptimality_factor=solver_suboptimality_factor,
        paired_run=paired_run,
        solver_status=resolved_solver_status,
        result_category=result_category,
        counted_run=counted_run,
        solved_run=solved_run,
        time_computation_halted_seconds=halted_time,
        num_conflicts_detected_at_halt=num_conflicts_detected_at_halt,
        average_path_length=average_path_length,
        num_high_level_nodes_expanded=num_high_level_nodes_expanded,
        runtime_limit_seconds=runtime_limit_seconds,
        map_identifier=run_configuration.map_identifier,
        map_seed=run_configuration.map_seed,
        assignment_seed=run_configuration.assignment_seed,
        dynamic_schedule_seed=run_configuration.dynamic_schedule_seed,
        initial_condition_spec=run_configuration.starts_and_goals,
    )


def run_static_mapping(
    *,
    composite_map: list[list[Any]],
    agents: list[dict[str, Any]],
    runtime_limit_seconds: float,
    logger: ExperimentLogger,
    label: str,
    solver_suboptimality_factor: float | None = None,
    true_static_shortest_path_distance: bool = False,
    tight_time_horizon: bool = False,
    agent_cohesion_enabled: bool = False,
    use_ecbs: bool | None = None,
) -> tuple[dict[str, Any] | None, float, str]:
    start = time.perf_counter()
    try:
        solver_result = solve_mapf_with_cbs(
            composite_map=composite_map,
            agents=agents,
            max_runtime_seconds=runtime_limit_seconds,
            progress_callback=build_progress_callback(logger, label),
            use_ecbs=bool(enhanced_CBS) if use_ecbs is None else bool(use_ecbs),
            ecbs_suboptimality_factor=solver_suboptimality_factor,
            true_static_shortest_path_distance=true_static_shortest_path_distance,
            tight_time_horizon=tight_time_horizon,
            agent_cohesion_enabled=agent_cohesion_enabled,
        )
        elapsed_seconds = time.perf_counter() - start
        return solver_result, elapsed_seconds, solver_result.get("status", "unknown_failure")
    except Exception as exc:  # pragma: no cover
        elapsed_seconds = time.perf_counter() - start
        return None, elapsed_seconds, f"exception:{type(exc).__name__}:{exc}"


def run_dynamic_mapping(
    *,
    mapped_loop: list[list[list[Any]]],
    agents: list[dict[str, Any]],
    runtime_limit_seconds: float,
    logger: ExperimentLogger,
    label: str,
    solver_suboptimality_factor: float | None = None,
    true_static_shortest_path_distance: bool = False,
    tight_time_horizon: bool = False,
    agent_cohesion_enabled: bool = False,
    use_ecbs: bool | None = None,
) -> tuple[dict[str, Any] | None, float, str]:
    start = time.perf_counter()
    try:
        solver_result = solve_time_expanded_mapf_with_cbs(
            mapped_loop=mapped_loop,
            agents=agents,
            max_runtime_seconds=runtime_limit_seconds,
            progress_callback=build_progress_callback(logger, label),
            use_ecbs=bool(enhanced_CBS) if use_ecbs is None else bool(use_ecbs),
            ecbs_suboptimality_factor=solver_suboptimality_factor,
            true_static_shortest_path_distance=true_static_shortest_path_distance,
            tight_time_horizon=tight_time_horizon,
            agent_cohesion_enabled=agent_cohesion_enabled,
        )
        elapsed_seconds = time.perf_counter() - start
        return solver_result, elapsed_seconds, solver_result.get("status", "unknown_failure")
    except Exception as exc:  # pragma: no cover
        elapsed_seconds = time.perf_counter() - start
        return None, elapsed_seconds, f"exception:{type(exc).__name__}:{exc}"
