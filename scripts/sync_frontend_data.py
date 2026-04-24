#!/usr/bin/env python3
"""
Copy the static frontend plus the CSV/GeoJSON the app loads into a
self-contained tree (outputs/frontend-snapshot/ by default).

Paths in frontend/js/config.js are resolved from .../frontend/index.html as
../data/..., ../baselines/outputs/..., ../outputs/interpretability/...
so the snapshot keeps that same layout under the output directory:

  frontend-snapshot/frontend/          — HTML, CSS, JS
  frontend-snapshot/data/processed/   — grid GeoJSON
  frontend-snapshot/baselines/outputs/ — model_results.csv
  frontend-snapshot/outputs/interpretability/ — explanations (+ optional files)

Test locally (from repo root, after this script):

  cd outputs/frontend-snapshot && python3 -m http.server 8000

Then open: http://localhost:8000/frontend/index.html

(Running the data/model pipeline first is separate; see README. This script
only syncs current repo files into the snapshot.)
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def copy_file(src: Path, dst: Path) -> bool:
    if not src.is_file():
        print(f"WARNING: missing file, skipped: {src}", file=sys.stderr)
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "outputs" / "frontend-snapshot",
        help="Output directory (default: outputs/frontend-snapshot under repo root)",
    )
    p.add_argument(
        "--zip",
        action="store_true",
        help="Create outputs/frontend-snapshot.zip next to the snapshot directory",
    )
    args = p.parse_args()
    out: Path = args.out.resolve()

    if out.is_file():
        p.error(f"--out must be a directory, got file: {out}")

    out.mkdir(parents=True, exist_ok=True)

    src_front = REPO_ROOT / "frontend"
    if not src_front.is_dir():
        p.error(f"Missing frontend: {src_front}")
    dst_front = out / "frontend"
    if dst_front.exists():
        shutil.rmtree(dst_front)
    shutil.copytree(src_front, dst_front, symlinks=False)

    n_ok = 0
    for rel in (
        "data/processed/grid_cells.geojson",
        "baselines/outputs/model_results.csv",
    ):
        if copy_file(REPO_ROOT / rel, out / rel):
            n_ok += 1

    inter = REPO_ROOT / "outputs" / "interpretability"
    if inter.is_dir():
        inter_dst = out / "outputs" / "interpretability"
        if inter_dst.exists():
            shutil.rmtree(inter_dst)
        shutil.copytree(inter, inter_dst, symlinks=False)
    else:
        print(
            f"WARNING: {inter} not found; app will load empty explanations",
            file=sys.stderr,
        )

    print(f"Wrote: {out}")
    print("Serve: cd", out, "&& python3 -m http.server 8000")
    print("  URL:  http://localhost:8000/frontend/index.html")

    if args.zip:
        out_parent = out.parent
        base_name = out.name
        zip_stem = out_parent / base_name
        if zip_stem.suffix:
            p.error("snapshot folder name should not be a file-like path for --zip")
        archive = shutil.make_archive(
            str(zip_stem),
            "zip",
            root_dir=str(out_parent),
            base_dir=base_name,
        )
        print(f"Zip:  {archive}")

    return 0 if n_ok == 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
