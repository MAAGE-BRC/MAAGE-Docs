#!/usr/bin/env python3
"""
Fix green fringe/bleed on white icons and text within the blue action bar.

After swapping the green bar color to blue, anti-aliased edges of white
icons/text still have green-tinted transition pixels. This script finds
those pixels and re-tints them to match a white-on-blue transition instead.

The approach:
  1. Locate the blue action bar in each image (vertical strip of ~#5f94ab).
  2. Within the bar region, find pixels with a green excess (G channel
     disproportionately higher than R and B).
  3. Re-map those pixels: replace the green bias with a blue bias that
     matches the new bar color, preserving the luminance/alpha relationship.

Usage:
    python3 fix_green_fringe.py                        # dry run
    python3 fix_green_fringe.py --apply                # modify in-place
    python3 fix_green_fringe.py --file path/to/img.png # single file
    python3 fix_green_fringe.py --file path/to/img.png --apply
"""

import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image

DEFAULT_IMAGE_DIR = "/home/ac.cucinell/public_html"

# The new bar color after the green->blue swap
BAR_COLOR = np.array([0x5F, 0x94, 0xAB], dtype=np.float64)
BAR_TOLERANCE = 15  # tolerance for identifying bar pixels

# Minimum green excess (G - avg(R,B)) to consider a pixel "green-tinted"
MIN_GREEN_EXCESS = 5


def fix_fringe_in_image(filepath, apply=False):
    """
    Find the blue action bar, then fix green-fringed pixels within it.
    Returns the number of pixels fixed, or 0 if none found.
    """
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

    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.float64)

    # 1. Find the blue bar pixels
    blue_diff = np.abs(rgb - BAR_COLOR)
    blue_mask = np.all(blue_diff <= BAR_TOLERANCE, axis=2)

    # Check if there's a meaningful number of bar pixels
    if blue_mask.sum() < 50:
        return 0

    # 2. Find contiguous vertical bar strips (the action bar)
    #    The action bar is a narrow vertical strip, typically 30-60px wide,
    #    where most of the column height is filled with the bar color.
    col_blue_count = blue_mask.sum(axis=0)

    # A column is a "bar column" if at least 20% of its height is blue
    min_col_fill = max(20, h * 0.15)
    candidate_cols = np.where(col_blue_count >= min_col_fill)[0]
    if len(candidate_cols) == 0:
        return 0

    # Find contiguous runs of bar columns (the actual bar strip)
    bar_strips = []
    run_start = candidate_cols[0]
    for i in range(1, len(candidate_cols)):
        if candidate_cols[i] != candidate_cols[i - 1] + 1:
            # End of a contiguous run
            run_width = candidate_cols[i - 1] - run_start + 1
            if run_width >= 5:  # bar must be at least 5px wide
                bar_strips.append((run_start, candidate_cols[i - 1]))
            run_start = candidate_cols[i]
    # Don't forget the last run
    run_width = candidate_cols[-1] - run_start + 1
    if run_width >= 5:
        bar_strips.append((run_start, candidate_cols[-1]))

    if len(bar_strips) == 0:
        return 0

    # Also find contiguous horizontal bar strips
    row_blue_count = blue_mask.sum(axis=1)
    min_row_fill = max(20, w * 0.15)
    candidate_rows = np.where(row_blue_count >= min_row_fill)[0]
    h_bar_strips = []
    if len(candidate_rows) > 0:
        run_start_r = candidate_rows[0]
        for i in range(1, len(candidate_rows)):
            if candidate_rows[i] != candidate_rows[i - 1] + 1:
                run_height = candidate_rows[i - 1] - run_start_r + 1
                if run_height >= 5:
                    h_bar_strips.append((run_start_r, candidate_rows[i - 1]))
                run_start_r = candidate_rows[i]
        run_height = candidate_rows[-1] - run_start_r + 1
        if run_height >= 5:
            h_bar_strips.append((run_start_r, candidate_rows[-1]))

    # Build a mask covering the bar region + a few pixels of padding for fringe
    bar_region_mask = np.zeros((h, w), dtype=bool)
    pad = 3
    for cs, ce in bar_strips:
        bar_region_mask[:, max(0, cs - pad):min(w, ce + pad + 1)] = True
    for rs, re in h_bar_strips:
        bar_region_mask[max(0, rs - pad):min(h, re + pad + 1), :] = True

    # 3. Within the bar region, find green-tinted pixels
    #    Must have high G relative to R and B, AND B must be lower than G
    #    (to distinguish from blue-to-white transitions which also have G > avg)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    green_excess = g - (r + b) / 2.0
    green_tinted = (green_excess > MIN_GREEN_EXCESS) & (g > 80) & (b < g - 10)

    # Exclude the actual blue bar pixels
    not_blue = ~blue_mask

    # The fringe pixels: in bar region, green-tinted, not the bar itself
    fringe_mask = bar_region_mask & green_tinted & not_blue

    count = int(fringe_mask.sum())
    if count == 0:
        return 0

    if apply:
        # Re-tint fringe pixels:
        # The fringe was originally a blend between white (255,255,255)
        # and the old green bar (#76a72d). We want to remap it to a blend
        # between white and the new blue bar (#5f94ab).
        #
        # Strategy: figure out the "blend factor" (how much bar vs white)
        # from the old green tint, then reconstruct with the new blue color.
        #
        # Old green bar: R=118, G=167, B=45
        # For a pixel that was alpha-blended: pixel = alpha*bar + (1-alpha)*white
        # We can estimate alpha from the green channel since it has the most
        # distinctive difference between bar (167) and white (255):
        #   G = alpha*167 + (1-alpha)*255
        #   alpha = (255 - G) / (255 - 167)

        old_bar = np.array([118.0, 167.0, 45.0])
        white = 255.0

        fringe_pixels = rgb[fringe_mask]

        # Estimate alpha (blend factor) from each channel independently,
        # then average for robustness
        alphas = np.zeros(fringe_pixels.shape[0])
        for ch in range(3):
            denom = white - old_bar[ch]
            if abs(denom) > 1:
                ch_alpha = (white - fringe_pixels[:, ch]) / denom
                alphas += np.clip(ch_alpha, 0, 1)
        alphas /= 3.0
        alphas = np.clip(alphas, 0, 1)

        # Reconstruct with new blue bar color
        new_pixels = np.zeros_like(fringe_pixels)
        for ch in range(3):
            new_pixels[:, ch] = alphas * BAR_COLOR[ch] + (1 - alphas) * white

        new_pixels = np.clip(new_pixels, 0, 255)
        rgb[fringe_mask] = new_pixels
        arr[:, :, :3] = rgb.astype(np.uint8)

        out_img = Image.fromarray(arr, "RGBA" if has_alpha else "RGB")
        if original_mode == "P":
            out_img = out_img.convert("P")
        elif original_mode == "PA":
            out_img = out_img.convert("PA")
        out_img.save(filepath)

    return count


def find_images(base_dir):
    """Find all PNG/JPG/GIF images under base_dir, excluding _build/."""
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
        description="Fix green fringe on white icons within the blue action bar."
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually modify images in-place (default is dry run)."
    )
    parser.add_argument(
        "--file", type=str, default=None,
        help="Process a single file instead of scanning the whole directory."
    )
    parser.add_argument(
        "--dir", type=str, default=DEFAULT_IMAGE_DIR,
        help=f"Base directory to scan (default: {DEFAULT_IMAGE_DIR})."
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
    print(f"Fixing green fringe in blue action bar regions")
    print(f"Scanning {len(files)} image(s)...\n")

    total_files = 0
    total_pixels = 0

    for fpath in files:
        try:
            count = fix_fringe_in_image(fpath, apply=args.apply)
        except Exception as e:
            print(f"  ERROR: {fpath}: {e}")
            continue

        if count > 0:
            rel = os.path.relpath(fpath, image_dir) if not args.file else fpath
            action = "fixed" if args.apply else "would fix"
            print(f"  {rel}: {count} fringe pixels {action}")
            total_files += 1
            total_pixels += count

    print(f"\nSummary: {total_files} file(s), {total_pixels} fringe pixel(s) {'fixed' if args.apply else 'would be fixed'}.")


if __name__ == "__main__":
    main()
