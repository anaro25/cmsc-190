from pathlib import Path

from cyclic_test.core.composite_elements import (
    HorizontalTransition,
    Special,
    Vertex,
    VerticalTransition,
)
from cyclic_test.paths import MAPF_RUNS_DIR


def convert_element_to_log_symbol(element):
    # Agent / target overlays
    if isinstance(element, str) and len(element) == 1:
        return element

    if element == Vertex.FREE_SPACE:
        return "o"
    elif element == Vertex.OBSTACLE:
        return "#"

    elif element == Special.PLACEHOLDER:
        return " "

    elif element == VerticalTransition.UP:
        return "↑"
    elif element == VerticalTransition.DOWN:
        return "↓"
    elif element == VerticalTransition.UP_AND_DOWN:
        return "↕"
    elif element == VerticalTransition.NO_VERTICAL_TRANSITION:
        return " "

    elif element == HorizontalTransition.LEFT:
        return "←"
    elif element == HorizontalTransition.RIGHT:
        return "→"
    elif element == HorizontalTransition.LEFT_AND_RIGHT:
        return "↔"
    elif element == HorizontalTransition.NO_HORIZONTAL_TRANSITION:
        return " "

    return str(element)
from cyclic_test.paths import MAPF_RUNS_DIR


def write_mapf_frame(frame, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        for row in frame:
            row_symbols = [convert_element_to_log_symbol(element) for element in row]
            file.write(" ".join(row_symbols) + "\n")
from cyclic_test.paths import MAPF_RUNS_DIR


def write_mapf_frames(map_name, frames, output_root=MAPF_RUNS_DIR):
    map_output_dir = Path(output_root) / map_name
    map_output_dir.mkdir(parents=True, exist_ok=True)

    for time_step, frame in enumerate(frames):
        output_path = map_output_dir / f"frame_{time_step:03d}.xml"
        write_mapf_frame(frame, output_path)