import random
from collections import deque

from dev.experiments.dynamic_port.preprocessing import get_neighbors, is_free_space_connected


def shortest_path_distance(matrix, start, goal):
    if start == goal:
        return 0

    queue = deque([(start, 0)])
    visited = {start}
    while queue:
        (r, c), dist = queue.popleft()
        for nr, nc in get_neighbors(matrix, r, c):
            if matrix[nr][nc] != 0 or (nr, nc) in visited:
                continue
            if (nr, nc) == goal:
                return dist + 1
            visited.add((nr, nc))
            queue.append(((nr, nc), dist + 1))
    return None


def frame_is_valid(base_matrix, dynamic_cells):
    frame = [row[:] for row in base_matrix]
    for r, c in dynamic_cells:
        if frame[r][c] == 0:
            frame[r][c] = 2
    traversable = [[0 if cell == 0 else 1 for cell in row] for row in frame]
    return is_free_space_connected(traversable)


def apply_dynamic_cells(base_matrix, dynamic_cells):
    frame = [row[:] for row in base_matrix]
    for r, c in dynamic_cells:
        if frame[r][c] == 0:
            frame[r][c] = 2
    return frame


def _free_cells(base_matrix):
    for r, row in enumerate(base_matrix):
        for c, value in enumerate(row):
            if value == 0:
                yield (r, c)


def _free_neighbor_count(base_matrix, cell):
    r, c = cell
    return sum(1 for nr, nc in get_neighbors(base_matrix, r, c) if base_matrix[nr][nc] == 0)


def _choose_distributed_centers(base_matrix, group_count, rng):
    candidates = [cell for cell in _free_cells(base_matrix) if _free_neighbor_count(base_matrix, cell) >= 2]
    if not candidates:
        candidates = list(_free_cells(base_matrix))
    rng.shuffle(candidates)
    candidates.sort(key=lambda cell: (_free_neighbor_count(base_matrix, cell), rng.random()), reverse=True)

    centers = []
    min_distance = max(4, min(len(base_matrix), len(base_matrix[0])) // 4)
    for cell in candidates:
        if all((shortest_path_distance(base_matrix, cell, other) or 999) >= min_distance for other in centers):
            centers.append(cell)
            if len(centers) == group_count:
                return centers

    for cell in candidates:
        if cell not in centers:
            centers.append(cell)
            if len(centers) == group_count:
                return centers
    return centers


def _ordered_frontier(base_matrix, group_cells, center, occupied_cells, rng):
    frontier = []
    if not group_cells:
        frontier.append(center)
    else:
        for cell in list(group_cells):
            for neighbor in get_neighbors(base_matrix, cell[0], cell[1]):
                if base_matrix[neighbor[0]][neighbor[1]] != 0:
                    continue
                if neighbor in group_cells or neighbor in occupied_cells or neighbor in frontier:
                    continue
                frontier.append(neighbor)
    rng.shuffle(frontier)
    frontier.sort(
        key=lambda cell: (
            abs(cell[0] - center[0]) + abs(cell[1] - center[1]),
            -_free_neighbor_count(base_matrix, cell),
            rng.random(),
        )
    )
    return frontier


def _grow_group_patch(base_matrix, center, target_count, occupied_cells, rng):
    group_cells = set()
    attempts = 0
    while len(group_cells) < target_count and attempts < max(80, target_count * 40):
        attempts += 1
        frontier = _ordered_frontier(base_matrix, group_cells, center, occupied_cells, rng)
        added = False
        for cell in frontier:
            candidate = group_cells | {cell}
            if frame_is_valid(base_matrix, occupied_cells | candidate):
                group_cells.add(cell)
                added = True
                break
        if not added:
            break
    return group_cells


def _build_group_patches(base_matrix, target_dynamic_cells, preferred_group_range, seed):
    rng = random.Random(seed)
    min_groups, max_groups = preferred_group_range
    group_count = rng.randint(min_groups, max_groups)
    centers = _choose_distributed_centers(base_matrix, group_count, rng)

    target_sizes = [target_dynamic_cells // group_count for _ in range(group_count)]
    for index in range(target_dynamic_cells % group_count):
        target_sizes[index] += 1

    patches = []
    occupied_cells = set()
    for group_index, (center, target_size) in enumerate(zip(centers, target_sizes)):
        patch_rng = random.Random(seed + 1000 + group_index * 97)
        patch = _grow_group_patch(
            base_matrix=base_matrix,
            center=center,
            target_count=max(target_size * 2, target_size + 8),
            occupied_cells=occupied_cells,
            rng=patch_rng,
        )
        if not patch:
            patch = _grow_group_patch(
                base_matrix=base_matrix,
                center=center,
                target_count=max(target_size, 1),
                occupied_cells=occupied_cells,
                rng=patch_rng,
            )
        ordered_patch = list(patch)
        patch_rng.shuffle(ordered_patch)
        ordered_patch.sort(
            key=lambda cell: (
                abs(cell[0] - center[0]) + abs(cell[1] - center[1]),
                -_free_neighbor_count(base_matrix, cell),
                patch_rng.random(),
            )
        )
        patches.append({
            "center": center,
            "cells": ordered_patch,
        })
        occupied_cells.update(ordered_patch)

    return patches


def _select_frame_dynamic_cells(base_matrix, patches, target_dynamic_cells, frame_seed):
    frame_rng = random.Random(frame_seed)
    frame_cells = set()
    group_indices = list(range(len(patches)))
    frame_rng.shuffle(group_indices)

    active_groups = []
    for group_index in group_indices:
        if frame_rng.random() < 0.55:
            active_groups.append(group_index)

    if not active_groups and patches:
        active_groups = [group_indices[0]]

    remaining = target_dynamic_cells
    groups_left = len(active_groups)

    for group_index in active_groups:
        groups_left -= 1
        patch_cells = patches[group_index]["cells"]
        if not patch_cells:
            continue

        max_take = min(len(patch_cells), remaining)
        min_take = 1 if groups_left == 0 else 0
        if max_take <= 0:
            continue

        desired = frame_rng.randint(min_take, max_take)
        ordered_cells = list(patch_cells)
        frame_rng.shuffle(ordered_cells)
        ordered_cells.sort(
            key=lambda cell: (
                abs(cell[0] - patches[group_index]["center"][0]) + abs(cell[1] - patches[group_index]["center"][1]),
                frame_rng.random(),
            )
        )
        for cell in ordered_cells[:desired]:
            candidate = frame_cells | {cell}
            if frame_is_valid(base_matrix, candidate):
                frame_cells.add(cell)
        remaining = target_dynamic_cells - len(frame_cells)

    if len(frame_cells) < target_dynamic_cells:
        fallback_candidates = []
        for group in patches:
            fallback_candidates.extend(group["cells"])
        # de-duplicate while preserving order
        seen = set()
        ordered_candidates = []
        for cell in fallback_candidates:
            if cell not in seen:
                seen.add(cell)
                ordered_candidates.append(cell)
        frame_rng.shuffle(ordered_candidates)
        ordered_candidates.sort(key=lambda cell: (_free_neighbor_count(base_matrix, cell), frame_rng.random()), reverse=True)

        for cell in ordered_candidates:
            if len(frame_cells) >= target_dynamic_cells:
                break
            if cell in frame_cells:
                continue
            candidate = frame_cells | {cell}
            if frame_is_valid(base_matrix, candidate):
                frame_cells.add(cell)

    if len(frame_cells) != target_dynamic_cells or not frame_is_valid(base_matrix, frame_cells):
        frame_cells = set()
        fallback_candidates = []
        for group in patches:
            fallback_candidates.extend(group["cells"])
        seen = set()
        ordered_candidates = []
        for cell in fallback_candidates:
            if cell not in seen:
                seen.add(cell)
                ordered_candidates.append(cell)
        ordered_candidates.sort(key=lambda cell: (_free_neighbor_count(base_matrix, cell), frame_rng.random()), reverse=True)
        for cell in ordered_candidates:
            if len(frame_cells) >= target_dynamic_cells:
                break
            candidate = frame_cells | {cell}
            if frame_is_valid(base_matrix, candidate):
                frame_cells.add(cell)

    return frame_cells


def build_dynamic_loop(
    base_matrix,
    dynamic_density,
    loop_length,
    preferred_group_range=(2, 3),
    seed=42,
):
    total_cells = len(base_matrix) * len(base_matrix[0])
    target_dynamic_cells = int(round(dynamic_density * total_cells))
    if target_dynamic_cells <= 0:
        return [apply_dynamic_cells(base_matrix, set()) for _ in range(max(1, loop_length))]

    loop_length = max(1, loop_length)
    patches = _build_group_patches(
        base_matrix=base_matrix,
        target_dynamic_cells=target_dynamic_cells,
        preferred_group_range=preferred_group_range,
        seed=seed,
    )

    frames = []
    for time_step in range(loop_length):
        dynamic_cells = _select_frame_dynamic_cells(
            base_matrix=base_matrix,
            patches=patches,
            target_dynamic_cells=target_dynamic_cells,
            frame_seed=seed + time_step * 1009,
        )
        frames.append(apply_dynamic_cells(base_matrix, dynamic_cells))

    return frames
