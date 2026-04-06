from dev.core.composite_elements import HorizontalTransition, VerticalTransition, Vertex
from dev.core.transition_utils import (
    get_adjacent_vertices,
    is_horizontal_slot,
    is_in_bounds,
    is_transition_slot,
    is_vertex_slot,
)


def is_free_vertex(grid, i, j):
    if not is_in_bounds(grid, i, j):
        return False
    if not is_vertex_slot(i, j):
        return False
    return grid[i][j] == Vertex.FREE_SPACE


def get_all_free_vertices(grid):
    free_vertices = []

    for i in range(len(grid)):
        for j in range(len(grid[i])):
            if is_free_vertex(grid, i, j):
                free_vertices.append((i, j))

    return free_vertices


def get_outgoing_neighbors(grid, vertex_position):
    """
    Returns all vertices directly reachable from this vertex
    according to the directed/bidirectional transitions in the composite grid.
    """
    vertex_i, vertex_j = vertex_position

    candidate_transition_positions = [
        (vertex_i, vertex_j - 1),  # left horizontal slot
        (vertex_i, vertex_j + 1),  # right horizontal slot
        (vertex_i - 1, vertex_j),  # upper vertical slot
        (vertex_i + 1, vertex_j),  # lower vertical slot
    ]

    neighbors = []

    for transition_position in candidate_transition_positions:
        transition_i, transition_j = transition_position

        if not is_in_bounds(grid, transition_i, transition_j):
            continue
        if not is_transition_slot(transition_i, transition_j):
            continue

        next_vertex = get_destination_vertex_if_traversable(
            grid,
            from_vertex=vertex_position,
            transition_position=transition_position,
        )

        if next_vertex is None:
            continue

        if is_free_vertex(grid, next_vertex[0], next_vertex[1]):
            neighbors.append(next_vertex)

    return neighbors


def get_destination_vertex_if_traversable(grid, from_vertex, transition_position):
    i, j = transition_position
    transition_value = grid[i][j]

    if is_horizontal_slot(i, j):
        left_vertex, right_vertex = get_adjacent_vertices(i, j)

        if transition_value == HorizontalTransition.RIGHT and from_vertex == left_vertex:
            return right_vertex
        if transition_value == HorizontalTransition.LEFT and from_vertex == right_vertex:
            return left_vertex
        if transition_value == HorizontalTransition.LEFT_AND_RIGHT:
            if from_vertex == left_vertex:
                return right_vertex
            if from_vertex == right_vertex:
                return left_vertex
        return None

    upper_vertex, lower_vertex = get_adjacent_vertices(i, j)

    if transition_value == VerticalTransition.DOWN and from_vertex == upper_vertex:
        return lower_vertex
    if transition_value == VerticalTransition.UP and from_vertex == lower_vertex:
        return upper_vertex
    if transition_value == VerticalTransition.UP_AND_DOWN:
        if from_vertex == upper_vertex:
            return lower_vertex
        if from_vertex == lower_vertex:
            return upper_vertex
    return None