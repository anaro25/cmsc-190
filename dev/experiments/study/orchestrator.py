from __future__ import annotations

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
from dev.experiments.study.preparation import (
    prepare_dynamic_branch_state,
    prepare_dynamic_run_context,
    prepare_static_run_context,
)
from dev.experiments.study.runtime import build_mapping_record, run_dynamic_mapping, run_static_mapping
from dev.experiments.study.visualization import render_selected_visualizations


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


def run_selected_experiment(
    map_type: str,
    *,
    seed_base: int | None = None,
    program_start_time: float | None = None,
) -> dict[str, Any]:
    branch_spec = get_branch_spec(map_type)
    resolved_seed_base = branch_spec.seed_base if seed_base is None else seed_base
    output_manager = BranchOutputManager(branch_spec)
    logger = ExperimentLogger(
        output_manager.logs_dir / "experiment.log",
        start_time=program_start_time,
    )
    log_branch_header(logger, branch_spec)
    logger.log_elapsed("Program stopwatch started.")
    write_json(output_manager.metadata_dir / "branch_spec.json", branch_spec.to_dict())

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
        write_json(
            output_manager.metadata_dir / "shared_dynamic_state.json",
            {
                "map_identifier": dynamic_state.map_identifier,
                "schedule_seed": dynamic_state.schedule_seed,
                "generation_mode": dynamic_state.generation_mode,
                "static_rows": len(dynamic_state.static_matrix),
                "static_cols": len(dynamic_state.static_matrix[0]) if dynamic_state.static_matrix else 0,
                "dynamic_loop_length": len(dynamic_state.dynamic_loop_frames),
            },
        )

    for agent_number_index, agent_number in enumerate(branch_spec.agent_numbers):
        logger.log("")
        logger.log("-" * 88)
        logger.log(
            f"Condition {agent_number_index + 1}/{len(branch_spec.agent_numbers)} | "
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
                f"Condition {agent_number_index + 1}/{len(branch_spec.agent_numbers)} completed "
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
                f"Condition {agent_number_index + 1}/{len(branch_spec.agent_numbers)} stopped the branch "
                f"(agent_number={agent_number})."
            )
            break

    write_json(output_manager.records_dir / "run_configurations.json", run_configurations)
    write_json(output_manager.records_dir / "run_records.json", run_records)
    write_json(output_manager.aggregates_dir / "condition_summary.json", aggregates_payload)
    write_csv(output_manager.records_dir / "run_configurations.csv", run_configurations)
    write_csv(output_manager.records_dir / "run_records.csv", run_records)
    write_csv(output_manager.aggregates_dir / "condition_summary.csv", aggregates_payload)
    write_json(output_manager.metadata_dir / "branch_stop_summary.json", branch_stop_summary)
    logger.log_elapsed("Structured records and summaries written to disk.")

    aggregate_objects = [ConditionAggregate(**payload) for payload in aggregates_payload]
    graph_paths = generate_graphs(branch_spec, aggregate_objects, output_manager.graphs_dir)
    visualization_summary = render_selected_visualizations(
        branch_spec=branch_spec,
        output_manager=output_manager,
        dynamic_state=dynamic_state,
        all_candidates=all_visualization_candidates,
        logger=logger,
    )
    logger.log_elapsed("Graphs and visualization exports completed.")

    logger.log("")
    logger.log("Final aggregate table:")
    for aggregate in aggregate_objects:
        print_aggregate_block(logger, aggregate)

    if branch_stop_summary["stop_triggered"]:
        logger.log("")
        logger.log("Branch stopped early:")
        logger.log(f"  Reason: {branch_stop_summary['stop_reason']}")
        logger.log(f"  Details: {branch_stop_summary['stop_message']}")
        logger.log(
            "  Reported agent numbers: "
            f"{branch_stop_summary['reported_agent_numbers']}"
        )

    logger.log("")
    logger.log_elapsed("Experiment finished.")
    logger.log("")
    logger.log("Generated graph files:")
    for graph_path in graph_paths:
        logger.log(f"  - {graph_path}")

    return {
        "branch_spec": branch_spec.to_dict(),
        "output_root": str(output_manager.branch_root),
        "run_configurations_path": str(output_manager.records_dir / "run_configurations.json"),
        "run_records_path": str(output_manager.records_dir / "run_records.json"),
        "condition_summary_path": str(output_manager.aggregates_dir / "condition_summary.json"),
        "branch_stop_summary_path": str(output_manager.metadata_dir / "branch_stop_summary.json"),
        "graph_paths": [str(path) for path in graph_paths],
        "visualizations_root": str(output_manager.visualizations_dir),
        "visualization_summary_path": str(output_manager.metadata_dir / "visualization_selection_summary.json"),
        "num_visualized_run_configurations": len(visualization_summary["selected_run_configurations"]),
        "log_path": str(output_manager.logs_dir / "experiment.log"),
    }
