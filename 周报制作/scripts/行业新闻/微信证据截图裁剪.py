#!/usr/bin/env python3
"""Tight-crop white screenshot canvas and optionally cap output width."""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageOps


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--padding", type=int, default=12)
    parser.add_argument("--threshold", type=int, default=10)
    parser.add_argument("--max-width", type=int)
    return parser.parse_args()


def content_bbox(image: Image.Image, threshold: int):
    rgb = image.convert("RGB")
    white = Image.new("RGB", rgb.size, "white")
    difference = ImageChops.difference(rgb, white).convert("L")
    mask = difference.point(lambda value: 255 if value > threshold else 0)
    return mask.getbbox()


def main() -> None:
    args = parse_args()
    image = Image.open(args.input).convert("RGBA")
    before = image.size
    bbox = content_bbox(image, args.threshold)
    if bbox is None:
        raise SystemExit("No non-white content found; refusing to create an empty crop.")
    cropped = image.crop(bbox)
    if args.padding:
        cropped = ImageOps.expand(cropped, border=args.padding, fill="white")
    if args.max_width and cropped.width > args.max_width:
        height = round(cropped.height * args.max_width / cropped.width)
        cropped = cropped.resize((args.max_width, height), Image.Resampling.LANCZOS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(args.output, format="PNG")
    print(json.dumps({
        "input": str(args.input),
        "output": str(args.output),
        "before": list(before),
        "content_bbox": list(bbox),
        "after": list(cropped.size),
        "padding": args.padding,
        "max_width": args.max_width,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
