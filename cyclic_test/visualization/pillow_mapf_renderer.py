from pathlib import Path

from PIL import Image, ImageDraw

from cyclic_test.core.composite_elements import (
    HorizontalTransition,
    Special,
    Vertex,
    VerticalTransition,
)
from cyclic_test.mapf.mapf_frame_builder import get_makespan, get_path_position
from cyclic_test.visualization.color_palette import build_distinct_rgb_palette


DEFAULT_CELL_SIZE = 32
GRID_LINE_COLOR = (210, 210, 210)
FREE_SPACE_COLOR = (255, 255, 255)
OBSTACLE_COLOR = (0, 0, 0)
ARROW_COLOR = (70, 70, 70)


class PillowMapfRenderer:
    def __init__(self, cell_size=DEFAULT_CELL_SIZE):
        self.cell_size = cell_size

    def render_all_frames(self, composite_map, agents, paths_by_agent, output_dir):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        makespan = get_makespan(paths_by_agent)
        agent_colors = self._build_agent_color_map(agents)

        rendered_paths = []
        for time_step in range(makespan + 1):
            output_path = output_dir / f"frame_{time_step:03d}.png"
            self.render_frame(
                composite_map=composite_map,
                agents=agents,
                paths_by_agent=paths_by_agent,
                time_step=time_step,
                output_path=output_path,
                agent_colors=agent_colors,
            )
            rendered_paths.append(output_path)

        return rendered_paths

    def render_frame(
        self,
        composite_map,
        agents,
        paths_by_agent,
        time_step,
        output_path,
        agent_colors,
    ):
        height = len(composite_map)
        width = len(composite_map[0]) if height > 0 else 0

        image = Image.new(
            mode="RGB",
            size=(width * self.cell_size, height * self.cell_size),
            color=FREE_SPACE_COLOR,
        )
        draw = ImageDraw.Draw(image)

        self._draw_base_grid(draw=draw, composite_map=composite_map)
        self._draw_targets(draw=draw, agents=agents, agent_colors=agent_colors)
        self._draw_agents(
            draw=draw,
            agents=agents,
            paths_by_agent=paths_by_agent,
            time_step=time_step,
            agent_colors=agent_colors,
        )

        image.save(output_path)

    def _build_agent_color_map(self, agents):
        palette = build_distinct_rgb_palette(len(agents))
        return {
            agent["id"]: palette[index]
            for index, agent in enumerate(agents)
        }

    def _draw_base_grid(self, draw, composite_map):
        for row_index, row in enumerate(composite_map):
            for column_index, cell_value in enumerate(row):
                bounds = self._get_cell_bounds(row_index, column_index)
                self._draw_cell_background(draw=draw, bounds=bounds, cell_value=cell_value)
                self._draw_grid_outline(draw=draw, bounds=bounds)
                self._draw_transition_symbol(
                    draw=draw,
                    bounds=bounds,
                    cell_value=cell_value,
                )

    def _draw_cell_background(self, draw, bounds, cell_value):
        fill_color = FREE_SPACE_COLOR
        if cell_value == Vertex.OBSTACLE:
            fill_color = OBSTACLE_COLOR

        draw.rectangle(bounds, fill=fill_color)

    def _draw_grid_outline(self, draw, bounds):
        draw.rectangle(bounds, outline=GRID_LINE_COLOR, width=1)

    def _draw_transition_symbol(self, draw, bounds, cell_value):
        if cell_value == HorizontalTransition.LEFT:
            self._draw_arrow(draw, bounds, direction="left")
        elif cell_value == HorizontalTransition.RIGHT:
            self._draw_arrow(draw, bounds, direction="right")
        elif cell_value == HorizontalTransition.LEFT_AND_RIGHT:
            self._draw_arrow(draw, bounds, direction="left")
            self._draw_arrow(draw, bounds, direction="right")
        elif cell_value == VerticalTransition.UP:
            self._draw_arrow(draw, bounds, direction="up")
        elif cell_value == VerticalTransition.DOWN:
            self._draw_arrow(draw, bounds, direction="down")
        elif cell_value == VerticalTransition.UP_AND_DOWN:
            self._draw_arrow(draw, bounds, direction="up")
            self._draw_arrow(draw, bounds, direction="down")
        elif cell_value in {
            HorizontalTransition.NO_HORIZONTAL_TRANSITION,
            VerticalTransition.NO_VERTICAL_TRANSITION,
            Vertex.FREE_SPACE,
            Vertex.OBSTACLE,
            Special.PLACEHOLDER,
        }:
            return

    def _draw_targets(self, draw, agents, agent_colors):
        for agent in agents:
            row_index, column_index = agent["goal"]
            bounds = self._get_cell_bounds(row_index, column_index)
            self._draw_triangle(draw, bounds, fill=agent_colors[agent["id"]])

    def _draw_agents(self, draw, agents, paths_by_agent, time_step, agent_colors):
        for agent in agents:
            current_position = get_path_position(paths_by_agent[agent["id"]], time_step)
            if current_position is None:
                continue

            row_index, column_index = current_position
            bounds = self._get_cell_bounds(row_index, column_index)
            self._draw_circle(draw, bounds, fill=agent_colors[agent["id"]])

    def _draw_circle(self, draw, bounds, fill):
        left, top, right, bottom = bounds
        margin = max(4, self.cell_size // 6)
        draw.ellipse(
            (left + margin, top + margin, right - margin, bottom - margin),
            fill=fill,
        )

    def _draw_triangle(self, draw, bounds, fill):
        left, top, right, bottom = bounds
        center_x = (left + right) / 2
        margin = max(5, self.cell_size // 6)
        points = [
            (center_x, top + margin),
            (left + margin, bottom - margin),
            (right - margin, bottom - margin),
        ]
        draw.polygon(points, fill=fill)

    def _draw_arrow(self, draw, bounds, direction):
        left, top, right, bottom = bounds
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        shaft_margin = max(5, self.cell_size // 5)
        head_size = max(4, self.cell_size // 6)
        shaft_width = max(2, self.cell_size // 14)

        if direction == "right":
            start = (left + shaft_margin, center_y)
            end = (right - shaft_margin, center_y)
            head = [
                end,
                (end[0] - head_size, end[1] - head_size),
                (end[0] - head_size, end[1] + head_size),
            ]
        elif direction == "left":
            start = (right - shaft_margin, center_y)
            end = (left + shaft_margin, center_y)
            head = [
                end,
                (end[0] + head_size, end[1] - head_size),
                (end[0] + head_size, end[1] + head_size),
            ]
        elif direction == "down":
            start = (center_x, top + shaft_margin)
            end = (center_x, bottom - shaft_margin)
            head = [
                end,
                (end[0] - head_size, end[1] - head_size),
                (end[0] + head_size, end[1] - head_size),
            ]
        elif direction == "up":
            start = (center_x, bottom - shaft_margin)
            end = (center_x, top + shaft_margin)
            head = [
                end,
                (end[0] - head_size, end[1] + head_size),
                (end[0] + head_size, end[1] + head_size),
            ]
        else:
            raise ValueError(f"Unsupported arrow direction: {direction}")

        draw.line((start, end), fill=ARROW_COLOR, width=shaft_width)
        draw.polygon(head, fill=ARROW_COLOR)

    def _get_cell_bounds(self, row_index, column_index):
        left = column_index * self.cell_size
        top = row_index * self.cell_size
        right = left + self.cell_size - 1
        bottom = top + self.cell_size - 1
        return (left, top, right, bottom)
