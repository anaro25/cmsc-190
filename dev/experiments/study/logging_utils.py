from __future__ import annotations

from dev.experiments.branch_specs import BranchSpec
from dev.experiments.study.constants import CONSECUTIVE_FAILED_PAIRED_SAMPLING_STOP_LIMIT
from dev.experiments.study.io_utils import ExperimentLogger
from dev.experiments.study.models import ConditionAggregate, DynamicBranchState, MappingRunRecord


def mapping_label(mapping_name: str) -> str:
    return "Classical" if mapping_name == "classical" else "Cyclic"


def format_metric(value: float | int | None) -> str:
    if value is None:
        return "null"
    return f"{float(value):.2f}"


def log_branch_header(logger: ExperimentLogger, branch_spec: BranchSpec) -> None:
    logger.log("=" * 88)
    logger.log(f"Branch: {branch_spec.display_name} ({branch_spec.map_type})")
    logger.log(f"Map obstacle type: {branch_spec.map_obstacle_type}")
    logger.log(f"Documented target type: {branch_spec.target_type_documented}")
    logger.log(f"Active target type: {branch_spec.target_type_active}")
    if branch_spec.is_dynamic and branch_spec.map_type.startswith("dynamic_campus_area"):
        logger.log(f"Campus single_cell_target mode: {branch_spec.single_cell_target}")
    logger.log(f"Seed: {branch_spec.seed_base}")
    logger.log(f"Jointly viable counted pairs required (n): {branch_spec.counted_runs_required}")
    logger.log(f"Runtime limit per run: {branch_spec.runtime_limit_seconds:.2f}s")
    start_agent_number, max_agent_number, step_size = branch_spec.agent_number_range
    logger.log(
        "Agent number range: "
        f"start={start_agent_number}, end={max_agent_number}, step={step_size}"
    )
    logger.log(f"Planned agent numbers before early stopping: {branch_spec.agent_numbers}")
    logger.log(
        "Early-stop rule 1: discard the current condition and stop when cyclic unfinished runs "
        "exceed cyclic successful runs within the retained counted pairs."
    )
    logger.log(
        "Early-stop rule 2: discard the current condition and stop after "
        f"{CONSECUTIVE_FAILED_PAIRED_SAMPLING_STOP_LIMIT} consecutive failed paired sampling attempts."
    )
    if branch_spec.notes:
        logger.log(f"Notes: {branch_spec.notes}")
    logger.log("=" * 88)


def log_dynamic_state(
    logger: ExperimentLogger,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState,
) -> None:
    rows = len(dynamic_state.static_matrix)
    cols = len(dynamic_state.static_matrix[0]) if rows else 0
    total_cells = max(1, rows * cols)
    raw_static_count = sum(cell == 1 for row in dynamic_state.raw_obstacle_matrix for cell in row)
    static_count = sum(cell == 1 for row in dynamic_state.static_matrix for cell in row)
    dynamic_count = (
        sum(cell == 2 for row in dynamic_state.dynamic_loop_frames[0] for cell in row)
        if dynamic_state.dynamic_loop_frames
        else 0
    )

    logger.log("Shared dynamic map prepared:")
    logger.log(f"  Image path: {branch_spec.image_path}")
    if branch_spec.image_resize_longest_side is not None:
        logger.log(f"  Resized longest side: {branch_spec.image_resize_longest_side}")
    logger.log(f"  Dimensions: {rows}x{cols}")
    logger.log(f"  Raw static density: {raw_static_count / total_cells:.2f}")
    if branch_spec.dynamic_target_static_obstacle_density is None:
        logger.log("  Target static density: preserved from source image")
    else:
        logger.log(f"  Target static density: {branch_spec.dynamic_target_static_obstacle_density:.2f}")
    logger.log(
        f"  Dynamic density target: {(branch_spec.dynamic_target_dynamic_obstacle_density or 0.0):.2f}"
    )
    logger.log(f"  Static obstacle cells per frame: {static_count}")
    logger.log(f"  Dynamic obstacle cells per frame: {dynamic_count}")
    logger.log(f"  Loop length: {len(dynamic_state.dynamic_loop_frames)}")
    logger.log(f"  Shared schedule seed: {dynamic_state.schedule_seed}")
    logger.log(f"  Dynamic generation mode: {dynamic_state.generation_mode}")
    logger.log(f"  Dynamic generation cell mode: {branch_spec.dynamic_generation_cell_mode}")
    logger.log(f"  Spawnable cell mode: {branch_spec.spawnable_cell_mode}")
    if dynamic_state.allowed_spawn_vertices is not None:
        logger.log(f"  Allowed spawn vertices on assignment map: {len(dynamic_state.allowed_spawn_vertices)}")
    if dynamic_state.zone_vertices_by_id:
        zone_counts = {zone_id: len(vertices) for zone_id, vertices in sorted(dynamic_state.zone_vertices_by_id.items())}
        logger.log(f"  Campus zone vertices on assignment map: {zone_counts}")


def log_mapping_record(logger: ExperimentLogger, record: MappingRunRecord) -> None:
    logger.log(
        "      "
        f"{mapping_label(record.mapping_name)} | {record.mapping_record_id} | "
        f"result={record.result_category} | solver_status={record.solver_status} | "
        f"counted={record.counted_run} | time_halted={record.time_computation_halted_seconds:.2f}s | "
        f"conflicts_at_halt={format_metric(record.num_conflicts_detected_at_halt)} | "
        f"avg_path={format_metric(record.average_path_length)} | "
        f"paired={record.paired_run}"
    )


def print_aggregate_block(logger: ExperimentLogger, aggregate: ConditionAggregate) -> None:
    logger.log(
        "    Condition aggregate | "
        f"{aggregate.condition_id} | agent_number={aggregate.agent_number} | "
        f"retained_pairs={aggregate.paired_run_configurations}/{aggregate.counted_runs_required}"
    )
    logger.log(
        "      Classical | "
        f"successful={aggregate.num_classical_successful_runs} | "
        f"unfinished={aggregate.num_classical_unfinished_runs} | "
        f"avg_time_halted={format_metric(aggregate.classical_avg_time_computation_halted)} | "
        f"avg_conflicts_at_halt={format_metric(aggregate.classical_avg_conflicts_at_halt)} | "
        f"avg_path={format_metric(aggregate.classical_avg_path_length)}"
    )
    logger.log(
        "      Cyclic | "
        f"successful={aggregate.num_cyclic_successful_runs} | "
        f"unfinished={aggregate.num_cyclic_unfinished_runs} | "
        f"avg_time_halted={format_metric(aggregate.cyclic_avg_time_computation_halted)} | "
        f"avg_conflicts_at_halt={format_metric(aggregate.cyclic_avg_conflicts_at_halt)} | "
        f"avg_path={format_metric(aggregate.cyclic_avg_path_length)}"
    )
