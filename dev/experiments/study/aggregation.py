from __future__ import annotations

from collections import Counter

from dev.experiments.branch_specs import BranchSpec
from dev.experiments.study.models import ConditionAggregate, MappingRunRecord


COUNTED_CATEGORIES = {"successful", "unfinished"}


def aggregate_mapping(records: list[MappingRunRecord]) -> tuple[float | None, float | None, float | None]:
    counted_records = [record for record in records if record.counted_run]
    if not counted_records:
        return None, None, None

    avg_halted_time = (
        sum(record.time_computation_halted_seconds for record in counted_records) / len(counted_records)
    )
    avg_conflicts = (
        sum((record.num_conflicts_detected_at_halt or 0) for record in counted_records)
        / len(counted_records)
    )
    path_values = [record.average_path_length for record in records if record.solved_run and record.average_path_length is not None]
    avg_path = sum(path_values) / len(path_values) if path_values else None
    return avg_halted_time, avg_conflicts, avg_path


def summarize_categories(records: list[MappingRunRecord]) -> Counter:
    return Counter(record.result_category for record in records)


def build_condition_aggregate(
    *,
    branch_spec: BranchSpec,
    agent_number: int,
    agent_number_index: int,
    classical_records: list[MappingRunRecord],
    cyclic_records: list[MappingRunRecord],
    paired_run_configurations: int,
) -> ConditionAggregate:
    classical_summary = summarize_categories(classical_records)
    cyclic_summary = summarize_categories(cyclic_records)

    classical_counted_runs = sum(classical_summary.get(category, 0) for category in COUNTED_CATEGORIES)
    cyclic_counted_runs = sum(cyclic_summary.get(category, 0) for category in COUNTED_CATEGORIES)

    classical_avg_time, classical_avg_conflicts, classical_avg_path = aggregate_mapping(classical_records)
    cyclic_avg_time, cyclic_avg_conflicts, cyclic_avg_path = aggregate_mapping(cyclic_records)

    classical_reached_counted_quota = classical_counted_runs >= branch_spec.counted_runs_required
    cyclic_replayed_all_paired_configs = len(cyclic_records) == paired_run_configurations

    if classical_reached_counted_quota and cyclic_replayed_all_paired_configs:
        notes = "paired_counted_replay"
    elif not classical_reached_counted_quota:
        notes = "classical_counted_quota_not_reached_before_safeguard"
    else:
        notes = "cyclic_replay_incomplete"

    return ConditionAggregate(
        branch_id=branch_spec.branch_id,
        branch_decimal=branch_spec.branch_decimal,
        map_type=branch_spec.map_type,
        map_obstacle_type=branch_spec.map_obstacle_type,
        target_type=branch_spec.target_type_active,
        agent_number=agent_number,
        agent_number_index=agent_number_index,
        condition_id=f"agent_number[{branch_spec.branch_decimal}.{agent_number_index}]",
        counted_runs_required=branch_spec.counted_runs_required,
        paired_run_configurations=paired_run_configurations,
        classical_reached_counted_quota=classical_reached_counted_quota,
        cyclic_replayed_all_paired_configs=cyclic_replayed_all_paired_configs,
        num_classical_attempts=len(classical_records),
        num_classical_counted_runs=classical_counted_runs,
        num_classical_successful_runs=classical_summary.get("successful", 0),
        num_classical_unfinished_runs=classical_summary.get("unfinished", 0),
        num_classical_unsolvable_runs=classical_summary.get("unsolvable", 0),
        num_classical_setup_failed_runs=classical_summary.get("setup_failed", 0),
        num_cyclic_attempts=len(cyclic_records),
        num_cyclic_counted_runs=cyclic_counted_runs,
        num_cyclic_successful_runs=cyclic_summary.get("successful", 0),
        num_cyclic_unfinished_runs=cyclic_summary.get("unfinished", 0),
        num_cyclic_unsolvable_runs=cyclic_summary.get("unsolvable", 0),
        num_cyclic_setup_failed_runs=cyclic_summary.get("setup_failed", 0),
        classical_avg_time_computation_halted=classical_avg_time,
        classical_avg_conflicts_at_halt=classical_avg_conflicts,
        classical_avg_path_length=classical_avg_path,
        cyclic_avg_time_computation_halted=cyclic_avg_time,
        cyclic_avg_conflicts_at_halt=cyclic_avg_conflicts,
        cyclic_avg_path_length=cyclic_avg_path,
        notes=notes,
    )
