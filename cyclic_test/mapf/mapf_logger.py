from pathlib import Path

from cyclic_test.paths import MAPF_RUNS_DIR
from cyclic_test.utils.log_symbols import convert_element_to_log_symbol


def write_mapf_frame(frame, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        for row in frame:
            row_symbols = [convert_element_to_log_symbol(element) for element in row]
            file.write(" ".join(row_symbols) + "\n")


def write_mapf_frames(map_name, frames, output_root=MAPF_RUNS_DIR):
    map_output_dir = Path(output_root) / map_name
    map_output_dir.mkdir(parents=True, exist_ok=True)

    for time_step, frame in enumerate(frames):
        output_path = map_output_dir / f"frame_{time_step:03d}.xml"
        write_mapf_frame(frame, output_path)
