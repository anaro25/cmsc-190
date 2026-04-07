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


def count_obstacles(matrix):
    return sum(cell == 1 for row in matrix for cell in row)


def count_free_cells(matrix):
    return sum(cell == 0 for row in matrix for cell in row)


def iter_free_cells(matrix):
    for r, row in enumerate(matrix):
        for c, value in enumerate(row):
            if value == 0:
                yield (r, c)


def is_free_space_connected(matrix):
    free_cells = list(iter_free_cells(matrix))
    if not free_cells:
        return True

    start = free_cells[0]
    queue = deque([start])
    visited = {start}

    while queue:
        r, c = queue.popleft()
        for nr, nc in get_neighbors(matrix, r, c):
            if matrix[nr][nc] != 0:
                continue
            if (nr, nc) in visited:
                continue
            visited.add((nr, nc))
            queue.append((nr, nc))

    return len(visited) == len(free_cells)


def has_adjacent_obstacle(matrix, row, col):
    return any(matrix[nr][nc] == 1 for nr, nc in get_neighbors(matrix, row, col))


def has_adjacent_free(matrix, row, col):
    return any(matrix[nr][nc] == 0 for nr, nc in get_neighbors(matrix, row, col))


def try_add_static_obstacle(matrix, rng):
    candidates = [
        (r, c)
        for r, c in iter_free_cells(matrix)
        if has_adjacent_obstacle(matrix, r, c)
    ]
    rng.shuffle(candidates)

    for r, c in candidates:
        matrix[r][c] = 1
        if is_free_space_connected(matrix):
            return True
        matrix[r][c] = 0

    return False


def try_remove_static_obstacle(matrix, rng):
    candidates = []
    for r, row in enumerate(matrix):
        for c, value in enumerate(row):
            if value == 1 and has_adjacent_free(matrix, r, c):
                candidates.append((r, c))

    rng.shuffle(candidates)
    if not candidates:
        return False

    r, c = candidates[0]
    matrix[r][c] = 0
    return True


def preprocess_static_obstacle_density(obstacle_matrix, target_density, seed=42):
    rng = random.Random(seed)
    matrix = [row[:] for row in obstacle_matrix]
    total_cells = len(matrix) * len(matrix[0])
    target_obstacles = int(round(target_density * total_cells))

    while count_obstacles(matrix) < target_obstacles:
        if not try_add_static_obstacle(matrix, rng):
            break

    while count_obstacles(matrix) > target_obstacles:
        if not try_remove_static_obstacle(matrix, rng):
            break

    return matrix
