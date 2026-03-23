
def overlay_classical_transitions(composite_grid):
    n = len(composite_grid)
    classical_composite_grid = [row[:] for row in composite_grid]

    for r in range(n):
        for c in range(n):
            # horizontal transition cells
            if r % 2 == 0 and c % 2 == 1:
                classical_composite_grid[r][c] = '↔'

            # vertical transition cells
            elif r % 2 == 1 and c % 2 == 0:
                classical_composite_grid[r][c] = '↕'

    return classical_composite_grid
	

def overlay_cyclic_transitions(composite_grid):
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
				if r == n - 1:
					# bottom row when bottom row is a left-arrow row
					if c % 4 == 1:
						cyclic_composite_grid[r][c] = '←'
				else:
					if c % 2 == 1:
						cyclic_composite_grid[r][c] = '←'

			# rows like: ↑ · ↓ · ↑ · ↓ ...
			elif r % 4 == 1:
				if c % 4 == 0 and c != n - 1:
					cyclic_composite_grid[r][c] = '↑'
				elif c % 4 == 2:
					cyclic_composite_grid[r][c] = '↓'

			# rows like: · · ↓ · ↑ · ↓ · ↑
			elif r % 4 == 3:
				if c % 4 == 2 and c != n - 1:
					cyclic_composite_grid[r][c] = '↓'
				elif c % 4 == 0 and c != 0:
					cyclic_composite_grid[r][c] = '↑'

	return cyclic_composite_grid