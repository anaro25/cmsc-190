from pathlib import Path
from PIL import Image, ImageDraw


CELL_SIZE = 24
BORDER_WIDTH = 1

FREE_CELL_COLOR = (245, 245, 245)
OBSTACLE_COLOR = (0, 0, 0)

AGENT_COLOR = (52, 120, 246)
TARGET_COLOR = (60, 180, 75)
TRAIL_COLOR = (52, 120, 246, 90)

CELL_BORDER_COLOR = (230, 230, 230)


def _detect_animation_type(astar_frames):
    """
    Detect whether the frames are classical or cyclic.

    Classical frames use bidirectional transitions: ↔, ↕
    Cyclic frames use directional transitions: →, ←, ↑, ↓
    """
    for frame in astar_frames:
        for row in frame:
            for cell in row:
                if cell in {'↔', '↕'}:
                    return "classical"
    return "cyclic"


def _get_output_directory(animation_type):
    module_dir = Path(__file__).resolve().parent

    if animation_type == "classical":
        return module_dir / "classical_animation"
    if animation_type == "cyclic":
        return module_dir / "cyclic_animation"

    raise ValueError(f"Unknown animation type: {animation_type}")


def _prepare_output_directory(output_dir):
    output_dir.mkdir(exist_ok=True)

    for png_file in output_dir.glob("*.png"):
        png_file.unlink()


def _extract_vertex_grid(char_frame):
    """
    Keep only actual traversable/occupancy cells from the composite grid.

    In the composite grid, real cells are one space apart, so they are found at:
    [0][0], [0][2], [0][4], ...
    [2][0], [2][2], [2][4], ...
    etc.
    """
    vertex_grid = []

    for row_index in range(0, len(char_frame), 2):
        vertex_row = []

        for col_index in range(0, len(char_frame[row_index]), 2):
            vertex_row.append(char_frame[row_index][col_index])

        vertex_grid.append(vertex_row)

    return vertex_grid


def _draw_cell_background(draw, x, y):
    draw.rectangle(
        [
            (x, y),
            (x + CELL_SIZE - 1, y + CELL_SIZE - 1),
        ],
        fill=FREE_CELL_COLOR,
        outline=CELL_BORDER_COLOR,
        width=BORDER_WIDTH
    )


def _draw_obstacle(draw, x, y):
    draw.rectangle(
        [
            (x, y),
            (x + CELL_SIZE - 1, y + CELL_SIZE - 1),
        ],
        fill=OBSTACLE_COLOR,
        outline=CELL_BORDER_COLOR,
        width=BORDER_WIDTH
    )


def _draw_agent(draw, x, y):
    margin = CELL_SIZE // 6
    draw.ellipse(
        [
            (x + margin, y + margin),
            (x + CELL_SIZE - 1 - margin, y + CELL_SIZE - 1 - margin),
        ],
        fill=AGENT_COLOR
    )


def _draw_trail(overlay_draw, x, y):
    margin = CELL_SIZE // 3
    overlay_draw.ellipse(
        [
            (x + margin, y + margin),
            (x + CELL_SIZE - 1 - margin, y + CELL_SIZE - 1 - margin),
        ],
        fill=TRAIL_COLOR
    )


def _draw_target(draw, x, y):
    margin = CELL_SIZE // 6
    draw.rectangle(
        [
            (x + margin, y + margin),
            (x + CELL_SIZE - 1 - margin, y + CELL_SIZE - 1 - margin),
        ],
        fill=TARGET_COLOR
    )


def _render_char_frame(char_frame):
    vertex_grid = _extract_vertex_grid(char_frame)

    rows = len(vertex_grid)
    cols = len(vertex_grid[0])

    image = Image.new("RGBA", (cols * CELL_SIZE, rows * CELL_SIZE), FREE_CELL_COLOR)
    draw = ImageDraw.Draw(image)

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    for r, row in enumerate(vertex_grid):
        for c, cell in enumerate(row):
            x = c * CELL_SIZE
            y = r * CELL_SIZE

            if cell == '#':
                _draw_obstacle(draw, x, y)
            else:
                _draw_cell_background(draw, x, y)

            if cell == 'a':
                _draw_trail(overlay_draw, x, y)
            elif cell == 'B':
                _draw_target(draw, x, y)
            elif cell == 'A':
                _draw_agent(draw, x, y)

    final_image = Image.alpha_composite(image, overlay)
    return final_image.convert("RGB")


def animate_astar_frames(astar_frames):
    """
    Convert each char frame into one PNG image.

    Output folder:
    - classical_animation
    - cyclic_animation
    """
    if not astar_frames:
        return

    animation_type = _detect_animation_type(astar_frames)
    output_dir = _get_output_directory(animation_type)
    _prepare_output_directory(output_dir)

    for frame_index, char_frame in enumerate(astar_frames, start=1):
        image = _render_char_frame(char_frame)
        image.save(output_dir / f"frame_{frame_index:04d}.png")