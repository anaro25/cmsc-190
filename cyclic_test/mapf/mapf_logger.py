from pathlib import Path

from cyclic_test.paths import MAPF_RUNS_DIR
from cyclic_test.visualization.pillow_mapf_renderer import PillowMapfRenderer


DEFAULT_PNG_CELL_SIZE = 32


def _build_renderer(cell_size):
    return PillowMapfRenderer(cell_size=cell_size)


def _get_map_output_dir(map_name, output_root):
    map_output_dir = Path(output_root) / map_name
    map_output_dir.mkdir(parents=True, exist_ok=True)
    return map_output_dir


def write_empty_map_config_frame(
    map_name,
    composite_map,
    output_root=MAPF_RUNS_DIR,
    cell_size=DEFAULT_PNG_CELL_SIZE,
):
    map_output_dir = _get_map_output_dir(map_name, output_root)
    renderer = _build_renderer(cell_size)
    output_path = map_output_dir / "config_000.png"
    renderer.render_obstacle_only_frame(
        composite_map=composite_map,
        output_path=output_path,
    )
    return output_path


def write_showcase_frame(
    map_name,
    composite_map,
    output_root=MAPF_RUNS_DIR,
    cell_size=DEFAULT_PNG_CELL_SIZE,
):
    map_output_dir = _get_map_output_dir(map_name, output_root)
    renderer = _build_renderer(cell_size)
    output_path = map_output_dir / "config_001.png"
    renderer.render_showcase_frame(
        composite_map=composite_map,
        output_path=output_path,
    )
    return output_path


def write_setup_frame(
    map_name,
    composite_map,
    agents,
    output_root=MAPF_RUNS_DIR,
    cell_size=DEFAULT_PNG_CELL_SIZE,
):
    map_output_dir = _get_map_output_dir(map_name, output_root)
    renderer = _build_renderer(cell_size)
    agent_colors = renderer._build_agent_color_map(agents)
    output_path = map_output_dir / "config_002.png"
    renderer.render_setup_frame(
        composite_map=composite_map,
        agents=agents,
        output_path=output_path,
        agent_colors=agent_colors,
    )
    return output_path


def write_mapf_frames(
    map_name,
    composite_map,
    agents,
    paths_by_agent,
    output_root=MAPF_RUNS_DIR,
    cell_size=DEFAULT_PNG_CELL_SIZE,
):
    map_output_dir = _get_map_output_dir(map_name, output_root)
    renderer = _build_renderer(cell_size)
    return renderer.render_all_frames(
        composite_map=composite_map,
        agents=agents,
        paths_by_agent=paths_by_agent,
        output_dir=map_output_dir,
    )
