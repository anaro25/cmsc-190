from .composite_grid_builder import add_cyclic_map


def print_grid(grid):
    for row in grid:
        print(' '.join(str(cell) for cell in row))


def print_cyclic_various_sizes():
    test_sizes = [3, 5, 7, 9]

    for comp_size in test_sizes:
        print(f"composite_grid size = {comp_size}x{comp_size}")

        composite_grid = [['·' for _ in range(comp_size)] for _ in range(comp_size)]
        composite_grid = add_cyclic_map(composite_grid)

        print_grid(composite_grid)
        print()