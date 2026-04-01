from pathlib import Path

from PIL import Image

from project_level_modules.composite_matrix_elements import Vertex


def _image_to_base_map(image_path: Path) -> list[list[Vertex]]:
    """
    Convert a black-and-white PNG image into a 2D list of Vertex enums.

    White pixel -> Vertex.FREE_SPACE
    Black pixel -> Vertex.OBSTACLE
    """
    image = Image.open(image_path).convert("RGB")
    width, height = image.size

    base_map = []

    for y in range(height):
        row = []

        for x in range(width):
            pixel = image.getpixel((x, y))

            if pixel == (255, 255, 255):
                row.append(Vertex.FREE_SPACE)
            elif pixel == (0, 0, 0):
                row.append(Vertex.OBSTACLE)
            else:
                raise ValueError(
                    f"Unexpected pixel color {pixel} in {image_path.name} at ({x}, {y}). "
                    "Image must contain only pure black and pure white pixels."
                )

        base_map.append(row)

    return base_map


def _vertex_to_symbol(vertex: Vertex) -> str:
    if vertex == Vertex.FREE_SPACE:
        return "o"
    if vertex == Vertex.OBSTACLE:
        return "#"

    raise ValueError(f"Unexpected vertex value: {vertex}")


def _write_base_map_xml(base_map: list[list[Vertex]], output_path: Path) -> None:
    """
    Write the base map into a plain text .xml file for logging only.

    Vertex.FREE_SPACE -> o
    Vertex.OBSTACLE   -> #
    """
    with output_path.open("w", encoding="utf-8") as file:
        for row in base_map:
            row_text = " ".join(_vertex_to_symbol(cell) for cell in row)
            file.write(f"{row_text}\n")


def assemble_base_maps() -> list[list[list[Vertex]]]:
    """
    Read the PNG images, convert them into 2D base maps,
    write XML log files, and return the base maps.

    Return order:
    [port_1, port_2, port_3, campus]
    """
    module_dir = Path(__file__).resolve().parent
    input_dir = module_dir / "rasterized_images"
    output_dir = module_dir / "base_map_logs"

    output_dir.mkdir(exist_ok=True)

    image_names = ["port_1", "port_2", "port_3", "campus"]
    base_maps = []

    for name in image_names:
        image_path = input_dir / f"{name}.png"

        if not image_path.exists():
            raise FileNotFoundError(f"Missing rasterized image: {image_path}")

        base_map = _image_to_base_map(image_path)
        base_maps.append(base_map)

        output_path = output_dir / f"{name}.xml"
        _write_base_map_xml(base_map, output_path)

    return base_maps