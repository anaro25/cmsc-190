from pathlib import Path

from cyclic_test.paths import CLASSICAL_LOGS_DIR, CYCLIC_LOGS_DIR
from cyclic_test.utils.log_symbols import convert_element_to_log_symbol


def write_composite_map(composite_map, output_path):
    output_path = Path(output_path)

    with output_path.open("w", encoding="utf-8") as file:
        for row in composite_map:
            row_symbols = [convert_element_to_log_symbol(element) for element in row]
            file.write(" ".join(row_symbols) + "\n")


def write_cyclic_composites(cyclic_maps, output_dir=CYCLIC_LOGS_DIR):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for map_name, composite_map in cyclic_maps.items():
        output_path = output_dir / f"{map_name}_cyclic.xml"
        write_composite_map(composite_map, output_path)


def write_classical_composites(classical_maps, output_dir=CLASSICAL_LOGS_DIR):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for map_name, composite_map in classical_maps.items():
        output_path = output_dir / f"{map_name}_classical.xml"
        write_composite_map(composite_map, output_path)
