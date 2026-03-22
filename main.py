def print_grid(grid):
    for row in grid:
        print(' '.join(str(cell) for cell in row))


def add_cyclic_map(composite_grid):
    n = len(composite_grid)
    cyclic_composite_grid = [row[:] for row in composite_grid]

    for r in range(n):
        for c in range(n):

            # rows with right arrows
            if r % 4 == 0:
                if r == 0:
                    # top row
                    if c % 4 == 1:
                        cyclic_composite_grid[r][c] = '→'
                elif r == n - 1:
                    # bottom row
                    if c % 4 == 3:
                        cyclic_composite_grid[r][c] = '→'
                else:
                    # middle rows
                    if c % 2 == 1:
                        cyclic_composite_grid[r][c] = '→'

            # rows with left arrows
            elif r % 4 == 2:
                if c % 2 == 1:
                    cyclic_composite_grid[r][c] = '←'

            # rows like: ↑ · ↓ · ↑ · ↓ · ·
            elif r % 4 == 1:
                if c % 4 == 0 and c != n - 1:
                    cyclic_composite_grid[r][c] = '↑'
                elif c % 4 == 2:
                    cyclic_composite_grid[r][c] = '↓'

            # rows like: · · ↓ · ↑ · ↓ · ↑
            elif r % 4 == 3:
                if c % 4 == 2:
                    cyclic_composite_grid[r][c] = '↓'
                elif c % 4 == 0 and c != 0:
                    cyclic_composite_grid[r][c] = '↑'

    return cyclic_composite_grid


def main():
    # for now, let's manually initialize the base grid
    base_grid = [
        ['0', '0', '0', '0', '1'],
        ['0', '0', '0', '0', '0'],
        ['0', '0', '0', '0', '0'],
        ['0', '0', '0', '0', '0'],
        ['1', '0', '0', '0', '0']
    ]

    base_size = len(base_grid)
    comp_size = (2 * base_size) - 1

    # initialize the composite grid
    composite_grid = [['·' for _ in range(comp_size)] for _ in range(comp_size)]

    cyclic_composite_grid = add_cyclic_map(composite_grid)

    print_grid(cyclic_composite_grid)


if __name__ == "__main__":
    main()