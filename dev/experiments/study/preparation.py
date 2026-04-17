from __future__ import annotations

import random
from typing import Any

from dev.core.composite_elements import Vertex
from dev.experiments.branch_specs import BranchSpec
from dev.experiments.dynamic_port.dynamic_loop import build_dynamic_loop
from dev.experiments.dynamic_port.pipeline import (
    build_mapped_loop,
    get_shared_assignment_map,
)
from dev.experiments.dynamic_port.preprocessing import iter_free_cells, preprocess_static_obstacle_density
from dev.experiments.study.io_utils import ExperimentLogger
from dev.experiments.study.models import DynamicBranchState, PreparedRunContext, RunConfiguration
from dev.experiments.study.runtime import seed_for
from dev.inputs.dynamic_port.loader import (
    load_campus_semantic_masks,
    load_port_obstacle_matrix,
    load_spawnable_white_mask,
)
from dev.inputs.dynamic_port.map_builder import obstacle_matrix_to_composite_base_map
from dev.mapf.agent_assignment import sample_agent_start_goal_pairs
from dev.maps.base_map_factory import create_base_map
from dev.maps.classical_mapper import apply_classical_mapping
from dev.maps.cyclic_mapper import apply_cyclic_mapping


def _log(logger: ExperimentLogger | None, message: str) -> None:
    if logger is not None:
        logger.log(message)


def _spawn_mask_to_composite_positions(spawn_mask: list[list[bool]]) -> set[tuple[int, int]]:
    positions: set[tuple[int, int]] = set()
    for row_index, row in enumerate(spawn_mask):
        for column_index, is_spawnable in enumerate(row):
            if is_spawnable:
                positions.add((2 * row_index, 2 * column_index))
    return positions


def _zone_id_matrix_to_composite_positions(
    zone_id_matrix: list[list[int | None]],
) -> dict[int, set[tuple[int, int]]]:
    positions_by_zone: dict[int, set[tuple[int, int]]] = {}
    for row_index, row in enumerate(zone_id_matrix):
        for column_index, zone_id in enumerate(row):
            if zone_id is None:
                continue
            positions_by_zone.setdefault(int(zone_id), set()).add((2 * row_index, 2 * column_index))
    return positions_by_zone


def _filter_free_vertex_positions(
    composite_map: list[list[Any]],
    positions: set[tuple[int, int]] | None,
) -> set[tuple[int, int]] | None:
    if positions is None:
        return None
    filtered: set[tuple[int, int]] = set()
    for row_index, column_index in positions:
        if row_index < 0 or row_index >= len(composite_map):
            continue
        if column_index < 0 or column_index >= len(composite_map[row_index]):
            continue
        if composite_map[row_index][column_index] == Vertex.FREE_SPACE:
            filtered.add((row_index, column_index))
    return filtered


def _filter_zone_vertices_by_assignment_map(
    composite_map: list[list[Any]],
    zone_vertices_by_id: dict[int, set[tuple[int, int]]],
) -> dict[int, set[tuple[int, int]]]:
    filtered: dict[int, set[tuple[int, int]]] = {}
    for zone_id, positions in zone_vertices_by_id.items():
        free_positions = _filter_free_vertex_positions(composite_map, positions) or set()
        if free_positions:
            filtered[zone_id] = free_positions
    return filtered


def _binary_matrix_from_spawn_mask(spawn_mask: list[list[bool]]) -> list[list[int]]:
    return [[0 if is_spawnable else 1 for is_spawnable in row] for row in spawn_mask]


def _mask_to_matrix_positions(mask: list[list[bool]]) -> set[tuple[int, int]]:
    positions: set[tuple[int, int]] = set()
    for row_index, row in enumerate(mask):
        for column_index, enabled in enumerate(row):
            if enabled:
                positions.add((row_index, column_index))
    return positions


def _count_free_components(matrix: list[list[int]]) -> int:
    free_cells = list(iter_free_cells(matrix))
    if not free_cells:
        return 0

    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    visited: set[tuple[int, int]] = set()
    component_count = 0

    for start in free_cells:
        if start in visited:
            continue
        component_count += 1
        stack = [start]
        visited.add(start)
        while stack:
            row, col = stack.pop()
            for next_row, next_col in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                if next_row < 0 or next_row >= rows or next_col < 0 or next_col >= cols:
                    continue
                if matrix[next_row][next_col] != 0:
                    continue
                neighbor = (next_row, next_col)
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                stack.append(neighbor)
    return component_count


def _serialize_agents(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "agent_id": agent["id"],
            "start": list(agent["start"]),
            "goal": list(agent["goal"]),
        }
        for agent in agents
    ]


def _ordered_distinct_zone_pairs(zone_vertices_by_id: dict[int, set[tuple[int, int]]], rng: random.Random) -> list[tuple[int, int]]:
    zone_ids = list(zone_vertices_by_id.keys())
    ordered_pairs = [(start_zone_id, goal_zone_id) for start_zone_id in zone_ids for goal_zone_id in zone_ids if start_zone_id != goal_zone_id]
    rng.shuffle(ordered_pairs)
    return ordered_pairs


def _sample_agents_for_branch(
    *,
    branch_spec: BranchSpec,
    composite_map: list[list[Any]],
    num_agents: int,
    rng: random.Random,
    allowed_spawn_vertices: set[tuple[int, int]] | None = None,
    zone_vertices_by_id: dict[int, set[tuple[int, int]]] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    zone_vertices_by_id = zone_vertices_by_id or {}

    if branch_spec.zone_relationship_mode == "distinct_campus_zones":
        if not zone_vertices_by_id:
            raise ValueError("distinct_campus_zones mode requires campus zone vertices on the assignment map.")

        last_error: Exception | None = None
        for start_zone_id, goal_zone_id in _ordered_distinct_zone_pairs(zone_vertices_by_id, rng):
            try:
                agents = sample_agent_start_goal_pairs(
                    composite_map=composite_map,
                    num_agents=num_agents,
                    rng=rng,
                    require_individual_reachability=branch_spec.require_individual_reachability,
                    allowed_start_vertices=zone_vertices_by_id[start_zone_id],
                    allowed_goal_vertices=zone_vertices_by_id[goal_zone_id],
                    start_distribution_mode=branch_spec.start_distribution_mode,
                    goal_distribution_mode=branch_spec.goal_distribution_mode,
                )
                return (
                    agents,
                    f"start_zone={start_zone_id} | goal_zone={goal_zone_id} | start_distribution={branch_spec.start_distribution_mode} | goal_distribution={branch_spec.goal_distribution_mode}",
                )
            except ValueError as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        raise ValueError("Could not sample a valid distinct-zone campus run configuration.")

    agents = sample_agent_start_goal_pairs(
        composite_map=composite_map,
        num_agents=num_agents,
        rng=rng,
        require_individual_reachability=branch_spec.require_individual_reachability,
        allowed_spawn_vertices=allowed_spawn_vertices,
        start_distribution_mode=branch_spec.start_distribution_mode,
        goal_distribution_mode=branch_spec.goal_distribution_mode,
    )
    return (
        agents,
        f"start_distribution={branch_spec.start_distribution_mode} | goal_distribution={branch_spec.goal_distribution_mode}",
    )


def fallback_build_dynamic_loop(
    base_matrix: list[list[int]],
    dynamic_density: float,
    loop_length: int,
    seed: int,
    eligible_dynamic_cells: set[tuple[int, int]] | None = None,
) -> list[list[list[int]]]:
    from dev.experiments.dynamic_port.dynamic_loop import apply_dynamic_cells, frame_is_valid

    rows = len(base_matrix)
    cols = len(base_matrix[0]) if rows else 0
    total_cells = rows * cols
    target_dynamic_cells = max(0, int(round(dynamic_density * total_cells)))
    free_cells = [
        (r, c)
        for r in range(rows)
        for c in range(cols)
        if base_matrix[r][c] == 0 and (eligible_dynamic_cells is None or (r, c) in eligible_dynamic_cells)
    ]
    if target_dynamic_cells <= 0 or not free_cells:
        return [[row[:] for row in base_matrix] for _ in range(max(1, loop_length))]
    if len(free_cells) < target_dynamic_cells:
        raise RuntimeError(
            "Fallback dynamic loop generation does not have enough eligible free cells for the requested dynamic density. "
            f"eligible_dynamic_cells={len(free_cells)} | requested_dynamic_cells={target_dynamic_cells}"
        )

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
        if not chosen and target_dynamic_cells > 0:
            chosen = set(candidates[: min(target_dynamic_cells, len(candidates))])
        frames.append(apply_dynamic_cells(base_matrix, chosen))
    return frames


def build_failure_run_configuration(
    *,
    branch_spec: BranchSpec,
    seed_base: int,
    agent_number: int,
    agent_number_index: int,
    run_index: int,
    note: str,
    dynamic_schedule_seed: int | None,
) -> RunConfiguration:
    return RunConfiguration(
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
        map_seed=seed_for(branch_spec.map_type, seed_base, "map", agent_number, run_index),
        assignment_seed=seed_for(branch_spec.map_type, seed_base, "assign", agent_number, run_index),
        dynamic_schedule_seed=dynamic_schedule_seed,
        paired_source=False,
        starts_and_goals=[],
        notes=note,
    )


def prepare_static_run_context(
    *,
    branch_spec: BranchSpec,
    agent_number: int,
    agent_number_index: int,
    run_index: int,
    seed_base: int,
) -> PreparedRunContext:
    map_seed = seed_for(branch_spec.map_type, seed_base, "map", agent_number, run_index)
    assignment_seed = seed_for(branch_spec.map_type, seed_base, "assign", agent_number, run_index)

    if branch_spec.image_path is None:
        base_map = create_base_map(
            base_rows=branch_spec.base_rows or 25,
            base_cols=branch_spec.base_cols or 25,
            obstacle_ratio=branch_spec.static_obstacle_density or 0.40,
            rng=random.Random(map_seed),
        )
        allowed_spawn_vertices = None
        zone_vertices_by_id: dict[int, set[tuple[int, int]]] = {}
        map_identifier = f"artificial_{branch_spec.base_rows}x{branch_spec.base_cols}_seed_{map_seed}"
        map_note = "Fresh artificial map for this run configuration."
    else:
        if branch_spec.spawnable_cell_mode == "zone_colors_only":
            campus_semantics = load_campus_semantic_masks(
                image_path=branch_spec.image_path,
                resize_longest_side=branch_spec.image_resize_longest_side,
            )
            obstacle_matrix = campus_semantics["traversable_matrix"]
            base_map = obstacle_matrix_to_composite_base_map(obstacle_matrix)
            allowed_spawn_vertices = _filter_free_vertex_positions(
                base_map,
                _spawn_mask_to_composite_positions(campus_semantics["zone_spawn_mask"]),
            )
            zone_vertices_by_id = _filter_zone_vertices_by_assignment_map(
                base_map,
                _zone_id_matrix_to_composite_positions(campus_semantics["zone_id_matrix"]),
            )
            map_note = "Static image-based campus map loaded with semantic zone masks."
        else:
            obstacle_matrix = load_port_obstacle_matrix(
                image_path=branch_spec.image_path,
                threshold=branch_spec.image_threshold,
                resize_longest_side=branch_spec.image_resize_longest_side,
            )
            base_map = obstacle_matrix_to_composite_base_map(obstacle_matrix)
            allowed_spawn_vertices = None
            zone_vertices_by_id = {}
            map_note = "Static image-based thresholded map loaded for this run configuration."
        map_identifier = f"{branch_spec.map_type}_static_image_seed_{map_seed}"

    classical_map = apply_classical_mapping({"map": base_map})["map"]
    cyclic_map = apply_cyclic_mapping({"map": base_map})["map"]
    agents, assignment_note = _sample_agents_for_branch(
        branch_spec=branch_spec,
        composite_map=classical_map,
        num_agents=agent_number,
        rng=random.Random(assignment_seed),
        allowed_spawn_vertices=allowed_spawn_vertices,
        zone_vertices_by_id=zone_vertices_by_id,
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
        map_identifier=map_identifier,
        map_seed=map_seed,
        assignment_seed=assignment_seed,
        dynamic_schedule_seed=None,
        paired_source=False,
        starts_and_goals=_serialize_agents(agents),
        notes=f"{map_note} {assignment_note}",
    )
    return PreparedRunContext(
        run_configuration=run_config,
        agents=agents,
        base_map=base_map,
        classical_map=classical_map,
        cyclic_map=cyclic_map,
    )


def prepare_dynamic_branch_state(
    branch_spec: BranchSpec,
    *,
    seed_base: int,
    logger: ExperimentLogger | None = None,
) -> DynamicBranchState:
    schedule_seed = seed_for(branch_spec.map_type, seed_base, "dynamic_schedule")
    _log(
        logger,
        f"Preparing shared dynamic branch state | schedule_seed={schedule_seed} | image_path={branch_spec.image_path}",
    )
    _log(
        logger,
        f"  Loading obstacle matrix | threshold={branch_spec.image_threshold} | resize_longest_side={branch_spec.image_resize_longest_side}",
    )

    spawn_mask: list[list[bool]] | None = None
    campus_zone_vertices_by_id: dict[int, set[tuple[int, int]]] = {}
    visually_free_vertices: set[tuple[int, int]] = set()
    eligible_dynamic_cells: set[tuple[int, int]] | None = None

    if branch_spec.dynamic_generation_cell_mode == "zone_colors_only" or branch_spec.spawnable_cell_mode == "zone_colors_only":
        _log(logger, "  Loading campus semantic masks (zones, walkways, gray regions)...")
        campus_semantics = load_campus_semantic_masks(
            image_path=branch_spec.image_path,
            resize_longest_side=branch_spec.image_resize_longest_side,
        )
        raw_obstacle_matrix = campus_semantics["traversable_matrix"]
        spawn_mask = campus_semantics["zone_spawn_mask"]
        campus_zone_vertices_by_id = _zone_id_matrix_to_composite_positions(campus_semantics["zone_id_matrix"])
        visually_free_vertices = _spawn_mask_to_composite_positions(campus_semantics["gray_mask"])
        eligible_dynamic_cells = _mask_to_matrix_positions(campus_semantics["zone_spawn_mask"])
        zone_cell_count = sum(cell for row in campus_semantics["zone_spawn_mask"] for cell in row)
        walkway_cell_count = sum(cell for row in campus_semantics["walkway_mask"] for cell in row)
        gray_cell_count = sum(cell for row in campus_semantics["gray_mask"] for cell in row)
        _log(
            logger,
            f"  Campus semantic masks loaded | zone_cells={zone_cell_count} | walkway_cells={walkway_cell_count} | gray_cells={gray_cell_count} | zones={len(campus_zone_vertices_by_id)}",
        )
    else:
        raw_obstacle_matrix = load_port_obstacle_matrix(
            image_path=branch_spec.image_path,
            threshold=branch_spec.image_threshold,
            resize_longest_side=branch_spec.image_resize_longest_side,
        )

    raw_rows = len(raw_obstacle_matrix)
    raw_cols = len(raw_obstacle_matrix[0]) if raw_rows else 0
    _log(logger, f"  Obstacle matrix loaded | dimensions={raw_rows}x{raw_cols}")

    generation_source_matrix = raw_obstacle_matrix
    raw_free_components = _count_free_components(raw_obstacle_matrix)
    _log(
        logger,
        f"  Traversable-space diagnostic | free_cells={sum(cell == 0 for row in raw_obstacle_matrix for cell in row)} | connected_components={raw_free_components}",
    )

    if branch_spec.dynamic_generation_cell_mode == "pure_white_only":
        _log(logger, "  Loading pure-white traversable mask for grouped dynamic-obstacle generation...")
        spawn_mask = load_spawnable_white_mask(
            image_path=branch_spec.image_path,
            resize_longest_side=branch_spec.image_resize_longest_side,
        )
        generation_source_matrix = _binary_matrix_from_spawn_mask(spawn_mask)
        generation_free_components = _count_free_components(generation_source_matrix)
        _log(
            logger,
            f"  Pure-white traversable-space diagnostic | free_cells={sum(cell == 0 for row in generation_source_matrix for cell in row)} | connected_components={generation_free_components}",
        )
        _log(
            logger,
            "  Using pure-white-only traversable cells for grouped dynamic-obstacle generation and connectivity checks.",
        )
    elif branch_spec.dynamic_generation_cell_mode == "zone_colors_only":
        _log(
            logger,
            f"  Using campus zone-color cells only for grouped dynamic-obstacle generation | eligible_cells={len(eligible_dynamic_cells or set())}",
        )
    else:
        _log(logger, "  Using all thresholded non-black cells for grouped dynamic-obstacle generation and connectivity checks.")

    if branch_spec.dynamic_target_static_obstacle_density is None:
        _log(logger, "  Preserving source-image static obstacle layout (no static-density preprocessing).")
        static_matrix = [row[:] for row in generation_source_matrix]
    else:
        _log(
            logger,
            f"  Preprocessing static obstacle density toward target={branch_spec.dynamic_target_static_obstacle_density:.2f}",
        )
        static_matrix = preprocess_static_obstacle_density(
            obstacle_matrix=generation_source_matrix,
            target_density=branch_spec.dynamic_target_static_obstacle_density,
            seed=schedule_seed,
        )
        _log(logger, "  Static obstacle density preprocessing completed.")

    generation_mode = "group_patch"
    _log(logger, "  Building shared dynamic loop with grouped obstacle patches...")
    try:
        dynamic_loop_frames = build_dynamic_loop(
            base_matrix=static_matrix,
            dynamic_density=branch_spec.dynamic_target_dynamic_obstacle_density or 0.10,
            loop_length=branch_spec.dynamic_loop_sequence_length or 30,
            group_stay_durations=branch_spec.dynamic_group_stay_durations or (3, 4, 5),
            seed=schedule_seed,
            progress_callback=(logger.log if logger is not None else None),
            eligible_dynamic_cells=eligible_dynamic_cells,
        )
    except RuntimeError as exc:
        generation_mode = "scattered_fallback"
        _log(
            logger,
            f"  Grouped dynamic loop generation failed ({type(exc).__name__}: {exc}). Switching to scattered fallback generator.",
        )
        dynamic_loop_frames = fallback_build_dynamic_loop(
            base_matrix=static_matrix,
            dynamic_density=branch_spec.dynamic_target_dynamic_obstacle_density or 0.10,
            loop_length=branch_spec.dynamic_loop_sequence_length or 30,
            seed=schedule_seed,
            eligible_dynamic_cells=eligible_dynamic_cells,
        )
        _log(logger, "  Scattered fallback dynamic loop generation completed.")

    _log(logger, "  Building mapped loop representations for classical and cyclic mappings...")
    classical_loop, cyclic_loop = build_mapped_loop(dynamic_loop_frames)
    _log(logger, "  Shared mapped loop representations completed.")
    _log(logger, "  Building shared assignment map from the classical loop...")
    assignment_map = get_shared_assignment_map(classical_loop)
    _log(logger, "  Shared assignment map ready.")

    allowed_spawn_vertices = None
    if branch_spec.spawnable_cell_mode == "pure_white_only":
        if spawn_mask is None:
            _log(logger, "  Loading pure-white spawn mask to restrict spawnable cells...")
            spawn_mask = load_spawnable_white_mask(
                image_path=branch_spec.image_path,
                resize_longest_side=branch_spec.image_resize_longest_side,
            )
        else:
            _log(logger, "  Reusing previously loaded pure-white mask to restrict spawnable cells...")
        allowed_spawn_vertices = _filter_free_vertex_positions(
            assignment_map,
            _spawn_mask_to_composite_positions(spawn_mask),
        )
        _log(
            logger,
            f"  Pure-white spawn mask ready | allowed_spawn_vertices={len(allowed_spawn_vertices or set())}",
        )
    elif branch_spec.spawnable_cell_mode == "zone_colors_only":
        if spawn_mask is None:
            raise ValueError("zone_colors_only spawn mode requires campus semantic masks to be loaded.")
        allowed_spawn_vertices = _filter_free_vertex_positions(
            assignment_map,
            _spawn_mask_to_composite_positions(spawn_mask),
        )
        campus_zone_vertices_by_id = _filter_zone_vertices_by_assignment_map(
            assignment_map,
            campus_zone_vertices_by_id,
        )
        _log(
            logger,
            f"  Campus zone spawn mask ready | allowed_spawn_vertices={len(allowed_spawn_vertices or set())} | usable_zones={len(campus_zone_vertices_by_id)}",
        )

    _log(logger, "Shared dynamic branch state preparation completed.")
    return DynamicBranchState(
        raw_obstacle_matrix=raw_obstacle_matrix,
        static_matrix=static_matrix,
        dynamic_loop_frames=dynamic_loop_frames,
        classical_loop=classical_loop,
        cyclic_loop=cyclic_loop,
        assignment_map=assignment_map,
        map_identifier=f"{branch_spec.map_type}_shared_map_seed_{schedule_seed}_{generation_mode}",
        schedule_seed=schedule_seed,
        generation_mode=generation_mode,
        allowed_spawn_vertices=allowed_spawn_vertices,
        zone_vertices_by_id=campus_zone_vertices_by_id,
        visually_free_vertices=visually_free_vertices,
    )


def prepare_dynamic_run_context(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState,
    agent_number: int,
    agent_number_index: int,
    run_index: int,
    seed_base: int,
) -> PreparedRunContext:
    assignment_seed = seed_for(branch_spec.map_type, seed_base, "assign", agent_number, run_index)
    assignment_rng = random.Random(assignment_seed)
    agents, assignment_note = _sample_agents_for_branch(
        branch_spec=branch_spec,
        composite_map=dynamic_state.assignment_map,
        num_agents=agent_number,
        rng=assignment_rng,
        allowed_spawn_vertices=dynamic_state.allowed_spawn_vertices,
        zone_vertices_by_id=dynamic_state.zone_vertices_by_id,
    )
    run_note = f"Shared dynamic map source; unique initial conditions for this run. {assignment_note}"

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
        starts_and_goals=_serialize_agents(agents),
        notes=run_note,
    )
    return PreparedRunContext(
        run_configuration=run_config,
        agents=agents,
        base_map=None,
        classical_map=None,
        cyclic_map=None,
    )
