"""Data collector: search the web for photos of each cheese, and save them to the bucket as raw.zip.

    python cli.py --bucket <bucket> --labels brie gouda gruyere parmigiano --per-label 50

raw.zip has one folder per cheese (brie/, gouda/, ...): the folder names become the model's labels.
The ML pipeline runs this as its first step; the data processor picks raw.zip up from there.
"""

import argparse
import tempfile
import zipfile
from pathlib import Path

from google.cloud import storage

import downloader


def main() -> None:
    parser = argparse.ArgumentParser(description="Data collector")
    parser.add_argument("--bucket", required=True, help="the bucket to save raw.zip in")
    parser.add_argument("--labels", nargs="+", default=["brie", "gouda", "gruyere", "parmigiano"])
    parser.add_argument("--per-label", type=int, default=50, help="photos to download for each cheese")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as work:
        raw = Path(work) / "raw"
        for label in args.labels:
            count = downloader.download_images(f"{label} cheese", raw / label, args.per_label)
            print(f"{label}: {count} photos")
            if count == 0:
                raise SystemExit(f"No photos found for {label}: has Bing changed its page?")

        raw_zip = Path(work) / "raw.zip"
        with zipfile.ZipFile(raw_zip, "w") as archive:
            for path in sorted(raw.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(raw))
        storage.Client().bucket(args.bucket).blob("raw.zip").upload_from_filename(raw_zip)
        print(f"Saved gs://{args.bucket}/raw.zip")


if __name__ == "__main__":
    main()
