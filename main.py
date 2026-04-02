from base_map_assembly.base_map_assembler import assemble_base_maps
from dynamic_loop_sequence_assembly.dynamic_loop_sequence_assembler import assemble_dynamic_loop_sequences

def main():
	base_maps = assemble_base_maps()
	
	dynamic_loop_sequences = assemble_dynamic_loop_sequences(base_maps)
	
if __name__ == "__main__":
	main()
