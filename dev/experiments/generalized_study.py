from __future__ import annotations

import csv
import json
import math
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import matplotlib.pyplot as plt

from dev.experiments.branch_specs import BranchSpec, get_branch_spec
from dev.experiments.dynamic_port.dynamic_loop import build_dynamic_loop
from dev.experiments.dynamic_port.pipeline import (
    build_mapped_loop,
    get_shared_assignment_map,
    matrix_to_obstacle_frame,
)
from dev.experiments.dynamic_port.preprocessing import preprocess_static_obstacle_density
from dev.inputs.dynamic_port.loader import load_port_obstacle_matrix
from dev.mapf.agent_assignment import sample_agent_start_goal_pairs
from dev.mapf.cbs_solver import compute_solution_cost as compute_static_solution_cost
from dev.mapf.cbs_solver import solve_mapf_with_cbs
from dev.mapf.time_expanded_cbs import compute_solution_cost as compute_dynamic_solution_cost
from dev.mapf.time_expanded_cbs import solve_time_expanded_mapf_with_cbs
from dev.maps.base_map_factory import create_base_map
from dev.maps.classical_mapper import apply_classical_mapping
from dev.maps.cyclic_mapper import apply_cyclic_mapping
from dev.paths import OUTPUTS_ROOT


DEFAULT_PROGRESS_REPORT_SECONDS = 5
MAX_CYCLIC_RECOVERY_ATTEMPTS = 30


def _fallback_build_dynamic_loop(base_matrix: list[list[int]], dynamic_density: float, loop_length: int, seed: int) -> list[list[list[int]]]:
    import random

    from dev.experiments.dynamic_port.dynamic_loop import apply_dynamic_cells, frame_is_valid

    rows = len(base_matrix)
    cols = len(base_matrix[0]) if rows else 0
    total_cells = rows * cols
    target_dynamic_cells = max(0, int(round(dynamic_density * total_cells)))
    free_cells = [(r, c) for r in range(rows) for c in range(cols) if base_matrix[r][c] == 0]
    if target_dynamic_cells <= 0 or not free_cells:
        return [[row[:] for row in base_matrix] for _ in range(max(1, loop_length))]

    frames: list[list[list[int]]] = []
    for time_step in range(max(1, loop_length)):
        rng = random.Random(seed + 1000 + time_step)
        candidates = free_cells[:]
        rng.shuffle(candidates)
        chosen: set[tuple[int, int]] = set()
        for cell in candidates:
            if len(chosen) >= target_dynamic_cells:
                break
            proposal = chosen | {cell}
            if frame_is_valid(base_matrix, proposal):
                chosen = proposal
        if len(chosen) == 0 and target_dynamic_cells > 0:
            chosen = set(candidates[: min(target_dynamic_cells, len(candidates))])
        frames.append(apply_dynamic_cells(base_matrix, chosen))
    return frames


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


class ExperimentLogger:
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text("", encoding="utf-8")

    def log(self, message: str = "") -> None:
        print(message)
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")


class BranchOutputManager:
    def __init__(self, branch_spec: BranchSpec):
        self.branch_root = OUTPUTS_ROOT / branch_spec.map_type
        if self.branch_root.exists():
            shutil.rmtree(self.branch_root)
        self.branch_root.mkdir(parents=True, exist_ok=True)
        self.metadata_dir = self.branch_root / "metadata"
        self.records_dir = self.branch_root / "records"
        self.aggregates_dir = self.branch_root / "aggregates"
        self.graphs_dir = self.branch_root / "graphs"
        self.logs_dir = self.branch_root / "logs"
        for directory in [
            self.metadata_dir,
            self.records_dir,
            self.aggregates_dir,
            self.graphs_dir,
            self.logs_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


def _build_progress_callback(logger: ExperimentLogger, label: str) -> Callable[[int], None]:
    def callback(elapsed_seconds: int) -> None:
        if elapsed_seconds <= 0:
            logger.log(f"    {label} progress: 0s")
        else:
            logger.log(f"    {label} progress: {elapsed_seconds}s")

    return callback


def _compute_average_path_length(paths_by_agent: dict[int, list[tuple[int, int]]], *, dynamic: bool) -> float:
    if not paths_by_agent:
        return 0.0
    total_cost = (
        compute_dynamic_solution_cost(paths_by_agent)
        if dynamic
        else compute_static_solution_cost(paths_by_agent)
    )
    return total_cost / len(paths_by_agent)


def _to_float_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _clean_csv_value(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return ""
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _clean_csv_value(value) for key, value in row.items()})


def _mapping_label(mapping_name: str) -> str:
    return "Classical" if mapping_name == "classical" else "Cyclic"


def _status_label(record: MappingRunRecord) -> str:
    if record.success:
        return "success"
    return record.failure_reason or record.status


def _seed_for(*parts: Any) -> int:
    text = "|".join(str(part) for part in parts)
    total = 0
    for index, character in enumerate(text, start=1):
        total = (total + index * ord(character)) % (2**31 - 1)
    return total or 1


def _build_mapping_record(
    *,
    run_configuration: RunConfiguration,
    mapping_name: str,
    comparison_case: str,
    runtime_limit_seconds: float,
    solver_result: dict[str, Any] | None,
    elapsed_seconds: float,
    paired_run: bool,
    success: bool,
    failure_reason: str | None,
    dynamic: bool,
) -> MappingRunRecord:
    average_path_length = None
    num_conflicts_detected = None
    num_high_level_nodes_expanded = None
    status = failure_reason or "unknown_failure"

    if solver_result is not None:
        status = solver_result.get("status", status)
        num_conflicts_detected = solver_result.get("num_conflicts_detected")
        num_high_level_nodes_expanded = solver_result.get("num_high_level_nodes_expanded")
        if solver_result.get("paths_by_agent"):
            average_path_length = _compute_average_path_length(
                solver_result["paths_by_agent"],
                dynamic=dynamic,
            )

    mapping_index = 0 if mapping_name == "classical" else 1
    return MappingRunRecord(
        branch_id=run_configuration.branch_id,
        branch_decimal=run_configuration.branch_decimal,
        map_type=run_configuration.map_type,
        map_obstacle_type=run_configuration.map_obstacle_type,
        target_type=run_configuration.target_type,
        agent_number=run_configuration.agent_number,
        agent_number_index=run_configuration.agent_number_index,
        run_index=run_configuration.run_index,
        run_config_id=run_configuration.run_config_id,
        mapping_name=mapping_name,
        mapping_index=mapping_index,
        mapping_record_id=(
            f"mapping[{run_configuration.branch_decimal}."
            f"{run_configuration.agent_number_index}.{run_configuration.run_index}.{mapping_index}]"
        ),
        comparison_case=comparison_case,
        paired_run=paired_run,
        success=success,
        status=status,
        failure_reason=None if success else failure_reason,
        computation_time_seconds=elapsed_seconds,
        num_conflicts_detected=num_conflicts_detected,
        average_path_length=average_path_length,
        num_high_level_nodes_expanded=num_high_level_nodes_expanded,
        runtime_limit_seconds=runtime_limit_seconds,
        map_identifier=run_configuration.map_identifier,
        map_seed=run_configuration.map_seed,
        assignment_seed=run_configuration.assignment_seed,
        dynamic_schedule_seed=run_configuration.dynamic_schedule_seed,
        initial_condition_spec=run_configuration.starts_and_goals,
    )


def _run_static_mapping(
    *,
    composite_map: list[list[Any]],
    agents: list[dict[str, Any]],
    runtime_limit_seconds: float,
    logger: ExperimentLogger,
    label: str,
) -> tuple[bool, dict[str, Any] | None, float, str | None]:
    start = time.perf_counter()
    try:
        solver_result = solve_mapf_with_cbs(
            composite_map=composite_map,
            agents=agents,
            max_runtime_seconds=runtime_limit_seconds,
            progress_callback=_build_progress_callback(logger, label),
        )
        elapsed_seconds = time.perf_counter() - start
        if solver_result.get("status") == "solved":
            return True, solver_result, elapsed_seconds, None
        return False, solver_result, elapsed_seconds, solver_result.get("status")
    except Exception as exc:  # pragma: no cover - defensive logging path
        elapsed_seconds = time.perf_counter() - start
        return False, None, elapsed_seconds, f"exception:{type(exc).__name__}:{exc}"


def _run_dynamic_mapping(
    *,
    mapped_loop: list[list[list[Any]]],
    agents: list[dict[str, Any]],
    runtime_limit_seconds: float,
    logger: ExperimentLogger,
    label: str,
) -> tuple[bool, dict[str, Any] | None, float, str | None]:
    start = time.perf_counter()
    try:
        solver_result = solve_time_expanded_mapf_with_cbs(
            mapped_loop=mapped_loop,
            agents=agents,
            max_runtime_seconds=runtime_limit_seconds,
            progress_callback=_build_progress_callback(logger, label),
        )
        elapsed_seconds = time.perf_counter() - start
        if solver_result.get("status") == "solved":
            return True, solver_result, elapsed_seconds, None
        return False, solver_result, elapsed_seconds, solver_result.get("status")
    except Exception as exc:  # pragma: no cover - defensive logging path
        elapsed_seconds = time.perf_counter() - start
        return False, None, elapsed_seconds, f"exception:{type(exc).__name__}:{exc}"


def _prepare_static_run_context(
    *,
    branch_spec: BranchSpec,
    agent_number: int,
    agent_number_index: int,
    run_index: int,
    seed_base: int,
) -> PreparedRunContext:
    map_seed = _seed_for(branch_spec.map_type, seed_base, "map", agent_number, run_index)
    assignment_seed = _seed_for(branch_spec.map_type, seed_base, "assign", agent_number, run_index)
    base_map = create_base_map(
        base_rows=branch_spec.base_rows or 25,
        base_cols=branch_spec.base_cols or 25,
        obstacle_ratio=branch_spec.static_obstacle_density or 0.40,
        rng=__import__("random").Random(map_seed),
    )
    classical_map = apply_classical_mapping({"map": base_map})["map"]
    cyclic_map = apply_cyclic_mapping({"map": base_map})["map"]
    agents = sample_agent_start_goal_pairs(
        composite_map=base_map,
        num_agents=agent_number,
        rng=__import__("random").Random(assignment_seed),
    )
    run_config = RunConfiguration(
        branch_id=branch_spec.branch_id,
        branch_decimal=branch_spec.branch_decimal,
        map_type=branch_spec.map_type,
        map_obstacle_type=branch_spec.map_obstacle_type,
        target_type=branch_spec.target_type_active,
        agent_number=agent_number,
        agent_number_index=agent_number_index,
        run_index=run_index,
        run_config_id=f"run[{branch_spec.branch_decimal}.{agent_number_index}.{run_index}]",
        map_identifier=f"artificial_{branch_spec.base_rows}x{branch_spec.base_cols}_seed_{map_seed}",
        map_seed=map_seed,
        assignment_seed=assignment_seed,
        dynamic_schedule_seed=None,
        paired_source=False,
        starts_and_goals=[
            {
                "agent_id": agent["id"],
                "start": list(agent["start"]),
                "goal": list(agent["goal"]),
            }
            for agent in agents
        ],
        notes="Fresh artificial map for this run configuration.",
    )
    return PreparedRunContext(
        run_configuration=run_config,
        agents=agents,
        base_map=base_map,
        classical_map=classical_map,
        cyclic_map=cyclic_map,
    )


def _prepare_dynamic_branch_state(branch_spec: BranchSpec, *, seed_base: int) -> DynamicBranchState:
    schedule_seed = _seed_for(branch_spec.map_type, seed_base, "dynamic_schedule")
    raw_obstacle_matrix = load_port_obstacle_matrix(
        image_path=branch_spec.image_path,
        threshold=branch_spec.image_threshold,
        resize_longest_side=branch_spec.image_resize_longest_side,
    )
    if branch_spec.dynamic_target_static_obstacle_density is None:
        static_matrix = [row[:] for row in raw_obstacle_matrix]
    else:
        static_matrix = preprocess_static_obstacle_density(
            obstacle_matrix=raw_obstacle_matrix,
            target_density=branch_spec.dynamic_target_static_obstacle_density,
            seed=schedule_seed,
        )
    dynamic_generation_mode = "group_patch"
    try:
        dynamic_loop_frames = build_dynamic_loop(
            base_matrix=static_matrix,
            dynamic_density=branch_spec.dynamic_target_dynamic_obstacle_density or 0.10,
            loop_length=branch_spec.dynamic_loop_sequence_length or 30,
            group_stay_durations=branch_spec.dynamic_group_stay_durations or (3, 4, 5),
            seed=schedule_seed,
        )
    except RuntimeError:
        dynamic_generation_mode = "scattered_fallback"
        dynamic_loop_frames = _fallback_build_dynamic_loop(
            base_matrix=static_matrix,
            dynamic_density=branch_spec.dynamic_target_dynamic_obstacle_density or 0.10,
            loop_length=branch_spec.dynamic_loop_sequence_length or 30,
            seed=schedule_seed,
        )
    classical_loop, cyclic_loop = build_mapped_loop(dynamic_loop_frames)
    assignment_map = get_shared_assignment_map(classical_loop)
    return DynamicBranchState(
        raw_obstacle_matrix=raw_obstacle_matrix,
        static_matrix=static_matrix,
        dynamic_loop_frames=dynamic_loop_frames,
        classical_loop=classical_loop,
        cyclic_loop=cyclic_loop,
        assignment_map=assignment_map,
        map_identifier=f"{branch_spec.map_type}_shared_map_seed_{schedule_seed}_{dynamic_generation_mode}",
        schedule_seed=schedule_seed,
    )


def _prepare_dynamic_run_context(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState,
    agent_number: int,
    agent_number_index: int,
    run_index: int,
    seed_base: int,
) -> PreparedRunContext:
    assignment_seed = _seed_for(branch_spec.map_type, seed_base, "assign", agent_number, run_index)
    agents = sample_agent_start_goal_pairs(
        composite_map=dynamic_state.assignment_map,
        num_agents=agent_number,
        rng=__import__("random").Random(assignment_seed),
    )
    run_config = RunConfiguration(
        branch_id=branch_spec.branch_id,
        branch_decimal=branch_spec.branch_decimal,
        map_type=branch_spec.map_type,
        map_obstacle_type=branch_spec.map_obstacle_type,
        target_type=branch_spec.target_type_active,
        agent_number=agent_number,
        agent_number_index=agent_number_index,
        run_index=run_index,
        run_config_id=f"run[{branch_spec.branch_decimal}.{agent_number_index}.{run_index}]",
        map_identifier=dynamic_state.map_identifier,
        map_seed=dynamic_state.schedule_seed,
        assignment_seed=assignment_seed,
        dynamic_schedule_seed=dynamic_state.schedule_seed,
        paired_source=False,
        starts_and_goals=[
            {
                "agent_id": agent["id"],
                "start": list(agent["start"]),
                "goal": list(agent["goal"]),
            }
            for agent in agents
        ],
        notes="Shared dynamic map source; unique initial conditions for this run.",
    )
    return PreparedRunContext(run_configuration=run_config, agents=agents)


def _format_metric(value: float | int | None) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _log_mapping_record(logger: ExperimentLogger, record: MappingRunRecord) -> None:
    logger.log(
        "      "
        f"{_mapping_label(record.mapping_name)} | {record.mapping_record_id} | "
        f"status={_status_label(record)} | time={record.computation_time_seconds:.4f}s | "
        f"conflicts={_format_metric(record.num_conflicts_detected)} | "
        f"avg_path={_format_metric(record.average_path_length)} | "
        f"paired={record.paired_run}"
    )


def _aggregate_mapping(records: list[MappingRunRecord]) -> tuple[float | None, float | None, float | None]:
    successful = [record for record in records if record.success]
    if not successful:
        return None, None, None
    avg_runtime = sum(record.computation_time_seconds for record in successful) / len(successful)
    avg_conflicts = sum((record.num_conflicts_detected or 0) for record in successful) / len(successful)
    path_values = [record.average_path_length for record in successful if record.average_path_length is not None]
    avg_path = sum(path_values) / len(path_values) if path_values else None
    return avg_runtime, avg_conflicts, avg_path


def _build_condition_aggregate(
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
    classical_avg_runtime, classical_avg_conflicts, classical_avg_path = _aggregate_mapping(classical_successes)
    cyclic_avg_runtime, cyclic_avg_conflicts, cyclic_avg_path = _aggregate_mapping(cyclic_successes)
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
        notes=(
            "paired_comparison" if paired_comparison else "cyclic_recovery_non_paired"
            if cyclic_recovery_non_paired else "classical_null_without_cyclic_data"
        ),
    )


def _plot_metric_graph(
    *,
    branch_spec: BranchSpec,
    aggregates: list[ConditionAggregate],
    metric_name: str,
    classical_getter: Callable[[ConditionAggregate], float | None],
    cyclic_getter: Callable[[ConditionAggregate], float | None],
    output_path: Path,
    y_label: str,
    title: str,
) -> None:
    x_values = [aggregate.agent_number for aggregate in aggregates]
    classical_values = [
        math.nan if classical_getter(aggregate) is None else classical_getter(aggregate)
        for aggregate in aggregates
    ]
    cyclic_paired_values = [
        math.nan
        if not aggregate.paired_comparison or cyclic_getter(aggregate) is None
        else cyclic_getter(aggregate)
        for aggregate in aggregates
    ]
    cyclic_recovery_values = [
        math.nan
        if not aggregate.cyclic_recovery_non_paired or cyclic_getter(aggregate) is None
        else cyclic_getter(aggregate)
        for aggregate in aggregates
    ]

    figure = plt.figure(figsize=(10, 6))
    axes = figure.add_subplot(111)
    axes.plot(x_values, classical_values, marker="o", label="Classical")
    axes.plot(x_values, cyclic_paired_values, marker="o", label="Cyclic (paired)")
    if any(not math.isnan(value) for value in cyclic_recovery_values):
        axes.plot(x_values, cyclic_recovery_values, marker="x", linestyle="--", label="Cyclic (recovery)")
    axes.set_xlabel("Agent number")
    axes.set_ylabel(y_label)
    axes.set_title(title)
    axes.grid(True, alpha=0.3)
    axes.legend()
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def _generate_graphs(branch_spec: BranchSpec, aggregates: list[ConditionAggregate], graphs_dir: Path) -> list[Path]:
    generated_paths: list[Path] = []
    runtime_path = graphs_dir / f"{branch_spec.map_type}_runtime.png"
    _plot_metric_graph(
        branch_spec=branch_spec,
        aggregates=aggregates,
        metric_name="runtime",
        classical_getter=lambda aggregate: aggregate.classical_avg_computation_time,
        cyclic_getter=lambda aggregate: aggregate.cyclic_avg_computation_time,
        output_path=runtime_path,
        y_label="Average computation time (seconds)",
        title=f"{branch_spec.display_name}: Runtime vs Agent Number",
    )
    generated_paths.append(runtime_path)

    conflicts_path = graphs_dir / f"{branch_spec.map_type}_conflicts.png"
    _plot_metric_graph(
        branch_spec=branch_spec,
        aggregates=aggregates,
        metric_name="conflicts",
        classical_getter=lambda aggregate: aggregate.classical_avg_conflicts,
        cyclic_getter=lambda aggregate: aggregate.cyclic_avg_conflicts,
        output_path=conflicts_path,
        y_label="Average number of conflicts",
        title=f"{branch_spec.display_name}: Conflicts vs Agent Number",
    )
    generated_paths.append(conflicts_path)

    if branch_spec.path_length_graph_enabled:
        path_length_path = graphs_dir / f"{branch_spec.map_type}_path_length.png"
        _plot_metric_graph(
            branch_spec=branch_spec,
            aggregates=aggregates,
            metric_name="path_length",
            classical_getter=lambda aggregate: aggregate.classical_avg_path_length,
            cyclic_getter=lambda aggregate: aggregate.cyclic_avg_path_length,
            output_path=path_length_path,
            y_label="Average of average path length",
            title=f"{branch_spec.display_name}: Path Length vs Agent Number",
        )
        generated_paths.append(path_length_path)

    return generated_paths


def _log_branch_header(logger: ExperimentLogger, branch_spec: BranchSpec) -> None:
    logger.log("=" * 88)
    logger.log(f"Branch: {branch_spec.display_name} ({branch_spec.map_type})")
    logger.log(f"Map obstacle type: {branch_spec.map_obstacle_type}")
    logger.log(f"Documented target type: {branch_spec.target_type_documented}")
    logger.log(f"Active target type: {branch_spec.target_type_active}")
    logger.log(f"Required successes (n): {branch_spec.required_successes}")
    logger.log(f"Maximum classical attempts (m): {branch_spec.max_classical_attempts}")
    logger.log(f"Runtime limit per run: {branch_spec.runtime_limit_seconds:.1f}s")
    logger.log(f"Agent numbers: {branch_spec.agent_numbers}")
    if branch_spec.notes:
        logger.log(f"Notes: {branch_spec.notes}")
    logger.log("=" * 88)


def _log_dynamic_state(logger: ExperimentLogger, branch_spec: BranchSpec, dynamic_state: DynamicBranchState) -> None:
    rows = len(dynamic_state.static_matrix)
    cols = len(dynamic_state.static_matrix[0]) if rows else 0
    total_cells = rows * cols
    raw_static_count = sum(cell == 1 for row in dynamic_state.raw_obstacle_matrix for cell in row)
    static_count = sum(cell == 1 for row in dynamic_state.static_matrix for cell in row)
    dynamic_count = sum(cell == 2 for row in dynamic_state.dynamic_loop_frames[0] for cell in row) if dynamic_state.dynamic_loop_frames else 0
    logger.log("Shared dynamic map prepared:")
    logger.log(f"  Image path: {branch_spec.image_path}")
    if branch_spec.image_resize_longest_side is not None:
        logger.log(f"  Resized longest side: {branch_spec.image_resize_longest_side}")
    logger.log(f"  Dimensions: {rows}x{cols}")
    logger.log(f"  Raw static density: {raw_static_count / total_cells:.4f}")
    if branch_spec.dynamic_target_static_obstacle_density is None:
        logger.log("  Target static density: preserved from source image")
    else:
        logger.log(f"  Target static density: {branch_spec.dynamic_target_static_obstacle_density:.4f}")
    logger.log(f"  Dynamic density target: {(branch_spec.dynamic_target_dynamic_obstacle_density or 0.0):.4f}")
    logger.log(f"  Static obstacle cells per frame: {static_count}")
    logger.log(f"  Dynamic obstacle cells per frame: {dynamic_count}")
    logger.log(f"  Loop length: {len(dynamic_state.dynamic_loop_frames)}")
    logger.log(f"  Shared schedule seed: {dynamic_state.schedule_seed}")
    if "_" in dynamic_state.map_identifier:
        logger.log(f"  Dynamic generation mode: {dynamic_state.map_identifier.split('_')[-1]}")


def _print_aggregate_block(logger: ExperimentLogger, aggregate: ConditionAggregate) -> None:
    logger.log(
        "    Condition aggregate | "
        f"{aggregate.condition_id} | agent_number={aggregate.agent_number} | "
        f"classical_successes={aggregate.num_classical_successes}/{aggregate.num_classical_attempts} | "
        f"cyclic_successes={aggregate.num_cyclic_successes}/{aggregate.num_cyclic_attempts} | "
        f"paired={aggregate.paired_comparison}"
    )
    logger.log(
        "      Averages | "
        f"classical_time={_format_metric(aggregate.classical_avg_computation_time)} | "
        f"cyclic_time={_format_metric(aggregate.cyclic_avg_computation_time)} | "
        f"classical_conflicts={_format_metric(aggregate.classical_avg_conflicts)} | "
        f"cyclic_conflicts={_format_metric(aggregate.cyclic_avg_conflicts)} | "
        f"classical_path={_format_metric(aggregate.classical_avg_path_length)} | "
        f"cyclic_path={_format_metric(aggregate.cyclic_avg_path_length)}"
    )


def run_selected_experiment(map_type: str, *, seed_base: int = 1) -> dict[str, Any]:
    branch_spec = get_branch_spec(map_type)
    output_manager = BranchOutputManager(branch_spec)
    logger = ExperimentLogger(output_manager.logs_dir / "experiment.log")
    _log_branch_header(logger, branch_spec)

    _write_json(output_manager.metadata_dir / "branch_spec.json", branch_spec.to_dict())

    run_configurations: list[dict[str, Any]] = []
    run_records: list[dict[str, Any]] = []
    aggregates_payload: list[dict[str, Any]] = []

    dynamic_state: DynamicBranchState | None = None
    if branch_spec.is_dynamic:
        dynamic_state = _prepare_dynamic_branch_state(branch_spec, seed_base=seed_base)
        _log_dynamic_state(logger, branch_spec, dynamic_state)
        _write_json(
            output_manager.metadata_dir / "shared_dynamic_state.json",
            {
                "map_identifier": dynamic_state.map_identifier,
                "schedule_seed": dynamic_state.schedule_seed,
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

        classical_records_objects: list[MappingRunRecord] = []
        cyclic_records_objects: list[MappingRunRecord] = []
        saved_success_contexts: list[PreparedRunContext] = []

        for classical_attempt_index in range(branch_spec.max_classical_attempts):
            run_index = classical_attempt_index
            try:
                prepared_context = (
                    _prepare_dynamic_run_context(
                        branch_spec=branch_spec,
                        dynamic_state=dynamic_state,
                        agent_number=agent_number,
                        agent_number_index=agent_number_index,
                        run_index=run_index,
                        seed_base=seed_base,
                    )
                    if branch_spec.is_dynamic
                    else _prepare_static_run_context(
                        branch_spec=branch_spec,
                        agent_number=agent_number,
                        agent_number_index=agent_number_index,
                        run_index=run_index,
                        seed_base=seed_base,
                    )
                )
            except Exception as exc:
                logger.log(
                    f"  Classical attempt {classical_attempt_index + 1}/{branch_spec.max_classical_attempts} | "
                    f"run_index={run_index} | setup_failed={type(exc).__name__}: {exc}"
                )
                failure_run_config = RunConfiguration(
                    branch_id=branch_spec.branch_id,
                    branch_decimal=branch_spec.branch_decimal,
                    map_type=branch_spec.map_type,
                    map_obstacle_type=branch_spec.map_obstacle_type,
                    target_type=branch_spec.target_type_active,
                    agent_number=agent_number,
                    agent_number_index=agent_number_index,
                    run_index=run_index,
                    run_config_id=f"run[{branch_spec.branch_decimal}.{agent_number_index}.{run_index}]",
                    map_identifier="setup_failure",
                    map_seed=_seed_for(branch_spec.map_type, seed_base, "map", agent_number, run_index),
                    assignment_seed=_seed_for(branch_spec.map_type, seed_base, "assign", agent_number, run_index),
                    dynamic_schedule_seed=(dynamic_state.schedule_seed if dynamic_state is not None else None),
                    paired_source=False,
                    starts_and_goals=[],
                    notes=f"setup_failed:{type(exc).__name__}:{exc}",
                )
                run_configurations.append(failure_run_config.to_dict())
                record = _build_mapping_record(
                    run_configuration=failure_run_config,
                    mapping_name="classical",
                    comparison_case="classical_attempt",
                    runtime_limit_seconds=branch_spec.runtime_limit_seconds,
                    solver_result=None,
                    elapsed_seconds=0.0,
                    paired_run=False,
                    success=False,
                    failure_reason=f"setup_failed:{type(exc).__name__}:{exc}",
                    dynamic=branch_spec.is_dynamic,
                )
                classical_records_objects.append(record)
                run_records.append(record.to_dict())
                _log_mapping_record(logger, record)
                continue

            run_configurations.append(prepared_context.run_configuration.to_dict())
            logger.log(
                f"  Classical attempt {classical_attempt_index + 1}/{branch_spec.max_classical_attempts} | "
                f"{prepared_context.run_configuration.run_config_id} | map_id={prepared_context.run_configuration.map_identifier}"
            )
            success, solver_result, elapsed_seconds, failure_reason = (
                _run_dynamic_mapping(
                    mapped_loop=dynamic_state.classical_loop,
                    agents=prepared_context.agents,
                    runtime_limit_seconds=branch_spec.runtime_limit_seconds,
                    logger=logger,
                    label=f"Classical {prepared_context.run_configuration.run_config_id}",
                )
                if branch_spec.is_dynamic
                else _run_static_mapping(
                    composite_map=prepared_context.classical_map,
                    agents=prepared_context.agents,
                    runtime_limit_seconds=branch_spec.runtime_limit_seconds,
                    logger=logger,
                    label=f"Classical {prepared_context.run_configuration.run_config_id}",
                )
            )
            record = _build_mapping_record(
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
            classical_records_objects.append(record)
            run_records.append(record.to_dict())
            _log_mapping_record(logger, record)
            if success:
                prepared_context.run_configuration.paired_source = True
                saved_success_contexts.append(prepared_context)
                if len(saved_success_contexts) >= branch_spec.required_successes:
                    logger.log(
                        f"  Classical reached required successes ({branch_spec.required_successes})."
                    )
                    break

        classical_success = len(saved_success_contexts) >= branch_spec.required_successes
        if classical_success:
            logger.log("  Replaying cyclic on saved successful classical run configurations.")
            for paired_index, prepared_context in enumerate(saved_success_contexts, start=1):
                logger.log(
                    f"  Cyclic paired replay {paired_index}/{len(saved_success_contexts)} | "
                    f"{prepared_context.run_configuration.run_config_id}"
                )
                success, solver_result, elapsed_seconds, failure_reason = (
                    _run_dynamic_mapping(
                        mapped_loop=dynamic_state.cyclic_loop,
                        agents=prepared_context.agents,
                        runtime_limit_seconds=branch_spec.runtime_limit_seconds,
                        logger=logger,
                        label=f"Cyclic {prepared_context.run_configuration.run_config_id}",
                    )
                    if branch_spec.is_dynamic
                    else _run_static_mapping(
                        composite_map=prepared_context.cyclic_map,
                        agents=prepared_context.agents,
                        runtime_limit_seconds=branch_spec.runtime_limit_seconds,
                        logger=logger,
                        label=f"Cyclic {prepared_context.run_configuration.run_config_id}",
                    )
                )
                record = _build_mapping_record(
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
                cyclic_records_objects.append(record)
                run_records.append(record.to_dict())
                _log_mapping_record(logger, record)
        else:
            logger.log(
                "  Classical did not reach required successes. "
                "Classical receives a null condition-level data point; cyclic enters recovery mode."
            )
            cyclic_success_count = 0
            recovery_attempt_index = 0
            while (
                cyclic_success_count < branch_spec.required_successes
                and recovery_attempt_index < MAX_CYCLIC_RECOVERY_ATTEMPTS
            ):
                run_index = branch_spec.max_classical_attempts + recovery_attempt_index
                try:
                    prepared_context = (
                        _prepare_dynamic_run_context(
                            branch_spec=branch_spec,
                            dynamic_state=dynamic_state,
                            agent_number=agent_number,
                            agent_number_index=agent_number_index,
                            run_index=run_index,
                            seed_base=seed_base,
                        )
                        if branch_spec.is_dynamic
                        else _prepare_static_run_context(
                            branch_spec=branch_spec,
                            agent_number=agent_number,
                            agent_number_index=agent_number_index,
                            run_index=run_index,
                            seed_base=seed_base,
                        )
                    )
                except Exception as exc:
                    logger.log(
                        f"  Cyclic recovery attempt {recovery_attempt_index + 1}/{MAX_CYCLIC_RECOVERY_ATTEMPTS} | "
                        f"run_index={run_index} | setup_failed={type(exc).__name__}: {exc}"
                    )
                    failure_run_config = RunConfiguration(
                        branch_id=branch_spec.branch_id,
                        branch_decimal=branch_spec.branch_decimal,
                        map_type=branch_spec.map_type,
                        map_obstacle_type=branch_spec.map_obstacle_type,
                        target_type=branch_spec.target_type_active,
                        agent_number=agent_number,
                        agent_number_index=agent_number_index,
                        run_index=run_index,
                        run_config_id=f"run[{branch_spec.branch_decimal}.{agent_number_index}.{run_index}]",
                        map_identifier="setup_failure",
                        map_seed=_seed_for(branch_spec.map_type, seed_base, "map", agent_number, run_index),
                        assignment_seed=_seed_for(branch_spec.map_type, seed_base, "assign", agent_number, run_index),
                        dynamic_schedule_seed=(dynamic_state.schedule_seed if dynamic_state is not None else None),
                        paired_source=False,
                        starts_and_goals=[],
                        notes=f"setup_failed:{type(exc).__name__}:{exc}",
                    )
                    run_configurations.append(failure_run_config.to_dict())
                    record = _build_mapping_record(
                        run_configuration=failure_run_config,
                        mapping_name="cyclic",
                        comparison_case="cyclic_recovery",
                        runtime_limit_seconds=branch_spec.runtime_limit_seconds,
                        solver_result=None,
                        elapsed_seconds=0.0,
                        paired_run=False,
                        success=False,
                        failure_reason=f"setup_failed:{type(exc).__name__}:{exc}",
                        dynamic=branch_spec.is_dynamic,
                    )
                    cyclic_records_objects.append(record)
                    run_records.append(record.to_dict())
                    _log_mapping_record(logger, record)
                    recovery_attempt_index += 1
                    continue

                run_configurations.append(prepared_context.run_configuration.to_dict())
                logger.log(
                    f"  Cyclic recovery attempt {recovery_attempt_index + 1}/{MAX_CYCLIC_RECOVERY_ATTEMPTS} | "
                    f"{prepared_context.run_configuration.run_config_id}"
                )
                success, solver_result, elapsed_seconds, failure_reason = (
                    _run_dynamic_mapping(
                        mapped_loop=dynamic_state.cyclic_loop,
                        agents=prepared_context.agents,
                        runtime_limit_seconds=branch_spec.runtime_limit_seconds,
                        logger=logger,
                        label=f"Cyclic {prepared_context.run_configuration.run_config_id}",
                    )
                    if branch_spec.is_dynamic
                    else _run_static_mapping(
                        composite_map=prepared_context.cyclic_map,
                        agents=prepared_context.agents,
                        runtime_limit_seconds=branch_spec.runtime_limit_seconds,
                        logger=logger,
                        label=f"Cyclic {prepared_context.run_configuration.run_config_id}",
                    )
                )
                record = _build_mapping_record(
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
                cyclic_records_objects.append(record)
                run_records.append(record.to_dict())
                _log_mapping_record(logger, record)
                if success:
                    cyclic_success_count += 1
                recovery_attempt_index += 1
            if cyclic_success_count < branch_spec.required_successes:
                logger.log(
                    f"  Cyclic recovery stopped at safeguard limit ({MAX_CYCLIC_RECOVERY_ATTEMPTS} attempts) "
                    f"with {cyclic_success_count} successes."
                )

        aggregate = _build_condition_aggregate(
            branch_spec=branch_spec,
            agent_number=agent_number,
            agent_number_index=agent_number_index,
            classical_records=classical_records_objects,
            cyclic_records=cyclic_records_objects,
        )
        aggregates_payload.append(aggregate.to_dict())
        _print_aggregate_block(logger, aggregate)

    _write_json(output_manager.records_dir / "run_configurations.json", run_configurations)
    _write_json(output_manager.records_dir / "run_records.json", run_records)
    _write_json(output_manager.aggregates_dir / "condition_summary.json", aggregates_payload)
    _write_csv(output_manager.records_dir / "run_configurations.csv", run_configurations)
    _write_csv(output_manager.records_dir / "run_records.csv", run_records)
    _write_csv(output_manager.aggregates_dir / "condition_summary.csv", aggregates_payload)

    aggregate_objects = [ConditionAggregate(**payload) for payload in aggregates_payload]
    graph_paths = _generate_graphs(branch_spec, aggregate_objects, output_manager.graphs_dir)

    logger.log("")
    logger.log("Final aggregate table:")
    for aggregate in aggregate_objects:
        _print_aggregate_block(logger, aggregate)

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
