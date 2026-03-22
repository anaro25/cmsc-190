from .composite_grid_builder import build_composite_grid
from .tester import print_grid
from .astar_runner import run_astar

def main():
	composite_grid = build_composite_grid()
	print_grid(composite_grid)
	
	# assign start and target cells manually
	composite_grid[6][2] = 'A'
	composite_grid[2][6] = 'B'
	print_grid(composite_grid)
	
	# get the series of composite grids that show A* from start to finish
	astar_frames = run_astar(composite_grid)

if __name__ == "__main__":
	main()