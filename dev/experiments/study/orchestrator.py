from __future__ import annotations

from pathlib import Path
from typing import Any

from dev.experiments.branch_specs import get_branch_spec
from dev.experiments.study.aggregation import build_condition_aggregate
from dev.experiments.study.constants import (
    CONSECUTIVE_FAILED_PAIRED_SAMPLING_STOP_LIMIT,
    INTERNAL_COUNTED_RUN_ATTEMPT_SAFEGUARD,
)
from dev.experiments.study.io_utils import (
    BranchOutputManager,
    BufferedExperimentLogger,
    ExperimentLogger,
    write_csv,
    write_json,
)
from dev.experiments.study.logging_utils import (
    log_branch_header,
    log_dynamic_state,
    log_mapping_record,
    print_aggregate_block,
)
from dev.experiments.study.models import (
    ConditionAggregate,
    DynamicBranchState,
    MappingRunRecord,
    PreparedRunContext,
    SamplingConditionResult,
    VisualizationCandidate,
)
from dev.experiments.study.plotting import generate_graphs
from dev.experiments.study.raw_data_store import BranchRawDataStore
from dev.experiments.study.preparation import (
    prepare_dynamic_branch_state,
    prepare_dynamic_run_context,
    prepare_static_run_context,
)
from dev.experiments.study.runtime import build_mapping_record, run_dynamic_mapping, run_static_mapping
from dev.experiments.study.visualization import render_selected_visualizations
from dev.master_config import recompute_MAPF, to_generate


def _prepare_run_context(
    *,
    branch_spec,
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
    branch_spec,
    dynamic_state: DynamicBranchState | None,
    prepared_context: PreparedRunContext,
    mapping_name: str,
    logger,
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
    )


def _run_jointly_viable_sampling(
    *,
    branch_spec,
    dynamic_state: DynamicBranchState | None,
    agent_number: int,
    agent_number_index: int,
    seed_base: int,
    logger: ExperimentLogger,
) -> SamplingConditionResult:
    classical_records: list[MappingRunRecord] = []
    cyclic_records: list[MappingRunRecord] = []
    run_configurations: list[dict[str, Any]] = []
    run_records: list[dict[str, Any]] = []
    visualization_candidates: list[VisualizationCandidate] = []

    attempt_index = 0
    retained_pairs = 0
    total_paired_sampling_attempts = 0
    consecutive_failed_paired_sampling_attempts = 0

    while (
        retained_pairs < branch_spec.counted_runs_required
        and attempt_index < INTERNAL_COUNTED_RUN_ATTEMPT_SAFEGUARD
    ):
        run_index = attempt_index
        logger.log(
            f"  Preparing paired sampling attempt {attempt_index + 1}... | "
            f"agent_number={agent_number} | run_index={run_index}"
        )
        try:
            prepared_context = _prepare_run_context(
                branch_spec=branch_spec,
                dynamic_state=dynamic_state,
                agent_number=agent_number,
                agent_number_index=agent_number_index,
                run_index=run_index,
                seed_base=seed_base,
            )
        except Exception as exc:
            logger.log(
                f"  Warning: skipped run_index={run_index} during preparation | "
                f"setup_failed={type(exc).__name__}: {exc}"
            )
            attempt_index += 1
            continue

        total_paired_sampling_attempts += 1
        logger.log(
            f"  Paired sampling attempt {attempt_index + 1} ongoing... | "
            f"{prepared_context.run_configuration.run_config_id} | "
            f"map_id={prepared_context.run_configuration.map_identifier}"
        )
        buffered_logger = BufferedExperimentLogger()

        classical_solver_result, classical_elapsed_seconds, classical_solver_status = _execute_mapping(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            prepared_context=prepared_context,
            mapping_name="classical",
            logger=buffered_logger,
        )
        classical_record = build_mapping_record(
            run_configuration=prepared_context.run_configuration,
            mapping_name="classical",
            comparison_case="paired_jointly_viable_sampling",
            runtime_limit_seconds=branch_spec.runtime_limit_seconds,
            solver_name=(classical_solver_result or {}).get("solver_name", branch_spec.solver_name),
            enhanced_cbs_enabled=branch_spec.enhanced_cbs_enabled,
            solver_suboptimality_factor=(classical_solver_result or {}).get("solver_suboptimality_factor", branch_spec.solver_suboptimality_factor),
            solver_result=classical_solver_result,
            elapsed_seconds=classical_elapsed_seconds,
            solver_status=classical_solver_status,
            paired_run=True,
            dynamic=branch_spec.is_dynamic,
        )

        cyclic_solver_result, cyclic_elapsed_seconds, cyclic_solver_status = _execute_mapping(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            prepared_context=prepared_context,
            mapping_name="cyclic",
            logger=buffered_logger,
        )
        cyclic_record = build_mapping_record(
            run_configuration=prepared_context.run_configuration,
            mapping_name="cyclic",
            comparison_case="paired_jointly_viable_sampling",
            runtime_limit_seconds=branch_spec.runtime_limit_seconds,
            solver_name=(cyclic_solver_result or {}).get("solver_name", branch_spec.solver_name),
            enhanced_cbs_enabled=branch_spec.enhanced_cbs_enabled,
            solver_suboptimality_factor=(cyclic_solver_result or {}).get("solver_suboptimality_factor", branch_spec.solver_suboptimality_factor),
            solver_result=cyclic_solver_result,
            elapsed_seconds=cyclic_elapsed_seconds,
            solver_status=cyclic_solver_status,
            paired_run=True,
            dynamic=branch_spec.is_dynamic,
        )

        both_counted = classical_record.counted_run and cyclic_record.counted_run
        if both_counted:
            prepared_context.run_configuration.paired_source = True
            run_configurations.append(prepared_context.run_configuration.to_dict())
            classical_records.append(classical_record)
            cyclic_records.append(cyclic_record)
            run_records.append(classical_record.to_dict())
            run_records.append(cyclic_record.to_dict())
            if classical_record.solved_run and classical_solver_result is not None:
                visualization_candidates.append(
                    VisualizationCandidate(
                        mapping_name="classical",
                        run_configuration=prepared_context.run_configuration,
                        agents=prepared_context.agents,
                        solver_result=classical_solver_result,
                        composite_map=prepared_context.classical_map,
                    )
                )
            if cyclic_record.solved_run and cyclic_solver_result is not None:
                visualization_candidates.append(
                    VisualizationCandidate(
                        mapping_name="cyclic",
                        run_configuration=prepared_context.run_configuration,
                        agents=prepared_context.agents,
                        solver_result=cyclic_solver_result,
                        composite_map=prepared_context.cyclic_map,
                    )
                )
            buffered_logger.flush_to(logger)
            log_mapping_record(logger, classical_record)
            log_mapping_record(logger, cyclic_record)
            retained_pairs += 1
            consecutive_failed_paired_sampling_attempts = 0
            logger.log(
                f"      Jointly viable counted pairs: {retained_pairs}/{branch_spec.counted_runs_required}"
            )
            logger.log("")
        else:
            if (
                classical_record.result_category == "unsolvable"
                or cyclic_record.result_category == "unsolvable"
            ):
                consecutive_failed_paired_sampling_attempts += 1
                logger.log(
                    "      Discarded paired sampling attempt due to joint unsolvability screening | "
                    f"classical={classical_record.result_category} | "
                    f"cyclic={cyclic_record.result_category} | "
                    "consecutive_failed_paired_sampling_attempts="
                    f"{consecutive_failed_paired_sampling_attempts}/"
                    f"{CONSECUTIVE_FAILED_PAIRED_SAMPLING_STOP_LIMIT}"
                )
            else:
                logger.log(
                    "      Discarded paired sampling attempt due to non-reportable setup outcome | "
                    f"classical={classical_record.result_category} | "
                    f"cyclic={cyclic_record.result_category}"
                )

            logger.log("")

            if (
                consecutive_failed_paired_sampling_attempts
                >= CONSECUTIVE_FAILED_PAIRED_SAMPLING_STOP_LIMIT
            ):
                stop_message = (
                    "Stop rule triggered: encountered "
                    f"{CONSECUTIVE_FAILED_PAIRED_SAMPLING_STOP_LIMIT} consecutive failed paired "
                    f"sampling attempts at agent_number={agent_number}. "
                    "The current condition is discarded and the branch stops before higher agent numbers."
                )
                logger.log(f"  {stop_message}")
                return SamplingConditionResult(
                    accepted_for_reporting=False,
                    stop_branch=True,
                    stop_reason="consecutive_failed_paired_sampling_attempts",
                    stop_message=stop_message,
                    retained_pairs=retained_pairs,
                    total_paired_sampling_attempts=total_paired_sampling_attempts,
                    consecutive_failed_paired_sampling_attempts=consecutive_failed_paired_sampling_attempts,
                )

        attempt_index += 1

    if retained_pairs < branch_spec.counted_runs_required:
        stop_message = (
            "Stop rule triggered by the internal attempt safeguard before the counted-pair quota was reached "
            f"({retained_pairs}/{branch_spec.counted_runs_required}) at agent_number={agent_number}. "
            "The current condition is discarded and the branch stops before higher agent numbers."
        )
        logger.log(f"  {stop_message}")
        return SamplingConditionResult(
            accepted_for_reporting=False,
            stop_branch=True,
            stop_reason="internal_attempt_safeguard",
            stop_message=stop_message,
            retained_pairs=retained_pairs,
            total_paired_sampling_attempts=total_paired_sampling_attempts,
            consecutive_failed_paired_sampling_attempts=consecutive_failed_paired_sampling_attempts,
        )

    num_cyclic_successful_runs = sum(
        record.result_category == "successful" for record in cyclic_records
    )
    num_cyclic_unfinished_runs = sum(
        record.result_category == "unfinished" for record in cyclic_records
    )
    if num_cyclic_unfinished_runs > num_cyclic_successful_runs:
        stop_message = (
            "Stop rule triggered: cyclic unfinished runs exceeded cyclic successful runs within the "
            f"retained counted pairs at agent_number={agent_number} "
            f"({num_cyclic_unfinished_runs} unfinished > {num_cyclic_successful_runs} successful). "
            "The current condition is discarded and the branch stops before higher agent numbers."
        )
        logger.log(f"  {stop_message}")
        return SamplingConditionResult(
            accepted_for_reporting=False,
            stop_branch=True,
            stop_reason="cyclic_unfinished_exceeded_successful",
            stop_message=stop_message,
            retained_pairs=retained_pairs,
            total_paired_sampling_attempts=total_paired_sampling_attempts,
            consecutive_failed_paired_sampling_attempts=consecutive_failed_paired_sampling_attempts,
        )

    return SamplingConditionResult(
        accepted_for_reporting=True,
        stop_branch=False,
        classical_records=classical_records,
        cyclic_records=cyclic_records,
        run_configurations=run_configurations,
        run_records=run_records,
        visualization_candidates=visualization_candidates,
        retained_pairs=retained_pairs,
        total_paired_sampling_attempts=total_paired_sampling_attempts,
        consecutive_failed_paired_sampling_attempts=consecutive_failed_paired_sampling_attempts,
    )


VALID_GENERATION_TARGETS = {"graphs_and_data", "visualization", "nothing"}


def _resolve_generation_target() -> str:
    generation_target = str(to_generate)
    if generation_target not in VALID_GENERATION_TARGETS:
        raise ValueError(
            "to_generate must be one of 'graphs_and_data', 'visualization', or 'nothing'."
        )
    return generation_target


def _build_dynamic_state_metadata(dynamic_state: DynamicBranchState) -> dict[str, Any]:
    return {
        "map_identifier": dynamic_state.map_identifier,
        "schedule_seed": dynamic_state.schedule_seed,
        "generation_mode": dynamic_state.generation_mode,
        "static_rows": len(dynamic_state.static_matrix),
        "static_cols": len(dynamic_state.static_matrix[0]) if dynamic_state.static_matrix else 0,
        "dynamic_loop_length": len(dynamic_state.dynamic_loop_frames),
    }


def _compute_raw_branch_data(
    *,
    branch_spec,
    resolved_seed_base: int,
    logger: ExperimentLogger,
) -> dict[str, Any]:
    run_configurations: list[dict[str, Any]] = []
    run_records: list[dict[str, Any]] = []
    aggregates_payload: list[dict[str, Any]] = []
    branch_stop_summary = {
        "stop_triggered": False,
        "stop_reason": None,
        "stop_message": "",
        "stopped_before_agent_number": None,
        "reported_agent_numbers": [],
        "planned_agent_numbers": branch_spec.agent_numbers,
    }
    all_visualization_candidates: list[VisualizationCandidate] = []

    dynamic_state: DynamicBranchState | None = None
    if branch_spec.is_dynamic:
        logger.log("Preparing shared dynamic map state before iterating agent-number conditions...")
        dynamic_state = prepare_dynamic_branch_state(
            branch_spec,
            seed_base=resolved_seed_base,
            logger=logger,
        )
        log_dynamic_state(logger, branch_spec, dynamic_state)
        logger.log_elapsed("Shared dynamic map preparation completed.")

    for agent_number_index, agent_number in enumerate(branch_spec.agent_numbers):
        logger.log("")
        logger.log("-" * 88)
        logger.log(
            f"Condition {agent_number_index + 1} | "
            f"agent_number={agent_number} | condition_id=agent_number[{branch_spec.branch_decimal}.{agent_number_index}]"
        )
        logger.log("-" * 88)

        sampling_result = _run_jointly_viable_sampling(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            agent_number=agent_number,
            agent_number_index=agent_number_index,
            seed_base=resolved_seed_base,
            logger=logger,
        )

        if sampling_result.accepted_for_reporting:
            run_configurations.extend(sampling_result.run_configurations)
            run_records.extend(sampling_result.run_records)
            all_visualization_candidates.extend(sampling_result.visualization_candidates)
            aggregate = build_condition_aggregate(
                branch_spec=branch_spec,
                agent_number=agent_number,
                agent_number_index=agent_number_index,
                classical_records=sampling_result.classical_records,
                cyclic_records=sampling_result.cyclic_records,
                paired_run_configurations=min(
                    len(sampling_result.classical_records),
                    len(sampling_result.cyclic_records),
                ),
            )
            aggregates_payload.append(aggregate.to_dict())
            branch_stop_summary["reported_agent_numbers"].append(agent_number)
            print_aggregate_block(logger, aggregate)
            logger.log_elapsed(
                f"Condition {agent_number_index + 1} completed "
                f"(agent_number={agent_number})."
            )
            continue

        if sampling_result.stop_branch:
            branch_stop_summary.update(
                {
                    "stop_triggered": True,
                    "stop_reason": sampling_result.stop_reason,
                    "stop_message": sampling_result.stop_message,
                    "stopped_before_agent_number": agent_number,
                }
            )
            logger.log_elapsed(
                f"Condition {agent_number_index + 1} stopped the branch "
                f"(agent_number={agent_number})."
            )
            break

    return {
        "branch_spec": branch_spec,
        "dynamic_state": dynamic_state,
        "run_configurations": run_configurations,
        "run_records": run_records,
        "aggregates_payload": aggregates_payload,
        "branch_stop_summary": branch_stop_summary,
        "all_visualization_candidates": all_visualization_candidates,
    }


def _write_graphs_and_data_outputs(
    *,
    current_branch_spec,
    raw_payload: dict[str, Any],
    output_manager: BranchOutputManager,
    logger: ExperimentLogger,
) -> list[Path]:
    raw_branch_spec = raw_payload["branch_spec"]
    dynamic_state = raw_payload.get("dynamic_state")
    run_configurations = list(raw_payload.get("run_configurations", []))
    run_records = list(raw_payload.get("run_records", []))
    aggregates_payload = list(raw_payload.get("aggregates_payload", []))
    branch_stop_summary = dict(raw_payload.get("branch_stop_summary", {}))

    output_manager.clear_graphs_and_data_outputs()
    write_json(output_manager.metadata_dir / "branch_spec.json", raw_branch_spec.to_dict())
    write_json(
        output_manager.metadata_dir / "graph_generation_branch_spec.json",
        current_branch_spec.to_dict(),
    )
    if dynamic_state is not None:
        write_json(
            output_manager.metadata_dir / "shared_dynamic_state.json",
            _build_dynamic_state_metadata(dynamic_state),
        )
    write_json(output_manager.records_dir / "run_configurations.json", run_configurations)
    write_json(output_manager.records_dir / "run_records.json", run_records)
    write_json(output_manager.aggregates_dir / "condition_summary.json", aggregates_payload)
    write_csv(output_manager.records_dir / "run_configurations.csv", run_configurations)
    write_csv(output_manager.records_dir / "run_records.csv", run_records)
    write_csv(output_manager.aggregates_dir / "condition_summary.csv", aggregates_payload)
    write_json(output_manager.metadata_dir / "branch_stop_summary.json", branch_stop_summary)
    logger.log_elapsed("Structured records and summaries regenerated from persisted raw MAPF data.")

    aggregate_objects = [ConditionAggregate(**payload) for payload in aggregates_payload]
    graph_paths = generate_graphs(current_branch_spec, aggregate_objects, output_manager.graphs_dir)
    if raw_branch_spec.agent_numbers != current_branch_spec.agent_numbers:
        logger.log(
            "Graph tick labels are generated from the agent numbers that are actually present in the persisted raw MAPF data, "
            "so later master_config.py domain edits do not stretch the x-axis when regenerating old graphs."
        )
    logger.log_elapsed("Graphs regenerated from persisted raw MAPF data.")

    logger.log("")
    logger.log("Final aggregate table:")
    for aggregate in aggregate_objects:
        print_aggregate_block(logger, aggregate)

    if branch_stop_summary.get("stop_triggered"):
        logger.log("")
        logger.log("Branch stopped early:")
        logger.log(f"  Reason: {branch_stop_summary.get('stop_reason')}")
        logger.log(f"  Details: {branch_stop_summary.get('stop_message')}")
        logger.log(
            "  Reported agent numbers: "
            f"{branch_stop_summary.get('reported_agent_numbers', [])}"
        )

    logger.log("")
    logger.log("Generated graph files:")
    for graph_path in graph_paths:
        logger.log(f"  - {graph_path}")
    return graph_paths


def _write_visualization_outputs(
    *,
    current_branch_spec,
    raw_payload: dict[str, Any],
    output_manager: BranchOutputManager,
    logger: ExperimentLogger,
) -> dict[str, Any]:
    raw_branch_spec = raw_payload["branch_spec"]
    dynamic_state = raw_payload.get("dynamic_state")
    all_visualization_candidates = list(raw_payload.get("all_visualization_candidates", []))

    logger.log(
        "Visualization selection controls are being read from the current master_config.py "
        f"for branch '{current_branch_spec.map_type}' "
        "("
        f"num_last_runs_to_visualize_jointly_successful="
        f"{current_branch_spec.num_last_runs_to_visualize_jointly_successful}, "
        f"num_last_runs_to_visualize_independently_successful="
        f"{current_branch_spec.num_last_runs_to_visualize_independently_successful}"
        ")."
    )
    output_manager.clear_visualization_outputs()
    visualization_summary = render_selected_visualizations(
        branch_spec=raw_branch_spec,
        output_manager=output_manager,
        dynamic_state=dynamic_state,
        all_candidates=all_visualization_candidates,
        logger=logger,
        num_last_runs_to_visualize_jointly_successful=(
            current_branch_spec.num_last_runs_to_visualize_jointly_successful
        ),
        num_last_runs_to_visualize_independently_successful=(
            current_branch_spec.num_last_runs_to_visualize_independently_successful
        ),
    )
    logger.log_elapsed("Pillow visualizations regenerated from persisted raw MAPF data using the current visualization controls.")
    logger.log(
        "Selected visualization entries generated across both variants: "
        f"{visualization_summary.get('total_selected_run_configurations', 0)}"
    )
    return visualization_summary


def run_selected_experiment(
    map_type: str,
    *,
    seed_base: int | None = None,
    program_start_time: float | None = None,
) -> dict[str, Any]:
    branch_spec = get_branch_spec(map_type)
    resolved_seed_base = branch_spec.seed_base if seed_base is None else seed_base
    generation_target = _resolve_generation_target()
    output_manager = BranchOutputManager(
        branch_spec,
        generation_target=generation_target,
        recompute_mapf=bool(recompute_MAPF),
    )
    log_path = output_manager.prepare_log_output()
    logger = ExperimentLogger(log_path, start_time=program_start_time)
    raw_store = BranchRawDataStore(branch_spec)

    log_branch_header(logger, branch_spec)
    logger.log(f"recompute_MAPF: {bool(recompute_MAPF)}")
    logger.log(f"to_generate: {generation_target}")
    logger.log(f"Persisted raw MAPF data root: {raw_store.branch_root}")
    logger.log(f"Persisted raw MAPF manifest path: {raw_store.manifest_path}")
    logger.log_elapsed("Program stopwatch started.")

    if recompute_MAPF:
        logger.log("")
        logger.log("Recomputing raw MAPF data for the selected branch and replacing the saved copy...")
        computed_payload = _compute_raw_branch_data(
            branch_spec=branch_spec,
            resolved_seed_base=resolved_seed_base,
            logger=logger,
        )
        raw_store.save(computed_payload)
        logger.log_elapsed("Raw MAPF data recomputed and saved.")
        logger.log("If graphs or visualization are requested in this run, they will be regenerated from the saved raw MAPF data on disk.")
    else:
        logger.log("")
        logger.log("recompute_MAPF is False. The persisted raw MAPF data for this branch will remain unchanged.")

    graph_paths: list[Path] = []
    visualization_summary: dict[str, Any] = {
        "selected_run_configurations": [],
        "selected_run_configurations_by_mapping": {"classical": [], "cyclic": []},
    }
    raw_payload_used = False
    result_branch_spec = branch_spec

    if generation_target == "nothing":
        logger.log("No graphs, data exports, or Pillow visualizations were generated because to_generate='nothing'.")
    else:
        try:
            if generation_target == "graphs_and_data":
                raw_payload = raw_store.load_graphs_and_data_payload()
            else:
                raw_payload = raw_store.load_visualization_payload()
        except FileNotFoundError as exc:
            logger.log(str(exc))
            raise
        raw_payload_used = True
        result_branch_spec = raw_payload["branch_spec"]
        if recompute_MAPF:
            logger.log("Reloaded the saved raw MAPF data from disk for output generation consistency.")
        else:
            logger.log("Loaded the persisted raw MAPF data for output generation.")

        if generation_target == "graphs_and_data":
            graph_paths = _write_graphs_and_data_outputs(
                current_branch_spec=branch_spec,
                raw_payload=raw_payload,
                output_manager=output_manager,
                logger=logger,
            )
        elif generation_target == "visualization":
            visualization_summary = _write_visualization_outputs(
                current_branch_spec=branch_spec,
                raw_payload=raw_payload,
                output_manager=output_manager,
                logger=logger,
            )

    logger.log("")
    logger.log_elapsed("Experiment finished.")

    return {
        "branch_spec": result_branch_spec.to_dict(),
        "output_root": str(output_manager.branch_root),
        "raw_mapf_data_path": str(raw_store.branch_root),
        "raw_mapf_data_manifest_path": str(raw_store.manifest_path),
        "raw_mapf_data_summary_path": str(raw_store.summary_path),
        "run_configurations_path": str(output_manager.records_dir / "run_configurations.json"),
        "run_records_path": str(output_manager.records_dir / "run_records.json"),
        "condition_summary_path": str(output_manager.aggregates_dir / "condition_summary.json"),
        "branch_stop_summary_path": str(output_manager.metadata_dir / "branch_stop_summary.json"),
        "graph_paths": [str(path) for path in graph_paths],
        "visualizations_root": str(output_manager.visualizations_dir),
        "visualization_summary_path": str(output_manager.metadata_dir / "visualization_selection_summary.json"),
        "num_visualized_run_configurations": int(
            visualization_summary.get("total_selected_run_configurations", 0)
        ),
        "log_path": str(log_path),
        "generation_target": generation_target,
        "recompute_MAPF": bool(recompute_MAPF),
        "raw_payload_used_for_generation": raw_payload_used,
    }
