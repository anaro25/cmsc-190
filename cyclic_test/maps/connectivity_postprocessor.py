# connectivity_postprocessor.py

from collections import deque

from cyclic_test.core.composite_elements import HorizontalTransition, VerticalTransition, Vertex
from cyclic_test.core.transition_utils import (
    get_adjacent_vertices,
    get_bidirectional_transition_for_slot,
    get_no_transition_for_slot,
    is_bidirectional_transition,
    is_horizontal_slot,
    is_in_bounds,
    is_no_transition,
    is_transition_slot,
    is_vertex_slot,
)


def reduce_excess_bidirectionals_and_restore_connectivity(cyclic_grid):
    """
    Post-processes a cyclic composite grid in two phases:

    Phase 1:
        Visit every bidirectional transition.
        If its two endpoint vertices remain mutually reachable through
        some alternative path when that transition is ignored, remove it.

    Phase 2:
        Visit every empty transition slot.
        If its two endpoint vertices are not mutually reachable at all,
        add a bidirectional there.

    This helps:
        1. reduce excess bidirectional transitions
        2. restore connectivity for isolated or disconnected free vertices
    """
    processed_grid = [row[:] for row in cyclic_grid]

    remove_redundant_bidirectionals(processed_grid)
    restore_required_connectivity(processed_grid)

    return processed_grid


def remove_redundant_bidirectionals(grid):
    bidirectional_positions = collect_bidirectional_positions(grid)

    for transition_position in bidirectional_positions:
        vertex_a, vertex_b = get_adjacent_vertices(*transition_position)

        if not endpoints_are_free_vertices(grid, vertex_a, vertex_b):
            continue

        if are_mutually_reachable(
            grid,
            start_vertex=vertex_a,
            goal_vertex=vertex_b,
            ignored_transition=transition_position,
        ):
            i, j = transition_position
            grid[i][j] = get_no_transition_for_slot(i, j)


def restore_required_connectivity(grid):
    empty_transition_positions = collect_empty_transition_positions(grid)

    for transition_position in empty_transition_positions:
        vertex_a, vertex_b = get_adjacent_vertices(*transition_position)

        if not endpoints_are_free_vertices(grid, vertex_a, vertex_b):
            continue

        if not are_mutually_reachable(
            grid,
            start_vertex=vertex_a,
            goal_vertex=vertex_b,
            ignored_transition=None,
        ):
            i, j = transition_position
            grid[i][j] = get_bidirectional_transition_for_slot(i, j)


def collect_bidirectional_positions(grid):
    positions = []

    for i in range(len(grid)):
        for j in range(len(grid[i])):
            if not is_transition_slot(i, j):
                continue
            if is_bidirectional_transition(grid[i][j]):
                positions.append((i, j))

    return positions


def collect_empty_transition_positions(grid):
    positions = []

    for i in range(len(grid)):
        for j in range(len(grid[i])):
            if not is_transition_slot(i, j):
                continue
            if is_no_transition(grid[i][j]):
                positions.append((i, j))

    return positions


def are_mutually_reachable(grid, start_vertex, goal_vertex, ignored_transition=None):
    """
    Mutual reachability means:
        start_vertex can reach goal_vertex
        and
        goal_vertex can reach start_vertex
    """
    return (
        is_reachable(grid, start_vertex, goal_vertex, ignored_transition)
        and is_reachable(grid, goal_vertex, start_vertex, ignored_transition)
    )


def is_reachable(grid, start_vertex, goal_vertex, ignored_transition=None):
    if start_vertex == goal_vertex:
        return True

    if not is_free_vertex(grid, *start_vertex):
        return False
    if not is_free_vertex(grid, *goal_vertex):
        return False

    visited = set()
    queue = deque([start_vertex])
    visited.add(start_vertex)

    while queue:
        current_vertex = queue.popleft()

        for next_vertex in get_outgoing_neighbors(
            grid,
            current_vertex,
            ignored_transition=ignored_transition,
        ):
            if next_vertex in visited:
                continue

            if next_vertex == goal_vertex:
                return True

            visited.add(next_vertex)
            queue.append(next_vertex)

    return False


def get_outgoing_neighbors(grid, vertex_position, ignored_transition=None):
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

        if ignored_transition is not None and transition_position == ignored_transition:
            continue

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

        neighbors.append(next_vertex)

    return neighbors


def get_destination_vertex_if_traversable(grid, from_vertex, transition_position):
    i, j = transition_position
    transition_value = grid[i][j]

    if is_horizontal_slot(i, j):
        left_vertex = (i, j - 1)
        right_vertex = (i, j + 1)

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

    upper_vertex = (i - 1, j)
    lower_vertex = (i + 1, j)

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


def endpoints_are_free_vertices(grid, vertex_a, vertex_b):
    return is_free_vertex(grid, *vertex_a) and is_free_vertex(grid, *vertex_b)


def is_free_vertex(grid, i, j):
    if not is_in_bounds(grid, i, j):
        return False
    if not is_vertex_slot(i, j):
        return False
    return grid[i][j] == Vertex.FREE_SPACE