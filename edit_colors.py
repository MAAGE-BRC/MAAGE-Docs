
from PIL import Image
import numpy as np
from pathlib import Path
import argparse

# =========================
# CONFIG
# =========================

COLOR_MAP = {
    "#4c783d": "#467386",
    "#81a447": "#6d9e89",
}

TOLERANCE = 10

EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


# =========================
# HELPERS
# =========================

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def color_distance(c1, c2):
    return np.sqrt(np.sum((np.array(c1) - np.array(c2)) ** 2, axis=-1))


def recolor_image(input_path, output_path):
    img = Image.open(input_path).convert("RGBA")
    data = np.array(img)

    rgb = data[:, :, :3]

    for old_hex, new_hex in COLOR_MAP.items():
        old_rgb = hex_to_rgb(old_hex)
        new_rgb = hex_to_rgb(new_hex)

        mask = color_distance(rgb, old_rgb) <= TOLERANCE
        data[mask, :3] = new_rgb

    result = Image.fromarray(data)
    result.save(output_path)

    print(f"Processed: {input_path.name}")


# =========================
# CLI
# =========================

parser = argparse.ArgumentParser(
    description="Batch recolor images in a directory."
)

parser.add_argument(
    "input_dir",
    help="Directory containing input images"
)

parser.add_argument(
    "output_dir",
    help="Directory where recolored images will be saved"
)

args = parser.parse_args()

input_dir = Path(args.input_dir)
output_dir = Path(args.output_dir)

# =========================
# MAIN
# =========================

if not input_dir.exists():
    raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

output_dir.mkdir(parents=True, exist_ok=True)

image_files = [
    f for f in input_dir.iterdir()
    if f.suffix.lower() in EXTENSIONS
]

if not image_files:
    print("No supported images found.")
else:
    for image_path in image_files:
        output_path = output_dir / image_path.name

        try:
            recolor_image(image_path, output_path)
        except Exception as e:
            print(f"Failed on {image_path.name}: {e}")

    print("\nDone!")
