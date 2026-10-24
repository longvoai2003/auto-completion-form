#!/usr/bin/env python3
import argparse
from pathlib import Path

from PIL import Image

SCREENSHOT_ROOT = Path("screenshots")
PROCESSED_ROOT = Path("processed_screenshot")
DEFAULT_SUBFOLDER = "Long_csv"
DEFAULT_WIDTH = 1009
DEFAULT_HEIGHT = 735
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def resolve_src(value: Path | None) -> Path:
    if value is None:
        return SCREENSHOT_ROOT / DEFAULT_SUBFOLDER
    if value.suffix.lower() == ".csv":
        return SCREENSHOT_ROOT / f"{value.stem}_csv"
    if value.is_absolute():
        return value
    if value.parts and value.parts[0] == SCREENSHOT_ROOT.name:
        return value
    return SCREENSHOT_ROOT / value


def resolve_dest(src: Path) -> Path:
    try:
        relative = src.resolve().relative_to(SCREENSHOT_ROOT.resolve())
    except ValueError:
        return PROCESSED_ROOT / src.name
    return PROCESSED_ROOT / relative


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
        description=(
            "Crop score screenshots from a subfolder of screenshots/ into "
            "the matching subfolder of processed_screenshot/."
        )
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=None,
        help=(
            "Source subfolder under screenshots/ "
            f"(default: {DEFAULT_SUBFOLDER}); a CSV path is also accepted"
        ),
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help=(
            "Override the destination folder "
            "(default: processed_screenshot/<source subfolder>)"
        ),
    )
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument(
        "--move",
        action="store_true",
        help="Delete each source image after it is cropped successfully",
    )
    args = parser.parse_args()

    src = resolve_src(args.src)
    dest = args.dest if args.dest is not None else resolve_dest(src)

    if not src.is_dir():
        print(f"Source folder not found: {src}")
        return 1

    files = sorted(
        path
        for path in src.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not files:
        print(f"No images found in {src}")
        return 1

    dest.mkdir(parents=True, exist_ok=True)
    print(
        f"Cropping {len(files)} image(s): {src} -> {dest} "
        f"(centered {args.width}x{args.height})"
    )

    success = 0
    failed = 0
    for path in files:
        dest_file = dest / path.name
        try:
            original, cropped, box = crop_image(
                path, dest_file, args.width, args.height
            )
            print(
                f"{path.name}: {original[0]}x{original[1]} -> "
                f"{cropped[0]}x{cropped[1]} {box}"
            )
            if args.move:
                path.unlink()
            success += 1
        except Exception as exc:
            print(f"FAILED {path.name}: {exc}")
            failed += 1

    print(f"Done. success={success} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
