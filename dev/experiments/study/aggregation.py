from __future__ import annotations

from dev.experiments.branch_specs import BranchSpec
from dev.experiments.study.models import ConditionAggregate, MappingRunRecord


def aggregate_mapping(records: list[MappingRunRecord]) -> tuple[float | None, float | None, float | None]:
    successful = [record for record in records if record.success]
    if not successful:
        return None, None, None

    avg_runtime = sum(record.computation_time_seconds for record in successful) / len(successful)
    avg_conflicts = sum((record.num_conflicts_detected or 0) for record in successful) / len(successful)
    path_values = [record.average_path_length for record in successful if record.average_path_length is not None]
    avg_path = sum(path_values) / len(path_values) if path_values else None
    return avg_runtime, avg_conflicts, avg_path


def build_condition_aggregate(
    *,
    branch_spec: BranchSpec,
    agent_number: int,
    agent_number_index: int,
    classical_records: list[MappingRunRecord],
    cyclic_records: list[MappingRunRecord],
) -> ConditionAggregate:
    classical_successes = [record for record in classical_records if record.success]
    cyclic_successes = [record for record in cyclic_records if record.success]
    classical_condition_success = len(classical_successes) >= branch_spec.required_successes
    cyclic_condition_success = len(cyclic_successes) >= branch_spec.required_successes
    paired_comparison = classical_condition_success and all(record.paired_run for record in cyclic_records)
    cyclic_recovery_non_paired = (not classical_condition_success) and bool(cyclic_records)

    classical_avg_runtime, classical_avg_conflicts, classical_avg_path = aggregate_mapping(classical_records)
    cyclic_avg_runtime, cyclic_avg_conflicts, cyclic_avg_path = aggregate_mapping(cyclic_records)

    if paired_comparison:
        notes = "paired_comparison"
    elif cyclic_recovery_non_paired:
        notes = "cyclic_recovery_non_paired"
    else:
        notes = "classical_null_without_cyclic_data"

    return ConditionAggregate(
        branch_id=branch_spec.branch_id,
        branch_decimal=branch_spec.branch_decimal,
        map_type=branch_spec.map_type,
        map_obstacle_type=branch_spec.map_obstacle_type,
        target_type=branch_spec.target_type_active,
        agent_number=agent_number,
        agent_number_index=agent_number_index,
        condition_id=f"agent_number[{branch_spec.branch_decimal}.{agent_number_index}]",
        required_successes=branch_spec.required_successes,
        max_classical_attempts=branch_spec.max_classical_attempts,
        classical_condition_success=classical_condition_success,
        classical_null_data_point=not classical_condition_success,
        cyclic_condition_success=cyclic_condition_success,
        paired_comparison=paired_comparison,
        cyclic_recovery_non_paired=cyclic_recovery_non_paired,
        num_classical_attempts=len(classical_records),
        num_classical_successes=len(classical_successes),
        num_cyclic_attempts=len(cyclic_records),
        num_cyclic_successes=len(cyclic_successes),
        classical_avg_computation_time=classical_avg_runtime,
        classical_avg_conflicts=classical_avg_conflicts,
        classical_avg_path_length=classical_avg_path,
        cyclic_avg_computation_time=cyclic_avg_runtime,
        cyclic_avg_conflicts=cyclic_avg_conflicts,
        cyclic_avg_path_length=cyclic_avg_path,
        notes=notes,
    )
