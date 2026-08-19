#!/usr/bin/env python3
"""After validate: decimate to 20k, copy YAML probes, write train/test CSVs, fill Hydra paths.

Holdouts: KwXUX (door_inner 1.3) and dWNQX (cavity_foam 60) — same physics split as
case9_bcLVXb / case3_WvXCHc last time.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    DATASET_NAME,
    DECIMATE_TARGET_POINTS,
    GLOBAL_OUTPUT_BASES,
    HOLDOUT_JOB_IDS,
    HOLDOUT_REASONS,
    KNOB_INPUTS,
    NUM_TIME_STEPS,
)


def _hps_datasets() -> Path:
    # HPS link_path on this box
    return Path("/enc/udeprod.fNLMWb/work/datasets")


def _case_job_id(case_dir: Path) -> str | None:
    # collect names: case0_wJNQX
    name = case_dir.name
    if "_" in name:
        return name.split("_", 1)[1]
    return None


def copy_yaml_into_preprocessed(cases_dir: Path, preproc_dir: Path) -> int:
    n = 0
    for src in cases_dir.iterdir():
        if not src.is_dir() or not src.name.startswith("case"):
            continue
        dst = preproc_dir / src.name
        dst.mkdir(parents=True, exist_ok=True)
        for fname in ("case_data.yml", "probe_timeseries.yml"):
            s = src / fname
            if s.is_file():
                shutil.copy2(s, dst / fname)
                n += 1
    return n


def write_split_csvs(preproc_dir: Path, artifacts: Path) -> dict:
    artifacts.mkdir(parents=True, exist_ok=True)
    cases = sorted(
        p for p in preproc_dir.iterdir() if p.is_dir() and p.name.startswith("case")
    )
    train, hold = [], []
    knob_train: dict[str, set] = defaultdict(set)
    knob_all: dict[str, set] = defaultdict(set)
    for c in cases:
        yml_path = c / "case_data.yml"
        yml = yaml.safe_load(yml_path.read_text()) if yml_path.is_file() else {}
        jid = _case_job_id(c)
        is_hold = jid in HOLDOUT_JOB_IDS or any(h in c.name for h in HOLDOUT_JOB_IDS)
        row = {"case_path": str(c)}
        for k in KNOB_INPUTS:
            row[k] = yml.get(k, "")
            knob_all[k].add(yml.get(k))
            if not is_hold:
                knob_train[k].add(yml.get(k))
        (hold if is_hold else train).append(row)

    def dump(path: Path, rows: list[dict]) -> None:
        if not rows:
            path.write_text("case_path\n")
            return
        fields = ["case_path"] + KNOB_INPUTS
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    dump(artifacts / "training.csv", train)
    dump(artifacts / "test.csv", hold)
    dump(artifacts / "all_cases.csv", train + hold)

    frozen = {
        k: sorted(v, key=lambda x: str(x))
        for k, v in knob_train.items()
        if len(v) <= 1
    }
    return {
        "n_train": len(train),
        "n_holdout": len(hold),
        "holdout_cases": [r["case_path"] for r in hold],
        "train_unique_knobs": {k: len(v) for k, v in knob_train.items()},
        "frozen_train_knobs": frozen,
        "all_unique_knobs": {k: len(v) for k, v in knob_all.items()},
    }


def fill_hydra_yaml(preproc_dir: Path, yaml_path: Path) -> None:
    text = yaml_path.read_text(encoding="utf-8")
    text = text.replace("PLACEHOLDER_PREPROCESSED", str(preproc_dir))
    yaml_path.write_text(text, encoding="utf-8")


def main() -> int:
    ds = _hps_datasets() / DATASET_NAME
    if not ds.is_dir():
        print(f"dataset not found: {ds}", file=sys.stderr)
        return 1

    print(f"dataset={ds}", flush=True)
    already = ds / "preprocessed"
    if already.is_dir() and any(already.iterdir()):
        print("preprocessed already exists; skipping decimate", flush=True)
    else:
        print("=== decimate_dataset --target-points", DECIMATE_TARGET_POINTS, flush=True)
        cmd = [
            "decimate_dataset",
            DATASET_NAME,
            "--source-version",
            "0",
            "--target-points",
            str(DECIMATE_TARGET_POINTS),
            "--name",
            f"n_points {DECIMATE_TARGET_POINTS}",
            "--notes",
            "A10G GeoT train; same target as last holdout",
            "--sequential",
        ]
        subprocess.check_call(cmd)

    preproc_root = ds / "preprocessed"
    versions = sorted(p for p in preproc_root.iterdir() if p.is_dir()) if preproc_root.is_dir() else []
    if not versions:
        print("no preprocessed dir after decimate", file=sys.stderr)
        return 1
    preproc = versions[-1]
    print(f"preprocessed={preproc}", flush=True)

    n_copied = copy_yaml_into_preprocessed(ds / "cases", preproc)
    print(f"copied yaml files={n_copied}", flush=True)

    artifacts = Path("/enc/udeprod_cXBNn/mclaren_holdout_c9_c3/models/geo-global-ts/versions/0/artifacts")
    split = write_split_csvs(preproc, artifacts)
    # also drop all_cases.csv next to eval root
    eval_root = Path("/enc/udeprod_cXBNn/mclaren_holdout_c9_c3")
    shutil.copy2(artifacts / "all_cases.csv", eval_root / "all_cases.csv")
    shutil.copy2(artifacts / "training.csv", eval_root / "training.csv")
    shutil.copy2(artifacts / "test.csv", eval_root / "test.csv")

    yaml_path = Path("/enc/udeprod_cXBNn/work/mclaren_p35_probes/scripts/mclaren_holdout_p35.yaml")
    fill_hydra_yaml(preproc, yaml_path)
    conf_copy = Path(
        "/enc/udeprod_cXBNn/work/rescale-ai/rescale_ai/solver/transient/conf/mclaren_holdout_p35.yaml"
    )
    shutil.copy2(yaml_path, conf_copy)

    report = {
        "dataset": str(ds),
        "preprocessed": str(preproc),
        "holdout_job_ids": HOLDOUT_JOB_IDS,
        "holdout_reasons": HOLDOUT_REASONS,
        "global_output_dim": len(GLOBAL_OUTPUT_BASES),
        "num_time_steps": NUM_TIME_STEPS,
        "split": split,
    }
    (eval_root / "prepare_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    if split["n_holdout"] != 2 or split["n_train"] != 16:
        print("ERROR unexpected split sizes", file=sys.stderr)
        return 2
    caused_by_holdout = {
        k: v
        for k, v in (split["frozen_train_knobs"] or {}).items()
        if int(split["all_unique_knobs"].get(k, 0)) > 1
    }
    if caused_by_holdout:
        print(
            "ERROR holding out would freeze knobs:",
            caused_by_holdout,
            file=sys.stderr,
        )
        return 3
    if split["frozen_train_knobs"]:
        print(
            "NOTE constant knobs in the whole DOE (not caused by holdout):",
            split["frozen_train_knobs"],
            flush=True,
        )
    print("READY_TO_TRAIN", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
