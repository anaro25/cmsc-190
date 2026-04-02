import random

from composite_elements import Vertex


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


def generate_clumped_obstacle_positions(composite_map, obstacle_ratio=0.40):
    vertex_positions = get_vertex_positions(composite_map)
    total_vertices = len(vertex_positions)
    target_obstacle_count = int(total_vertices * obstacle_ratio)

    if target_obstacle_count == 0:
        return set()

    obstacle_positions = set()

    seed_count = max(1, target_obstacle_count // 12)
    seed_positions = random.sample(
        vertex_positions,
        min(seed_count, len(vertex_positions))
    )

    frontier = []

    for seed in seed_positions:
        obstacle_positions.add(seed)
        frontier.append(seed)

    max_rows = len(composite_map)
    max_cols = len(composite_map[0])

    while len(obstacle_positions) < target_obstacle_count:
        if frontier:
            current = random.choice(frontier)
        else:
            remaining_positions = [
                pos for pos in vertex_positions if pos not in obstacle_positions
            ]
            if not remaining_positions:
                break
            current = random.choice(remaining_positions)
            obstacle_positions.add(current)
            frontier.append(current)
            continue

        neighbors = get_adjacent_vertex_positions(current, max_rows, max_cols)
        random.shuffle(neighbors)

        grew_cluster = False

        for neighbor in neighbors:
            if neighbor not in obstacle_positions:
                obstacle_positions.add(neighbor)
                frontier.append(neighbor)
                grew_cluster = True
                break

            if len(obstacle_positions) >= target_obstacle_count:
                break

        if not grew_cluster:
            frontier.remove(current)

    return obstacle_positions


def apply_randomized_vertices(composite_map, obstacle_ratio=0.40):
    obstacle_positions = generate_clumped_obstacle_positions(
        composite_map,
        obstacle_ratio=obstacle_ratio
    )

    for i in range(len(composite_map)):
        for j in range(len(composite_map[i])):
            if i % 2 == 0 and j % 2 == 0:
                if (i, j) in obstacle_positions:
                    composite_map[i][j] = Vertex.OBSTACLE
                else:
                    composite_map[i][j] = Vertex.FREE_SPACE

    return composite_map