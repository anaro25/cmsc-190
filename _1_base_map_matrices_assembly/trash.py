from pathlib import Path
from PIL import Image


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "1_rasterized_images"
OUTPUT_DIR = BASE_DIR / "2_raw_matrices"


def image_to_binary_matrix(image_path):
    """
    Convert a pure black-and-white PNG image into a binary matrix.
    white -> 0
    black -> 1
    """
    img = Image.open(image_path).convert("RGB")
    width, height = img.size

    matrix = []

    for y in range(height):
        row = []
        for x in range(width):
            pixel = img.getpixel((x, y))

            if pixel == (255, 255, 255):
                row.append("o")
            elif pixel == (0, 0, 0):
                row.append("#")
            else:
                raise ValueError(
                    f"Image {image_path.name} contains a non-binary pixel at ({x}, {y}): {pixel}"
                )

        matrix.append(row)

    return matrix


def write_matrix_xml(matrix, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("<matrix>\n")
        for row in matrix:
            f.write(" ".join(row) + "\n")
        f.write("</matrix>\n")


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    png_files = sorted(INPUT_DIR.glob("*.png"))

    if not png_files:
        print(f"No PNG files found in: {INPUT_DIR}")
        return

    for image_path in png_files:
        matrix = image_to_binary_matrix(image_path)
        output_name = f"{image_path.stem}_raw_matrix.xml"
        output_path = OUTPUT_DIR / output_name

        write_matrix_xml(matrix, output_path)
        print(f"Written: {output_path}")


if __name__ == "__main__":
    main()