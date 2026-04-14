from __future__ import annotations

import random
from typing import Any

from dev.experiments.branch_specs import BranchSpec
from dev.experiments.dynamic_port.dynamic_loop import build_dynamic_loop
from dev.experiments.dynamic_port.pipeline import (
    build_mapped_loop,
    get_shared_assignment_map,
)
from dev.experiments.dynamic_port.preprocessing import preprocess_static_obstacle_density
from dev.experiments.study.models import DynamicBranchState, PreparedRunContext, RunConfiguration
from dev.experiments.study.runtime import seed_for
from dev.inputs.dynamic_port.loader import load_port_obstacle_matrix, load_spawnable_white_mask
from dev.mapf.agent_assignment import sample_agent_start_goal_pairs
from dev.maps.base_map_factory import create_base_map
from dev.maps.classical_mapper import apply_classical_mapping
from dev.maps.cyclic_mapper import apply_cyclic_mapping


def _spawn_mask_to_composite_positions(spawn_mask: list[list[bool]]) -> set[tuple[int, int]]:
    positions: set[tuple[int, int]] = set()
    for row_index, row in enumerate(spawn_mask):
        for column_index, is_spawnable in enumerate(row):
            if is_spawnable:
                positions.add((2 * row_index, 2 * column_index))
    return positions


def _serialize_agents(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "agent_id": agent["id"],
            "start": list(agent["start"]),
            "goal": list(agent["goal"]),
        }
        for agent in agents
    ]


def fallback_build_dynamic_loop(
    base_matrix: list[list[int]],
    dynamic_density: float,
    loop_length: int,
    seed: int,
) -> list[list[list[int]]]:
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

    base_map = create_base_map(
        base_rows=branch_spec.base_rows or 25,
        base_cols=branch_spec.base_cols or 25,
        obstacle_ratio=branch_spec.static_obstacle_density or 0.40,
        rng=random.Random(map_seed),
    )
    classical_map = apply_classical_mapping({"map": base_map})["map"]
    cyclic_map = apply_cyclic_mapping({"map": base_map})["map"]
    agents = sample_agent_start_goal_pairs(
        composite_map=base_map,
        num_agents=agent_number,
        rng=random.Random(assignment_seed),
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
        starts_and_goals=_serialize_agents(agents),
        notes="Fresh artificial map for this run configuration.",
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
) -> DynamicBranchState:
    schedule_seed = seed_for(branch_spec.map_type, seed_base, "dynamic_schedule")
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

    generation_mode = "group_patch"
    try:
        dynamic_loop_frames = build_dynamic_loop(
            base_matrix=static_matrix,
            dynamic_density=branch_spec.dynamic_target_dynamic_obstacle_density or 0.10,
            loop_length=branch_spec.dynamic_loop_sequence_length or 30,
            group_stay_durations=branch_spec.dynamic_group_stay_durations or (3, 4, 5),
            seed=schedule_seed,
        )
    except RuntimeError:
        generation_mode = "scattered_fallback"
        dynamic_loop_frames = fallback_build_dynamic_loop(
            base_matrix=static_matrix,
            dynamic_density=branch_spec.dynamic_target_dynamic_obstacle_density or 0.10,
            loop_length=branch_spec.dynamic_loop_sequence_length or 30,
            seed=schedule_seed,
        )

    classical_loop, cyclic_loop = build_mapped_loop(dynamic_loop_frames)
    assignment_map = get_shared_assignment_map(classical_loop)
    allowed_spawn_vertices = None
    if branch_spec.spawnable_cell_mode == "pure_white_only":
        spawn_mask = load_spawnable_white_mask(
            image_path=branch_spec.image_path,
            resize_longest_side=branch_spec.image_resize_longest_side,
        )
        allowed_spawn_vertices = _spawn_mask_to_composite_positions(spawn_mask)
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
    agents = sample_agent_start_goal_pairs(
        composite_map=dynamic_state.assignment_map,
        num_agents=agent_number,
        rng=random.Random(assignment_seed),
        require_individual_reachability=True,
        allowed_spawn_vertices=dynamic_state.allowed_spawn_vertices,
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
        starts_and_goals=_serialize_agents(agents),
        notes="Shared dynamic map source; unique initial conditions for this run.",
    )
    return PreparedRunContext(run_configuration=run_config, agents=agents)
