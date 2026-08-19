#!/usr/bin/env python3
"""Enable geometry knobs + selected nodal/global outputs on versionMetadata.yaml."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    GLOBAL_OUTPUT_BASES,
    KNOB_DISABLE,
    KNOB_INPUTS,
    NODE_OUTPUT_BASES,
)

_TIME_RE = re.compile(r"^(?P<base>.+)_t\d+(?:\.\d+)?$")


def _base(name: str) -> str:
    m = _TIME_RE.match(name)
    return m.group("base") if m else name


def patch(meta: dict[str, Any]) -> dict[str, Any]:
    variables = meta.setdefault("variables", {})
    node_vars = list(variables.get("nodeVariables") or [])
    global_vars = list(variables.get("globalVariables") or [])

    global_wanted = set(KNOB_INPUTS) | set(GLOBAL_OUTPUT_BASES)
    report = {
        "node_enabled": [],
        "node_disabled": [],
        "global_input_enabled": [],
        "global_output_enabled": [],
        "global_disabled": [],
        "missing_knobs": [],
        "missing_globals": [],
        "unexpected_enabled_globals": [],
    }

    for var in node_vars:
        name = var.get("name") or ""
        base = _base(name)
        if base in NODE_OUTPUT_BASES:
            var["enabled"] = True
            var["type"] = "output"
            report["node_enabled"].append(name)
        else:
            var["enabled"] = False
            report["node_disabled"].append(name)

    present_bases = {_base(v.get("name") or "") for v in global_vars}
    present_names = {v.get("name") for v in global_vars}

    for knob in KNOB_INPUTS:
        if knob not in present_names and knob not in present_bases:
            report["missing_knobs"].append(knob)

    for gbase in GLOBAL_OUTPUT_BASES:
        # After init, globals are expanded to name_t0.000 etc.
        if gbase not in present_names and not any(
            _base(n or "") == gbase for n in present_names
        ):
            report["missing_globals"].append(gbase)

    for var in global_vars:
        name = var.get("name") or ""
        base = _base(name)
        if name in KNOB_DISABLE or base in KNOB_DISABLE:
            var["enabled"] = False
            report["global_disabled"].append(name)
            continue
        if name in KNOB_INPUTS or base in KNOB_INPUTS:
            var["enabled"] = True
            var["type"] = "input"
            report["global_input_enabled"].append(name)
            continue
        if base in GLOBAL_OUTPUT_BASES or name in GLOBAL_OUTPUT_BASES:
            var["enabled"] = True
            var["type"] = "output"
            report["global_output_enabled"].append(name)
            continue
        var["enabled"] = False
        report["global_disabled"].append(name)

    variables["nodeVariables"] = node_vars
    variables["globalVariables"] = global_vars
    meta["variables"] = variables
    return report


def find_meta(dataset_root: Path) -> Path:
    for candidate in (
        dataset_root / "versions" / "0" / "versionMetadata.yaml",
        dataset_root / "versions" / "0" / "versionMetadata.yml",
        dataset_root / "versionMetadata.yaml",
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"No versionMetadata.yaml under {dataset_root}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "dataset_root",
        type=Path,
        help="datasets/<name> directory (contains versions/0)",
    )
    args = parser.parse_args(argv)
    meta_path = find_meta(args.dataset_root.resolve())
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    report = patch(meta)
    meta_path.write_text(
        yaml.safe_dump(meta, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    out = meta_path.parent / "variable_enable_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"patched {meta_path}")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}, indent=2))
    if report["missing_knobs"] or report["missing_globals"]:
        print("MISSING knobs:", report["missing_knobs"])
        print("MISSING globals:", report["missing_globals"])
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
