from __future__ import annotations

from pathlib import Path

from dev.experiments.ref_comparison.aggregation import build_reference_aggregate
from dev.experiments.ref_comparison.io_utils import RefCaseOutputManager, RefExperimentLogger, RefRawDataStore, write_csv, write_json
from dev.experiments.ref_comparison.models import RefCaseSpec, RefConditionAggregate, RefMappingRunRecord, RefVisualizationCandidate
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
    NUM_LAST_SUCCESSFUL_RUNS_TO_VISUALIZE_PER_MAPPING,
    REFERENCE_COMPARISON_CASES,
    REMOVE_EXTRA_TRANSITIONS,
    SELECTED_PORT_EXPERIMENT,
    SELECTED_PORT_EXPERIMENT_CASES,
    SHARED_ECBS_SUBOPTIMALITY,
    SHARED_TIME_LIMIT_SECONDS,
    SHARED_TIGHT_TIME_HORIZON,
    SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE,
    TEMPORARY_FILTER_INDIVIDUAL_RUNS_UNTIL_CYCLIC_FASTER_MAX_ATTEMPTS,
    agent_cohesion,
    cohesion_factor,
    enhanced_CBS,
    recompute_MAPF,
    to_generate,
)

VALID_GENERATION_TARGETS = {"graphs_and_data", "visualization", "nothing"}


def _normalize_map_agent_numbers(value: object) -> dict[int, int]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[int, int] = {}
    for key, raw_count in value.items():
        map_number = int(key)
        agent_count = int(raw_count)
        if map_number <= 0:
            raise ValueError(f"Reference map numbers must be positive. Found {map_number}.")
        if agent_count <= 0:
            raise ValueError(f"Agent count for reference port map {map_number} must be positive. Found {agent_count}.")
        normalized[map_number] = agent_count
    return normalized


def _agent_number_for_map(case_spec: RefCaseSpec, map_number: int | None) -> int:
    if case_spec.experiment_mode != "multi_agent" or map_number is None:
        return int(case_spec.agent_number)
    return int(case_spec.map_agent_numbers.get(int(map_number), case_spec.agent_number))


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
        agent_number=int(config["agent_number"]),
        map_agent_numbers=_normalize_map_agent_numbers(config.get("map_agent_numbers", {})),
        counted_runs_required=int(config["counted_runs_required"]),
        runtime_limit_seconds=float(SHARED_TIME_LIMIT_SECONDS),
        use_ecbs=bool(enhanced_CBS) if experiment_mode == "multi_agent" else False,
        ecbs_suboptimality=float(SHARED_ECBS_SUBOPTIMALITY),
        true_static_shortest_path_distance=bool(SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE),
        tight_time_horizon=bool(SHARED_TIGHT_TIME_HORIZON),
        remove_extra_transitions=bool(REMOVE_EXTRA_TRANSITIONS),
        add_transitions_between_free_spaces=bool(ADD_TRANSITIONS_BETWEEN_FREE_SPACES),
        agent_cohesion_enabled=bool(agent_cohesion) if experiment_mode == "multi_agent" else False,
        cohesion_factor=float(cohesion_factor),
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
            else "Tang-inspired multi-agent reference case. ECBS compares classical mapping against cyclic mapping across the three configured 50x50 port maps. Each map uses its configured agent count and fixed release/spawn rule, and runtime is averaged over three identical ECBS executions per mapping. The cyclic-faster temporary filter is disabled."
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
    if case_spec.experiment_mode == "multi_agent":
        logger.log(f"default_agent_number: {case_spec.agent_number}")
    else:
        logger.log(f"agent_number: {case_spec.agent_number}")
    logger.log(f"counted_runs_required: {case_spec.counted_runs_required}")
    if case_spec.experiment_mode == "single_agent":
        logger.log(f"single_agent_timing_repetitions: {case_spec.single_agent_timing_repetitions}")
    if case_spec.experiment_mode == "multi_agent":
        logger.log(f"multi_agent_timing_repetitions: {case_spec.multi_agent_timing_repetitions}")
        if case_spec.map_agent_numbers:
            formatted_counts = ", ".join(
                f"map_{map_number}={agent_count}"
                for map_number, agent_count in sorted(case_spec.map_agent_numbers.items())
            )
            logger.log(f"map_agent_numbers: {formatted_counts}")
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
    visually_free_vertex_positions: set[tuple[int, int]] | None = None,
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
            visually_free_vertex_positions=visually_free_vertex_positions,
        )
    )


def _format_timing_samples(samples: list[float]) -> str:
    return ", ".join(f"{sample:.4f}" for sample in samples)


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
            f"invisible_obstacles={map_context.get('invisible_obstacle_count', 0)} | "
            f"image_path={map_context['image_path']}"
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
        _append_visualization_candidate(candidates=visualization_candidates, case_spec=case_spec, run_configuration=run_configuration, mapping_name="classical", agents=agents, solver_result=classical_result, composite_map=map_context["classical_map"], visually_free_vertex_positions=map_context.get("invisible_obstacle_vertices") or None)
        _append_visualization_candidate(candidates=visualization_candidates, case_spec=case_spec, run_configuration=run_configuration, mapping_name="cyclic", agents=agents, solver_result=cyclic_result, composite_map=map_context["cyclic_map"], visually_free_vertex_positions=map_context.get("invisible_obstacle_vertices") or None)

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
    logger.log(
        "Preparing multi-agent reference maps across the three configured port maps "
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
            f"invisible_obstacles={map_context.get('invisible_obstacle_count', 0)} | "
            f"image_path={map_context['image_path']}"
        )

        agent_number_for_map = _agent_number_for_map(case_spec, map_context["map_number"])
        agents = build_multi_agent_spawn_sequence(case_spec, map_context, agent_number=agent_number_for_map)
        assignment_note = (
            f"{agent_number_for_map} agents share the upper-right target and use fixed release/spawn times "
            "from the upper and right neighbors of the lower-left start cell; "
            f"runtime is averaged over {timing_repetitions} identical repetitions per mapping"
        )
        run_configuration = build_run_configuration(
            case_spec=case_spec,
            run_index=map_index,
            map_identifier=map_context["map_identifier"],
            agents=agents,
            agent_number=agent_number_for_map,
            notes=assignment_note,
            map_index=map_context["map_index"],
            map_number=map_context["map_number"],
            map_label_value=map_context["map_label"],
        )
        logger.log(f"Map run_config_id={run_configuration.run_config_id}")

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
                "  Warning: repeated multi-agent timings produced differing statuses | "
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
        _append_visualization_candidate(candidates=visualization_candidates, case_spec=case_spec, run_configuration=run_configuration, mapping_name="classical", agents=agents, solver_result=classical_result, composite_map=map_context["classical_map"], visually_free_vertex_positions=map_context.get("invisible_obstacle_vertices") or None)
        _append_visualization_candidate(candidates=visualization_candidates, case_spec=case_spec, run_configuration=run_configuration, mapping_name="cyclic", agents=agents, solver_result=cyclic_result, composite_map=map_context["cyclic_map"], visually_free_vertex_positions=map_context.get("invisible_obstacle_vertices") or None)

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
        "multi_agent_timing_repetitions": timing_repetitions,
        "map_agent_numbers": {str(key): value for key, value in sorted(case_spec.map_agent_numbers.items())},
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


def _compute_reference_case(case_spec: RefCaseSpec, logger: RefExperimentLogger) -> dict:
    if case_spec.experiment_mode == "single_agent":
        return _compute_single_agent_case(case_spec, logger)
    return _compute_multi_agent_case(case_spec, logger)


def _write_graphs_and_data_outputs(*, case_spec: RefCaseSpec, raw_payload: dict, output_manager: RefCaseOutputManager, logger: RefExperimentLogger) -> list[Path]:
    output_manager.clear_graphs_and_data_outputs()
    run_configurations = list(raw_payload.get("run_configurations", []))
    run_records = list(raw_payload.get("run_records", []))
    aggregate_payload = dict(raw_payload.get("aggregate") or {})
    map_aggregates_payload = list(raw_payload.get("map_aggregates", []))
    discarded_attempts = list(raw_payload.get("discarded_attempts", []))
    stop_summary = dict(raw_payload.get("stop_summary", {}))

    write_json(output_manager.metadata_dir / "case_spec.json", case_spec.to_dict())
    write_json(output_manager.metadata_dir / "stop_summary.json", stop_summary)
    write_json(output_manager.records_dir / "run_configurations.json", run_configurations)
    write_json(output_manager.records_dir / "run_records.json", run_records)
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


def _write_visualization_outputs(*, raw_payload: dict, output_manager: RefCaseOutputManager, logger: RefExperimentLogger) -> dict:
    output_manager.clear_visualization_outputs()
    candidates = list(raw_payload.get("visualization_candidates", []))
    summary = render_reference_visualizations(
        candidates=candidates,
        output_root=output_manager.visualizations_dir,
        num_last_successful_runs_per_mapping=NUM_LAST_SUCCESSFUL_RUNS_TO_VISUALIZE_PER_MAPPING,
        progress_logger=logger.log,
    )
    write_json(output_manager.metadata_dir / "visualization_selection_summary.json", summary)
    logger.log(f"Generated reference visualizations | selected_candidates={summary.get('selected_candidates', 0)} | available_candidates={summary.get('available_candidates', 0)}")
    return summary


def run_reference_case(case_spec: RefCaseSpec, *, generation_target: str, program_start_time: float | None = None) -> dict:
    output_manager = RefCaseOutputManager(case_spec, generation_target=generation_target, recompute_mapf=bool(recompute_MAPF))
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
    visualization_summary: dict = {}
    raw_payload_used = False

    if generation_target == "nothing":
        logger.log("No graphs, data exports, or visualizations generated because to_generate='nothing'.")
    else:
        raw_payload = raw_store.load()
        raw_payload_used = True
        logger.log("Loaded persisted raw reference-comparison data for output generation.")
        if generation_target == "graphs_and_data":
            graph_paths = _write_graphs_and_data_outputs(case_spec=case_spec, raw_payload=raw_payload, output_manager=output_manager, logger=logger)
        elif generation_target == "visualization":
            visualization_summary = _write_visualization_outputs(raw_payload=raw_payload, output_manager=output_manager, logger=logger)

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


def run_selected_ref_comparison(*, program_start_time: float | None = None) -> dict:
    generation_target = _resolve_generation_target()
    case_ids = _selected_case_ids()
    results = []
    for case_id in case_ids:
        case_spec = _build_case_spec(case_id)
        results.append(run_reference_case(case_spec, generation_target=generation_target, program_start_time=program_start_time))
    return {"selected_port_experiment": SELECTED_PORT_EXPERIMENT, "case_ids": case_ids, "results": results}
