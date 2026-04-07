from dev.core.composite_elements import Special, Vertex


def obstacle_matrix_to_composite_base_map(obstacle_matrix):
    rows = len(obstacle_matrix)
    cols = len(obstacle_matrix[0]) if rows else 0

    composite_rows = (2 * rows) - 1
    composite_cols = (2 * cols) - 1

    composite_map = [
        [Special.PLACEHOLDER for _ in range(composite_cols)]
        for _ in range(composite_rows)
    ]

    for r in range(rows):
        for c in range(cols):
            composite_r = 2 * r
            composite_c = 2 * c
            composite_map[composite_r][composite_c] = (
                Vertex.OBSTACLE if obstacle_matrix[r][c] == 1 else Vertex.FREE_SPACE
            )

    return composite_map


def composite_base_map_to_obstacle_matrix(composite_map):
    rows = (len(composite_map) + 1) // 2
    cols = (len(composite_map[0]) + 1) // 2

    obstacle_matrix = [[0 for _ in range(cols)] for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            composite_r = 2 * r
            composite_c = 2 * c
            obstacle_matrix[r][c] = 1 if composite_map[composite_r][composite_c] == Vertex.OBSTACLE else 0

    return obstacle_matrix
