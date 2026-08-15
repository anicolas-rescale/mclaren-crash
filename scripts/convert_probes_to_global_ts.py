#!/usr/bin/env python3
"""Convert McLaren sparse probe channels → case_data.yml timeseries globals.

Writes FEA-compatible::

    timeseries:
      times: [...]
      head_acceleration_x: [...]
      ...

Sources (auto):
  1. PSA channel CSVs in the case dir (preferred; same resampling as AI extractor)
  2. Else VTP probe nodes via NODE_ID / PROBE_CODE + probe_map.json

Usage::

    python scripts/convert_probes_to_global_ts.py scratch/HFuKPb
    python scripts/convert_probes_to_global_ts.py /path/to/case --source vtp
    python scripts/convert_probes_to_global_ts.py /path/to/dataset --recursive

See docs/probe-global-schema.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import yaml

_TIME_RE = re.compile(r"^(?P<base>.+)_t(?P<time>\d+(?:\.\d+)?)$")

# Repo-bundled probe map fallback
_REPO_PROBE_MAP = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "probe_map.json"
)
_REPO_PROBE_INDEX = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "probe_point_index.json"
)
_EXTRACTOR_PROBE_MAP = (
    Path(__file__).resolve().parents[2]
    / "automation-ai-extractor"
    / "src"
    / "core"
    / "solvers"
    / "ls_dyna"
    / "probe_map.json"
)


def _find_file(root: Path, name: str) -> Optional[Path]:
    direct = root / name
    if direct.is_file():
        return direct
    matches = list(root.rglob(name))
    return matches[0] if matches else None


def load_probe_map(case_dir: Path) -> Dict[str, dict]:
    for candidate in (
        case_dir / "probe_map.json",
        Path(__file__).resolve().parent / "probe_map.json",
        _REPO_PROBE_MAP if _REPO_PROBE_MAP.is_file() else None,
        _EXTRACTOR_PROBE_MAP if _EXTRACTOR_PROBE_MAP.is_file() else None,
    ):
        if candidate is None:
            continue
        if not Path(candidate).is_file():
            continue
        data = json.loads(Path(candidate).read_text(encoding="utf-8"))
        probes = data.get("probes", data)
        if isinstance(probes, dict) and probes:
            return probes
    raise FileNotFoundError(
        f"No probe_map.json found for {case_dir} "
        f"(checked case dir, script dir, {_REPO_PROBE_MAP}, {_EXTRACTOR_PROBE_MAP})"
    )


def read_psa_csv(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    times: List[float] = []
    values: List[float] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            try:
                times.append(float(row[0]))
                values.append(float(row[1]))
            except ValueError:
                continue
    return np.asarray(times, dtype=np.float64), np.asarray(values, dtype=np.float64)


def resample_series(
    src_t: np.ndarray, src_y: np.ndarray, dst_t: np.ndarray
) -> np.ndarray:
    if src_t.size == 0 or dst_t.size == 0:
        return np.zeros(len(dst_t), dtype=np.float64)
    if src_t.size == 1:
        return np.full(len(dst_t), float(src_y[0]), dtype=np.float64)
    return np.interp(dst_t, src_t, src_y).astype(np.float64)


def displacement_times_from_vtp(vtp_path: Path) -> np.ndarray:
    import pyvista as pv

    mesh = pv.read(str(vtp_path))
    times: List[Tuple[float, str]] = []
    for name in mesh.array_names:
        m = _TIME_RE.match(name)
        if not m or m.group("base") != "displacement":
            continue
        times.append((float(m.group("time")), name))
    if not times:
        raise ValueError(f"No displacement_t* arrays in {vtp_path}")
    times.sort(key=lambda x: x[0])
    # Stable unique by token string order already sorted numerically
    return np.asarray([t for t, _ in times], dtype=np.float64), mesh


def _xyz_from_prefix(
    root: Path, prefix: str, units: str, times: np.ndarray
) -> Optional[Dict[str, np.ndarray]]:
    out: Dict[str, np.ndarray] = {}
    for axis in ("x", "y", "z"):
        path = _find_file(root, f"{prefix}_{axis}__{units}.csv")
        if path is None:
            continue
        src_t, src_y = read_psa_csv(path)
        out[axis] = resample_series(src_t, src_y, times)
    return out or None


def timeseries_from_psa(
    case_dir: Path, probes: Dict[str, dict], times: np.ndarray
) -> Dict[str, List[float]]:
    ts: Dict[str, List[float]] = {"times": [float(t) for t in times]}
    found_any = False

    for name, spec in probes.items():
        role = spec.get("role")
        if role == "acceleration":
            prefix = spec.get("psa_csv_prefix")
            if not prefix:
                continue
            comps = _xyz_from_prefix(case_dir, prefix, "g", times)
            if comps is None:
                continue
            found_any = True
            for axis, arr in comps.items():
                ts[f"{name}_acceleration_{axis}"] = [float(v) for v in arr]
        elif role == "rib_defl":
            csv_name = spec.get("psa_csv")
            if not csv_name:
                continue
            path = _find_file(case_dir, csv_name)
            if path is None:
                continue
            src_t, src_y = read_psa_csv(path)
            found_any = True
            ts[f"{name}_defl"] = [
                float(v) for v in resample_series(src_t, src_y, times)
            ]
        elif role == "force_moment":
            if spec.get("psa_force_prefix"):
                comps = _xyz_from_prefix(
                    case_dir, spec["psa_force_prefix"], "kN", times
                )
                if comps is not None:
                    found_any = True
                    for axis, arr in comps.items():
                        ts[f"{name}_force_{axis}"] = [float(v) for v in arr]
            if spec.get("psa_moment_prefix"):
                comps = _xyz_from_prefix(
                    case_dir, spec["psa_moment_prefix"], "Nm", times
                )
                if comps is not None:
                    found_any = True
                    for axis, arr in comps.items():
                        ts[f"{name}_moment_{axis}"] = [float(v) for v in arr]

    if not found_any:
        raise FileNotFoundError(
            f"No PSA channel CSVs found under {case_dir} for probe_map roles"
        )
    return ts


def load_probe_point_index(path: Optional[Path] = None) -> Dict[str, int]:
    """Load frozen probe name → point_index map (for VTPs without bookkeeping)."""
    candidates = [
        path,
        Path(__file__).resolve().parent / "probe_point_index.json",
        _REPO_PROBE_INDEX if _REPO_PROBE_INDEX.is_file() else None,
    ]
    for candidate in candidates:
        if candidate is None or not Path(candidate).is_file():
            continue
        data = json.loads(Path(candidate).read_text(encoding="utf-8"))
        probes = data.get("probes", data)
        out: Dict[str, int] = {}
        for name, raw in probes.items():
            if isinstance(raw, dict) and "point_index" in raw:
                out[name] = int(raw["point_index"])
            elif isinstance(raw, int):
                out[name] = int(raw)
        if out:
            return out
    return {}


def _probe_point_index(
    mesh,
    probes: Dict[str, dict],
    *,
    probe_index_path: Optional[Path] = None,
) -> Dict[str, int]:
    """Map probe name → point index using PROBE_CODE, NODE_ID, frozen index, or XYZ match."""
    names_sorted = sorted(probes)
    if "PROBE_CODE" in mesh.array_names:
        code = np.asarray(mesh["PROBE_CODE"])
        index: Dict[str, int] = {}
        for i, name in enumerate(names_sorted, start=1):
            hits = np.where(code == i)[0]
            if len(hits) == 0:
                continue
            index[name] = int(hits[0])
        if index:
            return index

    if "NODE_ID" in mesh.array_names:
        nid = np.asarray(mesh["NODE_ID"]).astype(np.int64)
        id_to_idx = {int(n): i for i, n in enumerate(nid)}
        index = {}
        for name, spec in probes.items():
            for key in ("node_id", "elout_beam_id", "deforc_id"):
                raw = spec.get(key)
                if raw is None:
                    continue
                if int(raw) in id_to_idx:
                    index[name] = id_to_idx[int(raw)]
                    break
        if index:
            return index

    frozen_meta = _load_probe_index_meta(probe_index_path)
    frozen_idx = {
        k: int(v["point_index"])
        for k, v in frozen_meta.items()
        if isinstance(v, dict) and "point_index" in v and k in probes
    }
    frozen_xyz = {
        k: np.asarray(v["xyz"], dtype=np.float64)
        for k, v in frozen_meta.items()
        if isinstance(v, dict) and "xyz" in v and k in probes
    }

    n = int(mesh.n_points)
    # Fast path: same mesh topology as the reference extract.
    if frozen_idx and all(0 <= i < n for i in frozen_idx.values()) and n == max(
        (meta.get("n_points") or 0) for meta in [frozen_meta.get("_meta", {})] or [{}]
    ):
        # n_points stored separately — handled below
        pass

    ref_n = None
    raw_file = _resolve_probe_index_file(probe_index_path)
    if raw_file is not None:
        blob = json.loads(raw_file.read_text(encoding="utf-8"))
        ref_n = blob.get("n_points")

    if frozen_idx and ref_n is not None and n == int(ref_n):
        if all(0 <= i < n for i in frozen_idx.values()):
            return frozen_idx

    # Different mesh size: match reference XYZ to nonzero probe candidates.
    if frozen_xyz:
        candidates = _probe_candidate_indices(mesh)
        if candidates.size == 0:
            raise ValueError("No nonzero probe candidates found on VTP")
        pts = np.asarray(mesh.points, dtype=np.float64)
        cand_pts = pts[candidates]
        used: set[int] = set()
        index = {}
        # Match roles with fewer candidates first to reduce collisions.
        role_order = ("rib_defl", "acceleration", "force_moment")
        ordered_names = []
        for role in role_order:
            ordered_names.extend(
                [n for n, s in probes.items() if s.get("role") == role and n in frozen_xyz]
            )
        for name in ordered_names:
            if name not in frozen_xyz:
                continue
            target = frozen_xyz[name]
            dists = np.linalg.norm(cand_pts - target[None, :], axis=1)
            order = np.argsort(dists)
            chosen = None
            for j in order:
                idx = int(candidates[j])
                if idx in used:
                    continue
                chosen = idx
                break
            if chosen is None:
                continue
            used.add(chosen)
            index[name] = chosen
        if index:
            return index

    if frozen_idx:
        usable = {k: v for k, v in frozen_idx.items() if 0 <= v < n}
        if usable:
            return usable

    raise ValueError(
        "VTP has neither PROBE_CODE nor NODE_ID, and probe XYZ/index matching failed. "
        "Provide PSA CSVs, re-extract with EMIT_PROBE_BOOKKEEPING=1, or pass --probe-index."
    )


def _resolve_probe_index_file(path: Optional[Path] = None) -> Optional[Path]:
    for candidate in (
        path,
        Path(__file__).resolve().parent / "probe_point_index.json",
        _REPO_PROBE_INDEX if _REPO_PROBE_INDEX.is_file() else None,
    ):
        if candidate is not None and Path(candidate).is_file():
            return Path(candidate)
    return None


def _load_probe_index_meta(path: Optional[Path] = None) -> Dict[str, dict]:
    raw_file = _resolve_probe_index_file(path)
    if raw_file is None:
        return {}
    data = json.loads(raw_file.read_text(encoding="utf-8"))
    probes = data.get("probes", {})
    if not isinstance(probes, dict):
        return {}
    # stash n_points for callers
    out = dict(probes)
    out["_meta"] = {"n_points": data.get("n_points")}
    return out


def _probe_candidate_indices(mesh) -> np.ndarray:
    """Union of point indices with nonzero acc/force/moment/rib at a mid frame."""
    def mid_keys(prefix: str) -> List[str]:
        keys = sorted(
            [k for k in mesh.array_names if k.startswith(prefix + "_t")],
            key=lambda s: float(_TIME_RE.match(s).group("time"))  # type: ignore[union-attr]
            if _TIME_RE.match(s)
            else s,
        )
        return keys

    hits: set[int] = set()
    for prefix, vector in (
        ("acceleration", True),
        ("force", True),
        ("moment", True),
        ("rib_defl", False),
    ):
        keys = mid_keys(prefix)
        if not keys:
            continue
        arr = np.asarray(mesh[keys[len(keys) // 2]])
        if vector:
            if arr.ndim == 1:
                continue
            nnz = np.where(np.linalg.norm(arr, axis=1) > 0)[0]
        else:
            nnz = np.where(np.abs(arr) > 0)[0]
        hits.update(int(i) for i in nnz)
    return np.asarray(sorted(hits), dtype=np.int64)


def timeseries_from_vtp(
    mesh,
    probes: Dict[str, dict],
    times: np.ndarray,
    *,
    probe_index_path: Optional[Path] = None,
) -> Dict[str, List[float]]:
    index = _probe_point_index(mesh, probes, probe_index_path=probe_index_path)
    # Collect per-base timed arrays
    by_base: Dict[str, List[Tuple[float, str]]] = {}
    for name in mesh.array_names:
        m = _TIME_RE.match(name)
        if not m:
            continue
        base = m.group("base")
        if base not in ("acceleration", "force", "moment", "rib_defl"):
            continue
        by_base.setdefault(base, []).append((float(m.group("time")), name))
    for base in by_base:
        by_base[base].sort(key=lambda x: x[0])

    ts: Dict[str, List[float]] = {"times": [float(t) for t in times]}
    T = len(times)

    def series_at(base: str, idx: int) -> np.ndarray:
        frames = by_base.get(base, [])
        if not frames:
            return np.zeros((T, 3) if base != "rib_defl" else (T,), dtype=np.float64)
        # Align by nearest time token order (expect exact match to displacement times)
        if len(frames) != T:
            raise ValueError(
                f"{base}_t* count {len(frames)} != displacement T={T}"
            )
        rows = []
        for _, arr_name in frames:
            rows.append(np.asarray(mesh[arr_name])[idx])
        return np.asarray(rows, dtype=np.float64)

    for name, spec in probes.items():
        if name not in index:
            continue
        idx = index[name]
        role = spec.get("role")
        if role == "acceleration":
            arr = series_at("acceleration", idx)
            for a, axis in enumerate("xyz"):
                ts[f"{name}_acceleration_{axis}"] = [float(v) for v in arr[:, a]]
        elif role == "rib_defl":
            arr = series_at("rib_defl", idx)
            if arr.ndim > 1:
                arr = arr.reshape(T, -1)[:, 0]
            ts[f"{name}_defl"] = [float(v) for v in arr]
        elif role == "force_moment":
            force = series_at("force", idx)
            moment = series_at("moment", idx)
            # Always emit xyz once the probe point is identified so G is
            # stable across cases (zeros allowed).
            for a, axis in enumerate("xyz"):
                ts[f"{name}_force_{axis}"] = [float(v) for v in force[:, a]]
            # Moment only when probe_map declares a moment prefix (stable G).
            if spec.get("psa_moment_prefix"):
                for a, axis in enumerate("xyz"):
                    ts[f"{name}_moment_{axis}"] = [float(v) for v in moment[:, a]]

    channel_keys = [k for k in ts if k != "times"]
    if not channel_keys:
        raise ValueError("VTP extraction produced no probe channels")
    return ts


def default_knobs() -> Dict[str, Any]:
    """Fallback knobs if case_data.yml is missing (Comfort-like example)."""
    return {
        "doe_matrix": "McLaren P35 ES-2 side-pole",
        "solver": "LS-DYNA",
        "door_inner_mm": 1.2,
        "door_outer_mm": 1.2,
        "ttf_ms": 12.0,
        "airbag_E22": 0.0,
        "airbag_z_up_mm": 0.0,
        "bracket_cutt": 0.0,
        "trim_woodfibre": 0.0,
        "brace_P16": 0.0,
        "cavity_foam_gl": 0.0,
        "rail_foam": 0.0,
        "seat_inb_foam": 1.0,
        "seat_clubsport": 0.0,
    }


def merge_timeseries_into_yml(
    case_dir: Path, timeseries: Dict[str, List[float]], yml_path: Path
) -> Path:
    if yml_path.is_file():
        data = yaml.safe_load(yml_path.read_text(encoding="utf-8")) or {}
    else:
        data = default_knobs()
    data["timeseries"] = timeseries
    yml_path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=None),
        encoding="utf-8",
    )
    return yml_path


def convert_case(
    case_dir: Path,
    *,
    source: str = "auto",
    yml_name: str = "case_data.yml",
    vtp_name: str = "case_data.vtp",
    probe_index_path: Optional[Path] = None,
) -> Dict[str, Any]:
    case_dir = case_dir.resolve()
    vtp_path = case_dir / vtp_name
    if not vtp_path.is_file():
        # tolerate rescale-ai.vtp only
        alt = case_dir / "rescale-ai.vtp"
        if alt.is_file():
            vtp_path = alt
        else:
            raise FileNotFoundError(f"Missing {vtp_name} in {case_dir}")

    probes = load_probe_map(case_dir)
    times, mesh = displacement_times_from_vtp(vtp_path)

    use = source
    if use == "auto":
        # Prefer PSA if any acceleration/force CSV exists
        sample = _find_file(case_dir, "head_acceleration_x__g.csv")
        use = "csv" if sample is not None else "vtp"

    if use == "csv":
        timeseries = timeseries_from_psa(case_dir, probes, times)
    elif use == "vtp":
        timeseries = timeseries_from_vtp(
            mesh, probes, times, probe_index_path=probe_index_path
        )
    else:
        raise ValueError(f"Unknown source={source!r}")

    yml_path = case_dir / yml_name
    merge_timeseries_into_yml(case_dir, timeseries, yml_path)

    channels = [k for k in timeseries if k != "times"]
    return {
        "case_dir": str(case_dir),
        "source": use,
        "T": int(len(times)),
        "G": len(channels),
        "channels": channels,
        "yml": str(yml_path),
    }


def iter_case_dirs(root: Path) -> Iterable[Path]:
    if (root / "case_data.vtp").is_file() or (root / "rescale-ai.vtp").is_file():
        yield root
        return
    seen = set()
    for vtp in root.rglob("case_data.vtp"):
        d = vtp.parent.resolve()
        if d not in seen:
            seen.add(d)
            yield d


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        type=Path,
        help="Case directory (with VTP) or dataset root with --recursive",
    )
    parser.add_argument(
        "--source",
        choices=("auto", "csv", "vtp"),
        default="auto",
        help="Probe source (default: auto = CSV if present else VTP)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Convert every case_data.vtp under path",
    )
    parser.add_argument(
        "--probe-index",
        type=Path,
        default=None,
        help="probe_point_index.json for VTPs without NODE_ID/PROBE_CODE",
    )
    args = parser.parse_args(argv)

    roots = list(iter_case_dirs(args.path)) if args.recursive else [args.path]
    if not roots:
        print(f"No cases found under {args.path}", file=sys.stderr)
        return 1

    for case_dir in roots:
        summary = convert_case(
            case_dir,
            source=args.source,
            probe_index_path=args.probe_index,
        )
        print(
            f"OK {summary['case_dir']}: source={summary['source']} "
            f"T={summary['T']} G={summary['G']} → {summary['yml']}"
        )
        print("  channels:", ", ".join(summary["channels"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
