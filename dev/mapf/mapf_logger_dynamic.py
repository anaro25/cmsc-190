from pathlib import Path

from dev.mapf.mapf_frame_builder import get_makespan
from dev.visualization.pillow_mapf_renderer import PillowMapfRenderer


DEFAULT_PNG_CELL_SIZE = 32


def _build_renderer(cell_size):
    return PillowMapfRenderer(cell_size=cell_size)


def _get_map_output_dir(map_name, output_root):
    map_output_dir = Path(output_root) / map_name
    map_output_dir.mkdir(parents=True, exist_ok=True)
    return map_output_dir


def _dynamic_cells_to_composite_positions(dynamic_matrix):
    positions = set()
    for row_index, row in enumerate(dynamic_matrix):
        for column_index, value in enumerate(row):
            if value == 2:
                positions.add((2 * row_index, 2 * column_index))
    return positions


def write_dynamic_obstacle_only_frame(map_name, composite_map, output_root, cell_size=DEFAULT_PNG_CELL_SIZE):
    renderer = _build_renderer(cell_size)
    output_path = _get_map_output_dir(map_name, output_root) / 'config_000.png'
    renderer.render_obstacle_only_frame(
        composite_map,
        output_path,
    )
    return output_path


def write_dynamic_showcase_frame(map_name, composite_map, output_root, cell_size=DEFAULT_PNG_CELL_SIZE):
    renderer = _build_renderer(cell_size)
    output_path = _get_map_output_dir(map_name, output_root) / 'config_001.png'
    renderer.render_showcase_frame(
        composite_map,
        output_path,
    )
    return output_path


def write_dynamic_setup_frame(map_name, composite_map, agents, output_root, cell_size=DEFAULT_PNG_CELL_SIZE):
    renderer = _build_renderer(cell_size)
    output_path = _get_map_output_dir(map_name, output_root) / 'config_002.png'
    renderer.render_setup_frame(
        composite_map,
        agents,
        output_path,
        renderer._build_agent_color_map(agents),
    )
    return output_path


def write_dynamic_mapf_frames(map_name, composite_loop, dynamic_matrix_loop, agents, paths_by_agent, output_root, cell_size=DEFAULT_PNG_CELL_SIZE):
    renderer = _build_renderer(cell_size)
    output_dir = _get_map_output_dir(map_name, output_root)
    agent_colors = renderer._build_agent_color_map(agents)
    makespan = get_makespan(paths_by_agent)
    rendered = []

    for time_step in range(makespan + 1):
        composite_map = composite_loop[time_step % len(composite_loop)]
        dynamic_matrix = dynamic_matrix_loop[time_step % len(dynamic_matrix_loop)]
        output_path = output_dir / f'frame_{time_step:03d}.png'
        renderer.render_frame(
            composite_map=composite_map,
            agents=agents,
            paths_by_agent=paths_by_agent,
            time_step=time_step,
            output_path=output_path,
            agent_colors=agent_colors,
            dynamic_vertex_positions=_dynamic_cells_to_composite_positions(dynamic_matrix),
        )
        rendered.append(output_path)

    return rendered
