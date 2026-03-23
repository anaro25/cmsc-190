from .transitions_overlayer import overlay_classical_transitions, overlay_cyclic_transitions

def build_composite_grids(base_grid):

	base_size = len(base_grid)
	comp_size = (2 * base_size) - 1
	
	# populate grid with middle dots as placeholder
	composite_grid = [['·' for _ in range(comp_size)] for _ in range(comp_size)]
	
	# overlay base grid
	composite_grid = overlay_base_grid(composite_grid, base_grid)
	
	# overlay transitions
	classical_composite_grid = overlay_classical_transitions(composite_grid)
	cyclic_composite_grid = overlay_cyclic_transitions(composite_grid)
	
	return classical_composite_grid, cyclic_composite_grid


def overlay_base_grid(composite_grid, base_grid):
	updated_composite_grid = [row[:] for row in composite_grid]

	for r in range(len(base_grid)):
		for c in range(len(base_grid[r])):
			updated_composite_grid[2 * r][2 * c] = base_grid[r][c]

	return updated_composite_grid

