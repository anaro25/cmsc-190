from pathlib import Path

from cyclic_test.paths import MAPF_RUNS_DIR
from cyclic_test.visualization.pillow_mapf_renderer import PillowMapfRenderer


DEFAULT_PNG_CELL_SIZE = 32


def write_mapf_frames(
    map_name,
    composite_map,
    agents,
    paths_by_agent,
    output_root=MAPF_RUNS_DIR,
    cell_size=DEFAULT_PNG_CELL_SIZE,
):
    map_output_dir = Path(output_root) / map_name
    renderer = PillowMapfRenderer(cell_size=cell_size)
    return renderer.render_all_frames(
        composite_map=composite_map,
        agents=agents,
        paths_by_agent=paths_by_agent,
        output_dir=map_output_dir,
    )
