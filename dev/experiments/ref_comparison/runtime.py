from __future__ import annotations

import time
from pathlib import Path
from statistics import mean
from typing import Any, Callable

from PIL import Image

from dev.core.composite_elements import Vertex
from dev.experiments.ref_comparison.models import RefCaseSpec, RefMappingRunRecord, RefRunConfiguration
from dev.inputs.dynamic_port.map_builder import obstacle_matrix_to_composite_base_map
from dev.mapf.full.cbs_solver import solve_mapf_with_cbs
from dev.mapf.full.mapf_low_level_astar import find_path_for_agent
from dev.maps.classical_mapper import apply_classical_mapping
from dev.maps.cyclic_mapper import apply_cyclic_mapping
from dev.utils.log_symbols import AGENT_LOG_SYMBOL, TARGET_LOG_SYMBOL

COUNTED_RESULT_CATEGORIES = {"successful", "unfinished"}
INVISIBLE_OBSTACLE_COLOR = (232, 120, 122)  # #e8787a


def map_label(map_number: int | None) -> str:
    if map_number is None:
        return ""
    return f"Map {int(map_number)}"


def _composite_positions_for_cells(cells: set[tuple[int, int]]) -> set[tuple[int, int]]:
    return {(2 * row, 2 * col) for row, col in cells}


def load_reference_port_obstacle_data(image_path: str | Path) -> dict[str, Any]:
    """Load a reference port map with support for invisible obstacles.

    Pixel meaning for reference-comparison maps:
    - black (#000000): normal obstacle
    - white (#ffffff): free space
    - light red (#e8787a): invisible obstacle

    Invisible obstacles are blocked in the logical matrix, but their vertex
    positions are returned separately so visualizations can render them as
    ordinary free space.
    """
    image_path = Path(image_path)
    with Image.open(image_path) as image:
        rgb_image = image.convert("RGB")
        width, height = rgb_image.size
        pixels = rgb_image.load()
        matrix: list[list[int]] = []
        invisible_cells: set[tuple[int, int]] = set()
        for y in range(height):
            row: list[int] = []
            for x in range(width):
                value = pixels[x, y]
                if value == (0, 0, 0):
                    row.append(1)
                elif value == (255, 255, 255):
                    row.append(0)
                elif value == INVISIBLE_OBSTACLE_COLOR:
                    row.append(1)
                    invisible_cells.add((y, x))
                else:
                    raise ValueError(
                        "Reference port maps must contain only pure black obstacle pixels, "
                        "pure white free-space pixels, and light-red invisible-obstacle pixels "
                        f"(#e8787a). Found {value} at {(x, y)} in {image_path}."
                    )
            matrix.append(row)
    invisible_vertices = _composite_positions_for_cells(invisible_cells)
    return {
        "obstacle_matrix": matrix,
        "invisible_obstacle_cells": invisible_cells,
        "invisible_obstacle_vertices": invisible_vertices,
    }


def load_exact_black_white_obstacle_matrix(image_path: str | Path) -> list[list[int]]:
    """Backward-compatible loader name for reference port maps.

    The reference-comparison maps now also allow light-red invisible obstacles,
    which are logically encoded as obstacles in the returned matrix.
    """
    return load_reference_port_obstacle_data(image_path)["obstacle_matrix"]


def _composite_vertex_for_cell(row: int, col: int) -> tuple[int, int]:
    return (2 * row, 2 * col)


def _assert_free_vertex(composite_map: list[list[Any]], vertex: tuple[int, int], label: str) -> None:
    row, col = vertex
    if row < 0 or row >= len(composite_map) or col < 0 or col >= len(composite_map[row]):
        raise ValueError(f"{label} vertex {vertex} is outside the composite map.")
    if composite_map[row][col] != Vertex.FREE_SPACE:
        raise ValueError(f"{label} vertex {vertex} is not free space.")


def build_reference_maps(case_spec: RefCaseSpec, *, map_index: int = 0) -> dict[str, Any]:
    map_paths = list(case_spec.map_image_paths or [case_spec.image_path])
    if not map_paths:
        raise ValueError(f"No reference port maps configured for {case_spec.case_id}.")
    if map_index < 0 or map_index >= len(map_paths):
        raise IndexError(f"map_index {map_index} is outside the configured reference port map list.")

    map_number = int(map_index) + 1
    image_path = Path(map_paths[map_index])
    obstacle_data = load_reference_port_obstacle_data(image_path)
    obstacle_matrix = obstacle_data["obstacle_matrix"]
    invisible_obstacle_vertices = obstacle_data["invisible_obstacle_vertices"]
    rows = len(obstacle_matrix)
    cols = len(obstacle_matrix[0]) if rows else 0
    if rows != case_spec.map_size or cols != case_spec.map_size:
        raise ValueError(
            f"Expected {case_spec.map_size}x{case_spec.map_size} reference map for {case_spec.case_id}, "
            f"but got {rows}x{cols} in {image_path}."
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

    label = map_label(map_number)
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
        "invisible_obstacle_vertices": invisible_obstacle_vertices,
        "invisible_obstacle_count": len(invisible_obstacle_vertices),
        "map_index": map_index,
        "map_number": map_number,
        "map_label": label,
        "image_path": str(image_path),
        "map_identifier": f"reference_port_map_{map_number}",
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
    return [_build_agent(0, map_context["lower_left_start"], map_context["upper_right_goal"], spawn_time=0)]


def _path_position(path: list[Any], time_step: int) -> Any:
    if time_step < 0:
        return None
    if time_step < len(path):
        return path[time_step]
    return None


def _spawn_cell_is_available(*, spawn_vertex: tuple[int, int], proposed_spawn_time: int, reservation_paths: list[list[Any]]) -> bool:
    for path in reservation_paths:
        if _path_position(path, proposed_spawn_time) == spawn_vertex:
            return False
        if _path_position(path, proposed_spawn_time + 1) == spawn_vertex:
            return False
    return True


def build_multi_agent_spawn_sequence(case_spec: RefCaseSpec, map_context: dict[str, Any], *, agent_number: int | None = None) -> list[dict[str, Any]]:
    requested_agent_number = int(agent_number if agent_number is not None else case_spec.agent_number)
    if requested_agent_number <= 0:
        raise ValueError(f"Requested multi-agent reference agent count must be positive. Found {requested_agent_number}.")
    agents: list[dict[str, Any]] = []
    spawn_vertices = list(map_context["spawn_vertices"])
    goal = map_context["upper_right_goal"]
    reservation_paths: list[list[Any]] = []
    search_time_limit = max(case_spec.map_size * requested_agent_number * 4, requested_agent_number * 10)

    proposed_spawn_time = 0
    next_spawn_index = 0
    while len(agents) < requested_agent_number and proposed_spawn_time <= search_time_limit:
        spawned_this_timestep = 0
        for spawn_vertex in spawn_vertices:
            if len(agents) >= requested_agent_number:
                break
            if not _spawn_cell_is_available(
                spawn_vertex=spawn_vertex,
                proposed_spawn_time=proposed_spawn_time,
                reservation_paths=reservation_paths,
            ):
                continue

            agent = _build_agent(next_spawn_index, spawn_vertex, goal, spawn_time=proposed_spawn_time)
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

    if len(agents) < requested_agent_number:
        raise ValueError(
            f"Could not create the requested {requested_agent_number}-agent release schedule "
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


def build_run_configuration(*, case_spec: RefCaseSpec, run_index: int, map_identifier: str, agents: list[dict[str, Any]], notes: str, map_index: int | None = None, map_number: int | None = None, map_label_value: str = "", agent_number: int | None = None) -> RefRunConfiguration:
    resolved_agent_number = int(agent_number if agent_number is not None else case_spec.agent_number)
    suffix = ""
    if map_number is not None:
        suffix = f".map_{int(map_number)}"
    return RefRunConfiguration(
        case_id=case_spec.case_id,
        experiment_mode=case_spec.experiment_mode,
        size_label=case_spec.size_label,
        map_size=case_spec.map_size,
        agent_number=resolved_agent_number,
        run_index=run_index,
        run_config_id=f"ref_run[{case_spec.case_id}{suffix}.{run_index}]",
        map_identifier=map_identifier,
        paired_source=True,
        agents=serialize_agents(agents),
        map_index=map_index,
        map_number=map_number,
        map_label=map_label_value,
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
        direction = (current_position[0] - previous_position[0], current_position[1] - previous_position[1])
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
    if solver_status == "solver_timeout":
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


def _single_agent_solver_result(*, composite_map: list[list[Any]], agent: dict[str, Any], case_spec: RefCaseSpec) -> dict[str, Any]:
    result = find_path_for_agent(
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
        return_diagnostics=True,
    )
    path = result.get("path")
    nodes_expanded = result.get("num_expanded_nodes")
    if path is None:
        return {
            "status": "no_solution",
            "paths_by_agent": None,
            "num_conflicts_detected": 0,
            "num_high_level_nodes_expanded": nodes_expanded,
            "solver_name": "A*",
            "solver_suboptimality_factor": None,
            "agent_cohesion_enabled": False,
        }
    return {
        "status": "solved",
        "paths_by_agent": {agent["id"]: path},
        "num_conflicts_detected": 0,
        "num_high_level_nodes_expanded": nodes_expanded,
        "solver_name": "A*",
        "solver_suboptimality_factor": None,
        "agent_cohesion_enabled": False,
    }


def execute_mapping(*, case_spec: RefCaseSpec, composite_map: list[list[Any]], agents: list[dict[str, Any]], mapping_name: str, logger: Any) -> tuple[dict[str, Any] | None, float, str]:
    label = f"{case_spec.case_id} {mapping_name}"
    start_time = time.perf_counter()
    try:
        if case_spec.experiment_mode == "single_agent":
            solver_result = _single_agent_solver_result(composite_map=composite_map, agent=agents[0], case_spec=case_spec)
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
    except Exception as exc:  # pragma: no cover
        elapsed_seconds = time.perf_counter() - start_time
        return None, elapsed_seconds, f"exception:{type(exc).__name__}:{exc}"


def execute_mapping_with_timing_repetitions(
    *,
    case_spec: RefCaseSpec,
    composite_map: list[list[Any]],
    agents: list[dict[str, Any]],
    mapping_name: str,
    logger: Any,
    repetitions: int,
) -> tuple[dict[str, Any] | None, float, str, list[float], list[str]]:
    repetition_count = max(1, int(repetitions))
    elapsed_samples: list[float] = []
    status_samples: list[str] = []
    representative_result: dict[str, Any] | None = None
    representative_status = "unknown_failure"

    for _ in range(repetition_count):
        solver_result, elapsed_seconds, solver_status = execute_mapping(
            case_spec=case_spec,
            composite_map=composite_map,
            agents=agents,
            mapping_name=mapping_name,
            logger=logger,
        )
        elapsed_samples.append(elapsed_seconds)
        status_samples.append(solver_status)

        # The reference setup is deterministic for both single-agent and multi-agent
        # cases, so path-related values should be identical across timing repeats.
        # Prefer a solved run as the representative source of path, conflict, node,
        # turn, and distance metrics if one exists.
        if representative_result is None or (representative_status != "solved" and solver_status == "solved"):
            representative_result = solver_result
            representative_status = solver_status

    return representative_result, mean(elapsed_samples), representative_status, elapsed_samples, status_samples


def build_mapping_record(
    *,
    case_spec: RefCaseSpec,
    run_configuration: RefRunConfiguration,
    mapping_name: str,
    solver_result: dict[str, Any] | None,
    elapsed_seconds: float,
    solver_status: str | None,
    timing_repetitions: int = 1,
    timing_elapsed_samples_seconds: list[float] | None = None,
) -> RefMappingRunRecord:
    resolved_status = solver_status or "unknown_failure"
    paths_by_agent = None
    conflicts = None
    high_level_nodes = None
    solver_name = "A*" if case_spec.experiment_mode == "single_agent" else ("ECBS" if case_spec.use_ecbs else "CBS")
    suboptimality = case_spec.ecbs_suboptimality if solver_name == "ECBS" else None

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
        agent_number=run_configuration.agent_number,
        run_index=run_configuration.run_index,
        run_config_id=run_configuration.run_config_id,
        mapping_name=mapping_name,
        mapping_index=mapping_index,
        comparison_case="reference_comparison_paired",
        solver_name=solver_name,
        enhanced_cbs_enabled=(solver_name == "ECBS"),
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
        map_index=run_configuration.map_index,
        map_number=run_configuration.map_number,
        map_label=run_configuration.map_label,
        notes=(
            f"single-agent traditional A* on {mapping_name} mapping; runtime averaged over {int(timing_repetitions)} identical timing repetitions"
            if case_spec.experiment_mode == "single_agent"
            else f"multi-agent ECBS on {mapping_name} mapping; runtime averaged over {int(timing_repetitions)} identical timing repetitions"
        ),
        timing_repetitions=max(1, int(timing_repetitions)),
        timing_elapsed_samples_seconds=timing_elapsed_samples_seconds,
    )
