from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
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
    solver_name: str
    enhanced_cbs_enabled: bool
    solver_suboptimality_factor: float | None
    paired_run: bool
    solver_status: str
    result_category: str
    counted_run: bool
    solved_run: bool
    time_computation_halted_seconds: float
    num_conflicts_detected_at_halt: int | None
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
    counted_runs_required: int
    paired_run_configurations: int
    classical_reached_counted_quota: bool
    cyclic_replayed_all_paired_configs: bool
    num_classical_attempts: int
    num_classical_counted_runs: int
    num_classical_successful_runs: int
    num_classical_unfinished_runs: int
    num_classical_unsolvable_runs: int
    num_classical_setup_failed_runs: int
    num_cyclic_attempts: int
    num_cyclic_counted_runs: int
    num_cyclic_successful_runs: int
    num_cyclic_unfinished_runs: int
    num_cyclic_unsolvable_runs: int
    num_cyclic_setup_failed_runs: int
    classical_avg_time_computation_halted: float | None
    classical_avg_conflicts_at_halt: float | None
    classical_avg_path_length: float | None
    cyclic_avg_time_computation_halted: float | None
    cyclic_avg_conflicts_at_halt: float | None
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
    allowed_spawn_vertices: set[tuple[int, int]] | None = None
    zone_vertices_by_id: dict[int, set[tuple[int, int]]] = field(default_factory=dict)
    single_target_vertices_by_id: dict[int, set[tuple[int, int]]] = field(default_factory=dict)
    visually_free_vertices: set[tuple[int, int]] = field(default_factory=set)


@dataclass
class VisualizationCandidate:
    mapping_name: str
    run_configuration: RunConfiguration
    agents: list[dict[str, Any]]
    solver_result: dict[str, Any]
    composite_map: list[list[Any]] | None = None


@dataclass
class SamplingConditionResult:
    accepted_for_reporting: bool
    stop_branch: bool
    stop_reason: str | None = None
    stop_message: str = ""
    classical_records: list[MappingRunRecord] = field(default_factory=list)
    cyclic_records: list[MappingRunRecord] = field(default_factory=list)
    run_configurations: list[dict[str, Any]] = field(default_factory=list)
    run_records: list[dict[str, Any]] = field(default_factory=list)
    visualization_candidates: list[VisualizationCandidate] = field(default_factory=list)
    retained_pairs: int = 0
    total_paired_sampling_attempts: int = 0
    consecutive_failed_paired_sampling_attempts: int = 0
