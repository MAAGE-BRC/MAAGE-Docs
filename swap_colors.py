#!/usr/bin/env python3

import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image

# --- Configuration ---
OLD_TO_NEW_COLORS = [
    (
        np.array([0x76, 0xA7, 0x2D], dtype=np.float64),  # #76a72d
        np.array([0x5F, 0x94, 0xAB], dtype=np.float64),  # #5f94ab
    ),
    (
        np.array([0x82, 0xA6, 0x43], dtype=np.float64),  # #82a643
        np.array([0x5F, 0x94, 0xAB], dtype=np.float64),  # #5f94ab
    ),
]

DEFAULT_IMAGE_DIR = "/home/ac.cucinell/public_html"
DEFAULT_TOLERANCE = 10


def swap_color_in_image(filepath, tolerance, apply=False):
    img = Image.open(filepath)
    original_mode = img.mode

    if img.mode in ("RGBA", "PA"):
        arr = np.array(img.convert("RGBA"))
        has_alpha = True
    elif img.mode == "P":
        arr = np.array(img.convert("RGB"))
        has_alpha = False
    else:
        arr = np.array(img.convert("RGB"))
        has_alpha = False

    rgb = arr[:, :, :3].astype(np.float64)

    total_count = 0

    for old_color_rgb, new_color_rgb in OLD_TO_NEW_COLORS:
        diff = np.abs(rgb - old_color_rgb)
        mask = np.all(diff <= tolerance, axis=2)

        count = int(mask.sum())
        if count == 0:
            continue

        total_count += count

        if apply:
            shift = new_color_rgb - old_color_rgb
            rgb[mask] = rgb[mask] + shift

    if total_count == 0:
        return 0

    if apply:
        rgb = np.clip(rgb, 0, 255)
        arr[:, :, :3] = rgb.astype(np.uint8)

        out_img = Image.fromarray(arr, "RGBA" if has_alpha else "RGB")

        if original_mode == "P":
            out_img = out_img.convert("P")
        elif original_mode == "PA":
            out_img = out_img.convert("PA")

        out_img.save(filepath)

    return total_count


def find_images(base_dir):
    patterns = ["**/*.png", "**/*.jpg", "**/*.jpeg", "**/*.gif"]
    results = []

    for pat in patterns:
        for fpath in glob.glob(os.path.join(base_dir, pat), recursive=True):
            rel = os.path.relpath(fpath, base_dir)

            if rel.startswith("_build" + os.sep) or rel.startswith("_build/"):
                continue

            results.append(fpath)

    return sorted(results)


def main():
    parser = argparse.ArgumentParser(
        description="Swap green bar colors to #5f94ab in documentation images."
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually modify images in-place. Default is dry run.",
    )

    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Process a single file instead of scanning the whole directory.",
    )

    parser.add_argument(
        "--dir",
        type=str,
        default=DEFAULT_IMAGE_DIR,
        help=f"Base directory to scan. Default: {DEFAULT_IMAGE_DIR}",
    )

    parser.add_argument(
        "--tolerance",
        type=int,
        default=DEFAULT_TOLERANCE,
        help=f"Per-channel color tolerance. Default: {DEFAULT_TOLERANCE}",
    )

    args = parser.parse_args()

    image_dir = os.path.abspath(args.dir)

    if args.file:
        files = [os.path.abspath(args.file)]
    else:
        if not os.path.isdir(image_dir):
            print(f"ERROR: Image directory not found: {image_dir}")
            sys.exit(1)

        files = find_images(image_dir)

    mode_label = "APPLY" if args.apply else "DRY RUN"

    print(f"Mode: {mode_label}")
    print(f"Replacing #76a72d -> #5f94ab")
    print(f"Replacing #82a643 -> #5f94ab")
    print(f"Tolerance: +/-{args.tolerance} per channel")
    print(f"Scanning {len(files)} image(s)...\n")

    total_files_changed = 0
    total_pixels_changed = 0

    for fpath in files:
        try:
            count = swap_color_in_image(
                fpath,
                args.tolerance,
                apply=args.apply,
            )
        except Exception as e:
            print(f"  ERROR: {fpath}: {e}")
            continue

        if count > 0:
            rel = os.path.relpath(fpath, image_dir) if not args.file else fpath
            action = "changed" if args.apply else "would change"
            print(f"  {rel}: {count} pixels {action}")

            total_files_changed += 1
            total_pixels_changed += count

    final_action = "changed" if args.apply else "would be changed"

    print(
        f"\nSummary: {total_files_changed} file(s), "
        f"{total_pixels_changed} pixel(s) {final_action}."
    )


if __name__ == "__main__":
    main()

# #!/usr/bin/env python3
# """
# Swap the green action bar color (~#76a72d) with #5f94ab (blue) in all
# PNG images under a target directory (default: ~/public_html).

# Uses tolerance-based matching to catch anti-aliased and compression-
# artifact pixels near the target green, and shifts them proportionally
# into the blue color space.

# Usage:
#     # Dry run (default) — reports which files would be changed:
#     python3 swap_color.py

#     # Actually modify the images in-place:
#     python3 swap_color.py --apply

#     # Process a single file (dry run):
#     python3 swap_color.py --file path/to/image.png

#     # Process a single file (apply):
#     python3 swap_color.py --file path/to/image.png --apply

#     # Use a custom directory:
#     python3 swap_color.py --dir /path/to/images --apply

#     # Adjust tolerance (default 10):
#     python3 swap_color.py --tolerance 15 --apply
# """

# import argparse
# import glob
# import os
# import sys

# import numpy as np
# from PIL import Image

# # --- Configuration ---
# OLD_COLOR_RGB = np.array([0x76, 0xA7, 0x2D], dtype=np.float64)  # #76a72d (green)
# NEW_COLOR_RGB = np.array([0x5F, 0x94, 0xAB], dtype=np.float64)  # #5f94ab (blue)

# #DEFAULT_IMAGE_DIR = "/home/ac.cucinell/public_html"
# DEFAULT_TOLERANCE = 10  # per-channel tolerance


# def swap_color_in_image(filepath, tolerance, apply=False):
#     """
#     Replace all pixels within `tolerance` of OLD_COLOR_RGB, shifting them
#     proportionally toward NEW_COLOR_RGB.

#     For pixels that exactly match OLD_COLOR_RGB, they become exactly
#     NEW_COLOR_RGB. For pixels that are close (e.g. anti-aliased edges),
#     the same offset is applied so gradients remain smooth.

#     Returns the number of pixels changed, or 0 if no match.
#     If apply=False, the file is not modified (dry run).
#     """
#     img = Image.open(filepath)
#     original_mode = img.mode

#     # Work in RGBA to preserve transparency; fall back to RGB
#     if img.mode in ("RGBA", "PA"):
#         arr = np.array(img.convert("RGBA"))
#         has_alpha = True
#     elif img.mode == "P":
#         arr = np.array(img.convert("RGB"))
#         has_alpha = False
#     else:
#         arr = np.array(img.convert("RGB"))
#         has_alpha = False

#     rgb = arr[:, :, :3].astype(np.float64)

#     # Build a mask: each channel within tolerance of the old color
#     diff = np.abs(rgb - OLD_COLOR_RGB)
#     mask = np.all(diff <= tolerance, axis=2)

#     count = int(mask.sum())
#     if count == 0:
#         return 0

#     if apply:
#         # Compute the shift vector (new - old) and apply it to matched pixels
#         shift = NEW_COLOR_RGB - OLD_COLOR_RGB
#         rgb[mask] = rgb[mask] + shift
#         # Clamp to valid range
#         rgb = np.clip(rgb, 0, 255)
#         arr[:, :, :3] = rgb.astype(np.uint8)

#         out_img = Image.fromarray(arr, "RGBA" if has_alpha else "RGB")
#         if original_mode == "P":
#             out_img = out_img.convert("P")
#         elif original_mode == "PA":
#             out_img = out_img.convert("PA")
#         out_img.save(filepath)

#     return count


# def find_images(base_dir):
#     """Find all PNG/JPG/GIF images under base_dir, excluding _build/."""
#     patterns = ["**/*.png", "**/*.jpg", "**/*.jpeg", "**/*.gif"]
#     results = []
#     for pat in patterns:
#         for fpath in glob.glob(os.path.join(base_dir, pat), recursive=True):
#             rel = os.path.relpath(fpath, base_dir)
#             if rel.startswith("_build" + os.sep) or rel.startswith("_build/"):
#                 continue
#             results.append(fpath)
#     return sorted(results)


# def main():
#     parser = argparse.ArgumentParser(
#         description="Swap green bar color (~#76a72d) -> #5f94ab in documentation images."
#     )
#     parser.add_argument(
#         "--apply", action="store_true",
#         help="Actually modify images in-place (default is dry run)."
#     )
#     parser.add_argument(
#         "--file", type=str, default=None,
#         help="Process a single file instead of scanning the whole directory."
#     )
#     parser.add_argument(
#         "--dir", type=str, default=DEFAULT_IMAGE_DIR,
#         help=f"Base directory to scan (default: {DEFAULT_IMAGE_DIR})."
#     )
#     parser.add_argument(
#         "--tolerance", type=int, default=DEFAULT_TOLERANCE,
#         help=f"Per-channel color tolerance (default: {DEFAULT_TOLERANCE})."
#     )
#     args = parser.parse_args()

#     image_dir = os.path.abspath(args.dir)

#     if args.file:
#         files = [os.path.abspath(args.file)]
#     else:
#         if not os.path.isdir(image_dir):
#             print(f"ERROR: Image directory not found: {image_dir}")
#             sys.exit(1)
#         files = find_images(image_dir)

#     mode_label = "APPLY" if args.apply else "DRY RUN"
#     old_hex = f"#{int(OLD_COLOR_RGB[0]):02x}{int(OLD_COLOR_RGB[1]):02x}{int(OLD_COLOR_RGB[2]):02x}"
#     new_hex = f"#{int(NEW_COLOR_RGB[0]):02x}{int(NEW_COLOR_RGB[1]):02x}{int(NEW_COLOR_RGB[2]):02x}"
#     print(f"Mode: {mode_label}")
#     print(f"Old color: {old_hex}  (tolerance: +/-{args.tolerance} per channel)")
#     print(f"New color: {new_hex}")
#     print(f"Scanning {len(files)} image(s)...\n")

#     total_files_changed = 0
#     total_pixels_changed = 0

#     for fpath in files:
#         try:
#             count = swap_color_in_image(fpath, args.tolerance, apply=args.apply)
#         except Exception as e:
#             print(f"  ERROR: {fpath}: {e}")
#             continue

#         if count > 0:
#             rel = os.path.relpath(fpath, image_dir) if not args.file else fpath
#             action = "changed" if args.apply else "would change"
#             print(f"  {rel}: {count} pixels {action}")
#             total_files_changed += 1
#             total_pixels_changed += count

#     print(f"\nSummary: {total_files_changed} file(s), {total_pixels_changed} pixel(s) {'changed' if args.apply else 'would be changed'}.")


# if __name__ == "__main__":
#     main()
