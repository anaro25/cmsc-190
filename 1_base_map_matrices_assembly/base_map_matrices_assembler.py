from project_level_modules.composite_matrix_elements import Vertex

def assemble_base_map_matrices():
	# for now, declare as 1D list
	port_1_base_map_matrix = []
	port_2_base_map_matrix = []
	port_3_base_map_matrix = []
	campus_base_map_matrix = []
	
	base_map_matrices = [
		port_1_base_map_matrix,
		port_2_base_map_matrix,
		port_3_base_map_matrix,
		campus_base_map_matrix
	]
	
	# access the PNG images
		# assign a 2D list value to each of the base map matrices
			# if the pixel is white, store enum constant Vertex.FREE_SPACE
			# if the pixel is black, store enum constant Vertex.OBSTACLE
	
	# logging (print the matrices (2D lists))
		# access the 2D lists (not the images)
		# print free spaces as "o" and obstacles as "#"
			# print the elements one space apart
		# don't print in terminal. Just write in dedicated files inside 2_base_map_matrix_logs
			
	return base_map_matrices
