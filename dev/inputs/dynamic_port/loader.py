from pathlib import Path

from PIL import Image


def _binarize_pixel(value, threshold=127):
    if isinstance(value, int):
        return 1 if value <= threshold else 0

    if isinstance(value, tuple):
        grayscale = int(round(sum(value[:3]) / 3))
        return 1 if grayscale <= threshold else 0

    raise TypeError(f"Unsupported pixel value: {value!r}")


def build_fallback_port_matrix(rows=25, cols=25):
    """
    1 = obstacle, 0 = free space.
    Creates a 25x25 port-like yard with rectangular blocks and lanes.
    """
    grid = [[0 for _ in range(cols)] for _ in range(rows)]

    for r in range(rows):
        grid[r][0] = 1
        grid[r][-1] = 1
    for c in range(cols):
        grid[0][c] = 1
        grid[-1][c] = 1

    obstacle_rectangles = [
        (2, 2, 5, 5),
        (2, 8, 5, 11),
        (2, 14, 5, 17),
        (2, 20, 5, 22),
        (9, 3, 12, 6),
        (9, 9, 12, 12),
        (9, 15, 12, 18),
        (16, 2, 19, 5),
        (16, 8, 19, 11),
        (16, 14, 19, 17),
        (16, 20, 19, 22),
    ]

    for r0, c0, r1, c1 in obstacle_rectangles:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                grid[r][c] = 1

    for r in range(1, rows - 1):
        grid[r][7] = 0
        grid[r][13] = 0
        grid[r][19] = 0
    for c in range(1, cols - 1):
        grid[7][c] = 0
        grid[13][c] = 0

    return grid


def load_port_obstacle_matrix(image_path, threshold=127, resize_longest_side=None):
    image_path = Path(image_path)

    if not image_path.exists():
        return build_fallback_port_matrix()

    with Image.open(image_path) as image:
        grayscale_image = image.convert("L")
        if resize_longest_side is not None and resize_longest_side > 0:
            width, height = grayscale_image.size
            longest_side = max(width, height)
            if longest_side > resize_longest_side:
                scale = resize_longest_side / float(longest_side)
                resized_width = max(1, int(round(width * scale)))
                resized_height = max(1, int(round(height * scale)))
                grayscale_image = grayscale_image.resize((resized_width, resized_height), Image.NEAREST)
        width, height = grayscale_image.size
        pixels = grayscale_image.load()

        matrix = []
        for y in range(height):
            row = []
            for x in range(width):
                row.append(_binarize_pixel(pixels[x, y], threshold=threshold))
            matrix.append(row)

    return matrix
