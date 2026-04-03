
from cyclic_test.core.composite_elements import HorizontalTransition, VerticalTransition, Vertex
from cyclic_test.core.transition_utils import (
    get_adjacent_vertices,
    get_bidirectional_transition_for_slot,
    get_no_transition_for_slot,
    get_removed_marker,
    is_horizontal_slot,
    is_in_bounds,
    is_one_way_transition,
    is_perpendicular,
    is_transition_slot,
)


MOVE_BY_TRANSITION = {
    HorizontalTransition.RIGHT: (0, 1),
    HorizontalTransition.LEFT: (0, -1),
    VerticalTransition.DOWN: (1, 0),
    VerticalTransition.UP: (-1, 0),
}


def remove_obstacle_connected_cyclic_transitions(cyclic_grid):
    cleaned_grid = [row[:] for row in cyclic_grid]
    original_cyclic_grid = [row[:] for row in cyclic_grid]

    removed_positions = mark_obstacle_connected_transitions(
        cleaned_grid,
        original_cyclic_grid,
    )

    repair_disrupted_local_cycles(
        cleaned_grid,
        original_cyclic_grid,
        removed_positions,
    )

    finalize_removed_transitions(cleaned_grid, removed_positions)

    return cleaned_grid


def mark_obstacle_connected_transitions(cleaned_grid, original_cyclic_grid):
    removed_positions = set()

    for i in range(len(cleaned_grid)):
        for j in range(len(cleaned_grid[i])):
            if not is_transition_slot(i, j):
                continue

            transition_value = original_cyclic_grid[i][j]
            if not is_one_way_transition(transition_value):
                continue

            vertex_a, vertex_b = get_adjacent_vertices(i, j)
            value_a = cleaned_grid[vertex_a[0]][vertex_a[1]]
            value_b = cleaned_grid[vertex_b[0]][vertex_b[1]]

            if value_a == Vertex.OBSTACLE or value_b == Vertex.OBSTACLE:
                cleaned_grid[i][j] = get_removed_marker(i, j)
                removed_positions.add((i, j))

    return removed_positions


def repair_disrupted_local_cycles(cleaned_grid, original_cyclic_grid, removed_positions):
    repaired_positions = set()

    for removed_position in removed_positions:
        local_cycle = trace_local_cycle(original_cyclic_grid, removed_position)

        for transition_position in local_cycle:
            if transition_position in removed_positions:
                continue
            if transition_position in repaired_positions:
                continue

            i, j = transition_position
            transition_value = cleaned_grid[i][j]

            if is_one_way_transition(transition_value):
                cleaned_grid[i][j] = get_bidirectional_transition_for_slot(i, j)
                repaired_positions.add(transition_position)


def finalize_removed_transitions(cleaned_grid, removed_positions):
    for i, j in removed_positions:
        cleaned_grid[i][j] = get_no_transition_for_slot(i, j)


def trace_local_cycle(original_cyclic_grid, start_transition_position):
    cycle = []
    current_transition = start_transition_position
    current_move = get_transition_move(original_cyclic_grid, current_transition)

    for _ in range(4):
        cycle.append(current_transition)

        target_vertex = get_transition_target_vertex(current_transition, current_move)
        next_transition, next_move = get_turning_transition_from_vertex(
            original_cyclic_grid,
            target_vertex,
            current_move,
            exclude_transition=current_transition,
        )

        current_transition = next_transition
        current_move = next_move

        if current_transition == start_transition_position:
            break

    return cycle


def get_transition_move(original_cyclic_grid, transition_position):
    i, j = transition_position
    transition_value = original_cyclic_grid[i][j]

    if transition_value not in MOVE_BY_TRANSITION:
        raise ValueError(
            f"Transition at {transition_position} is not a one-way cyclic transition: {transition_value}"
        )

    return MOVE_BY_TRANSITION[transition_value]


def get_transition_target_vertex(transition_position, move):
    i, j = transition_position
    di, dj = move

    if is_horizontal_slot(i, j):
        if dj == 1:
            return (i, j + 1)
        if dj == -1:
            return (i, j - 1)
    else:
        if di == 1:
            return (i + 1, j)
        if di == -1:
            return (i - 1, j)

    raise ValueError(f"Invalid move {move} for transition {transition_position}.")


def get_turning_transition_from_vertex(
    original_cyclic_grid,
    vertex_position,
    incoming_move,
    exclude_transition,
):
    vertex_i, vertex_j = vertex_position
    candidate_positions = [
        (vertex_i, vertex_j - 1),
        (vertex_i, vertex_j + 1),
        (vertex_i - 1, vertex_j),
        (vertex_i + 1, vertex_j),
    ]

    for candidate in candidate_positions:
        candidate_i, candidate_j = candidate

        if candidate == exclude_transition:
            continue
        if not is_in_bounds(original_cyclic_grid, candidate_i, candidate_j):
            continue
        if not is_transition_slot(candidate_i, candidate_j):
            continue
        if not can_depart_from_vertex(original_cyclic_grid, candidate, vertex_position):
            continue

        candidate_move = get_move_from_vertex_through_transition(
            original_cyclic_grid,
            candidate,
            vertex_position,
        )

        if is_perpendicular(incoming_move, candidate_move):
            return candidate, candidate_move

    raise ValueError(
        f"Could not continue local cycle from vertex {vertex_position}."
    )


def can_depart_from_vertex(original_cyclic_grid, transition_position, vertex_position):
    i, j = transition_position
    transition_value = original_cyclic_grid[i][j]

    if is_horizontal_slot(i, j):
        left_vertex = (i, j - 1)
        right_vertex = (i, j + 1)

        if transition_value == HorizontalTransition.RIGHT:
            return vertex_position == left_vertex
        if transition_value == HorizontalTransition.LEFT:
            return vertex_position == right_vertex
        return False

    upper_vertex = (i - 1, j)
    lower_vertex = (i + 1, j)

    if transition_value == VerticalTransition.DOWN:
        return vertex_position == upper_vertex
    if transition_value == VerticalTransition.UP:
        return vertex_position == lower_vertex
    return False


def get_move_from_vertex_through_transition(
    original_cyclic_grid,
    transition_position,
    vertex_position,
):
    i, j = transition_position
    transition_value = original_cyclic_grid[i][j]

    if is_horizontal_slot(i, j):
        left_vertex = (i, j - 1)
        right_vertex = (i, j + 1)

        if transition_value == HorizontalTransition.RIGHT and vertex_position == left_vertex:
            return (0, 1)
        if transition_value == HorizontalTransition.LEFT and vertex_position == right_vertex:
            return (0, -1)
    else:
        upper_vertex = (i - 1, j)
        lower_vertex = (i + 1, j)

        if transition_value == VerticalTransition.DOWN and vertex_position == upper_vertex:
            return (1, 0)
        if transition_value == VerticalTransition.UP and vertex_position == lower_vertex:
            return (-1, 0)

    raise ValueError(
        f"Vertex {vertex_position} cannot depart through transition {transition_position}."
    )
