from pathlib import Path

from PIL import Image


CAMPUS_ZONE_RGBS = (
    (182, 218, 249),  # blue
    (175, 252, 198),  # green
    (245, 196, 198),  # light red
)
CAMPUS_SINGLE_TARGET_RGBS = (
    (40, 140, 227),  # dark blue single-target marker
    (66, 218, 111),  # dark green single-target marker
    (232, 120, 122),  # dark red single-target marker
)
CAMPUS_GRAY_RGB = (208, 208, 208)
CAMPUS_WHITE_RGB = (255, 255, 255)
CAMPUS_BLACK_RGB = (0, 0, 0)


def _binarize_pixel(value, threshold=127):
    if isinstance(value, int):
        return 1 if value <= threshold else 0

    if isinstance(value, tuple):
        grayscale = int(round(sum(value[:3]) / 3))
        return 1 if grayscale <= threshold else 0

    raise TypeError(f"Unsupported pixel value: {value!r}")


def _is_pure_white_pixel(value):
    if isinstance(value, int):
        return value == 255

    if isinstance(value, tuple):
        return all(channel == 255 for channel in value[:3])

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


def _load_resized_images(image_path, resize_longest_side=None):
    image_path = Path(image_path)

    if not image_path.exists():
        return None, None

    with Image.open(image_path) as image:
        rgb_image = image.convert("RGB")
        grayscale_image = image.convert("L")
        if resize_longest_side is not None and resize_longest_side > 0:
            width, height = grayscale_image.size
            longest_side = max(width, height)
            if longest_side > resize_longest_side:
                scale = resize_longest_side / float(longest_side)
                resized_width = max(1, int(round(width * scale)))
                resized_height = max(1, int(round(height * scale)))
                resize_size = (resized_width, resized_height)
                rgb_image = rgb_image.resize(resize_size, Image.NEAREST)
                grayscale_image = grayscale_image.resize(resize_size, Image.NEAREST)
        return rgb_image, grayscale_image


def load_port_obstacle_matrix(image_path, threshold=127, resize_longest_side=None):
    _, grayscale_image = _load_resized_images(
        image_path=image_path,
        resize_longest_side=resize_longest_side,
    )
    if grayscale_image is None:
        return build_fallback_port_matrix()

    width, height = grayscale_image.size
    pixels = grayscale_image.load()

    matrix = []
    for y in range(height):
        row = []
        for x in range(width):
            row.append(_binarize_pixel(pixels[x, y], threshold=threshold))
        matrix.append(row)

    return matrix


def load_spawnable_white_mask(image_path, resize_longest_side=None):
    rgb_image, _ = _load_resized_images(
        image_path=image_path,
        resize_longest_side=resize_longest_side,
    )
    if rgb_image is None:
        fallback = build_fallback_port_matrix()
        return [[cell == 0 for cell in row] for row in fallback]

    width, height = rgb_image.size
    pixels = rgb_image.load()

    mask = []
    for y in range(height):
        row = []
        for x in range(width):
            row.append(_is_pure_white_pixel(pixels[x, y]))
        mask.append(row)

    return mask


def _rgb_tuple(value):
    if isinstance(value, int):
        return (value, value, value)

    if isinstance(value, tuple):
        return tuple(int(channel) for channel in value[:3])

    raise TypeError(f"Unsupported pixel value: {value!r}")


def _is_rgb_close(value, target_rgb, tolerance=8):
    rgb = _rgb_tuple(value)
    return all(abs(channel - target) <= tolerance for channel, target in zip(rgb, target_rgb))


def _classify_campus_pixel(value, tolerance=8):
    if _is_rgb_close(value, CAMPUS_BLACK_RGB, tolerance=tolerance):
        return ("obstacle", None, False)
    if _is_rgb_close(value, CAMPUS_GRAY_RGB, tolerance=tolerance):
        return ("gray", None, False)
    if _is_rgb_close(value, CAMPUS_WHITE_RGB, tolerance=tolerance):
        return ("walkway", None, False)

    for zone_id, zone_rgb in enumerate(CAMPUS_ZONE_RGBS, start=1):
        if _is_rgb_close(value, zone_rgb, tolerance=tolerance):
            return ("zone", zone_id, False)

    for zone_id, marker_rgb in enumerate(CAMPUS_SINGLE_TARGET_RGBS, start=1):
        if _is_rgb_close(value, marker_rgb, tolerance=tolerance):
            return ("zone", zone_id, True)

    rgb = _rgb_tuple(value)
    raise ValueError(
        "Unsupported campus-map pixel color encountered. "
        "Expected black, white, gray, one of the regular campus zone colors, "
        f"or one of the dark single-target marker colors, but found {rgb}."
    )


def load_campus_semantic_masks(image_path, resize_longest_side=None, color_tolerance=8):
    rgb_image, _ = _load_resized_images(
        image_path=image_path,
        resize_longest_side=resize_longest_side,
    )
    if rgb_image is None:
        fallback = build_fallback_port_matrix()
        zone_id_matrix = []
        single_target_id_matrix = []
        traversable_matrix = []
        zone_spawn_mask = []
        single_target_mask = []
        walkway_mask = []
        gray_mask = []
        for row in fallback:
            traversable_row = []
            zone_row = []
            single_target_row = []
            walkway_row = []
            gray_row = []
            zone_id_row = []
            single_target_id_row = []
            for cell in row:
                is_free = cell == 0
                traversable_row.append(0 if is_free else 1)
                zone_row.append(is_free)
                single_target_row.append(False)
                walkway_row.append(False)
                gray_row.append(False)
                zone_id_row.append(1 if is_free else None)
                single_target_id_row.append(None)
            traversable_matrix.append(traversable_row)
            zone_spawn_mask.append(zone_row)
            single_target_mask.append(single_target_row)
            walkway_mask.append(walkway_row)
            gray_mask.append(gray_row)
            zone_id_matrix.append(zone_id_row)
            single_target_id_matrix.append(single_target_id_row)
        return {
            "traversable_matrix": traversable_matrix,
            "zone_spawn_mask": zone_spawn_mask,
            "single_target_mask": single_target_mask,
            "walkway_mask": walkway_mask,
            "gray_mask": gray_mask,
            "zone_id_matrix": zone_id_matrix,
            "single_target_id_matrix": single_target_id_matrix,
        }

    width, height = rgb_image.size
    pixels = rgb_image.load()

    traversable_matrix = []
    zone_spawn_mask = []
    single_target_mask = []
    walkway_mask = []
    gray_mask = []
    zone_id_matrix = []
    single_target_id_matrix = []

    for y in range(height):
        traversable_row = []
        zone_row = []
        single_target_row = []
        walkway_row = []
        gray_row = []
        zone_id_row = []
        single_target_id_row = []
        for x in range(width):
            pixel_type, zone_id, is_single_target_marker = _classify_campus_pixel(pixels[x, y], tolerance=color_tolerance)
            traversable_row.append(0 if pixel_type in {"zone", "walkway"} else 1)
            zone_row.append(pixel_type == "zone")
            single_target_row.append(is_single_target_marker)
            walkway_row.append(pixel_type == "walkway")
            gray_row.append(pixel_type == "gray")
            zone_id_row.append(zone_id)
            single_target_id_row.append(zone_id if is_single_target_marker else None)
        traversable_matrix.append(traversable_row)
        zone_spawn_mask.append(zone_row)
        single_target_mask.append(single_target_row)
        walkway_mask.append(walkway_row)
        gray_mask.append(gray_row)
        zone_id_matrix.append(zone_id_row)
        single_target_id_matrix.append(single_target_id_row)

    return {
        "traversable_matrix": traversable_matrix,
        "zone_spawn_mask": zone_spawn_mask,
        "single_target_mask": single_target_mask,
        "walkway_mask": walkway_mask,
        "gray_mask": gray_mask,
        "zone_id_matrix": zone_id_matrix,
        "single_target_id_matrix": single_target_id_matrix,
    }
