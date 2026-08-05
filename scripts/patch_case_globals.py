"""Patch a collected McLaren case with DOE globals, then re-initialize.

Run on the AI Physics workstation / HPS after collect_cases, if globals are
missing (Auto Download / Program / … instead of door_inner_mm, ttf_ms, …).

Usage (from notebook or shell, cwd anywhere):

    from pathlib import Path
    import sys
    sys.path.insert(0, "/path/to/mclaren-crash-pole/scripts")  # optional
    # or paste this cell and set CASE_DIR

Why this is needed
------------------
Utilities clones do not inherit PSA catalog custom fields. Without
``mclaren_catalog.json`` on the job, metadata leaves ``inputs: null``, so
initialize_dataset only sees job plumbing fields as globals.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# --- edit if your collect layout differs ---
DATASET_NAME = "mclaren-crash-smoke"
CASE_GLOB = "**/case0_aMYNZb"  # folder name from collect

# Knobs for HFuKPb / aMYNZb Comfort Inb Foam clone (from examples/mclaren_catalog.json)
GLOBALS = {
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


def find_case_dir(root: Path) -> Path:
    matches = list(root.glob(f"**/{CASE_GLOB.strip('*/')}"))
    if not matches:
        # broader: any case_* with case_data.vtp
        matches = [p.parent for p in root.rglob("case_data.vtp")]
    if not matches:
        raise FileNotFoundError(f"No case_data.vtp under {root}")
    # prefer path containing aMYNZb
    for m in matches:
        if "aMYNZb" in str(m):
            return m if m.is_dir() else m.parent
    p = matches[0]
    return p if p.is_dir() else p.parent


def main() -> None:
    # DatasetBuilder scratch is typically under cwd or ~/…
    candidates = [
        Path.cwd() / "datasets" / DATASET_NAME,
        Path.cwd() / DATASET_NAME,
        Path.cwd() / "scratch" / DATASET_NAME,
        Path.home() / "datasets" / DATASET_NAME,
    ]
    root = next((c for c in candidates if c.is_dir()), None)
    if root is None:
        # last resort: search for case_data.vtp near cwd
        hits = list(Path.cwd().rglob("case_data.vtp"))
        if not hits:
            raise FileNotFoundError(
                f"Could not find dataset {DATASET_NAME!r}; set root manually"
            )
        case_dir = hits[0].parent
    else:
        case_dir = find_case_dir(root)

    yml = case_dir / "case_data.yml"
    yml.write_text(yaml.safe_dump(GLOBALS, sort_keys=False), encoding="utf-8")
    print(f"Wrote {yml}")
    print("Next: re-run initialize_dataset + validate_dataset (see handoff).")


if __name__ == "__main__":
    main()
