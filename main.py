from .composite_grid_builder import add_cyclic_map, overlay_base_grid
from .tester import print_grid


def main():
    base_grid = [
        ['o', 'o', 'o', 'o', '#'],
        ['o', 'o', 'o', 'o', 'o'],
        ['o', 'o', 'o', 'o', 'o'],
        ['o', 'o', 'o', 'o', 'o'],
        ['#', 'o', 'o', 'o', 'o']
    ]

    base_size = len(base_grid)
    comp_size = (2 * base_size) - 1
    
    composite_grid = [['·' for _ in range(comp_size)] for _ in range(comp_size)]
    composite_grid = add_cyclic_map(composite_grid)
    composite_grid = overlay_base_grid(composite_grid, base_grid)

    print_grid(composite_grid)


if __name__ == "__main__":
    main()