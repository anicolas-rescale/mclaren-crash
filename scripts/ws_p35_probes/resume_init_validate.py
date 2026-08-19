#!/usr/bin/env python3
"""Resume after collect: files are on disk; skip re-download.

collect_cases treated ``case_data.yml.lock`` as matching the yml regex and
failed verification on 18 empty lock files. Real VTPs/yml/stl/probes are complete.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DATASET_NAME, NUM_WORKERS_INIT


def main() -> int:
    from rescale_ai.interactive import DatasetBuilder

    builder = DatasetBuilder()
    link = Path(builder.hps.link_path)
    scratch = link / "scratch" / DATASET_NAME
    cases = scratch / "cases"
    print(f"HPS={link} scratch={scratch}", flush=True)
    if not cases.is_dir():
        print("missing cases dir", file=sys.stderr)
        return 1

    removed = []
    for p in cases.rglob("*"):
        if p.is_file() and (p.name.endswith(".lock") or ".tmpdecrypt" in p.name):
            p.unlink()
            removed.append(str(p))
    print(f"removed junk files={len(removed)}", flush=True)

    n = len([p for p in cases.iterdir() if p.is_dir() and p.name.startswith("case")])
    print(f"n_cases={n}", flush=True)
    if n != 18:
        print("expected 18 cases", file=sys.stderr)
        return 2

    builder.initialize_dataset(
        name=DATASET_NAME,
        dataset_type="fea-deform",
        surface_file_name="case_data.vtp",
        num_workers=NUM_WORKERS_INIT,
    )
    final = builder.validate_dataset(
        DATASET_NAME,
        num_workers=NUM_WORKERS_INIT,
        upload_to_platform=True,
        description=(
            "McLaren P35 ES2 side-pole, 18 OFAT extracts (crashPostProcOK), "
            "displacement nodal + occupant probe global time series"
        ),
    )
    print(f"dataset={final}", flush=True)
    summary = {"dataset_name": DATASET_NAME, "dataset_path": str(final), "n_cases": n}
    Path(final).joinpath("collect_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print("DONE initialize+validate", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
