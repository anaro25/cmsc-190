from __future__ import annotations

from statistics import mean
from typing import Callable, TypeVar

from dev.experiments.ref_comparison.models import RefCaseSpec, RefConditionAggregate, RefMappingRunRecord

T = TypeVar("T", int, float)


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


def _aggregate_agent_number(case_spec: RefCaseSpec, records: list[RefMappingRunRecord]) -> int:
    agent_numbers = {int(record.agent_number) for record in records}
    if len(agent_numbers) == 1:
        return next(iter(agent_numbers))
    return int(case_spec.agent_number)


def build_reference_aggregate(
    *,
    case_spec: RefCaseSpec,
    classical_records: list[RefMappingRunRecord],
    cyclic_records: list[RefMappingRunRecord],
    map_index: int | None = None,
    map_number: int | None = None,
    map_label: str = "",
) -> RefConditionAggregate:
    return RefConditionAggregate(
        case_id=case_spec.case_id,
        experiment_mode=case_spec.experiment_mode,
        size_label=case_spec.size_label,
        map_size=case_spec.map_size,
        agent_number=_aggregate_agent_number(case_spec, classical_records + cyclic_records),
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
        classical_avg_time_computation_halted=_average(classical_records, lambda r: r.time_computation_halted_seconds),
        cyclic_avg_time_computation_halted=_average(cyclic_records, lambda r: r.time_computation_halted_seconds),
        classical_avg_conflicts_at_halt=_average(classical_records, lambda r: r.num_conflicts_detected_at_halt),
        cyclic_avg_conflicts_at_halt=_average(cyclic_records, lambda r: r.num_conflicts_detected_at_halt),
        classical_avg_total_path_length=_average(classical_records, lambda r: r.total_path_length, solved_only=True),
        cyclic_avg_total_path_length=_average(cyclic_records, lambda r: r.total_path_length, solved_only=True),
        classical_avg_total_turns=_average(classical_records, lambda r: r.total_turns, solved_only=True),
        cyclic_avg_total_turns=_average(cyclic_records, lambda r: r.total_turns, solved_only=True),
        classical_avg_search_nodes_expanded=_average(classical_records, lambda r: r.num_high_level_nodes_expanded, solved_only=False),
        cyclic_avg_search_nodes_expanded=_average(cyclic_records, lambda r: r.num_high_level_nodes_expanded, solved_only=False),
        map_index=map_index,
        map_number=map_number,
        map_label=map_label,
        notes=(
            f"Single-agent reference case: cyclic-faster filtering is disabled; runtime values use {int(case_spec.single_agent_timing_repetitions)} repeated timing samples per map."
            if case_spec.experiment_mode == "single_agent"
            else f"Multi-agent reference case: cyclic-faster filtering is disabled; three reference port maps are evaluated with map-specific agent counts; runtime values use {int(case_spec.multi_agent_timing_repetitions)} repeated timing samples per map."
        ),
    )
