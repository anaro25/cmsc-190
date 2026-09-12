from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dev.experiments.frame_by_frame_store import ReferenceFrameByFrameStore
from dev.experiments.ref_comparison.aggregation import build_reference_aggregate
from dev.experiments.ref_comparison.io_utils import RefCaseOutputManager, RefExperimentLogger, RefRawDataStore, write_csv, write_json
from dev.experiments.ref_comparison.models import RefCaseSpec, RefConditionAggregate, RefMappingRunRecord, RefRunConfiguration, RefVisualizationCandidate
from dev.experiments.ref_comparison.plotting import generate_reference_graphs
from dev.experiments.ref_comparison.runtime import (
    build_multi_agent_spawn_sequence,
    build_reference_maps,
    build_run_configuration,
    build_mapping_record,
    build_single_agent,
    execute_mapping,
    execute_mapping_with_timing_repetitions,
)
from dev.experiments.ref_comparison.visualization import render_reference_visualizations
from dev.master_config_ref_comparison import (
    ADD_TRANSITIONS_BETWEEN_FREE_SPACES,
    REFERENCE_COMPARISON_CASES,
    REMOVE_EXTRA_TRANSITIONS,
    SELECTED_PORT_EXPERIMENT,
    SELECTED_PORT_EXPERIMENT_CASES,
    SHARED_ECBS_SUBOPTIMALITY,
    SHARED_TIME_LIMIT_SECONDS,
    SHARED_TIGHT_TIME_HORIZON,
    SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
    TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER_MAX_ATTEMPTS,
    enhanced_CBS,
    to_generate,
)

VALID_GENERATION_TARGETS = {"raw_data", "graphs", "visualization"}


def _build_case_spec(case_id: str) -> RefCaseSpec:
    if case_id not in REFERENCE_COMPARISON_CASES:
        raise ValueError(f"Unknown reference-comparison case_id '{case_id}'.")
    config = dict(REFERENCE_COMPARISON_CASES[case_id])
    experiment_mode = str(config["experiment_mode"])
    if experiment_mode not in {"single_agent", "multi_agent"}:
        raise ValueError(f"Unsupported reference experiment_mode '{experiment_mode}'.")

    return RefCaseSpec(
        case_id=str(config["case_id"]),
        experiment_mode=experiment_mode,
        display_name=str(config["display_name"]),
        size_label=str(config["size_label"]),
        map_size=int(config["map_size"]),
        image_path=str(config.get("image_path", "")),
        map_image_paths=[str(path) for path in config.get("map_image_paths", [config.get("image_path", "")]) if str(path)],
        agent_number=int(config.get("agent_number", 1 if experiment_mode == "single_agent" else 0)),
        counted_runs_required=int(config["counted_runs_required"]),
        capacity_search_enabled=bool(config.get("capacity_search_enabled", False)),
        capacity_attempts_per_agent_number=max(1, int(config.get("capacity_attempts_per_agent_number", 5))),
        capacity_successful_runs_required=max(1, int(config.get("capacity_successful_runs_required", 3))),
        capacity_pass_criterion=str(config.get("capacity_pass_criterion", "solver_success")),
        runtime_limit_seconds=float(SHARED_TIME_LIMIT_SECONDS),
        use_ecbs=bool(enhanced_CBS) if experiment_mode == "multi_agent" else False,
        ecbs_suboptimality=float(SHARED_ECBS_SUBOPTIMALITY),
        true_static_shortest_path_distance=bool(SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE),
        tight_time_horizon=bool(SHARED_TIGHT_TIME_HORIZON),
        remove_extra_transitions=bool(REMOVE_EXTRA_TRANSITIONS),
        add_transitions_between_free_spaces=bool(ADD_TRANSITIONS_BETWEEN_FREE_SPACES),
        filter_individual_runs_until_cyclic_faster=bool(config.get("filter_individual_runs_until_cyclic_faster", False)),
        filter_individual_runs_until_cyclic_faster_max_attempts=(
            int(TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER_MAX_ATTEMPTS) if experiment_mode == "multi_agent" else None
        ),
        single_agent_timing_repetitions=(
            max(1, int(config.get("single_agent_timing_repetitions", 1))) if experiment_mode == "single_agent" else 1
        ),
        multi_agent_timing_repetitions=(
            max(1, int(config.get("multi_agent_timing_repetitions", 1))) if experiment_mode == "multi_agent" else 1
        ),
        notes=(
            "Tang-inspired single-agent reference case. Both sides use the project traditional A* solver; the classical side uses classical mapping and the cyclic side uses cyclic mapping. The three configured 50x50 port maps are evaluated together. For each map, runtime is averaged over repeated identical A* executions. The cyclic-faster temporary filter is deliberately disabled."
            if experiment_mode == "single_agent"
            else "Tang-inspired multi-agent reference case. Classical and cyclic capacities are searched independently over 1..F traversable cells. Each tested agent number uses five runs and passes with at least three solver successes. Each mapping is then evaluated at its own discovered capacity, with runtime averaged over three identical ECBS executions."
        ),
    )

def _selected_case_ids() -> list[str]:
    if SELECTED_PORT_EXPERIMENT not in SELECTED_PORT_EXPERIMENT_CASES:
        available = ", ".join(sorted(SELECTED_PORT_EXPERIMENT_CASES))
        raise ValueError(f"Unknown SELECTED_PORT_EXPERIMENT '{SELECTED_PORT_EXPERIMENT}'. Available: {available}")
    return list(SELECTED_PORT_EXPERIMENT_CASES[SELECTED_PORT_EXPERIMENT])


def _resolve_generation_target() -> str:
    generation_target = str(to_generate)
    if generation_target not in VALID_GENERATION_TARGETS:
        raise ValueError("to_generate must be one of 'raw_data', 'graphs', or 'visualization'.")
    return generation_target


def _should_recompute_raw_mapf(generation_target: str) -> bool:
    return generation_target == "raw_data"


def _log_case_header(logger: RefExperimentLogger, case_spec: RefCaseSpec) -> None:
    logger.log("=" * 88)
    logger.log("REFERENCE COMPARISON EXPERIMENT")
    logger.log("=" * 88)
    logger.log(f"case_id: {case_spec.case_id}")
    logger.log(f"display_name: {case_spec.display_name}")
    logger.log(f"experiment_mode: {case_spec.experiment_mode}")
    logger.log(f"map_size: {case_spec.map_size}x{case_spec.map_size}")
    if case_spec.experiment_mode == "single_agent":
        logger.log(f"agent_number: {case_spec.agent_number}")
    logger.log(f"counted_runs_required: {case_spec.counted_runs_required}")
    if case_spec.experiment_mode == "single_agent":
        logger.log(f"single_agent_timing_repetitions: {case_spec.single_agent_timing_repetitions}")
    if case_spec.experiment_mode == "multi_agent":
        logger.log(f"multi_agent_timing_repetitions: {case_spec.multi_agent_timing_repetitions}")
        logger.log(f"capacity_search_enabled: {case_spec.capacity_search_enabled}")
        logger.log(f"capacity_pass_criterion: {case_spec.capacity_pass_criterion}")
        logger.log("capacity_agent_range: 1..F (derived separately for each reference map)")
        logger.log(f"capacity_attempts_per_agent_number: {case_spec.capacity_attempts_per_agent_number}")
        logger.log(f"capacity_successful_runs_required: {case_spec.capacity_successful_runs_required}")
        logger.log("capacity_search_mappings: classical and cyclic independently")
        logger.log("capacity_search_early_stop_after_first_success: disabled")
        logger.log("agent_cohesion_enabled: False")
    logger.log(f"runtime_limit_seconds: {case_spec.runtime_limit_seconds}")
    logger.log(f"true_static_shortest_path_distance: {case_spec.true_static_shortest_path_distance}")
    logger.log(f"remove_extra_transitions: {case_spec.remove_extra_transitions}")
    logger.log(f"add_transitions_between_free_spaces: {case_spec.add_transitions_between_free_spaces}")
    logger.log(f"filter_individual_runs_until_cyclic_faster: {case_spec.filter_individual_runs_until_cyclic_faster}")
    for index, image_path in enumerate(case_spec.map_image_paths, start=1):
        logger.log(f"map_{index}_image_path: {image_path}")
    logger.log("=" * 88)

def _append_visualization_candidate(
    *,
    candidates: list[RefVisualizationCandidate],
    case_spec: RefCaseSpec,
    run_configuration,
    mapping_name: str,
    agents: list[dict],
    solver_result: dict | None,
    composite_map: list[list],
) -> None:
    if not solver_result or solver_result.get("status") != "solved" or not solver_result.get("paths_by_agent"):
        return
    candidates.append(
        RefVisualizationCandidate(
            case_spec=case_spec,
            run_configuration=run_configuration,
            mapping_name=mapping_name,
            agents=agents,
            solver_result=solver_result,
            composite_map=composite_map,
        )
    )


def _format_timing_samples(samples: list[float]) -> str:
    return ", ".join(f"{sample:.4f}" for sample in samples)


@dataclass
class _RefCapacityTrial:
    mapping_name: str
    agent_number: int
    passed: bool
    success_count: int
    attempt_slots_evaluated: int
    failure_reason: str | None
    reasons: list[str]
    run_configurations: list[RefRunConfiguration]
    records: list[RefMappingRunRecord]

    def to_summary(self) -> dict:
        attempts: list[dict] = []
        record_by_id = {record.run_config_id: record for record in self.records}
        for run_configuration in self.run_configurations:
            record = record_by_id.get(run_configuration.run_config_id)
            attempts.append(
                {
                    "run_configuration": run_configuration.to_dict(),
                    "record": record.to_dict() if record is not None else None,
                }
            )
        return {
            "mapping_name": self.mapping_name,
            "agent_number": self.agent_number,
            "passed": self.passed,
            "success_count": self.success_count,
            "attempts_evaluated": self.attempt_slots_evaluated,
            "solver_runs_completed": len(self.records),
            "failure_reason": self.failure_reason,
            "reasons": list(self.reasons),
            "attempts": attempts,
        }


@dataclass
class _RefCapacitySearchResult:
    mapping_name: str
    candidate_maximum: int
    best_agent_number: int
    tested_trials: list[_RefCapacityTrial]
    search_trace: list[dict]

    def to_summary(self) -> dict:
        return {
            "mapping_name": self.mapping_name,
            "pass_criterion": "solver_success",
            "candidate_maximum": self.candidate_maximum,
            "best_agent_number": self.best_agent_number,
            "tested_agent_numbers": [trial.to_summary() for trial in self.tested_trials],
            "search_trace": list(self.search_trace),
        }


def _validate_reference_capacity_config(case_spec: RefCaseSpec) -> None:
    if not case_spec.capacity_search_enabled:
        raise ValueError("Multi-agent reference comparison requires capacity_search_enabled=True.")
    if case_spec.capacity_pass_criterion != "solver_success":
        raise ValueError("Reference capacity_pass_criterion must be 'solver_success'.")
    if case_spec.capacity_attempts_per_agent_number != 5:
        raise ValueError("Reference capacity search must evaluate exactly five runs per tested agent number.")
    if case_spec.capacity_successful_runs_required != 3:
        raise ValueError("Reference capacity search must require at least three successful runs out of five.")


def _test_reference_capacity_candidate(
    *,
    case_spec: RefCaseSpec,
    map_context: dict,
    mapping_name: str,
    agent_number: int,
    search_step_index: int,
    logger: RefExperimentLogger,
) -> _RefCapacityTrial:
    if mapping_name not in {"classical", "cyclic"}:
        raise ValueError(f"Unsupported reference capacity mapping '{mapping_name}'.")

    max_attempts = int(case_spec.capacity_attempts_per_agent_number)
    required_successes = int(case_spec.capacity_successful_runs_required)
    logger.log("")
    logger.log(
        f"    Testing N={agent_number} for {mapping_name} reference capacity | "
        f"pass_rule={required_successes}/{max_attempts} successful solver runs within "
        f"{case_spec.runtime_limit_seconds:.0f}s; all five run slots are evaluated"
    )

    run_configurations: list[RefRunConfiguration] = []
    records: list[RefMappingRunRecord] = []
    reasons: list[str] = []
    success_count = 0

    for attempt_index in range(1, max_attempts + 1):
        try:
            agents = build_multi_agent_spawn_sequence(
                case_spec,
                map_context,
                agent_number=agent_number,
                mapping_name=mapping_name,
            )
            run_configuration = build_run_configuration(
                case_spec=case_spec,
                run_index=attempt_index - 1,
                map_identifier=map_context["map_identifier"],
                agents=agents,
                agent_number=agent_number,
                notes=(
                    f"reference capacity-search run {attempt_index}/{max_attempts} for {mapping_name}; "
                    "capacity success depends only on this mapping returning a valid solution within the time limit"
                ),
                map_index=map_context["map_index"],
                map_number=map_context["map_number"],
                map_label_value=map_context["map_label"],
                run_config_tag=f"capacity_{mapping_name}_step_{search_step_index}_attempt_{attempt_index}",
                paired_source=False,
            )
        except Exception as exc:
            reason = f"attempt_{attempt_index}:setup_unavailable:{type(exc).__name__}:{exc}"
            reasons.append(reason)
            logger.log(f"      Run {attempt_index}/{max_attempts}: setup unavailable ({type(exc).__name__}: {exc})")
            continue

        run_configurations.append(run_configuration)
        solver_result, elapsed_seconds, solver_status = execute_mapping(
            case_spec=case_spec,
            composite_map=map_context[f"{mapping_name}_map"],
            agents=agents,
            mapping_name=mapping_name,
            logger=logger,
        )
        record = build_mapping_record(
            case_spec=case_spec,
            run_configuration=run_configuration,
            mapping_name=mapping_name,
            solver_result=solver_result,
            elapsed_seconds=elapsed_seconds,
            solver_status=solver_status,
            comparison_case=f"capacity_search_{mapping_name}",
        )
        records.append(record)
        if record.solved_run:
            success_count += 1
        else:
            reasons.append(f"attempt_{attempt_index}:{record.result_category}")
        logger.log(
            f"      Run {attempt_index}/{max_attempts}: {record.result_category} | "
            f"t={record.time_computation_halted_seconds:.4f}s | "
            f"conflicts={record.num_conflicts_detected_at_halt}"
        )

    passed = success_count >= required_successes
    if passed:
        failure_reason = None
    elif not records:
        failure_reason = "setup_unavailable"
    else:
        failure_reason = "solver_fail"

    logger.log(
        f"    Result for N={agent_number} | mapping={mapping_name} | passed={passed} | "
        f"successful={success_count}/{max_attempts} | run_slots_evaluated={max_attempts} | "
        f"failure_reason={failure_reason or 'none'}"
    )
    return _RefCapacityTrial(
        mapping_name=mapping_name,
        agent_number=agent_number,
        passed=passed,
        success_count=success_count,
        attempt_slots_evaluated=max_attempts,
        failure_reason=failure_reason,
        reasons=reasons,
        run_configurations=run_configurations,
        records=records,
    )


def _run_reference_capacity_search(
    *,
    case_spec: RefCaseSpec,
    map_context: dict,
    mapping_name: str,
    capacity_upper_bound: int,
    logger: RefExperimentLogger,
) -> _RefCapacitySearchResult:
    _validate_reference_capacity_config(case_spec)
    if mapping_name not in {"classical", "cyclic"}:
        raise ValueError(f"Unsupported reference capacity mapping '{mapping_name}'.")
    if int(capacity_upper_bound) < 1:
        raise ValueError("Reference capacity search requires at least one traversable cell (F >= 1).")

    low = 1
    high = int(capacity_upper_bound)
    best_agent_number = 0
    tested_trials: list[_RefCapacityTrial] = []
    search_trace: list[dict] = []
    search_step_index = 0

    logger.log("")
    logger.log("-" * 88)
    logger.log(
        f"{mapping_name.title()} reference capacity search started | map={map_context['map_label']} | "
        f"criterion=solver_success | range=1..{high} (F={high}) | "
        f"runs_per_candidate={case_spec.capacity_attempts_per_agent_number} | "
        f"successes_required={case_spec.capacity_successful_runs_required}"
    )
    logger.log("-" * 88)

    while low <= high:
        midpoint = (low + high) // 2
        search_step_index += 1
        low_before = low
        high_before = high
        trial = _test_reference_capacity_candidate(
            case_spec=case_spec,
            map_context=map_context,
            mapping_name=mapping_name,
            agent_number=midpoint,
            search_step_index=search_step_index,
            logger=logger,
        )
        tested_trials.append(trial)
        search_trace.append(
            {
                "step": search_step_index,
                "low_before": low_before,
                "high_before": high_before,
                "tested_agent_number": midpoint,
                "pass_criterion": "solver_success",
                "passed": trial.passed,
                "success_count": trial.success_count,
                "attempts_required": case_spec.capacity_attempts_per_agent_number,
                "failure_reason": trial.failure_reason,
            }
        )

        if trial.passed:
            best_agent_number = midpoint
            low = midpoint + 1
            logger.log(f"    N={midpoint} passed; moving to search interval {low}..{high}.")
        else:
            high = midpoint - 1
            logger.log(
                f"    N={midpoint} failed (reason={trial.failure_reason or 'unknown'}); "
                f"moving to search interval {low}..{high}."
            )

    logger.log(
        f"{mapping_name.title()} reference capacity search finished | map={map_context['map_label']} | "
        f"N_max={best_agent_number} | tested_agent_numbers={len(tested_trials)}"
    )
    return _RefCapacitySearchResult(
        mapping_name=mapping_name,
        candidate_maximum=int(capacity_upper_bound),
        best_agent_number=best_agent_number,
        tested_trials=tested_trials,
        search_trace=search_trace,
    )

def _compute_single_agent_case(case_spec: RefCaseSpec, logger: RefExperimentLogger) -> dict:
    timing_repetitions = max(1, int(case_spec.single_agent_timing_repetitions))
    logger.log(
        "Preparing single-agent reference maps across the three configured port maps "
        f"with {timing_repetitions} timing repetitions per mapping..."
    )
    classical_records: list[RefMappingRunRecord] = []
    cyclic_records: list[RefMappingRunRecord] = []
    run_configurations: list[dict] = []
    run_records: list[dict] = []
    visualization_candidates: list[RefVisualizationCandidate] = []
    map_aggregates: list[dict] = []

    for map_index in range(len(case_spec.map_image_paths)):
        map_context = build_reference_maps(case_spec, map_index=map_index)
        logger.log(
            f"Map {map_context['map_number']}/{len(case_spec.map_image_paths)} | "
            f"map_identifier={map_context['map_identifier']} | dimensions={map_context['rows']}x{map_context['cols']} | "
            f"traversable_cells={map_context['traversable_cell_count']} | image_path={map_context['image_path']}"
        )
        agents = build_single_agent(case_spec, map_context)
        run_configuration = build_run_configuration(
            case_spec=case_spec,
            run_index=map_index,
            map_identifier=map_context["map_identifier"],
            agents=agents,
            notes=(
                "single agent starts at lower-left-most cell and targets the upper-right-most cell; "
                f"runtime is averaged over {timing_repetitions} identical repetitions per mapping"
            ),
            map_index=map_context["map_index"],
            map_number=map_context["map_number"],
            map_label_value=map_context["map_label"],
        )
        classical_result, classical_elapsed, classical_status, classical_samples, classical_statuses = execute_mapping_with_timing_repetitions(
            case_spec=case_spec,
            composite_map=map_context["classical_map"],
            agents=agents,
            mapping_name="classical",
            logger=logger,
            repetitions=timing_repetitions,
        )
        classical_record = build_mapping_record(
            case_spec=case_spec,
            run_configuration=run_configuration,
            mapping_name="classical",
            solver_result=classical_result,
            elapsed_seconds=classical_elapsed,
            solver_status=classical_status,
            timing_repetitions=timing_repetitions,
            timing_elapsed_samples_seconds=classical_samples,
        )

        cyclic_result, cyclic_elapsed, cyclic_status, cyclic_samples, cyclic_statuses = execute_mapping_with_timing_repetitions(
            case_spec=case_spec,
            composite_map=map_context["cyclic_map"],
            agents=agents,
            mapping_name="cyclic",
            logger=logger,
            repetitions=timing_repetitions,
        )
        cyclic_record = build_mapping_record(
            case_spec=case_spec,
            run_configuration=run_configuration,
            mapping_name="cyclic",
            solver_result=cyclic_result,
            elapsed_seconds=cyclic_elapsed,
            solver_status=cyclic_status,
            timing_repetitions=timing_repetitions,
            timing_elapsed_samples_seconds=cyclic_samples,
        )

        if len(set(classical_statuses)) > 1 or len(set(cyclic_statuses)) > 1:
            logger.log(
                "  Warning: repeated single-agent timings produced differing statuses | "
                f"classical={classical_statuses} | cyclic={cyclic_statuses}"
            )
        logger.log(
            "  Result | "
            f"classical={classical_record.result_category}, avg_t={classical_record.time_computation_halted_seconds:.4f}s, "
            f"samples=[{_format_timing_samples(classical_samples)}] | "
            f"cyclic={cyclic_record.result_category}, avg_t={cyclic_record.time_computation_halted_seconds:.4f}s, "
            f"samples=[{_format_timing_samples(cyclic_samples)}]"
        )

        run_configurations.append(run_configuration.to_dict())
        classical_records.append(classical_record)
        cyclic_records.append(cyclic_record)
        run_records.extend([classical_record.to_dict(), cyclic_record.to_dict()])
        _append_visualization_candidate(candidates=visualization_candidates, case_spec=case_spec, run_configuration=run_configuration, mapping_name="classical", agents=agents, solver_result=classical_result, composite_map=map_context["classical_map"])
        _append_visualization_candidate(candidates=visualization_candidates, case_spec=case_spec, run_configuration=run_configuration, mapping_name="cyclic", agents=agents, solver_result=cyclic_result, composite_map=map_context["cyclic_map"])

        aggregate = build_reference_aggregate(
            case_spec=case_spec,
            classical_records=[classical_record],
            cyclic_records=[cyclic_record],
            map_index=map_context["map_index"],
            map_number=map_context["map_number"],
            map_label=map_context["map_label"],
        )
        map_aggregates.append(aggregate.to_dict())

    overall_aggregate = build_reference_aggregate(case_spec=case_spec, classical_records=classical_records, cyclic_records=cyclic_records)
    stop_summary = {
        "case_id": case_spec.case_id,
        "retained_pairs": len(run_configurations),
        "attempts_used": len(run_configurations),
        "max_attempts": len(run_configurations),
        "completed_counted_quota": True,
        "filter_individual_runs_until_cyclic_faster": False,
        "discarded_attempts_count": 0,
        "num_reference_maps": len(case_spec.map_image_paths),
        "single_agent_timing_repetitions": timing_repetitions,
        "stop_reason": None,
    }
    return {
        "case_spec": case_spec,
        "run_configurations": run_configurations,
        "run_records": run_records,
        "aggregate": overall_aggregate.to_dict(),
        "map_aggregates": map_aggregates,
        "discarded_attempts": [],
        "visualization_candidates": visualization_candidates,
        "stop_summary": stop_summary,
    }


def _compute_multi_agent_case(case_spec: RefCaseSpec, logger: RefExperimentLogger) -> dict:
    timing_repetitions = max(1, int(case_spec.multi_agent_timing_repetitions))
    _validate_reference_capacity_config(case_spec)
    logger.log(
        "Preparing multi-agent reference maps across the three configured port maps. "
        "Each map searches classical and cyclic capacities independently over 1..F, "
        "using five runs per tested agent number and a three-success majority. "
        f"Each mapping is then measured at its own capacity with {timing_repetitions} timing repetitions."
    )

    classical_records: list[RefMappingRunRecord] = []
    cyclic_records: list[RefMappingRunRecord] = []
    run_configurations: list[dict] = []
    run_records: list[dict] = []
    visualization_candidates: list[RefVisualizationCandidate] = []
    map_aggregates: list[dict] = []
    capacity_searches: list[dict] = []
    map_classical_capacities: dict[str, int] = {}
    map_cyclic_capacities: dict[str, int] = {}
    map_traversable_cell_counts: dict[str, int] = {}

    for map_index in range(len(case_spec.map_image_paths)):
        map_context = build_reference_maps(case_spec, map_index=map_index)
        traversable_cell_count = int(map_context["traversable_cell_count"])
        map_key = str(map_context["map_number"])
        map_traversable_cell_counts[map_key] = traversable_cell_count
        logger.log(
            f"Map {map_context['map_number']}/{len(case_spec.map_image_paths)} | "
            f"map_identifier={map_context['map_identifier']} | dimensions={map_context['rows']}x{map_context['cols']} | "
            f"F={traversable_cell_count} traversable cells | image_path={map_context['image_path']}"
        )

        classical_search = _run_reference_capacity_search(
            case_spec=case_spec,
            map_context=map_context,
            mapping_name="classical",
            capacity_upper_bound=traversable_cell_count,
            logger=logger,
        )
        cyclic_search = _run_reference_capacity_search(
            case_spec=case_spec,
            map_context=map_context,
            mapping_name="cyclic",
            capacity_upper_bound=traversable_cell_count,
            logger=logger,
        )
        classical_capacity = int(classical_search.best_agent_number)
        cyclic_capacity = int(cyclic_search.best_agent_number)
        map_classical_capacities[map_key] = classical_capacity
        map_cyclic_capacities[map_key] = cyclic_capacity
        capacity_searches.append(
            {
                "map_index": map_context["map_index"],
                "map_number": map_context["map_number"],
                "map_label": map_context["map_label"],
                "map_identifier": map_context["map_identifier"],
                "traversable_cell_count": traversable_cell_count,
                "classical_capacity_search": classical_search.to_summary(),
                "cyclic_capacity_search": cyclic_search.to_summary(),
            }
        )

        map_classical_records: list[RefMappingRunRecord] = []
        map_cyclic_records: list[RefMappingRunRecord] = []

        if classical_capacity > 0:
            classical_agents = build_multi_agent_spawn_sequence(
                case_spec,
                map_context,
                agent_number=classical_capacity,
                mapping_name="classical",
            )
            classical_run_configuration = build_run_configuration(
                case_spec=case_spec,
                run_index=map_index,
                map_identifier=map_context["map_identifier"],
                agents=classical_agents,
                agent_number=classical_capacity,
                notes=(
                    f"classical mapping evaluated at its independently discovered capacity N={classical_capacity}; "
                    "agents share the upper-right target and use fixed release/spawn times from the upper and right "
                    "neighbors of the lower-left start cell; "
                    f"runtime is averaged over {timing_repetitions} identical repetitions"
                ),
                map_index=map_context["map_index"],
                map_number=map_context["map_number"],
                map_label_value=map_context["map_label"],
                run_config_tag="classical_capacity_final",
                paired_source=False,
            )
            logger.log(
                f"Final classical measurement at N_classical_capacity={classical_capacity} | "
                f"run_config_id={classical_run_configuration.run_config_id}"
            )
            classical_result, classical_elapsed, classical_status, classical_samples, classical_statuses = execute_mapping_with_timing_repetitions(
                case_spec=case_spec,
                composite_map=map_context["classical_map"],
                agents=classical_agents,
                mapping_name="classical",
                logger=logger,
                repetitions=timing_repetitions,
            )
            classical_record = build_mapping_record(
                case_spec=case_spec,
                run_configuration=classical_run_configuration,
                mapping_name="classical",
                solver_result=classical_result,
                elapsed_seconds=classical_elapsed,
                solver_status=classical_status,
                timing_repetitions=timing_repetitions,
                timing_elapsed_samples_seconds=classical_samples,
                comparison_case="classical_at_classical_capacity",
            )
            if len(set(classical_statuses)) > 1:
                logger.log(f"  Warning: repeated classical timings produced differing statuses | {classical_statuses}")
            logger.log(
                f"  Classical final result | N={classical_capacity} | "
                f"result={classical_record.result_category}, avg_t={classical_record.time_computation_halted_seconds:.4f}s, "
                f"conflicts={classical_record.num_conflicts_detected_at_halt}, samples=[{_format_timing_samples(classical_samples)}]"
            )
            run_configurations.append(classical_run_configuration.to_dict())
            run_records.append(classical_record.to_dict())
            classical_records.append(classical_record)
            map_classical_records.append(classical_record)
            _append_visualization_candidate(
                candidates=visualization_candidates,
                case_spec=case_spec,
                run_configuration=classical_run_configuration,
                mapping_name="classical",
                agents=classical_agents,
                solver_result=classical_result,
                composite_map=map_context["classical_map"],
            )
        else:
            logger.log(f"No passing classical capacity was found for {map_context['map_label']}.")

        if cyclic_capacity > 0:
            cyclic_agents = build_multi_agent_spawn_sequence(
                case_spec,
                map_context,
                agent_number=cyclic_capacity,
                mapping_name="cyclic",
            )
            cyclic_run_configuration = build_run_configuration(
                case_spec=case_spec,
                run_index=map_index,
                map_identifier=map_context["map_identifier"],
                agents=cyclic_agents,
                agent_number=cyclic_capacity,
                notes=(
                    f"cyclic mapping evaluated at its independently discovered capacity N={cyclic_capacity}; "
                    "agents share the upper-right target and use fixed release/spawn times from the upper and right "
                    "neighbors of the lower-left start cell; "
                    f"runtime is averaged over {timing_repetitions} identical repetitions"
                ),
                map_index=map_context["map_index"],
                map_number=map_context["map_number"],
                map_label_value=map_context["map_label"],
                run_config_tag="cyclic_capacity_final",
                paired_source=False,
            )
            logger.log(
                f"Final cyclic measurement at N_cyclic_capacity={cyclic_capacity} | "
                f"run_config_id={cyclic_run_configuration.run_config_id}"
            )
            cyclic_result, cyclic_elapsed, cyclic_status, cyclic_samples, cyclic_statuses = execute_mapping_with_timing_repetitions(
                case_spec=case_spec,
                composite_map=map_context["cyclic_map"],
                agents=cyclic_agents,
                mapping_name="cyclic",
                logger=logger,
                repetitions=timing_repetitions,
            )
            cyclic_record = build_mapping_record(
                case_spec=case_spec,
                run_configuration=cyclic_run_configuration,
                mapping_name="cyclic",
                solver_result=cyclic_result,
                elapsed_seconds=cyclic_elapsed,
                solver_status=cyclic_status,
                timing_repetitions=timing_repetitions,
                timing_elapsed_samples_seconds=cyclic_samples,
                comparison_case="cyclic_at_cyclic_capacity",
            )
            if len(set(cyclic_statuses)) > 1:
                logger.log(f"  Warning: repeated cyclic timings produced differing statuses | {cyclic_statuses}")
            logger.log(
                f"  Cyclic final result | N={cyclic_capacity} | "
                f"result={cyclic_record.result_category}, avg_t={cyclic_record.time_computation_halted_seconds:.4f}s, "
                f"conflicts={cyclic_record.num_conflicts_detected_at_halt}, samples=[{_format_timing_samples(cyclic_samples)}]"
            )
            run_configurations.append(cyclic_run_configuration.to_dict())
            run_records.append(cyclic_record.to_dict())
            cyclic_records.append(cyclic_record)
            map_cyclic_records.append(cyclic_record)
            _append_visualization_candidate(
                candidates=visualization_candidates,
                case_spec=case_spec,
                run_configuration=cyclic_run_configuration,
                mapping_name="cyclic",
                agents=cyclic_agents,
                solver_result=cyclic_result,
                composite_map=map_context["cyclic_map"],
            )
        else:
            logger.log(f"No passing cyclic capacity was found for {map_context['map_label']}.")

        aggregate = build_reference_aggregate(
            case_spec=case_spec,
            classical_records=map_classical_records,
            cyclic_records=map_cyclic_records,
            map_index=map_context["map_index"],
            map_number=map_context["map_number"],
            map_label=map_context["map_label"],
        )
        map_aggregates.append(aggregate.to_dict())

    overall_aggregate = build_reference_aggregate(
        case_spec=case_spec,
        classical_records=classical_records,
        cyclic_records=cyclic_records,
    )
    maps_without_classical_capacity = [key for key, value in map_classical_capacities.items() if int(value) <= 0]
    maps_without_cyclic_capacity = [key for key, value in map_cyclic_capacities.items() if int(value) <= 0]
    total_capacity_run_slots = 0
    for entry in capacity_searches:
        for mapping_key in ("classical_capacity_search", "cyclic_capacity_search"):
            for trial in entry[mapping_key]["tested_agent_numbers"]:
                total_capacity_run_slots += int(trial.get("attempts_evaluated", 0))

    missing_capacity_parts: list[str] = []
    if maps_without_classical_capacity:
        missing_capacity_parts.append("classical:" + ",".join(maps_without_classical_capacity))
    if maps_without_cyclic_capacity:
        missing_capacity_parts.append("cyclic:" + ",".join(maps_without_cyclic_capacity))

    stop_summary = {
        "case_id": case_spec.case_id,
        "retained_mapping_results": len(run_records),
        "attempts_used": total_capacity_run_slots,
        "completed_counted_quota": not missing_capacity_parts,
        "filter_individual_runs_until_cyclic_faster": False,
        "discarded_attempts_count": 0,
        "num_reference_maps": len(case_spec.map_image_paths),
        "multi_agent_timing_repetitions": timing_repetitions,
        "capacity_search_mappings": "classical_and_cyclic_independent",
        "capacity_pass_criterion": case_spec.capacity_pass_criterion,
        "capacity_agent_range": "1..F per map",
        "capacity_attempts_per_agent_number": case_spec.capacity_attempts_per_agent_number,
        "capacity_successful_runs_required": case_spec.capacity_successful_runs_required,
        "capacity_search_early_stop_after_first_success": False,
        "map_traversable_cell_counts": map_traversable_cell_counts,
        "map_classical_capacities": map_classical_capacities,
        "map_cyclic_capacities": map_cyclic_capacities,
        "stop_reason": None if not missing_capacity_parts else "no_passing_capacity_for_" + ";".join(missing_capacity_parts),
    }
    return {
        "case_spec": case_spec,
        "run_configurations": run_configurations,
        "run_records": run_records,
        "aggregate": overall_aggregate.to_dict(),
        "map_aggregates": map_aggregates,
        "capacity_searches": capacity_searches,
        "discarded_attempts": [],
        "visualization_candidates": visualization_candidates,
        "stop_summary": stop_summary,
    }

def _compute_reference_case(case_spec: RefCaseSpec, logger: RefExperimentLogger) -> dict:
    if case_spec.experiment_mode == "single_agent":
        return _compute_single_agent_case(case_spec, logger)
    return _compute_multi_agent_case(case_spec, logger)


def _write_graphs_outputs(*, case_spec: RefCaseSpec, raw_payload: dict, output_manager: RefCaseOutputManager, logger: RefExperimentLogger) -> list[Path]:
    output_manager.clear_graphs_outputs()
    run_configurations = list(raw_payload.get("run_configurations", []))
    run_records = list(raw_payload.get("run_records", []))
    aggregate_payload = dict(raw_payload.get("aggregate") or {})
    map_aggregates_payload = list(raw_payload.get("map_aggregates", []))
    capacity_searches = list(raw_payload.get("capacity_searches", []))
    discarded_attempts = list(raw_payload.get("discarded_attempts", []))
    stop_summary = dict(raw_payload.get("stop_summary", {}))

    write_json(output_manager.metadata_dir / "case_spec.json", case_spec.to_dict())
    write_json(output_manager.metadata_dir / "stop_summary.json", stop_summary)
    write_json(output_manager.records_dir / "run_configurations.json", run_configurations)
    write_json(output_manager.records_dir / "run_records.json", run_records)
    write_json(output_manager.records_dir / "capacity_searches.json", capacity_searches)
    write_json(output_manager.records_dir / "discarded_attempts.json", discarded_attempts)
    write_json(output_manager.aggregates_dir / "condition_summary.json", aggregate_payload)
    if map_aggregates_payload:
        write_json(output_manager.aggregates_dir / "map_condition_summaries.json", map_aggregates_payload)
    write_csv(output_manager.records_dir / "run_configurations.csv", run_configurations)
    write_csv(output_manager.records_dir / "run_records.csv", run_records)
    write_csv(output_manager.records_dir / "discarded_attempts.csv", [{"attempt_index": row.get("attempt_index"), "reason": row.get("reason"), "classical_halted": row.get("classical_halted"), "cyclic_halted": row.get("cyclic_halted")} for row in discarded_attempts])
    write_csv(output_manager.aggregates_dir / "condition_summary.csv", [aggregate_payload] if aggregate_payload else [])
    write_csv(output_manager.aggregates_dir / "map_condition_summaries.csv", map_aggregates_payload)

    aggregate = RefConditionAggregate(**aggregate_payload)
    map_aggregates = [RefConditionAggregate(**payload) for payload in map_aggregates_payload]
    graph_paths = generate_reference_graphs(case_spec, aggregate, output_manager.graphs_dir, map_aggregates=map_aggregates)
    logger.log("Generated graph/data outputs:")
    for path in graph_paths:
        logger.log(f"  - {path}")
    return graph_paths


def _write_visualization_outputs(
    *,
    frame_by_frame_store: ReferenceFrameByFrameStore,
    output_manager: RefCaseOutputManager,
    logger: RefExperimentLogger,
) -> dict:
    candidates = frame_by_frame_store.load_candidates()
    output_manager.clear_visualization_outputs()
    summary = render_reference_visualizations(
        candidates=candidates,
        output_root=output_manager.visualizations_dir,
        # The frame-by-frame store already contains exactly the designated first
        # successful run for each map/mapping pair.
        num_last_successful_runs_per_mapping=1,
        progress_logger=logger.log,
    )
    write_json(output_manager.metadata_dir / "visualization_selection_summary.json", summary)
    logger.log(
        "Generated reference visualizations from saved frame-by-frame data | "
        f"selected_candidates={summary.get('selected_candidates', 0)} | "
        f"available_candidates={summary.get('available_candidates', 0)}"
    )
    return summary


def run_reference_case(case_spec: RefCaseSpec, *, generation_target: str, program_start_time: float | None = None) -> dict:
    recompute_raw_mapf = _should_recompute_raw_mapf(generation_target)
    output_manager = RefCaseOutputManager(case_spec, generation_target=generation_target, recompute_mapf=recompute_raw_mapf)
    logger = RefExperimentLogger(output_manager.prepare_log_output(), start_time=program_start_time)
    raw_store = RefRawDataStore(case_spec)
    frame_by_frame_store = ReferenceFrameByFrameStore(case_spec)

    _log_case_header(logger, case_spec)
    logger.log(f"to_generate: {generation_target}")
    logger.log(f"recompute raw MAPF data: {recompute_raw_mapf}")
    logger.log(f"raw_reference_data_root: {raw_store.case_root}")
    logger.log(f"frame_by_frame_root: {frame_by_frame_store.mode_root}")
    logger.log_elapsed("Reference-comparison stopwatch started.")

    if recompute_raw_mapf:
        logger.log("Computing raw reference-comparison MAPF data and replacing the saved copy...")
        payload = _compute_reference_case(case_spec, logger)
        raw_store.save(payload)
        frame_by_frame_summary = frame_by_frame_store.save(
            payload.get("visualization_candidates", [])
        )
        logger.log(
            "Saved designated reference frame-by-frame runs | "
            f"count={frame_by_frame_summary.get('saved_run_count', 0)} | "
            f"root={frame_by_frame_summary.get('frame_by_frame_root')}"
        )
        logger.log_elapsed("Raw reference-comparison data and frame-by-frame runs computed and saved.")
    else:
        logger.log("Persisted numerical or frame-by-frame data will be reused according to the requested output.")

    graph_paths: list[Path] = []
    visualization_summary: dict = {}
    raw_payload_used = False
    frame_by_frame_used = False

    if generation_target == "raw_data":
        logger.log(
            "Numerical raw data and the designated successful frame-by-frame runs were generated. "
            "Graphs and Pillow visualizations were not regenerated in this run."
        )
    elif generation_target == "graphs":
        raw_payload = raw_store.load()
        raw_payload_used = True
        logger.log("Loaded persisted numerical reference-comparison data for graph generation.")
        graph_paths = _write_graphs_outputs(
            case_spec=case_spec,
            raw_payload=raw_payload,
            output_manager=output_manager,
            logger=logger,
        )
    elif generation_target == "visualization":
        frame_by_frame_used = True
        logger.log("Loading saved reference frame-by-frame files for Pillow visualization generation.")
        visualization_summary = _write_visualization_outputs(
            frame_by_frame_store=frame_by_frame_store,
            output_manager=output_manager,
            logger=logger,
        )

    logger.log_elapsed("Reference-comparison case finished.")
    return {
        "case_id": case_spec.case_id,
        "output_root": str(output_manager.case_root),
        "raw_reference_data_root": str(raw_store.case_root),
        "frame_by_frame_root": str(frame_by_frame_store.mode_root),
        "graph_paths": [str(path) for path in graph_paths],
        "visualization_summary": visualization_summary,
        "generation_target": generation_target,
        "raw_mapf_data_recomputed": recompute_raw_mapf,
        "raw_payload_used_for_generation": raw_payload_used,
        "frame_by_frame_used_for_generation": frame_by_frame_used,
    }


def run_selected_ref_comparison(*, program_start_time: float | None = None) -> dict:
    generation_target = _resolve_generation_target()
    case_ids = _selected_case_ids()
    results = []
    for case_id in case_ids:
        case_spec = _build_case_spec(case_id)
        results.append(run_reference_case(case_spec, generation_target=generation_target, program_start_time=program_start_time))
    return {"selected_port_experiment": SELECTED_PORT_EXPERIMENT, "case_ids": case_ids, "results": results}
