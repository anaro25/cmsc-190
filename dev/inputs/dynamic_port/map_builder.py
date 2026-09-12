from dev.core.composite_elements import Special, Vertex


def obstacle_matrix_to_composite_base_map(obstacle_matrix, *, free_value=0):
    """Convert a binary cell matrix into the composite-grid vertex map.

    ``free_value`` selects the binary convention. The legacy/reference
    pipeline keeps its historical default (0 = free, 1 = obstacle), while the
    main experiment passes ``free_value=1`` to match the manuscript.
    """
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
                Vertex.FREE_SPACE if obstacle_matrix[r][c] == free_value else Vertex.OBSTACLE
            )

    return composite_map


def composite_base_map_to_obstacle_matrix(composite_map, *, free_value=0):
    """Convert a composite-grid map into a binary cell matrix.

    ``free_value=1`` yields the manuscript convention (1 = traversable,
    0 = obstacle). The default preserves the reference pipeline's historical
    convention.
    """
    rows = (len(composite_map) + 1) // 2
    cols = (len(composite_map[0]) + 1) // 2
    obstacle_value = 0 if free_value == 1 else 1

    obstacle_matrix = [[obstacle_value for _ in range(cols)] for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            composite_r = 2 * r
            composite_c = 2 * c
            obstacle_matrix[r][c] = (
                free_value
                if composite_map[composite_r][composite_c] == Vertex.FREE_SPACE
                else obstacle_value
            )

    return obstacle_matrix
