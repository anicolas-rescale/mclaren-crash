#!/usr/bin/env python3
"""Prep McLaren scratch for re-initialize_dataset.

1. Ensure scratch cases have timeseries (copy yml from datasets if needed)
2. Rename timeseries.times -> timeseries.timesteps
3. Print a short readiness summary

Run ON the workstation::

    python3 /enc/udeprod_ZUKEb/mclaren_probe_convert/prep_scratch_for_reinit.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

HPS = Path("/enc/udeprod_ZUKEb/storage_wtaTdb")
DS = HPS / "datasets" / "mclaren-p35-side-pole-19"
SC = HPS / "scratch" / "mclaren-p35-side-pole-19"


def case_dirs(root: Path) -> list[Path]:
    cases = root / "cases"
    if not cases.is_dir():
        return []
    return sorted(p for p in cases.glob("case*") if p.is_dir())


def has_timeseries(yml: Path) -> bool:
    if not yml.is_file():
        return False
    data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
    ts = data.get("timeseries")
    return isinstance(ts, dict) and any(k not in ("times", "timesteps") for k in ts)


def rename_times_key(yml: Path) -> str:
    """Return 'renamed' | 'already' | 'missing' | 'noop'."""
    data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
    ts = data.get("timeseries")
    if not isinstance(ts, dict):
        return "missing"
    if "timesteps" in ts and "times" not in ts:
        return "already"
    if "times" not in ts:
        return "noop"
    ts["timesteps"] = ts.pop("times")
    data["timeseries"] = ts
    yml.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=None),
        encoding="utf-8",
    )
    return "renamed"


def main() -> int:
    print(f"datasets: {DS} exists={DS.is_dir()}")
    print(f"scratch:  {SC} exists={SC.is_dir()}")

    ds_cases = case_dirs(DS)
    sc_cases = case_dirs(SC)
    print(f"datasets cases: {len(ds_cases)}")
    print(f"scratch cases:  {len(sc_cases)}")

    if not ds_cases:
        print("ERROR: no cases under datasets/; nothing to sync from")
        return 1

    # Create scratch skeleton if missing
    if not SC.exists():
        print("Creating scratch directory skeleton...")
        (SC / "cases").mkdir(parents=True, exist_ok=True)

    # Sync case_data.yml from datasets -> scratch when scratch lacks timeseries
    copied = 0
    skipped = 0
    for ds_case in ds_cases:
        name = ds_case.name
        sc_case = SC / "cases" / name
        sc_case.mkdir(parents=True, exist_ok=True)
        src = ds_case / "case_data.yml"
        dst = sc_case / "case_data.yml"
        if not src.is_file():
            print(f"WARN missing source yml: {src}")
            continue
        if has_timeseries(dst):
            skipped += 1
            continue
        # Backup existing scratch yml if present and different
        if dst.is_file():
            bak = sc_case / "case_data.yml.bak_pre_timeseries_sync"
            if not bak.exists():
                shutil.copy2(dst, bak)
        shutil.copy2(src, dst)
        copied += 1
        print(f"copied yml -> {dst}")

    print(f"yml sync: copied={copied} already_had_timeseries={skipped}")

    # Rename times -> timesteps on both trees (datasets + scratch)
    stats = {"renamed": 0, "already": 0, "missing": 0, "noop": 0}
    for root_label, root in (("datasets", DS), ("scratch", SC)):
        for case in case_dirs(root):
            yml = case / "case_data.yml"
            if not yml.is_file():
                stats["missing"] += 1
                continue
            result = rename_times_key(yml)
            stats[result] = stats.get(result, 0) + 1
            if result == "renamed":
                print(f"renamed times->timesteps: {root_label}/{case.name}")

    print(f"rename stats: {stats}")

    # Final readiness
    sc_ready = sum(
        1 for c in case_dirs(SC) if has_timeseries(c / "case_data.yml")
    )
    print()
    print(f"READY scratch cases with timeseries: {sc_ready}/{len(case_dirs(SC))}")
    if sc_ready == 0:
        print("ERROR: scratch still has no timeseries; abort before initialize")
        return 1

    # Spot-check one case
    sample = next(c for c in case_dirs(SC) if has_timeseries(c / "case_data.yml"))
    data = yaml.safe_load((sample / "case_data.yml").read_text(encoding="utf-8"))
    ts = data["timeseries"]
    keys = [k for k in ts if k not in ("times", "timesteps")]
    print(f"sample {sample.name}: timesteps={'timesteps' in ts} G={len(keys)} T={len(ts.get('timesteps') or ts.get('times') or [])}")
    print()
    print("Next (in notebook):")
    print("  builder.initialize_dataset(name='mclaren-p35-side-pole-19', dataset_type='fea-deform', surface_file_name='case_data.vtp', num_workers=1)")
    print("  builder.validate_dataset('mclaren-p35-side-pole-19', num_workers=1)")
    print("After init: disable the junk 'timesteps' time-series group in the UI if it appears.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
