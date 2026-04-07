from pathlib import Path

from PIL import Image, ImageDraw

from dev.visualization.composite_grid_geometry import CompositeGridGeometry

from dev.core.composite_elements import (
    HorizontalTransition,
    Special,
    Vertex,
    VerticalTransition,
)
from dev.mapf.mapf_frame_builder import get_makespan, get_path_position
from dev.visualization.color_palette import build_distinct_rgb_palette


DEFAULT_CELL_SIZE = 32
DEFAULT_OUTER_MARGIN_RATIO = 1 / 6
FREE_SPACE_COLOR = (255, 255, 255)
OBSTACLE_COLOR = (0, 0, 0)
OBSTACLE_FILLER_COLOR = (105, 105, 105)
DEFAULT_ARROW_COLOR = (228, 228, 228)
ACTIVE_ARROW_COLOR = (0, 0, 0)
SHOWCASE_ARROW_COLOR = (90, 90, 90)
FREE_SPACE_DOT_COLOR = (210, 210, 210)


class PillowMapfRenderer:
    def __init__(
        self,
        cell_size=DEFAULT_CELL_SIZE,
        transition_scale=2 / 3,
        outer_margin_ratio=DEFAULT_OUTER_MARGIN_RATIO,
    ):
        self.cell_size = cell_size
        self.outer_margin = max(1, int(round(cell_size * outer_margin_ratio)))
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

    def render_obstacle_only_frame(self, composite_map, output_path, dynamic_vertex_positions=None):
        image = self._create_base_image(composite_map)
        draw = ImageDraw.Draw(image)

        self._draw_base_grid(
            draw=draw,
            composite_map=composite_map,
            active_arrows={},
            transition_mode="hidden",
            draw_free_space_dots=False,
            dynamic_vertex_positions=dynamic_vertex_positions,
        )

        image.save(output_path)

    def render_showcase_frame(self, composite_map, output_path, dynamic_vertex_positions=None):
        image = self._create_base_image(composite_map)
        draw = ImageDraw.Draw(image)

        self._draw_base_grid(
            draw=draw,
            composite_map=composite_map,
            active_arrows={},
            transition_mode="showcase",
            draw_free_space_dots=False,
            dynamic_vertex_positions=dynamic_vertex_positions,
        )

        image.save(output_path)

    def render_setup_frame(
        self,
        composite_map,
        agents,
        output_path,
        agent_colors,
        dynamic_vertex_positions=None,
    ):
        image = self._create_base_image(composite_map)
        draw = ImageDraw.Draw(image)

        self._draw_base_grid(
            draw=draw,
            composite_map=composite_map,
            active_arrows={},
            transition_mode="normal",
            draw_free_space_dots=False,
            dynamic_vertex_positions=dynamic_vertex_positions,
        )
        self._draw_targets(
            draw=draw,
            agents=agents,
            agent_colors=agent_colors,
            paths_by_agent=None,
            time_step=None,
        )
        self._draw_agents_at_start(
            draw=draw,
            agents=agents,
            agent_colors=agent_colors,
        )

        image.save(output_path)

    def render_frame(
        self,
        composite_map,
        agents,
        paths_by_agent,
        time_step,
        output_path,
        agent_colors,
        dynamic_vertex_positions=None,
    ):
        image = self._create_base_image(composite_map)
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
            transition_mode="normal",
            draw_free_space_dots=False,
            dynamic_vertex_positions=dynamic_vertex_positions,
        )
        self._draw_targets(
            draw=draw,
            agents=agents,
            agent_colors=agent_colors,
            paths_by_agent=paths_by_agent,
            time_step=time_step,
        )
        self._draw_agents(
            draw=draw,
            agents=agents,
            paths_by_agent=paths_by_agent,
            time_step=time_step,
            agent_colors=agent_colors,
        )

        image.save(output_path)

    def _create_base_image(self, composite_map):
        return Image.new(
            mode="RGB",
            size=self._get_image_size(composite_map),
            color=FREE_SPACE_COLOR,
        )

    def _get_image_size(self, composite_map):
        base_width, base_height = self.geometry.get_total_size(composite_map)
        return (
            base_width + (2 * self.outer_margin),
            base_height + (2 * self.outer_margin),
        )

    def _build_agent_color_map(self, agents):
        palette = build_distinct_rgb_palette(len(agents))
        return {agent["id"]: palette[index] for index, agent in enumerate(agents)}

    def _draw_base_grid(
        self,
        draw,
        composite_map,
        active_arrows,
        transition_mode="normal",
        draw_free_space_dots=False,
        dynamic_vertex_positions=None,
    ):
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
                    dynamic_vertex_positions=dynamic_vertex_positions or set(),
                )
                self._draw_transition_symbol(
                    draw=draw,
                    bounds=bounds,
                    cell_value=cell_value,
                    active_directions=active_arrows.get((row_index, column_index), set()),
                    background_color=background_color,
                    transition_mode=transition_mode,
                )
                if draw_free_space_dots:
                    self._draw_free_space_dot(
                        draw=draw,
                        bounds=bounds,
                        cell_value=cell_value,
                    )

    def _draw_cell_background(
        self,
        draw,
        composite_map,
        row_index,
        column_index,
        bounds,
        cell_value,
        dynamic_vertex_positions,
    ):
        fill_color = FREE_SPACE_COLOR
        if cell_value == Vertex.OBSTACLE:
            fill_color = OBSTACLE_COLOR
            draw.rectangle(bounds, fill=fill_color)
            return fill_color

        if self._should_fill_obstacle_gap(composite_map, row_index, column_index):
            fill_color = OBSTACLE_FILLER_COLOR
            draw.rectangle(bounds, fill=fill_color)
            return fill_color

        draw.rectangle(bounds, fill=fill_color)
        self._draw_partial_obstacle_gap(
            draw=draw,
            composite_map=composite_map,
            row_index=row_index,
            column_index=column_index,
            bounds=bounds,
            cell_value=cell_value,
            dynamic_vertex_positions=dynamic_vertex_positions,
        )
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

    def _draw_partial_obstacle_gap(
        self,
        draw,
        composite_map,
        row_index,
        column_index,
        bounds,
        cell_value,
        dynamic_vertex_positions,
    ):
        left, top, right, bottom = bounds
        midpoint_x = (left + right) / 2
        midpoint_y = (top + bottom) / 2

        if row_index % 2 == 0 and column_index % 2 == 1:
            left_is_obstacle = self._vertex_is_obstacle(composite_map, row_index, column_index - 1)
            right_is_obstacle = self._vertex_is_obstacle(composite_map, row_index, column_index + 1)
            if left_is_obstacle ^ right_is_obstacle:
                if left_is_obstacle:
                    fill_bounds = (left, top, midpoint_x, bottom)
                else:
                    fill_bounds = (midpoint_x, top, right, bottom)
                draw.rectangle(fill_bounds, fill=OBSTACLE_FILLER_COLOR)
            return

        if row_index % 2 == 1 and column_index % 2 == 0:
            upper_is_obstacle = self._vertex_is_obstacle(composite_map, row_index - 1, column_index)
            lower_is_obstacle = self._vertex_is_obstacle(composite_map, row_index + 1, column_index)
            if upper_is_obstacle ^ lower_is_obstacle:
                if upper_is_obstacle:
                    fill_bounds = (left, top, right, midpoint_y)
                else:
                    fill_bounds = (left, midpoint_y, right, bottom)
                draw.rectangle(fill_bounds, fill=OBSTACLE_FILLER_COLOR)
            return

        if row_index % 2 == 1 and column_index % 2 == 1:
            diagonal_quadrants = [
                (self._vertex_is_obstacle(composite_map, row_index - 1, column_index - 1), (left, top, midpoint_x, midpoint_y)),
                (self._vertex_is_obstacle(composite_map, row_index - 1, column_index + 1), (midpoint_x, top, right, midpoint_y)),
                (self._vertex_is_obstacle(composite_map, row_index + 1, column_index - 1), (left, midpoint_y, midpoint_x, bottom)),
                (self._vertex_is_obstacle(composite_map, row_index + 1, column_index + 1), (midpoint_x, midpoint_y, right, bottom)),
            ]
            for has_obstacle, fill_bounds in diagonal_quadrants:
                if has_obstacle:
                    draw.rectangle(fill_bounds, fill=OBSTACLE_FILLER_COLOR)
            return

    def _vertex_is_obstacle(self, composite_map, row_index, column_index):
        if not self._cell_is_in_bounds(composite_map, row_index, column_index):
            return False
        return composite_map[row_index][column_index] == Vertex.OBSTACLE

    def _draw_transition_symbol(
        self,
        draw,
        bounds,
        cell_value,
        active_directions,
        background_color,
        transition_mode="normal",
    ):
        if transition_mode == "hidden":
            return
        if cell_value == HorizontalTransition.LEFT:
            self._draw_arrow(
                draw,
                bounds,
                direction="left",
                arrow_color=self._get_arrow_color("left", active_directions, transition_mode=transition_mode),
                is_active=("left" in active_directions),
                background_color=background_color,
            )
        elif cell_value == HorizontalTransition.RIGHT:
            self._draw_arrow(
                draw,
                bounds,
                direction="right",
                arrow_color=self._get_arrow_color("right", active_directions, transition_mode=transition_mode),
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
                transition_mode=transition_mode,
            )
        elif cell_value == VerticalTransition.UP:
            self._draw_arrow(
                draw,
                bounds,
                direction="up",
                arrow_color=self._get_arrow_color("up", active_directions, transition_mode=transition_mode),
                is_active=("up" in active_directions),
                background_color=background_color,
            )
        elif cell_value == VerticalTransition.DOWN:
            self._draw_arrow(
                draw,
                bounds,
                direction="down",
                arrow_color=self._get_arrow_color("down", active_directions, transition_mode=transition_mode),
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
                transition_mode=transition_mode,
            )
        elif cell_value in {
            HorizontalTransition.NO_HORIZONTAL_TRANSITION,
            VerticalTransition.NO_VERTICAL_TRANSITION,
            Vertex.FREE_SPACE,
            Vertex.OBSTACLE,
            Special.PLACEHOLDER,
        }:
            return

    def _get_arrow_color(self, direction, active_directions, transition_mode="normal"):
        if transition_mode == "hidden":
            return None
        if transition_mode == "showcase":
            return SHOWCASE_ARROW_COLOR
        if direction in active_directions:
            return ACTIVE_ARROW_COLOR
        return DEFAULT_ARROW_COLOR

    def _draw_targets(self, draw, agents, agent_colors, paths_by_agent, time_step):
        for agent in agents:
            row_index, column_index = agent["goal"]
            bounds = self._get_cell_bounds(row_index, column_index)
            reached_goal = False
            if paths_by_agent is not None and time_step is not None:
                reached_goal = self._agent_has_reached_goal(
                    path=paths_by_agent[agent["id"]],
                    goal_position=agent["goal"],
                    time_step=time_step,
                )
            self._draw_target_triangle(
                draw,
                bounds,
                fill=agent_colors[agent["id"]],
                inverted=reached_goal,
            )

    def _draw_agents_at_start(self, draw, agents, agent_colors):
        for agent in agents:
            row_index, column_index = agent["start"]
            bounds = self._get_cell_bounds(row_index, column_index)
            self._draw_circle(draw, bounds, fill=agent_colors[agent["id"]])

    def _draw_agents(self, draw, agents, paths_by_agent, time_step, agent_colors):
        for agent in agents:
            current_position = get_path_position(paths_by_agent[agent["id"]], time_step)
            if current_position is None:
                continue
            if current_position == agent["goal"]:
                continue

            row_index, column_index = current_position
            bounds = self._get_cell_bounds(row_index, column_index)
            self._draw_circle(draw, bounds, fill=agent_colors[agent["id"]])


    def _agent_has_reached_goal(self, path, goal_position, time_step):
        capped_time_step = min(time_step, len(path) - 1)
        for index in range(capped_time_step + 1):
            if path[index] == goal_position:
                return True
        return False

    def _draw_free_space_dot(self, draw, bounds, cell_value):
        if cell_value != Vertex.FREE_SPACE:
            return

        left, top, right, bottom = bounds
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        radius = max(2, int(round(min(right - left + 1, bottom - top + 1) * 0.10)))
        draw.ellipse(
            (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
            fill=FREE_SPACE_DOT_COLOR,
        )

    def _draw_circle(self, draw, bounds, fill):
        left, top, right, bottom = bounds
        draw.ellipse((left, top, right, bottom), fill=fill)

    def _draw_target_triangle(self, draw, bounds, fill, inverted=False):
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

        if inverted:
            triangle = [
                (center_x, base_y),
                (center_x - half_base, top_y),
                (center_x + half_base, top_y),
            ]
        else:
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
        center_override=None,
        head_side_override=None,
        shaft_length_override=None,
        shaft_thickness_override=None,
    ):
        left, top, right, bottom = bounds
        width = right - left + 1
        height = bottom - top + 1
        min_dimension = min(width, height)

        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        if center_override is not None:
            center_x, center_y = center_override

        head_side = max(6.0, min_dimension * (0.52 if is_active else 0.48))
        shaft_thickness = max(2.0, head_side * (0.22 if is_active else 0.16))
        shaft_length = max(8.0, head_side * (1.15 if is_active else 1.00))
        if head_side_override is not None:
            head_side = head_side_override
        if shaft_thickness_override is not None:
            shaft_thickness = shaft_thickness_override
        if shaft_length_override is not None:
            shaft_length = shaft_length_override
        if direction in {"left", "right"}:
            shaft_length = min(shaft_length, max(7.0, width * 0.48))
        else:
            shaft_length = min(shaft_length, max(7.0, height * 0.48))

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
        transition_mode="normal",
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
            symbol_color=(SHOWCASE_ARROW_COLOR if transition_mode == "showcase" else (ACTIVE_ARROW_COLOR if active_count >= 2 else DEFAULT_ARROW_COLOR)),
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
            offset = max(4.0, width * (0.22 if is_active else 0.20))
            head_side = max(6.0, min(width, height) * (0.38 if is_active else 0.34))
            shaft_thickness = max(2.0, head_side * (0.20 if is_active else 0.16))
            shaft_length = max(4.0, width * (0.11 if is_active else 0.10))
            self._draw_arrow(
                draw=draw,
                bounds=bounds,
                direction="left",
                arrow_color=symbol_color,
                is_active=is_active,
                background_color=FREE_SPACE_COLOR,
                center_override=(center_x - offset, center_y),
                head_side_override=head_side,
                shaft_length_override=shaft_length,
                shaft_thickness_override=shaft_thickness,
            )
            self._draw_arrow(
                draw=draw,
                bounds=bounds,
                direction="right",
                arrow_color=symbol_color,
                is_active=is_active,
                background_color=FREE_SPACE_COLOR,
                center_override=(center_x + offset, center_y),
                head_side_override=head_side,
                shaft_length_override=shaft_length,
                shaft_thickness_override=shaft_thickness,
            )
            return

        offset = max(4.0, height * (0.22 if is_active else 0.20))
        head_side = max(6.0, min(width, height) * (0.38 if is_active else 0.34))
        shaft_thickness = max(2.0, head_side * (0.20 if is_active else 0.16))
        shaft_length = max(4.0, height * (0.11 if is_active else 0.10))
        self._draw_arrow(
            draw=draw,
            bounds=bounds,
            direction="up",
            arrow_color=symbol_color,
            is_active=is_active,
            background_color=FREE_SPACE_COLOR,
            center_override=(center_x, center_y - offset),
            head_side_override=head_side,
            shaft_length_override=shaft_length,
            shaft_thickness_override=shaft_thickness,
        )
        self._draw_arrow(
            draw=draw,
            bounds=bounds,
            direction="down",
            arrow_color=symbol_color,
            is_active=is_active,
            background_color=FREE_SPACE_COLOR,
            center_override=(center_x, center_y + offset),
            head_side_override=head_side,
            shaft_length_override=shaft_length,
            shaft_thickness_override=shaft_thickness,
        )

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
            if current_position == agent["goal"]:
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

    def _get_cell_bounds(self, row_index, column_index):
        left, top, right, bottom = self.geometry.get_cell_bounds(row_index, column_index)
        return (
            left + self.outer_margin,
            top + self.outer_margin,
            right + self.outer_margin,
            bottom + self.outer_margin,
        )

    def _cell_is_in_bounds(self, composite_map, row_index, column_index):
        return (
            0 <= row_index < len(composite_map)
            and 0 <= column_index < len(composite_map[0])
        )
