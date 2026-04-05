from pathlib import Path

from PIL import Image, ImageDraw

from cyclic_test.visualization.composite_grid_geometry import CompositeGridGeometry

from cyclic_test.core.composite_elements import (
    HorizontalTransition,
    Special,
    Vertex,
    VerticalTransition,
)
from cyclic_test.mapf.mapf_frame_builder import get_makespan, get_path_position
from cyclic_test.visualization.color_palette import build_distinct_rgb_palette


DEFAULT_CELL_SIZE = 32
FREE_SPACE_COLOR = (255, 255, 255)
OBSTACLE_COLOR = (0, 0, 0)
OBSTACLE_FILLER_COLOR = (105, 105, 105)
DEFAULT_ARROW_COLOR = (228, 228, 228)
ACTIVE_ARROW_COLOR = (0, 0, 0)


class PillowMapfRenderer:
    def __init__(self, cell_size=DEFAULT_CELL_SIZE, transition_scale=2 / 3):
        self.cell_size = cell_size
        self.geometry = CompositeGridGeometry(
            cell_size=cell_size,
            transition_scale=transition_scale,
        )

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
        image = Image.new(
            mode="RGB",
            size=self.geometry.get_total_size(composite_map),
            color=FREE_SPACE_COLOR,
        )
        draw = ImageDraw.Draw(image)

        active_arrows = self._get_active_arrow_directions(
            composite_map=composite_map,
            agents=agents,
            paths_by_agent=paths_by_agent,
            time_step=time_step,
        )

        self._draw_base_grid(
            draw=draw,
            composite_map=composite_map,
            active_arrows=active_arrows,
        )
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
        return {agent["id"]: palette[index] for index, agent in enumerate(agents)}

    def _draw_base_grid(self, draw, composite_map, active_arrows):
        for row_index, row in enumerate(composite_map):
            for column_index, cell_value in enumerate(row):
                bounds = self._get_cell_bounds(row_index, column_index)
                background_color = self._draw_cell_background(
                    draw=draw,
                    composite_map=composite_map,
                    row_index=row_index,
                    column_index=column_index,
                    bounds=bounds,
                    cell_value=cell_value,
                )
                self._draw_transition_symbol(
                    draw=draw,
                    bounds=bounds,
                    cell_value=cell_value,
                    active_directions=active_arrows.get((row_index, column_index), set()),
                    background_color=background_color,
                )

    def _draw_cell_background(
        self,
        draw,
        composite_map,
        row_index,
        column_index,
        bounds,
        cell_value,
    ):
        fill_color = FREE_SPACE_COLOR
        if cell_value == Vertex.OBSTACLE:
            fill_color = OBSTACLE_COLOR
        elif self._should_fill_obstacle_gap(composite_map, row_index, column_index):
            fill_color = OBSTACLE_FILLER_COLOR

        draw.rectangle(bounds, fill=fill_color)
        return fill_color

    def _should_fill_obstacle_gap(self, composite_map, row_index, column_index):
        if row_index % 2 == 0 and column_index % 2 == 0:
            return False

        if row_index % 2 == 0 and column_index % 2 == 1:
            left_cell = (row_index, column_index - 1)
            right_cell = (row_index, column_index + 1)
            return self._all_are_obstacles(composite_map, [left_cell, right_cell])

        if row_index % 2 == 1 and column_index % 2 == 0:
            upper_cell = (row_index - 1, column_index)
            lower_cell = (row_index + 1, column_index)
            return self._all_are_obstacles(composite_map, [upper_cell, lower_cell])

        surrounding_cells = [
            (row_index - 1, column_index - 1),
            (row_index - 1, column_index + 1),
            (row_index + 1, column_index - 1),
            (row_index + 1, column_index + 1),
        ]
        return self._all_are_obstacles(composite_map, surrounding_cells)

    def _all_are_obstacles(self, composite_map, positions):
        for row_index, column_index in positions:
            if not self._cell_is_in_bounds(composite_map, row_index, column_index):
                return False
            if composite_map[row_index][column_index] != Vertex.OBSTACLE:
                return False
        return True

    def _draw_transition_symbol(self, draw, bounds, cell_value, active_directions, background_color):
        if cell_value == HorizontalTransition.LEFT:
            self._draw_arrow(
                draw,
                bounds,
                direction="left",
                arrow_color=self._get_arrow_color("left", active_directions),
                is_active=("left" in active_directions),
                background_color=background_color,
            )
        elif cell_value == HorizontalTransition.RIGHT:
            self._draw_arrow(
                draw,
                bounds,
                direction="right",
                arrow_color=self._get_arrow_color("right", active_directions),
                is_active=("right" in active_directions),
                background_color=background_color,
            )
        elif cell_value == HorizontalTransition.LEFT_AND_RIGHT:
            self._draw_bidirectional_transition(
                draw=draw,
                bounds=bounds,
                orientation="horizontal",
                active_directions=active_directions,
                background_color=background_color,
            )
        elif cell_value == VerticalTransition.UP:
            self._draw_arrow(
                draw,
                bounds,
                direction="up",
                arrow_color=self._get_arrow_color("up", active_directions),
                is_active=("up" in active_directions),
                background_color=background_color,
            )
        elif cell_value == VerticalTransition.DOWN:
            self._draw_arrow(
                draw,
                bounds,
                direction="down",
                arrow_color=self._get_arrow_color("down", active_directions),
                is_active=("down" in active_directions),
                background_color=background_color,
            )
        elif cell_value == VerticalTransition.UP_AND_DOWN:
            self._draw_bidirectional_transition(
                draw=draw,
                bounds=bounds,
                orientation="vertical",
                active_directions=active_directions,
                background_color=background_color,
            )
        elif cell_value in {
            HorizontalTransition.NO_HORIZONTAL_TRANSITION,
            VerticalTransition.NO_VERTICAL_TRANSITION,
            Vertex.FREE_SPACE,
            Vertex.OBSTACLE,
            Special.PLACEHOLDER,
        }:
            return

    def _get_arrow_color(self, direction, active_directions):
        if direction in active_directions:
            return ACTIVE_ARROW_COLOR
        return DEFAULT_ARROW_COLOR

    def _draw_targets(self, draw, agents, agent_colors):
        for agent in agents:
            row_index, column_index = agent["goal"]
            bounds = self._get_cell_bounds(row_index, column_index)
            self._draw_target_triangle(draw, bounds, fill=agent_colors[agent["id"]])

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
        draw.ellipse((left, top, right, bottom), fill=fill)

    def _draw_target_triangle(self, draw, bounds, fill):
        left, top, right, bottom = bounds
        width = right - left + 1
        height = bottom - top + 1

        side_length = max(8, min(width, int(height * 1.154700538)))
        side_length = max(8, int(side_length))
        triangle_height = side_length * (3 ** 0.5) / 2
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2

        top_y = center_y - (2 * triangle_height / 3)
        base_y = center_y + (triangle_height / 3)
        half_base = side_length / 2

        triangle = [
            (center_x, top_y),
            (center_x - half_base, base_y),
            (center_x + half_base, base_y),
        ]
        draw.polygon(triangle, fill=fill)

    def _draw_arrow(
        self,
        draw,
        bounds,
        direction,
        arrow_color,
        is_active=False,
        background_color=FREE_SPACE_COLOR,
    ):
        left, top, right, bottom = bounds
        width = right - left + 1
        height = bottom - top + 1
        min_dimension = min(width, height)

        center_x = (left + right) / 2
        center_y = (top + bottom) / 2

        head_side = max(7.0, min_dimension * (0.60 if is_active else 0.56))
        shaft_thickness = max(2.0, head_side * (0.22 if is_active else 0.16))
        shaft_length = max(6.0, head_side * (0.74 if is_active else 0.66))
        if direction in {"left", "right"}:
            shaft_length = min(shaft_length, max(5.0, width * 0.40))
        else:
            shaft_length = min(shaft_length, max(5.0, height * 0.40))

        head_points, shaft_bounds = self._build_arrow_geometry(
            center_x=center_x,
            center_y=center_y,
            side_length=head_side,
            shaft_length=shaft_length,
            shaft_thickness=shaft_thickness,
            direction=direction,
        )

        if shaft_bounds is not None:
            draw.rounded_rectangle(shaft_bounds, radius=shaft_thickness / 2, fill=arrow_color)
        draw.polygon(head_points, fill=arrow_color)

    def _build_arrow_geometry(
        self,
        center_x,
        center_y,
        side_length,
        shaft_length,
        shaft_thickness,
        direction,
    ):
        triangle_height = side_length * (3 ** 0.5) / 2
        distance_to_tip = (2 * triangle_height) / 3
        distance_to_base = triangle_height / 3
        half_side = side_length / 2
        half_shaft = shaft_thickness / 2

        if direction == "right":
            head_points = [
                (center_x + distance_to_tip, center_y),
                (center_x - distance_to_base, center_y - half_side),
                (center_x - distance_to_base, center_y + half_side),
            ]
            shaft_bounds = (
                center_x - distance_to_base - shaft_length,
                center_y - half_shaft,
                center_x - distance_to_base,
                center_y + half_shaft,
            )
            return head_points, shaft_bounds

        if direction == "left":
            head_points = [
                (center_x - distance_to_tip, center_y),
                (center_x + distance_to_base, center_y - half_side),
                (center_x + distance_to_base, center_y + half_side),
            ]
            shaft_bounds = (
                center_x + distance_to_base,
                center_y - half_shaft,
                center_x + distance_to_base + shaft_length,
                center_y + half_shaft,
            )
            return head_points, shaft_bounds

        if direction == "down":
            head_points = [
                (center_x, center_y + distance_to_tip),
                (center_x - half_side, center_y - distance_to_base),
                (center_x + half_side, center_y - distance_to_base),
            ]
            shaft_bounds = (
                center_x - half_shaft,
                center_y - distance_to_base - shaft_length,
                center_x + half_shaft,
                center_y - distance_to_base,
            )
            return head_points, shaft_bounds

        if direction == "up":
            head_points = [
                (center_x, center_y - distance_to_tip),
                (center_x - half_side, center_y + distance_to_base),
                (center_x + half_side, center_y + distance_to_base),
            ]
            shaft_bounds = (
                center_x - half_shaft,
                center_y + distance_to_base,
                center_x + half_shaft,
                center_y + distance_to_base + shaft_length,
            )
            return head_points, shaft_bounds

        raise ValueError(f"Unsupported arrow direction: {direction}")

    def _draw_bidirectional_transition(
        self,
        draw,
        bounds,
        orientation,
        active_directions,
        background_color=FREE_SPACE_COLOR,
    ):
        active_count = len(active_directions)

        if active_count == 1:
            direction = next(iter(active_directions))
            self._draw_arrow(
                draw=draw,
                bounds=bounds,
                direction=direction,
                arrow_color=ACTIVE_ARROW_COLOR,
                is_active=True,
                background_color=background_color,
            )
            return

        self._draw_bidirectional_symbol(
            draw=draw,
            bounds=bounds,
            symbol_color=(ACTIVE_ARROW_COLOR if active_count >= 2 else DEFAULT_ARROW_COLOR),
            orientation=orientation,
            is_active=bool(active_directions),
        )

    def _draw_bidirectional_symbol(
        self,
        draw,
        bounds,
        symbol_color,
        orientation,
        is_active=False,
    ):
        left, top, right, bottom = bounds
        width = right - left + 1
        height = bottom - top + 1

        center_x = (left + right) / 2
        center_y = (top + bottom) / 2

        if orientation == "horizontal":
            half_width = max(5.0, width * (0.44 if is_active else 0.40))
            half_height = max(4.0, height * (0.28 if is_active else 0.24))
        else:
            half_width = max(4.0, width * (0.28 if is_active else 0.24))
            half_height = max(5.0, height * (0.44 if is_active else 0.40))

        diamond = [
            (center_x, center_y - half_height),
            (center_x + half_width, center_y),
            (center_x, center_y + half_height),
            (center_x - half_width, center_y),
        ]
        draw.polygon(diamond, fill=symbol_color)

    def _build_equilateral_triangle(
        self,
        center_x,
        center_y,
        side_length,
        direction,
        tip_offset=0.0,
    ):
        triangle_height = side_length * (3 ** 0.5) / 2
        distance_to_tip = (2 * triangle_height) / 3
        distance_to_base = triangle_height / 3
        half_side = side_length / 2

        if direction == "right":
            return [
                (center_x + distance_to_tip + tip_offset, center_y),
                (center_x - distance_to_base + tip_offset, center_y - half_side),
                (center_x - distance_to_base + tip_offset, center_y + half_side),
            ]
        if direction == "left":
            return [
                (center_x - distance_to_tip - tip_offset, center_y),
                (center_x + distance_to_base - tip_offset, center_y - half_side),
                (center_x + distance_to_base - tip_offset, center_y + half_side),
            ]
        if direction == "down":
            return [
                (center_x, center_y + distance_to_tip + tip_offset),
                (center_x - half_side, center_y - distance_to_base + tip_offset),
                (center_x + half_side, center_y - distance_to_base + tip_offset),
            ]
        if direction == "up":
            return [
                (center_x, center_y - distance_to_tip - tip_offset),
                (center_x - half_side, center_y + distance_to_base - tip_offset),
                (center_x + half_side, center_y + distance_to_base - tip_offset),
            ]
        raise ValueError(f"Unsupported arrow direction: {direction}")

    def _get_active_arrow_directions(self, composite_map, agents, paths_by_agent, time_step):
        active_arrows = {}

        for agent in agents:
            current_position = get_path_position(paths_by_agent[agent["id"]], time_step)
            if current_position is None:
                continue

            row_index, column_index = current_position
            for transition_row, transition_column, direction in self._get_outgoing_transition_slots(
                row_index,
                column_index,
            ):
                if not self._cell_is_in_bounds(composite_map, transition_row, transition_column):
                    continue

                if self._transition_supports_direction(
                    composite_map[transition_row][transition_column],
                    direction,
                ):
                    active_arrows.setdefault(
                        (transition_row, transition_column),
                        set(),
                    ).add(direction)

        return active_arrows

    def _get_outgoing_transition_slots(self, row_index, column_index):
        return [
            (row_index, column_index - 1, "left"),
            (row_index, column_index + 1, "right"),
            (row_index - 1, column_index, "up"),
            (row_index + 1, column_index, "down"),
        ]

    def _transition_supports_direction(self, cell_value, direction):
        direction_to_supported_values = {
            "left": {HorizontalTransition.LEFT, HorizontalTransition.LEFT_AND_RIGHT},
            "right": {HorizontalTransition.RIGHT, HorizontalTransition.LEFT_AND_RIGHT},
            "up": {VerticalTransition.UP, VerticalTransition.UP_AND_DOWN},
            "down": {VerticalTransition.DOWN, VerticalTransition.UP_AND_DOWN},
        }
        return cell_value in direction_to_supported_values[direction]

    def _cell_is_in_bounds(self, composite_map, row_index, column_index):
        return (
            0 <= row_index < len(composite_map)
            and 0 <= column_index < len(composite_map[0])
        )

    def _get_cell_bounds(self, row_index, column_index):
        return self.geometry.get_cell_bounds(row_index, column_index)
