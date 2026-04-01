from _1_base_map_matrices_assembly.base_map_matrices_assembler import assemble_base_map_matrices

def main():
	base_map_matrices = assemble_base_map_matrices()
	
	# vertex map = base map + additional obstacles (if any)
	# dynamic_vertex_map_looping_matrices = assemble_dynamic_vertex_map_looping_matrices()
	
if __name__ == "__main__":
	main()
