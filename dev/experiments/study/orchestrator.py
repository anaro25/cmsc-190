from __future__ import annotations

import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dev.experiments.branch_specs import BranchSpec, get_branch_specs_for_selected_map_configs
from dev.experiments.frame_by_frame_store import MainExperimentFrameByFrameStore
from dev.experiments.study.io_utils import (
    ExperimentLogger,
    format_elapsed_mmss,
    write_csv,
)
from dev.experiments.study.logging_utils import log_branch_header, log_dynamic_state, log_mapping_record
from dev.experiments.study.metrics_data_store import (
    prepare_metrics_data_root,
    write_metrics_data_package,
)
from dev.experiments.study.models import DynamicBranchState, MappingRunRecord, PreparedRunContext
from dev.experiments.study.preparation import (
    prepare_dynamic_branch_state,
    prepare_dynamic_run_context,
    prepare_static_run_context,
)
from dev.experiments.study.runtime import build_mapping_record, run_dynamic_mapping, run_static_mapping
from dev.experiments.study.visualization import render_saved_frame_by_frame_packages
from dev.master_config import to_generate
from dev.mapf.agent_assignment import (
    MAX_ASSIGNMENT_ATTEMPTS,
    MAX_ASSIGNMENT_WALLTIME_SECONDS,
    _iter_free_vertices,
)
from dev.paths import OUTPUTS_MAIN_ROOT


VALID_GENERATION_TARGETS = {"raw_data", "visualization"}
COUNTED_RESULT_CATEGORIES = {"successful", "unfinished"}
MAPPING_NAMES = ("classical", "cyclic")


@dataclass
class SolverAttempt:
    prepared_context: PreparedRunContext
    record: MappingRunRecord
    solver_result: dict[str, Any] | None
    generation_attempts_used: int


@dataclass
class AgentNumberTestResult:
    mapping_name: str
    agent_number: int
    search_step_index: int
    pass_criterion: str
    passed: bool
    failure_reason: str | None
    success_count: int
    counted_attempt_count: int
    invalid_attempt_count: int
    invalid_generation_cap_exhausted: bool
    attempts: list[SolverAttempt]
    successful_attempts: list[SolverAttempt]
    comparison_attempts: list[SolverAttempt]
    trace: list[dict[str, Any]]


@dataclass
class CapacitySearchResult:
    mapping_name: str
    best_agent_number: int
    best_successful_attempts: list[SolverAttempt]
    tested_agent_numbers: list[AgentNumberTestResult]
    search_trace: list[dict[str, Any]]


def _resolve_generation_target() -> str:
    generation_target = str(to_generate)
    if generation_target not in VALID_GENERATION_TARGETS:
        raise ValueError("to_generate must be either 'raw_data' or 'visualization'.")
    return generation_target


def _prepare_run_context(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState | None,
    agent_number: int,
    agent_number_index: int,
    run_index: int,
    seed_base: int,
) -> PreparedRunContext:
    if branch_spec.is_dynamic:
        if dynamic_state is None:
            raise ValueError("dynamic_state is required for dynamic branches")
        return prepare_dynamic_run_context(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            agent_number=agent_number,
            agent_number_index=agent_number_index,
            run_index=run_index,
            seed_base=seed_base,
        )
    return prepare_static_run_context(
        branch_spec=branch_spec,
        agent_number=agent_number,
        agent_number_index=agent_number_index,
        run_index=run_index,
        seed_base=seed_base,
    )


def _execute_mapping(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState | None,
    prepared_context: PreparedRunContext,
    mapping_name: str,
    logger: ExperimentLogger,
) -> tuple[dict[str, Any] | None, float, str]:
    label = f"{mapping_name.title()} {prepared_context.run_configuration.run_config_id}"
    if branch_spec.is_dynamic:
        if dynamic_state is None:
            raise ValueError("dynamic_state is required for dynamic branches")
        mapped_loop = dynamic_state.classical_loop if mapping_name == "classical" else dynamic_state.cyclic_loop
        return run_dynamic_mapping(
            mapped_loop=mapped_loop,
            agents=prepared_context.agents,
            runtime_limit_seconds=branch_spec.runtime_limit_seconds,
            logger=logger,
            label=label,
            solver_suboptimality_factor=branch_spec.solver_suboptimality_factor,
            true_static_shortest_path_distance=branch_spec.true_static_shortest_path_distance,
            tight_time_horizon=branch_spec.tight_time_horizon,
            agent_cohesion_enabled=branch_spec.agent_cohesion_enabled,
        )

    composite_map = prepared_context.classical_map if mapping_name == "classical" else prepared_context.cyclic_map
    if composite_map is None:
        raise ValueError(f"missing {mapping_name} composite map for static branch")
    return run_static_mapping(
        composite_map=composite_map,
        agents=prepared_context.agents,
        runtime_limit_seconds=branch_spec.runtime_limit_seconds,
        logger=logger,
        label=label,
        solver_suboptimality_factor=branch_spec.solver_suboptimality_factor,
        true_static_shortest_path_distance=branch_spec.true_static_shortest_path_distance,
        tight_time_horizon=branch_spec.tight_time_horizon,
        agent_cohesion_enabled=branch_spec.agent_cohesion_enabled,
    )


def _format_invalid_generation_summary(invalid_trace: list[dict[str, Any]]) -> str:
    if not invalid_trace:
        return "none"

    grouped: dict[tuple[str, str], int] = {}
    for item in invalid_trace:
        kind = str(item.get("kind", "invalid"))
        if kind == "setup_failed":
            detail = f"{item.get('error_type', 'Exception')}: {item.get('error_message', '')}"
        else:
            status = item.get("solver_status")
            detail = f"solver_status={status}" if status else kind
        key = (kind, detail)
        grouped[key] = grouped.get(key, 0) + 1

    parts = [f"{kind} x{count} ({detail})" for (kind, detail), count in grouped.items()]
    return "; ".join(parts)


def _log_invalid_generation_summary(
    *,
    logger: ExperimentLogger,
    invalid_trace: list[dict[str, Any]],
    mapping_name: str,
    solver_attempt_index: int,
    cap: int,
) -> None:
    if not invalid_trace:
        return
    logger.log(
        f"      Regeneration summary | mapping={mapping_name} | "
        f"solver_attempt={solver_attempt_index + 1} | "
        f"invalid_generations={len(invalid_trace)}/{cap} | "
        f"details={_format_invalid_generation_summary(invalid_trace)}"
    )


def _count_free_assignment_vertices(composite_map: list[list[Any]] | None) -> int | None:
    if composite_map is None:
        return None
    return sum(1 for _ in _iter_free_vertices(composite_map))


def _log_feasibility_diagnostic(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState | None,
    mapping_name: str,
    agent_number: int,
    logger: ExperimentLogger,
) -> None:
    details = [
        f"N={agent_number}",
        f"mapping={mapping_name}",
        f"start_mode={branch_spec.start_distribution_mode}",
        f"goal_mode={branch_spec.goal_distribution_mode}",
        f"zone_mode={branch_spec.zone_relationship_mode}",
        f"spawn_mode={branch_spec.spawnable_cell_mode}",
        f"setup_generation_cap={branch_spec.setup_generation_attempt_cap_per_solver_attempt}",
        f"assignment_attempt_cap={MAX_ASSIGNMENT_ATTEMPTS}",
        f"assignment_walltime_cap={MAX_ASSIGNMENT_WALLTIME_SECONDS:.1f}s",
    ]

    if dynamic_state is not None:
        free_count = _count_free_assignment_vertices(dynamic_state.assignment_map)
        details.append(f"assignment_free_vertices={free_count}")
        if dynamic_state.allowed_spawn_vertices is not None:
            details.append(f"allowed_spawn_vertices={len(dynamic_state.allowed_spawn_vertices)}")
        if dynamic_state.zone_vertices_by_id:
            zone_counts = {zone_id: len(vertices) for zone_id, vertices in sorted(dynamic_state.zone_vertices_by_id.items())}
            details.append(f"zone_vertices={zone_counts}")
        if dynamic_state.single_target_vertices_by_id:
            single_counts = {zone_id: len(vertices) for zone_id, vertices in sorted(dynamic_state.single_target_vertices_by_id.items())}
            details.append(f"single_target_vertices={single_counts}")
    elif branch_spec.image_path is None:
        details.append("candidate_counts=per generated artificial map")
    else:
        details.append("candidate_counts=per static image run context")

    logger.log("    Feasibility diagnostic | " + " | ".join(details))


def _run_valid_solver_attempt(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState | None,
    mapping_name: str,
    comparison_case: str,
    agent_number: int,
    search_step_index: int,
    solver_attempt_index: int,
    seed_base: int,
    logger: ExperimentLogger,
) -> tuple[SolverAttempt | None, list[dict[str, Any]]]:
    invalid_trace: list[dict[str, Any]] = []
    logged_invalid_count = 0
    cap = int(branch_spec.setup_generation_attempt_cap_per_solver_attempt)
    for generation_attempt_index in range(cap):
        run_index = (
            search_step_index * 100000
            + solver_attempt_index * 1000
            + generation_attempt_index
        )
        logger.log(
            f"      Setup generation attempt {generation_attempt_index + 1}/{cap} | "
            f"mapping={mapping_name} | solver_attempt={solver_attempt_index + 1} | N={agent_number}"
        )
        try:
            prepared_context = _prepare_run_context(
                branch_spec=branch_spec,
                dynamic_state=dynamic_state,
                agent_number=agent_number,
                agent_number_index=search_step_index,
                run_index=run_index,
                seed_base=seed_base,
            )
        except Exception as exc:
            invalid_trace.append(
                {
                    "kind": "setup_failed",
                    "generation_attempt_index": generation_attempt_index + 1,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            logger.log(
                f"      Setup generation failed | mapping={mapping_name} | "
                f"solver_attempt={solver_attempt_index + 1} | "
                f"generation_attempt={generation_attempt_index + 1}/{cap} | "
                f"{type(exc).__name__}: {exc}"
            )
            logged_invalid_count = len(invalid_trace)
            continue

        _log_invalid_generation_summary(
            logger=logger,
            invalid_trace=invalid_trace[logged_invalid_count:],
            mapping_name=mapping_name,
            solver_attempt_index=solver_attempt_index,
            cap=cap,
        )
        logged_invalid_count = len(invalid_trace)
        logger.log("")
        logger.log(
            f"      Solver attempt {solver_attempt_index + 1} | mapping={mapping_name} | "
            f"agent_number={agent_number} | generation_attempt={generation_attempt_index + 1}/{cap}"
        )
        solver_result, elapsed_seconds, solver_status = _execute_mapping(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            prepared_context=prepared_context,
            mapping_name=mapping_name,
            logger=logger,
        )
        record = build_mapping_record(
            run_configuration=prepared_context.run_configuration,
            mapping_name=mapping_name,
            comparison_case=comparison_case,
            runtime_limit_seconds=branch_spec.runtime_limit_seconds,
            solver_name=(solver_result or {}).get("solver_name", branch_spec.solver_name),
            enhanced_cbs_enabled=branch_spec.enhanced_cbs_enabled,
            solver_suboptimality_factor=(solver_result or {}).get(
                "solver_suboptimality_factor",
                branch_spec.solver_suboptimality_factor,
            ),
            solver_result=solver_result,
            elapsed_seconds=elapsed_seconds,
            solver_status=solver_status,
            paired_run=False,
            dynamic=branch_spec.is_dynamic,
        )
        if record.result_category not in COUNTED_RESULT_CATEGORIES:
            invalid_trace.append(
                {
                    "kind": record.result_category,
                    "generation_attempt_index": generation_attempt_index + 1,
                    "solver_status": record.solver_status,
                    "elapsed_seconds": record.time_computation_halted_seconds,
                }
            )
            continue

        log_mapping_record(logger, record)
        return (
            SolverAttempt(
                prepared_context=prepared_context,
                record=record,
                solver_result=solver_result,
                generation_attempts_used=generation_attempt_index + 1,
            ),
            invalid_trace,
        )

    _log_invalid_generation_summary(
        logger=logger,
        invalid_trace=invalid_trace[logged_invalid_count:],
        mapping_name=mapping_name,
        solver_attempt_index=solver_attempt_index,
        cap=cap,
    )
    return None, invalid_trace



def _effective_pass_criterion(branch_spec: BranchSpec, mapping_name: str) -> str:
    configured = str(branch_spec.capacity_pass_criterion)
    valid_criteria = {"solver_success", "temp_cyclic", "temp_pairwise"}
    if configured not in valid_criteria:
        raise ValueError(
            "capacity_pass_criterion must be one of "
            "'solver_success', 'temp_cyclic', or 'temp_pairwise'."
        )
    if configured == "solver_success":
        return "solver_success"
    if configured == "temp_cyclic":
        return "temp_cyclic" if mapping_name == "cyclic" else "solver_success"
    if mapping_name == "classical":
        return "temp_classical"
    return "temp_cyclic"


def _criterion_description(criterion: str, *, required_successes: int, max_attempts: int, time_limit_seconds: float) -> str:
    if criterion == "temp_classical":
        return (
            f"{required_successes}/{max_attempts} temp classical-origin run(s): classical must solve within "
            f"{time_limit_seconds:.0f}s, and cyclic must solve and have lower halted time and lower "
            "conflicts than classical on the same generated setup"
        )
    if criterion == "temp_cyclic":
        return (
            f"{required_successes}/{max_attempts} temp cyclic-origin run(s): cyclic must solve within "
            f"{time_limit_seconds:.0f}s and have lower halted time and lower conflicts than classical "
            "on the same generated setup"
        )
    return f"{required_successes}/{max_attempts} successful within {time_limit_seconds:.0f}s"


def _run_paired_mapping_on_context(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState | None,
    prepared_context: PreparedRunContext,
    mapping_name: str,
    comparison_case: str,
    logger: ExperimentLogger,
) -> SolverAttempt:
    solver_result, elapsed_seconds, solver_status = _execute_mapping(
        branch_spec=branch_spec,
        dynamic_state=dynamic_state,
        prepared_context=prepared_context,
        mapping_name=mapping_name,
        logger=logger,
    )
    record = build_mapping_record(
        run_configuration=prepared_context.run_configuration,
        mapping_name=mapping_name,
        comparison_case=comparison_case,
        runtime_limit_seconds=branch_spec.runtime_limit_seconds,
        solver_name=(solver_result or {}).get("solver_name", branch_spec.solver_name),
        enhanced_cbs_enabled=branch_spec.enhanced_cbs_enabled,
        solver_suboptimality_factor=(solver_result or {}).get(
            "solver_suboptimality_factor",
            branch_spec.solver_suboptimality_factor,
        ),
        solver_result=solver_result,
        elapsed_seconds=elapsed_seconds,
        solver_status=solver_status,
        paired_run=True,
        dynamic=branch_spec.is_dynamic,
    )
    log_mapping_record(logger, record)
    return SolverAttempt(
        prepared_context=prepared_context,
        record=record,
        solver_result=solver_result,
        generation_attempts_used=0,
    )


def _conflict_value_for_comparison(record: MappingRunRecord) -> int | None:
    return record.num_conflicts_detected_at_halt


def _is_cyclic_temp(
    *,
    cyclic_record: MappingRunRecord,
    classical_record: MappingRunRecord,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not cyclic_record.solved_run:
        reasons.append("cyclic_not_successful")
    if classical_record.result_category not in COUNTED_RESULT_CATEGORIES:
        reasons.append(f"classical_not_counted:{classical_record.result_category}")

    cyclic_time = cyclic_record.time_computation_halted_seconds
    classical_time = classical_record.time_computation_halted_seconds
    if not (cyclic_time < classical_time):
        reasons.append("cyclic_time_not_lower")

    cyclic_conflicts = _conflict_value_for_comparison(cyclic_record)
    classical_conflicts = _conflict_value_for_comparison(classical_record)
    if cyclic_conflicts is None or classical_conflicts is None:
        reasons.append("conflicts_unavailable")
    elif not (cyclic_conflicts < classical_conflicts):
        reasons.append("cyclic_conflicts_not_lower")

    return not reasons, reasons


def _classify_failure_reason(
    *,
    criterion: str,
    attempts: list[SolverAttempt],
    invalid_generation_cap_exhausted: bool,
) -> str:
    if not attempts and invalid_generation_cap_exhausted:
        return "setup_unavailable"
    if criterion == "temp_classical":
        if not any(attempt.record.solved_run for attempt in attempts):
            return "classical_solver_fail"
        return "temp_fail"
    if criterion == "temp_cyclic":
        if not any(attempt.record.solved_run for attempt in attempts):
            return "cyclic_solver_fail"
        return "temp_fail"
    return "solver_fail"


def _test_agent_number_for_mapping(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState | None,
    mapping_name: str,
    agent_number: int,
    search_step_index: int,
    seed_base: int,
    logger: ExperimentLogger,
) -> AgentNumberTestResult:
    attempts: list[SolverAttempt] = []
    comparison_attempts: list[SolverAttempt] = []
    successful_attempts: list[SolverAttempt] = []
    trace: list[dict[str, Any]] = []
    invalid_attempt_count = 0
    invalid_generation_cap_exhausted = False
    max_attempts = int(branch_spec.capacity_attempts_per_agent_number)
    required_successes = int(branch_spec.capacity_successful_runs_required)
    criterion = _effective_pass_criterion(branch_spec, mapping_name)

    logger.log("")
    logger.log(
        f"    Testing N={agent_number} for {mapping_name} | "
        f"pass_rule={_criterion_description(criterion, required_successes=required_successes, max_attempts=max_attempts, time_limit_seconds=branch_spec.runtime_limit_seconds)}"
    )
    _log_feasibility_diagnostic(
        branch_spec=branch_spec,
        dynamic_state=dynamic_state,
        mapping_name=mapping_name,
        agent_number=agent_number,
        logger=logger,
    )

    solver_attempt_index = 0
    while solver_attempt_index < max_attempts:
        remaining_attempts_including_current = max_attempts - solver_attempt_index
        if len(successful_attempts) + remaining_attempts_including_current < required_successes:
            break
        if len(successful_attempts) >= required_successes:
            break

        attempt, invalid_trace = _run_valid_solver_attempt(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            mapping_name=mapping_name,
            comparison_case=f"capacity_search_{mapping_name}",
            agent_number=agent_number,
            search_step_index=search_step_index,
            solver_attempt_index=solver_attempt_index,
            seed_base=seed_base,
            logger=logger,
        )
        invalid_attempt_count += len(invalid_trace)
        trace.extend(invalid_trace)
        if attempt is None:
            invalid_generation_cap_exhausted = True
            trace.append(
                {
                    "kind": "generation_cap_exhausted",
                    "solver_attempt_index": solver_attempt_index + 1,
                    "cap": branch_spec.setup_generation_attempt_cap_per_solver_attempt,
                }
            )
            logger.log(
                f"      Generation cap exhausted for one solver attempt | mapping={mapping_name} | "
                f"agent_number={agent_number} | cap={branch_spec.setup_generation_attempt_cap_per_solver_attempt}"
            )
            break

        attempts.append(attempt)
        if criterion in {"temp_classical", "temp_cyclic"}:
            if attempt.record.result_category == "successful":
                comparison_mapping_name = "cyclic" if mapping_name == "classical" else "classical"
                comparison_case = (
                    "temp_capacity_cyclic_comparison"
                    if comparison_mapping_name == "cyclic"
                    else "temp_capacity_classical_comparison"
                )
                logger.log(
                    f"      Temp-capacity comparison | running {comparison_mapping_name} on "
                    f"the same setup before accepting this {mapping_name} success"
                )
                comparison_attempt = _run_paired_mapping_on_context(
                    branch_spec=branch_spec,
                    dynamic_state=dynamic_state,
                    prepared_context=attempt.prepared_context,
                    mapping_name=comparison_mapping_name,
                    comparison_case=comparison_case,
                    logger=logger,
                )
                comparison_attempts.append(comparison_attempt)
                if mapping_name == "cyclic":
                    cyclic_record = attempt.record
                    classical_record = comparison_attempt.record
                else:
                    cyclic_record = comparison_attempt.record
                    classical_record = attempt.record
                temp_pass, reasons = _is_cyclic_temp(
                    cyclic_record=cyclic_record,
                    classical_record=classical_record,
                )
                trace.append(
                    {
                        "kind": "temp_capacity_evaluation",
                        "solver_attempt_index": solver_attempt_index + 1,
                        "primary_mapping_name": mapping_name,
                        "comparison_mapping_name": comparison_mapping_name,
                        "temp_pass": temp_pass,
                        "reasons": reasons,
                        "cyclic_time": cyclic_record.time_computation_halted_seconds,
                        "classical_time": classical_record.time_computation_halted_seconds,
                        "cyclic_conflicts": cyclic_record.num_conflicts_detected_at_halt,
                        "classical_conflicts": classical_record.num_conflicts_detected_at_halt,
                    }
                )
                logger.log(
                    f"      Temp-capacity evaluation | passed={temp_pass} | "
                    f"reasons={','.join(reasons) if reasons else 'none'}"
                )
                if temp_pass:
                    successful_attempts.append(attempt)
            else:
                trace.append(
                    {
                        "kind": "temp_capacity_evaluation_skipped",
                        "solver_attempt_index": solver_attempt_index + 1,
                        "reason": f"{mapping_name}_result_category={attempt.record.result_category}",
                    }
                )
        elif attempt.record.result_category == "successful":
            successful_attempts.append(attempt)
        solver_attempt_index += 1

    passed = len(successful_attempts) >= required_successes
    failure_reason = None if passed else _classify_failure_reason(
        criterion=criterion,
        attempts=attempts,
        invalid_generation_cap_exhausted=invalid_generation_cap_exhausted,
    )
    logger.log(
        f"    Result for N={agent_number} | mapping={mapping_name} | criterion={criterion} | "
        f"passed={passed} | successful={len(successful_attempts)} | counted_attempts={len(attempts)} | "
        f"invalid_regenerated={invalid_attempt_count} | failure_reason={failure_reason or 'none'}"
    )
    logger.log_elapsed(f"Finished tested agent number N={agent_number} for {mapping_name}")
    return AgentNumberTestResult(
        mapping_name=mapping_name,
        agent_number=agent_number,
        search_step_index=search_step_index,
        pass_criterion=criterion,
        passed=passed,
        failure_reason=failure_reason,
        success_count=len(successful_attempts),
        counted_attempt_count=len(attempts),
        invalid_attempt_count=invalid_attempt_count,
        invalid_generation_cap_exhausted=invalid_generation_cap_exhausted,
        attempts=attempts,
        successful_attempts=successful_attempts[:required_successes],
        comparison_attempts=comparison_attempts,
        trace=trace,
    )


def _run_capacity_search(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState | None,
    mapping_name: str,
    seed_base: int,
    logger: ExperimentLogger,
) -> CapacitySearchResult:
    low = 1
    high = int(branch_spec.capacity_agent_upper_bound)
    max_downward_moves = max(0, int(branch_spec.capacity_binary_search_max_downward_moves))
    current_depth = 0
    downward_moves_after_first_success = 0
    has_found_success = False
    best_agent_number = 0
    best_successful_attempts: list[SolverAttempt] = []
    tested_agent_numbers: list[AgentNumberTestResult] = []
    search_trace: list[dict[str, Any]] = []
    search_step_index = 0

    logger.log("")
    logger.log("-" * 88)
    search_criterion = _effective_pass_criterion(branch_spec, mapping_name)
    if search_criterion == "temp_classical":
        search_label = "Temp classical capacity search"
    elif search_criterion == "temp_cyclic":
        search_label = "Temp cyclic capacity search"
    else:
        search_label = "Solver capacity search"
    logger.log(
        f"{search_label} started | mapping={mapping_name} | criterion={search_criterion} | range=1..{high} | "
        f"max_downward_moves_after_first_success={max_downward_moves}"
    )
    logger.log("-" * 88)

    while low <= high:
        midpoint = (low + high) // 2
        search_step_index += 1
        test_result = _test_agent_number_for_mapping(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            mapping_name=mapping_name,
            agent_number=midpoint,
            search_step_index=search_step_index,
            seed_base=seed_base,
            logger=logger,
        )
        tested_agent_numbers.append(test_result)
        search_trace.append(
            {
                "step": search_step_index,
                "depth_from_root": current_depth,
                "downward_moves_after_first_success": downward_moves_after_first_success,
                "limit_active": has_found_success,
                "low_before": low,
                "high_before": high,
                "tested_agent_number": midpoint,
                "pass_criterion": test_result.pass_criterion,
                "passed": test_result.passed,
                "failure_reason": test_result.failure_reason,
                "success_count": test_result.success_count,
                "counted_attempt_count": test_result.counted_attempt_count,
                "invalid_attempt_count": test_result.invalid_attempt_count,
            }
        )

        if test_result.passed:
            best_agent_number = midpoint
            best_successful_attempts = test_result.successful_attempts
            has_found_success = True

        if has_found_success and downward_moves_after_first_success >= max_downward_moves:
            logger.log(
                f"    N={midpoint} {'passed' if test_result.passed else 'failed'} "
                f"(reason={test_result.failure_reason or 'none'}); "
                f"binary-search downward-move limit after first success reached ({max_downward_moves}). "
                "Stopping without descending to another child."
            )
            break

        if test_result.passed:
            low = midpoint + 1
            logger.log(f"    N={midpoint} passed; moving to right child/search interval {low}..{high}.")
        else:
            high = midpoint - 1
            logger.log(
                f"    N={midpoint} failed (reason={test_result.failure_reason or 'unknown'}); "
                f"moving to left child/search interval {low}..{high}."
            )
        current_depth += 1
        if has_found_success:
            downward_moves_after_first_success += 1

    logger.log(
        f"{search_label} finished | mapping={mapping_name} | criterion={search_criterion} | "
        f"N_max={best_agent_number} | saved_successful_runs={len(best_successful_attempts)} | "
        f"tested_agent_numbers={len(tested_agent_numbers)}"
    )
    return CapacitySearchResult(
        mapping_name=mapping_name,
        best_agent_number=best_agent_number,
        best_successful_attempts=best_successful_attempts,
        tested_agent_numbers=tested_agent_numbers,
        search_trace=search_trace,
    )


def _run_comparative_attempts(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState | None,
    baseline_mapping_name: str,
    comparative_mapping_name: str,
    capacity_label: str,
    baseline_successful_attempts: list[SolverAttempt],
    logger: ExperimentLogger,
) -> list[SolverAttempt]:
    comparative_attempts: list[SolverAttempt] = []
    logger.log("")
    logger.log(
        f"Comparative runs started | capacity_point={capacity_label} | "
        f"baseline={baseline_mapping_name} | comparative={comparative_mapping_name} | "
        f"paired_initial_conditions={len(baseline_successful_attempts)}"
    )
    for paired_index, baseline_attempt in enumerate(baseline_successful_attempts, start=1):
        prepared_context = baseline_attempt.prepared_context
        logger.log("")
        logger.log(
            f"    Comparative paired run {paired_index} | "
            f"{comparative_mapping_name} on {baseline_mapping_name} capacity initial conditions"
        )
        solver_result, elapsed_seconds, solver_status = _execute_mapping(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            prepared_context=prepared_context,
            mapping_name=comparative_mapping_name,
            logger=logger,
        )
        record = build_mapping_record(
            run_configuration=prepared_context.run_configuration,
            mapping_name=comparative_mapping_name,
            comparison_case=f"comparative_{comparative_mapping_name}_at_{capacity_label}",
            runtime_limit_seconds=branch_spec.runtime_limit_seconds,
            solver_name=(solver_result or {}).get("solver_name", branch_spec.solver_name),
            enhanced_cbs_enabled=branch_spec.enhanced_cbs_enabled,
            solver_suboptimality_factor=(solver_result or {}).get(
                "solver_suboptimality_factor",
                branch_spec.solver_suboptimality_factor,
            ),
            solver_result=solver_result,
            elapsed_seconds=elapsed_seconds,
            solver_status=solver_status,
            paired_run=True,
            dynamic=branch_spec.is_dynamic,
        )
        log_mapping_record(logger, record)
        comparative_attempts.append(
            SolverAttempt(
                prepared_context=prepared_context,
                record=record,
                solver_result=solver_result,
                generation_attempts_used=0,
            )
        )
    return comparative_attempts


def _metric_value(record: MappingRunRecord, metric: str) -> float | int | None:
    if metric == "time":
        return record.time_computation_halted_seconds
    if metric == "conflicts":
        return record.num_conflicts_detected_at_halt
    if metric == "path":
        if not record.solved_run:
            return None
        return record.total_path_length
    raise ValueError(f"Unsupported metric: {metric}")


def _average_metric(records: list[MappingRunRecord], metric: str) -> float | None:
    values: list[float] = []
    for record in records:
        value = _metric_value(record, metric)
        if value is None:
            if metric == "path":
                return None
            continue
        values.append(float(value))
    if not values:
        return None
    return sum(values) / len(values)


def _format_value(value: float | int | None, *, decimals: int = 2) -> str:
    if value is None:
        return "null"
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.{decimals}f}"


def _format_path_value(record: MappingRunRecord) -> str:
    if not record.solved_run:
        return "null (unfinished)"
    return _format_value(record.total_path_length)


def _format_path_average(records: list[MappingRunRecord]) -> str:
    if not records:
        return "null (unavailable)"
    if any(not record.solved_run or record.total_path_length is None for record in records):
        return "null (incomplete successful runs)"
    return _format_value(_average_metric(records, "path"))


def _evaluate_lower_is_better(cyclic_average: float | None, classical_average: float | None) -> str:
    if cyclic_average is None or classical_average is None:
        return "TBD"
    tolerance = 1e-9
    if abs(cyclic_average - classical_average) <= tolerance:
        return "SAME"
    if cyclic_average < classical_average:
        return "CYCLIC IS BETTER"
    return "CLASSICAL IS BETTER"


def _records_from_attempts(attempts: list[SolverAttempt]) -> list[MappingRunRecord]:
    return [attempt.record for attempt in attempts]


def _append_run_values(
    lines: list[str],
    *,
    records: list[MappingRunRecord],
    metric: str,
    successful_label: bool,
) -> None:
    for index, record in enumerate(records, start=1):
        if successful_label:
            prefix = "Successful run" if record.solved_run else "Run"
        else:
            prefix = "Run"
        if metric == "path":
            value_text = _format_path_value(record)
        else:
            value_text = _format_value(_metric_value(record, metric))
        lines.append(f"                    {prefix} {index}: {value_text}")

    if len(records) > 1:
        if metric == "path":
            aggregate_text = _format_path_average(records)
        else:
            aggregate_text = _format_value(_average_metric(records, metric))
        lines.append(f"                    Average: {aggregate_text}")


def _append_metric_block(
    lines: list[str],
    *,
    metric_title: str,
    baseline_title: str,
    comparative_title: str,
    baseline_records: list[MappingRunRecord],
    comparative_records: list[MappingRunRecord],
    metric: str,
) -> None:
    lines.append(f"            {metric_title}")
    lines.append(f"                {baseline_title}")
    _append_run_values(
        lines,
        records=baseline_records,
        metric=metric,
        successful_label=True,
    )

    lines.append(f"                {comparative_title}")
    _append_run_values(
        lines,
        records=comparative_records,
        metric=metric,
        successful_label=False,
    )
    lines.append("")


def _append_evaluation_block(
    lines: list[str],
    *,
    baseline_records: list[MappingRunRecord],
    comparative_records: list[MappingRunRecord],
) -> None:
    classical_records = [record for record in baseline_records + comparative_records if record.mapping_name == "classical"]
    cyclic_records = [record for record in baseline_records + comparative_records if record.mapping_name == "cyclic"]
    time_eval = _evaluate_lower_is_better(
        _average_metric(cyclic_records, "time"),
        _average_metric(classical_records, "time"),
    )
    conflicts_eval = _evaluate_lower_is_better(
        _average_metric(cyclic_records, "conflicts"),
        _average_metric(classical_records, "conflicts"),
    )
    lines.append("            Condensed evaluation")
    lines.append("                Time computation halted")
    lines.append(f"                    Evaluation: {time_eval}")
    lines.append("                Number of conflicts at halt")
    lines.append(f"                    Evaluation: {conflicts_eval}")
    lines.append("")


def _build_configuration_log_text(
    *,
    branch_spec: BranchSpec,
    classical_search: CapacitySearchResult,
    cyclic_search: CapacitySearchResult,
    cyclic_at_classical: list[SolverAttempt],
    classical_at_cyclic: list[SolverAttempt],
) -> str:
    category_title = branch_spec.category_map_type.replace("_", " ").title()
    lines: list[str] = []
    lines.append(category_title)
    lines.append(f"    {branch_spec.layout_label}")
    lines.append(f"        N_temp_classical_capacity: {classical_search.best_agent_number}")
    lines.append(f"        N_temp_cyclic_capacity: {cyclic_search.best_agent_number}")
    lines.append("        Temp capacity criterion: the primary mapping must solve, and cyclic must solve and have lower halted time and lower conflicts than classical on the same setup")
    lines.append("")

    classical_baseline = _records_from_attempts(classical_search.best_successful_attempts)
    cyclic_comparative = _records_from_attempts(cyclic_at_classical)
    cyclic_baseline = _records_from_attempts(cyclic_search.best_successful_attempts)
    classical_comparative = _records_from_attempts(classical_at_cyclic)

    lines.append("        Under temp classical capacity (N_temp_classical_capacity)")
    _append_metric_block(
        lines,
        metric_title="Time computation halted (secs)",
        baseline_title="Stats of classical at temp classical capacity",
        comparative_title="Stats of cyclic at temp classical capacity",
        baseline_records=classical_baseline,
        comparative_records=cyclic_comparative,
        metric="time",
    )
    _append_metric_block(
        lines,
        metric_title="Number of conflicts at halt",
        baseline_title="Stats of classical at temp classical capacity",
        comparative_title="Stats of cyclic at temp classical capacity",
        baseline_records=classical_baseline,
        comparative_records=cyclic_comparative,
        metric="conflicts",
    )
    _append_metric_block(
        lines,
        metric_title="Total path length",
        baseline_title="Stats of classical at temp classical capacity",
        comparative_title="Stats of cyclic at temp classical capacity",
        baseline_records=classical_baseline,
        comparative_records=cyclic_comparative,
        metric="path",
    )
    _append_evaluation_block(
        lines,
        baseline_records=classical_baseline,
        comparative_records=cyclic_comparative,
    )

    lines.append("        Under temp cyclic capacity (N_temp_cyclic_capacity)")
    _append_metric_block(
        lines,
        metric_title="Time computation halted (secs)",
        baseline_title="Stats of cyclic at temp cyclic capacity",
        comparative_title="Stats of classical at temp cyclic capacity",
        baseline_records=cyclic_baseline,
        comparative_records=classical_comparative,
        metric="time",
    )
    _append_metric_block(
        lines,
        metric_title="Number of conflicts at halt",
        baseline_title="Stats of cyclic at temp cyclic capacity",
        comparative_title="Stats of classical at temp cyclic capacity",
        baseline_records=cyclic_baseline,
        comparative_records=classical_comparative,
        metric="conflicts",
    )
    _append_metric_block(
        lines,
        metric_title="Total path length",
        baseline_title="Stats of cyclic at temp cyclic capacity",
        comparative_title="Stats of classical at temp cyclic capacity",
        baseline_records=cyclic_baseline,
        comparative_records=classical_comparative,
        metric="path",
    )
    _append_evaluation_block(
        lines,
        baseline_records=cyclic_baseline,
        comparative_records=classical_comparative,
    )
    return "\n".join(lines).rstrip() + "\n"


def _attempt_to_summary(attempt: SolverAttempt) -> dict[str, Any]:
    record = attempt.record
    return {
        "generation_attempts_used": attempt.generation_attempts_used,
        "run_configuration": attempt.prepared_context.run_configuration.to_dict(),
        "record": record.to_dict(),
        "solver_status": record.solver_status,
        "result_category": record.result_category,
        "solved_run": record.solved_run,
        "time_computation_halted_seconds": record.time_computation_halted_seconds,
        "num_conflicts_detected_at_halt": record.num_conflicts_detected_at_halt,
        "total_path_length": record.total_path_length if record.solved_run else None,
    }


def _test_to_summary(test_result: AgentNumberTestResult) -> dict[str, Any]:
    return {
        "mapping_name": test_result.mapping_name,
        "agent_number": test_result.agent_number,
        "search_step_index": test_result.search_step_index,
        "pass_criterion": test_result.pass_criterion,
        "passed": test_result.passed,
        "failure_reason": test_result.failure_reason,
        "success_count": test_result.success_count,
        "counted_attempt_count": test_result.counted_attempt_count,
        "invalid_attempt_count": test_result.invalid_attempt_count,
        "invalid_generation_cap_exhausted": test_result.invalid_generation_cap_exhausted,
        "attempts": [_attempt_to_summary(attempt) for attempt in test_result.attempts],
        "successful_attempts": [_attempt_to_summary(attempt) for attempt in test_result.successful_attempts],
        "comparison_attempts": [_attempt_to_summary(attempt) for attempt in test_result.comparison_attempts],
        "trace": test_result.trace,
    }


def _search_to_summary(search_result: CapacitySearchResult) -> dict[str, Any]:
    return {
        "mapping_name": search_result.mapping_name,
        "best_agent_number": search_result.best_agent_number,
        "best_successful_attempts": [_attempt_to_summary(attempt) for attempt in search_result.best_successful_attempts],
        "search_trace": search_result.search_trace,
        "tested_agent_numbers": [_test_to_summary(test) for test in search_result.tested_agent_numbers],
    }


def _dynamic_state_metadata(dynamic_state: DynamicBranchState | None) -> dict[str, Any] | None:
    if dynamic_state is None:
        return None
    return {
        "map_identifier": dynamic_state.map_identifier,
        "schedule_seed": dynamic_state.schedule_seed,
        "generation_mode": dynamic_state.generation_mode,
        "static_rows": len(dynamic_state.static_matrix),
        "static_cols": len(dynamic_state.static_matrix[0]) if dynamic_state.static_matrix else 0,
        "dynamic_loop_length": len(dynamic_state.dynamic_loop_frames),
    }


def _compute_single_configuration(
    *,
    branch_spec: BranchSpec,
    seed_base: int,
    logger: ExperimentLogger,
) -> dict[str, Any]:
    logger.log("")
    logger.log("=" * 88)
    logger.log(f"Configuration started: {branch_spec.display_name} ({branch_spec.map_type})")
    logger.log("=" * 88)
    log_branch_header(logger, branch_spec)

    metrics_inspection_dir = (
        OUTPUTS_MAIN_ROOT
        / "metrics_data_inspection"
        / branch_spec.data_log_category_dir_name
    )
    metrics_inspection_dir.mkdir(parents=True, exist_ok=True)
    data_log_path = metrics_inspection_dir / f"{branch_spec.data_log_file_stem}_evaluation.xml"
    obsolete_raw_json_path = metrics_inspection_dir / f"{branch_spec.data_log_file_stem}_raw_data.json"
    if obsolete_raw_json_path.is_file():
        obsolete_raw_json_path.unlink()
        logger.log(f"Removed obsolete configuration raw-data JSON: {obsolete_raw_json_path}")

    dynamic_state: DynamicBranchState | None = None
    if branch_spec.is_dynamic:
        logger.log("Preparing shared dynamic map state for this layout configuration...")
        dynamic_state = prepare_dynamic_branch_state(
            branch_spec,
            seed_base=seed_base,
            logger=logger,
        )
        log_dynamic_state(logger, branch_spec, dynamic_state)

    classical_search = _run_capacity_search(
        branch_spec=branch_spec,
        dynamic_state=dynamic_state,
        mapping_name="classical",
        seed_base=seed_base,
        logger=logger,
    )
    cyclic_search = _run_capacity_search(
        branch_spec=branch_spec,
        dynamic_state=dynamic_state,
        mapping_name="cyclic",
        seed_base=seed_base,
        logger=logger,
    )

    cyclic_at_classical = _run_comparative_attempts(
        branch_spec=branch_spec,
        dynamic_state=dynamic_state,
        baseline_mapping_name="classical",
        comparative_mapping_name="cyclic",
        capacity_label="temp_classical_capacity",
        baseline_successful_attempts=classical_search.best_successful_attempts,
        logger=logger,
    )
    classical_at_cyclic = _run_comparative_attempts(
        branch_spec=branch_spec,
        dynamic_state=dynamic_state,
        baseline_mapping_name="cyclic",
        comparative_mapping_name="classical",
        capacity_label="temp_cyclic_capacity",
        baseline_successful_attempts=cyclic_search.best_successful_attempts,
        logger=logger,
    )

    data_log_text = _build_configuration_log_text(
        branch_spec=branch_spec,
        classical_search=classical_search,
        cyclic_search=cyclic_search,
        cyclic_at_classical=cyclic_at_classical,
        classical_at_cyclic=classical_at_cyclic,
    )
    data_log_path.write_text(data_log_text, encoding="utf-8")

    raw_payload = {
        "branch_spec": branch_spec.to_dict(),
        "dynamic_state_metadata": _dynamic_state_metadata(dynamic_state),
        "capacity_search": {
            "classical": _search_to_summary(classical_search),
            "cyclic": _search_to_summary(cyclic_search),
        },
        "comparative_runs": {
            "cyclic_at_temp_classical_capacity": [_attempt_to_summary(attempt) for attempt in cyclic_at_classical],
            "classical_at_temp_cyclic_capacity": [_attempt_to_summary(attempt) for attempt in classical_at_cyclic],
        },
        "data_log_path": str(data_log_path),
    }
    metrics_package_summary = write_metrics_data_package(
        branch_spec=branch_spec,
        payload=raw_payload,
        metrics_data_root=OUTPUTS_MAIN_ROOT / "metrics_data",
    )
    metrics_data_dir = Path(metrics_package_summary["metrics_data_dir"])
    metrics_csv_path = Path(metrics_package_summary["primary_results_csv_path"])

    frame_by_frame_store = MainExperimentFrameByFrameStore(branch_spec)
    classical_selected_attempt = (
        classical_search.best_successful_attempts[-1]
        if classical_search.best_successful_attempts
        else None
    )
    cyclic_selected_attempt = (
        cyclic_search.best_successful_attempts[-1]
        if cyclic_search.best_successful_attempts
        else None
    )
    frame_by_frame_summary = frame_by_frame_store.save_selected_runs(
        classical_attempt=classical_selected_attempt,
        cyclic_attempt=cyclic_selected_attempt,
        dynamic_state=dynamic_state,
    )

    logger.log(f"Detailed configuration/evaluation log written: {data_log_path}")
    logger.log(f"Results-ready metrics CSV written: {metrics_csv_path}")
    logger.log(f"Metrics package JSON written: {metrics_package_summary['package_json_path']}")
    logger.log(f"Metrics reader guide written: {metrics_package_summary['reader_guide_path']}")
    logger.log(
        "Designated frame-by-frame runs written | "
        f"count={frame_by_frame_summary.get('saved_run_count', 0)} | "
        f"root={frame_by_frame_summary.get('frame_by_frame_root')}"
    )
    logger.log_elapsed(f"Configuration completed: {branch_spec.map_type}")

    return {
        "map_type": branch_spec.map_type,
        "category_map_type": branch_spec.category_map_type,
        "layout_key": branch_spec.layout_key,
        "n_temp_classical_capacity": classical_search.best_agent_number,
        "n_temp_cyclic_capacity": cyclic_search.best_agent_number,
        "n_classical_max": classical_search.best_agent_number,
        "n_cyclic_max": cyclic_search.best_agent_number,
        "data_log_path": str(data_log_path),
        "metrics_data_dir": str(metrics_data_dir),
        "metrics_data_path": str(metrics_csv_path),
        "metrics_package_path": metrics_package_summary["package_json_path"],
        "metrics_reader_guide_path": metrics_package_summary["reader_guide_path"],
        "metrics_written_files": metrics_package_summary["written_files"],
        "frame_by_frame_root": frame_by_frame_summary.get("frame_by_frame_root"),
        "frame_by_frame_manifest_path": frame_by_frame_summary.get("manifest_path"),
        "frame_by_frame_saved_run_count": frame_by_frame_summary.get("saved_run_count", 0),
    }



def _read_line_with_timeout(prompt: str, timeout_seconds: float) -> str | None:
    """Read one console line with a timeout.

    Returns None when no complete response is available before the timeout,
    or when stdin is not interactive. This keeps unattended experiment runs
    from blocking forever at the between-config prompt.
    """
    timeout_seconds = max(0.0, float(timeout_seconds))
    print(prompt, end="", flush=True)

    if timeout_seconds <= 0.0 or not sys.stdin.isatty():
        print()
        return None

    if sys.platform.startswith("win"):
        try:
            import msvcrt
        except ImportError:
            print()
            return None

        buffer: list[str] = []
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if msvcrt.kbhit():
                char = msvcrt.getwch()
                if char in {"\r", "\n"}:
                    print()
                    return "".join(buffer)
                if char == "\003":
                    raise KeyboardInterrupt
                if char in {"\b", "\x7f"}:
                    if buffer:
                        buffer.pop()
                        print("\b \b", end="", flush=True)
                    continue
                buffer.append(char)
                print(char, end="", flush=True)
            time.sleep(0.05)

        print()
        return None

    try:
        import select

        readable, _, _ = select.select([sys.stdin], [], [], timeout_seconds)
    except (OSError, ValueError):
        print()
        return None

    if not readable:
        print()
        return None

    line = sys.stdin.readline()
    if line == "":
        return None
    return line.rstrip("\r\n")


def _prompt_continue_to_next_map_config(
    *,
    logger: ExperimentLogger,
    completed_index: int,
    total_count: int,
    next_branch_spec: BranchSpec,
) -> bool:
    timeout_seconds = next_branch_spec.prompt_before_next_map_config_timeout_seconds
    prompt = (
        "\n"
        f"Completed map config {completed_index}/{total_count}. "
        f"Next: {next_branch_spec.display_name}.\n"
        f"Enter 1 to continue, or 0 to terminate early "
        f"(auto-continues after {timeout_seconds:g} seconds): "
    )
    choice = _read_line_with_timeout(prompt, timeout_seconds)

    if choice is None or not choice.strip():
        logger.log(
            f"No continue/terminate response after map config {completed_index}/{total_count} "
            f"within {timeout_seconds:g} seconds. Continuing to next map config by default."
        )
        return True

    choice = choice.strip()
    if choice == "1":
        logger.log(
            f"User prompt response after map config {completed_index}/{total_count}: "
            "1 -> continuing to next map config."
        )
        return True
    if choice == "0":
        logger.log(
            f"User prompt response after map config {completed_index}/{total_count}: "
            "0 -> terminating early."
        )
        return False

    print("Invalid entry. Defaulting to continue.")
    logger.log(
        f"Invalid continue/terminate response after map config {completed_index}/{total_count}: "
        f"{choice!r}. Continuing to next map config by default."
    )
    return True





def _generate_single_configuration_visualizations(
    *,
    branch_spec: BranchSpec,
    logger: ExperimentLogger,
) -> dict[str, Any]:
    frame_by_frame_store = MainExperimentFrameByFrameStore(branch_spec)
    packages = frame_by_frame_store.load_packages()
    visualization_root = (
        OUTPUTS_MAIN_ROOT
        / "visualization"
        / branch_spec.data_log_category_dir_name
        / branch_spec.data_log_file_stem
    )
    logger.log(
        "Loaded saved frame-by-frame packages for Pillow visualization generation | "
        f"count={len(packages)} | root={frame_by_frame_store.config_root}"
    )
    summary = render_saved_frame_by_frame_packages(
        packages=packages,
        output_root=visualization_root,
        logger=logger,
    )
    return {
        "map_type": branch_spec.map_type,
        "frame_by_frame_root": str(frame_by_frame_store.config_root),
        "frame_by_frame_manifest_path": str(frame_by_frame_store.manifest_path),
        "visualization_root": str(visualization_root),
        "visualization_summary": summary,
    }


def _selected_map_config_terminal_log_path(
    *,
    branch_spec: BranchSpec,
    generation_target: str,
) -> Path:
    return (
        OUTPUTS_MAIN_ROOT
        / "terminal_logs"
        / branch_spec.data_log_category_dir_name
        / branch_spec.data_log_file_stem
        / f"{generation_target}.log"
    )


def run_selected_experiment(
    selected_map_configs: list[str] | tuple[str, ...] | str,
    *,
    seed_base: int | None = None,
    program_start_time: float | None = None,
) -> dict[str, Any]:
    generation_target = _resolve_generation_target()
    branch_specs = get_branch_specs_for_selected_map_configs(selected_map_configs)
    if not branch_specs:
        raise ValueError("No map configurations were selected in SELECTED_MAP_CONFIGS.")

    run_start_time = time.perf_counter() if program_start_time is None else program_start_time
    terminal_logs_root = OUTPUTS_MAIN_ROOT / "terminal_logs"
    terminal_logs_root.mkdir(parents=True, exist_ok=True)

    metrics_data_root = OUTPUTS_MAIN_ROOT / "metrics_data"
    metrics_root_summary: dict[str, Any] | None = None
    if generation_target == "raw_data":
        metrics_root_summary = prepare_metrics_data_root(metrics_data_root)

    metrics_inspection_root = OUTPUTS_MAIN_ROOT / "metrics_data_inspection"
    metrics_inspection_root.mkdir(parents=True, exist_ok=True)
    removed_general_summaries: list[str] = []
    for obsolete_summary in metrics_inspection_root.glob("selected_map_configs_*_summary.json"):
        if obsolete_summary.is_file():
            obsolete_summary.unlink()
            removed_general_summaries.append(str(obsolete_summary))

    print("=" * 88, flush=True)
    print("Selected exact main-experiment map configurations:", flush=True)
    for index, branch_spec in enumerate(branch_specs, start=1):
        print(f"  {index}. {branch_spec.map_type} — {branch_spec.display_name}", flush=True)
    print(f"to_generate: {generation_target}", flush=True)
    print(f"Map configurations to process: {len(branch_specs)}", flush=True)
    print(
        f"Metrics-data-inspection root: {OUTPUTS_MAIN_ROOT / 'metrics_data_inspection'}",
        flush=True,
    )
    print(f"Metrics-data root: {OUTPUTS_MAIN_ROOT / 'metrics_data'}", flush=True)
    print(f"Frame-by-frame root: {OUTPUTS_MAIN_ROOT / 'frame_by_frame'}", flush=True)
    print(f"Terminal-log root: {terminal_logs_root}", flush=True)
    removed_general_files = list(removed_general_summaries)
    if metrics_root_summary is not None:
        print(
            f"Project-level data dictionary: {metrics_root_summary['data_dictionary_path']}",
            flush=True,
        )
        removed_general_files.extend(metrics_root_summary.get("removed_obsolete_files", []))
    if removed_general_files:
        print(f"Removed obsolete project-level output files: {len(removed_general_files)}", flush=True)
    print("=" * 88, flush=True)

    summaries: list[dict[str, Any]] = []
    terminal_log_paths: list[str] = []
    terminated_early = False
    for branch_index, branch_spec in enumerate(branch_specs, start=1):
        terminal_log_path = _selected_map_config_terminal_log_path(
            branch_spec=branch_spec,
            generation_target=generation_target,
        )
        logger = ExperimentLogger(terminal_log_path, start_time=run_start_time)
        terminal_log_paths.append(str(terminal_log_path))

        logger.log("=" * 88)
        logger.log(
            f"Selected exact main-experiment map configuration "
            f"{branch_index} of {len(branch_specs)}:"
        )
        logger.log(f"  {branch_spec.map_type} — {branch_spec.display_name}")
        logger.log(f"to_generate: {generation_target}")
        logger.log(
            f"Metrics-data-inspection root: "
            f"{OUTPUTS_MAIN_ROOT / 'metrics_data_inspection'}"
        )
        logger.log(f"Metrics-data root: {OUTPUTS_MAIN_ROOT / 'metrics_data'}")
        logger.log(f"Frame-by-frame root: {OUTPUTS_MAIN_ROOT / 'frame_by_frame'}")
        logger.log(f"Terminal log: {terminal_log_path}")
        logger.log("=" * 88)

        if generation_target == "raw_data":
            resolved_seed_base = branch_spec.seed_base if seed_base is None else seed_base
            summary = _compute_single_configuration(
                branch_spec=branch_spec,
                seed_base=resolved_seed_base,
                logger=logger,
            )
        elif generation_target == "visualization":
            summary = _generate_single_configuration_visualizations(branch_spec=branch_spec, logger=logger)
        else:
            raise ValueError(f"Unsupported generation target: {generation_target}")

        summary = dict(summary)
        summary["terminal_log_path"] = str(terminal_log_path)
        summaries.append(summary)
        logger.log("")
        logger.log_elapsed(f"{branch_spec.map_type} {generation_target} finished.")

        if branch_index < len(branch_specs) and branch_spec.prompt_before_next_map_config:
            if not _prompt_continue_to_next_map_config(
                logger=logger,
                completed_index=branch_index,
                total_count=len(branch_specs),
                next_branch_spec=branch_specs[branch_index],
            ):
                terminated_early = True
                break

    elapsed_seconds = time.perf_counter() - run_start_time
    print(
        f"[Elapsed: {format_elapsed_mmss(elapsed_seconds)}] "
        "Selected main-experiment map configurations finished.",
        flush=True,
    )

    return {
        "selected_map_configs": [branch_spec.map_type for branch_spec in branch_specs],
        "generation_target": generation_target,
        "output_root": str(OUTPUTS_MAIN_ROOT),
        "terminal_logs_root": str(terminal_logs_root),
        "terminal_log_paths": terminal_log_paths,
        "log_path": terminal_log_paths[0] if len(terminal_log_paths) == 1 else None,
        "map_configurations": summaries,
        "terminated_early": terminated_early,
    }
