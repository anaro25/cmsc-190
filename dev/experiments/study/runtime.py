from __future__ import annotations

import time
from typing import Any, Callable

from dev.experiments.study.io_utils import ExperimentLogger
from dev.experiments.study.models import MappingRunRecord, RunConfiguration
from dev.mapf.cbs_solver import compute_solution_cost as compute_static_solution_cost
from dev.mapf.cbs_solver import solve_mapf_with_cbs
from dev.mapf.time_expanded_cbs import compute_solution_cost as compute_dynamic_solution_cost
from dev.mapf.time_expanded_cbs import solve_time_expanded_mapf_with_cbs


def build_progress_callback(logger: ExperimentLogger, label: str) -> Callable[[int], None]:
    def callback(elapsed_seconds: int) -> None:
        logger.log(f"    {label} progress: {max(0, elapsed_seconds)}s")

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


def build_mapping_record(
    *,
    run_configuration: RunConfiguration,
    mapping_name: str,
    comparison_case: str,
    runtime_limit_seconds: float,
    solver_result: dict[str, Any] | None,
    elapsed_seconds: float,
    paired_run: bool,
    success: bool,
    failure_reason: str | None,
    dynamic: bool,
) -> MappingRunRecord:
    average_path_length = None
    num_conflicts_detected = None
    num_high_level_nodes_expanded = None
    status = failure_reason or "unknown_failure"

    if solver_result is not None:
        status = solver_result.get("status", status)
        num_conflicts_detected = solver_result.get("num_conflicts_detected")
        num_high_level_nodes_expanded = solver_result.get("num_high_level_nodes_expanded")
        if solver_result.get("paths_by_agent"):
            average_path_length = compute_average_path_length(
                solver_result["paths_by_agent"],
                dynamic=dynamic,
            )

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
        paired_run=paired_run,
        success=success,
        status=status,
        failure_reason=None if success else failure_reason,
        computation_time_seconds=elapsed_seconds,
        num_conflicts_detected=num_conflicts_detected,
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
) -> tuple[bool, dict[str, Any] | None, float, str | None]:
    start = time.perf_counter()
    try:
        solver_result = solve_mapf_with_cbs(
            composite_map=composite_map,
            agents=agents,
            max_runtime_seconds=runtime_limit_seconds,
            progress_callback=build_progress_callback(logger, label),
        )
        elapsed_seconds = time.perf_counter() - start
        if solver_result.get("status") == "solved":
            return True, solver_result, elapsed_seconds, None
        return False, solver_result, elapsed_seconds, solver_result.get("status")
    except Exception as exc:  # pragma: no cover
        elapsed_seconds = time.perf_counter() - start
        return False, None, elapsed_seconds, f"exception:{type(exc).__name__}:{exc}"


def run_dynamic_mapping(
    *,
    mapped_loop: list[list[list[Any]]],
    agents: list[dict[str, Any]],
    runtime_limit_seconds: float,
    logger: ExperimentLogger,
    label: str,
) -> tuple[bool, dict[str, Any] | None, float, str | None]:
    start = time.perf_counter()
    try:
        solver_result = solve_time_expanded_mapf_with_cbs(
            mapped_loop=mapped_loop,
            agents=agents,
            max_runtime_seconds=runtime_limit_seconds,
            progress_callback=build_progress_callback(logger, label),
        )
        elapsed_seconds = time.perf_counter() - start
        if solver_result.get("status") == "solved":
            return True, solver_result, elapsed_seconds, None
        return False, solver_result, elapsed_seconds, solver_result.get("status")
    except Exception as exc:  # pragma: no cover
        elapsed_seconds = time.perf_counter() - start
        return False, None, elapsed_seconds, f"exception:{type(exc).__name__}:{exc}"
