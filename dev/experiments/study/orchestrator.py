from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dev.experiments.branch_specs import BranchSpec, get_branch_specs_for_selected_map_type
from dev.experiments.study.io_utils import ExperimentLogger, write_json
from dev.experiments.study.logging_utils import log_branch_header, log_dynamic_state, log_mapping_record
from dev.experiments.study.models import DynamicBranchState, MappingRunRecord, PreparedRunContext, VisualizationCandidate
from dev.experiments.study.preparation import (
    prepare_dynamic_branch_state,
    prepare_dynamic_run_context,
    prepare_static_run_context,
)
from dev.experiments.study.runtime import build_mapping_record, run_dynamic_mapping, run_static_mapping
from dev.master_config import to_generate
from dev.paths import OUTPUTS_MAIN_EXPERIMENT_ROOT


VALID_GENERATION_TARGETS = {"raw_data", "graphs", "visualization"}
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
    passed: bool
    success_count: int
    counted_attempt_count: int
    invalid_attempt_count: int
    invalid_generation_cap_exhausted: bool
    attempts: list[SolverAttempt]
    successful_attempts: list[SolverAttempt]
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
        raise ValueError("to_generate must be one of 'raw_data', 'graphs', or 'visualization'.")
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
    cap = int(branch_spec.setup_generation_attempt_cap_per_solver_attempt)
    for generation_attempt_index in range(cap):
        run_index = (
            search_step_index * 100000
            + solver_attempt_index * 1000
            + generation_attempt_index
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
                f"      setup_failed regenerated | mapping={mapping_name} | "
                f"solver_attempt={solver_attempt_index + 1} | "
                f"generation_attempt={generation_attempt_index + 1}/{cap} | "
                f"{type(exc).__name__}: {exc}"
            )
            continue

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
            logger.log(
                f"      {record.result_category} regenerated | mapping={mapping_name} | "
                f"solver_attempt={solver_attempt_index + 1} | "
                f"generation_attempt={generation_attempt_index + 1}/{cap} | "
                f"solver_status={record.solver_status}"
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

    return None, invalid_trace


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
    successful_attempts: list[SolverAttempt] = []
    trace: list[dict[str, Any]] = []
    invalid_attempt_count = 0
    invalid_generation_cap_exhausted = False
    max_attempts = int(branch_spec.capacity_attempts_per_agent_number)
    required_successes = int(branch_spec.capacity_successful_runs_required)

    logger.log(
        f"    Testing N={agent_number} for {mapping_name} | "
        f"pass_rule={required_successes}/{max_attempts} successful within {branch_spec.runtime_limit_seconds:.0f}s"
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
        if attempt.record.result_category == "successful":
            successful_attempts.append(attempt)
        solver_attempt_index += 1

    passed = len(successful_attempts) >= required_successes
    logger.log(
        f"    Result for N={agent_number} | mapping={mapping_name} | "
        f"passed={passed} | successful={len(successful_attempts)} | counted_attempts={len(attempts)} | "
        f"invalid_regenerated={invalid_attempt_count}"
    )
    return AgentNumberTestResult(
        mapping_name=mapping_name,
        agent_number=agent_number,
        search_step_index=search_step_index,
        passed=passed,
        success_count=len(successful_attempts),
        counted_attempt_count=len(attempts),
        invalid_attempt_count=invalid_attempt_count,
        invalid_generation_cap_exhausted=invalid_generation_cap_exhausted,
        attempts=attempts,
        successful_attempts=successful_attempts[:required_successes],
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
    best_agent_number = 0
    best_successful_attempts: list[SolverAttempt] = []
    tested_agent_numbers: list[AgentNumberTestResult] = []
    search_trace: list[dict[str, Any]] = []
    search_step_index = 0

    logger.log("")
    logger.log("-" * 88)
    logger.log(f"Capacity search started | mapping={mapping_name} | range=1..{high}")
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
                "low_before": low,
                "high_before": high,
                "tested_agent_number": midpoint,
                "passed": test_result.passed,
                "success_count": test_result.success_count,
                "counted_attempt_count": test_result.counted_attempt_count,
                "invalid_attempt_count": test_result.invalid_attempt_count,
            }
        )
        if test_result.passed:
            best_agent_number = midpoint
            best_successful_attempts = test_result.successful_attempts
            low = midpoint + 1
            logger.log(f"    N={midpoint} passed; moving to right child/search interval {low}..{high}.")
        else:
            high = midpoint - 1
            logger.log(f"    N={midpoint} failed; moving to left child/search interval {low}..{high}.")

    logger.log(
        f"Capacity search finished | mapping={mapping_name} | "
        f"N_max={best_agent_number} | saved_successful_runs={len(best_successful_attempts)}"
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
    for index, record in enumerate(baseline_records, start=1):
        prefix = "Successful run" if record.solved_run else "Run"
        if metric == "path":
            value_text = _format_path_value(record)
        else:
            value_text = _format_value(_metric_value(record, metric))
        lines.append(f"                    {prefix} {index}: {value_text}")
    if metric == "path":
        average_text = _format_path_average(baseline_records)
    else:
        average_text = _format_value(_average_metric(baseline_records, metric))
    lines.append(f"                    Average: {average_text}")

    lines.append(f"                {comparative_title}")
    for index, record in enumerate(comparative_records, start=1):
        if metric == "path":
            value_text = _format_path_value(record)
        else:
            value_text = _format_value(_metric_value(record, metric))
        lines.append(f"                    Run {index}: {value_text}")
    if metric == "path":
        average_text = _format_path_average(comparative_records)
    else:
        average_text = _format_value(_average_metric(comparative_records, metric))
    lines.append(f"                    Average: {average_text}")
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
    lines.append(f"        N_classical_max: {classical_search.best_agent_number}")
    lines.append(f"        N_cyclic_max: {cyclic_search.best_agent_number}")
    lines.append("")

    classical_baseline = _records_from_attempts(classical_search.best_successful_attempts)
    cyclic_comparative = _records_from_attempts(cyclic_at_classical)
    cyclic_baseline = _records_from_attempts(cyclic_search.best_successful_attempts)
    classical_comparative = _records_from_attempts(classical_at_cyclic)

    lines.append("        Under classical max agent number (N_classical_max)")
    _append_metric_block(
        lines,
        metric_title="Time computation halted (secs)",
        baseline_title="Stats of classical at classical max",
        comparative_title="Stats of cyclic at classical max",
        baseline_records=classical_baseline,
        comparative_records=cyclic_comparative,
        metric="time",
    )
    _append_metric_block(
        lines,
        metric_title="Number of conflicts at halt",
        baseline_title="Stats of classical at classical max",
        comparative_title="Stats of cyclic at classical max",
        baseline_records=classical_baseline,
        comparative_records=cyclic_comparative,
        metric="conflicts",
    )
    _append_metric_block(
        lines,
        metric_title="Total path length",
        baseline_title="Stats of classical at classical max",
        comparative_title="Stats of cyclic at classical max",
        baseline_records=classical_baseline,
        comparative_records=cyclic_comparative,
        metric="path",
    )
    _append_evaluation_block(
        lines,
        baseline_records=classical_baseline,
        comparative_records=cyclic_comparative,
    )

    lines.append("        Under cyclic max agent number (N_cyclic_max)")
    _append_metric_block(
        lines,
        metric_title="Time computation halted (secs)",
        baseline_title="Stats of cyclic at cyclic max",
        comparative_title="Stats of classical at cyclic max",
        baseline_records=cyclic_baseline,
        comparative_records=classical_comparative,
        metric="time",
    )
    _append_metric_block(
        lines,
        metric_title="Number of conflicts at halt",
        baseline_title="Stats of cyclic at cyclic max",
        comparative_title="Stats of classical at cyclic max",
        baseline_records=cyclic_baseline,
        comparative_records=classical_comparative,
        metric="conflicts",
    )
    _append_metric_block(
        lines,
        metric_title="Total path length",
        baseline_title="Stats of cyclic at cyclic max",
        comparative_title="Stats of classical at cyclic max",
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
        "passed": test_result.passed,
        "success_count": test_result.success_count,
        "counted_attempt_count": test_result.counted_attempt_count,
        "invalid_attempt_count": test_result.invalid_attempt_count,
        "invalid_generation_cap_exhausted": test_result.invalid_generation_cap_exhausted,
        "attempts": [_attempt_to_summary(attempt) for attempt in test_result.attempts],
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
        capacity_label="classical_capacity",
        baseline_successful_attempts=classical_search.best_successful_attempts,
        logger=logger,
    )
    classical_at_cyclic = _run_comparative_attempts(
        branch_spec=branch_spec,
        dynamic_state=dynamic_state,
        baseline_mapping_name="cyclic",
        comparative_mapping_name="classical",
        capacity_label="cyclic_capacity",
        baseline_successful_attempts=cyclic_search.best_successful_attempts,
        logger=logger,
    )

    data_log_dir = OUTPUTS_MAIN_EXPERIMENT_ROOT / "data_log" / branch_spec.data_log_category_dir_name
    data_log_dir.mkdir(parents=True, exist_ok=True)
    data_log_path = data_log_dir / f"{branch_spec.data_log_file_stem}_evaluation.xml"
    raw_json_path = data_log_dir / f"{branch_spec.data_log_file_stem}_raw_data.json"

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
            "cyclic_at_classical_capacity": [_attempt_to_summary(attempt) for attempt in cyclic_at_classical],
            "classical_at_cyclic_capacity": [_attempt_to_summary(attempt) for attempt in classical_at_cyclic],
        },
        "data_log_path": str(data_log_path),
    }
    write_json(raw_json_path, raw_payload)

    logger.log(f"Detailed configuration/evaluation log written: {data_log_path}")
    logger.log(f"Structured raw data written: {raw_json_path}")
    logger.log_elapsed(f"Configuration completed: {branch_spec.map_type}")

    return {
        "map_type": branch_spec.map_type,
        "category_map_type": branch_spec.category_map_type,
        "layout_key": branch_spec.layout_key,
        "n_classical_max": classical_search.best_agent_number,
        "n_cyclic_max": cyclic_search.best_agent_number,
        "data_log_path": str(data_log_path),
        "raw_data_path": str(raw_json_path),
    }


def run_selected_experiment(
    map_type: str,
    *,
    seed_base: int | None = None,
    program_start_time: float | None = None,
) -> dict[str, Any]:
    generation_target = _resolve_generation_target()
    if generation_target != "raw_data":
        raise NotImplementedError(
            "The updated main-experiment protocol currently supports to_generate = 'raw_data'. "
            "Graphs and visualization should be updated later from the new raw-data/log format."
        )

    branch_specs = get_branch_specs_for_selected_map_type(map_type)
    if not branch_specs:
        raise ValueError(f"No layout configurations found for MAP_TYPE={map_type!r}")

    logs_dir = OUTPUTS_MAIN_EXPERIMENT_ROOT / "logs" / map_type
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = ExperimentLogger(logs_dir / "raw_data_capacity_protocol.log", start_time=program_start_time)

    logger.log("=" * 88)
    logger.log(f"Selected main-experiment category: {map_type}")
    logger.log(f"to_generate: {generation_target}")
    logger.log(f"Layout configurations to run: {len(branch_specs)}")
    logger.log(f"Data-log root: {OUTPUTS_MAIN_EXPERIMENT_ROOT / 'data_log'}")
    logger.log("=" * 88)

    summaries: list[dict[str, Any]] = []
    for branch_spec in branch_specs:
        resolved_seed_base = branch_spec.seed_base if seed_base is None else seed_base
        summaries.append(
            _compute_single_configuration(
                branch_spec=branch_spec,
                seed_base=resolved_seed_base,
                logger=logger,
            )
        )

    summary_path = OUTPUTS_MAIN_EXPERIMENT_ROOT / "data_log" / f"{branch_specs[0].data_log_category_dir_name}_summary.json"
    write_json(
        summary_path,
        {
            "selected_map_type": map_type,
            "generation_target": generation_target,
            "layout_configurations": summaries,
        },
    )
    logger.log("")
    logger.log(f"Category summary written: {summary_path}")
    logger.log_elapsed("Selected main-experiment category finished.")

    return {
        "selected_map_type": map_type,
        "generation_target": generation_target,
        "output_root": str(OUTPUTS_MAIN_EXPERIMENT_ROOT),
        "log_path": str(logs_dir / "raw_data_capacity_protocol.log"),
        "category_summary_path": str(summary_path),
        "layout_configurations": summaries,
    }
