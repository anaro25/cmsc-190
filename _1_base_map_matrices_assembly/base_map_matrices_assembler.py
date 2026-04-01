from pathlib import Path
from PIL import Image

from project_level_modules.composite_matrix_elements import Vertex


BASE_DIR = Path(__file__).resolve().parent
RASTERIZED_IMAGES_DIR = BASE_DIR / "_1_base_map_rasterized_images"
MATRIX_LOGS_DIR = BASE_DIR / "_2_base_map_matrix_logs"


def image_to_base_map_matrix(image_path):
    """
    Convert a pure black-and-white PNG image into a 2D list of Vertex enums.

    white -> Vertex.FREE_SPACE
    black -> Vertex.OBSTACLE
    """
    img = Image.open(image_path).convert("RGB")
    width, height = img.size

    base_map_matrix = []

    for y in range(height):
        row = []

        for x in range(width):
            pixel = img.getpixel((x, y))

            if pixel == (255, 255, 255):
                row.append(Vertex.FREE_SPACE)
            elif pixel == (0, 0, 0):
                row.append(Vertex.OBSTACLE)
            else:
                raise ValueError(
                    f"Image '{image_path.name}' contains a non-binary pixel at "
                    f"({x}, {y}): {pixel}"
                )

        base_map_matrix.append(row)

    return base_map_matrix


def vertex_to_log_symbol(vertex):
    if vertex == Vertex.FREE_SPACE:
        return "o"
    if vertex == Vertex.OBSTACLE:
        return "#"

    raise ValueError(f"Unexpected vertex value: {vertex}")


def write_base_map_matrix_log(base_map_matrix, output_path):
    """
    Write the matrix into an .xml log file.

    FREE_SPACE -> o
    OBSTACLE   -> #

    Elements are one space apart.
    """
    with open(output_path, "w", encoding="utf-8") as file:
        file.write("<matrix>\n")

        for row in base_map_matrix:
            log_row = [vertex_to_log_symbol(vertex) for vertex in row]
            file.write(" ".join(log_row) + "\n")

        file.write("</matrix>\n")


def assemble_base_map_matrices():
    """
    Reads all rasterized base map PNG images, converts them into 2D lists
    of Vertex enums, writes their logs, and returns them as a list.

    Return order:
    [
        port_1_base_map_matrix,
        port_2_base_map_matrix,
        port_3_base_map_matrix,
        campus_base_map_matrix
    ]
    """
    MATRIX_LOGS_DIR.mkdir(exist_ok=True)

    image_filenames = [
        "port_1_base_map_rasterized_image.png",
        "port_2_base_map_rasterized_image.png",
        "port_3_base_map_rasterized_image.png",
        "campus_base_map_rasterized_image.png",
    ]

    base_map_matrices = []

    for image_filename in image_filenames:
        image_path = RASTERIZED_IMAGES_DIR / image_filename

        if not image_path.exists():
            raise FileNotFoundError(f"Missing rasterized image: {image_path}")

        base_map_matrix = image_to_base_map_matrix(image_path)
        base_map_matrices.append(base_map_matrix)

        log_filename = image_filename.replace(
            "_base_map_rasterized_image.png",
            "_base_map_matrix_log.xml"
        )
        output_path = MATRIX_LOGS_DIR / log_filename

        write_base_map_matrix_log(base_map_matrix, output_path)

    return base_map_matrices