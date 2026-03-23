
def print_grid(grid):
    for row in grid:
        print(' '.join(str(cell) for cell in row))
    print("--------------------------------------")


def print_astar_frames(astar_frames):
    for frame in astar_frames:
        print_grid(frame)
