from pathlib import Path
from PIL import Image, ImageDraw


# visual constants
CELL_SIZE = 32
BACKGROUND_COLOR = (255, 255, 255)
FREE_CELL_COLOR = (245, 245, 245)
OBSTACLE_COLOR = (0, 0, 0)

AGENT_COLOR = (52, 120, 246)
TARGET_COLOR = (220, 60, 60)

TRAIL_COLOR = (52, 120, 246, 90)  # same hue as agent, faded with alpha

GRID_LINE_COLOR = (220, 220, 220)


def _detect_animation_type(astar_frames):
    """
    Detect whether the frames belong to classical or cyclic mapping.

    Classical frames contain bidirectional transition symbols: ↔, ↕
    Cyclic frames contain directional symbols: →, ←, ↑, ↓
    """
    for frame in astar_frames:
        for row in frame:
            for cell in row:
                if cell in {'↔', '↕'}:
                    return "classical"

    return "cyclic"


def _get_output_directory(animation_type):
    current_dir = Path(__file__).resolve().parent

    if animation_type == "classical":
        return current_dir / "classical_animation"
    elif animation_type == "cyclic":
        return current_dir / "cyclic_animation"
    else:
        raise ValueError(f"Unknown animation type: {animation_type}")


def _clear_existing_frames(output_dir):
    output_dir.mkdir(exist_ok=True)

    for png_file in output_dir.glob("*.png"):
        png_file.unlink()


def _draw_cell_background(draw, top_left_x, top_left_y):
    draw.rectangle(
        [
            (top_left_x, top_left_y),
            (top_left_x + CELL_SIZE - 1, top_left_y + CELL_SIZE - 1),
        ],
        fill=FREE_CELL_COLOR,
        outline=GRID_LINE_COLOR
    )


def _draw_obstacle(draw, top_left_x, top_left_y):
    draw.rectangle(
        [
            (top_left_x, top_left_y),
            (top_left_x + CELL_SIZE - 1, top_left_y + CELL_SIZE - 1),
        ],
        fill=OBSTACLE_COLOR,
        outline=GRID_LINE_COLOR
    )


def _draw_agent(draw, top_left_x, top_left_y):
    margin = CELL_SIZE // 6
    draw.ellipse(
        [
            (top_left_x + margin, top_left_y + margin),
            (top_left_x + CELL_SIZE - margin, top_left_y + CELL_SIZE - margin),
        ],
        fill=AGENT_COLOR
    )


def _draw_trail(overlay_draw, top_left_x, top_left_y):
    margin = CELL_SIZE // 3
    overlay_draw.ellipse(
        [
            (top_left_x + margin, top_left_y + margin),
            (top_left_x + CELL_SIZE - margin, top_left_y + CELL_SIZE - margin),
        ],
        fill=TRAIL_COLOR
    )


def _draw_target(draw, top_left_x, top_left_y):
    margin = CELL_SIZE // 4
    draw.rectangle(
        [
            (top_left_x + margin, top_left_y + margin),
            (top_left_x + CELL_SIZE - margin, top_left_y + CELL_SIZE - margin),
        ],
        fill=TARGET_COLOR
    )


def _render_char_frame(char_frame):
    rows = len(char_frame)
    cols = len(char_frame[0])

    image = Image.new(
        "RGBA",
        (cols * CELL_SIZE, rows * CELL_SIZE),
        BACKGROUND_COLOR
    )
    draw = ImageDraw.Draw(image)

    # separate transparent layer for faded trail
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    for r, row in enumerate(char_frame):
        for c, cell in enumerate(row):
            x = c * CELL_SIZE
            y = r * CELL_SIZE

            # draw background only for actual base cells
            if cell in {'o', 'A', 'B', 'a', '#'}:
                _draw_cell_background(draw, x, y)

            if cell == '#':
                _draw_obstacle(draw, x, y)
            elif cell == 'a':
                _draw_trail(overlay_draw, x, y)
            elif cell == 'B':
                _draw_target(draw, x, y)
            elif cell == 'A':
                _draw_agent(draw, x, y)

    return Image.alpha_composite(image, overlay).convert("RGB")


def animate_astar_frames(astar_frames):
    if not astar_frames:
        return

    animation_type = _detect_animation_type(astar_frames)
    output_dir = _get_output_directory(animation_type)
    _clear_existing_frames(output_dir)

    for frame_index, char_frame in enumerate(astar_frames, start=1):
        image = _render_char_frame(char_frame)
        output_path = output_dir / f"frame_{frame_index:04d}.png"
        image.save(output_path)