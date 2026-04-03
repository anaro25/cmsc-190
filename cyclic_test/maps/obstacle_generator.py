import random

from cyclic_test.core.composite_elements import Vertex


def get_vertex_positions(composite_map):
    vertex_positions = []

    for i in range(len(composite_map)):
        for j in range(len(composite_map[i])):
            if i % 2 == 0 and j % 2 == 0:
                vertex_positions.append((i, j))

    return vertex_positions


def get_adjacent_vertex_positions(position, max_rows, max_cols):
    i, j = position

    candidates = [
        (i - 2, j),
        (i + 2, j),
        (i, j - 2),
        (i, j + 2),
    ]

    valid_neighbors = []

    for ni, nj in candidates:
        if 0 <= ni < max_rows and 0 <= nj < max_cols:
            valid_neighbors.append((ni, nj))

    return valid_neighbors


def generate_connected_free_positions(composite_map, obstacle_ratio=0.40):
    vertex_positions = get_vertex_positions(composite_map)
    total_vertices = len(vertex_positions)

    target_obstacle_count = int(total_vertices * obstacle_ratio)
    target_free_count = total_vertices - target_obstacle_count

    if target_free_count <= 0:
        return set()

    max_rows = len(composite_map)
    max_cols = len(composite_map[0])

    free_positions = set()

    start = random.choice(vertex_positions)
    free_positions.add(start)

    while len(free_positions) < target_free_count:
        frontier = set()

        for free_pos in free_positions:
            neighbors = get_adjacent_vertex_positions(free_pos, max_rows, max_cols)
            for neighbor in neighbors:
                if neighbor not in free_positions:
                    frontier.add(neighbor)

        if not frontier:
            break

        next_free = random.choice(list(frontier))
        free_positions.add(next_free)

    return free_positions


def apply_randomized_vertices(composite_map, obstacle_ratio=0.40):
    free_positions = generate_connected_free_positions(
        composite_map,
        obstacle_ratio=obstacle_ratio
    )

    for i in range(len(composite_map)):
        for j in range(len(composite_map[i])):
            if i % 2 == 0 and j % 2 == 0:
                if (i, j) in free_positions:
                    composite_map[i][j] = Vertex.FREE_SPACE
                else:
                    composite_map[i][j] = Vertex.OBSTACLE

    return composite_map