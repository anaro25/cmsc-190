"""Build Results-ready main-experiment metric packages for human and LLM readers."""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dev.experiments.branch_specs import BranchSpec
from dev.experiments.study.io_utils import write_csv, write_json


METRICS_DATA_SCHEMA_VERSION = 3


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result):
        return None
    return result


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(float(value), digits)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _percent_change(new_value: float | None, old_value: float | None) -> float | None:
    if new_value is None or old_value is None or abs(old_value) <= 1e-12:
        return None
    return _round(((new_value - old_value) / old_value) * 100.0)


def _difference(new_value: float | None, old_value: float | None) -> float | None:
    if new_value is None or old_value is None:
        return None
    return _round(new_value - old_value)


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or abs(denominator) <= 1e-12:
        return None
    return _round(numerator / denominator)


def _lower_is_better(classical_value: float | None, cyclic_value: float | None) -> str:
    if classical_value is None or cyclic_value is None:
        return "unavailable"
    if abs(classical_value - cyclic_value) <= 1e-12:
        return "same"
    return "cyclic" if cyclic_value < classical_value else "classical"


def _path_tradeoff(classical_value: float | None, cyclic_value: float | None) -> str:
    if classical_value is None or cyclic_value is None:
        return "unavailable"
    if abs(classical_value - cyclic_value) <= 1e-12:
        return "same"
    return "cyclic_longer" if cyclic_value > classical_value else "cyclic_shorter"


def _map_family(category_map_type: str) -> str:
    for prefix in ("static_", "dynamic_"):
        if category_map_type.startswith(prefix):
            return category_map_type[len(prefix) :]
    return category_map_type


def _broad_arrangement(mode: str) -> str:
    return "dispersed" if mode == "dispersed" else "compact"


def _record_from_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
    record = attempt.get("record")
    return dict(record) if isinstance(record, dict) else {}


def _record_id(record: dict[str, Any]) -> str:
    return str(record.get("mapping_record_id") or record.get("run_config_id") or "")


def _run_config_id(attempt: dict[str, Any]) -> str:
    run_configuration = attempt.get("run_configuration")
    if isinstance(run_configuration, dict):
        value = run_configuration.get("run_config_id")
        if value is not None:
            return str(value)
    return str(_record_from_attempt(attempt).get("run_config_id") or "")


def _metric_stats(values: Iterable[float | int | None]) -> dict[str, Any]:
    cleaned = [float(value) for value in values if value is not None]
    if not cleaned:
        return {
            "value_count": 0,
            "mean": None,
            "median": None,
            "minimum": None,
            "maximum": None,
            "population_standard_deviation": None,
        }
    return {
        "value_count": len(cleaned),
        "mean": _round(statistics.fmean(cleaned)),
        "median": _round(statistics.median(cleaned)),
        "minimum": _round(min(cleaned)),
        "maximum": _round(max(cleaned)),
        "population_standard_deviation": _round(statistics.pstdev(cleaned)),
    }


def _configuration_metadata(
    branch_spec: BranchSpec,
    payload: dict[str, Any],
) -> dict[str, Any]:
    dynamic_metadata = payload.get("dynamic_state_metadata") or {}
    map_family = _map_family(branch_spec.category_map_type)
    return {
        "schema_version": METRICS_DATA_SCHEMA_VERSION,
        "map_config": branch_spec.map_type,
        "display_name": branch_spec.display_name,
        "branch_id": branch_spec.branch_id,
        "branch_decimal": branch_spec.branch_decimal,
        "category_index": branch_spec.category_index,
        "layout_index": branch_spec.layout_index,
        "map_category": branch_spec.category_map_type,
        "map_family": map_family,
        "study_context": "campus_crowd_simulation" if "campus" in map_family else "traditional_mapf",
        "environment_type": "dynamic" if branch_spec.is_dynamic else "static",
        "layout_key": branch_spec.layout_key,
        "layout_label": branch_spec.layout_label,
        "agent_arrangement": branch_spec.start_distribution_mode,
        "target_arrangement": branch_spec.goal_distribution_mode,
        "strict_dispersed_8_neighbor_clearance": _yes_no(
            branch_spec.strict_dispersed_8_neighbor_clearance
        ),
        "broad_agent_arrangement": _broad_arrangement(branch_spec.start_distribution_mode),
        "broad_target_arrangement": _broad_arrangement(branch_spec.goal_distribution_mode),
        "map_obstacle_type": branch_spec.map_obstacle_type,
        "documented_target_type": branch_spec.target_type_documented,
        "active_target_type": branch_spec.target_type_active,
        "compact_clustering": _yes_no(branch_spec.compact_clustering),
        "clustering_style_name": branch_spec.clustering_style_name,
        "clustered_start_goal_min_distance_cells": branch_spec.clustered_start_goal_min_distance,
        "require_individual_reachability": _yes_no(branch_spec.require_individual_reachability),
        "zone_relationship_mode": branch_spec.zone_relationship_mode,
        "spawnable_cell_mode": branch_spec.spawnable_cell_mode,
        "map_rows": dynamic_metadata.get("static_rows") or branch_spec.base_rows,
        "map_columns": dynamic_metadata.get("static_cols") or branch_spec.base_cols,
        "map_identifier": dynamic_metadata.get("map_identifier"),
        "source_image_path": branch_spec.image_path,
        "image_threshold": branch_spec.image_threshold,
        "image_resize_longest_side": branch_spec.image_resize_longest_side,
        "static_obstacle_density": branch_spec.static_obstacle_density,
        "dynamic_target_static_obstacle_density": branch_spec.dynamic_target_static_obstacle_density,
        "dynamic_obstacle_density": branch_spec.dynamic_target_dynamic_obstacle_density,
        "dynamic_schedule_length": dynamic_metadata.get("dynamic_loop_length") or branch_spec.dynamic_loop_sequence_length,
        "dynamic_schedule_seed": dynamic_metadata.get("schedule_seed"),
        "dynamic_generation_mode": dynamic_metadata.get("generation_mode") or branch_spec.dynamic_generation_cell_mode,
        "dynamic_group_stay_durations": _json_text(branch_spec.dynamic_group_stay_durations),
        "seed_base": branch_spec.seed_base,
        "solver_name": branch_spec.solver_name,
        "enhanced_cbs_enabled": _yes_no(branch_spec.enhanced_cbs_enabled),
        "solver_suboptimality_factor": branch_spec.solver_suboptimality_factor,
        "true_static_shortest_path_distance": _yes_no(branch_spec.true_static_shortest_path_distance),
        "tight_time_horizon": _yes_no(branch_spec.tight_time_horizon),
        "agent_cohesion_enabled": _yes_no(branch_spec.agent_cohesion_enabled),
        "cohesion_factor": branch_spec.cohesion_factor,
        "runtime_limit_seconds": branch_spec.runtime_limit_seconds,
        "capacity_candidate_minimum": 1,
        "capacity_candidate_maximum": branch_spec.capacity_agent_upper_bound,
        "capacity_attempts_per_agent_number": branch_spec.capacity_attempts_per_agent_number,
        "capacity_successful_runs_required": branch_spec.capacity_successful_runs_required,
        "capacity_pass_criterion": branch_spec.capacity_pass_criterion,
        "capacity_binary_search_max_downward_moves": branch_spec.capacity_binary_search_max_downward_moves,
        "setup_generation_attempt_cap_per_solver_attempt": branch_spec.setup_generation_attempt_cap_per_solver_attempt,
        "paired_scenarios_use_same_initial_conditions": "yes",
        "path_metric_definition": "total path length over all agents for solved runs only",
        "time_metric_definition": "time computation halted in seconds; includes the runtime-limit value for unfinished counted runs",
        "conflict_metric_definition": "number of conflicts detected when computation halted",
        "capacity_definition": "highest tested agent number accepted by the configured capacity-search protocol",
        "notes": branch_spec.notes,
    }


def _capacity_searches(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    capacity_search = payload.get("capacity_search")
    if not isinstance(capacity_search, dict):
        return {"classical": {}, "cyclic": {}}
    return {
        "classical": dict(capacity_search.get("classical") or {}),
        "cyclic": dict(capacity_search.get("cyclic") or {}),
    }


def _effective_capacity_criterion(configured: str, mapping_name: str) -> str:
    if configured == "temp_pairwise":
        return "temp_classical" if mapping_name == "classical" else "temp_cyclic"
    if configured == "temp_cyclic":
        return "solver_success" if mapping_name == "classical" else "temp_cyclic"
    return "solver_success"


def _capacity_summary_rows(
    metadata: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mapping_name, search in _capacity_searches(payload).items():
        tests = list(search.get("tested_agent_numbers") or [])
        passed = [int(test.get("agent_number")) for test in tests if test.get("passed")]
        failed = [int(test.get("agent_number")) for test in tests if not test.get("passed")]
        primary_attempt_count = sum(len(test.get("attempts") or []) for test in tests)
        comparison_attempt_count = sum(len(test.get("comparison_attempts") or []) for test in tests)
        best_agent_number = _as_int(search.get("best_agent_number")) or 0
        rows.append(
            {
                "schema_version": METRICS_DATA_SCHEMA_VERSION,
                "map_config": metadata["map_config"],
                "map_category": metadata["map_category"],
                "environment_type": metadata["environment_type"],
                "map_family": metadata["map_family"],
                "layout_key": metadata["layout_key"],
                "mapping_name": mapping_name,
                "protocol_capacity_agent_number": best_agent_number,
                "capacity_found": _yes_no(best_agent_number > 0),
                "capacity_is_protocol_based": "yes",
                "capacity_pass_criterion": (
                    tests[0].get("pass_criterion")
                    if tests
                    else _effective_capacity_criterion(str(metadata["capacity_pass_criterion"]), mapping_name)
                ),
                "candidate_minimum": metadata["capacity_candidate_minimum"],
                "candidate_maximum": metadata["capacity_candidate_maximum"],
                "tested_agent_number_count": len(tests),
                "tested_agent_numbers": _json_text([test.get("agent_number") for test in tests]),
                "passed_test_count": len(passed),
                "passed_agent_numbers": _json_text(passed),
                "failed_test_count": len(failed),
                "failed_agent_numbers": _json_text(failed),
                "primary_solver_attempt_count": primary_attempt_count,
                "paired_comparison_attempt_count": comparison_attempt_count,
                "invalid_generation_count": sum(int(test.get("invalid_attempt_count") or 0) for test in tests),
                "retained_successful_capacity_run_count": len(search.get("best_successful_attempts") or []),
            }
        )
    return rows


def _capacity_comparison_row(
    metadata: dict[str, Any],
    capacity_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    by_mapping = {row["mapping_name"]: row for row in capacity_rows}
    classical = _as_float(by_mapping.get("classical", {}).get("protocol_capacity_agent_number"))
    cyclic = _as_float(by_mapping.get("cyclic", {}).get("protocol_capacity_agent_number"))
    if classical is None or cyclic is None:
        larger = "unavailable"
    elif abs(classical - cyclic) <= 1e-12:
        larger = "same"
    else:
        larger = "cyclic" if cyclic > classical else "classical"
    return {
        "schema_version": METRICS_DATA_SCHEMA_VERSION,
        "map_config": metadata["map_config"],
        "map_category": metadata["map_category"],
        "environment_type": metadata["environment_type"],
        "map_family": metadata["map_family"],
        "layout_key": metadata["layout_key"],
        "classical_protocol_capacity_agent_number": _as_int(classical),
        "cyclic_protocol_capacity_agent_number": _as_int(cyclic),
        "cyclic_minus_classical_capacity": (
            int(cyclic - classical) if cyclic is not None and classical is not None else None
        ),
        "cyclic_capacity_percent_change_from_classical": _percent_change(cyclic, classical),
        "cyclic_to_classical_capacity_ratio": _ratio(cyclic, classical),
        "larger_protocol_capacity": larger,
        "capacity_interpretation_note": "Protocol-based tested capacity, not a theoretical maximum.",
    }


def _capacity_search_test_rows(
    metadata: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mapping_name, search in _capacity_searches(payload).items():
        trace_by_step = {
            int(item.get("step")): item
            for item in (search.get("search_trace") or [])
            if item.get("step") is not None
        }
        for test_order, test in enumerate(search.get("tested_agent_numbers") or [], start=1):
            step = int(test.get("search_step_index") or test_order)
            trace = trace_by_step.get(step, {})
            attempts = list(test.get("attempts") or [])
            comparison_attempts = list(test.get("comparison_attempts") or [])
            rows.append(
                {
                    "schema_version": METRICS_DATA_SCHEMA_VERSION,
                    "map_config": metadata["map_config"],
                    "mapping_capacity_search": mapping_name,
                    "test_order": test_order,
                    "search_step_index": step,
                    "depth_from_root": trace.get("depth_from_root"),
                    "low_before_test": trace.get("low_before"),
                    "high_before_test": trace.get("high_before"),
                    "tested_agent_number": test.get("agent_number"),
                    "pass_criterion": test.get("pass_criterion"),
                    "passed": _yes_no(test.get("passed")),
                    "failure_reason": test.get("failure_reason"),
                    "successful_qualifying_attempt_count": test.get("success_count"),
                    "counted_primary_attempt_count": test.get("counted_attempt_count"),
                    "primary_attempt_count_saved": len(attempts),
                    "paired_comparison_attempt_count_saved": len(comparison_attempts),
                    "invalid_generation_count": test.get("invalid_attempt_count"),
                    "generation_cap_exhausted": _yes_no(test.get("invalid_generation_cap_exhausted")),
                    "primary_result_categories": _json_text([
                        _record_from_attempt(attempt).get("result_category") for attempt in attempts
                    ]),
                    "comparison_result_categories": _json_text([
                        _record_from_attempt(attempt).get("result_category") for attempt in comparison_attempts
                    ]),
                    "trace_events": _json_text(test.get("trace") or []),
                }
            )
    return rows


def _base_run_record_fields(
    metadata: dict[str, Any],
    attempt: dict[str, Any],
) -> dict[str, Any]:
    record = _record_from_attempt(attempt)
    run_configuration = attempt.get("run_configuration") or {}
    return {
        "schema_version": METRICS_DATA_SCHEMA_VERSION,
        "map_config": metadata["map_config"],
        "map_category": metadata["map_category"],
        "environment_type": metadata["environment_type"],
        "map_family": metadata["map_family"],
        "layout_key": metadata["layout_key"],
        "mapping_name": record.get("mapping_name"),
        "mapping_record_id": _record_id(record),
        "run_config_id": record.get("run_config_id") or run_configuration.get("run_config_id"),
        "agent_number": record.get("agent_number") or run_configuration.get("agent_number"),
        "solver_name": record.get("solver_name"),
        "enhanced_cbs_enabled": record.get("enhanced_cbs_enabled"),
        "solver_suboptimality_factor": record.get("solver_suboptimality_factor"),
        "solver_status": record.get("solver_status"),
        "result_category": record.get("result_category"),
        "counted_run": record.get("counted_run"),
        "solved_run": record.get("solved_run"),
        "time_computation_halted_seconds": record.get("time_computation_halted_seconds"),
        "num_conflicts_detected_at_halt": record.get("num_conflicts_detected_at_halt"),
        "total_path_length": record.get("total_path_length") if record.get("solved_run") else None,
        "num_high_level_nodes_expanded": record.get("num_high_level_nodes_expanded"),
        "runtime_limit_seconds": record.get("runtime_limit_seconds") or metadata["runtime_limit_seconds"],
        "reached_runtime_limit": _yes_no(
            str(record.get("result_category")) == "unfinished"
            or (
                _as_float(record.get("time_computation_halted_seconds")) is not None
                and _as_float(record.get("runtime_limit_seconds") or metadata["runtime_limit_seconds"]) is not None
                and _as_float(record.get("time_computation_halted_seconds"))
                >= _as_float(record.get("runtime_limit_seconds") or metadata["runtime_limit_seconds"]) - 1e-6
                and not bool(record.get("solved_run"))
            )
        ),
        "comparison_case": record.get("comparison_case"),
        "paired_run": record.get("paired_run"),
        "map_identifier": record.get("map_identifier") or run_configuration.get("map_identifier"),
        "map_seed": record.get("map_seed") or run_configuration.get("map_seed"),
        "assignment_seed": record.get("assignment_seed") or run_configuration.get("assignment_seed"),
        "dynamic_schedule_seed": record.get("dynamic_schedule_seed") or run_configuration.get("dynamic_schedule_seed"),
        "generation_attempts_used": attempt.get("generation_attempts_used"),
        "initial_condition_spec": record.get("initial_condition_spec") or _json_text(run_configuration.get("starts_and_goals") or []),
    }


def _capacity_search_run_rows(
    metadata: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mapping_name, search in _capacity_searches(payload).items():
        for test_order, test in enumerate(search.get("tested_agent_numbers") or [], start=1):
            successful_ids = {
                _record_id(_record_from_attempt(attempt))
                for attempt in (test.get("successful_attempts") or [])
            }
            for role, attempts in (
                ("primary", test.get("attempts") or []),
                ("paired_comparison", test.get("comparison_attempts") or []),
            ):
                for attempt_order, attempt in enumerate(attempts, start=1):
                    base = _base_run_record_fields(metadata, attempt)
                    base.update(
                        {
                            "capacity_search_mapping": mapping_name,
                            "capacity_search_role": role,
                            "test_order": test_order,
                            "tested_agent_number": test.get("agent_number"),
                            "pass_criterion": test.get("pass_criterion"),
                            "tested_agent_number_passed": _yes_no(test.get("passed")),
                            "test_failure_reason": test.get("failure_reason"),
                            "attempt_order_within_test_and_role": attempt_order,
                            "qualifying_capacity_success": _yes_no(
                                role == "primary" and _record_id(_record_from_attempt(attempt)) in successful_ids
                            ),
                        }
                    )
                    rows.append(base)
    return rows


def _capacity_point_groups(payload: dict[str, Any]) -> list[tuple[str, str, str, list[dict[str, Any]]]]:
    searches = _capacity_searches(payload)
    comparative = payload.get("comparative_runs") or {}
    return [
        (
            "temp_classical_capacity",
            "classical",
            "capacity_origin_mapping",
            list(searches["classical"].get("best_successful_attempts") or []),
        ),
        (
            "temp_classical_capacity",
            "cyclic",
            "paired_comparative_mapping",
            list(comparative.get("cyclic_at_temp_classical_capacity") or []),
        ),
        (
            "temp_cyclic_capacity",
            "cyclic",
            "capacity_origin_mapping",
            list(searches["cyclic"].get("best_successful_attempts") or []),
        ),
        (
            "temp_cyclic_capacity",
            "classical",
            "paired_comparative_mapping",
            list(comparative.get("classical_at_temp_cyclic_capacity") or []),
        ),
    ]


def _capacity_agent_numbers(payload: dict[str, Any]) -> dict[str, int]:
    searches = _capacity_searches(payload)
    return {
        "temp_classical_capacity": int(searches["classical"].get("best_agent_number") or 0),
        "temp_cyclic_capacity": int(searches["cyclic"].get("best_agent_number") or 0),
    }


def _capacity_point_run_rows(
    metadata: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    capacities = _capacity_agent_numbers(payload)
    for capacity_label, expected_mapping, role, attempts in _capacity_point_groups(payload):
        for run_order, attempt in enumerate(attempts, start=1):
            base = _base_run_record_fields(metadata, attempt)
            base.update(
                {
                    "capacity_label": capacity_label,
                    "capacity_origin_mapping": "classical" if capacity_label == "temp_classical_capacity" else "cyclic",
                    "capacity_agent_number": capacities[capacity_label],
                    "comparison_role": role,
                    "expected_mapping_name": expected_mapping,
                    "run_order_within_group": run_order,
                }
            )
            rows.append(base)
    return rows


def _capacity_point_summary_rows(
    metadata: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    capacities = _capacity_agent_numbers(payload)
    for capacity_label, expected_mapping, role, attempts in _capacity_point_groups(payload):
        records = [_record_from_attempt(attempt) for attempt in attempts]
        time_stats = _metric_stats(_as_float(record.get("time_computation_halted_seconds")) for record in records)
        conflict_stats = _metric_stats(_as_float(record.get("num_conflicts_detected_at_halt")) for record in records)
        path_stats = _metric_stats(
            _as_float(record.get("total_path_length")) if record.get("solved_run") else None
            for record in records
        )
        result_categories = [str(record.get("result_category") or "unknown") for record in records]
        rows.append(
            {
                "schema_version": METRICS_DATA_SCHEMA_VERSION,
                "map_config": metadata["map_config"],
                "map_category": metadata["map_category"],
                "environment_type": metadata["environment_type"],
                "map_family": metadata["map_family"],
                "layout_key": metadata["layout_key"],
                "capacity_label": capacity_label,
                "capacity_origin_mapping": "classical" if capacity_label == "temp_classical_capacity" else "cyclic",
                "capacity_agent_number": capacities[capacity_label],
                "mapping_name": expected_mapping,
                "comparison_role": role,
                "run_record_count": len(records),
                "counted_run_count": sum(bool(record.get("counted_run")) for record in records),
                "successful_run_count": sum(str(record.get("result_category")) == "successful" for record in records),
                "unfinished_run_count": sum(str(record.get("result_category")) == "unfinished" for record in records),
                "solved_run_count": sum(bool(record.get("solved_run")) for record in records),
                "all_runs_solved": _yes_no(bool(records) and all(bool(record.get("solved_run")) for record in records)),
                "contains_unfinished_run": _yes_no(any(str(record.get("result_category")) == "unfinished" for record in records)),
                "result_categories": _json_text(result_categories),
                "time_value_count": time_stats["value_count"],
                "time_mean_seconds": time_stats["mean"],
                "time_median_seconds": time_stats["median"],
                "time_minimum_seconds": time_stats["minimum"],
                "time_maximum_seconds": time_stats["maximum"],
                "time_population_standard_deviation_seconds": time_stats["population_standard_deviation"],
                "conflicts_value_count": conflict_stats["value_count"],
                "conflicts_mean": conflict_stats["mean"],
                "conflicts_median": conflict_stats["median"],
                "conflicts_minimum": conflict_stats["minimum"],
                "conflicts_maximum": conflict_stats["maximum"],
                "conflicts_population_standard_deviation": conflict_stats["population_standard_deviation"],
                "path_value_count_solved_runs_only": path_stats["value_count"],
                "total_path_length_mean": path_stats["mean"],
                "total_path_length_median": path_stats["median"],
                "total_path_length_minimum": path_stats["minimum"],
                "total_path_length_maximum": path_stats["maximum"],
                "total_path_length_population_standard_deviation": path_stats["population_standard_deviation"],
            }
        )
    return rows


def _attempts_by_run_config(attempts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_run_config_id(attempt): attempt for attempt in attempts if _run_config_id(attempt)}


def _paired_comparison_rows(
    metadata: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    searches = _capacity_searches(payload)
    comparative = payload.get("comparative_runs") or {}
    capacities = _capacity_agent_numbers(payload)
    contexts = [
        (
            "temp_classical_capacity",
            list(searches["classical"].get("best_successful_attempts") or []),
            list(comparative.get("cyclic_at_temp_classical_capacity") or []),
        ),
        (
            "temp_cyclic_capacity",
            list(comparative.get("classical_at_temp_cyclic_capacity") or []),
            list(searches["cyclic"].get("best_successful_attempts") or []),
        ),
    ]
    rows: list[dict[str, Any]] = []
    for capacity_label, classical_attempts, cyclic_attempts in contexts:
        classical_by_id = _attempts_by_run_config(classical_attempts)
        cyclic_by_id = _attempts_by_run_config(cyclic_attempts)
        all_ids = list(dict.fromkeys([*classical_by_id.keys(), *cyclic_by_id.keys()]))
        for pair_order, run_config_id in enumerate(all_ids, start=1):
            classical = _record_from_attempt(classical_by_id.get(run_config_id, {}))
            cyclic = _record_from_attempt(cyclic_by_id.get(run_config_id, {}))
            classical_time = _as_float(classical.get("time_computation_halted_seconds"))
            cyclic_time = _as_float(cyclic.get("time_computation_halted_seconds"))
            classical_conflicts = _as_float(classical.get("num_conflicts_detected_at_halt"))
            cyclic_conflicts = _as_float(cyclic.get("num_conflicts_detected_at_halt"))
            classical_path = _as_float(classical.get("total_path_length")) if classical.get("solved_run") else None
            cyclic_path = _as_float(cyclic.get("total_path_length")) if cyclic.get("solved_run") else None
            rows.append(
                {
                    "schema_version": METRICS_DATA_SCHEMA_VERSION,
                    "map_config": metadata["map_config"],
                    "map_category": metadata["map_category"],
                    "environment_type": metadata["environment_type"],
                    "map_family": metadata["map_family"],
                    "layout_key": metadata["layout_key"],
                    "capacity_label": capacity_label,
                    "capacity_origin_mapping": "classical" if capacity_label == "temp_classical_capacity" else "cyclic",
                    "capacity_agent_number": capacities[capacity_label],
                    "pair_order": pair_order,
                    "run_config_id": run_config_id,
                    "same_initial_conditions": "yes" if classical and cyclic else "incomplete_pair",
                    "classical_solver_status": classical.get("solver_status"),
                    "classical_result_category": classical.get("result_category"),
                    "classical_solved_run": classical.get("solved_run"),
                    "classical_time_seconds": classical_time,
                    "classical_conflicts": classical_conflicts,
                    "classical_total_path_length": classical_path,
                    "cyclic_solver_status": cyclic.get("solver_status"),
                    "cyclic_result_category": cyclic.get("result_category"),
                    "cyclic_solved_run": cyclic.get("solved_run"),
                    "cyclic_time_seconds": cyclic_time,
                    "cyclic_conflicts": cyclic_conflicts,
                    "cyclic_total_path_length": cyclic_path,
                    "both_mappings_solved": _yes_no(bool(classical.get("solved_run")) and bool(cyclic.get("solved_run"))),
                    "cyclic_minus_classical_time_seconds": _difference(cyclic_time, classical_time),
                    "cyclic_time_percent_change_from_classical": _percent_change(cyclic_time, classical_time),
                    "lower_time_mapping": _lower_is_better(classical_time, cyclic_time),
                    "cyclic_minus_classical_conflicts": _difference(cyclic_conflicts, classical_conflicts),
                    "cyclic_conflicts_percent_change_from_classical": _percent_change(cyclic_conflicts, classical_conflicts),
                    "lower_conflicts_mapping": _lower_is_better(classical_conflicts, cyclic_conflicts),
                    "cyclic_minus_classical_total_path_length": _difference(cyclic_path, classical_path),
                    "cyclic_total_path_length_percent_change_from_classical": _percent_change(cyclic_path, classical_path),
                    "path_tradeoff_direction": _path_tradeoff(classical_path, cyclic_path),
                    "map_seed": classical.get("map_seed") or cyclic.get("map_seed"),
                    "assignment_seed": classical.get("assignment_seed") or cyclic.get("assignment_seed"),
                    "dynamic_schedule_seed": classical.get("dynamic_schedule_seed") or cyclic.get("dynamic_schedule_seed"),
                }
            )
    return rows


def _results_ready_rows(
    metadata: dict[str, Any],
    capacity_comparison: dict[str, Any],
    summary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_context: dict[str, dict[str, dict[str, Any]]] = {}
    for row in summary_rows:
        by_context.setdefault(row["capacity_label"], {})[row["mapping_name"]] = row

    rows: list[dict[str, Any]] = []
    for capacity_label in ("temp_classical_capacity", "temp_cyclic_capacity"):
        context = by_context.get(capacity_label, {})
        classical = context.get("classical", {})
        cyclic = context.get("cyclic", {})
        classical_time = _as_float(classical.get("time_mean_seconds"))
        cyclic_time = _as_float(cyclic.get("time_mean_seconds"))
        classical_conflicts = _as_float(classical.get("conflicts_mean"))
        cyclic_conflicts = _as_float(cyclic.get("conflicts_mean"))
        classical_path = _as_float(classical.get("total_path_length_mean"))
        cyclic_path = _as_float(cyclic.get("total_path_length_mean"))
        rows.append(
            {
                "schema_version": METRICS_DATA_SCHEMA_VERSION,
                "map_config": metadata["map_config"],
                "display_name": metadata["display_name"],
                "map_category": metadata["map_category"],
                "map_family": metadata["map_family"],
                "study_context": metadata["study_context"],
                "environment_type": metadata["environment_type"],
                "agent_arrangement": metadata["agent_arrangement"],
                "target_arrangement": metadata["target_arrangement"],
                "strict_dispersed_8_neighbor_clearance": metadata[
                    "strict_dispersed_8_neighbor_clearance"
                ],
                "broad_agent_arrangement": metadata["broad_agent_arrangement"],
                "broad_target_arrangement": metadata["broad_target_arrangement"],
                "capacity_label": capacity_label,
                "capacity_origin_mapping": "classical" if capacity_label == "temp_classical_capacity" else "cyclic",
                "capacity_agent_number": classical.get("capacity_agent_number") or cyclic.get("capacity_agent_number"),
                "classical_protocol_capacity_agent_number": capacity_comparison["classical_protocol_capacity_agent_number"],
                "cyclic_protocol_capacity_agent_number": capacity_comparison["cyclic_protocol_capacity_agent_number"],
                "cyclic_minus_classical_capacity": capacity_comparison["cyclic_minus_classical_capacity"],
                "cyclic_capacity_percent_change_from_classical": capacity_comparison["cyclic_capacity_percent_change_from_classical"],
                "classical_run_record_count": classical.get("run_record_count", 0),
                "classical_successful_run_count": classical.get("successful_run_count", 0),
                "classical_unfinished_run_count": classical.get("unfinished_run_count", 0),
                "classical_path_value_count_solved_runs_only": classical.get("path_value_count_solved_runs_only", 0),
                "cyclic_run_record_count": cyclic.get("run_record_count", 0),
                "cyclic_successful_run_count": cyclic.get("successful_run_count", 0),
                "cyclic_unfinished_run_count": cyclic.get("unfinished_run_count", 0),
                "cyclic_path_value_count_solved_runs_only": cyclic.get("path_value_count_solved_runs_only", 0),
                "classical_time_mean_seconds": classical_time,
                "cyclic_time_mean_seconds": cyclic_time,
                "cyclic_minus_classical_time_seconds": _difference(cyclic_time, classical_time),
                "cyclic_time_percent_change_from_classical": _percent_change(cyclic_time, classical_time),
                "lower_time_mapping": _lower_is_better(classical_time, cyclic_time),
                "classical_conflicts_mean": classical_conflicts,
                "cyclic_conflicts_mean": cyclic_conflicts,
                "cyclic_minus_classical_conflicts": _difference(cyclic_conflicts, classical_conflicts),
                "cyclic_conflicts_percent_change_from_classical": _percent_change(cyclic_conflicts, classical_conflicts),
                "lower_conflicts_mapping": _lower_is_better(classical_conflicts, cyclic_conflicts),
                "classical_total_path_length_mean": classical_path,
                "cyclic_total_path_length_mean": cyclic_path,
                "cyclic_minus_classical_total_path_length": _difference(cyclic_path, classical_path),
                "cyclic_total_path_length_percent_change_from_classical": _percent_change(cyclic_path, classical_path),
                "path_tradeoff_direction": _path_tradeoff(classical_path, cyclic_path),
                "both_mapping_groups_have_records": _yes_no(bool(classical.get("run_record_count")) and bool(cyclic.get("run_record_count"))),
                "both_mapping_groups_all_runs_solved": _yes_no(
                    classical.get("all_runs_solved") == "yes" and cyclic.get("all_runs_solved") == "yes"
                ),
                "runtime_limit_seconds": metadata["runtime_limit_seconds"],
                "solver_name": metadata["solver_name"],
                "solver_suboptimality_factor": metadata["solver_suboptimality_factor"],
            }
        )
    return rows


def _reader_guide(metadata: dict[str, Any], file_names: list[str]) -> str:
    return f"""MAIN EXPERIMENT METRICS DATA — READER GUIDE

Map configuration: {metadata['map_config']}
Display name: {metadata['display_name']}
Schema version: {METRICS_DATA_SCHEMA_VERSION}

PURPOSE
This folder is a Results-ready data package for the main experiment. It contains the numerical evidence, protocol context, run outcomes, and paired comparisons needed to write the corresponding Results and Discussion subsection. It does not contain reference-comparison data or plot images.

RECOMMENDED READING ORDER
1. configuration_metadata.csv — identify the map, environment, arrangements, solver, runtime limit, and capacity protocol.
2. capacity_comparison.csv — report classical and cyclic protocol capacities and their difference.
3. results_ready_comparisons.csv — use this as the primary compact table for prose and manuscript tables.
4. capacity_point_summary.csv — verify sample counts, completion behavior, averages, ranges, and variability.
5. paired_run_comparisons.csv — inspect matched classical/cyclic outcomes on the same initial conditions.
6. capacity_search_tests.csv — explain how each protocol capacity was reached.
7. capacity_point_run_records.csv and capacity_search_run_records.csv — audit the individual observations.
8. metrics_package.json — complete machine-readable package containing all tables above.

INTERPRETATION RULES
- Capacities are protocol-based highest accepted tested agent numbers, not theoretical maxima.
- A capacity value of 0 means the search found no accepted tested value under the configured protocol.
- Blank metric cells mean unavailable or not applicable; they must not be interpreted as zero.
- Time and conflict summaries include counted successful and unfinished runs when present.
- Total path length is available only for solved runs. Always report its valid value count.
- Positive percentage change means cyclic is larger than classical; negative means cyclic is smaller.
- Classical and cyclic records sharing a run_config_id used the same generated initial conditions.
- Do not describe a one-record mean as evidence of low variability; consult run_record_count and standard-deviation columns.

FILES WRITTEN
{chr(10).join(f'- {name}' for name in file_names)}
"""


def _data_dictionary_rows() -> list[dict[str, Any]]:
    entries = [
        ("all", "schema_version", "Version of the metrics-data output schema.", "number", "Always populated."),
        ("all", "map_config", "Exact main-experiment map-configuration identifier.", "text", "Always populated."),
        ("configuration_metadata.csv", "map_category", "Static/dynamic map category before arrangement suffixes.", "text", "Always populated."),
        ("configuration_metadata.csv", "map_family", "Artificial, port, campus_area_1, or campus_area_2 family.", "text", "Always populated."),
        ("configuration_metadata.csv", "study_context", "Traditional MAPF or campus crowd-simulation grouping.", "text", "Always populated."),
        ("configuration_metadata.csv", "environment_type", "Static or dynamic environment.", "text", "Always populated."),
        ("configuration_metadata.csv", "agent_arrangement", "Exact agent/start arrangement mode.", "text", "Always populated."),
        ("configuration_metadata.csv", "target_arrangement", "Exact target/goal arrangement mode.", "text", "Always populated."),
        ("configuration_metadata.csv and results_ready_comparisons.csv", "strict_dispersed_8_neighbor_clearance", "Whether dispersed starts and targets must strictly maintain 8-neighbor clearance instead of using adjacent unique cells as a shortage fallback.", "yes/no", "Always populated."),
        ("configuration_metadata.csv", "broad_agent_arrangement", "Dispersed or compact cross-attribute class.", "text", "Always populated."),
        ("configuration_metadata.csv", "broad_target_arrangement", "Dispersed or compact cross-attribute class.", "text", "Always populated."),
        ("configuration_metadata.csv", "runtime_limit_seconds", "Per-mapping solver runtime limit.", "seconds", "Always populated."),
        ("configuration_metadata.csv", "capacity_pass_criterion", "Configured rule for accepting a tested agent number.", "text", "Always populated."),
        ("capacity_comparison.csv", "classical_protocol_capacity_agent_number", "Highest tested agent number accepted for classical capacity search.", "agents", "0 means no accepted tested value."),
        ("capacity_comparison.csv", "cyclic_protocol_capacity_agent_number", "Highest tested agent number accepted for cyclic capacity search.", "agents", "0 means no accepted tested value."),
        ("capacity_comparison.csv", "cyclic_minus_classical_capacity", "Cyclic capacity minus classical capacity.", "agents", "Blank only if comparison unavailable."),
        ("capacity_comparison.csv", "cyclic_capacity_percent_change_from_classical", "Capacity percentage change, using classical as denominator.", "percent", "Blank when classical capacity is zero/unavailable."),
        ("capacity_search_tests.csv", "tested_agent_number", "Agent number evaluated at one binary-search-style step.", "agents", "Always populated per row."),
        ("capacity_search_tests.csv", "passed", "Whether the tested value satisfied the configured criterion.", "yes/no", "Always populated."),
        ("capacity_search_tests.csv", "failure_reason", "Program classification for a failed test.", "text", "Blank for passed tests."),
        ("capacity_search_run_records.csv", "qualifying_capacity_success", "Whether the primary run was retained as a qualifying success for that tested value.", "yes/no", "Always populated."),
        ("capacity_point_run_records.csv", "capacity_label", "Whether results are evaluated at classical-origin or cyclic-origin protocol capacity.", "text", "Always populated."),
        ("capacity_point_run_records.csv", "capacity_agent_number", "Actual agent number represented by the capacity context.", "agents", "0 means no accepted capacity."),
        ("capacity_point_run_records.csv", "result_category", "Successful, unfinished, or another program result classification.", "text", "Always populated when a run exists."),
        ("capacity_point_run_records.csv", "time_computation_halted_seconds", "Elapsed computation time when the solver halted.", "seconds", "Blank only if the record itself lacks time."),
        ("capacity_point_run_records.csv", "num_conflicts_detected_at_halt", "Conflicts detected when computation halted.", "conflicts", "Blank when unavailable; never assume zero."),
        ("capacity_point_run_records.csv", "total_path_length", "Sum of all agent path lengths.", "grid-step path length", "Blank for unfinished/unsolved runs."),
        ("capacity_point_summary.csv", "run_record_count", "Number of records summarized in the mapping/capacity group.", "runs", "Zero means no records were available."),
        ("capacity_point_summary.csv", "successful_run_count", "Number of successful records in the group.", "runs", "Zero is a tested count."),
        ("capacity_point_summary.csv", "unfinished_run_count", "Number of runtime-limited unfinished records in the group.", "runs", "Zero is a tested count."),
        ("capacity_point_summary.csv", "path_value_count_solved_runs_only", "Number of solved runs contributing to path statistics.", "runs", "Zero means no valid path values."),
        ("capacity_point_summary.csv", "time_mean_seconds", "Arithmetic mean halted time across available group records.", "seconds", "Blank when no time values exist."),
        ("capacity_point_summary.csv", "conflicts_mean", "Arithmetic mean conflicts at halt across available group records.", "conflicts", "Blank when no conflict values exist."),
        ("capacity_point_summary.csv", "total_path_length_mean", "Arithmetic mean total path length across solved records only.", "grid-step path length", "Blank when no solved path values exist."),
        ("paired_run_comparisons.csv", "same_initial_conditions", "Whether both mappings were matched by run_config_id.", "yes/incomplete_pair", "Incomplete pair means one side is missing."),
        ("paired_run_comparisons.csv", "cyclic_time_percent_change_from_classical", "Paired cyclic time percentage change relative to classical.", "percent", "Blank when classical time is zero/unavailable."),
        ("paired_run_comparisons.csv", "cyclic_conflicts_percent_change_from_classical", "Paired cyclic conflicts percentage change relative to classical.", "percent", "Blank when classical conflicts are zero/unavailable."),
        ("paired_run_comparisons.csv", "cyclic_total_path_length_percent_change_from_classical", "Paired cyclic path-length percentage change relative to classical.", "percent", "Blank unless both runs solved and classical path is nonzero."),
        ("results_ready_comparisons.csv", "lower_time_mapping", "Mapping with lower mean halted time in the capacity context.", "classical/cyclic/same/unavailable", "Unavailable when either mean is missing."),
        ("results_ready_comparisons.csv", "lower_conflicts_mapping", "Mapping with lower mean conflicts in the capacity context.", "classical/cyclic/same/unavailable", "Unavailable when either mean is missing."),
        ("results_ready_comparisons.csv", "path_tradeoff_direction", "Whether cyclic mean total path length is longer, shorter, same, or unavailable.", "text", "Unavailable when either path mean is missing."),
    ]
    return [
        {
            "file_name": file_name,
            "field_name": field_name,
            "definition": definition,
            "unit_or_type": unit,
            "missing_value_interpretation": missing,
        }
        for file_name, field_name, definition, unit, missing in entries
    ]



def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    write_csv(path, rows)


def _package_payload(
    metadata: dict[str, Any],
    capacity_summary: list[dict[str, Any]],
    capacity_comparison: dict[str, Any],
    capacity_search_tests: list[dict[str, Any]],
    capacity_search_runs: list[dict[str, Any]],
    capacity_point_runs: list[dict[str, Any]],
    capacity_point_summary: list[dict[str, Any]],
    paired_comparisons: list[dict[str, Any]],
    results_ready: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": METRICS_DATA_SCHEMA_VERSION,
        "generated_at_utc": _utc_timestamp(),
        "scope": "main_experiment",
        "configuration_metadata": metadata,
        "capacity_summary": capacity_summary,
        "capacity_comparison": capacity_comparison,
        "capacity_search_tests": capacity_search_tests,
        "capacity_search_run_records": capacity_search_runs,
        "capacity_point_run_records": capacity_point_runs,
        "capacity_point_summary": capacity_point_summary,
        "paired_run_comparisons": paired_comparisons,
        "results_ready_comparisons": results_ready,
    }


OBSOLETE_PROJECT_LEVEL_METRICS_FILE_NAMES = (
    "dataset_manifest.json",
)


def prepare_project_level_files_root(project_level_files_root: Path) -> dict[str, Any]:
    """Write the generated project-level data dictionary without touching readme.txt."""
    project_level_files_root.mkdir(parents=True, exist_ok=True)

    removed_files: list[str] = []
    candidates = list(project_level_files_root.glob("main_experiment_*.csv"))
    candidates.extend(
        project_level_files_root / name
        for name in OBSOLETE_PROJECT_LEVEL_METRICS_FILE_NAMES
    )
    for candidate in candidates:
        if candidate.is_file():
            candidate.unlink()
            removed_files.append(str(candidate))

    data_dictionary_path = project_level_files_root / "data_dictionary.csv"
    write_csv(data_dictionary_path, _data_dictionary_rows())
    return {
        "data_dictionary_path": str(data_dictionary_path),
        "removed_obsolete_files": removed_files,
    }


def write_metrics_data_package(
    *,
    branch_spec: BranchSpec,
    payload: dict[str, Any],
    metrics_data_dir: Path,
) -> dict[str, Any]:
    config_dir = Path(metrics_data_dir)
    config_dir.mkdir(parents=True, exist_ok=True)

    metadata = _configuration_metadata(branch_spec, payload)
    capacity_summary = _capacity_summary_rows(metadata, payload)
    capacity_comparison = _capacity_comparison_row(metadata, capacity_summary)
    capacity_search_tests = _capacity_search_test_rows(metadata, payload)
    capacity_search_runs = _capacity_search_run_rows(metadata, payload)
    capacity_point_runs = _capacity_point_run_rows(metadata, payload)
    capacity_point_summary = _capacity_point_summary_rows(metadata, payload)
    paired_comparisons = _paired_comparison_rows(metadata, payload)
    results_ready = _results_ready_rows(metadata, capacity_comparison, capacity_point_summary)

    file_rows: list[tuple[str, list[dict[str, Any]]]] = [
        ("configuration_metadata.csv", [metadata]),
        ("capacity_summary.csv", capacity_summary),
        ("capacity_comparison.csv", [capacity_comparison]),
        ("capacity_search_tests.csv", capacity_search_tests),
        ("capacity_search_run_records.csv", capacity_search_runs),
        ("capacity_point_run_records.csv", capacity_point_runs),
        ("capacity_point_summary.csv", capacity_point_summary),
        ("paired_run_comparisons.csv", paired_comparisons),
        ("results_ready_comparisons.csv", results_ready),
    ]
    for file_name, rows in file_rows:
        _write_rows(config_dir / file_name, rows)

    legacy_primary_name = f"{branch_spec.data_log_file_stem}_metrics_data.csv"
    _write_rows(config_dir / legacy_primary_name, results_ready)

    package = _package_payload(
        metadata,
        capacity_summary,
        capacity_comparison,
        capacity_search_tests,
        capacity_search_runs,
        capacity_point_runs,
        capacity_point_summary,
        paired_comparisons,
        results_ready,
    )
    package_path = config_dir / "metrics_package.json"
    write_json(package_path, package)

    written_names = [
        "README.txt",
        *[file_name for file_name, _ in file_rows],
        legacy_primary_name,
        "metrics_package.json",
    ]
    (config_dir / "README.txt").write_text(
        _reader_guide(metadata, written_names),
        encoding="utf-8",
    )

    return {
        "metrics_data_dir": str(config_dir),
        "primary_results_csv_path": str(config_dir / legacy_primary_name),
        "results_ready_csv_path": str(config_dir / "results_ready_comparisons.csv"),
        "package_json_path": str(package_path),
        "reader_guide_path": str(config_dir / "README.txt"),
        "written_files": [str(config_dir / name) for name in written_names],
    }
