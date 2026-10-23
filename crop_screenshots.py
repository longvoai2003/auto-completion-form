#!/usr/bin/env python3
import argparse
from pathlib import Path

from PIL import Image

DEFAULT_SRC = Path("screenshots/Long_csv")
DEFAULT_DEST = Path("processed_screenshot/Long_csv")
DEFAULT_WIDTH = 1009
DEFAULT_HEIGHT = 735
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def crop_image(src: Path, dest: Path, width: int, height: int):
    with Image.open(src) as image:
        original_size = image.size
        original_width, original_height = original_size
        if original_width < width or original_height < height:
            raise ValueError(
                f"Image {original_size} is smaller than {width}x{height}"
            )

        left = (original_width - width) // 2
        top = 0
        box = (left, top, left + width, top + height)
        cropped = image.crop(box)
        dest.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(dest)
        return original_size, cropped.size, box


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crop score screenshots from the source folder into the destination folder."
    )
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument(
        "--move",
        action="store_true",
        help="Delete each source image after it is cropped successfully",
    )
    args = parser.parse_args()

    if not args.src.is_dir():
        print(f"Source folder not found: {args.src}")
        return 1

    files = sorted(
        path
        for path in args.src.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not files:
        print(f"No images found in {args.src}")
        return 1

    args.dest.mkdir(parents=True, exist_ok=True)
    print(
        f"Cropping {len(files)} image(s): {args.src} -> {args.dest} "
        f"(centered {args.width}x{args.height})"
    )

    success = 0
    failed = 0
    for src in files:
        dest = args.dest / src.name
        try:
            original, cropped, box = crop_image(
                src, dest, args.width, args.height
            )
            print(
                f"{src.name}: {original[0]}x{original[1]} -> "
                f"{cropped[0]}x{cropped[1]} {box}"
            )
            if args.move:
                src.unlink()
            success += 1
        except Exception as exc:
            print(f"FAILED {src.name}: {exc}")
            failed += 1

    print(f"Done. success={success} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
