from project_level_modules.composite_matrix_elements import Vertex


def get_num_d_obstacles(base_maps):
	num_free_spaces = get_num_free_spaces(base_maps)
	density = 0.5 # constant density = 50%
	
	num_d_obstacles = [] # 2D list
	
	for num_free_space in num_free_spaces:
		num_d_obstacle = 
		num_d_obstacles.append(num_d_obstacle)
	
	return num_d_obstacles


def get_num_free_spaces(base_maps):
    num_free_spaces = []

    for base_map in base_maps:
        count = 0

        for row in base_map:
            for cell in row:
                if cell == Vertex.FREE_SPACE:
                    count += 1

        num_free_spaces.append(count)

    return num_free_spaces
