from .composite_grid_builder import add_cyclic_map
from .tester import print_cyclic_various_sizes

def print_grid(grid):
    for row in grid:
        print(' '.join(str(cell) for cell in row))


def main():
    base_grid = [
        ['0', '0', '0', '0', '1'],
        ['0', '0', '0', '0', '0'],
        ['0', '0', '0', '0', '0'],
        ['0', '0', '0', '0', '0'],
        ['1', '0', '0', '0', '0']
    ]

    base_size = len(base_grid)
    comp_size = (2 * base_size) - 1

    composite_grid = [['·' for _ in range(comp_size)] for _ in range(comp_size)]
    cyclic_composite_grid = add_cyclic_map(composite_grid)

    print_grid(cyclic_composite_grid)


if __name__ == "__main__":
    main()