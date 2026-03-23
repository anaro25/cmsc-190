import random
from .astar_runner import run_astar


def _get_traversable_positions(grid):
    traversable_positions = []

    for r in range(0, len(grid), 2):
        for c in range(0, len(grid[r]), 2):
            if grid[r][c] == 'o':
                traversable_positions.append((r, c))

    return traversable_positions


def _choose_random_position(grid, excluded_positions=None):
    if excluded_positions is None:
        excluded_positions = set()

    candidates = [
        position
        for position in _get_traversable_positions(grid)
        if position not in excluded_positions
    ]

    if not candidates:
        raise ValueError("No valid traversable position is available.")

    return random.choice(candidates)


def _build_setup_grid(base_grid, start, goal):
    setup_grid = [row[:] for row in base_grid]
    setup_grid[start[0]][start[1]] = 'A'
    setup_grid[goal[0]][goal[1]] = 'B'
    return setup_grid


def run_astar_successive_targets(composite_grid, num_targets=3, rng_seed=None):
    if rng_seed is not None:
        random.seed(rng_seed)

    all_frames = []

    # generate the initial agent position only once
    current_start = _choose_random_position(composite_grid)

    for _ in range(num_targets):
        frames = []
        attempts = 0

        while not frames:
            attempts += 1

            if attempts > 100:
                raise ValueError(
                    "Could not find a reachable random target after many attempts."
                )

            target = _choose_random_position(
                composite_grid,
                excluded_positions={current_start}
            )

            setup_grid = _build_setup_grid(composite_grid, current_start, target)
            frames = run_astar(setup_grid)

        all_frames.extend(frames)

        # next setup starts where the previous one ended
        current_start = target

    return all_frames