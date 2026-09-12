import random
from collections import deque


CARDINAL_STEPS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def in_bounds(matrix, row, col):
    return 0 <= row < len(matrix) and 0 <= col < len(matrix[0])


def get_neighbors(matrix, row, col):
    neighbors = []
    for dr, dc in CARDINAL_STEPS:
        nr, nc = row + dr, col + dc
        if in_bounds(matrix, nr, nc):
            neighbors.append((nr, nc))
    return neighbors


def _obstacle_value(free_value):
    return 0 if free_value == 1 else 1


def count_obstacles(matrix, *, free_value=0):
    obstacle_value = _obstacle_value(free_value)
    return sum(cell == obstacle_value for row in matrix for cell in row)


def count_free_cells(matrix, *, free_value=0):
    return sum(cell == free_value for row in matrix for cell in row)


def iter_free_cells(matrix, *, free_value=0):
    for r, row in enumerate(matrix):
        for c, value in enumerate(row):
            if value == free_value:
                yield (r, c)


def is_free_space_connected(matrix, *, free_value=0):
    free_cells = list(iter_free_cells(matrix, free_value=free_value))
    if not free_cells:
        return True

    start = free_cells[0]
    queue = deque([start])
    visited = {start}

    while queue:
        r, c = queue.popleft()
        for nr, nc in get_neighbors(matrix, r, c):
            if matrix[nr][nc] != free_value:
                continue
            if (nr, nc) in visited:
                continue
            visited.add((nr, nc))
            queue.append((nr, nc))

    return len(visited) == len(free_cells)


def has_adjacent_obstacle(matrix, row, col, *, free_value=0):
    obstacle_value = _obstacle_value(free_value)
    return any(matrix[nr][nc] == obstacle_value for nr, nc in get_neighbors(matrix, row, col))


def has_adjacent_free(matrix, row, col, *, free_value=0):
    return any(matrix[nr][nc] == free_value for nr, nc in get_neighbors(matrix, row, col))


def try_add_static_obstacle(matrix, rng, *, free_value=0):
    obstacle_value = _obstacle_value(free_value)
    candidates = [
        (r, c)
        for r, c in iter_free_cells(matrix, free_value=free_value)
        if has_adjacent_obstacle(matrix, r, c, free_value=free_value)
    ]
    rng.shuffle(candidates)

    for r, c in candidates:
        matrix[r][c] = obstacle_value
        if is_free_space_connected(matrix, free_value=free_value):
            return True
        matrix[r][c] = free_value

    return False


def try_remove_static_obstacle(matrix, rng, *, free_value=0):
    obstacle_value = _obstacle_value(free_value)
    candidates = []
    for r, row in enumerate(matrix):
        for c, value in enumerate(row):
            if value == obstacle_value and has_adjacent_free(matrix, r, c, free_value=free_value):
                candidates.append((r, c))

    rng.shuffle(candidates)
    if not candidates:
        return False

    r, c = candidates[0]
    matrix[r][c] = free_value
    return True


def preprocess_static_obstacle_density(obstacle_matrix, target_density, seed=42, *, free_value=0):
    matrix = [row[:] for row in obstacle_matrix]
    if target_density is None or float(target_density) >= 1.0:
        return matrix

    rng = random.Random(seed)
    total_cells = len(matrix) * len(matrix[0])
    target_obstacles = int(round(float(target_density) * total_cells))

    while count_obstacles(matrix, free_value=free_value) < target_obstacles:
        if not try_add_static_obstacle(matrix, rng, free_value=free_value):
            break

    while count_obstacles(matrix, free_value=free_value) > target_obstacles:
        if not try_remove_static_obstacle(matrix, rng, free_value=free_value):
            break

    return matrix
