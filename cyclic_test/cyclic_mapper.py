from composite_elements import HorizontalTransition, VerticalTransition


def apply_classical_mapping(base_maps):
    classical_maps = {}

    for map_name, base_map in base_maps.items():
        classical_maps[map_name] = overlay_classical_transitions(base_map)

    return classical_maps


def apply_cyclic_mapping(base_maps):
    cyclic_maps = {}

    for map_name, base_map in base_maps.items():
        cyclic_maps[map_name] = overlay_cyclic_transitions(base_map)

    return cyclic_maps


def overlay_classical_transitions(composite_grid):
    num_rows = len(composite_grid)
    num_cols = len(composite_grid[0])

    classical_composite_grid = [row[:] for row in composite_grid]

    for i in range(num_rows):
        for j in range(num_cols):
            # horizontal transition cells
            if i % 2 == 0 and j % 2 == 1:
                classical_composite_grid[i][j] = HorizontalTransition.LEFT_AND_RIGHT

            # vertical transition cells
            elif i % 2 == 1 and j % 2 == 0:
                classical_composite_grid[i][j] = VerticalTransition.UP_AND_DOWN

    return classical_composite_grid


def overlay_cyclic_transitions(composite_grid):
    num_rows = len(composite_grid)
    num_cols = len(composite_grid[0])

    cyclic_composite_grid = [row[:] for row in composite_grid]

    for i in range(num_rows):
        for j in range(num_cols):

            # rows with right transitions
            if i % 4 == 0:
                if i == 0:
                    # top row
                    if j % 4 == 1:
                        cyclic_composite_grid[i][j] = HorizontalTransition.RIGHT
                elif i == num_rows - 1:
                    # bottom row
                    if j % 4 == 3:
                        cyclic_composite_grid[i][j] = HorizontalTransition.RIGHT
                else:
                    # middle rows
                    if j % 2 == 1:
                        cyclic_composite_grid[i][j] = HorizontalTransition.RIGHT

            # rows with left transitions
            elif i % 4 == 2:
                if i == num_rows - 1:
                    # bottom row when bottom row is a left-transition row
                    if j % 4 == 1:
                        cyclic_composite_grid[i][j] = HorizontalTransition.LEFT
                else:
                    if j % 2 == 1:
                        cyclic_composite_grid[i][j] = HorizontalTransition.LEFT

            # rows like: UP · DOWN · UP · DOWN ...
            elif i % 4 == 1:
                if j % 4 == 0 and j != num_cols - 1:
                    cyclic_composite_grid[i][j] = VerticalTransition.UP
                elif j % 4 == 2:
                    cyclic_composite_grid[i][j] = VerticalTransition.DOWN

            # rows like: · · DOWN · UP · DOWN · UP
            elif i % 4 == 3:
                if j % 4 == 2 and j != num_cols - 1:
                    cyclic_composite_grid[i][j] = VerticalTransition.DOWN
                elif j % 4 == 0 and j != 0:
                    cyclic_composite_grid[i][j] = VerticalTransition.UP

    return cyclic_composite_grid