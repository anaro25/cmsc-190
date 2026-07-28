from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RefCaseSpec:
    case_id: str
    experiment_mode: str
    display_name: str
    size_label: str
    map_size: int
    image_path: str
    map_image_paths: list[str]
    agent_number: int
    counted_runs_required: int
    capacity_search_enabled: bool
    capacity_agent_upper_bound: int
    capacity_binary_search_max_downward_moves: int
    capacity_attempts_per_agent_number: int
    capacity_pass_criterion: str
    runtime_limit_seconds: float
    use_ecbs: bool
    ecbs_suboptimality: float
    true_static_shortest_path_distance: bool
    tight_time_horizon: bool
    remove_extra_transitions: bool
    add_transitions_between_free_spaces: bool
    agent_cohesion_enabled: bool
    cohesion_factor: float
    filter_individual_runs_until_cyclic_faster: bool
    filter_individual_runs_until_cyclic_faster_max_attempts: int | None
    single_agent_timing_repetitions: int = 1
    multi_agent_timing_repetitions: int = 1
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RefRunConfiguration:
    case_id: str
    experiment_mode: str
    size_label: str
    map_size: int
    agent_number: int
    run_index: int
    run_config_id: str
    map_identifier: str
    paired_source: bool
    agents: list[dict[str, Any]]
    map_index: int | None = None
    map_number: int | None = None
    map_label: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RefMappingRunRecord:
    case_id: str
    experiment_mode: str
    size_label: str
    map_size: int
    agent_number: int
    run_index: int
    run_config_id: str
    mapping_name: str
    mapping_index: int
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
    total_path_length: int | None
    total_turns: int | None
    num_high_level_nodes_expanded: int | None
    runtime_limit_seconds: float
    map_identifier: str
    initial_condition_spec: list[dict[str, Any]]
    map_index: int | None = None
    map_number: int | None = None
    map_label: str = ""
    notes: str = ""
    timing_repetitions: int = 1
    timing_elapsed_samples_seconds: list[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RefConditionAggregate:
    case_id: str
    experiment_mode: str
    size_label: str
    map_size: int
    agent_number: int
    counted_runs_required: int
    paired_run_configurations: int
    num_classical_counted_runs: int
    num_classical_successful_runs: int
    num_classical_unfinished_runs: int
    num_classical_unsolvable_runs: int
    num_cyclic_counted_runs: int
    num_cyclic_successful_runs: int
    num_cyclic_unfinished_runs: int
    num_cyclic_unsolvable_runs: int
    classical_avg_time_computation_halted: float | None
    cyclic_avg_time_computation_halted: float | None
    classical_avg_conflicts_at_halt: float | None
    cyclic_avg_conflicts_at_halt: float | None
    classical_avg_total_path_length: float | None
    cyclic_avg_total_path_length: float | None
    classical_avg_total_turns: float | None
    cyclic_avg_total_turns: float | None
    classical_avg_search_nodes_expanded: float | None = None
    cyclic_avg_search_nodes_expanded: float | None = None
    map_index: int | None = None
    map_number: int | None = None
    map_label: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RefVisualizationCandidate:
    case_spec: RefCaseSpec
    run_configuration: RefRunConfiguration
    mapping_name: str
    agents: list[dict[str, Any]]
    solver_result: dict[str, Any]
    composite_map: list[list[Any]]
    visually_free_vertex_positions: set[tuple[int, int]] | None = None


@dataclass
class RefComputationPayload:
    case_spec: RefCaseSpec
    run_configurations: list[dict[str, Any]] = field(default_factory=list)
    run_records: list[dict[str, Any]] = field(default_factory=list)
    aggregate: dict[str, Any] | None = None
    map_aggregates: list[dict[str, Any]] = field(default_factory=list)
    capacity_searches: list[dict[str, Any]] = field(default_factory=list)
    discarded_attempts: list[dict[str, Any]] = field(default_factory=list)
    visualization_candidates: list[RefVisualizationCandidate] = field(default_factory=list)
    stop_summary: dict[str, Any] = field(default_factory=dict)
