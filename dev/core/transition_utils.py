
from dev.core.composite_elements import HorizontalTransition, VerticalTransition


ONE_WAY_HORIZONTAL_TRANSITIONS = {
    HorizontalTransition.LEFT,
    HorizontalTransition.RIGHT,
}

BIDIRECTIONAL_HORIZONTAL_TRANSITIONS = {
    HorizontalTransition.LEFT_AND_RIGHT,
}

NO_HORIZONTAL_TRANSITIONS = {
    HorizontalTransition.NO_HORIZONTAL_TRANSITION,
}

ONE_WAY_VERTICAL_TRANSITIONS = {
    VerticalTransition.UP,
    VerticalTransition.DOWN,
}

BIDIRECTIONAL_VERTICAL_TRANSITIONS = {
    VerticalTransition.UP_AND_DOWN,
}

NO_VERTICAL_TRANSITIONS = {
    VerticalTransition.NO_VERTICAL_TRANSITION,
}


REMOVED_HORIZONTAL = object()
REMOVED_VERTICAL = object()


def is_horizontal_slot(i, j):
    return i % 2 == 0 and j % 2 == 1


def is_vertical_slot(i, j):
    return i % 2 == 1 and j % 2 == 0


def is_transition_slot(i, j):
    return is_horizontal_slot(i, j) or is_vertical_slot(i, j)


def is_vertex_slot(i, j):
    return i % 2 == 0 and j % 2 == 0


def is_in_bounds(grid, i, j):
    return 0 <= i < len(grid) and 0 <= j < len(grid[0])


def get_adjacent_vertices(i, j):
    if is_horizontal_slot(i, j):
        return (i, j - 1), (i, j + 1)
    return (i - 1, j), (i + 1, j)


def get_removed_marker(i, j):
    if is_horizontal_slot(i, j):
        return REMOVED_HORIZONTAL
    return REMOVED_VERTICAL


def is_removed_marker(value):
    return value is REMOVED_HORIZONTAL or value is REMOVED_VERTICAL


def is_one_way_transition(value):
    return value in ONE_WAY_HORIZONTAL_TRANSITIONS or value in ONE_WAY_VERTICAL_TRANSITIONS


def is_no_transition(value):
    return value in NO_HORIZONTAL_TRANSITIONS or value in NO_VERTICAL_TRANSITIONS


def is_bidirectional_transition(value):
    return value in BIDIRECTIONAL_HORIZONTAL_TRANSITIONS or value in BIDIRECTIONAL_VERTICAL_TRANSITIONS


def get_no_transition_for_slot(i, j):
    if is_horizontal_slot(i, j):
        return HorizontalTransition.NO_HORIZONTAL_TRANSITION
    return VerticalTransition.NO_VERTICAL_TRANSITION


def get_bidirectional_transition_for_slot(i, j):
    if is_horizontal_slot(i, j):
        return HorizontalTransition.LEFT_AND_RIGHT
    return VerticalTransition.UP_AND_DOWN


def is_perpendicular(move_a, move_b):
    return move_a[0] * move_b[0] + move_a[1] * move_b[1] == 0
