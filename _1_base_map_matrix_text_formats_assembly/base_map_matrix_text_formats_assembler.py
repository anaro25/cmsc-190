from pathlib import Path
from PIL import Image


BASE_DIR = Path(__file__).resolve().parent
RASTERIZED_IMAGES_DIR = BASE_DIR / "_1_base_map_rasterized_images"
MATRIX_TEXT_FORMATS_DIR = BASE_DIR / "_2_base_map_matrix_text_formats"


def pixel_to_text_symbol(pixel, image_path, x, y):
    if pixel == (255, 255, 255):
        return "o"
    if pixel == (0, 0, 0):
        return "#"

    raise ValueError(
        f"Image '{image_path.name}' contains a non-binary pixel at "
        f"({x}, {y}): {pixel}"
    )


def image_to_text_rows(image_path):
    """
    Convert a pure black-and-white PNG image into rows of text symbols.

    white -> o
    black -> #
    """
    img = Image.open(image_path).convert("RGB")
    width, height = img.size

    text_rows = []

    for y in range(height):
        row = []

        for x in range(width):
            pixel = img.getpixel((x, y))
            row.append(pixel_to_text_symbol(pixel, image_path, x, y))

        text_rows.append(row)

    return text_rows


def write_base_map_matrix_text_format(text_rows, output_path):
    """
    Write the text rows into an .xml text file.

    FREE_SPACE -> o
    OBSTACLE   -> #

    Elements are one space apart.
    """
    with open(output_path, "w", encoding="utf-8") as file:
        file.write("<matrix>\n")

        for row in text_rows:
            file.write(" ".join(row) + "\n")

        file.write("</matrix>\n")


def assemble_base_map_matrix_text_formats():
    """
    Read rasterized PNG images and write their corresponding
    base map matrix text-format XML files.
    """
    MATRIX_TEXT_FORMATS_DIR.mkdir(exist_ok=True)

    image_filenames = [
        "port_1_base_map_rasterized_image.png",
        "port_2_base_map_rasterized_image.png",
        "port_3_base_map_rasterized_image.png",
        "campus_base_map_rasterized_image.png",
    ]

    for image_filename in image_filenames:
        image_path = RASTERIZED_IMAGES_DIR / image_filename

        if not image_path.exists():
            raise FileNotFoundError(f"Missing rasterized image: {image_path}")

        text_rows = image_to_text_rows(image_path)

        text_format_filename = image_filename.replace(
            "_base_map_rasterized_image.png",
            "_base_map_matrix_text_format.xml"
        )
        text_format_path = MATRIX_TEXT_FORMATS_DIR / text_format_filename

        write_base_map_matrix_text_format(text_rows, text_format_path)