#!/usr/bin/env python3
"""Verify case_data.yml timeseries can stack as [T, G] (Phase 1 exit check).

Does not require Transient / GeoTransolver code — only YAML + numpy.

Usage::

    python scripts/verify_probe_globals.py scratch/HFuKPb
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
import yaml

_TIME_RE = re.compile(r"^displacement_t(\d+(?:\.\d+)?)$")


def displacement_T_from_vtp(vtp: Path) -> Optional[int]:
    try:
        import pyvista as pv
    except ImportError:
        return None
    mesh = pv.read(str(vtp))
    times = []
    for name in mesh.array_names:
        m = _TIME_RE.match(name)
        if m:
            times.append(float(m.group(1)))
    return len(times) if times else None


def load_outvar_matrix(yml_path: Path) -> tuple[np.ndarray, List[str], List[float]]:
    data = yaml.safe_load(yml_path.read_text(encoding="utf-8")) or {}
    ts = data.get("timeseries")
    if not isinstance(ts, dict):
        raise ValueError(f"No timeseries dict in {yml_path}")

    times = ts.get("times")
    keys = [k for k in ts.keys() if k != "times"]
    if not keys:
        raise ValueError("timeseries has no channel keys")

    cols = []
    lengths = []
    for k in keys:
        arr = np.asarray(ts[k], dtype=np.float64)
        if arr.ndim != 1:
            raise ValueError(f"{k} must be a 1-D list, got shape {arr.shape}")
        cols.append(arr)
        lengths.append(arr.shape[0])

    if len(set(lengths)) != 1:
        raise ValueError(f"Mismatched channel lengths: {dict(zip(keys, lengths))}")

    T = lengths[0]
    matrix = np.column_stack(cols)  # [T, G]
    time_list = [float(t) for t in times] if isinstance(times, list) else []
    if time_list and len(time_list) != T:
        raise ValueError(
            f"times length {len(time_list)} != channel T={T}"
        )
    return matrix, keys, time_list


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--yml", default="case_data.yml")
    args = parser.parse_args(argv)

    case_dir = args.case_dir.resolve()
    yml_path = case_dir / args.yml
    if not yml_path.is_file():
        print(f"Missing {yml_path}", file=sys.stderr)
        return 1

    matrix, keys, times = load_outvar_matrix(yml_path)
    T, G = matrix.shape
    print(f"OK loaded outvar_ts shape [T, G] = [{T}, {G}] from {yml_path}")
    print(f"  channels ({G}): {', '.join(keys)}")
    if times:
        print(f"  times[0]={times[0]} times[-1]={times[-1]}")

    finite = np.isfinite(matrix).all()
    print(f"  all_finite={finite} abs_max={float(np.max(np.abs(matrix))):.6g}")
    if not finite:
        return 1

    vtp = case_dir / "case_data.vtp"
    if not vtp.is_file():
        vtp = case_dir / "rescale-ai.vtp"
    if vtp.is_file():
        disp_T = displacement_T_from_vtp(vtp)
        if disp_T is not None:
            match = disp_T == T
            print(f"  displacement_t* count={disp_T} match_T={match}")
            if not match:
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
