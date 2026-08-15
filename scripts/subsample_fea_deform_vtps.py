#!/usr/bin/env python3
"""Subsample fea-deform VTPs for GeoTransolver smoke (does not change YAML probes).

Transient GeoTransolver loads the full N into GPU. McLaren cases are ~1.28M points
x 41 frames; an A10 24 GB box cannot train that. This keeps a random vertex subset
plus one dummy triangle so the VTP reader edge assert still passes (GeoT ignores
connectivity). Probe timeseries in case_data.yml are copied unchanged.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import pyvista as pv


def subsample_vtp(src: Path, dst: Path, n_points: int, seed: int) -> tuple[int, int]:
    mesh = pv.read(str(src))
    n_in = int(mesh.n_points)
    n_keep = min(int(n_points), n_in)
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(n_in, size=n_keep, replace=False))
    out = pv.PolyData(mesh.points[idx])
    for name in mesh.point_data.keys():
        out.point_data[name] = np.asarray(mesh.point_data[name])[idx]
    if n_keep >= 3:
        out.faces = np.hstack([[3, 0, 1, 2]])
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(str(dst))
    return n_in, n_keep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path, help="Dataset cases/ directory")
    ap.add_argument("--dst", required=True, type=Path, help="Output cases/ directory")
    ap.add_argument("--n-points", type=int, default=8192)
    ap.add_argument("--n-cases", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    cases = sorted(
        p
        for p in args.src.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "case_data.vtp").exists()
    )
    if not cases:
        raise SystemExit(f"No case_data.vtp cases under {args.src}")
    chosen = cases[: args.n_cases]
    args.dst.mkdir(parents=True, exist_ok=True)
    for i, case in enumerate(chosen):
        dest_case = args.dst / case.name
        dest_case.mkdir(parents=True, exist_ok=True)
        n_in, n_keep = subsample_vtp(
            case / "case_data.vtp",
            dest_case / "case_data.vtp",
            args.n_points,
            args.seed + i,
        )
        yml = case / "case_data.yml"
        if yml.exists():
            shutil.copy2(yml, dest_case / "case_data.yml")
        print(f"{case.name}: {n_in} -> {n_keep} points", flush=True)
    print(f"Wrote {len(chosen)} cases to {args.dst}")


if __name__ == "__main__":
    main()
