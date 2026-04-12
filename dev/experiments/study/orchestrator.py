from __future__ import annotations

from typing import Any

from dev.experiments.branch_specs import BranchSpec, get_branch_spec
from dev.experiments.study.aggregation import build_condition_aggregate
from dev.experiments.study.constants import MAX_CYCLIC_RECOVERY_ATTEMPTS
from dev.experiments.study.io_utils import BranchOutputManager, ExperimentLogger, write_csv, write_json
from dev.experiments.study.logging_utils import (
    log_branch_header,
    log_dynamic_state,
    log_mapping_record,
    print_aggregate_block,
)
from dev.experiments.study.models import ConditionAggregate, DynamicBranchState, MappingRunRecord, PreparedRunContext
from dev.experiments.study.plotting import generate_graphs
from dev.experiments.study.preparation import (
    build_failure_run_configuration,
    prepare_dynamic_branch_state,
    prepare_dynamic_run_context,
    prepare_static_run_context,
)
from dev.experiments.study.runtime import build_mapping_record, run_dynamic_mapping, run_static_mapping


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
) -> tuple[bool, dict[str, Any] | None, float, str | None]:
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


def _record_setup_failure(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState | None,
    seed_base: int,
    agent_number: int,
    agent_number_index: int,
    run_index: int,
    mapping_name: str,
    comparison_case: str,
    run_configurations: list[dict[str, Any]],
    run_records: list[dict[str, Any]],
    record_bucket: list[MappingRunRecord],
    logger: ExperimentLogger,
    exc: Exception,
) -> None:
    note = f"setup_failed:{type(exc).__name__}:{exc}"
    failure_run_config = build_failure_run_configuration(
        branch_spec=branch_spec,
        seed_base=seed_base,
        agent_number=agent_number,
        agent_number_index=agent_number_index,
        run_index=run_index,
        note=note,
        dynamic_schedule_seed=(dynamic_state.schedule_seed if dynamic_state is not None else None),
    )
    run_configurations.append(failure_run_config.to_dict())
    record = build_mapping_record(
        run_configuration=failure_run_config,
        mapping_name=mapping_name,
        comparison_case=comparison_case,
        runtime_limit_seconds=branch_spec.runtime_limit_seconds,
        solver_result=None,
        elapsed_seconds=0.0,
        paired_run=False,
        success=False,
        failure_reason=note,
        dynamic=branch_spec.is_dynamic,
    )
    record_bucket.append(record)
    run_records.append(record.to_dict())
    log_mapping_record(logger, record)


def _run_classical_phase(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState | None,
    agent_number: int,
    agent_number_index: int,
    seed_base: int,
    logger: ExperimentLogger,
    run_configurations: list[dict[str, Any]],
    run_records: list[dict[str, Any]],
) -> tuple[list[MappingRunRecord], list[PreparedRunContext]]:
    classical_records: list[MappingRunRecord] = []
    saved_success_contexts: list[PreparedRunContext] = []

    for classical_attempt_index in range(branch_spec.max_classical_attempts):
        run_index = classical_attempt_index
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
                f"  Classical attempt {classical_attempt_index + 1}/{branch_spec.max_classical_attempts} | "
                f"run_index={run_index} | setup_failed={type(exc).__name__}: {exc}"
            )
            _record_setup_failure(
                branch_spec=branch_spec,
                dynamic_state=dynamic_state,
                seed_base=seed_base,
                agent_number=agent_number,
                agent_number_index=agent_number_index,
                run_index=run_index,
                mapping_name="classical",
                comparison_case="classical_attempt",
                run_configurations=run_configurations,
                run_records=run_records,
                record_bucket=classical_records,
                logger=logger,
                exc=exc,
            )
            continue

        run_configurations.append(prepared_context.run_configuration.to_dict())
        logger.log(
            f"  Classical attempt {classical_attempt_index + 1}/{branch_spec.max_classical_attempts} | "
            f"{prepared_context.run_configuration.run_config_id} | "
            f"map_id={prepared_context.run_configuration.map_identifier}"
        )
        success, solver_result, elapsed_seconds, failure_reason = _execute_mapping(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            prepared_context=prepared_context,
            mapping_name="classical",
            logger=logger,
        )
        record = build_mapping_record(
            run_configuration=prepared_context.run_configuration,
            mapping_name="classical",
            comparison_case="classical_attempt",
            runtime_limit_seconds=branch_spec.runtime_limit_seconds,
            solver_result=solver_result,
            elapsed_seconds=elapsed_seconds,
            paired_run=False,
            success=success,
            failure_reason=failure_reason,
            dynamic=branch_spec.is_dynamic,
        )
        classical_records.append(record)
        run_records.append(record.to_dict())
        log_mapping_record(logger, record)
        if success:
            prepared_context.run_configuration.paired_source = True
            saved_success_contexts.append(prepared_context)
            if len(saved_success_contexts) >= branch_spec.required_successes:
                logger.log(f"  Classical reached required successes ({branch_spec.required_successes}).")
                break

    return classical_records, saved_success_contexts


def _run_cyclic_paired_phase(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState | None,
    saved_success_contexts: list[PreparedRunContext],
    logger: ExperimentLogger,
    run_records: list[dict[str, Any]],
) -> list[MappingRunRecord]:
    cyclic_records: list[MappingRunRecord] = []
    logger.log("  Replaying cyclic on saved successful classical run configurations.")
    for paired_index, prepared_context in enumerate(saved_success_contexts, start=1):
        logger.log(
            f"  Cyclic paired replay {paired_index}/{len(saved_success_contexts)} | "
            f"{prepared_context.run_configuration.run_config_id}"
        )
        success, solver_result, elapsed_seconds, failure_reason = _execute_mapping(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            prepared_context=prepared_context,
            mapping_name="cyclic",
            logger=logger,
        )
        record = build_mapping_record(
            run_configuration=prepared_context.run_configuration,
            mapping_name="cyclic",
            comparison_case="paired_replay",
            runtime_limit_seconds=branch_spec.runtime_limit_seconds,
            solver_result=solver_result,
            elapsed_seconds=elapsed_seconds,
            paired_run=True,
            success=success,
            failure_reason=failure_reason,
            dynamic=branch_spec.is_dynamic,
        )
        cyclic_records.append(record)
        run_records.append(record.to_dict())
        log_mapping_record(logger, record)
    return cyclic_records


def _run_cyclic_recovery_phase(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState | None,
    agent_number: int,
    agent_number_index: int,
    seed_base: int,
    logger: ExperimentLogger,
    run_configurations: list[dict[str, Any]],
    run_records: list[dict[str, Any]],
) -> list[MappingRunRecord]:
    cyclic_records: list[MappingRunRecord] = []
    cyclic_success_count = 0
    recovery_attempt_index = 0

    logger.log(
        "  Classical did not reach required successes. "
        "Classical receives a null condition-level data point; cyclic enters recovery mode."
    )

    while (
        cyclic_success_count < branch_spec.required_successes
        and recovery_attempt_index < MAX_CYCLIC_RECOVERY_ATTEMPTS
    ):
        run_index = branch_spec.max_classical_attempts + recovery_attempt_index
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
                f"  Cyclic recovery attempt {recovery_attempt_index + 1}/{MAX_CYCLIC_RECOVERY_ATTEMPTS} | "
                f"run_index={run_index} | setup_failed={type(exc).__name__}: {exc}"
            )
            _record_setup_failure(
                branch_spec=branch_spec,
                dynamic_state=dynamic_state,
                seed_base=seed_base,
                agent_number=agent_number,
                agent_number_index=agent_number_index,
                run_index=run_index,
                mapping_name="cyclic",
                comparison_case="cyclic_recovery",
                run_configurations=run_configurations,
                run_records=run_records,
                record_bucket=cyclic_records,
                logger=logger,
                exc=exc,
            )
            recovery_attempt_index += 1
            continue

        run_configurations.append(prepared_context.run_configuration.to_dict())
        logger.log(
            f"  Cyclic recovery attempt {recovery_attempt_index + 1}/{MAX_CYCLIC_RECOVERY_ATTEMPTS} | "
            f"{prepared_context.run_configuration.run_config_id}"
        )
        success, solver_result, elapsed_seconds, failure_reason = _execute_mapping(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            prepared_context=prepared_context,
            mapping_name="cyclic",
            logger=logger,
        )
        record = build_mapping_record(
            run_configuration=prepared_context.run_configuration,
            mapping_name="cyclic",
            comparison_case="cyclic_recovery",
            runtime_limit_seconds=branch_spec.runtime_limit_seconds,
            solver_result=solver_result,
            elapsed_seconds=elapsed_seconds,
            paired_run=False,
            success=success,
            failure_reason=failure_reason,
            dynamic=branch_spec.is_dynamic,
        )
        cyclic_records.append(record)
        run_records.append(record.to_dict())
        log_mapping_record(logger, record)
        if success:
            cyclic_success_count += 1
        recovery_attempt_index += 1

    if cyclic_success_count < branch_spec.required_successes:
        logger.log(
            f"  Cyclic recovery stopped at safeguard limit ({MAX_CYCLIC_RECOVERY_ATTEMPTS} attempts) "
            f"with {cyclic_success_count} successes."
        )
    return cyclic_records


def run_selected_experiment(map_type: str, *, seed_base: int = 1) -> dict[str, Any]:
    branch_spec = get_branch_spec(map_type)
    output_manager = BranchOutputManager(branch_spec)
    logger = ExperimentLogger(output_manager.logs_dir / "experiment.log")
    log_branch_header(logger, branch_spec)
    write_json(output_manager.metadata_dir / "branch_spec.json", branch_spec.to_dict())

    run_configurations: list[dict[str, Any]] = []
    run_records: list[dict[str, Any]] = []
    aggregates_payload: list[dict[str, Any]] = []

    dynamic_state: DynamicBranchState | None = None
    if branch_spec.is_dynamic:
        dynamic_state = prepare_dynamic_branch_state(branch_spec, seed_base=seed_base)
        log_dynamic_state(logger, branch_spec, dynamic_state)
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

        classical_records, saved_success_contexts = _run_classical_phase(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            agent_number=agent_number,
            agent_number_index=agent_number_index,
            seed_base=seed_base,
            logger=logger,
            run_configurations=run_configurations,
            run_records=run_records,
        )
        classical_success = len(saved_success_contexts) >= branch_spec.required_successes

        if classical_success:
            cyclic_records = _run_cyclic_paired_phase(
                branch_spec=branch_spec,
                dynamic_state=dynamic_state,
                saved_success_contexts=saved_success_contexts,
                logger=logger,
                run_records=run_records,
            )
        else:
            cyclic_records = _run_cyclic_recovery_phase(
                branch_spec=branch_spec,
                dynamic_state=dynamic_state,
                agent_number=agent_number,
                agent_number_index=agent_number_index,
                seed_base=seed_base,
                logger=logger,
                run_configurations=run_configurations,
                run_records=run_records,
            )

        aggregate = build_condition_aggregate(
            branch_spec=branch_spec,
            agent_number=agent_number,
            agent_number_index=agent_number_index,
            classical_records=classical_records,
            cyclic_records=cyclic_records,
        )
        aggregates_payload.append(aggregate.to_dict())
        print_aggregate_block(logger, aggregate)

    write_json(output_manager.records_dir / "run_configurations.json", run_configurations)
    write_json(output_manager.records_dir / "run_records.json", run_records)
    write_json(output_manager.aggregates_dir / "condition_summary.json", aggregates_payload)
    write_csv(output_manager.records_dir / "run_configurations.csv", run_configurations)
    write_csv(output_manager.records_dir / "run_records.csv", run_records)
    write_csv(output_manager.aggregates_dir / "condition_summary.csv", aggregates_payload)

    aggregate_objects = [ConditionAggregate(**payload) for payload in aggregates_payload]
    graph_paths = generate_graphs(branch_spec, aggregate_objects, output_manager.graphs_dir)

    logger.log("")
    logger.log("Final aggregate table:")
    for aggregate in aggregate_objects:
        print_aggregate_block(logger, aggregate)

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
        "graph_paths": [str(path) for path in graph_paths],
        "log_path": str(output_manager.logs_dir / "experiment.log"),
    }
