from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RunConfiguration:
    branch_id: str
    branch_decimal: str
    map_type: str
    map_obstacle_type: str
    target_type: str
    agent_number: int
    agent_number_index: int
    run_index: int
    run_config_id: str
    map_identifier: str
    map_seed: int
    assignment_seed: int
    dynamic_schedule_seed: int | None
    paired_source: bool
    starts_and_goals: list[dict[str, Any]]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MappingRunRecord:
    branch_id: str
    branch_decimal: str
    map_type: str
    map_obstacle_type: str
    target_type: str
    agent_number: int
    agent_number_index: int
    run_index: int
    run_config_id: str
    mapping_name: str
    mapping_index: int
    mapping_record_id: str
    comparison_case: str
    paired_run: bool
    success: bool
    status: str
    failure_reason: str | None
    computation_time_seconds: float
    num_conflicts_detected: int | None
    average_path_length: float | None
    num_high_level_nodes_expanded: int | None
    runtime_limit_seconds: float
    map_identifier: str
    map_seed: int
    assignment_seed: int
    dynamic_schedule_seed: int | None
    initial_condition_spec: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["initial_condition_spec"] = json.dumps(
            payload["initial_condition_spec"], ensure_ascii=False
        )
        return payload


@dataclass
class ConditionAggregate:
    branch_id: str
    branch_decimal: str
    map_type: str
    map_obstacle_type: str
    target_type: str
    agent_number: int
    agent_number_index: int
    condition_id: str
    required_successes: int
    max_classical_attempts: int
    classical_condition_success: bool
    classical_null_data_point: bool
    cyclic_condition_success: bool
    paired_comparison: bool
    cyclic_recovery_non_paired: bool
    num_classical_attempts: int
    num_classical_successes: int
    num_cyclic_attempts: int
    num_cyclic_successes: int
    classical_avg_computation_time: float | None
    classical_avg_conflicts: float | None
    classical_avg_path_length: float | None
    cyclic_avg_computation_time: float | None
    cyclic_avg_conflicts: float | None
    cyclic_avg_path_length: float | None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PreparedRunContext:
    run_configuration: RunConfiguration
    agents: list[dict[str, Any]]
    base_map: list[list[Any]] | None = None
    classical_map: list[list[Any]] | None = None
    cyclic_map: list[list[Any]] | None = None


@dataclass
class DynamicBranchState:
    raw_obstacle_matrix: list[list[int]]
    static_matrix: list[list[int]]
    dynamic_loop_frames: list[list[list[int]]]
    classical_loop: list[list[list[Any]]]
    cyclic_loop: list[list[list[Any]]]
    assignment_map: list[list[Any]]
    map_identifier: str
    schedule_seed: int
    generation_mode: str
