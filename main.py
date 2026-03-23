from .base_grid_getter import get_base_grid
from .composite_grid_builder import build_composite_grids

from .tester import print_grid
from .experiment_runner import run_astar_successive_targets


def main():

    base_grid = get_base_grid()

    classical_composite_grid, cyclic_composite_grid = build_composite_grids(base_grid)

    astar_frames = run_astar_successive_targets(
        cyclic_composite_grid,
        num_targets=3
    )

    for frame in astar_frames:
        print_grid(frame)


if __name__ == "__main__":
    main()