from colorsys import hsv_to_rgb


def build_distinct_rgb_palette(num_colors):
    """
    Returns visually distinct RGB tuples.
    """
    if num_colors <= 0:
        return []

    palette = []
    for index in range(num_colors):
        hue = index / max(1, num_colors)
        saturation = 0.75
        value = 0.90
        r, g, b = hsv_to_rgb(hue, saturation, value)
        palette.append((int(r * 255), int(g * 255), int(b * 255)))

    return palette
