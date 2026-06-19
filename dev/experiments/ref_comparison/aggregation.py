from __future__ import annotations

from statistics import mean
from typing import Callable, TypeVar

from dev.experiments.ref_comparison.models import RefCaseSpec, RefConditionAggregate, RefMappingRunRecord

T = TypeVar("T", int, float)


def _records_for_mapping(records: list[RefMappingRunRecord], mapping_name: str) -> list[RefMappingRunRecord]:
    return [record for record in records if record.mapping_name == mapping_name]


def _count(records: list[RefMappingRunRecord], result_category: str) -> int:
    return sum(record.result_category == result_category for record in records)


def _average(records: list[RefMappingRunRecord], getter: Callable[[RefMappingRunRecord], T | None], *, solved_only: bool = False) -> float | None:
    values: list[float] = []
    for record in records:
        if solved_only and not record.solved_run:
            continue
        value = getter(record)
        if value is None:
            continue
        values.append(float(value))
    if not values:
        return None
    return mean(values)


def build_reference_aggregate(
    *,
    case_spec: RefCaseSpec,
    classical_records: list[RefMappingRunRecord],
    cyclic_records: list[RefMappingRunRecord],
) -> RefConditionAggregate:
    return RefConditionAggregate(
        case_id=case_spec.case_id,
        experiment_mode=case_spec.experiment_mode,
        size_label=case_spec.size_label,
        map_size=case_spec.map_size,
        agent_number=case_spec.agent_number,
        counted_runs_required=case_spec.counted_runs_required,
        paired_run_configurations=min(len(classical_records), len(cyclic_records)),
        num_classical_counted_runs=sum(record.counted_run for record in classical_records),
        num_classical_successful_runs=_count(classical_records, "successful"),
        num_classical_unfinished_runs=_count(classical_records, "unfinished"),
        num_classical_unsolvable_runs=_count(classical_records, "unsolvable"),
        num_cyclic_counted_runs=sum(record.counted_run for record in cyclic_records),
        num_cyclic_successful_runs=_count(cyclic_records, "successful"),
        num_cyclic_unfinished_runs=_count(cyclic_records, "unfinished"),
        num_cyclic_unsolvable_runs=_count(cyclic_records, "unsolvable"),
        classical_avg_time_computation_halted=_average(
            classical_records,
            lambda record: record.time_computation_halted_seconds,
        ),
        cyclic_avg_time_computation_halted=_average(
            cyclic_records,
            lambda record: record.time_computation_halted_seconds,
        ),
        classical_avg_conflicts_at_halt=_average(
            classical_records,
            lambda record: record.num_conflicts_detected_at_halt,
        ),
        cyclic_avg_conflicts_at_halt=_average(
            cyclic_records,
            lambda record: record.num_conflicts_detected_at_halt,
        ),
        classical_avg_total_path_length=_average(
            classical_records,
            lambda record: record.total_path_length,
            solved_only=True,
        ),
        cyclic_avg_total_path_length=_average(
            cyclic_records,
            lambda record: record.total_path_length,
            solved_only=True,
        ),
        classical_avg_total_turns=_average(
            classical_records,
            lambda record: record.total_turns,
            solved_only=True,
        ),
        cyclic_avg_total_turns=_average(
            cyclic_records,
            lambda record: record.total_turns,
            solved_only=True,
        ),
        notes=(
            "Single-agent reference case: cyclic-faster filtering is disabled."
            if case_spec.experiment_mode == "single_agent"
            else "Multi-agent reference case: retained pairs use the individual cyclic-faster temporary filter."
        ),
    )
