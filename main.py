from .base_grid_getter import get_base_grid
from .composite_grid_builder import build_composite_grids

from .tester import print_grid
from .astar_runner import run_astar

def main():
	
	base_grid = get_base_grid()
	
	classical_composite_grid, cyclic_composite_grid = build_composite_grids(base_grid)
	
	print_grid(classical_composite_grid)
	print_grid(cyclic_composite_grid)
	
	# assign start and target cells manually
	# composite_grid[4][0] = 'A'
	# composite_grid[2][6] = 'B'
	
	# get the series of composite grids that show A* from start to finish
	# astar_frames = run_astar(composite_grid)
	
	# for frame in astar_frames:
	# 	print_grid(frame)

if __name__ == "__main__":
	main()
	