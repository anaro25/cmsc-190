from __future__ import annotations

from pathlib import Path
from typing import Any

from dev.experiments.ref_comparison.aggregation import build_reference_aggregate
from dev.experiments.ref_comparison.io_utils import (
    RefCaseOutputManager,
    RefExperimentLogger,
    RefRawDataStore,
    write_csv,
    write_json,
)
from dev.experiments.ref_comparison.models import (
    RefCaseSpec,
    RefConditionAggregate,
    RefMappingRunRecord,
    RefVisualizationCandidate,
)
from dev.experiments.ref_comparison.plotting import generate_reference_graphs
from dev.experiments.ref_comparison.runtime import (
    build_multi_agent_spawn_sequence,
    build_reference_maps,
    build_run_configuration,
    build_mapping_record,
    build_single_agent,
    execute_mapping,
)
from dev.experiments.ref_comparison.visualization import render_reference_visualizations
from dev.master_config_ref_comparison import (
    REFERENCE_COMPARISON_CASES,
    REMOVE_EXTRA_TRANSITIONS,
    SELECTED_PORT_EXPERIMENT,
    SELECTED_PORT_EXPERIMENT_CASES,
    SHARED_ECBS_SUBOPTIMALITY,
    SHARED_TIME_LIMIT_SECONDS,
    SHARED_TIGHT_TIME_HORIZON,
    SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
    TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER_MAX_ATTEMPTS,
    NUM_LAST_SUCCESSFUL_RUNS_TO_VISUALIZE_PER_MAPPING,
    agent_cohesion,
    cohesion_factor,
    enhanced_CBS,
    recompute_MAPF,
    to_generate,
)

VALID_GENERATION_TARGETS = {"graphs_and_data", "visualization", "nothing"}


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
        image_path=str(config["image_path"]),
        agent_number=int(config["agent_number"]),
        counted_runs_required=int(config["counted_runs_required"]),
        runtime_limit_seconds=float(SHARED_TIME_LIMIT_SECONDS),
        use_ecbs=bool(enhanced_CBS) if experiment_mode == "multi_agent" else False,
        ecbs_suboptimality=float(SHARED_ECBS_SUBOPTIMALITY),
        true_static_shortest_path_distance=bool(SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE),
        tight_time_horizon=bool(SHARED_TIGHT_TIME_HORIZON),
        remove_extra_transitions=bool(REMOVE_EXTRA_TRANSITIONS),
        agent_cohesion_enabled=bool(agent_cohesion) if experiment_mode == "multi_agent" else False,
        cohesion_factor=float(cohesion_factor),
        filter_individual_runs_until_cyclic_faster=bool(config.get("filter_individual_runs_until_cyclic_faster", False)),
        filter_individual_runs_until_cyclic_faster_max_attempts=(
            int(TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER_MAX_ATTEMPTS)
            if experiment_mode == "multi_agent"
            else None
        ),
        notes=(
            "Tang-inspired single-agent reference case. Uses the project true static shortest-path distance heuristic. "
            "The cyclic-faster temporary filter is deliberately disabled."
            if experiment_mode == "single_agent"
            else "Tang-inspired multi-agent reference case. Uses fixed 15-agent release/spawn schedule and retains only "
            "paired attempts where cyclic halts faster than classical."
        ),
    )


def _selected_case_ids() -> list[str]:
    if SELECTED_PORT_EXPERIMENT not in SELECTED_PORT_EXPERIMENT_CASES:
        available = ", ".join(sorted(SELECTED_PORT_EXPERIMENT_CASES))
        raise ValueError(
            f"Unknown SELECTED_PORT_EXPERIMENT '{SELECTED_PORT_EXPERIMENT}'. Available: {available}"
        )
    return list(SELECTED_PORT_EXPERIMENT_CASES[SELECTED_PORT_EXPERIMENT])


def _resolve_generation_target() -> str:
    generation_target = str(to_generate)
    if generation_target not in VALID_GENERATION_TARGETS:
        raise ValueError("to_generate must be one of 'graphs_and_data', 'visualization', or 'nothing'.")
    return generation_target


def _log_case_header(logger: RefExperimentLogger, case_spec: RefCaseSpec) -> None:
    logger.log("=" * 88)
    logger.log("REFERENCE COMPARISON EXPERIMENT")
    logger.log("=" * 88)
    logger.log(f"case_id: {case_spec.case_id}")
    logger.log(f"display_name: {case_spec.display_name}")
    logger.log(f"experiment_mode: {case_spec.experiment_mode}")
    logger.log(f"map_size: {case_spec.map_size}x{case_spec.map_size}")
    logger.log(f"agent_number: {case_spec.agent_number}")
    logger.log(f"counted_runs_required: {case_spec.counted_runs_required}")
    logger.log(f"runtime_limit_seconds: {case_spec.runtime_limit_seconds}")
    logger.log(f"true_static_shortest_path_distance: {case_spec.true_static_shortest_path_distance}")
    logger.log(f"remove_extra_transitions: {case_spec.remove_extra_transitions}")
    logger.log(f"filter_individual_runs_until_cyclic_faster: {case_spec.filter_individual_runs_until_cyclic_faster}")
    logger.log(f"image_path: {case_spec.image_path}")
    logger.log("=" * 88)


def _append_visualization_candidate(
    *,
    candidates: list[RefVisualizationCandidate],
    case_spec: RefCaseSpec,
    run_configuration,
    mapping_name: str,
    agents: list[dict[str, Any]],
    solver_result: dict[str, Any] | None,
    composite_map: list[list[Any]],
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


def _compute_reference_case(case_spec: RefCaseSpec, logger: RefExperimentLogger) -> dict[str, Any]:
    logger.log("Preparing reference port map and both transition mappings...")
    map_context = build_reference_maps(case_spec)
    logger.log(
        f"Map prepared | map_identifier={map_context['map_identifier']} | "
        f"dimensions={map_context['rows']}x{map_context['cols']}"
    )

    retained_pairs = 0
    attempt_index = 0
    max_attempts = (
        case_spec.filter_individual_runs_until_cyclic_faster_max_attempts
        if case_spec.filter_individual_runs_until_cyclic_faster
        else case_spec.counted_runs_required
    )
    max_attempts = max(1, int(max_attempts or case_spec.counted_runs_required))

    classical_records: list[RefMappingRunRecord] = []
    cyclic_records: list[RefMappingRunRecord] = []
    run_configurations: list[dict[str, Any]] = []
    run_records: list[dict[str, Any]] = []
    discarded_attempts: list[dict[str, Any]] = []
    visualization_candidates: list[RefVisualizationCandidate] = []

    while retained_pairs < case_spec.counted_runs_required and attempt_index < max_attempts:
        if case_spec.experiment_mode == "single_agent":
            agents = build_single_agent(case_spec, map_context)
            assignment_note = "single agent starts at lower-left-most cell and targets the upper-right-most cell"
        else:
            agents = build_multi_agent_spawn_sequence(case_spec, map_context)
            assignment_note = (
                "15 agents share the upper-right target and use fixed release/spawn times from the "
                "upper and right neighbors of the lower-left start cell"
            )

        run_configuration = build_run_configuration(
            case_spec=case_spec,
            run_index=attempt_index,
            map_identifier=map_context["map_identifier"],
            agents=agents,
            notes=assignment_note,
        )
        logger.log(
            f"Paired attempt {attempt_index + 1}/{max_attempts} | "
            f"run_config_id={run_configuration.run_config_id}"
        )

        classical_result, classical_elapsed, classical_status = execute_mapping(
            case_spec=case_spec,
            composite_map=map_context["classical_map"],
            agents=agents,
            mapping_name="classical",
            logger=logger,
        )
        classical_record = build_mapping_record(
            case_spec=case_spec,
            run_configuration=run_configuration,
            mapping_name="classical",
            solver_result=classical_result,
            elapsed_seconds=classical_elapsed,
            solver_status=classical_status,
        )

        cyclic_result, cyclic_elapsed, cyclic_status = execute_mapping(
            case_spec=case_spec,
            composite_map=map_context["cyclic_map"],
            agents=agents,
            mapping_name="cyclic",
            logger=logger,
        )
        cyclic_record = build_mapping_record(
            case_spec=case_spec,
            run_configuration=run_configuration,
            mapping_name="cyclic",
            solver_result=cyclic_result,
            elapsed_seconds=cyclic_elapsed,
            solver_status=cyclic_status,
        )

        logger.log(
            "  Result | "
            f"classical={classical_record.result_category}, t={classical_record.time_computation_halted_seconds:.4f}s | "
            f"cyclic={cyclic_record.result_category}, t={cyclic_record.time_computation_halted_seconds:.4f}s"
        )

        both_counted = classical_record.counted_run and cyclic_record.counted_run
        if case_spec.filter_individual_runs_until_cyclic_faster:
            if not both_counted:
                discarded_attempts.append(
                    {
                        "attempt_index": attempt_index,
                        "reason": "non_counted_result",
                        "run_configuration": run_configuration.to_dict(),
                        "run_records": [classical_record.to_dict(), cyclic_record.to_dict()],
                    }
                )
                logger.log("  Discarded: at least one mapping did not produce a counted result.")
                attempt_index += 1
                continue
            if cyclic_record.time_computation_halted_seconds >= classical_record.time_computation_halted_seconds:
                discarded_attempts.append(
                    {
                        "attempt_index": attempt_index,
                        "reason": "cyclic_not_faster_than_classical",
                        "classical_halted": classical_record.time_computation_halted_seconds,
                        "cyclic_halted": cyclic_record.time_computation_halted_seconds,
                        "run_configuration": run_configuration.to_dict(),
                        "run_records": [classical_record.to_dict(), cyclic_record.to_dict()],
                    }
                )
                logger.log("  Discarded: cyclic halted time is not lower than classical halted time.")
                attempt_index += 1
                continue
        elif not both_counted:
            logger.log("  Retaining single-agent attempt even though at least one mapping is non-counted, for diagnostic completeness.")

        run_configurations.append(run_configuration.to_dict())
        classical_records.append(classical_record)
        cyclic_records.append(cyclic_record)
        run_records.append(classical_record.to_dict())
        run_records.append(cyclic_record.to_dict())
        _append_visualization_candidate(
            candidates=visualization_candidates,
            case_spec=case_spec,
            run_configuration=run_configuration,
            mapping_name="classical",
            agents=agents,
            solver_result=classical_result,
            composite_map=map_context["classical_map"],
        )
        _append_visualization_candidate(
            candidates=visualization_candidates,
            case_spec=case_spec,
            run_configuration=run_configuration,
            mapping_name="cyclic",
            agents=agents,
            solver_result=cyclic_result,
            composite_map=map_context["cyclic_map"],
        )
        retained_pairs += 1
        logger.log(f"  Retained pairs: {retained_pairs}/{case_spec.counted_runs_required}")
        attempt_index += 1

    aggregate = build_reference_aggregate(
        case_spec=case_spec,
        classical_records=classical_records,
        cyclic_records=cyclic_records,
    )
    stop_summary = {
        "case_id": case_spec.case_id,
        "retained_pairs": retained_pairs,
        "attempts_used": attempt_index,
        "max_attempts": max_attempts,
        "completed_counted_quota": retained_pairs >= case_spec.counted_runs_required,
        "filter_individual_runs_until_cyclic_faster": case_spec.filter_individual_runs_until_cyclic_faster,
        "discarded_attempts_count": len(discarded_attempts),
    }
    if retained_pairs < case_spec.counted_runs_required:
        stop_summary["stop_reason"] = "max_attempts_exhausted_before_counted_quota"
        logger.log(
            "Stop summary: max attempts exhausted before retained-pair quota was reached "
            f"({retained_pairs}/{case_spec.counted_runs_required})."
        )
    else:
        stop_summary["stop_reason"] = None

    logger.log("Aggregate summary:")
    logger.log(f"  classical_avg_time={aggregate.classical_avg_time_computation_halted}")
    logger.log(f"  cyclic_avg_time={aggregate.cyclic_avg_time_computation_halted}")
    logger.log(f"  classical_avg_total_path_length={aggregate.classical_avg_total_path_length}")
    logger.log(f"  cyclic_avg_total_path_length={aggregate.cyclic_avg_total_path_length}")
    logger.log(f"  classical_avg_total_turns={aggregate.classical_avg_total_turns}")
    logger.log(f"  cyclic_avg_total_turns={aggregate.cyclic_avg_total_turns}")

    return {
        "case_spec": case_spec,
        "run_configurations": run_configurations,
        "run_records": run_records,
        "aggregate": aggregate.to_dict(),
        "discarded_attempts": discarded_attempts,
        "visualization_candidates": visualization_candidates,
        "stop_summary": stop_summary,
    }


def _write_graphs_and_data_outputs(
    *,
    case_spec: RefCaseSpec,
    raw_payload: dict[str, Any],
    output_manager: RefCaseOutputManager,
    logger: RefExperimentLogger,
) -> list[Path]:
    output_manager.clear_graphs_and_data_outputs()
    run_configurations = list(raw_payload.get("run_configurations", []))
    run_records = list(raw_payload.get("run_records", []))
    aggregate_payload = dict(raw_payload.get("aggregate") or {})
    discarded_attempts = list(raw_payload.get("discarded_attempts", []))
    stop_summary = dict(raw_payload.get("stop_summary", {}))

    write_json(output_manager.metadata_dir / "case_spec.json", case_spec.to_dict())
    write_json(output_manager.metadata_dir / "stop_summary.json", stop_summary)
    write_json(output_manager.records_dir / "run_configurations.json", run_configurations)
    write_json(output_manager.records_dir / "run_records.json", run_records)
    write_json(output_manager.records_dir / "discarded_attempts.json", discarded_attempts)
    write_json(output_manager.aggregates_dir / "condition_summary.json", aggregate_payload)
    write_csv(output_manager.records_dir / "run_configurations.csv", run_configurations)
    write_csv(output_manager.records_dir / "run_records.csv", run_records)
    write_csv(output_manager.records_dir / "discarded_attempts.csv", [
        {
            "attempt_index": row.get("attempt_index"),
            "reason": row.get("reason"),
            "classical_halted": row.get("classical_halted"),
            "cyclic_halted": row.get("cyclic_halted"),
        }
        for row in discarded_attempts
    ])
    write_csv(output_manager.aggregates_dir / "condition_summary.csv", [aggregate_payload] if aggregate_payload else [])

    aggregate = RefConditionAggregate(**aggregate_payload)
    graph_paths = generate_reference_graphs(case_spec, aggregate, output_manager.graphs_dir)
    logger.log("Generated graph/data outputs:")
    for path in graph_paths:
        logger.log(f"  - {path}")
    return graph_paths


def _write_visualization_outputs(
    *,
    raw_payload: dict[str, Any],
    output_manager: RefCaseOutputManager,
    logger: RefExperimentLogger,
) -> dict[str, Any]:
    output_manager.clear_visualization_outputs()
    candidates = list(raw_payload.get("visualization_candidates", []))
    summary = render_reference_visualizations(
        candidates=candidates,
        output_root=output_manager.visualizations_dir,
        num_last_successful_runs_per_mapping=NUM_LAST_SUCCESSFUL_RUNS_TO_VISUALIZE_PER_MAPPING,
    )
    write_json(output_manager.metadata_dir / "visualization_selection_summary.json", summary)
    logger.log(
        "Generated reference visualizations | "
        f"selected_candidates={summary.get('selected_candidates', 0)} | "
        f"available_candidates={summary.get('available_candidates', 0)}"
    )
    return summary


def run_reference_case(
    case_spec: RefCaseSpec,
    *,
    generation_target: str,
    program_start_time: float | None = None,
) -> dict[str, Any]:
    output_manager = RefCaseOutputManager(
        case_spec,
        generation_target=generation_target,
        recompute_mapf=bool(recompute_MAPF),
    )
    logger = RefExperimentLogger(output_manager.prepare_log_output(), start_time=program_start_time)
    raw_store = RefRawDataStore(case_spec)

    _log_case_header(logger, case_spec)
    logger.log(f"recompute_MAPF: {bool(recompute_MAPF)}")
    logger.log(f"to_generate: {generation_target}")
    logger.log(f"raw_reference_data_root: {raw_store.case_root}")
    logger.log_elapsed("Reference-comparison stopwatch started.")

    if recompute_MAPF:
        logger.log("Computing raw reference-comparison MAPF data and replacing the saved copy...")
        payload = _compute_reference_case(case_spec, logger)
        raw_store.save(payload)
        logger.log_elapsed("Raw reference-comparison data computed and saved.")
    else:
        logger.log("recompute_MAPF is False. Persisted raw reference-comparison data will be reused if outputs are requested.")

    graph_paths: list[Path] = []
    visualization_summary: dict[str, Any] = {}
    raw_payload_used = False

    if generation_target == "nothing":
        logger.log("No graphs, data exports, or visualizations generated because to_generate='nothing'.")
    else:
        raw_payload = raw_store.load()
        raw_payload_used = True
        logger.log("Loaded persisted raw reference-comparison data for output generation.")
        if generation_target == "graphs_and_data":
            graph_paths = _write_graphs_and_data_outputs(
                case_spec=case_spec,
                raw_payload=raw_payload,
                output_manager=output_manager,
                logger=logger,
            )
        elif generation_target == "visualization":
            visualization_summary = _write_visualization_outputs(
                raw_payload=raw_payload,
                output_manager=output_manager,
                logger=logger,
            )

    logger.log_elapsed("Reference-comparison case finished.")
    return {
        "case_id": case_spec.case_id,
        "output_root": str(output_manager.case_root),
        "raw_reference_data_root": str(raw_store.case_root),
        "graph_paths": [str(path) for path in graph_paths],
        "visualization_summary": visualization_summary,
        "generation_target": generation_target,
        "recompute_MAPF": bool(recompute_MAPF),
        "raw_payload_used_for_generation": raw_payload_used,
    }


def run_selected_ref_comparison(*, program_start_time: float | None = None) -> dict[str, Any]:
    generation_target = _resolve_generation_target()
    case_ids = _selected_case_ids()
    results = []
    for case_id in case_ids:
        case_spec = _build_case_spec(case_id)
        results.append(
            run_reference_case(
                case_spec,
                generation_target=generation_target,
                program_start_time=program_start_time,
            )
        )
    return {
        "selected_port_experiment": SELECTED_PORT_EXPERIMENT,
        "case_ids": case_ids,
        "results": results,
    }
