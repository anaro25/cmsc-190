
When to_generate = "raw_data", the following folders are generated:

* metrics_data/
	* This contains all the numerical data that will be presented in the Results chapter of the manuscript.
	* This will be the input to the LLM which writes the Results chapter.
	
* metrics_data_inspection/
	* This contains the simplified data for the author's immediate checking. It won't be used elsewhere.

* frame_by_frame/
	* This contains the frame by frame information of a single successful run for each map config selected.
	* This will be read by the program when to_generate = "visualization".

* terminal_logs/
	* This records the terminal output during the running of the program.

