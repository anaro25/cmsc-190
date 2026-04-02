from pathlib import Path

from composite_elements import (
    Vertex,
    Special,
    VerticalTransition,
    HorizontalTransition,
)


def convert_element_to_log_symbol(element):
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


def write_composite_map(composite_map, output_path):
    output_path = Path(output_path)

    with output_path.open("w", encoding="utf-8") as file:
        for row in composite_map:
            row_symbols = [convert_element_to_log_symbol(element) for element in row]
            file.write(" ".join(row_symbols) + "\n")


def write_cyclic_composites(cyclic_maps, output_dir="cyclic_logs"):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for map_name, composite_map in cyclic_maps.items():
        output_path = output_dir / f"{map_name}_cyclic.xml"
        write_composite_map(composite_map, output_path)