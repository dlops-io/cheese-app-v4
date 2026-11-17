"""Data processor: clean raw.zip into clean.zip, the photos the model trains on.

    python cli.py --bucket <bucket>

For each cheese it keeps the photos that open, turns them into RGB JPEGs at most 512 px on a side, and
drops near-duplicates (the same photo, resized or recompressed, often shows up on several sites).
The ML pipeline runs this after the data collector; the model training picks clean.zip up from here.
"""

import argparse
import tempfile
import zipfile
from pathlib import Path

from google.cloud import storage
from PIL import Image

MAX_SIDE = 512
MIN_PER_LABEL = 10  # fewer than this, and the model has too little to learn from


def average_hash(image: Image.Image) -> int:
    """A fingerprint that survives resizing and recompression: 64 bits, one for each pixel of an 8x8
    grey thumbnail, set where that pixel is brighter than the average"""
    pixels = list(image.convert("L").resize((8, 8), Image.Resampling.LANCZOS).tobytes())  # 64 values
    average = sum(pixels) / len(pixels)
    return sum(1 << i for i, pixel in enumerate(pixels) if pixel > average)


def is_near_duplicate(fingerprint: int, seen: list[int], max_bits: int = 4) -> bool:
    return any((fingerprint ^ other).bit_count() <= max_bits for other in seen)


def clean_label(source: Path, target: Path) -> tuple[int, int, int]:
    """Returns (kept, broken, duplicates)"""
    target.mkdir(parents=True)
    seen: list[int] = []
    kept = broken = duplicates = 0
    for path in sorted(source.iterdir()):
        try:
            with Image.open(path) as image:
                if image.mode == "P":  # palette images (GIFs, some PNGs) keep transparency apart
                    image = image.convert("RGBA")
                image = image.convert("RGB")
        except Exception:
            broken += 1
            continue
        fingerprint = average_hash(image)
        if is_near_duplicate(fingerprint, seen):
            duplicates += 1
            continue
        seen.append(fingerprint)
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        kept += 1
        image.save(target / f"{kept:03d}.jpg", "JPEG", quality=90)
    return kept, broken, duplicates


def main() -> None:
    parser = argparse.ArgumentParser(description="Data processor")
    parser.add_argument("--bucket", required=True, help="the bucket with raw.zip; clean.zip goes there")
    args = parser.parse_args()
    bucket = storage.Client().bucket(args.bucket)

    with tempfile.TemporaryDirectory() as work:
        raw, clean = Path(work) / "raw", Path(work) / "clean"
        raw_zip = Path(work) / "raw.zip"
        bucket.blob("raw.zip").download_to_filename(raw_zip)
        with zipfile.ZipFile(raw_zip) as archive:
            archive.extractall(raw)

        for label_folder in sorted(path for path in raw.iterdir() if path.is_dir()):
            kept, broken, duplicates = clean_label(label_folder, clean / label_folder.name)
            print(f"{label_folder.name}: kept {kept}, {broken} broken, {duplicates} duplicates")
            if kept < MIN_PER_LABEL:
                raise SystemExit(f"Only {kept} photos of {label_folder.name}: collect more first")

        clean_zip = Path(work) / "clean.zip"
        with zipfile.ZipFile(clean_zip, "w") as archive:
            for path in sorted(clean.rglob("*.jpg")):
                archive.write(path, path.relative_to(clean))
        bucket.blob("clean.zip").upload_from_filename(clean_zip)
        print(f"Saved gs://{args.bucket}/clean.zip")


if __name__ == "__main__":
    main()
