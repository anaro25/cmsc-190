from .base_grid_getter import get_base_grid
from .composite_grid_builder import build_composite_grids

from .tester import print_astar_frames
from .experiment_runner import run_astar_successive_targets


def run_classical_astar(classical_composite_grid, num_targets):
	
	classical_astar_frames = run_astar_successive_targets(
		classical_composite_grid,
		num_targets
	)

	print_astar_frames(classical_astar_frames)


def run_cyclic_astar(cyclic_composite_grid, num_targets):
	
	cyclic_astar_frames = run_astar_successive_targets(
		cyclic_composite_grid,
		num_targets
	)

	print_astar_frames(cyclic_astar_frames)
	

def main():

	base_grid = get_base_grid()
	classical_composite_grid, cyclic_composite_grid = build_composite_grids(base_grid)
	
	num_targets = 3
	
	run_classical_astar(classical_composite_grid, num_targets)
	# print('*' * 50)
	# run_cyclic_astar(cyclic_composite_grid, num_targets)

if __name__ == "__main__":
	main()