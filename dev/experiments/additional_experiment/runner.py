from __future__ import annotations

import copy
import json
import shutil
import time
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from dev.experiments.additional_experiment.plotting import generate_additional_experiment_graphs
from dev.experiments.branch_specs import BranchSpec
from dev.experiments.study.io_utils import BufferedExperimentLogger, ExperimentLogger, write_csv, write_json
from dev.experiments.study.models import MappingRunRecord, PreparedRunContext
from dev.experiments.study.preparation import prepare_static_run_context
from dev.experiments.study.runtime import build_mapping_record, run_static_mapping
from dev.master_config import compact_clustering
from dev.master_config_additional_experiment import (
    ADDITIONAL_EXPERIMENT_MAPS,
    ADDITIONAL_EXPERIMENT_MAX_TOTAL_ATTEMPTS_PER_WEIGHT,
    ADDITIONAL_EXPERIMENT_REUSE_INITIAL_CONDITIONS_ACROSS_WEIGHTS,
    ADDITIONAL_EXPERIMENT_RUNS_PER_WEIGHT,
    ADDITIONAL_EXPERIMENT_TEMPORARY_EXTRA_ATTEMPTS,
    ADDITIONAL_EXPERIMENT_TIME_LIMIT_SECONDS,
    ADDITIONAL_EXPERIMENT_USE_TEMPORARY_TESTING,
    ADDITIONAL_EXPERIMENT_WEIGHT_LOWER_BOUND,
    ADDITIONAL_EXPERIMENT_WEIGHT_STEP,
    ADDITIONAL_EXPERIMENT_WEIGHT_UPPER_BOUND,
    ADDITIONAL_EXPERIMENT_WEIGHTS,
    MAP_TYPE_ADDITIONAL_EXP,
    OUTPUT_ADDITIONAL_EXP_ROOT,
    recompute_MAPF,
    to_generate,
)


VALID_GENERATION_TARGETS = {"graphs_and_data", "nothing"}
COUNTED_CATEGORIES = {"successful", "unfinished"}


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _resolve_generation_target() -> str:
    generation_target = str(to_generate)
    if generation_target not in VALID_GENERATION_TARGETS:
        raise ValueError("to_generate must be one of 'graphs_and_data' or 'nothing'.")
    return generation_target


def _float_to_weight_label(weight: float) -> str:
    return f"{float(weight):.1f}"


def _safe_map_config(config: dict[str, Any]) -> dict[str, Any]:
    safe = dict(config)
    if safe.get("image_path") is not None:
        safe["image_path"] = str(safe["image_path"])
    if safe.get("map_size") is not None:
        safe["map_size"] = list(safe["map_size"])
    return safe


def _build_branch_spec(map_config: dict[str, Any], *, weight: float) -> BranchSpec:
    map_type = str(map_config["map_type"])
    agent_count = int(map_config["agent_count"])
    map_size = map_config.get("map_size")
    return BranchSpec(
        map_type=map_type,
        branch_id=map_type,
        branch_decimal=str(map_config.get("branch_decimal", "additional")),
        map_obstacle_type="static",
        map_obstacle_index=0,
        map_type_index=int(map_config.get("map_type_index", 90)),
        display_name=str(map_config.get("display_name", map_type.replace("_", " ").title())),
        target_type_documented="dispersed_targets",
        target_type_active="dispersed_targets",
        seed_base=int(map_config["seed"]),
        agent_number_range=(agent_count, agent_count, 1),
        agent_numbers=[agent_count],
        runtime_limit_seconds=float(ADDITIONAL_EXPERIMENT_TIME_LIMIT_SECONDS),
        counted_runs_required=int(ADDITIONAL_EXPERIMENT_RUNS_PER_WEIGHT),
        num_last_runs_to_visualize_jointly_successful=0,
        num_last_runs_to_visualize_independently_successful=0,
        path_length_graph_enabled=False,
        is_dynamic=False,
        start_distribution_mode="dispersed",
        goal_distribution_mode="dispersed",
        clustered_start_goal_min_distance=None,
        require_individual_reachability=bool(map_config.get("require_individual_reachability", False)),
        zone_relationship_mode="none",
        compact_clustering=bool(compact_clustering),
        clustering_style_name="compact" if compact_clustering else "spaced",
        base_rows=None if map_size is None else int(map_size[0]),
        base_cols=None if map_size is None else int(map_size[1]),
        static_obstacle_density=(
            None if map_config.get("static_obstacle_density") is None else float(map_config["static_obstacle_density"])
        ),
        image_path=None if map_config.get("image_path") is None else str(map_config["image_path"]),
        image_threshold=int(map_config.get("image_threshold", 127)),
        image_resize_longest_side=(
            None if map_config.get("image_resize_longest_side") is None else int(map_config["image_resize_longest_side"])
        ),
        dynamic_target_static_obstacle_density=None,
        dynamic_target_dynamic_obstacle_density=None,
        dynamic_loop_sequence_length=None,
        dynamic_group_stay_durations=None,
        dynamic_generation_cell_mode="all_free",
        spawnable_cell_mode="all_free",
        solver_name="ECBS",
        enhanced_cbs_enabled=True,
        solver_suboptimality_factor=float(weight),
        true_static_shortest_path_distance=True,
        tight_time_horizon=False,
        agent_cohesion_enabled=False,
        cohesion_factor=0.0,
        filter_individual_runs_until_cyclic_faster=False,
        filter_individual_runs_until_cyclic_faster_max_attempts=None,
        rerun_until_cyclic_faster=False,
        rerun_until_cyclic_faster_max_batches=None,
        notes=(
            "Additional weight-sweep experiment. Agent count is fixed, starts and goals are dispersed, "
            "and ECBS suboptimality factor is the condition variable. Average path length is recorded "
            "but not plotted."
        ),
    )


class RunContextCache:
    def __init__(self, *, base_branch_spec: BranchSpec, agent_count: int, logger: ExperimentLogger):
        self.base_branch_spec = base_branch_spec
        self.agent_count = int(agent_count)
        self.logger = logger
        self._cache: dict[int, PreparedRunContext] = {}

    def get(self, run_index: int) -> PreparedRunContext:
        if run_index not in self._cache:
            self.logger.log(f"    Preparing deterministic initial condition run_index={run_index}...")
            self._cache[run_index] = prepare_static_run_context(
                branch_spec=self.base_branch_spec,
                agent_number=self.agent_count,
                agent_number_index=0,
                run_index=run_index,
                seed_base=self.base_branch_spec.seed_base,
            )
        return copy.deepcopy(self._cache[run_index])


def _execute_mapping(
    *,
    branch_spec: BranchSpec,
    prepared_context: PreparedRunContext,
    mapping_name: str,
    logger: BufferedExperimentLogger,
) -> tuple[dict[str, Any] | None, float, str, MappingRunRecord]:
    composite_map = prepared_context.classical_map if mapping_name == "classical" else prepared_context.cyclic_map
    if composite_map is None:
        raise ValueError(f"missing {mapping_name} composite map")
    label = f"{mapping_name.title()} {prepared_context.run_configuration.run_config_id} | w={branch_spec.solver_suboptimality_factor}"
    solver_result, elapsed_seconds, solver_status = run_static_mapping(
        composite_map=composite_map,
        agents=prepared_context.agents,
        runtime_limit_seconds=branch_spec.runtime_limit_seconds,
        logger=logger,
        label=label,
        solver_suboptimality_factor=branch_spec.solver_suboptimality_factor,
        true_static_shortest_path_distance=branch_spec.true_static_shortest_path_distance,
        tight_time_horizon=branch_spec.tight_time_horizon,
        agent_cohesion_enabled=False,
        use_ecbs=True,
    )
    record = build_mapping_record(
        run_configuration=prepared_context.run_configuration,
        mapping_name=mapping_name,
        comparison_case="additional_weight_sweep",
        runtime_limit_seconds=branch_spec.runtime_limit_seconds,
        solver_name=(solver_result or {}).get("solver_name", branch_spec.solver_name),
        enhanced_cbs_enabled=branch_spec.enhanced_cbs_enabled,
        solver_suboptimality_factor=(solver_result or {}).get(
            "solver_suboptimality_factor", branch_spec.solver_suboptimality_factor
        ),
        solver_result=solver_result,
        elapsed_seconds=elapsed_seconds,
        solver_status=solver_status,
        paired_run=True,
        dynamic=False,
    )
    weight_label = _float_to_weight_label(branch_spec.solver_suboptimality_factor or 1.0)
    record.mapping_record_id = (
        f"mapping_weight[{prepared_context.run_configuration.branch_decimal}."
        f"w{weight_label}.{prepared_context.run_configuration.run_index}.{record.mapping_index}]"
    )
    return solver_result, elapsed_seconds, solver_status, record


def _count_cyclic_results(records: list[MappingRunRecord]) -> tuple[int, int]:
    successful = sum(record.result_category == "successful" for record in records)
    unfinished = sum(record.result_category == "unfinished" for record in records)
    return successful, unfinished


def _cyclic_unfinished_would_trigger_boundary(
    *,
    counted_runs_required: int,
    cyclic_records: list[MappingRunRecord],
    cyclic_record: MappingRunRecord,
) -> bool:
    if not cyclic_record.counted_run or cyclic_record.result_category != "unfinished":
        return False
    _successful, unfinished = _count_cyclic_results(cyclic_records)
    projected_unfinished = unfinished + 1
    maximum_possible_successful = int(counted_runs_required) - projected_unfinished
    return projected_unfinished > maximum_possible_successful


def _record_pair(
    *,
    prepared_context: PreparedRunContext,
    classical_record: MappingRunRecord,
    cyclic_record: MappingRunRecord,
    suboptimality_factor: float,
    run_configurations: list[dict[str, Any]],
    run_records: list[dict[str, Any]],
    classical_records: list[MappingRunRecord],
    cyclic_records: list[MappingRunRecord],
) -> None:
    prepared_context.run_configuration.paired_source = True
    run_config_payload = prepared_context.run_configuration.to_dict()
    run_config_payload["suboptimality_factor"] = float(suboptimality_factor)
    run_config_payload["weight_run_config_id"] = (
        f"weight_run[{_float_to_weight_label(suboptimality_factor)}.{prepared_context.run_configuration.run_index}]"
    )
    run_configurations.append(run_config_payload)

    for record in (classical_record, cyclic_record):
        payload = record.to_dict()
        payload["suboptimality_factor"] = float(suboptimality_factor)
        payload["weight_mapping_record_id"] = (
            f"weight_mapping[{_float_to_weight_label(suboptimality_factor)}.{record.run_index}.{record.mapping_index}]"
        )
        run_records.append(payload)

    classical_records.append(classical_record)
    cyclic_records.append(cyclic_record)


def _aggregate_mapping(records: list[MappingRunRecord]) -> tuple[float | None, float | None, float | None]:
    counted_records = [record for record in records if record.counted_run]
    if not counted_records:
        return None, None, None
    avg_halted_time = sum(record.time_computation_halted_seconds for record in counted_records) / len(counted_records)
    avg_conflicts = sum((record.num_conflicts_detected_at_halt or 0) for record in counted_records) / len(counted_records)
    path_values = [record.average_path_length for record in records if record.solved_run and record.average_path_length is not None]
    avg_path = sum(path_values) / len(path_values) if path_values else None
    return avg_halted_time, avg_conflicts, avg_path


def _aggregate_weight_condition(
    *,
    branch_spec: BranchSpec,
    suboptimality_factor: float,
    weight_index: int,
    classical_records: list[MappingRunRecord],
    cyclic_records: list[MappingRunRecord],
    total_attempts: int,
    discarded_attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    classical_summary = Counter(record.result_category for record in classical_records)
    cyclic_summary = Counter(record.result_category for record in cyclic_records)
    classical_counted = sum(classical_summary.get(category, 0) for category in COUNTED_CATEGORIES)
    cyclic_counted = sum(cyclic_summary.get(category, 0) for category in COUNTED_CATEGORIES)
    classical_avg_time, classical_avg_conflicts, classical_avg_path = _aggregate_mapping(classical_records)
    cyclic_avg_time, cyclic_avg_conflicts, cyclic_avg_path = _aggregate_mapping(cyclic_records)
    return {
        "branch_id": branch_spec.branch_id,
        "branch_decimal": branch_spec.branch_decimal,
        "map_type": branch_spec.map_type,
        "map_obstacle_type": branch_spec.map_obstacle_type,
        "target_type": branch_spec.target_type_active,
        "agent_number": branch_spec.agent_numbers[0],
        "suboptimality_factor": float(suboptimality_factor),
        "weight_index": int(weight_index),
        "condition_id": f"weight[{_float_to_weight_label(suboptimality_factor)}]",
        "counted_runs_required": branch_spec.counted_runs_required,
        "paired_run_configurations": min(len(classical_records), len(cyclic_records)),
        "num_total_paired_attempts": int(total_attempts),
        "num_discarded_attempts": len(discarded_attempts),
        "num_classical_attempts": len(classical_records),
        "num_classical_counted_runs": classical_counted,
        "num_classical_successful_runs": classical_summary.get("successful", 0),
        "num_classical_unfinished_runs": classical_summary.get("unfinished", 0),
        "num_cyclic_attempts": len(cyclic_records),
        "num_cyclic_counted_runs": cyclic_counted,
        "num_cyclic_successful_runs": cyclic_summary.get("successful", 0),
        "num_cyclic_unfinished_runs": cyclic_summary.get("unfinished", 0),
        "classical_avg_time_computation_halted": classical_avg_time,
        "classical_avg_conflicts_at_halt": classical_avg_conflicts,
        "classical_avg_path_length": classical_avg_path,
        "cyclic_avg_time_computation_halted": cyclic_avg_time,
        "cyclic_avg_conflicts_at_halt": cyclic_avg_conflicts,
        "cyclic_avg_path_length": cyclic_avg_path,
        "notes": (
            "additional_weight_sweep; line_graph_output; path_length_recorded_not_plotted"
            + ("; temporary_testing_enabled" if ADDITIONAL_EXPERIMENT_USE_TEMPORARY_TESTING else "")
        ),
    }


def _run_weight_condition(
    *,
    weight_branch_spec: BranchSpec,
    context_cache: RunContextCache,
    suboptimality_factor: float,
    weight_index: int,
    logger: ExperimentLogger,
) -> dict[str, Any]:
    classical_records: list[MappingRunRecord] = []
    cyclic_records: list[MappingRunRecord] = []
    run_configurations: list[dict[str, Any]] = []
    run_records: list[dict[str, Any]] = []
    discarded_attempts: list[dict[str, Any]] = []

    retained_pairs = 0
    attempt_index = 0
    total_attempts = 0
    retry_attempts_remaining = 0

    logger.log("")
    logger.log("-" * 88)
    logger.log(
        f"Weight condition {weight_index + 1} | w={_float_to_weight_label(suboptimality_factor)} | "
        f"agent_count={weight_branch_spec.agent_numbers[0]}"
    )
    logger.log("-" * 88)

    while retained_pairs < weight_branch_spec.counted_runs_required:
        if attempt_index >= int(ADDITIONAL_EXPERIMENT_MAX_TOTAL_ATTEMPTS_PER_WEIGHT):
            raise RuntimeError(
                "Additional experiment stopped for debugging: maximum paired attempts were exhausted before "
                f"collecting {weight_branch_spec.counted_runs_required} valid runs at "
                f"map={weight_branch_spec.map_type}, w={suboptimality_factor}."
            )

        prepared_context = context_cache.get(attempt_index)
        total_attempts += 1
        logger.log(
            f"  Paired attempt {attempt_index + 1} | run_index={attempt_index} | "
            f"retained={retained_pairs}/{weight_branch_spec.counted_runs_required}"
        )
        buffered_logger = BufferedExperimentLogger()

        _classical_result, _classical_elapsed, _classical_status, classical_record = _execute_mapping(
            branch_spec=weight_branch_spec,
            prepared_context=prepared_context,
            mapping_name="classical",
            logger=buffered_logger,
        )
        _cyclic_result, _cyclic_elapsed, _cyclic_status, cyclic_record = _execute_mapping(
            branch_spec=weight_branch_spec,
            prepared_context=prepared_context,
            mapping_name="cyclic",
            logger=buffered_logger,
        )

        both_counted = classical_record.counted_run and cyclic_record.counted_run
        if not both_counted:
            discarded_attempts.append(
                {
                    "suboptimality_factor": float(suboptimality_factor),
                    "run_index": attempt_index,
                    "reason": "non_counted_pair",
                    "classical_status": classical_record.solver_status,
                    "cyclic_status": cyclic_record.solver_status,
                }
            )
            logger.log(
                "    Discarded paired attempt because at least one mapping was not countable | "
                f"classical={classical_record.result_category} | cyclic={cyclic_record.result_category}"
            )
            attempt_index += 1
            continue

        cyclic_boundary = _cyclic_unfinished_would_trigger_boundary(
            counted_runs_required=weight_branch_spec.counted_runs_required,
            cyclic_records=cyclic_records,
            cyclic_record=cyclic_record,
        )
        if ADDITIONAL_EXPERIMENT_USE_TEMPORARY_TESTING and cyclic_boundary:
            discarded_attempts.append(
                {
                    "suboptimality_factor": float(suboptimality_factor),
                    "run_index": attempt_index,
                    "reason": "cyclic_unfinished_boundary_discarded_for_temporary_testing",
                    "classical_status": classical_record.solver_status,
                    "cyclic_status": cyclic_record.solver_status,
                }
            )
            if retry_attempts_remaining <= 0:
                retry_attempts_remaining = int(ADDITIONAL_EXPERIMENT_TEMPORARY_EXTRA_ATTEMPTS)
                logger.log(
                    "    Discarded paired attempt because cyclic would reach the unfinished majority boundary | "
                    f"extra_attempts_remaining={retry_attempts_remaining}"
                )
            else:
                retry_attempts_remaining -= 1
                logger.log(
                    "    Discarded extra paired attempt because cyclic remained unfinished on the boundary | "
                    f"extra_attempts_remaining={retry_attempts_remaining}"
                )
                if retry_attempts_remaining <= 0:
                    raise RuntimeError(
                        "Additional experiment stopped for debugging: cyclic reached the unfinished boundary and "
                        f"all {ADDITIONAL_EXPERIMENT_TEMPORARY_EXTRA_ATTEMPTS} temporary extra attempts failed at "
                        f"map={weight_branch_spec.map_type}, w={suboptimality_factor}."
                    )
            attempt_index += 1
            continue

        if not ADDITIONAL_EXPERIMENT_USE_TEMPORARY_TESTING and cyclic_boundary:
            raise RuntimeError(
                "Additional experiment stopped for debugging: cyclic reached the unfinished majority boundary at "
                f"map={weight_branch_spec.map_type}, w={suboptimality_factor}. This experiment requires "
                f"{weight_branch_spec.counted_runs_required} valid paired runs per weight."
            )

        _record_pair(
            prepared_context=prepared_context,
            classical_record=classical_record,
            cyclic_record=cyclic_record,
            suboptimality_factor=suboptimality_factor,
            run_configurations=run_configurations,
            run_records=run_records,
            classical_records=classical_records,
            cyclic_records=cyclic_records,
        )
        retry_attempts_remaining = 0
        retained_pairs += 1
        buffered_logger.flush_to(logger)
        logger.log(
            "    Recorded paired run | "
            f"classical={classical_record.result_category}, t={classical_record.time_computation_halted_seconds:.3f}s, "
            f"conflicts={classical_record.num_conflicts_detected_at_halt} | "
            f"cyclic={cyclic_record.result_category}, t={cyclic_record.time_computation_halted_seconds:.3f}s, "
            f"conflicts={cyclic_record.num_conflicts_detected_at_halt} | "
            f"retained={retained_pairs}/{weight_branch_spec.counted_runs_required}"
        )
        attempt_index += 1

    aggregate = _aggregate_weight_condition(
        branch_spec=weight_branch_spec,
        suboptimality_factor=suboptimality_factor,
        weight_index=weight_index,
        classical_records=classical_records,
        cyclic_records=cyclic_records,
        total_attempts=total_attempts,
        discarded_attempts=discarded_attempts,
    )
    logger.log(
        "  Weight aggregate | "
        f"w={_float_to_weight_label(suboptimality_factor)} | "
        f"classical_avg_time={aggregate['classical_avg_time_computation_halted']} | "
        f"cyclic_avg_time={aggregate['cyclic_avg_time_computation_halted']} | "
        f"classical_avg_conflicts={aggregate['classical_avg_conflicts_at_halt']} | "
        f"cyclic_avg_conflicts={aggregate['cyclic_avg_conflicts_at_halt']}"
    )
    return {
        "aggregate": aggregate,
        "run_configurations": run_configurations,
        "run_records": run_records,
        "discarded_attempts": discarded_attempts,
    }


def _map_output_dirs(map_type: str) -> dict[str, Path]:
    root = OUTPUT_ADDITIONAL_EXP_ROOT / map_type
    return {
        "root": root,
        "metadata": root / "metadata",
        "records": root / "records",
        "aggregates": root / "aggregates",
        "graphs": root / "graphs",
        "logs": root / "logs",
    }


def _write_map_outputs(
    *,
    map_config: dict[str, Any],
    branch_spec: BranchSpec,
    aggregates: list[dict[str, Any]],
    run_configurations: list[dict[str, Any]],
    run_records: list[dict[str, Any]],
    discarded_attempts: list[dict[str, Any]],
    graph_paths: list[Path],
) -> None:
    dirs = _map_output_dirs(str(map_config["map_type"]))
    write_json(dirs["metadata"] / "map_config.json", _safe_map_config(map_config))
    write_json(dirs["metadata"] / "branch_spec_template.json", branch_spec.to_dict())
    write_json(dirs["metadata"] / "additional_experiment_settings.json", _additional_settings_payload())
    write_json(dirs["metadata"] / "generated_graphs.json", [str(path) for path in graph_paths])
    write_json(dirs["records"] / "run_configurations.json", run_configurations)
    write_json(dirs["records"] / "run_records.json", run_records)
    write_json(dirs["records"] / "discarded_attempts.json", discarded_attempts)
    write_json(dirs["aggregates"] / "weight_summary.json", aggregates)
    write_csv(dirs["records"] / "run_configurations.csv", run_configurations)
    write_csv(dirs["records"] / "run_records.csv", run_records)
    write_csv(dirs["records"] / "discarded_attempts.csv", discarded_attempts)
    write_csv(dirs["aggregates"] / "weight_summary.csv", aggregates)


def _additional_settings_payload() -> dict[str, Any]:
    return {
        "recompute_MAPF": bool(recompute_MAPF),
        "to_generate": str(to_generate),
        "selected_map_key": str(MAP_TYPE_ADDITIONAL_EXP),
        "weights": [float(weight) for weight in ADDITIONAL_EXPERIMENT_WEIGHTS],
        "weight_lower_bound": float(ADDITIONAL_EXPERIMENT_WEIGHT_LOWER_BOUND),
        "weight_upper_bound": float(ADDITIONAL_EXPERIMENT_WEIGHT_UPPER_BOUND),
        "weight_step": float(ADDITIONAL_EXPERIMENT_WEIGHT_STEP),
        "runs_per_weight": int(ADDITIONAL_EXPERIMENT_RUNS_PER_WEIGHT),
        "time_limit_seconds": float(ADDITIONAL_EXPERIMENT_TIME_LIMIT_SECONDS),
        "use_temporary_testing": bool(ADDITIONAL_EXPERIMENT_USE_TEMPORARY_TESTING),
        "temporary_extra_attempts": int(ADDITIONAL_EXPERIMENT_TEMPORARY_EXTRA_ATTEMPTS),
        "reuse_initial_conditions_across_weights": bool(
            ADDITIONAL_EXPERIMENT_REUSE_INITIAL_CONDITIONS_ACROSS_WEIGHTS
        ),
        "graph_type": "line_graph",
        "plotted_metrics": ["computation_time_halted", "num_conflicts"],
        "recorded_but_not_plotted_metrics": ["average_path_length"],
        "output_root": str(OUTPUT_ADDITIONAL_EXP_ROOT),
    }


def _load_existing_aggregates(map_type: str) -> list[dict[str, Any]]:
    path = _map_output_dirs(map_type)["aggregates"] / "weight_summary.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No saved additional-experiment aggregate file found at {path}. "
            "Set recompute_MAPF=True in master_config_additional_experiment.py first."
        )
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _run_single_map(
    *,
    map_config: dict[str, Any],
    generation_target: str,
    program_start_time: float | None,
) -> dict[str, Any]:
    map_type = str(map_config["map_type"])
    dirs = _map_output_dirs(map_type)
    dirs["root"].mkdir(parents=True, exist_ok=True)
    _reset_dir(dirs["logs"])
    logger = ExperimentLogger(dirs["logs"] / "additional_experiment.log", start_time=program_start_time)

    base_branch_spec = _build_branch_spec(map_config, weight=float(ADDITIONAL_EXPERIMENT_WEIGHTS[0]))
    logger.log("=" * 88)
    logger.log(f"Additional experiment map: {base_branch_spec.display_name} ({map_type})")
    logger.log("=" * 88)
    logger.log(f"recompute_MAPF: {bool(recompute_MAPF)}")
    logger.log(f"to_generate: {generation_target}")
    logger.log(f"output_root: {dirs['root']}")
    logger.log(f"agent_count: {base_branch_spec.agent_numbers[0]}")
    logger.log(f"selected_map_key: {MAP_TYPE_ADDITIONAL_EXP}")
    logger.log(f"weight_lower_bound: {ADDITIONAL_EXPERIMENT_WEIGHT_LOWER_BOUND}")
    logger.log(f"weight_upper_bound: {ADDITIONAL_EXPERIMENT_WEIGHT_UPPER_BOUND}")
    logger.log(f"weight_step: {ADDITIONAL_EXPERIMENT_WEIGHT_STEP}")
    logger.log(f"weights: {[float(weight) for weight in ADDITIONAL_EXPERIMENT_WEIGHTS]}")
    logger.log(f"runs_per_weight: {ADDITIONAL_EXPERIMENT_RUNS_PER_WEIGHT}")
    logger.log(f"temporary_testing: {bool(ADDITIONAL_EXPERIMENT_USE_TEMPORARY_TESTING)}")
    logger.log_elapsed("Program stopwatch started.")

    aggregates: list[dict[str, Any]] = []
    run_configurations: list[dict[str, Any]] = []
    run_records: list[dict[str, Any]] = []
    discarded_attempts: list[dict[str, Any]] = []

    if recompute_MAPF:
        for dirname in ("metadata", "records", "aggregates", "graphs"):
            _reset_dir(dirs[dirname])
        context_cache = RunContextCache(
            base_branch_spec=base_branch_spec,
            agent_count=base_branch_spec.agent_numbers[0],
            logger=logger,
        )
        for weight_index, raw_weight in enumerate(ADDITIONAL_EXPERIMENT_WEIGHTS):
            weight = float(raw_weight)
            weight_branch_spec = replace(base_branch_spec, solver_suboptimality_factor=weight)
            result = _run_weight_condition(
                weight_branch_spec=weight_branch_spec,
                context_cache=context_cache,
                suboptimality_factor=weight,
                weight_index=weight_index,
                logger=logger,
            )
            aggregates.append(result["aggregate"])
            run_configurations.extend(result["run_configurations"])
            run_records.extend(result["run_records"])
            discarded_attempts.extend(result["discarded_attempts"])
        logger.log_elapsed("Raw additional-experiment MAPF data recomputed.")
    else:
        logger.log("recompute_MAPF is False. Existing additional-experiment aggregates will be reused for graph generation.")
        if generation_target != "nothing":
            aggregates = _load_existing_aggregates(map_type)

    graph_paths: list[Path] = []
    if generation_target == "graphs_and_data":
        _reset_dir(dirs["graphs"])
        graph_paths = generate_additional_experiment_graphs(
            map_type=map_type,
            display_name=base_branch_spec.display_name,
            aggregates=aggregates,
            graphs_dir=dirs["graphs"],
        )
        if recompute_MAPF:
            _write_map_outputs(
                map_config=map_config,
                branch_spec=base_branch_spec,
                aggregates=aggregates,
                run_configurations=run_configurations,
                run_records=run_records,
                discarded_attempts=discarded_attempts,
                graph_paths=graph_paths,
            )
        else:
            write_json(dirs["metadata"] / "generated_graphs.json", [str(path) for path in graph_paths])
        logger.log_elapsed("Additional-experiment graphs and data outputs generated.")
    else:
        if recompute_MAPF:
            _write_map_outputs(
                map_config=map_config,
                branch_spec=base_branch_spec,
                aggregates=aggregates,
                run_configurations=run_configurations,
                run_records=run_records,
                discarded_attempts=discarded_attempts,
                graph_paths=[],
            )
        logger.log("No additional-experiment graphs generated because to_generate='nothing'.")

    logger.log("")
    logger.log("Generated graph files:")
    for path in graph_paths:
        logger.log(f"  - {path}")
    logger.log_elapsed("Additional experiment map finished.")

    return {
        "map_type": map_type,
        "display_name": base_branch_spec.display_name,
        "output_root": str(dirs["root"]),
        "weight_summary_path": str(dirs["aggregates"] / "weight_summary.json"),
        "run_records_path": str(dirs["records"] / "run_records.json"),
        "graph_paths": [str(path) for path in graph_paths],
        "log_path": str(dirs["logs"] / "additional_experiment.log"),
    }


def run_additional_experiment(*, program_start_time: float | None = None) -> dict[str, Any]:
    generation_target = _resolve_generation_target()
    OUTPUT_ADDITIONAL_EXP_ROOT.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for map_config in ADDITIONAL_EXPERIMENT_MAPS:
        results.append(
            _run_single_map(
                map_config=map_config,
                generation_target=generation_target,
                program_start_time=program_start_time or time.perf_counter(),
            )
        )
    write_json(
        OUTPUT_ADDITIONAL_EXP_ROOT / "additional_experiment_summary.json",
        {
            "settings": _additional_settings_payload(),
            "maps": results,
        },
    )
    return {
        "experiment": "additional_experiment",
        "output_root": str(OUTPUT_ADDITIONAL_EXP_ROOT),
        "maps": results,
        "generation_target": generation_target,
        "recompute_MAPF": bool(recompute_MAPF),
    }


__all__ = ["run_additional_experiment"]
