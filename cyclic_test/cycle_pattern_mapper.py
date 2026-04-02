
from composite_elements import HorizontalTransition, VerticalTransition
from transition_utils import is_horizontal_slot, is_vertical_slot


def initialize_transition_elements(composite_grid):
    initialized_grid = [row[:] for row in composite_grid]

    for i in range(len(initialized_grid)):
        for j in range(len(initialized_grid[i])):
            if is_horizontal_slot(i, j):
                initialized_grid[i][j] = HorizontalTransition.NO_HORIZONTAL_TRANSITION
            elif is_vertical_slot(i, j):
                initialized_grid[i][j] = VerticalTransition.NO_VERTICAL_TRANSITION

    return initialized_grid


def overlay_classical_transitions(composite_grid):
    classical_grid = initialize_transition_elements(composite_grid)

    for i in range(len(classical_grid)):
        for j in range(len(classical_grid[i])):
            if is_horizontal_slot(i, j):
                classical_grid[i][j] = HorizontalTransition.LEFT_AND_RIGHT
            elif is_vertical_slot(i, j):
                classical_grid[i][j] = VerticalTransition.UP_AND_DOWN

    return classical_grid


def overlay_cyclic_transitions(composite_grid):
    cyclic_grid = initialize_transition_elements(composite_grid)
    num_rows = len(cyclic_grid)
    num_cols = len(cyclic_grid[0])

    for i in range(num_rows):
        for j in range(num_cols):
            if i % 4 == 0:
                if i == 0:
                    if j % 4 == 1:
                        cyclic_grid[i][j] = HorizontalTransition.RIGHT
                elif i == num_rows - 1:
                    if j % 4 == 3:
                        cyclic_grid[i][j] = HorizontalTransition.RIGHT
                elif j % 2 == 1:
                    cyclic_grid[i][j] = HorizontalTransition.RIGHT

            elif i % 4 == 2:
                if i == num_rows - 1:
                    if j % 4 == 1:
                        cyclic_grid[i][j] = HorizontalTransition.LEFT
                elif j % 2 == 1:
                    cyclic_grid[i][j] = HorizontalTransition.LEFT

            elif i % 4 == 1:
                if j % 4 == 0 and j != num_cols - 1:
                    cyclic_grid[i][j] = VerticalTransition.UP
                elif j % 4 == 2:
                    cyclic_grid[i][j] = VerticalTransition.DOWN

            elif i % 4 == 3:
                if j % 4 == 2 and j != num_cols - 1:
                    cyclic_grid[i][j] = VerticalTransition.DOWN
                elif j % 4 == 0 and j != 0:
                    cyclic_grid[i][j] = VerticalTransition.UP

    return cyclic_grid


def apply_classical_mapping(base_maps):
    classical_maps = {}

    for map_name, base_map in base_maps.items():
        classical_maps[map_name] = overlay_classical_transitions(base_map)

    return classical_maps
