#!/usr/bin/env python3
"""Patch versionMetadata.yaml so probes are global outputs, displacement nodal-only.

Use on an already-initialized fea-deform dataset *after*
``convert_probes_to_global_ts.py`` has written ``timeseries`` into each
``case_data.yml``.

This does **not** teach Transient to train yet (Phase 2). It only aligns
metadata flags for the eventual model version / re-init.

Usage::

    python scripts/patch_version_metadata_probe_globals.py \\
        /enc/.../datasets/mclaren-p35-side-pole-19/versions/0

Disables node outputs whose base name is in
{acceleration, force, moment, rib_defl}. Leaves displacement enabled.
Ensures globalVariables entries exist for each timeseries channel base
as type=output (platform may still require ``_t*`` names — Phase 2 wires that).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

_PROBE_NODE_BASES = {"acceleration", "force", "moment", "rib_defl"}
_TIME_RE = re.compile(r"^(?P<base>.+)_t\d+(?:\.\d+)?$")


def _base(name: str) -> str:
    m = _TIME_RE.match(name)
    return m.group("base") if m else name


def collect_timeseries_keys(dataset_version: Path) -> List[str]:
    keys: Set[str] = set()
    search_roots = [dataset_version]
    # Platform layout: cases/ live next to versions/, not inside versions/0
    sibling_cases = dataset_version.parent.parent / "cases"
    if sibling_cases.is_dir():
        search_roots.append(sibling_cases)
    parent_cases = dataset_version.parent / "cases"
    if parent_cases.is_dir():
        search_roots.append(parent_cases)

    for root in search_roots:
        for yml in root.rglob("case_data.yml"):
            data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
            ts = data.get("timeseries") or {}
            for k in ts:
                if k != "times":
                    keys.add(k)
    return sorted(keys)


def patch_metadata(meta_path: Path, channel_keys: List[str]) -> Dict[str, Any]:
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    variables = meta.setdefault("variables", {})
    node_vars: List[Dict[str, Any]] = list(variables.get("nodeVariables") or [])
    global_vars: List[Dict[str, Any]] = list(variables.get("globalVariables") or [])

    disabled_nodes = []
    for var in node_vars:
        base = _base(var.get("name", ""))
        if base in _PROBE_NODE_BASES:
            var["enabled"] = False
            disabled_nodes.append(var.get("name"))

    existing_global = {v.get("name"): v for v in global_vars}
    added = []
    for key in channel_keys:
        # Store unsuffixed channel name; Phase 2 maps these to outvar_ts_keys.
        if key in existing_global:
            existing_global[key]["type"] = "output"
            existing_global[key]["enabled"] = True
        else:
            entry = {
                "name": key,
                "type": "output",
                "enabled": True,
                "unit": "",
                "description": "McLaren probe global time series (from case_data.yml timeseries)",
            }
            global_vars.append(entry)
            added.append(key)

    variables["nodeVariables"] = node_vars
    variables["globalVariables"] = global_vars
    meta["variables"] = variables
    meta_path.write_text(
        yaml.safe_dump(meta, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return {
        "disabled_node_outputs": len(disabled_nodes),
        "added_global_outputs": added,
        "channel_count": len(channel_keys),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dataset_version",
        type=Path,
        help="Path to dataset version dir (contains versionMetadata.yaml + cases/)",
    )
    args = parser.parse_args(argv)
    root = args.dataset_version.resolve()
    meta_path = root / "versionMetadata.yaml"
    if not meta_path.is_file():
        # some layouts use versionMetadata.yml
        alt = root / "versionMetadata.yml"
        if alt.is_file():
            meta_path = alt
        else:
            print(f"Missing versionMetadata.yaml under {root}", file=sys.stderr)
            return 1

    channels = collect_timeseries_keys(root)
    if not channels:
        print(
            "No timeseries channels found in case_data.yml files. "
            "Run convert_probes_to_global_ts.py first.",
            file=sys.stderr,
        )
        return 1

    summary = patch_metadata(meta_path, channels)
    print(f"Patched {meta_path}")
    print(
        f"  channels={summary['channel_count']} "
        f"disabled_probe_node_fields≈{summary['disabled_node_outputs']} "
        f"added_globals={len(summary['added_global_outputs'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
