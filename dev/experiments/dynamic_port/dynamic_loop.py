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


def _split_exact_total(total, count):
    values = [total // count for _ in range(count)]
    for index in range(total % count):
        values[index] += 1
    return values


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


def _ordered_frontier(base_matrix, dynamic_cells, center, rng):
    frontier = []
    if not dynamic_cells:
        frontier.append(center)
    else:
        for cell in list(dynamic_cells):
            for neighbor in get_neighbors(base_matrix, cell[0], cell[1]):
                if base_matrix[neighbor[0]][neighbor[1]] != 0 or neighbor in dynamic_cells or neighbor in frontier:
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


def _grow_group(base_matrix, center, target_count, blocked_cells, rng):
    dynamic_cells = set()
    attempts = 0
    while len(dynamic_cells) < target_count and attempts < max(40, target_count * 30):
        attempts += 1
        frontier = _ordered_frontier(base_matrix, dynamic_cells, center, rng)
        added = False
        for cell in frontier:
            if cell in blocked_cells:
                continue
            candidate = dynamic_cells | {cell}
            if frame_is_valid(base_matrix, blocked_cells | candidate):
                dynamic_cells.add(cell)
                added = True
                break
        if not added:
            break
    return dynamic_cells


def _top_up_dynamic_cells(base_matrix, dynamic_cells, target_total, rng):
    candidates = [cell for cell in _free_cells(base_matrix) if cell not in dynamic_cells]
    rng.shuffle(candidates)
    candidates.sort(key=lambda cell: (_free_neighbor_count(base_matrix, cell), rng.random()), reverse=True)
    for cell in candidates:
        if len(dynamic_cells) >= target_total:
            break
        candidate = dynamic_cells | {cell}
        if frame_is_valid(base_matrix, candidate):
            dynamic_cells = candidate
    return dynamic_cells


def build_dynamic_loop(
    base_matrix,
    dynamic_density,
    loop_length,
    preferred_group_range=(2, 3),
    seed=42,
):
    rng = random.Random(seed)
    total_cells = len(base_matrix) * len(base_matrix[0])
    target_dynamic_cells = int(round(dynamic_density * total_cells))
    if target_dynamic_cells <= 0:
        return [apply_dynamic_cells(base_matrix, set()) for _ in range(max(1, loop_length))]

    loop_length = max(1, loop_length)
    frames = []

    for time_step in range(loop_length):
        frame_rng = random.Random(seed + (time_step * 1009))
        group_count = frame_rng.randint(preferred_group_range[0], preferred_group_range[1])
        group_sizes = _split_exact_total(target_dynamic_cells, group_count)
        centers = _choose_distributed_centers(base_matrix, group_count, frame_rng)

        dynamic_cells = set()
        for group_index, (center, group_size) in enumerate(zip(centers, group_sizes)):
            group_rng = random.Random(seed + (time_step * 4099) + (group_index * 131))
            group_cells = _grow_group(base_matrix, center, group_size, dynamic_cells, group_rng)
            dynamic_cells.update(group_cells)

        if len(dynamic_cells) < target_dynamic_cells:
            dynamic_cells = _top_up_dynamic_cells(base_matrix, dynamic_cells, target_dynamic_cells, frame_rng)

        retries = 0
        while (len(dynamic_cells) != target_dynamic_cells or not frame_is_valid(base_matrix, dynamic_cells)) and retries < 12:
            retries += 1
            retry_rng = random.Random(seed + (time_step * 7919) + retries * 313)
            group_count = retry_rng.randint(preferred_group_range[0], preferred_group_range[1])
            group_sizes = _split_exact_total(target_dynamic_cells, group_count)
            centers = _choose_distributed_centers(base_matrix, group_count, retry_rng)
            dynamic_cells = set()
            for group_index, (center, group_size) in enumerate(zip(centers, group_sizes)):
                group_rng = random.Random(seed + (time_step * 4099) + retries * 577 + group_index * 131)
                group_cells = _grow_group(base_matrix, center, group_size, dynamic_cells, group_rng)
                dynamic_cells.update(group_cells)
            if len(dynamic_cells) < target_dynamic_cells:
                dynamic_cells = _top_up_dynamic_cells(base_matrix, dynamic_cells, target_dynamic_cells, retry_rng)

        if len(dynamic_cells) != target_dynamic_cells or not frame_is_valid(base_matrix, dynamic_cells):
            dynamic_cells = set()
            candidates = list(_free_cells(base_matrix))
            frame_rng.shuffle(candidates)
            candidates.sort(key=lambda cell: (_free_neighbor_count(base_matrix, cell), frame_rng.random()), reverse=True)
            for cell in candidates:
                if len(dynamic_cells) >= target_dynamic_cells:
                    break
                candidate = dynamic_cells | {cell}
                if frame_is_valid(base_matrix, candidate):
                    dynamic_cells = candidate

        frames.append(apply_dynamic_cells(base_matrix, dynamic_cells))

    return frames
