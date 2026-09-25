"""Load cached McLaren eval artifacts for laptop demo mode (no GPU inference)."""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
DEMO_DIR = APP_DIR / "demo_data"
EVAL_DIR = DEMO_DIR / "evaluation"
CASES_CSV = DEMO_DIR / "cases.csv"
KNOBS_PATH = APP_DIR / "knobs.json"

KNOB_KEYS = [
    "airbag_E22",
    "airbag_z_up_mm",
    "brace_P16",
    "bracket_cutt",
    "cavity_foam_gl",
    "door_inner_mm",
    "door_outer_mm",
    "rail_foam",
    "seat_inb_foam",
    "ttf_ms",
]

PROBE_CHANNELS = [
    "head_acceleration_x",
    "head_acceleration_y",
    "head_acceleration_z",
    "lower_rib_defl",
    "lower_rib_viscous_criterion",
    "middle_rib_defl",
    "middle_rib_viscous_criterion",
    "neck_upper_force_x",
    "neck_upper_force_y",
    "neck_upper_force_z",
    "neck_upper_moment_x",
    "neck_upper_moment_y",
    "neck_upper_moment_z",
    "pelvis_acceleration_x",
    "pelvis_acceleration_y",
    "pelvis_acceleration_z",
    "pubic_force_y",
    "shoulder_left_force_x",
    "shoulder_left_force_y",
    "shoulder_left_force_z",
    "t12_acceleration_x",
    "t12_acceleration_y",
    "t12_acceleration_z",
    "t1_acceleration_x",
    "t1_acceleration_y",
    "t1_acceleration_z",
    "upper_rib_defl",
    "upper_rib_viscous_criterion",
]


@lru_cache(maxsize=1)
def load_knobs_config() -> dict[str, Any]:
    return json.loads(KNOBS_PATH.read_text())


@lru_cache(maxsize=1)
def load_cases() -> list[dict[str, Any]]:
    if not CASES_CSV.exists():
        return []
    rows: list[dict[str, Any]] = []
    with CASES_CSV.open() as f:
        for row in csv.DictReader(f):
            case_path = row["case_path"]
            case_id = Path(case_path).name  # e.g. case0_chFXfb
            knobs = {k: float(row[k]) for k in KNOB_KEYS}
            rows.append(
                {
                    "case_id": case_id,
                    "case_path": case_path,
                    "knobs": knobs,
                    "global_json": EVAL_DIR / f"prediction_{case_id}_global_values.json",
                    "vtp": EVAL_DIR / f"prediction_{case_id}.vtp",
                }
            )
    return rows


def demo_data_ready() -> tuple[bool, str]:
    cases = load_cases()
    if not cases:
        return False, f"Missing {CASES_CSV} — pull demo_data from the workstation."
    extra_json = list(EVAL_DIR.glob("prediction_*_global_values.json"))
    n_vtp = len(list(EVAL_DIR.glob("prediction_*.vtp")))
    if not extra_json:
        return False, f"No *_global_values.json under {EVAL_DIR}"
    return True, f"{len(cases)} DOE cases · {len(extra_json)} probe JSONs · {n_vtp} local meshes"


def knob_distance(a: dict[str, float], b: dict[str, float]) -> float:
    """Normalized L2 across knobs (binary + continuous mixed)."""
    total = 0.0
    cfg = load_knobs_config()
    for k in KNOB_KEYS:
        av = float(a[k])
        bv = float(b[k])
        meta = cfg[k]
        if meta["kind"] == "binary":
            scale = 1.0
        else:
            opts = meta.get("options") or [0.0, 1.0]
            span = max(opts) - min(opts)
            scale = span if span > 0 else 1.0
        total += ((av - bv) / scale) ** 2
    return total**0.5


def nearest_case(knobs: dict[str, float]) -> dict[str, Any] | None:
    cases = load_cases()
    if not cases:
        return None
    ranked = sorted(cases, key=lambda c: knob_distance(knobs, c["knobs"]))
    best = dict(ranked[0])
    best["distance"] = knob_distance(knobs, best["knobs"])
    best["exact"] = best["distance"] < 1e-9
    return best


def list_all_eval_cases() -> list[str]:
    """Case ids that have a global_values JSON (train + holdouts)."""
    ids: list[str] = []
    for p in sorted(EVAL_DIR.glob("prediction_*_global_values.json")):
        # prediction_case3_dWNQX_global_values.json
        stem = p.name.removeprefix("prediction_").removesuffix("_global_values.json")
        ids.append(stem)
    return ids


def load_global_values(case_id: str) -> dict[str, Any]:
    path = EVAL_DIR / f"prediction_{case_id}_global_values.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text())


def probe_series(global_values: dict[str, Any], channel: str) -> tuple[list[float], list[float], list[float] | None]:
    """Return (time, pred, actual_or_None) for one probe channel."""
    time = list(global_values.get("time_step") or [])
    pred = list(global_values.get(f"{channel}_pred") or global_values.get(channel) or [])
    actual_key = channel
    actual = global_values.get(actual_key)
    # When GT exists it is the bare channel name; pred is *_pred
    if f"{channel}_pred" in global_values and actual is not None:
        actual_list = list(actual)
    else:
        actual_list = None
    return time, pred, actual_list


def vtp_path_for(case_id: str) -> Path | None:
    p = EVAL_DIR / f"prediction_{case_id}.vtp"
    return p if p.exists() else None
