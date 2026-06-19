from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from dev.core.composite_elements import Vertex
from dev.experiments.ref_comparison.models import (
    RefCaseSpec,
    RefMappingRunRecord,
    RefRunConfiguration,
)
from dev.inputs.dynamic_port.map_builder import obstacle_matrix_to_composite_base_map
from dev.mapf.full.cbs_solver import solve_mapf_with_cbs
from dev.mapf.full.mapf_low_level_astar import find_path_for_agent
from dev.maps.classical_mapper import apply_classical_mapping
from dev.maps.cyclic_mapper import apply_cyclic_mapping
from dev.utils.log_symbols import AGENT_LOG_SYMBOL, TARGET_LOG_SYMBOL


COUNTED_RESULT_CATEGORIES = {"successful", "unfinished"}


def load_exact_black_white_obstacle_matrix(image_path: str | Path) -> list[list[int]]:
    """Load reference map images where pure black is obstacle and pure white is free."""
    image_path = Path(image_path)
    with Image.open(image_path) as image:
        rgb_image = image.convert("RGB")
        width, height = rgb_image.size
        pixels = rgb_image.load()
        matrix: list[list[int]] = []
        for y in range(height):
            row: list[int] = []
            for x in range(width):
                value = pixels[x, y]
                if value == (0, 0, 0):
                    row.append(1)
                elif value == (255, 255, 255):
                    row.append(0)
                else:
                    raise ValueError(
                        "Reference port maps must contain only pure black obstacle pixels "
                        f"and pure white free-space pixels. Found {value} at {(x, y)} in {image_path}."
                    )
            matrix.append(row)
    return matrix


def _composite_vertex_for_cell(row: int, col: int) -> tuple[int, int]:
    return (2 * row, 2 * col)


def _assert_free_vertex(composite_map: list[list[Any]], vertex: tuple[int, int], label: str) -> None:
    row, col = vertex
    if row < 0 or row >= len(composite_map) or col < 0 or col >= len(composite_map[row]):
        raise ValueError(f"{label} vertex {vertex} is outside the composite map.")
    if composite_map[row][col] != Vertex.FREE_SPACE:
        raise ValueError(f"{label} vertex {vertex} is not free space.")


def build_reference_maps(case_spec: RefCaseSpec) -> dict[str, Any]:
    obstacle_matrix = load_exact_black_white_obstacle_matrix(case_spec.image_path)
    rows = len(obstacle_matrix)
    cols = len(obstacle_matrix[0]) if rows else 0
    if rows != case_spec.map_size or cols != case_spec.map_size:
        raise ValueError(
            f"Expected {case_spec.map_size}x{case_spec.map_size} reference map for {case_spec.case_id}, "
            f"but got {rows}x{cols}."
        )

    base_map = obstacle_matrix_to_composite_base_map(obstacle_matrix)
    classical_map = apply_classical_mapping({"map": base_map})["map"]
    cyclic_map = apply_cyclic_mapping(
        {"map": base_map},
        remove_extra_transitions=case_spec.remove_extra_transitions,
        add_transitions_between_free_spaces=case_spec.add_transitions_between_free_spaces,
    )["map"]

    lower_left = _composite_vertex_for_cell(rows - 1, 0)
    upper_right = _composite_vertex_for_cell(0, cols - 1)
    upper_neighbor_of_start = _composite_vertex_for_cell(rows - 2, 0)
    right_neighbor_of_start = _composite_vertex_for_cell(rows - 1, 1)

    for label, vertex in (
        ("lower-left start", lower_left),
        ("upper-right target", upper_right),
        ("upper neighbor spawn", upper_neighbor_of_start),
        ("right neighbor spawn", right_neighbor_of_start),
    ):
        _assert_free_vertex(base_map, vertex, label)

    return {
        "obstacle_matrix": obstacle_matrix,
        "base_map": base_map,
        "classical_map": classical_map,
        "cyclic_map": cyclic_map,
        "remove_extra_transitions": case_spec.remove_extra_transitions,
        "add_transitions_between_free_spaces": case_spec.add_transitions_between_free_spaces,
        "rows": rows,
        "cols": cols,
        "lower_left_start": lower_left,
        "upper_right_goal": upper_right,
        "spawn_vertices": [upper_neighbor_of_start, right_neighbor_of_start],
        "map_identifier": f"reference_port_{case_spec.size_label}",
    }


def _build_agent(agent_id: int, start: tuple[int, int], goal: tuple[int, int], *, spawn_time: int = 0) -> dict[str, Any]:
    return {
        "id": agent_id,
        "label": AGENT_LOG_SYMBOL,
        "goal_label": TARGET_LOG_SYMBOL,
        "start": start,
        "goal": goal,
        "spawn_time": int(spawn_time),
    }


def build_single_agent(case_spec: RefCaseSpec, map_context: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _build_agent(
            0,
            map_context["lower_left_start"],
            map_context["upper_right_goal"],
            spawn_time=0,
        )
    ]


def _path_position(path: list[Any], time_step: int) -> Any:
    if time_step < 0:
        return None
    if time_step < len(path):
        return path[time_step]
    return None


def _spawn_cell_is_available(
    *,
    spawn_vertex: tuple[int, int],
    proposed_spawn_time: int,
    reservation_paths: list[list[Any]],
) -> bool:
    # The prompt says to spawn when the spawn cell will not be occupied in the
    # next timestep. We also require it to be unoccupied at the actual spawn
    # timestep so the release itself is well-defined.
    for path in reservation_paths:
        if _path_position(path, proposed_spawn_time) == spawn_vertex:
            return False
        if _path_position(path, proposed_spawn_time + 1) == spawn_vertex:
            return False
    return True


def build_multi_agent_spawn_sequence(case_spec: RefCaseSpec, map_context: dict[str, Any]) -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    spawn_vertices = list(map_context["spawn_vertices"])
    goal = map_context["upper_right_goal"]
    reservation_paths: list[list[Any]] = []
    search_time_limit = max(case_spec.map_size * case_spec.agent_number * 4, case_spec.agent_number * 10)

    proposed_spawn_time = 0
    next_spawn_index = 0
    while len(agents) < case_spec.agent_number and proposed_spawn_time <= search_time_limit:
        spawned_this_timestep = 0
        for spawn_vertex in spawn_vertices:
            if len(agents) >= case_spec.agent_number:
                break
            if not _spawn_cell_is_available(
                spawn_vertex=spawn_vertex,
                proposed_spawn_time=proposed_spawn_time,
                reservation_paths=reservation_paths,
            ):
                continue

            agent = _build_agent(
                next_spawn_index,
                spawn_vertex,
                goal,
                spawn_time=proposed_spawn_time,
            )
            classical_nominal_path = find_path_for_agent(
                map_context["classical_map"],
                agent["id"],
                agent["start"],
                agent["goal"],
                [],
                true_static_shortest_path_distance=case_spec.true_static_shortest_path_distance,
                tight_time_horizon=case_spec.tight_time_horizon,
                spawn_time=proposed_spawn_time,
            )
            cyclic_nominal_path = find_path_for_agent(
                map_context["cyclic_map"],
                agent["id"],
                agent["start"],
                agent["goal"],
                [],
                true_static_shortest_path_distance=case_spec.true_static_shortest_path_distance,
                tight_time_horizon=case_spec.tight_time_horizon,
                spawn_time=proposed_spawn_time,
            )
            if classical_nominal_path is None or cyclic_nominal_path is None:
                continue

            agents.append(agent)
            reservation_paths.append(classical_nominal_path)
            reservation_paths.append(cyclic_nominal_path)
            next_spawn_index += 1
            spawned_this_timestep += 1

        proposed_spawn_time += 1
        if spawned_this_timestep == 0 and proposed_spawn_time > search_time_limit:
            break

    if len(agents) < case_spec.agent_number:
        raise ValueError(
            f"Could not create the requested {case_spec.agent_number}-agent release schedule "
            f"for {case_spec.case_id} within {search_time_limit} timesteps."
        )
    return agents


def serialize_agents(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "agent_id": int(agent["id"]),
            "start": list(agent["start"]),
            "goal": list(agent["goal"]),
            "spawn_time": int(agent.get("spawn_time", 0) or 0),
        }
        for agent in agents
    ]


def build_run_configuration(
    *,
    case_spec: RefCaseSpec,
    run_index: int,
    map_identifier: str,
    agents: list[dict[str, Any]],
    notes: str,
) -> RefRunConfiguration:
    return RefRunConfiguration(
        case_id=case_spec.case_id,
        experiment_mode=case_spec.experiment_mode,
        size_label=case_spec.size_label,
        map_size=case_spec.map_size,
        agent_number=case_spec.agent_number,
        run_index=run_index,
        run_config_id=f"ref_run[{case_spec.case_id}.{run_index}]",
        map_identifier=map_identifier,
        paired_source=True,
        agents=serialize_agents(agents),
        notes=notes,
    )


def _active_positions(path: list[Any]) -> list[tuple[int, int]]:
    return [position for position in path if position is not None]


def path_movement_length(path: list[Any]) -> int:
    active_positions = _active_positions(path)
    if not active_positions:
        return 0
    return max(0, len(active_positions) - 1)


def total_path_length(paths_by_agent: dict[int, list[Any]] | None) -> int | None:
    if not paths_by_agent:
        return None
    return sum(path_movement_length(path) for path in paths_by_agent.values())


def count_turns_for_path(path: list[Any]) -> int:
    active_positions = _active_positions(path)
    if len(active_positions) < 3:
        return 0

    previous_direction: tuple[int, int] | None = None
    turns = 0
    for previous_position, current_position in zip(active_positions, active_positions[1:]):
        if previous_position == current_position:
            continue
        direction = (
            current_position[0] - previous_position[0],
            current_position[1] - previous_position[1],
        )
        if previous_direction is not None and direction != previous_direction:
            turns += 1
        previous_direction = direction
    return turns


def total_turns(paths_by_agent: dict[int, list[Any]] | None) -> int | None:
    if not paths_by_agent:
        return None
    return sum(count_turns_for_path(path) for path in paths_by_agent.values())


def categorize_solver_status(solver_status: str | None) -> tuple[str, bool, bool]:
    if solver_status == "solved":
        return "successful", True, True
    if solver_status == "bad_setup_timeout":
        return "unfinished", True, False
    if solver_status == "no_solution":
        return "unsolvable", False, False
    if solver_status and solver_status.startswith("exception"):
        return "setup_failed", False, False
    return "setup_failed", False, False


def _progress_callback_factory(logger: Any, label: str) -> Callable[[int], None]:
    def callback(elapsed_seconds: int) -> None:
        logger.log(f"    {label} progress: {max(0, elapsed_seconds):.2f}s")

    return callback


def _single_agent_solver_result(
    *,
    composite_map: list[list[Any]],
    agent: dict[str, Any],
    case_spec: RefCaseSpec,
) -> dict[str, Any]:
    path = find_path_for_agent(
        cyclic_map=composite_map,
        agent_id=agent["id"],
        start=agent["start"],
        goal=agent["goal"],
        constraints=[],
        heuristic_weight=1.0,
        true_static_shortest_path_distance=case_spec.true_static_shortest_path_distance,
        tight_time_horizon=case_spec.tight_time_horizon,
        agent_cohesion_enabled=False,
        cohesion_reference_paths=None,
        spawn_time=int(agent.get("spawn_time", 0) or 0),
    )
    if path is None:
        return {
            "status": "no_solution",
            "paths_by_agent": None,
            "num_conflicts_detected": None,
            "num_high_level_nodes_expanded": None,
            "solver_name": "A*",
            "solver_suboptimality_factor": None,
            "agent_cohesion_enabled": False,
        }
    return {
        "status": "solved",
        "paths_by_agent": {agent["id"]: path},
        "num_conflicts_detected": None,
        "num_high_level_nodes_expanded": None,
        "solver_name": "A*",
        "solver_suboptimality_factor": None,
        "agent_cohesion_enabled": False,
    }


def execute_mapping(
    *,
    case_spec: RefCaseSpec,
    composite_map: list[list[Any]],
    agents: list[dict[str, Any]],
    mapping_name: str,
    logger: Any,
) -> tuple[dict[str, Any] | None, float, str]:
    label = f"{case_spec.case_id} {mapping_name}"
    start_time = time.perf_counter()
    try:
        if case_spec.experiment_mode == "single_agent":
            solver_result = _single_agent_solver_result(
                composite_map=composite_map,
                agent=agents[0],
                case_spec=case_spec,
            )
        else:
            solver_result = solve_mapf_with_cbs(
                composite_map=composite_map,
                agents=agents,
                max_runtime_seconds=case_spec.runtime_limit_seconds,
                progress_callback=_progress_callback_factory(logger, label),
                use_ecbs=case_spec.use_ecbs,
                ecbs_suboptimality_factor=case_spec.ecbs_suboptimality,
                true_static_shortest_path_distance=case_spec.true_static_shortest_path_distance,
                tight_time_horizon=case_spec.tight_time_horizon,
                agent_cohesion_enabled=case_spec.agent_cohesion_enabled,
            )
        elapsed_seconds = time.perf_counter() - start_time
        return solver_result, elapsed_seconds, solver_result.get("status", "unknown_failure")
    except Exception as exc:  # pragma: no cover - defensive logging path
        elapsed_seconds = time.perf_counter() - start_time
        return None, elapsed_seconds, f"exception:{type(exc).__name__}:{exc}"


def build_mapping_record(
    *,
    case_spec: RefCaseSpec,
    run_configuration: RefRunConfiguration,
    mapping_name: str,
    solver_result: dict[str, Any] | None,
    elapsed_seconds: float,
    solver_status: str | None,
) -> RefMappingRunRecord:
    resolved_status = solver_status or "unknown_failure"
    paths_by_agent = None
    conflicts = None
    high_level_nodes = None
    solver_name = "A*" if case_spec.experiment_mode == "single_agent" else ("ECBS" if case_spec.use_ecbs else "CBS")
    suboptimality = None if solver_name in {"A*", "CBS"} else case_spec.ecbs_suboptimality

    if solver_result is not None:
        resolved_status = solver_result.get("status", resolved_status)
        paths_by_agent = solver_result.get("paths_by_agent")
        conflicts = solver_result.get("num_conflicts_detected")
        if conflicts is None:
            conflicts = solver_result.get("num_conflicts_detected_at_halt")
        high_level_nodes = solver_result.get("num_high_level_nodes_expanded")
        solver_name = solver_result.get("solver_name", solver_name)
        suboptimality = solver_result.get("solver_suboptimality_factor", suboptimality)

    result_category, counted_run, solved_run = categorize_solver_status(resolved_status)
    halted_time = case_spec.runtime_limit_seconds if result_category == "unfinished" else elapsed_seconds
    mapping_index = 0 if mapping_name == "classical" else 1

    return RefMappingRunRecord(
        case_id=case_spec.case_id,
        experiment_mode=case_spec.experiment_mode,
        size_label=case_spec.size_label,
        map_size=case_spec.map_size,
        agent_number=case_spec.agent_number,
        run_index=run_configuration.run_index,
        run_config_id=run_configuration.run_config_id,
        mapping_name=mapping_name,
        mapping_index=mapping_index,
        comparison_case="reference_comparison_paired",
        solver_name=solver_name,
        enhanced_cbs_enabled=bool(case_spec.use_ecbs) if solver_name != "A*" else False,
        solver_suboptimality_factor=suboptimality,
        paired_run=True,
        solver_status=resolved_status,
        result_category=result_category,
        counted_run=counted_run,
        solved_run=solved_run,
        time_computation_halted_seconds=halted_time,
        num_conflicts_detected_at_halt=conflicts,
        total_path_length=total_path_length(paths_by_agent),
        total_turns=total_turns(paths_by_agent),
        num_high_level_nodes_expanded=high_level_nodes,
        runtime_limit_seconds=case_spec.runtime_limit_seconds,
        map_identifier=run_configuration.map_identifier,
        initial_condition_spec=run_configuration.agents,
        notes=(
            "single-agent A* reference case"
            if case_spec.experiment_mode == "single_agent"
            else "multi-agent ECBS reference case with release/spawn times"
        ),
    )
